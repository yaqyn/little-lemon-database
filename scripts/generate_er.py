"""Generate an ER diagram from the deployed schema, not a separate hand-drawn model.

Run from the project root: python scripts/generate_er.py
Requires the Graphviz `dot` executable. Every metadata query uses a pooled cursor.
"""
from __future__ import annotations

from collections import defaultdict
from html import escape
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from python.database import create_pool, pooled_cursor

EXPECTED_TABLES = {"Customers", "Bookings", "Menus", "MenuItems", "MenuComponents", "Orders", "OrderDeliveryStatus"}


def inspect_schema(pool):
    """Return stable, JSON-compatible metadata for every deployed table and FK."""
    with pooled_cursor(pool, dictionary=True) as (_, cursor):
        cursor.execute("SELECT DATABASE() AS DatabaseName")
        database = cursor.fetchone()["DatabaseName"]
        if database != "little_lemon_database":
            raise ValueError("ER inspection is restricted to little_lemon_database.")
        cursor.execute("""
            SELECT TABLE_NAME, COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE,
                   COLUMN_KEY, COLUMN_DEFAULT, EXTRA
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA=DATABASE()
            ORDER BY TABLE_NAME, ORDINAL_POSITION
        """)
        tables = defaultdict(list)
        for row in cursor.fetchall():
            tables[row["TABLE_NAME"]].append({
                "name": row["COLUMN_NAME"], "type": row["COLUMN_TYPE"],
                "nullable": row["IS_NULLABLE"] == "YES", "key": row["COLUMN_KEY"],
                "default": row["COLUMN_DEFAULT"], "extra": row["EXTRA"],
            })
        cursor.execute("""
            SELECT TABLE_NAME, INDEX_NAME, NON_UNIQUE, COLUMN_NAME, SEQ_IN_INDEX
            FROM information_schema.STATISTICS
            WHERE TABLE_SCHEMA=DATABASE()
            ORDER BY TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX
        """)
        grouped_indexes = {}
        for row in cursor.fetchall():
            key = row["TABLE_NAME"], row["INDEX_NAME"]
            item = grouped_indexes.setdefault(key, {
                "name": row["INDEX_NAME"], "unique": row["NON_UNIQUE"] == 0,
                "columns": [],
            })
            item["columns"].append(row["COLUMN_NAME"])
        indexes = {table: [] for table in tables}
        for (table, _), item in grouped_indexes.items():
            indexes[table].append(item)
        cursor.execute("""
            SELECT k.TABLE_NAME, k.COLUMN_NAME, k.REFERENCED_TABLE_NAME,
                   k.REFERENCED_COLUMN_NAME, k.CONSTRAINT_NAME, k.ORDINAL_POSITION,
                   r.UPDATE_RULE, r.DELETE_RULE
            FROM information_schema.KEY_COLUMN_USAGE k
            JOIN information_schema.REFERENTIAL_CONSTRAINTS r
              ON k.CONSTRAINT_SCHEMA=r.CONSTRAINT_SCHEMA
             AND k.CONSTRAINT_NAME=r.CONSTRAINT_NAME
             AND k.TABLE_NAME=r.TABLE_NAME
            WHERE k.TABLE_SCHEMA=DATABASE() AND k.REFERENCED_TABLE_NAME IS NOT NULL
            ORDER BY k.TABLE_NAME, k.CONSTRAINT_NAME, k.ORDINAL_POSITION
        """)
        foreign_keys = [{
            "table": row["TABLE_NAME"], "column": row["COLUMN_NAME"],
            "referenced_table": row["REFERENCED_TABLE_NAME"],
            "referenced_column": row["REFERENCED_COLUMN_NAME"],
            "constraint": row["CONSTRAINT_NAME"], "position": row["ORDINAL_POSITION"],
            "on_update": row["UPDATE_RULE"], "on_delete": row["DELETE_RULE"],
        } for row in cursor.fetchall()]
    if set(tables) != EXPECTED_TABLES:
        raise AssertionError(f"Expected seven assignment tables; deployed tables are {sorted(tables)}")
    return {"database": database, "tables": dict(tables), "indexes": indexes, "foreign_keys": foreign_keys}


def compare_schema(pool, manifestpath=None):
    """Fail if the committed diagram metadata differs from the live MySQL schema."""
    path = Path(manifestpath) if manifestpath else ROOT / "diagrams" / "schema_manifest.json"
    expected = json.loads(path.read_text())
    actual = inspect_schema(pool)
    if expected != actual:
        raise AssertionError("ER schema manifest differs from the deployed MySQL columns, indexes, or relationships.")
    return True


def _dot_quote(value):
    return json.dumps(str(value), ensure_ascii=True)


def graph_source(manifest):
    """Use one metadata object for table fields, ports, keys and cardinalities."""
    fk_columns = {(fk["table"], fk["column"]) for fk in manifest["foreign_keys"]}
    lines = [
        "digraph LittleLemon {",
        '  graph [rankdir=LR, bgcolor="white", pad="0.28", nodesep="0.55", ranksep="1.0", splines=polyline, fontname="Helvetica", fontsize=19, labelloc=t, label="Little Lemon Database\\nDeployed MySQL schema", dpi=160];',
        '  node [shape=plain, fontname="Helvetica", fontsize=11];',
        '  edge [color="#587267", penwidth=1.3, fontname="Helvetica", fontsize=10, arrowsize=0.85, labeldistance=1.8];',
    ]
    ports = {}
    for table, columns in manifest["tables"].items():
        unique_columns = {index["columns"][0] for index in manifest["indexes"][table]
                          if index["unique"] and len(index["columns"]) == 1 and index["name"] != "PRIMARY"}
        rows = [f'<TR><TD COLSPAN="4" BGCOLOR="#24483e" CELLPADDING="9"><FONT COLOR="white" POINT-SIZE="14"><B>{escape(table)}</B></FONT></TD></TR>',
                '<TR><TD BGCOLOR="#edf3ee"><B>Key</B></TD><TD BGCOLOR="#edf3ee"><B>Column</B></TD><TD BGCOLOR="#edf3ee"><B>Type</B></TD><TD BGCOLOR="#edf3ee"><B>Null</B></TD></TR>']
        for i, col in enumerate(columns):
            key = []
            if col["key"] == "PRI": key.append("PK")
            if (table, col["name"]) in fk_columns: key.append("FK")
            if col["name"] in unique_columns: key.append("UK")
            port = f"column_{i}"
            ports[(table, col["name"])] = {"left": "left_" + port, "right": "right_" + port}
            fill = "#f8faf8" if i % 2 else "white"
            column_type = col["type"]
            # Enum membership remains exact but wraps without widening the whole graph.
            if column_type.startswith("enum("):
                type_html = "ENUM<BR/>" + "<BR/>".join(escape(part) for part in column_type[5:-1].split(","))
            else:
                type_html = escape(column_type)
            rows.append(f'<TR><TD PORT="left_{port}" BGCOLOR="{fill}" ALIGN="LEFT">{escape(", ".join(key))}</TD><TD BGCOLOR="{fill}" ALIGN="LEFT">{escape(col["name"])}</TD><TD BGCOLOR="{fill}" ALIGN="LEFT">{type_html}</TD><TD PORT="right_{port}" BGCOLOR="{fill}">{"YES" if col["nullable"] else "NO"}</TD></TR>')
        lines.append(f'  {_dot_quote(table)} [label=<<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0" CELLPADDING="5" COLOR="#cad8ce">{"".join(rows)}</TABLE>>];')
    groups = defaultdict(list)
    for fk in manifest["foreign_keys"]:
        groups[(fk["table"], fk["constraint"])].append(fk)
    for (child, _), relationships in groups.items():
        fk = relationships[0]
        columns = [rel["column"] for rel in relationships]
        unique = any(index["unique"] and set(index["columns"]) == set(columns) for index in manifest["indexes"][child])
        mandatory = all(not col["nullable"] for col in manifest["tables"][child] if col["name"] in columns)
        parent_cardinality = "1" if mandatory else "0..1"
        child_cardinality = "0..1" if unique else "0..N"
        parent = fk["referenced_table"]
        parent_port = ports[(parent, fk["referenced_column"])]["right"]
        child_port = ports[(child, fk["column"])]["left"]
        lines.append(f'  {_dot_quote(parent)}:{parent_port}:e -> {_dot_quote(child)}:{child_port}:w [dir=both, arrowtail={"tee" if mandatory else "odottee"}, arrowhead={"odottee" if unique else "odotcrow"}, taillabel={_dot_quote(parent_cardinality)}, headlabel={_dot_quote(child_cardinality)}];')
    lines += [
        '  note [shape=box, style="rounded,filled", fillcolor="#f5f8f5", color="#cad8ce", fontcolor="#24483e", fontsize=11, margin="0.18,0.12", label="PK: primary key   FK: foreign key   UK: single-column unique key\\lNull: whether a column permits SQL NULL\\l\\lOrders.OrderID = workbook Row Number. SourceOrderID is retained and is not unique.\\lMenuComponents describes bundle membership, not item-level order quantities.\\lBookings are separately labeled fixtures; no workbook booking association is invented.\\lCardinalities describe constraints, not observed row counts.\\l"];',
        "}",
    ]
    return "\n".join(lines) + "\n"


def generate_er(pool=None):
    pool = pool or create_pool()
    manifest = inspect_schema(pool)
    directory = ROOT / "diagrams"
    directory.mkdir(exist_ok=True)
    (directory / "schema_manifest.json").write_text(json.dumps(manifest, indent=2, default=str) + "\n")
    source = directory / "little_lemon_er_diagram.dot"
    source.write_text(graph_source(manifest))
    for file_format in ("svg", "png", "pdf"):
        subprocess.run(["dot", f"-T{file_format}", str(source), "-o", str(directory / f"little_lemon_er_diagram.{file_format}")], check=True)
    compare_schema(pool, directory / "schema_manifest.json")
    print("ER PNG, PDF and SVG generated from live MySQL metadata; schema alignment verified.")
    return manifest


if __name__ == "__main__":
    generate_er()
