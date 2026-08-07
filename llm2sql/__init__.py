"""자연어 질의를 SQL로 변환해 PostgreSQL에 실행하는 패키지.

권장 사용::

    from llm2sql import Llm2SqlEngine, SessionContext

    with Llm2SqlEngine.from_env() as engine:
        result = engine.ask("기능 알려줘")
        print(result.answer)
"""

from llm2sql.config import Settings, load_settings
from llm2sql.engine import Llm2SqlEngine
from llm2sql.pipeline import ask
from llm2sql.session import SessionContext
from llm2sql.types import AskResult

__all__ = [
    "AskResult",
    "Llm2SqlEngine",
    "SessionContext",
    "Settings",
    "ask",
    "load_settings",
]
