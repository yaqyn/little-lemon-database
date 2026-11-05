# Tableau-ready data and reproduction

**Tableau Desktop execution: NOT VERIFIED.** No Tableau Desktop executable or
Tableau application connector is accessible in this environment. No `.twb` or
`.twbx` file is fabricated. The CSV files were generated from the actual deployed
MySQL data and are independently reconciled to the supplied workbook.

## Files and grain

| File | Grain | Intended use |
| --- | --- | --- |
| `order_facts.csv` | One row per source Row Number; 21,000 rows | Main analysis source with customer, menu-bundle and delivery fields |
| `bookings.csv` | One row per booking; initially four clearly labeled fixtures | Demonstration booking views; not workbook booking history |
| `menu_components.csv` | One menu/role/component; 360 rows | Menu composition reference, not an order revenue fact |
| `sales_by_month.csv` | One recorded order month; 44 rows | Reconciled monthly source-measure summary |
| `sales_by_cuisine.csv` | One cuisine; three rows | Reconciled source-measure summary |

`export_manifest.json` records exact columns, counts, file SHA-256 values, and
source-workbook SHA-256. Regenerate with:

```bash
python python/tableau_export.py
```

## Meaning and quality limits

The workbook has 21,000 rows but only 1,000 source Order ID values, each repeated
with differing measures. `OrderRecordID` is the unique workbook Row Number.
`SourceOrderID` remains a nonunique source attribute. Count records with
`COUNT([OrderRecordID])`; do not label that count as verified unique transactions.
`COUNTD([SourceOrderID])` gives 1,000 source identifiers, not proof that all other
rows should be removed.

The workbook does not identify currency or explain Discount units. Label Sales,
Cost and DeliveryCost as **source units**. Do not apply an invented percentage
interpretation, subtract Discount again, convert currency, or claim verified
restaurant profit. Monetary measures retain four decimal places because genuine
half-cent values occur; round only the displayed aggregate if desired.

`PostalCodeRaw` must be a string, including negative/fractional source values.
It is not a validated geographic postal code. `DeliveryBeforeOrder` flags 9,366
source records; the dates are preserved rather than guessed into a new order.

## Desktop steps to create a genuine workbook

1. Open Tableau Desktop and choose **Text file**, selecting `order_facts.csv`.
2. Check the field types against `field_mappings.json`. Keep identifiers and
   PostalCodeRaw as strings/dimensions. Set OrderDate and DeliveryDate to Date;
   Quantity to whole number; the four monetary measures to decimal.
3. Build **Source records over time**: month of OrderDate on Columns and count of
   OrderRecordID on Rows. Title it as workbook records, not unique transactions.
4. Build **Sales measure by month**: month of OrderDate and SUM(Sales). Axis label:
   `Sales (source units)`. Reconcile the grand total to **4,631,847.0300**.
5. Build **Cuisine summary**: CuisineName and SUM(Sales), with count of source
   records in tooltips. This uses the flattened fact's one-row-per-record grain.
6. Build **Date quality**: use `DeliveryBeforeOrder = 1` and show the count of
   OrderRecordID; it must be **9,366**. Do not silently discard these records.
7. Add `bookings.csv` as a **separate data source**. Build a date/table booking
   view and label the dashboard panel **Supplemental demonstration bookings**.
8. Place the views on a dashboard with notes explaining unknown currency,
   repeated source IDs and anomalous dates. Use clear source-unit labels.
9. Save a real `.twb`, then **File > Export Packaged Workbook** to create `.twbx`.
   Close and reopen it in Tableau, confirm that data is included, and verify the
   counts/totals before describing Tableau as tested.

**Avoid fan-out:** never physically join all five MenuComponents rows to each
order and then sum Sales. That multiplies sales by five. The provided fact CSV
pivots components to columns before joining, preserving exactly 21,000 rows.
If modeling multiple sources in Tableau, use appropriate logical relationships
and independently reconcile the fact measure totals.
