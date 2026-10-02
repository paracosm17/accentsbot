from __future__ import annotations

import pytest

from scripts.migration_preflight import (
    EXPECTED_USER_SCHEMA,
    SchemaState,
    validate_legacy_user_schema,
)


def compatible_state(**overrides) -> SchemaState:
    values = {
        "tables": frozenset({"user"}),
        "user_columns": frozenset(EXPECTED_USER_SCHEMA),
        "user_count": 19_642,
        "user_primary_key": ("user_id",),
        "user_column_specs": tuple(EXPECTED_USER_SCHEMA.items()),
    }
    values.update(overrides)
    return SchemaState(**values)


def test_legacy_schema_validation_accepts_expected_schema() -> None:
    validate_legacy_user_schema(compatible_state())


def test_legacy_schema_validation_fails_closed_on_missing_column() -> None:
    state = compatible_state(user_columns=frozenset({"user_id"}))
    with pytest.raises(RuntimeError, match="missing required columns"):
        validate_legacy_user_schema(state)


def test_legacy_schema_validation_requires_user_id_primary_key() -> None:
    state = compatible_state(user_primary_key=())
    with pytest.raises(RuntimeError, match="primary key"):
        validate_legacy_user_schema(state)


def test_legacy_schema_validation_rejects_type_or_nullability_drift() -> None:
    specs = dict(EXPECTED_USER_SCHEMA)
    specs["user_id"] = specs["username"]
    state = compatible_state(user_column_specs=tuple(specs.items()))
    with pytest.raises(RuntimeError, match="column definitions"):
        validate_legacy_user_schema(state)
