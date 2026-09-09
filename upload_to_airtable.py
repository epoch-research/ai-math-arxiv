#!/usr/bin/env python3
"""upload_to_airtable.py — sync the committed data tables to Airtable.

Calls ``arxiv_math_ai_data.get_all_tables()`` (the same accessor everyone else
uses; the committed CSVs under ``data/`` are the source of truth) and uploads
each DataFrame with the ``epochutils.data.airtable`` library. Re-runs are
idempotent: ``sync_dataframe`` upserts on the primary field and prunes rows that
are no longer in the source.

    # creds from AIRTABLE_API_KEY / AIRTABLE_BASE_ID (env or .env)
    python upload_to_airtable.py                       # the default table set
    python upload_to_airtable.py --tables monthly examined
    python upload_to_airtable.py --all                 # every table, see the cap note below
    python upload_to_airtable.py --dry-run             # build the frames, print, do not connect

Table and field contract (the website's datahub reader depends on it):

  * one Airtable table per DataFrame returned by ``get_all_tables()``, named
    after the CSV file stem (``arxiv_trends_monthly``, ``math_examined``, ...);
  * field names are the CSV column names, verbatim;
  * the primary field is a natural single unique column where one exists
    (``arxiv_id`` for papers, ``author`` for authors) and otherwise a synthesized
    ``Name`` = the table's key columns joined with ``|``;
  * counts (``numerator``, ``denominator``, ``papers_*``, ``n_*``) are integer
    ``number`` fields, boolean columns (``is_partial``, ``panel``, ...) are
    checkboxes, everything else is single-line text.

Airtable caps: a base holds at most 50,000 records on Team, 125,000 on Business
and 500,000 on Enterprise plans (airtable.com/pricing, September 2026). The
author-side tables alone are ~2.6M rows and ``math_papers`` is ~155k, so the
DEFAULT set uploads only the three paper-side tables the tracker's charts and
methodology need (~61k rows). Pass ``--all`` or ``--tables`` to override.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from dataclasses import dataclass

import pandas as pd
from dotenv import load_dotenv

load_dotenv()

from arxiv_math_ai_data import FILES, get_all_tables

PRIMARY = "Name"  # the synthesized primary field, when a table needs one
SEP = "|"


@dataclass(frozen=True)
class TableSpec:
    key: str                     # get_all_tables() key
    key_columns: tuple[str, ...]  # one column -> used as the primary field directly;
                                  # several -> joined with SEP into `Name`
    default: bool = True         # uploaded when no --tables/--all is given

    @property
    def name(self) -> str:
        """Airtable table name: the CSV file stem (arxiv_trends_monthly, math_examined, ...)."""
        return FILES[self.key].split(".")[0]

    @property
    def primary(self) -> str:
        return self.key_columns[0] if len(self.key_columns) == 1 else PRIMARY


TABLES = [
    TableSpec("monthly",       ("metric", "field", "period", "population", "category")),
    TableSpec("examined",      ("month", "field")),
    # (arxiv_id, tag) repeats when one paper earns the same tag from several quotes,
    # so the key carries a short hash of the quote: stable across refreshes, unlike
    # a positional ordinal, and short enough to read.
    TableSpec("disclosures",   ("arxiv_id", "tag", "quote")),
    TableSpec("papers",        ("arxiv_id",),                       default=False),
    TableSpec("authors",       ("author",),                         default=False),
    TableSpec("author_fields", ("author", "field"),                 default=False),
    TableSpec("author_papers", ("author", "arxiv_id"),              default=False),
    TableSpec("author_ids",    ("author", "openalex_author_id", "orcid"), default=False),
]
BY_KEY = {spec.key: spec for spec in TABLES}
BY_NAME = {spec.name: spec for spec in TABLES}

#: Columns hashed rather than embedded when they form part of a synthesized key.
HASHED_KEY_COLUMNS = {"quote"}

CHECKBOX = {"type": "checkbox", "options": {"icon": "check", "color": "greenBright"}}
INTEGER = {"type": "number", "options": {"precision": 0}}


def _key_part(df: pd.DataFrame, column: str) -> pd.Series:
    values = df[column].astype("string").fillna("")
    if column in HASHED_KEY_COLUMNS:
        return values.map(lambda s: hashlib.sha1(s.encode("utf-8")).hexdigest()[:8])
    return values


def build_frame(spec: TableSpec, df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """The DataFrame as it is uploaded, plus the ``column_types`` overrides for it.

    Adds the synthesized ``Name`` column first when the table needs one, turns
    booleans into checkbox values (True / None) and empty strings into None so
    Airtable stores an empty cell rather than "".
    """
    out = df.copy()
    if spec.primary == PRIMARY:
        parts = [_key_part(out, c) for c in spec.key_columns]
        name = parts[0]
        for part in parts[1:]:
            name = name + SEP + part
        out.insert(0, PRIMARY, name.astype(object))

    column_types: dict[str, dict] = {}
    for col in out.columns:
        dtype = out[col].dtype
        if pd.api.types.is_bool_dtype(dtype):
            column_types[col] = CHECKBOX
            out[col] = out[col].map({True: True, False: None}).astype(object)
        elif pd.api.types.is_integer_dtype(dtype):
            column_types[col] = INTEGER
        else:
            # text: "" -> None; leave the primary field alone (sync_dataframe
            # rejects empty keys, which is what we want to hear about)
            if col != spec.primary:
                out[col] = out[col].astype(object).where(out[col].astype("string") != "", None)
    return out, column_types


def describe(spec: TableSpec, df: pd.DataFrame, column_types: dict) -> str:
    dupes = int(df[spec.primary].duplicated().sum())
    empties = int((df[spec.primary].astype("string").fillna("") == "").sum())
    lines = [
        f"[{spec.name}]  key={spec.key}  rows={len(df):,}  primary={spec.primary}"
        f"  duplicate keys={dupes}  empty keys={empties}"
    ]
    if spec.primary == PRIMARY:
        lines.append(f"    Name = {SEP.join(spec.key_columns)}"
                     + (f"  ({', '.join(sorted(HASHED_KEY_COLUMNS & set(spec.key_columns)))} as sha1[:8])"
                        if HASHED_KEY_COLUMNS & set(spec.key_columns) else ""))
    for col in df.columns:
        ctype = column_types.get(col, {}).get("type", "singleLineText")
        lines.append(f"    {col:<22} {ctype}")
    return "\n".join(lines)


def select_tables(names: list[str] | None, all_tables: bool) -> list[TableSpec]:
    if all_tables:
        return list(TABLES)
    if not names:
        return [spec for spec in TABLES if spec.default]
    chosen = []
    for name in names:
        spec = BY_KEY.get(name) or BY_NAME.get(name)
        if spec is None:
            sys.exit(f"unknown table {name!r}; choose from {sorted(BY_KEY)} or {sorted(BY_NAME)}")
        if spec not in chosen:
            chosen.append(spec)
    return chosen


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--tables", nargs="+", metavar="TABLE",
                        help="restrict to these tables (get_all_tables() keys or Airtable names)")
    parser.add_argument("--all", action="store_true",
                        help="upload every table, including the author tables (~2.6M rows)")
    parser.add_argument("--dry-run", action="store_true",
                        help="build and describe the frames, then exit without connecting")
    args = parser.parse_args(argv)

    specs = select_tables(args.tables, args.all)
    tables = get_all_tables()
    frames = {spec.key: build_frame(spec, tables[spec.key]) for spec in specs}

    total = 0
    for spec in specs:
        df, column_types = frames[spec.key]
        print(describe(spec, df, column_types))
        total += len(df)
    print(f"{len(specs)} table(s), {total:,} records in total")

    bad = [spec.name for spec in specs
           if frames[spec.key][0][spec.primary].duplicated().any()]
    if bad:
        sys.exit(f"duplicate primary keys in {bad}; fix the key columns before uploading")

    if args.dry_run:
        print("Dry run: not connecting to Airtable.")
        return

    api_key = os.environ.get("AIRTABLE_API_KEY")
    base_id = os.environ.get("AIRTABLE_BASE_ID")
    if not api_key or not base_id:
        sys.exit("AIRTABLE_API_KEY and AIRTABLE_BASE_ID must be set (env or .env)")

    from epochutils.data import airtable  # imported late so --dry-run needs no Airtable client

    base = airtable.connect(api_key, base_id)
    for spec in specs:
        df, column_types = frames[spec.key]
        print(f"Syncing {spec.name} ({len(df):,} rows)…")
        airtable.sync_dataframe(base, spec.name, df, spec.primary, column_types=column_types)

    print("Done.")


if __name__ == "__main__":
    main()
