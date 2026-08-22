"""직전 결과(focus 건물)에 대한 후속 질문 처리."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import psycopg
from psycopg.rows import dict_row

from llm2sql.answer import fmt_value
from llm2sql.domain import has_anaphora, looks_like_standalone_question
from llm2sql.session import SessionContext
from llm2sql.units import with_pyeong

# 지시 대명·직전 참조
_ANAPHORA = (
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
)

# focus 건물이 있을 때만 짧은 속성 질문으로 허용
_ATTR_ONLY = (
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
    (("이름", "건물명", "명칭", "뭐라는"), "A24", "건물명"),
    (("동명", "건물동", "동 이름"), "A25", "건물동명"),
    (("주소", "어디"), "_ADDR", "주소"),
    (("지번",), "A5", "지번"),
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
    """직전 focus 건물을 가리키는 후속만 True. 새 주제 질문은 False."""
    if session is None:
        return False
    _recover_focus_from_last_rows(session)
    if session.focus_row is None:
        return False
    q = question.strip()
    if not q:
        return False
    # 새 장소·새 주제면 후속이 아님
    if looks_like_standalone_question(q):
        return False
    # '그 중에서 가장 최근'·건설일 제외 재조회는 특정 건물 카드 후속이 아님
    if _subset_order(q) is not None and (
        any(h in q for h in _SUBSET_HINTS)
        or "제외" in q
        or "건설일" in q
    ):
        return False

    if has_anaphora(q) or any(h in q for h in _ANAPHORA):
        return True

    short_attr = q in {
        "이름은?",
        "이름?",
        "건물명은?",
        "주소는?",
        "주소?",
        "지번은?",
        "지번?",
        "높이는?",
        "몇 층?",
        "몇층?",
    } or (
        len(q) <= 16 and any(h in q for h in _ATTR_ONLY)
    )
    return short_attr


def _recover_focus_from_last_rows(session: SessionContext) -> None:
    """focus가 비었지만 직전 단일 건물 결과가 있으면 복구."""
    if session.focus_row is not None:
        return
    rows = session.last_rows or []
    if len(rows) != 1:
        return
    route = str(session.last_route or "")
    row = _normalize_building_row(rows[0])
    building_like = any(
        k in row and row.get(k) is not None
        for k in ("A0", "A5", "A14", "A24", "A4")
    )
    if not building_like:
        return
    if (
        route.startswith("building_rank_")
        or route in {"building_name_lookup", "llm", "sql", "None", ""}
        or (session.last_sql and "AL_D010" in str(session.last_sql))
    ):
        session.focus_row = row
        if not session.table:
            session.table = "AL_D010_26_20250704"


_ROW_ALIAS_TO_COL = {
    "연면적": "A14",
    "건물면적": "A12",
    "건축물면적": "A12",
    "대지면적": "A15",
    "높이": "A16",
    "지상층": "A26",
    "지상층수": "A26",
    "법정동명": "A4",
    "법정동": "A4",
    "지번": "A5",
    "용도": "A9",
    "건축물용도명": "A9",
    "건물명": "A24",
    "건축물ID": "A19",
    "건축물id": "A19",
    "건물통합식별번호": "A1",
    "gis건물통합식별번호": "A1",
}


def _normalize_building_row(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    for key, val in list(row.items()):
        col = _ROW_ALIAS_TO_COL.get(str(key))
        if col and col not in out:
            out[col] = val
        # 소문자/공백 변형
        compact = str(key).replace(" ", "").lower()
        for alias, mapped in _ROW_ALIAS_TO_COL.items():
            if compact == alias.replace(" ", "").lower() and mapped not in out:
                out[mapped] = val
    return out


def answer_followup(
    conn: psycopg.Connection,
    question: str,
    session: SessionContext,
) -> FollowupAnswer:
    q = question.strip()
    _recover_focus_from_last_rows(session)
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
    area_q = " ".join(
        p
        for p in (
            q,
            session.last_full_question or "",
            session.last_question or "",
        )
        if p
    )

    if not attrs or any(k in q for k in ("자세히", "상세", "더 알려", "정보")):
        return FollowupAnswer(
            intent="followup_detail",
            answer=_format_building_card(
                row,
                title="직전에 조회한 건물 정보입니다.",
                question=area_q,
            ),
            sql=None,
            rows=[row],
            tables=[session.table] if session.table else [],
        )

    lines = ["직전 건물 기준으로 답합니다."]
    for col, label in attrs:
        if col == "_ADDR":
            addr = " ".join(
                str(x).strip()
                for x in (row.get("A4"), row.get("A5"))
                if x not in (None, "") and str(x).lower() != "nan"
            )
            lines.append(f"- 주소: {addr or '—'}")
            continue
        val = row.get(col)
        if col in {"A12", "A14", "A15"}:
            lines.append(
                f"- {label}: {with_pyeong(f'{fmt_value(val)}㎡', val, question=area_q)}"
            )
        elif col == "A16":
            lines.append(f"- {label}: {fmt_value(val)}m")
        elif col == "A26":
            lines.append(f"- {label}: {fmt_value(val)}층")
        else:
            lines.append(f"- {label}: {fmt_value(val)}")
    if not row.get("A24"):
        lines.append(
            f"(참고: 건물명이 비어 있어 지번 {row.get('A5') or '—'} / "
            f"건축물ID {row.get('A19') or '—'} 로 식별합니다.)"
        )
    return FollowupAnswer(
        intent="followup_attr",
        answer="\n".join(lines),
        sql=None,
        rows=[row],
        tables=[session.table] if session.table else [],
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
    row = _normalize_building_row(dict(session.focus_row or {}))
    need = ["A24", "A25", "A5", "A19", "A0", "A11", "A15", "A27"]
    if all(k in row and row.get(k) is not None for k in ("A5", "A4")) and (
        row.get("A0") is not None or row.get("A19") is not None or row.get("A24") is not None
    ):
        # 핵심 식별·주소가 있으면 그대로 사용 (상세 보강은 부족할 때만)
        if row.get("A0") is not None or row.get("A14") is not None:
            session.focus_row = row
            if row.get("A5") is not None:
                return row

    where = None
    params: tuple[Any, ...] = ()
    if row.get("A0") is not None:
        where = '"A0" = %s'
        params = (row["A0"],)
    elif row.get("A19"):
        where = '"A19" = %s'
        params = (row["A19"],)
    elif row.get("A1"):
        where = '"A1" = %s'
        params = (row["A1"],)
    elif row.get("A4") and row.get("A14") is not None:
        where = '"A4" = %s AND "A14" = %s'
        params = (row["A4"], row["A14"])
    if not where:
        session.focus_row = row
        return row

    table = session.table or "AL_D010_26_20250704"
    cols = (
        '"A0", "A1", "A4", "A5", "A9", "A11", "A12", "A14", "A15", '
        '"A16", "A19", "A24", "A25", "A26", "A27"'
    )
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f'SELECT {cols} FROM "{table}" WHERE {where} LIMIT 1',
            params,
        )
        fetched = cur.fetchone()
        if fetched:
            row.update(fetched)
            session.focus_row = dict(row)
    _ = need
    return row


def _format_building_card(
    row: dict[str, Any], *, title: str, question: str = ""
) -> str:
    name = row.get("A24")
    name_s = (
        str(name)
        if name not in (None, "") and str(name).lower() != "nan"
        else None
    )
    lines = [title]
    if name_s:
        lines.append(f"- 건물명: {name_s}")
    bldg_area = with_pyeong(
        f"{fmt_value(row.get('A12'))}㎡", row.get("A12"), question=question
    )
    floor_area = with_pyeong(
        f"{fmt_value(row.get('A14'))}㎡", row.get("A14"), question=question
    )
    lines.extend(
        [
            f"- 법정동: {row.get('A4') or '—'}",
            f"- 지번: {row.get('A5') or '—'}",
            f"- 용도: {row.get('A9') or '—'}",
            f"- 건물면적: {bldg_area}",
            f"- 연면적: {floor_area}",
            f"- 높이: {fmt_value(row.get('A16'))}m",
            f"- 지상층: {fmt_value(row.get('A26'))}층",
            f"- 건축물ID: {row.get('A19') or '—'}",
        ]
    )
    return "\n".join(lines)


_SUBSET_HINTS = (
    "그 중",
    "그중",
    "이 중",
    "이 가운데",
    "그 가운데",
    "중에서",
    "그중에",
)
_RECENCY_RECENT = (
    "가장 최근",
    "제일 최근",
    "최근에 지어",
    "가장 늦게",
    "새로 지은",
    "가장 나중에",
)
_RECENCY_OLD = ("가장 오래", "제일 오래", "가장 먼저 지어", "가장 오래된")


_LIST_FOLLOW_HINTS = (
    "출력",
    "보여",
    "나열",
    "목록",
    "리스트",
)

# 직전 목록을 유지한 채 속성만 더 보여 달라는 후속
_LIST_ATTR_FOLLOW = (
    "각각",
    "일자도",
    "날짜도",
    "승인일도",
    "허가일도",
    "도 출력",
    "도 알려",
    "도 보여",
    "도 포함",
    "같이 출력",
    "함께 출력",
    "같이 알려",
    "함께 알려",
)


def is_list_attr_followup(
    question: str, session: SessionContext | None
) -> bool:
    """직전 N건 목록에 사용승인일 등을 덧붙여 달라는 후속인지."""
    if session is None or not session.last_rows or not session.last_sql:
        return False
    q = question.strip()
    if not q or looks_like_standalone_question(q):
        return False
    if any(k in q for k in ("제외", "가장 최근", "제일 최근", "몇 채", "몇 개야")):
        return False
    n = _extract_followup_n(q, default=0)
    if n >= 1 and not any(k in q for k in ("각각", "일자", "날짜", "도 ")):
        return False
    if any(k in q for k in _LIST_ATTR_FOLLOW):
        return True
    if any(k in q for k in ("사용승인일", "허가일", "건설일", "준공일")) and any(
        k in q for k in ("출력", "알려", "보여", "포함")
    ):
        return True
    return False


def _extract_followup_n(q: str, *, default: int = 1) -> int:
    from llm2sql.intent_router import _extract_top_n

    return _extract_top_n(q, default=default)


def _last_was_date_rank(session: SessionContext) -> bool:
    sql = session.last_sql or ""
    last_q = session.last_full_question or session.last_question or ""
    if re.search(r'ORDER\s+BY\s+"A3[34]"', sql, flags=re.I):
        return True
    if any(k in last_q for k in ("지어진", "건설일", "사용승인", "준공")) and any(
        k in last_q for k in ("최근", "오래")
    ):
        return True
    return False


def _order_from_last_sql(sql: str) -> tuple[str, str] | None:
    m = re.search(
        r'ORDER\s+BY\s+"([^"]+)"\s+(ASC|DESC)',
        sql,
        flags=re.I,
    )
    if not m:
        return None
    return m.group(1), m.group(2).upper()


def is_subset_followup(question: str, session: SessionContext | None) -> bool:
    """직전 결과 집합을 가리키는 후속(그 중에 … / 최근 N개)인지."""
    if session is None or not session.last_sql:
        return False
    q = question.strip()
    if not q:
        return False
    from llm2sql.domain import extract_gu, extract_place

    hinted = has_anaphora(q) or any(h in q for h in _SUBSET_HINTS) or (
        "제외" in q and ("건설일" in q or "사용승인" in q or "준공" in q)
    )
    last_gu = extract_gu(session.last_question or session.last_full_question or "")
    cur_gu = extract_gu(q)
    if cur_gu and last_gu and cur_gu != last_gu:
        return False
    new_place = extract_place(q)
    last_place = extract_place(session.last_question or "")
    if (
        new_place
        and new_place.endswith("동")
        and last_place
        and last_place.endswith("동")
        and new_place != last_place
    ):
        return False
    if _subset_order(q, session) is not None:
        return True
    n = _extract_followup_n(q, default=0)
    if n > 1 or (
        any(k in q for k in _LIST_FOLLOW_HINTS)
        and ("최근" in q or "상위" in q or n > 1)
    ):
        return bool(_order_from_last_sql(session.last_sql or "") or hinted)
    if not hinted:
        return False
    return _subset_order(q, session) is not None


def _subset_order(
    q: str, session: SessionContext | None = None
) -> tuple[str, str] | None:
    """(지표 종류, ASC|DESC)."""
    if any(k in q for k in _RECENCY_OLD):
        return ("date", "ASC")
    if any(k in q for k in _RECENCY_RECENT) or (
        "최근" in q
        and any(k in q for k in ("지어", "준공", "사용승인", "허가", "건설일"))
    ):
        return ("date", "DESC")
    if "최근" in q and session is not None and _last_was_date_rank(session):
        return ("date", "DESC")
    if any(k in q for k in ("가장 높", "제일 높")):
        return ("height", "DESC")
    if "건폐율" in q and any(k in q for k in ("가장", "제일", "최대")):
        return ("far_cov", "DESC")
    if any(k in q for k in ("용적율", "용적률")) and any(
        k in q for k in ("가장", "제일", "최대")
    ):
        return ("far", "DESC")
    if any(k in q for k in ("가장 큰", "제일 큰", "가장 넓은", "제일 넓은")):
        return ("area", "DESC")
    return None


def _sql_table_where(sql: str) -> tuple[str, str] | None:
    """직전 SQL에서 첫 테이블과 WHERE 조건을 꺼낸다."""
    body = sql.strip().rstrip(";").strip()
    m = re.search(
        r'FROM\s+"([^"]+)"\s+WHERE\s+(.+)$',
        body,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not m:
        return None
    table, where = m.group(1), m.group(2).strip()
    where = re.sub(r"\s+ORDER\s+BY\s+.+$", "", where, flags=re.I | re.S)
    where = re.sub(r"\s+LIMIT\s+\d+\s*$", "", where, flags=re.I)
    where = re.sub(r"\s+GROUP\s+BY\s+.+$", "", where, flags=re.I | re.S)
    where = re.sub(r"\s+HAVING\s+.+$", "", where, flags=re.I | re.S)
    where = where.strip().rstrip(";")
    if where.endswith(")") and "UNION" in body.upper():
        where = where.rsplit(")", 1)[0].strip()
    return table, where


def _gu_from_subset_context(
    question: str,
    session: SessionContext,
    where: str,
) -> str | None:
    from llm2sql.domain import extract_gu

    gu = extract_gu(question)
    if gu:
        return gu
    gu = extract_gu(session.last_full_question or session.last_question or "")
    if gu:
        return gu
    m = re.search(r"LIKE '%([^']+구)%'", where)
    return m.group(1) if m else None


def _rewrite_subset_built_date(
    table: str,
    where: str,
    question: str,
    session: SessionContext,
) -> tuple[str, str, bool]:
    """금정·동래 건축일은 D198 사용승인일자(A34)로 옮긴다."""
    from llm2sql.domain import d198_table_for_gu

    gu = _gu_from_subset_context(question, session, where)
    d198 = d198_table_for_gu(gu)
    last_q = session.last_full_question or session.last_question or ""
    want_apt = "아파트" in question or "아파트" in last_q
    if d198 and (
        table.startswith("AL_D010")
        or any(k in question for k in ("건설일", "지어", "준공", "사용승인"))
    ):
        table = d198
        where = where.replace('"A9"', '"A25"')
        where = re.sub(r'"A13"', '"A34"', where)
        if want_apt and "A27" not in where:
            where = f"{where} AND \"A27\" ILIKE '%아파트%'" if where else (
                "\"A27\" ILIKE '%아파트%'"
            )
        return table, where, True
    return table, where, table.startswith("AL_D198")


def try_subset_followup(
    question: str,
    session: SessionContext,
) -> Any | None:
    """직전 WHERE(구·용도·일자 등)를 유지한 채 순위/최근 건물을 조회."""
    from llm2sql.catalog_attrs import BAS, BND, D010, D060
    from llm2sql.d198_attrs import D198_SELECT_COLS
    from llm2sql.intent_router import RoutedQuery, try_route

    if not is_subset_followup(question, session):
        return None
    if is_list_attr_followup(question, session):
        return None
    from llm2sql.d198_attrs import is_year_grain_followup

    if is_year_grain_followup(question, session):
        return None
    q = question.strip()
    spec = _subset_order(q, session)
    last_order = _order_from_last_sql(session.last_sql or "")
    limit_n = _extract_followup_n(q, default=1)
    if spec is None and last_order is not None:
        col, direction = last_order
        kind_by_col = {
            "A16": "height",
            "A30": "height",
            "A14": "area",
            "A12": "area",
            "A19": "area",
            "A15": "area",
            "A13": "date",
            "A33": "date",
            "A34": "date",
            "A18": "far",
            "A20": "far",
            "A17": "far_cov",
            "A21": "far_cov",
        }
        spec = (kind_by_col.get(col, "area"), direction)
    if spec is None:
        return None
    kind, direction = spec
    from llm2sql.domain import extract_gu

    # 건축일 순위는 직전 D010 MAX(A13) SQL을 재쓰지 않고 규칙 라우트를 우선한다.
    # 다만 '최근 3개'처럼 장소 없는 짧은 후속은 직전 SQL을 재사용한다.
    if kind == "date" and extract_gu(q):
        routed = try_route(q)
        if routed is not None and (
            '"A34"' in routed.sql or '"A33"' in routed.sql
        ):
            if limit_n > 1:
                routed_sql = re.sub(
                    r"LIMIT\s+\d+\s*;?\s*$",
                    f"LIMIT {limit_n};",
                    routed.sql.strip(),
                    flags=re.I,
                )
                intent = (
                    "d198_attr_list"
                    if routed.intent.startswith("d198_")
                    else routed.intent
                )
                return RoutedQuery(intent, routed_sql)
            return routed

    parsed = _sql_table_where(session.last_sql or "")
    if parsed is None:
        return try_route(q) if kind == "date" else None
    table, where = parsed
    is_d198 = table.startswith("AL_D198")
    if kind == "date":
        table, where, is_d198 = _rewrite_subset_built_date(
            table, where, q, session
        )
    ds_map = {d.table: d for d in (D010, D060, BND, BAS)}
    ds = ds_map.get(table)
    col_map = {
        "date": "A34" if is_d198 else "A13",
        "height": "A30" if is_d198 else "A16",
        "area": "A19" if is_d198 else "A14",
        "far": "A20" if is_d198 else "A18",
        "far_cov": "A21" if is_d198 else "A17",
    }
    if ds is not None and not is_d198:
        date_col = next((a.col for a in ds.attrs if a.kind == "date"), ds.order_col)
        num_col = next((a.col for a in ds.attrs if a.kind == "numeric"), ds.order_col)
        height_col = next(
            (a.col for a in ds.attrs if "높이" in a.label), num_col
        )
        area_col = next(
            (a.col for a in ds.attrs if "면적" in a.label), num_col
        )
        far_col = next(
            (a.col for a in ds.attrs if "용적" in a.label), ds.order_col
        )
        cov_col = next(
            (a.col for a in ds.attrs if "건폐" in a.label), ds.order_col
        )
        col_map = {
            "date": date_col,
            "height": height_col,
            "area": area_col,
            "far": far_col,
            "far_cov": cov_col,
        }
    if kind == "date" and "허가" in q and not any(
        k in q for k in ("지어", "준공", "사용승인", "건설일")
    ):
        order_col = "A33" if is_d198 else col_map["date"]
    elif last_order is not None and last_order[0] not in col_map.values():
        order_col, direction = last_order
    elif last_order is not None and kind == "date":
        order_col, direction = last_order[0], last_order[1]
    else:
        order_col = col_map[kind]
    extra = ""
    if kind == "date" or order_col in {"A13", "A33", "A34"}:
        extra = f" AND \"{order_col}\"::text ~ '^[0-9]{{4}}'"
        extra += (
            f" AND TRIM(COALESCE(\"{order_col}\"::text, '')) NOT IN ('', '없음')"
        )
    if is_d198:
        cols = ", ".join(f'"{c}"' for c in D198_SELECT_COLS)
    elif ds is not None:
        cols = ", ".join(f'"{c}"' for c in ds.select_cols)
    else:
        cols = '"A0", "A4", "A5", "A9", "A11", "A12", "A14", "A16", "A24", "A26"'
    limit_n = max(1, min(limit_n, 20))
    sql = (
        f"SELECT {cols}\n"
        f'FROM "{table}"\n'
        f"WHERE {where}{extra}\n"
        f'ORDER BY "{order_col}" {direction} NULLS LAST\n'
        f"LIMIT {limit_n};"
    )
    if is_d198:
        intent = "d198_attr_list" if limit_n > 1 else "d198_attr_rank"
    elif ds is not None:
        intent = f"{ds.intent_prefix}_{'list' if limit_n > 1 else 'rank'}"
    else:
        intent = "building_rank_연면적"
    return RoutedQuery(intent, sql)
