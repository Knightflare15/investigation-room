from __future__ import annotations

import argparse
from pathlib import Path

import psycopg


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply a SQL migration to the production database.")
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--file", default="backend/migrations/001_production.sql")
    args = parser.parse_args()

    sql = Path(args.file).read_text(encoding="utf-8")
    with psycopg.connect(args.database_url) as connection:
        connection.execute(sql)
    print(f"Applied {args.file}")


if __name__ == "__main__":
    main()
