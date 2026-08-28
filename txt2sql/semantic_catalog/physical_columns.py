"""Back-compat re-export of the canonical physical column map.

Prefer importing from ``txt2sql.canonical_physical_columns`` directly
(especially from ``semantic_plan.catalog``, which must not create a cycle
through ``semantic_catalog.__init__``).
"""

from txt2sql.canonical_physical_columns import (  # noqa: F401
    CONCEPT_PHYSICAL_FIELDS,
    CONCEPT_TO_FIELD,
    D010_FIELD_COLUMNS,
    D198_FIELD_COLUMNS,
)

__all__ = [
    "CONCEPT_PHYSICAL_FIELDS",
    "CONCEPT_TO_FIELD",
    "D010_FIELD_COLUMNS",
    "D198_FIELD_COLUMNS",
]
