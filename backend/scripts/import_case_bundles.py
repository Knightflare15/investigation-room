from __future__ import annotations

import argparse
import json
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb

from backend.app.case_loader import load_authoring_bundle


def main() -> None:
    parser = argparse.ArgumentParser(description="Idempotently import filesystem case bundles into Postgres.")
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--cases-path", default="cases")
    args = parser.parse_args()

    with psycopg.connect(args.database_url) as connection:
        for case_dir in sorted(path for path in Path(args.cases_path).iterdir() if path.is_dir()):
            bundle = load_authoring_bundle(case_dir)
            payload = bundle.model_dump(mode="json")
            connection.execute(
                """
                INSERT INTO production_cases (id, owner_user_id, status, owner_alias, version, bundle)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT(id) DO UPDATE SET
                    owner_user_id = EXCLUDED.owner_user_id,
                    status = EXCLUDED.status,
                    owner_alias = EXCLUDED.owner_alias,
                    version = EXCLUDED.version,
                    bundle = EXCLUDED.bundle,
                    updated_at = NOW()
                """,
                (
                    bundle.case.id,
                    bundle.case.owner_user_id,
                    bundle.case.status,
                    bundle.case.owner_alias,
                    bundle.case.version,
                    Jsonb(payload),
                ),
            )
            connection.execute(
                """
                INSERT INTO case_versions (case_id, version, bundle, created_by)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT(case_id, version) DO UPDATE SET bundle = EXCLUDED.bundle
                """,
                (bundle.case.id, bundle.case.version, Jsonb(payload), bundle.case.owner_alias or "repository-seed"),
            )
            print(json.dumps({"imported": bundle.case.id, "version": bundle.case.version}))


if __name__ == "__main__":
    main()
