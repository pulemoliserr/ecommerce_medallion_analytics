# E-Commerce Analytics Platform — Streamlit dashboard

A Streamlit dashboard on the Gold layer of the Medallion pipeline (Evaluated Exercise 3).
The same code runs in two places:

| Where | Data source | How it is chosen |
|---|---|---|
| Your laptop | `data/gold_*.csv` (export of the Gold tables) | default |
| Databricks App | Live query of `workspace.evaluated_exercise3.gold_*` via the SQL warehouse | `DATABRICKS_WAREHOUSE_ID` is set by `app.yaml` |

If the live Databricks query fails (missing permission, warehouse stopped), the app shows a
yellow notice and falls back to the bundled CSV snapshot, so the demo never shows an empty page.

```
ecommerce_analytics_app/
├── app.py                 dashboard (4 tabs)
├── data_source.py         loads Gold tables from Databricks or CSV
├── app.yaml               Databricks App start command + environment
├── requirements.txt       Python packages
├── .streamlit/config.toml colours
├── export_gold_to_csv.py  Databricks notebook cell: Gold tables -> CSV
└── data/                  gold_monthly_sales.csv, gold_country_sales.csv, gold_customer_summary.csv
```

The bundled CSVs were produced by the same tested pipeline on the same UCI data and match the
notebook's results (net revenue £9,778,989.97). To use your own export, run
`export_gold_to_csv.py` in Databricks and replace the three files in `data/`.

## A. Run on your laptop

Needs Python 3.10 or newer.

```bash
cd ecommerce_analytics_app
python -m venv .venv
# Windows:  .venv\Scripts\activate        macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

The browser opens at http://localhost:8501. The sidebar shows *Data source: CSV export of the Gold tables*.

## B. Run as a Databricks App (Free Edition allows up to 3 apps)

1. **Upload the folder.** Workspace → your user folder → **Create → Folder** `ecommerce_analytics_app` →
   open it → **⋮ → Import** → upload `app.py`, `data_source.py`, `app.yaml`, `requirements.txt`.
   Create a sub-folder `data` and import the three CSV files into it (needed for the fallback).
   `.streamlit/config.toml` is optional (colours only).
2. **Create the app.** Left sidebar **Compute → Apps → Create app → Create a custom app**.
   Name it e.g. `ecommerce-analytics`. Under **App resources → Add resource → SQL warehouse**:
   choose your Serverless Starter Warehouse, permission **Can use**, resource key **`sql-warehouse`**
   (must match `app.yaml`). Click **Create app**.
3. **Deploy.** On the app page click **Deploy** and select the workspace folder from step 1.
   The first deployment installs the packages (2–5 minutes).
4. **Give the app read access to the Gold tables.** On the app page, open **Authorization** and copy the
   app's **service principal** application ID. In a SQL editor or notebook cell run (replace the ID):

   ```sql
   GRANT USE CATALOG ON CATALOG workspace TO `<service-principal-application-id>`;
   GRANT USE SCHEMA  ON SCHEMA  workspace.evaluated_exercise3 TO `<service-principal-application-id>`;
   GRANT SELECT      ON SCHEMA  workspace.evaluated_exercise3 TO `<service-principal-application-id>`;
   ```

5. **Open the app URL.** The sidebar should read *Databricks SQL warehouse · workspace.evaluated_exercise3*.
   If it reads *Bundled CSV snapshot (fallback)*, the yellow notice at the top says why (usually step 4).

If your tables live in another catalog, change `GOLD_SCHEMA` in `app.yaml` (the export cell prints the right value).

**Free Edition stops apps automatically after a while.** Before presenting, open the app page and
click **Start** if it is stopped; starting takes a few minutes.

## The four tabs

1. **Sales development** — monthly bars (Sep–Nov peak in orange, partial Dec 2011 in grey), five measures.
2. **Countries** — top N markets, option to hide the UK to zoom into export markets, customers per market.
3. **Customers** — concentration curve (top 1% → 30%, top 20% → 74%), segments, key accounts at risk.
4. **Data quality & lineage** — live consistency checks on the Gold tables and the Bronze→Gold row counts.
