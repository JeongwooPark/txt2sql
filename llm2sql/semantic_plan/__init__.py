"""Router 미적중 질의를 Semantic Query Plan으로 컴파일하는 계층."""

from llm2sql.semantic_plan.runner import run_semantic_plan

__all__ = ["run_semantic_plan"]
