"""교체 가능한 문항 파일을 읽는다."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
DEFAULT_QUESTIONS = HERE / "questions.json"


def load_questions(path: Path | None = None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """문항 JSON을 연다.

    지원 형식
    - ``{"include": "상대/또는/절대/경로.json"}`` — 다른 골드 파일을 가리킴
    - ``{"questions": [...]}`` — 골드와 같은 배열 (평가문항_500.json 호환)
    - ``[...]`` — 문항 배열만
    """
    src = Path(path) if path is not None else DEFAULT_QUESTIONS
    src = src.resolve()
    if not src.is_file():
        raise FileNotFoundError(f"문항 파일이 없습니다: {src}")
    raw = json.loads(src.read_text(encoding="utf-8"))
    meta: dict[str, Any] = {
        "path": str(src),
        "name": src.stem,
    }
    questions: list[dict[str, Any]]
    if isinstance(raw, list):
        questions = raw
    elif isinstance(raw, dict):
        include = raw.get("include")
        if include:
            target = Path(str(include))
            if not target.is_absolute():
                target = (src.parent / target).resolve()
            nested_meta, questions = load_questions(target)
            meta["name"] = raw.get("name") or nested_meta.get("name") or src.stem
            meta["included"] = str(target)
        elif "questions" in raw:
            questions = list(raw["questions"] or [])
            meta["name"] = raw.get("name") or src.stem
        else:
            raise ValueError(f"문항 형식 오류: include 또는 questions 키가 필요합니다 ({src})")
        if raw.get("name"):
            meta["name"] = raw["name"]
    else:
        raise ValueError(f"문항 형식 오류: JSON 객체 또는 배열이어야 합니다 ({src})")

    cleaned: list[dict[str, Any]] = []
    for i, item in enumerate(questions):
        if not isinstance(item, dict):
            raise ValueError(f"문항 {i}가 객체가 아닙니다")
        q = str(item.get("q") or item.get("question") or "").strip()
        if not q:
            raise ValueError(f"문항 {i}에 q(질문)가 없습니다")
        qid = str(item.get("id") or f"Q{i + 1:03d}")
        cleaned.append(
            {
                "id": qid,
                "q": q,
                "kind": str(item.get("kind") or "fallback"),
                "gold": item.get("gold") or "",
                "cat": item.get("cat") or "기타",
                "source": item.get("source") or meta.get("name") or "custom",
                "session": item.get("session"),
                "parent": item.get("parent"),
                "sql": item.get("sql"),
                "note": item.get("note") or "",
            }
        )
    meta["total"] = len(cleaned)
    return meta, cleaned
