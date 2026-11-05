# Supplied workbook audit and mapping

Source: `data/source/LittleLemon_data.xlsx`, an unchanged copy of the workbook
supplied with this assignment. Its SHA-256 is recorded in
[workbook_profile.json](workbook_profile.json) and [workbook_expected.json](workbook_expected.json).
The workbook is the source for the imported customer, menu, order, and delivery
records. Its contents are not replaced with the separate sales-report project's
fictional dataset.

## Actual workbook structure

- One sheet: **Orders**.
- Used range: **A1:U21001**.
- **21 columns**, **21,000 data rows**, and **0 formula cells**.
- **0 missing values** in every source column.
- Excel's declared **1900 date system** is used for date conversion.
- There are **21,000 unique Row Number values** and no exact duplicate rows.
- There are only **1,000 distinct source Order ID values**, each occurring **21 times**.
  These repeats differ in Postal Code, Cost, Sales, and Discount. They must not be
  discarded or collapsed into 1,000 orders without a course-supplied explanation.
- The 1,000 source Customer IDs have stable name, city, country, and country-code
  attributes. They are normalized into 1,000 Customers rows.
- There are **72 unique menu bundles**, **30 role-specific menu items**, and
  **360 menu-component relationships**.

## Columns, types, missing values, and field mapping

All columns have zero missing values. Complete per-column uniqueness and XLSX
storage-type counts are in `workbook_profile.json`.

| Source column | Observed / imported type | Mapping and handling |
| --- | --- | --- |
| Row Number | Numeric integer → INT | `Orders.OrderID`, unique source-row identity |
| Order ID | Text → VARCHAR(32) | `Orders.SourceOrderID`, indexed but deliberately not unique |
| Order Date | Excel numeric date → DATE | `Orders.OrderDate`, actual date conversion |
| Delivery Date | Excel numeric date → DATE | `OrderDeliveryStatus.DeliveryDate`, dates preserved |
| Customer ID | Text → VARCHAR(32) | `Customers.CustomerID` and `Orders.CustomerID` FK |
| Customer Name | Text → VARCHAR(150) | `Customers.CustomerName` |
| City | Text → VARCHAR(150) | `Customers.City` |
| Country | Text → VARCHAR(150) | `Customers.Country` |
| Postal Code | 8,648 text / 12,352 numeric cells → VARCHAR(64) | `Orders.PostalCodeRaw`; exact XML value retained as text |
| Country Code | Text → VARCHAR(8) | `Customers.CountryCode` |
| ` Cost` | Numeric → DECIMAL(18,4) | Strip header's leading space; `Orders.Cost` |
| Sales | Numeric → DECIMAL(18,4) | `Orders.Sales`; preserve genuine fractional cents |
| Quantity | Numeric integer → INT | `Orders.Quantity`, maximum 3, total 44,625 |
| Discount | Numeric → DECIMAL(18,4) | `Orders.Discount`; meaning/unit not supplied |
| Delivery Cost | Numeric → DECIMAL(18,4) | `Orders.DeliveryCost` |
| Course Name | Text → VARCHAR(150) | `MenuItems.ItemName`, role `Course` |
| Cuisine Name | Text → VARCHAR(100) | `Menus.CuisineName` |
| Starter Name | Text → VARCHAR(150) | `MenuItems.ItemName`, role `Starter` |
| Desert Name | Text → VARCHAR(150) | Source spelling mapped to internal DessertName, role `Dessert`; original values unchanged |
| Drink | Text → VARCHAR(150) | `MenuItems.ItemName`, role `Drink` |
| Sides | Text → VARCHAR(150) | `MenuItems.ItemName`, role `Side` |

Menus are bundles of the actual course, starter, dessert, drink, and side names
under one cuisine. A deterministic SHA-256 `BundleKey` identifies that complete
combination; sorted bundle/item values produce deterministic numeric keys.

## Data-quality findings preserved rather than invented away

**Delivery dates:** 9,366 source rows have a delivery date earlier than their order
date. The order-date range is 2019-06-14 through 2023-01-06; delivery dates run from
2019-10-10 through 2023-01-07. The importer preserves these dates. Analysis can flag
those rows, but there is no evidence for a corrected delivery date or a realistic
delivery-duration interpretation.

**Postal codes:** 3,701 raw values begin with a minus sign; numeric values also
include fractions. These are not silently converted into valid geographic codes.
Postal data varies within source customer IDs and therefore stays on each source
order row, not on the stable Customers dimension. Geographic views should use the
provided Country/City fields and treat postal mapping as unverified.

**Money precision:** Excel stores binary-serialization artifacts such as
`36.369999999999997`. The importer reads the underlying XML numeric text into
`Decimal` and rounds only beyond four decimal places with `ROUND_HALF_UP`.
That removes representation noise while preserving 5,726 Sales values with genuine
fractional cents. Summing four-decimal Sales yields **4,631,847.0300**. Rounding each
source row to two decimals first would yield **4,631,847.04** instead. Reports must
aggregate four-decimal amounts first and round only for display.

| Workbook measure | Imported sum, four decimal places |
| --- | ---: |
| Cost | 3,087,898.0200 |
| Sales | 4,631,847.0300 |
| Discount | 1,032,361.9800 |
| Delivery Cost | 1,070,484.6600 |

The workbook does not specify currency or explain whether Discount is a percentage,
a currency amount, or already included in Sales. No currency, net sales, margin,
or profit semantics are invented. In particular, component prices and component
quantities cannot be derived from an order's bundle-level Sales and Quantity.

## Boundaries and import safety

The workbook contains no booking IDs, table assignments, employees, customer
contact details, or delivery-status labels. The project therefore does not invent
employee rows, contact fields, component prices, or separate order-item quantities.
The required Bookings table is supported by clearly labeled supplemental booking
fixtures, kept separate from workbook-derived order data.

`python/import_workbook.py:import_workbook` uses connections acquired through the
project pool. It inserts missing identities in one transaction and commits only
when all six imported tables succeed. Existing matching rows are skipped. An
existing identity with different values raises an import conflict and rolls back;
it is never overwritten. Unrelated existing records are preserved. The unchanged
source workbook remains available to inspect all original values and transformations.
