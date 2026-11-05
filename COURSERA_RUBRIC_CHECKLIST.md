# Little Lemon database: peer-grade rubric checklist

This checklist evaluates the eight criteria supplied with the assignment, using
the deployed MySQL database and the actual supplied workbook. It does not claim
access to hidden grader rules or an unavailable detailed lab-signature sheet.
Procedure signatures are documented in README.md and verified against the
supplied baseline. The provided deadline is November 16, 23:59 UTC+03:00.

| # | Criterion | Status | File and supporting evidence |
| --- | --- | --- | --- |
| 1 | GitHub repository successfully created | PASS | Verified public repository: https://github.com/yaqyn/little-lemon-database. GitHub API confirms the repository and main branch. |
| 2 | Appropriate project present in repository | PASS | GitHub recursive tree verified: SQL procedures, source workbook, executed notebook, tests, ER PNG/PDF and documentation are present on main. |
| 3 | Appropriate ER diagram with table connections | PASS | `diagrams/little_lemon_er_diagram.png` and `.pdf` are generated from actual `information_schema`. Seven tables, columns, keys and FK relationships are captured in `schema_manifest.json`; `test_er_diagram_metadata_matches_deployed_schema` passes. PNG and rasterized PDF were visually inspected. |
| 4 | `GetMaxQuantity()` | PASS | `sql/stored_procedures.sql`: `MAX(Orders.Quantity)` returns **3** from the actual workbook. `test_get_max_quantity_uses_imported_order_quantities` and the executed Python demo/notebook verify it. |
| 5 | `ManageBooking()` | PASS | Accepts DATE and table number, returns an actual availability message and `IsBooked`. Tests cover booked, available and invalid cases. The demo prints `Table 1 is already booked` for the seeded example. |
| 6 | `UpdateBooking()` | PASS | Accepts booking ID and new date; locks the row, updates it, and reports missing bookings. Tests verify persisted updates, duplicate-table/date rejection, and rollback when Python does not commit. |
| 7 | `AddBooking()` | PASS | Accepts booking ID, actual-format customer ID, date and table; validates required values, customer existence and uniqueness. Tests cover success, historical dates, invalid/missing values, duplicate IDs/date-table pairs, and rollback. |
| 8 | `CancelBooking()` | PASS | Locks and deletes the requested booking, with a clear result and missing-booking error. Tests verify commit persistence and rollback, using only temporary test IDs. |

All eight supplied rubric criteria have supporting evidence: **8 PASS, 0 FAIL,
0 NOT VERIFIED**. Supplemental native application limitations are listed below.

## Executed technical checks

- Actual database: **little_lemon_database**, MySQL **8.4.13**.
- `python -m unittest discover -v`: **48 passed**, 0 failures, 0 errors, 0 skipped.
  This includes 33 MySQL integration checks and 15 offline unit/workbook checks.
- Completed notebook: **10/10 code cells**, **two successful full executions**,
  **0 unexpected exceptions**. Saved outputs are in
  `notebooks/Little_Lemon_Database.ipynb`.
- Actual workbook import: 1,000 Customers, 30 MenuItems, 72 Menus,
  360 MenuComponents, 21,000 Orders and 21,000 delivery rows; four separately
  labeled demonstration bookings. Setup/import rerun inserts zero duplicates.
- Source-measure reconciliation: Sales **4,631,847.0300**, total Quantity **44,625**,
  maximum Quantity **3**. Currency and Discount interpretation are not supplied.
- Tableau-ready fact extract: 21,000 unique source row keys; totals reconcile
  without five-component join fan-out. Three export tests cover counts, checksum
  manifests, monetary sums, anomalies and separate demo bookings.
- ER schema alignment, Python compilation, dependency compatibility and source
  workbook hash checks passed. Dependency audit found no known vulnerabilities.

## Supplemental artifacts and limitations

| Item | Status | Evidence / limitation |
| --- | --- | --- |
| Original workbook inspected and imported | PASS | `data/WORKBOOK_AUDIT.md`, `workbook_profile.json` and `workbook_expected.json` document the actual file, source hash, every column, data types, counts, missing values and transformations. |
| MySQL Workbench `.mwb` | NOT VERIFIED | Workbench is not accessible; no fake native file is included. SQL and genuine ER PNG/PDF exports are supplied, with reverse-engineering instructions in `diagrams/README.md`. |
| Tableau Desktop / `.twbx` | NOT VERIFIED | Tableau Desktop is not accessible; no native workbook or Tableau execution is claimed. Verified CSVs, field mappings, reconciliation manifests and reproduction instructions are in `tableau/`. |
| Original detailed lab parameter signatures | NOT VERIFIED | No original lab instruction sheet was found. The five implemented signatures follow the explicit baseline in the task, including string customer IDs required by the actual source. |
| Both existing projects preserved | PASS | `evidence/preservation.json`: all 69 Django and 44 sales-report tracked files match before/after fingerprints; data in their 14 and seven tables is unchanged. Neither repository is edited or pushed to. |

Repeated source Order IDs are retained, not guessed into unique transactions.
The 9,366 delivery-before-order records and malformed postal values remain
traceable. No employee records, component prices, real booking associations,
currency or missing delivery status values are invented. Temporary procedure
demonstrations leave the four booking fixtures and all imported source rows intact.

Machine-readable execution evidence is in `evidence/verification.json` and
`evidence/notebook_execution.json`.
