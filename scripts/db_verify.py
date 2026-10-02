from __future__ import annotations

import argparse
import asyncio

from scripts.migration_preflight import inspect_schema, validate_final_schema
from tgbot.config import load_database_config


async def verify(expected_users: int | None) -> None:
    state = await inspect_schema(load_database_config().construct_sqlalchemy_url())
    validate_final_schema(state, expected_users=expected_users)
    print(f"database tables={sorted(state.tables)}")
    print(f"user_rows={state.user_count}")
    print(f"alembic_revision={state.alembic_revision}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify accentsbot PostgreSQL after restore/deploy."
    )
    parser.add_argument("--expected-users", type=int, default=None)
    args = parser.parse_args()
    asyncio.run(verify(args.expected_users))
    print("DB_VERIFY=OK")


if __name__ == "__main__":
    main()
