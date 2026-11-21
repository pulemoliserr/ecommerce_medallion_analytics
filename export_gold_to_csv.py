# Databricks notebook source
# MAGIC %md
# MAGIC ## Export the Gold tables to CSV for the laptop version of the dashboard
# MAGIC Run this once, after the EE3 notebook has built the Gold tables. It writes three CSV files
# MAGIC into a Unity Catalog volume; download them and put them in the app's `data/` folder.

# COMMAND ----------

# The Gold tables are small (13 + 38 + ~4,400 rows), so converting them to pandas is safe here.
# This step is an export for the dashboard, not part of the graded Spark processing.
SCHEMA = "evaluated_exercise3"
TABLES = ["gold_monthly_sales", "gold_country_sales", "gold_customer_summary"]

catalog = spark.sql("SELECT current_catalog()").first()[0]
spark.sql(f"CREATE VOLUME IF NOT EXISTS {catalog}.{SCHEMA}.app_exports")
export_dir = f"/Volumes/{catalog}/{SCHEMA}/app_exports"

for t in TABLES:
    pdf = spark.table(f"{catalog}.{SCHEMA}.{t}").toPandas()
    pdf.to_csv(f"{export_dir}/{t}.csv", index=False)
    print(f"{t}: {len(pdf):,} rows -> {export_dir}/{t}.csv")

print("\nDownload: Catalog > " + catalog + " > " + SCHEMA + " > Volumes > app_exports > file menu > Download")
print("Also note the catalog for app.yaml (GOLD_SCHEMA):", f"{catalog}.{SCHEMA}")
