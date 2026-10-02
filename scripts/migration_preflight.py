from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass

from alembic import command
from alembic.config import Config as AlembicConfig
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine


@dataclass(frozen=True, slots=True)
class ColumnSpec:
    data_type: str
    nullable: bool
    max_length: int | None = None


EXPECTED_USER_SCHEMA: dict[str, ColumnSpec] = {
    "user_id": ColumnSpec("bigint", False),
    "username": ColumnSpec("character varying", True, 128),
    "full_name": ColumnSpec("character varying", False, 128),
    "language_code": ColumnSpec("character varying", True, 4),
    "banned": ColumnSpec("boolean", False),
    "active": ColumnSpec("boolean", False),
    "last_active": ColumnSpec("timestamp without time zone", True),
    "words": ColumnSpec("integer", False),
    "created_at": ColumnSpec("timestamp without time zone", False),
}
EXPECTED_USER_COLUMNS = frozenset(EXPECTED_USER_SCHEMA)


@dataclass(frozen=True, slots=True)
class SchemaState:
    tables: frozenset[str]
    user_columns: frozenset[str]
    user_count: int | None
    user_primary_key: tuple[str, ...] = ()
    user_column_specs: tuple[tuple[str, ColumnSpec], ...] = ()
    alembic_revision: str | None = None

    @property
    def has_user(self) -> bool:
        return "user" in self.tables

    @property
    def has_alembic_version(self) -> bool:
        return "alembic_version" in self.tables

    @property
    def column_specs(self) -> dict[str, ColumnSpec]:
        return dict(self.user_column_specs)


async def inspect_schema(database_url: str) -> SchemaState:
    engine = create_async_engine(database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            tables = frozenset(await connection.run_sync(lambda c: inspect(c).get_table_names()))
            columns: frozenset[str] = frozenset()
            column_specs: tuple[tuple[str, ColumnSpec], ...] = ()
            primary_key: tuple[str, ...] = ()
            count: int | None = None
            revision: str | None = None

            if "user" in tables:
                raw_columns = (
                    (
                        await connection.execute(
                            text(
                                """
                            SELECT column_name, data_type, is_nullable, character_maximum_length
                            FROM information_schema.columns
                            WHERE table_schema = 'public' AND table_name = 'user'
                            ORDER BY ordinal_position
                            """
                            )
                        )
                    )
                    .mappings()
                    .all()
                )
                columns = frozenset(str(item["column_name"]) for item in raw_columns)
                column_specs = tuple(
                    (
                        str(item["column_name"]),
                        ColumnSpec(
                            data_type=str(item["data_type"]),
                            nullable=item["is_nullable"] == "YES",
                            max_length=(
                                int(item["character_maximum_length"])
                                if item["character_maximum_length"] is not None
                                else None
                            ),
                        ),
                    )
                    for item in raw_columns
                )
                pk = await connection.run_sync(lambda c: inspect(c).get_pk_constraint("user"))
                primary_key = tuple(pk.get("constrained_columns") or ())
                count = int(
                    (await connection.execute(text('SELECT count(*) FROM "user"'))).scalar_one()
                )

            if "alembic_version" in tables:
                revision = (
                    await connection.execute(
                        text("SELECT version_num FROM alembic_version LIMIT 1")
                    )
                ).scalar_one_or_none()

            return SchemaState(
                tables=tables,
                user_columns=columns,
                user_count=count,
                user_primary_key=primary_key,
                user_column_specs=column_specs,
                alembic_revision=revision,
            )
    finally:
        await engine.dispose()


def alembic_config() -> AlembicConfig:
    return AlembicConfig("alembic.ini")


def expected_head() -> str:
    head = ScriptDirectory.from_config(alembic_config()).get_current_head()
    if head is None:
        raise RuntimeError("Alembic has no head revision")
    return head


def validate_legacy_user_schema(state: SchemaState) -> None:
    if not state.has_user:
        raise RuntimeError('required table "user" is missing')

    missing = EXPECTED_USER_COLUMNS - state.user_columns
    unexpected = state.user_columns - EXPECTED_USER_COLUMNS
    if missing:
        raise RuntimeError(f"legacy user table is missing required columns: {sorted(missing)}")
    if unexpected:
        raise RuntimeError(f"legacy user table has unexpected columns: {sorted(unexpected)}")
    if state.user_primary_key != ("user_id",):
        raise RuntimeError(
            f"legacy user primary key is incompatible: {list(state.user_primary_key)!r}"
        )

    actual_specs = state.column_specs
    if not actual_specs:
        raise RuntimeError("legacy user column type metadata is missing")
    mismatches = {
        name: {"expected": expected, "actual": actual_specs.get(name)}
        for name, expected in EXPECTED_USER_SCHEMA.items()
        if actual_specs.get(name) != expected
    }
    if mismatches:
        raise RuntimeError(f"legacy user column definitions are incompatible: {mismatches!r}")


def validate_final_schema(state: SchemaState, *, expected_users: int | None) -> None:
    validate_legacy_user_schema(state)
    if not state.has_alembic_version:
        raise RuntimeError("alembic_version table is missing after upgrade")
    if state.alembic_revision != expected_head():
        raise RuntimeError(
            f"alembic revision mismatch: expected={expected_head()} actual={state.alembic_revision}"
        )
    if expected_users is not None and state.user_count != expected_users:
        raise RuntimeError(
            f"user row count mismatch: expected={expected_users} actual={state.user_count}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate/upgrade accentsbot PostgreSQL schema without destructive data migration."
    )
    parser.add_argument(
        "--adopt-existing",
        action="store_true",
        help="Stamp a compatible restored legacy user table at Alembic head before upgrade.",
    )
    parser.add_argument(
        "--expected-users",
        type=int,
        default=None,
        help="Fail unless the final user row count equals this value.",
    )
    return parser.parse_args()


def main() -> None:
    from tgbot.config import load_database_config

    args = parse_args()
    database_url = load_database_config().construct_sqlalchemy_url()

    before = asyncio.run(inspect_schema(database_url))
    print(
        f"preflight before: tables={sorted(before.tables)} "
        f"user_count={before.user_count if before.user_count is not None else 'n/a'} "
        f"revision={before.alembic_revision or 'MISSING'}"
    )

    if before.has_user and not before.has_alembic_version:
        validate_legacy_user_schema(before)
        if not args.adopt_existing:
            raise SystemExit(
                "Existing user table has no alembic_version. Re-run with --adopt-existing only "
                "after restoring and validating the intended legacy PostgreSQL dump."
            )
        command.stamp(alembic_config(), "head")
        print("adopted compatible legacy schema: alembic stamp head")

    command.upgrade(alembic_config(), "head")
    # Run a second time deliberately: schema initialization must be idempotent.
    command.upgrade(alembic_config(), "head")

    after = asyncio.run(inspect_schema(database_url))
    validate_final_schema(after, expected_users=args.expected_users)

    print(
        f"preflight after: tables={sorted(after.tables)} user_count={after.user_count} "
        f"revision={after.alembic_revision}"
    )
    print("MIGRATION_PREFLIGHT=OK")


if __name__ == "__main__":
    main()
