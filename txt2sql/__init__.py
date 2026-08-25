"""자연어 질의를 SQL로 변환해 PostgreSQL에 실행하는 패키지.

권장 사용::

    from txt2sql import Txt2SqlEngine, SessionContext

    with Txt2SqlEngine.from_env() as engine:
        result = engine.ask("기능 알려줘")
        print(result.answer)
"""

from txt2sql.config import Settings, load_settings
from txt2sql.engine import Txt2SqlEngine
from txt2sql.pipeline import ask
from txt2sql.session import SessionContext
from txt2sql.types import AskResult

__all__ = [
    "AskResult",
    "Txt2SqlEngine",
    "SessionContext",
    "Settings",
    "ask",
    "load_settings",
]
