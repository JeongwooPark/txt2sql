"""직전 결과(focus 건물)에 대한 후속 질문 처리."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import psycopg
from psycopg.rows import dict_row

from llm2sql.answer import _fmt_number  # noqa: PLC2701 — 내부 포맷 재사용
from llm2sql.session import SessionContext

_FOLLOW_HINTS = (
    "그 ",
    "그거",
    "그게",
    "그것",
    "해당",
    "이 건물",
    "그 건물",
    "그 아파트",
    "해당 아파트",
    "앞의",
    "방금",
    "아까",
    "위에서",
    "이름",
    "건물명",
    "명칭",
    "지번",
    "주소",
    "어디",
    "몇 층",
    "몇층",
    "높이는",
    "연면적은",
    "건물면적은",
    "용도는",
    "더 알려",
    "자세히",
    "상세",
)

_ATTR_MAP: list[tuple[tuple[str, ...], str, str]] = [
    (("이름", "건물명", "명칭", "뭐라는", "뭐야"), "A24", "건물명"),
    (("동명", "건물동", "동 이름"), "A25", "건물동명"),
    (("지번", "주소", "어디"), "A5", "지번"),
    (("법정동",), "A4", "법정동명"),
    (("용도",), "A9", "용도"),
    (("건물면적", "건축물면적", "건축면적"), "A12", "건물면적"),
    (("연면적",), "A14", "연면적"),
    (("대지면적",), "A15", "대지면적"),
    (("높이",), "A16", "높이"),
    (("지상층", "몇 층", "몇층", "층수"), "A26", "지상층"),
    (("지하",), "A27", "지하층"),
    (("구조",), "A11", "건축물구조명"),
    (("아이디", "id", "ID", "식별"), "A19", "건축물ID"),
]


@dataclass(frozen=True)
class FollowupAnswer:
    intent: str
    answer: str
    sql: str | None
    rows: list[dict[str, Any]]
    tables: list[str]


def is_followup_question(question: str, session: SessionContext | None) -> bool:
    if session is None:
        return False
    q = question.strip()
    if not q:
        return False
    # 새 장소/완전 신규 질의로 보이면 후속 아님
    if re.search(r"[가-힣0-9]{1,12}동", q) and not any(
        k in q for k in ("그 ", "해당", "앞의", "방금", "아까", "그거", "그 아파트", "그 건물")
    ):
        # "구서동에서..." 는 신규. 단 "그 구서동" 류는 드묾
        if not q.startswith(("그", "해당", "앞", "방금", "아까", "이 ", "저 ")):
            return False
    return any(h in q for h in _FOLLOW_HINTS) or q in {
        "이름은?",
        "이름?",
        "건물명은?",
        "주소는?",
        "지번은?",
        "높이는?",
        "몇 층?",
        "몇층?",
    }


def answer_followup(
    conn: psycopg.Connection,
    question: str,
    session: SessionContext,
) -> FollowupAnswer:
    q = question.strip()
    if session.focus_row is None:
        return FollowupAnswer(
            intent="followup_no_context",
            answer=(
                "직전에 특정 건물 결과가 없어 ‘그 아파트’를 특정할 수 없습니다.\n"
                "먼저 예: 「구서동에서 건물면적이 가장 큰 아파트는?」처럼 "
                "건물을 찾은 뒤, 「그 아파트의 이름은?」처럼 이어서 물어 주세요."
            ),
            sql=None,
            rows=[],
            tables=[],
        )

    row = _ensure_detail_row(conn, session)
    attrs = _requested_attrs(q)

    if not attrs or any(k in q for k in ("자세히", "상세", "더 알려", "정보")):
        return FollowupAnswer(
            intent="followup_detail",
            answer=_format_building_card(row, title="직전에 조회한 건물 정보입니다."),
            sql=None,
            rows=[row],
            tables=[session.table or "AL_D010_26_20250704"],
        )

    lines = ["직전에 찾은 건물 기준으로 답하면 다음과 같습니다."]
    for col, label in attrs:
        val = row.get(col)
        if val is None or val == "" or str(val).lower() == "nan":
            lines.append(f"- {label}: 데이터에 등록되어 있지 않습니다.")
        elif col in {"A12", "A14", "A15"}:
            lines.append(f"- {label}: {_fmt_number(val)}㎡")
        elif col == "A16":
            lines.append(f"- {label}: {_fmt_number(val)}m")
        elif col in {"A26", "A27"}:
            lines.append(f"- {label}: {_fmt_number(val)}층")
        else:
            lines.append(f"- {label}: {val}")

    # 이름 질문인데 비어 있으면 식별 정보 보완
    if any(c == "A24" for c, _ in attrs):
        name = row.get("A24")
        if name is None or name == "" or str(name).lower() == "nan":
            lines.append(
                "참고: 이 데이터셋의 ‘건물명’(A24)이 비어 있어, "
                f"지번 {row.get('A5') or '—'} / 건축물ID {row.get('A19') or '—'} "
                "로 식별할 수 있습니다."
            )

    return FollowupAnswer(
        intent="followup_attr",
        answer="\n".join(lines),
        sql=None,
        rows=[row],
        tables=[session.table or "AL_D010_26_20250704"],
    )


def _requested_attrs(q: str) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for keys, col, label in _ATTR_MAP:
        if any(k in q for k in keys):
            found.append((col, label))
    return found


def _ensure_detail_row(
    conn: psycopg.Connection,
    session: SessionContext,
) -> dict[str, Any]:
    row = dict(session.focus_row or {})
    need = ["A24", "A25", "A5", "A19", "A0", "A11", "A15", "A27"]
    if all(k in row and row.get(k) is not None for k in ("A24", "A5", "A19")):
        return row

    table = session.table or "AL_D010_26_20250704"
    where = None
    params: tuple[Any, ...] = ()
    if row.get("A0") is not None:
        where = '"A0" = %s'
        params = (row["A0"],)
    elif row.get("A19"):
        where = '"A19" = %s'
        params = (row["A19"],)
    elif row.get("A4") and row.get("A14") is not None:
        where = '"A4" = %s AND "A14" = %s'
        params = (row["A4"], row["A14"])

    if not where:
        return row

    cols = (
        '"A0", "A4", "A5", "A9", "A11", "A12", "A14", "A15", '
        '"A16", "A19", "A24", "A25", "A26", "A27"'
    )
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f'SELECT {cols} FROM "{table}" WHERE {where} LIMIT 1',
            params,
        )
        detailed = cur.fetchone()
    if detailed:
        session.focus_row = dict(detailed)
        return dict(detailed)
    return row


def _format_building_card(row: dict[str, Any], *, title: str) -> str:
    name = row.get("A24")
    name_s = (
        str(name)
        if name not in (None, "") and str(name).lower() != "nan"
        else "(건물명 미등록)"
    )
    lines = [
        title,
        f"- 건물명: {name_s}",
        f"- 법정동: {row.get('A4') or '—'}",
        f"- 지번: {row.get('A5') or '—'}",
        f"- 용도: {row.get('A9') or '—'}",
        f"- 건물면적: {_fmt_number(row.get('A12'))}㎡",
        f"- 연면적: {_fmt_number(row.get('A14'))}㎡",
        f"- 높이: {_fmt_number(row.get('A16'))}m",
        f"- 지상층: {_fmt_number(row.get('A26'))}층",
        f"- 건축물ID: {row.get('A19') or '—'}",
    ]
    if row.get("A25"):
        lines.insert(2, f"- 건물동명: {row.get('A25')}")
    return "\n".join(lines)
