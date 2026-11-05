# Deployed-schema ER diagram

The PNG, PDF, SVG and Graphviz source are generated from the actual
`little_lemon_database` schema using MySQL's `information_schema`. They are not a
separate conceptual drawing. `schema_manifest.json` records the exact table
columns, MySQL types, nullability, defaults, indexes and foreign-key constraints
that produced the diagram.

## Regenerate and verify

After configuring the project environment and deploying/importing the database:

```bash
python scripts/generate_er.py
```

Graphviz's `dot` executable is required. The generator acquires its metadata
connection through `python.database.pooled_cursor`, exports all three image
formats, and verifies that the saved manifest still equals the live schema.
To check alignment without regenerating the diagram:

```python
from python.database import create_pool
from scripts.generate_er import compare_schema

assert compare_schema(create_pool())
```

The diagram shows every column. `PK` means primary key, `FK` foreign key, and
`UK` a single-column unique key. The Null column records whether SQL NULL is
allowed. Relationship cardinalities come from FK nullability and unique indexes:
a parent may have zero children; a unique child FK permits at most one child.
The connections are constraints, not claims about how many rows are observed.

## Workbook-related design choices

- `Orders.OrderID` uses the workbook's unique Row Number. The original order ID
  is preserved as `SourceOrderID` and is intentionally not unique because it
  repeats with conflicting source values.
- `MenuComponents` expresses menu-bundle membership. The source does not supply
  per-component order quantities or prices, so an invented order-items table
  would misrepresent the workbook's grain.
- `Bookings` connects to `Customers`, but no direct Orders-to-Bookings FK is
  invented: the workbook supplies no booking assignment.
- No employee table is fabricated when employee data is unavailable.

## MySQL Workbench native model

**NOT VERIFIED:** MySQL Workbench is not installed/available in this runtime.
No `.mwb` file is included or represented as a genuine Workbench model.
The deployed SQL schema and exported ER diagrams are provided instead.

To create a genuine native model in an environment with Workbench:

1. Connect using the restricted account for `little_lemon_database`.
2. Choose **Database > Reverse Engineer**, selecting only this database.
3. Import the seven tables and place them on an EER diagram.
4. Compare the columns and FK connections with `schema_manifest.json`.
5. Save as `little_lemon_model.mwb`, close it, and reopen it to verify the model.

Do not select or alter either existing Little Lemon database during that process.

The MenuItems-to-MenuComponents connector represents the composite constraint
`(ItemID, ComponentRole) -> (ItemID, ItemType)`. Both child columns are marked FK;
the manifest records both column pairs even though one table-level connector
represents the single composite relationship.
