"""Phase 11: thin deprecation shims for duplicated NL metric hints.

Prefer semantic_catalog.concepts.FIELD_TO_CONCEPT / bind_concept instead of
adding new keyword branches in intent_router.
"""

from __future__ import annotations

from txt2sql.semantic_catalog.concepts import FIELD_TO_CONCEPT, resolve_concept
from txt2sql.semantic_catalog.binding import bind_concept

# Re-export canonical maps so legacy call sites can migrate without new parsers.
LEGACY_FIELD_ALIASES = dict(FIELD_TO_CONCEPT)


def canonical_concept(token: str) -> str | None:
    concept = resolve_concept(token)
    return concept.key if concept else None


def preferred_dataset_for_metric(token: str) -> str | None:
    binding = bind_concept(token)
    return binding.dataset if binding else None
