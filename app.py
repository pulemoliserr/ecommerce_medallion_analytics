"""Scalable E-Commerce Analytics Platform - Streamlit dashboard on the Gold layer.

Runs unchanged on a laptop (CSV export of the Gold tables) and as a Databricks App
(live query of the Gold Delta tables through a SQL warehouse). See README.md.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from data_source import load_gold, requested_mode

NAVY, BLUE, LIGHT_BLUE, GREY, ORANGE = "#14213D", "#2B4C7E", "#9DBBDD", "#B8C1CF", "#D9731A"
PEAK_MONTHS = {"2011-09", "2011-10", "2011-11"}

st.set_page_config(page_title="E-Commerce Analytics Platform", page_icon="📊", layout="wide")


def gbp(x: float, decimals: int = 0) -> str:
    sign = "−" if x < 0 else ""
    x = abs(x)
    if x >= 1_000_000:
        return f"{sign}£{x / 1_000_000:.2f}m"
    if x >= 10_000:
        return f"{sign}£{x / 1_000:.1f}k"
    return f"{sign}£{x:,.{decimals}f}"


@st.cache_data(ttl=600, show_spinner="Loading Gold tables…")
def get_data():
    return load_gold()


tables, source_label, load_warning = get_data()
monthly = tables["gold_monthly_sales"].sort_values("month_start").reset_index(drop=True)
country = tables["gold_country_sales"].sort_values("revenue_rank").reset_index(drop=True)
customer = tables["gold_customer_summary"].sort_values("revenue_rank").reset_index(drop=True)
total_net = monthly["net_revenue"].sum()

# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.header("Filters")
    months = monthly["year_month"].tolist()
    start_m, end_m = st.select_slider("Month range", options=months, value=(months[0], months[-1]))
    include_partial = st.checkbox("Include Dec 2011 (partial: 1–9 Dec)", value=True)
    st.divider()
    st.caption("**Data source**")
    st.caption(source_label)
    st.caption(f"Mode requested: `{requested_mode()}`")
    if st.button("Reload data"):
        st.cache_data.clear()
        st.rerun()
    st.divider()
    st.caption("Pipeline: UCI Excel → Bronze → Silver → Gold (Delta, PySpark/SparkSQL on Databricks) → this app.")

if load_warning:
    st.warning(load_warning)

sel = monthly[(monthly["year_month"] >= start_m) & (monthly["year_month"] <= end_m)]
if not include_partial:
    sel = sel[~sel["is_partial_month"]]

# ---------------------------------------------------------------- header + KPIs
st.title("E-Commerce Analytics Platform")
st.caption("UK online retailer · 541,909 order lines · 1 Dec 2010 – 9 Dec 2011 · amounts in £ (assumed) · "
           "net revenue = product sales − product cancellations")

if sel.empty:
    st.info("No months in the selected range.")
    st.stop()

gross, canc, net, orders = (sel["gross_sales"].sum(), sel["cancellations"].sum(),
                            sel["net_revenue"].sum(), int(sel["orders"].sum()))
best = sel.loc[sel["net_revenue"].idxmax()]
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Net revenue", gbp(net), help="Sales minus cancellations in the selected months")
k2.metric("Orders", f"{orders:,}")
k3.metric("Avg order value", gbp(gross / orders, 2) if orders else "–")
k4.metric("Cancellation rate", f"{-100 * canc / gross:.2f}%" if gross else "–")
k5.metric("Best month", best["year_month"], gbp(best["net_revenue"]), delta_color="off", delta_arrow="off")

tab_sales, tab_country, tab_customer, tab_quality = st.tabs(
    ["📈 Sales development", "🌍 Countries", "👥 Customers", "✅ Data quality & lineage"])

# ---------------------------------------------------------------- Q1: sales over time
with tab_sales:
    metric_options = {
        "Net revenue (£)": "net_revenue",
        "Net revenue per trading day (£)": "net_revenue_per_trading_day",
        "Orders": "orders",
        "Average order value (£)": "avg_order_value",
        "Cancellation rate (%)": "cancellation_rate_pct",
    }
    label = st.radio("Measure", list(metric_options), horizontal=True)
    col = metric_options[label]
    colors = [GREY if p else (ORANGE if ym in PEAK_MONTHS else BLUE)
              for ym, p in zip(sel["year_month"], sel["is_partial_month"])]
    fig = go.Figure(go.Bar(x=sel["year_month"], y=sel[col], marker_color=colors,
                           text=[f"{v:,.0f}" if v >= 100 else f"{v:,.2f}" for v in sel[col]],
                           textposition="outside", cliponaxis=False,
                           hovertemplate="%{x}<br>%{y:,.2f}<extra></extra>"))
    fig.update_layout(height=430, margin=dict(t=30, b=10, l=10, r=10), yaxis_title=label,
                      plot_bgcolor="white", xaxis=dict(type="category"))
    fig.update_yaxes(gridcolor="#E5E8EE")
    st.plotly_chart(fig, width="stretch")
    st.caption("Orange = Sep–Nov peak · grey = Dec 2011, only 8 trading days (1–9 Dec) · blue = other months.")

    in_sel = sel["net_revenue"].sum()
    peak = sel[sel["year_month"].isin(PEAK_MONTHS)]["net_revenue"].sum()
    c1, c2 = st.columns(2)
    c1.metric("Sep–Nov share of selected net revenue", f"{100 * peak / in_sel:.1f}%" if in_sel else "–")
    full = sel[~sel["is_partial_month"]]
    if not full.empty:
        low = full.loc[full["net_revenue"].idxmin()]
        c2.metric("Weakest full month", low["year_month"], gbp(low["net_revenue"]), delta_color="off", delta_arrow="off")
    with st.expander("Monthly Gold table"):
        st.dataframe(sel.drop(columns=["month_start"]), hide_index=True, width="stretch")

# ---------------------------------------------------------------- Q2: geography
with tab_country:
    c1, c2 = st.columns([1, 1])
    top_n = c1.slider("Countries to show", 5, 20, 10)
    exclude_uk = c2.toggle("Hide United Kingdom (zoom into export markets)", value=False)
    view = country[country["country"] != "United Kingdom"] if exclude_uk else country
    top = view.head(top_n)
    rest = view.iloc[top_n:]
    bars = pd.concat([top[["country", "net_revenue", "revenue_share_pct", "customers"]],
                      pd.DataFrame([{"country": f"{len(rest)} other countries",
                                     "net_revenue": rest["net_revenue"].sum(),
                                     "revenue_share_pct": rest["revenue_share_pct"].sum(),
                                     "customers": rest["customers"].sum()}])]) if len(rest) else top
    fig = go.Figure(go.Bar(
        x=bars["net_revenue"], y=bars["country"], orientation="h",
        marker_color=[NAVY if c == "United Kingdom" else (GREY if "other" in c else BLUE) for c in bars["country"]],
        text=[f"{s:.1f}% · {int(n)} customers" for s, n in zip(bars["revenue_share_pct"], bars["customers"])],
        textposition="outside", cliponaxis=False,
        hovertemplate="%{y}<br>£%{x:,.0f}<extra></extra>"))
    fig.update_layout(height=max(320, 34 * len(bars)), margin=dict(t=10, b=10, l=10, r=140),
                      yaxis=dict(autorange="reversed"), xaxis_title="Net revenue (£)", plot_bgcolor="white")
    fig.update_xaxes(gridcolor="#E5E8EE")
    st.plotly_chart(fig, width="stretch")
    uk = country.loc[country["country"] == "United Kingdom", "revenue_share_pct"].sum()
    c1, c2, c3 = st.columns(3)
    c1.metric("United Kingdom share", f"{uk:.1f}%")
    c2.metric("Top 5 countries share", f"{country.head(5)['revenue_share_pct'].sum():.1f}%")
    c3.metric("Countries with revenue", f"{len(country)}")
    st.caption("Shares of total net revenue. Customer counts show how many identified buyers a market rests on.")

# ---------------------------------------------------------------- Q2: customers
with tab_customer:
    n = len(customer)
    cust = customer.assign(customer_pct=100 * customer["revenue_rank"] / n)
    fig = go.Figure(go.Scatter(x=cust["customer_pct"], y=cust["cumulative_share_pct"], mode="lines",
                               line=dict(color=BLUE, width=3),
                               hovertemplate="Top %{x:.1f}% of customers<br>%{y:.1f}% of revenue<extra></extra>"))
    for pct in (1, 20):
        y = cust.loc[cust["customer_pct"] <= pct, "cumulative_share_pct"].max()
        fig.add_trace(go.Scatter(x=[pct], y=[y], mode="markers+text", marker=dict(size=12, color=ORANGE),
                                 text=[f"Top {pct}% → {y:.0f}%"], textposition="middle right",
                                 showlegend=False, hoverinfo="skip"))
    fig.update_layout(height=380, showlegend=False, margin=dict(t=10, b=10, l=10, r=10), plot_bgcolor="white",
                      xaxis_title="Share of identified customers, ranked by net revenue (%)",
                      yaxis_title="Cumulative share of identified revenue (%)")
    fig.update_xaxes(gridcolor="#E5E8EE", range=[0, 100])
    fig.update_yaxes(gridcolor="#E5E8EE")
    st.plotly_chart(fig, width="stretch")

    seg = (customer.groupby("customer_segment", as_index=False)
           .agg(customers=("customer_id", "count"), net_revenue=("net_revenue", "sum"),
                share_pct=("revenue_share_pct", "sum")))
    order = {"Top 1%": 0, "Top 2-10%": 1, "Top 11-20%": 2, "Remaining 80%": 3}
    seg = seg.sort_values("customer_segment", key=lambda s: s.map(order))
    seg = seg.assign(net_revenue=seg["net_revenue"].map(lambda v: f"£{v:,.0f}"),
                     share_pct=seg["share_pct"].map(lambda v: f"{v:.1f}%"),
                     customers=seg["customers"].map(lambda v: f"{v:,}"))
    seg.columns = ["Segment", "Customers", "Net revenue", "Share of identified revenue"]
    c1, c2 = st.columns([1, 1])
    with c1:
        st.subheader("Customer segments")
        st.dataframe(seg, hide_index=True, width="stretch")
        coverage = 100 * customer["net_revenue"].sum() / total_net
        st.caption(f"Identified customers cover {coverage:.1f}% of net revenue; "
                   f"{100 - coverage:.1f}% has no customer ID.")
    with c2:
        st.subheader("Key accounts at risk")
        days = st.slider("No purchase for more than … days", 7, 180, 60, step=7)
        risk = customer[customer["customer_segment"].isin(["Top 1%", "Top 2-10%"])
                        & (customer["days_since_last_purchase"] > days)]
        st.metric("Top-10% customers without a recent order", f"{len(risk)}",
                  f"{gbp(risk['net_revenue'].sum())} of revenue", delta_color="off", delta_arrow="off")
        st.dataframe(risk[["customer_id", "main_country", "net_revenue", "orders", "last_purchase",
                           "days_since_last_purchase"]].head(15),
                     hide_index=True, width="stretch",
                     column_config={
                         "net_revenue": st.column_config.NumberColumn("Net revenue", format="£%,.0f"),
                         "last_purchase": st.column_config.DateColumn("Last purchase", format="YYYY-MM-DD"),
                         "days_since_last_purchase": st.column_config.NumberColumn("Days since"),
                         "customer_id": "Customer", "main_country": "Country", "orders": "Orders"})

# ---------------------------------------------------------------- trust
with tab_quality:
    st.subheader("Live consistency checks on the Gold tables")
    checks = [
        ("Monthly and country tables report the same net revenue",
         abs(monthly["net_revenue"].sum() - country["net_revenue"].sum()) < 0.005,
         f"£{monthly['net_revenue'].sum():,.2f} vs £{country['net_revenue'].sum():,.2f}"),
        ("13 months, Dec 2010 – Dec 2011", len(monthly) == 13, f"{len(monthly)} months"),
        ("Only Dec 2011 flagged as partial", monthly.loc[monthly["is_partial_month"], "year_month"].tolist() == ["2011-12"],
         ", ".join(monthly.loc[monthly["is_partial_month"], "year_month"])),
        ("One row per customer", customer["customer_id"].is_unique, f"{len(customer):,} customers"),
        ("Country shares add up to 100%", abs(country["revenue_share_pct"].sum() - 100) < 0.1,
         f"{country['revenue_share_pct'].sum():.2f}%"),
    ]
    st.dataframe(pd.DataFrame([{"check": c, "passed": "✅ yes" if ok else "❌ no", "evidence": e}
                               for c, ok, e in checks]), hide_index=True, width="stretch")
    st.subheader("Lineage")
    st.markdown(
        "| Layer | Content | Rows |\n|---|---|---:|\n"
        "| Source | UCI Online Retail Excel, loaded once | 541,909 |\n"
        "| Bronze | Unchanged copy (audit trail) | 541,909 |\n"
        "| Silver | Exact duplicates removed (5,268); cancellations, fees, adjustments flagged, not deleted | 536,641 |\n"
        f"| Gold | Monthly · country · customer tables, one revenue rule | {len(monthly)} · {len(country)} · {len(customer):,} |")
    st.caption("All transformations run in PySpark/SparkSQL on Databricks; every Gold total was reconciled "
               "to Silver to the penny (£9,778,989.97) in the pipeline notebook.")
