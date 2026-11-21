"""Loads the three Gold tables, from Databricks (SQL warehouse) or from bundled CSV files.

Mode selection
--------------
* DATA_SOURCE=databricks  -> query the Gold tables through a Databricks SQL warehouse.
                             Used automatically when DATABRICKS_WAREHOUSE_ID is set
                             (app.yaml sets it inside a Databricks App).
* DATA_SOURCE=csv         -> read data/gold_*.csv (default on a laptop).

If the Databricks query fails (missing permission, stopped warehouse, ...), the
loader falls back to the CSV files and reports why, so a live demo never ends
on an empty page.
"""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

TABLES = ("gold_monthly_sales", "gold_country_sales", "gold_customer_summary")
DATA_DIR = Path(__file__).parent / "data"

NUMERIC_COLUMNS = {
    "gold_monthly_sales": ["gross_sales", "cancellations", "net_revenue", "orders", "active_customers",
                           "trading_days", "avg_order_value", "cancellation_rate_pct",
                           "net_revenue_per_trading_day", "mom_change_pct"],
    "gold_country_sales": ["gross_sales", "net_revenue", "orders", "customers", "revenue_share_pct",
                           "revenue_rank", "cumulative_share_pct"],
    "gold_customer_summary": ["gross_sales", "net_revenue", "orders", "avg_order_value",
                              "days_since_last_purchase", "revenue_rank", "revenue_share_pct",
                              "cumulative_share_pct"],
}
DATE_COLUMNS = {
    "gold_monthly_sales": ["month_start"],
    "gold_country_sales": [],
    "gold_customer_summary": ["first_purchase", "last_purchase"],
}


def requested_mode() -> str:
    mode = os.getenv("DATA_SOURCE", "").strip().lower()
    if mode in ("csv", "databricks"):
        return mode
    return "databricks" if os.getenv("DATABRICKS_WAREHOUSE_ID") else "csv"


def gold_schema() -> str:
    # Databricks Free Edition creates tables in the "workspace" catalog by default.
    return os.getenv("GOLD_SCHEMA", "workspace.evaluated_exercise3")


def _normalise(name: str, df: pd.DataFrame) -> pd.DataFrame:
    """Give both sources identical dtypes (SQL returns Decimals, CSV returns text for dates)."""
    df = df.copy()
    for col in NUMERIC_COLUMNS[name]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in DATE_COLUMNS[name]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col])
    if "is_partial_month" in df.columns:
        df["is_partial_month"] = df["is_partial_month"].astype(str).str.lower().eq("true")
    for col in ("customer_id",):
        if col in df.columns:
            df[col] = df[col].astype(str)
    return df


def load_csv() -> dict[str, pd.DataFrame]:
    return {t: _normalise(t, pd.read_csv(DATA_DIR / f"{t}.csv", dtype={"customer_id": str}))
            for t in TABLES}


def load_databricks() -> dict[str, pd.DataFrame]:
    # Imported here so a laptop run in CSV mode needs only streamlit, pandas and plotly.
    from databricks import sql
    from databricks.sdk.core import Config

    cfg = Config()  # Inside a Databricks App this picks up the app's own credentials.
    host = cfg.host.replace("https://", "").replace("http://", "").rstrip("/")
    warehouse_id = os.environ["DATABRICKS_WAREHOUSE_ID"]
    frames = {}
    with sql.connect(server_hostname=host,
                     http_path=f"/sql/1.0/warehouses/{warehouse_id}",
                     credentials_provider=lambda: cfg.authenticate) as conn:
        with conn.cursor() as cur:
            for t in TABLES:
                cur.execute(f"SELECT * FROM {gold_schema()}.{t}")
                frames[t] = _normalise(t, cur.fetchall_arrow().to_pandas())
    return frames


def load_gold() -> tuple[dict[str, pd.DataFrame], str, str | None]:
    """Returns (tables, source_label, warning_or_None)."""
    if requested_mode() == "databricks":
        try:
            return load_databricks(), f"Databricks SQL warehouse · {gold_schema()}", None
        except Exception as exc:  # noqa: BLE001 - any failure falls back to the snapshot
            return (load_csv(), "Bundled CSV snapshot (fallback)",
                    f"Could not query Databricks ({type(exc).__name__}: {str(exc)[:200]}). "
                    "Showing the bundled CSV snapshot of the same Gold tables instead.")
    return load_csv(), "CSV export of the Gold tables (data/)", None
