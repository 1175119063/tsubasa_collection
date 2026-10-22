"""Build aliases.local.json from the application database (read-only).

Chinese names are not reliably searchable on iNaturalist, so the experiment
uses the archive's own 39 Chinese/scientific pairs as the first resolution
layer.  Reading the database does not modify it.
"""

from __future__ import annotations

import json
import pathlib
import sqlite3

LAB_DIR = pathlib.Path(__file__).resolve().parent
DATABASE = LAB_DIR.parent / "data" / "database.sqlite"


def main() -> int:
    if not DATABASE.is_file():
        print(f"database not found: {DATABASE}")
        return 1
    connection = sqlite3.connect(f"file:{DATABASE.as_posix()}?mode=ro", uri=True)
    try:
        rows = connection.execute(
            "SELECT chinese_name, scientific_name FROM species "
            "WHERE trim(coalesce(chinese_name, '')) <> '' "
            "AND trim(coalesce(scientific_name, '')) <> ''"
        ).fetchall()
    finally:
        connection.close()
    aliases = {str(zh).strip(): str(sci).strip() for zh, sci in rows}
    destination = LAB_DIR / "aliases.local.json"
    destination.write_text(
        json.dumps(aliases, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(f"{destination.name}: {len(aliases)} aliases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
