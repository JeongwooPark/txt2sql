"""고빈도 GIS 질의 패턴을 규칙으로 해석해 SQL을 직접 생성한다."""

from __future__ import annotations

import re
from dataclasses import dataclass

import psycopg
from psycopg.rows import dict_row

from llm2sql.domain import (
    D198_TABLES,
    DONG_PATTERN,
    GU_PATTERN,
    USAGE_ALIASES,
    USAGE_PATTERN,
    age_date_predicate,
    d198_table_for_gu,
    extract_age_compare,
    extract_age_years,
    extract_gu,
    extract_place,
    extract_usage,
    is_busan_wide,
    legal_dong_guess,
    looks_like_age_question,
    place_a4_predicate,
    sane_floor_area_sql,
    sane_footprint_sql,
    sane_height_sql,
)


@dataclass(frozen=True)
class RoutedQuery:
    intent: str
    sql: str


_GU = GU_PATTERN
_DONG = DONG_PATTERN
_COUNT_HINT = ("몇", "개수", "건수", "채", "수", "세어", "구해", "알려", "조회", "얼마")
_LIST_HINT = (
    "무엇이 있어",
    "뭐가 있어",
    "뭐 있어",
    "어떤 게 있어",
    "어떤것이 있어",
    "어떤 것이 있어",
    "목록",
    "리스트",
)


def _wants_count(q: str) -> bool:
    # 순위·최댓값 질의는 건수가 아님
    if any(k in q for k in ("가장", "제일", "최대", "상위", "1등", "큰 순", "높은 순")):
        return False
    if any(k in q for k in _COUNT_HINT):
        return True
    # "해운대구 건물?"처럼 짧은 물음만 건수로 간주
    stripped = q.rstrip()
    if stripped.endswith(("?", "？")) and len(stripped) <= 24:
        return True
    return False


def _wants_list(q: str) -> bool:
    return any(k in q for k in _LIST_HINT)


def try_route(
    question: str,
    conn: psycopg.Connection | None = None,
) -> RoutedQuery | None:
    q = question.strip()

    # 좌표 버퍼 (LLM이 D198로 빠지는 경우 방지)
    m = re.search(
        r"(?:좌표|점)?\s*\(?\s*(12\d\.\d+)\s*[, ]\s*(35\.\d+)\s*\)?.*?"
        r"(\d+)\s*미터",
        q,
    )
    if m and ("이내" in q or "근처" in q or "버퍼" in q):
        lon, lat, meters = m.group(1), m.group(2), m.group(3)
        return RoutedQuery(
            "buffer_count",
            (
                'SELECT COUNT(*) AS cnt\n'
                'FROM "AL_D010_26_20250704" b\n'
                "WHERE ST_DWithin(\n"
                "  b.geometry::geography,\n"
                f"  ST_SetSRID(ST_MakePoint({lon}, {lat}), 4326)::geography,\n"
                f"  {meters}\n"
                ");"
            ),
        )

    # 구 기초구역 ∩ 산업단지
    m = re.search(rf"{_GU}\s*기초구역.{{0,20}}교차.{{0,20}}산업단지", q)
    if not m:
        m = re.search(rf"산업단지.{{0,24}}{_GU}\s*기초구역", q)
    if m and ("산업단지" in q and "기초구역" in q and "교차" in q):
        gu = m.group(1)
        return RoutedQuery(
            "industrial_bas_intersect",
            (
                'SELECT COUNT(DISTINCT i."A0") AS cnt\n'
                'FROM "AL_D060_00_20250804" i\n'
                'JOIN "TL_KODIS_BAS_26_202507" t\n'
                "  ON ST_Intersects(i.geometry, t.geometry)\n"
                f'WHERE t."SIG_KOR_NM" = \'{gu}\';'
            ),
        )

    # 기초구역 개수
    m = re.search(rf"{_GU}\s*기초구역", q)
    if (
        m
        and _wants_count(q)
        and "산업단지" not in q
        and "교차" not in q
        and "면적" not in q
    ):
        gu = m.group(1)
        return RoutedQuery(
            "bas_count",
            (
                'SELECT COUNT(*) AS cnt\n'
                'FROM "TL_KODIS_BAS_26_202507"\n'
                f'WHERE "SIG_KOR_NM" = \'{gu}\';'
            ),
        )

    # 건축 경과년수 (동래/금정 D198 사용승인·허가일자)
    aged = _route_building_age(q, conn=conn)
    if aged is not None:
        return aged

    # 공공시설 등 목록
    listed = _route_facility_list(q, conn=conn)
    if listed is not None:
        return listed

    # 장소(동 우선) + 용도 COUNT / 행정동 공간 COUNT
    usage_count = _route_place_usage_count(q, conn=conn)
    if usage_count is not None:
        return usage_count

    # 장소(구/동) + 건물 건수 (용도 미지정)
    place_count = _route_place_building_count(q)
    if place_count is not None:
        return place_count

    # 구 + 높이 (이상/넘는)
    m = re.search(
        rf"{_GU}.*?높이[가이]?\s*(\d+)\s*미터",
        q,
    )
    if not m:
        m = re.search(rf"{_GU}.*?높이\s*(\d+)\s*미터", q)
    if m and ("높이" in q) and _wants_count(q):
        gu, meters = m.group(1), m.group(2)
        op = ">" if ("넘는" in q or "초과" in q) else ">="
        return RoutedQuery(
            "building_height_count",
            (
                'SELECT COUNT(*) AS cnt\n'
                'FROM "AL_D010_26_20250704"\n'
                f'WHERE "A4" LIKE \'%{gu}%\' AND "A16" {op} {meters};'
            ),
        )

    # 구 + 지상층 (지상층 / 지상 N층)
    m = re.search(rf"{_GU}.*?지상\s*층?[이]?\s*(\d+)\s*층", q)
    if m and ("지상" in q) and (_wants_count(q) or "이상" in q):
        gu, floors = m.group(1), m.group(2)
        return RoutedQuery(
            "building_floor_count",
            (
                'SELECT COUNT(*) AS cnt\n'
                'FROM "AL_D010_26_20250704"\n'
                f'WHERE "A4" LIKE \'%{gu}%\' AND "A26" >= {floors};'
            ),
        )

    # 동 공간 포함 (안에/내부/안쪽/경계 안)
    m = re.search(
        rf"{_DONG}\s*(?:안(?:에|쪽)?|내부|경계\s*안).{{0,12}}건물",
        q,
    )
    if not m:
        m = re.search(rf"건물.{{0,12}}{_DONG}\s*(?:안(?:에|쪽)?|내부|경계\s*안)", q)
        if m:
            dong = m.group(1)
        else:
            dong = None
    else:
        dong = m.group(1)
    if dong and _wants_count(q):
        return RoutedQuery(
            "building_in_dong_spatial",
            (
                'SELECT COUNT(*) AS cnt\n'
                'FROM "AL_D010_26_20250704" b\n'
                'JOIN "BND_ADM_DONG_PG" d\n'
                "  ON ST_Intersects(b.geometry, d.geometry)\n"
                f'WHERE d."ADM_NM" LIKE \'%{dong}%\';'
            ),
        )

    # 산업단지 코드 prefix
    if "산업단지" in q and re.search(r"\b26\b|26으로", q) and _wants_count(q):
        if "교차" not in q and "기초구역" not in q:
            return RoutedQuery(
                "industrial_code_prefix",
                (
                    'SELECT COUNT(*) AS cnt\n'
                    'FROM "AL_D060_00_20250804"\n'
                    'WHERE "A4" LIKE \'26%\';'
                ),
            )

    # 구 주요용도명/용도 종류 (동래→D198_26260, 금정→D198_26410, 그 외 D010 A9)
    if "종류" in q and ("용도" in q):
        if "동래" in q:
            return RoutedQuery(
                "usage_kinds_dongrae",
                (
                    'SELECT COUNT(DISTINCT "A25") AS cnt\n'
                    'FROM "AL_D198_26260_20250115";'
                ),
            )
        if "금정" in q:
            return RoutedQuery(
                "usage_kinds_geumjeong",
                (
                    'SELECT COUNT(DISTINCT "A25") AS cnt\n'
                    'FROM "AL_D198_26410_20250115";'
                ),
            )

    # 구 연면적 상위 N
    m = re.search(rf"{_GU}.{{0,20}}연면적.{{0,16}}(?:상위\s*)?(\d+)", q)
    if m and any(k in q for k in ("상위", "큰 순", "연면적")):
        gu, n = m.group(1), m.group(2)
        only_area = any(k in q for k in ("면적값", "면적 값", "연면적만", "값만"))
        cols = (
            '"A14" AS v'
            if only_area or (n == "1" and "가장" in q)
            else '"A4", "A9", "A14"'
        )
        if only_area or (n == "1" and "가장" in q and "보여" not in q):
            if "가장" in q and n == "1":
                cols = '"A14" AS v'
                return RoutedQuery(
                    "building_area_top1_value",
                    (
                        f"SELECT {cols}\n"
                        'FROM "AL_D010_26_20250704"\n'
                        f'WHERE "A4" LIKE \'%{gu}%\'\n'
                        'ORDER BY "A14" DESC NULLS LAST\n'
                        "LIMIT 1;"
                    ),
                )
        return RoutedQuery(
            "building_area_topn",
            (
                f"SELECT {cols}\n"
                'FROM "AL_D010_26_20250704"\n'
                f'WHERE "A4" LIKE \'%{gu}%\'\n'
                'ORDER BY "A14" DESC NULLS LAST\n'
                f"LIMIT {n};"
            ),
        )

    # 구 기초구역 면적 상위 N (면적값이면 BAS_AR만)
    m = re.search(rf"{_GU}\s*기초구역.{{0,24}}(?:상위\s*)?(\d+)", q)
    if m and any(k in q for k in ("면적", "큰 순", "상위")):
        gu, n = m.group(1), m.group(2)
        if any(k in q for k in ("면적값", "면적 값", "면적만")) or (
            n == "1" and "면적" in q
        ):
            return RoutedQuery(
                "bas_area_topn_value",
                (
                    'SELECT "BAS_AR" AS v\n'
                    'FROM "TL_KODIS_BAS_26_202507"\n'
                    f'WHERE "SIG_KOR_NM" = \'{gu}\'\n'
                    'ORDER BY "BAS_AR" DESC NULLS LAST\n'
                    f"LIMIT {n};"
                ),
            )
        return RoutedQuery(
            "bas_area_topn",
            (
                'SELECT "BAS_AR", "BAS_ID", "SIG_KOR_NM"\n'
                'FROM "TL_KODIS_BAS_26_202507"\n'
                f'WHERE "SIG_KOR_NM" = \'{gu}\'\n'
                'ORDER BY "BAS_AR" DESC NULLS LAST\n'
                f"LIMIT {n};"
            ),
        )

    # 구 연면적 임계 COUNT (+ 용도 선택)
    m = re.search(rf"{_GU}.{{0,24}}연면적\s*(\d+).{{0,12}}이상", q)
    if m and _wants_count(q):
        gu, area = m.group(1), m.group(2)
        usage = None
        um = re.search(USAGE_PATTERN, q)
        if um:
            usage = USAGE_ALIASES.get(um.group(1), um.group(1))
        place = extract_place(q)
        if place and place.endswith("동"):
            where = f'{place_a4_predicate(place)} AND "A14" >= {area}'
            if gu:
                where = f'({where}) AND "A4" LIKE \'%{gu}%\''
        else:
            where = f'"A4" LIKE \'%{gu}%\' AND "A14" >= {area}'
        if usage:
            where += f' AND "A9" = \'{usage}\''
        return RoutedQuery(
            "building_area_threshold_count",
            (
                'SELECT COUNT(*) AS cnt\n'
                'FROM "AL_D010_26_20250704"\n'
                f"WHERE {where};"
            ),
        )

    ranked = _route_building_rank(q)
    if ranked is not None:
        return ranked

    return None


_USAGE_PAT = USAGE_PATTERN
_USAGE_SQL = USAGE_ALIASES


def _resolve_d198_table(
    q: str,
    *,
    conn: psycopg.Connection | None,
    gu: str | None,
    place: str | None,
) -> str | None:
    table = d198_table_for_gu(gu)
    if table:
        return table
    if conn is None or not place:
        return None
    with conn.cursor(row_factory=dict_row) as cur:
        for tbl in (
            "AL_D198_26410_20250115",
            "AL_D198_26260_20250115",
        ):
            cur.execute(
                f"""
                SELECT 1 AS ok FROM "{tbl}"
                WHERE "A4" LIKE %s
                LIMIT 1
                """,
                (f"%{place}%",),
            )
            if cur.fetchone():
                return tbl
    return None


def _route_place_building_count(q: str) -> RoutedQuery | None:
    """용도 없이 구/동 건물 건수만 묻는 경우."""
    if not any(k in q for k in ("건물", "건축물", "채")):
        return None
    if extract_usage(q):
        return None
    if not _wants_count(q):
        return None
    if looks_like_age_question(q):
        return None
    if "산업단지" in q or "기초구역" in q:
        return None
    if any(k in q for k in ("연면적", "건물면적", "대지면적", "높이", "지상층", "층수")):
        return None
    if any(k in q for k in ("안에", "내부", "안쪽", "경계 안")):
        return None

    place = extract_place(q)
    gu = extract_gu(q)
    if not place and not gu:
        return None

    if place and place.endswith("동"):
        where = place_a4_predicate(place)
        if gu:
            where = f"({where}) AND \"A4\" LIKE '%{gu}%'"
    elif gu:
        where = f"\"A4\" LIKE '%{gu}%'"
    else:
        return None

    return RoutedQuery(
        "building_place_count",
        (
            'SELECT COUNT(*) AS cnt\n'
            'FROM "AL_D010_26_20250704"\n'
            f"WHERE {where};"
        ),
    )


def _route_place_usage_count(
    q: str,
    *,
    conn: psycopg.Connection | None,
) -> RoutedQuery | None:
    usage = extract_usage(q)
    if not usage or "산업단지" in q:
        return None
    if not _wants_count(q):
        return None
    if ("연면적" in q or "건물면적" in q or "대지면적" in q) and any(
        k in q for k in ("이상", "이하", "초과", "미만", "넘는")
    ):
        return None
    if looks_like_age_question(q):
        return None

    place = extract_place(q)
    gu = extract_gu(q)
    if not place and not gu:
        return None

    # 행정동(구서1동) → 경계 교차
    if place and place.endswith("동") and conn is not None:
        from llm2sql.clarify_qa import _lookup_admin_dong, _lookup_places

        admin = _lookup_admin_dong(conn, place)
        if admin:
            legal_hits = _lookup_places(conn, place, gu=gu)
            if not legal_hits:
                if usage == "공공용시설":
                    usage_filter = (
                        ' AND (b."A9" = \'공공용시설\' OR b."A9" ILIKE \'%공공%\')'
                    )
                else:
                    usage_filter = f' AND b."A9" = \'{usage}\''
                return RoutedQuery(
                    "building_admin_dong_usage_count",
                    (
                        'SELECT COUNT(*) AS cnt\n'
                        'FROM "AL_D010_26_20250704" b\n'
                        'JOIN "BND_ADM_DONG_PG" d\n'
                        "  ON ST_Intersects(b.geometry, d.geometry)\n"
                        f'WHERE d."ADM_NM" LIKE \'%{place}%\'{usage_filter};'
                    ),
                )

    if place and place.endswith("동"):
        where = place_a4_predicate(place)
        if gu:
            where = f"({where}) AND \"A4\" LIKE '%{gu}%'"
    elif gu:
        where = f"\"A4\" LIKE '%{gu}%'"
    else:
        return None

    if usage == "공공용시설":
        where += " AND (\"A9\" = '공공용시설' OR \"A9\" ILIKE '%공공%')"
    else:
        where += f" AND \"A9\" = '{usage}'"

    return RoutedQuery(
        "building_usage_count",
        (
            'SELECT COUNT(*) AS cnt\n'
            'FROM "AL_D010_26_20250704"\n'
            f"WHERE {where};"
        ),
    )


def _route_building_age(
    q: str,
    *,
    conn: psycopg.Connection | None,
) -> RoutedQuery | None:
    if not looks_like_age_question(q):
        return None
    years = extract_age_years(q)
    if years is None:
        return None

    gu = extract_gu(q)
    place = extract_place(q)
    usage = extract_usage(q)
    compare = extract_age_compare(q)
    date_col = "A33" if "허가" in q and "사용승인" not in q else "A34"

    table = _resolve_d198_table(q, conn=conn, gu=gu, place=place)
    tables: list[str]
    if table:
        tables = [table]
    elif is_busan_wide(q) or (gu is None and place is None):
        # 부산 전체·장소 미지정 → 사용승인일이 있는 동래+금정 합산
        tables = list(D198_TABLES)
    else:
        return None

    where: list[str] = []
    if place and place.endswith("동"):
        dong = place
        if conn is not None:
            from llm2sql.clarify_qa import _lookup_admin_dong

            if _lookup_admin_dong(conn, place):
                guessed = legal_dong_guess(place)
                if guessed:
                    dong = guessed
        where.append(f'"A4" LIKE \'%{dong}%\'')
        if gu:
            where.append(f'"A4" LIKE \'%{gu}%\'')
    elif gu:
        where.append(f'"A4" LIKE \'%{gu}%\'')

    if usage and usage != "공공용시설":
        where.append(f'"A25" = \'{usage}\'')
    elif usage == "공공용시설":
        where.append("(\"A29\" = '공공용' OR \"A25\" ILIKE '%공공%')")

    where.append(age_date_predicate(date_col, years, compare))
    where_sql = " AND ".join(where) if where else age_date_predicate(
        date_col, years, compare
    )

    if len(tables) == 1:
        sql = (
            "SELECT COUNT(*) AS cnt\n"
            f'FROM "{tables[0]}"\n'
            f"WHERE {where_sql};"
        )
        intent = "building_age_count"
    else:
        parts = [
            f'SELECT COUNT(*) AS c FROM "{t}" WHERE {where_sql}' for t in tables
        ]
        sql = (
            "SELECT COALESCE(SUM(c), 0) AS cnt\n"
            "FROM (\n  "
            + "\n  UNION ALL\n  ".join(parts)
            + "\n) AS age_parts;"
        )
        intent = "building_age_count_d198_partial"

    return RoutedQuery(intent, sql)


def _route_facility_list(
    q: str,
    *,
    conn: psycopg.Connection | None,
) -> RoutedQuery | None:
    if not _wants_list(q):
        return None
    usage = extract_usage(q)
    public = usage == "공공용시설" or any(
        k in q for k in ("공공시설", "공공시설물", "공공용")
    )
    if not public and usage is None:
        return None
    place = extract_place(q)
    gu = extract_gu(q)
    if not place and not gu:
        return None

    table = _resolve_d198_table(q, conn=conn, gu=gu, place=place)
    if table and public:
        where: list[str] = []
        if place and place.endswith("동"):
            dong = place
            if conn is not None:
                from llm2sql.clarify_qa import _lookup_admin_dong

                if _lookup_admin_dong(conn, place):
                    guessed = legal_dong_guess(place)
                    if guessed:
                        dong = guessed
            where.append(f'"A4" LIKE \'%{dong}%\'')
        elif gu:
            where.append(f'"A4" LIKE \'%{gu}%\'')
        where.append("(\"A29\" = '공공용' OR \"A25\" ILIKE '%공공%' OR \"A28\" = '5')")
        where_sql = " AND ".join(where)
        return RoutedQuery(
            "public_facility_list",
            (
                'SELECT "A25" AS usage, "A13" AS name, "A7" AS jibeon, COUNT(*) AS n\n'
                f'FROM "{table}"\n'
                f"WHERE {where_sql}\n"
                'GROUP BY "A25", "A13", "A7"\n'
                "ORDER BY n DESC NULLS LAST\n"
                "LIMIT 30;"
            ),
        )

    where2: list[str] = []
    if place and place.endswith("동"):
        where2.append(place_a4_predicate(place))
        if gu:
            where2.append(f'"A4" LIKE \'%{gu}%\'')
    elif gu:
        where2.append(f'"A4" LIKE \'%{gu}%\'')
    if public:
        where2.append("(\"A9\" = '공공용시설' OR \"A9\" ILIKE '%공공%')")
    elif usage:
        where2.append(f'"A9" = \'{usage}\'')
    where_sql2 = " AND ".join(where2)
    return RoutedQuery(
        "facility_usage_list",
        (
            'SELECT "A9" AS usage, "A24" AS name, "A5" AS jibeon, COUNT(*) AS n\n'
            'FROM "AL_D010_26_20250704"\n'
            f"WHERE {where_sql2}\n"
            'GROUP BY "A9", "A24", "A5"\n'
            "ORDER BY n DESC NULLS LAST\n"
            "LIMIT 30;"
        ),
    )


_RANK_SUPERLATIVE = (
    "가장 큰",
    "제일 큰",
    "가장 넓은",
    "제일 넓은",
    "가장넓은",
    "제일넓은",
    "최대",
    "1등",
    "최고",
)


def _route_building_rank(q: str) -> RoutedQuery | None:
    metric_col = None
    metric_name = None
    has_super = any(k in q for k in _RANK_SUPERLATIVE)
    if any(k in q for k in ("건물면적", "건축물면적", "건축면적")) and has_super:
        metric_col, metric_name = "A12", "건물면적"
    elif "연면적" in q and has_super:
        metric_col, metric_name = "A14", "연면적"
    elif "대지면적" in q and has_super:
        metric_col, metric_name = "A15", "대지면적"
    elif any(k in q for k in ("가장 높", "제일 높")) or (
        "높이" in q and any(k in q for k in ("가장", "제일", "최대", "1등", "최고"))
    ):
        metric_col, metric_name = "A16", "높이"
    elif ("지상층" in q or "층수" in q or "지상 층" in q) and any(
        k in q for k in ("가장 많", "제일 많", "가장 높", "최대", "1등", "제일 높")
    ):
        metric_col, metric_name = "A26", "지상층"
    else:
        return None

    place = extract_place(q)
    where: list[str] = []
    if place:
        where.append(place_a4_predicate(place))
    # 장소 없음·부산시 전체 → AL_D010 전역 (부산 DB)

    usage_sql = None
    m = re.search(_USAGE_PAT, q)
    if m:
        usage_sql = _USAGE_SQL.get(m.group(1), m.group(1))
    if usage_sql:
        where.append(f'"A9" = \'{usage_sql}\'')

    if metric_col == "A16":
        where.append(sane_height_sql("A16", "A26"))
    elif metric_col == "A12":
        where.append(sane_footprint_sql("A12", "A14"))
    elif metric_col == "A14":
        where.append(sane_floor_area_sql("A14"))
    elif metric_col == "A15":
        where.append('"A15" > 0 AND "A15" <= 2000000')

    where_sql = (" WHERE " + " AND ".join(where)) if where else ""

    return RoutedQuery(
        f"building_rank_{metric_name}",
        (
            'SELECT "A0", "A4", "A5", "A9", "A12", "A14", "A15", "A16", "A19", "A24", "A25", "A26"\n'
            'FROM "AL_D010_26_20250704"'
            f"{where_sql}\n"
            f'ORDER BY "{metric_col}" DESC NULLS LAST\n'
            "LIMIT 1;"
        ),
    )


def fix_common_sql_mistakes(sql: str, question: str | None = None) -> str:
    """LLM SQL의 고빈도 실수를 후처리로 교정."""
    out = re.sub(
        r'"A3"\s+LIKE\s+\'%([가-힣0-9]+(?:구|동))%\'',
        r'"A4" LIKE \'%\1%\'',
        sql,
    )
    if "ST_DWithin" in out or "ST_DWITHIN" in out.upper():
        out = out.replace("AL_D198_26260_20250115", "AL_D010_26_20250704")
        out = out.replace("AL_D198_26410_20250115", "AL_D010_26_20250704")

    q = (question or "").strip()
    if q:
        forced = _route_building_rank(q)
        if forced is not None:
            # 순위 질의는 규칙 SQL로 고정 (잘못된 ORDER BY/컬럼 별칭 방지)
            return forced.sql
    return out