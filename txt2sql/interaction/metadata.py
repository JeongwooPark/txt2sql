"""Metadata interaction intent."""

from __future__ import annotations

from txt2sql.interaction.delta import classify_interaction_intent


def is_metadata_interaction(question: str) -> bool:
    return classify_interaction_intent(question) == "metadata"
