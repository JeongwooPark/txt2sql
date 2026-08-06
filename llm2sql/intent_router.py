"""고빈도 GIS 질의 패턴을 규칙으로 해석해 SQL을 직접 생성한다."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class RoutedQuery:
    intent: str
    sql: str


_GU = (
    r"(중구|서구|동구|영도구|부산진구|동래구|남구|북구|해운대구|사하구|"
    r"금정구|강서구|연제구|수영구|사상구|기장군|[가-힣]{1,6}구)"
)
_DONG = r"([가-힣0-9]{1,12}동)"
_COUNT_HINT = ("몇", "개수", "건수", "채", "수", "세어", "구해", "알려", "조회", "얼마")


def _wants_count(q: str) -> bool:
    return any(k in q for k in _COUNT_HINT) or q.rstrip().endswith("?") or q.rstrip().endswith("？")


def try_route(question: str) -> RoutedQuery | None:
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

    # 구 + 용도 COUNT
    m = re.search(
        rf"{_GU}.{{0,16}}(단독주택|공동주택|공장|아파트|창고시설|교육연구시설)",
        q,
    )
    if m:
        gu, usage = m.group(1), m.group(2)
    else:
        m = re.search(
            rf"(단독주택|공동주택|공장|아파트|창고시설|교육연구시설).{{0,16}}{_GU}",
            q,
        )
        if m:
            usage, gu = m.group(1), m.group(2)
        else:
            gu = usage = None
    if gu and usage and _wants_count(q) and "산업단지" not in q:
        return RoutedQuery(
            "building_usage_count",
            (
                'SELECT COUNT(*) AS cnt\n'
                'FROM "AL_D010_26_20250704"\n'
                f'WHERE "A4" LIKE \'%{gu}%\' AND "A9" = \'{usage}\';'
            ),
        )

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
                    'FROM "AL_D198_26260_20250115"\n'
                    'WHERE "A4" LIKE \'%동래구%\' AND "A25" IS NOT NULL;'
                ),
            )
        if "금정" in q:
            return RoutedQuery(
                "usage_kinds_geumjeong",
                (
                    'SELECT COUNT(DISTINCT "A25") AS cnt\n'
                    'FROM "AL_D198_26410_20250115"\n'
                    'WHERE "A4" LIKE \'%금정구%\' AND "A25" IS NOT NULL;'
                ),
            )

    # 구 연면적 상위 N / 가장 큰 연면적
    if "연면적" in q:
        m = re.search(rf"{_GU}.{{0,24}}연면적.{{0,20}}상위\s*(\d+)", q)
        if not m:
            m = re.search(rf"{_GU}.{{0,24}}연면적.{{0,20}}(\d+)\s*개", q)
        if m and any(k in q for k in ("상위", "큰", "많은", "순위")):
            gu, n = m.group(1), m.group(2)
            only_area = any(k in q for k in ("면적값", "연면적 값", "연면적값", "가장 큰"))
            cols = '"A14" AS v' if only_area or n == "1" and "가장" in q else '"A4", "A9", "A14"'
            if "가장 큰" in q or "1등" in q or "상위 1" in q:
                n = "1"
                cols = '"A14" AS v'
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
        m = re.search(rf"{_GU}.{{0,20}}(?:연면적).{{0,20}}가장 큰", q)
        if m:
            gu = m.group(1)
            return RoutedQuery(
                "building_area_max",
                (
                    'SELECT "A14" AS v\n'
                    'FROM "AL_D010_26_20250704"\n'
                    f'WHERE "A4" LIKE \'%{gu}%\'\n'
                    'ORDER BY "A14" DESC NULLS LAST\n'
                    "LIMIT 1;"
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

    # 구 연면적 임계 COUNT
    m = re.search(rf"{_GU}.{{0,20}}연면적\s*(\d+).{{0,8}}이상", q)
    if m and _wants_count(q):
        gu, area = m.group(1), m.group(2)
        return RoutedQuery(
            "building_area_threshold_count",
            (
                'SELECT COUNT(*) AS cnt\n'
                'FROM "AL_D010_26_20250704"\n'
                f'WHERE "A4" LIKE \'%{gu}%\' AND "A14" >= {area};'
            ),
        )

    # 동/구 + (용도) + 연면적/높이/지상층 최대(가장 큰·높은·많은)
    ranked = _route_building_rank(q)
    if ranked is not None:
        return ranked

    return None


_USAGE_PAT = (
    r"(아파트|공동주택|단독주택|공장|창고시설|창고|"
    r"교육연구시설|업무시설|숙박시설|종교시설)"
)
_USAGE_SQL = {
    "아파트": "공동주택",
    "공동주택": "공동주택",
    "단독주택": "단독주택",
    "공장": "공장",
    "창고시설": "창고시설",
    "창고": "창고시설",
    "교육연구시설": "교육연구시설",
    "업무시설": "업무시설",
    "숙박시설": "숙박시설",
    "종교시설": "종교시설",
}


def _route_building_rank(q: str) -> RoutedQuery | None:
    metric_col = None
    metric_name = None
    # 건물면적=건축물면적(A12). '연면적'보다 먼저 건물/건축 면적을 판별
    if any(k in q for k in ("건물면적", "건축물면적", "건축면적")) and any(
        k in q for k in ("가장 큰", "제일 큰", "최대", "1등", "가장 넓은")
    ):
        metric_col, metric_name = "A12", "건물면적"
    elif "연면적" in q and any(
        k in q for k in ("가장 큰", "제일 큰", "최대", "1등", "가장 넓은")
    ):
        metric_col, metric_name = "A14", "연면적"
    elif "대지면적" in q and any(
        k in q for k in ("가장 큰", "제일 큰", "최대", "1등", "가장 넓은")
    ):
        metric_col, metric_name = "A15", "대지면적"
    elif "높이" in q and any(k in q for k in ("가장 높", "제일 높", "최대", "1등")):
        metric_col, metric_name = "A16", "높이"
    elif ("지상층" in q or "층수" in q or "지상 층" in q) and any(
        k in q for k in ("가장 많", "제일 많", "가장 높", "최대", "1등")
    ):
        metric_col, metric_name = "A26", "지상층"
    else:
        return None

    place = None
    place_pred = None
    m = re.search(_DONG, q)
    if m:
        place = m.group(1)
        place_pred = f'("A4" LIKE \'% {place}\' OR "A4" = \'{place}\')'
    else:
        m = re.search(_GU, q)
        if m:
            place = m.group(1)
            place_pred = f'"A4" LIKE \'%{place}%\''
    if not place_pred:
        return None

    usage_sql = None
    m = re.search(_USAGE_PAT, q)
    if m:
        usage_sql = _USAGE_SQL.get(m.group(1), m.group(1))

    where = [place_pred]
    if usage_sql:
        where.append(f'"A9" = \'{usage_sql}\'')
    where_sql = " AND ".join(where)

    return RoutedQuery(
        f"building_rank_{metric_name}",
        (
            'SELECT "A0", "A4", "A5", "A9", "A12", "A14", "A15", "A16", "A19", "A24", "A25", "A26"\n'
            'FROM "AL_D010_26_20250704"\n'
            f"WHERE {where_sql}\n"
            f'ORDER BY "{metric_col}" DESC NULLS LAST\n'
            "LIMIT 1;"
        ),
    )


def fix_common_sql_mistakes(sql: str) -> str:
    """LLM SQL의 고빈도 실수를 후처리로 교정."""
    out = re.sub(
        r'"A3"\s+LIKE\s+\'%([가-힣0-9]+(?:구|동))%\'',
        r'"A4" LIKE \'%\1%\'',
        sql,
    )
    # 버퍼/전역 건물 질의에서 동래 전용 테이블 단독 사용 → AL_D010으로 교체
    if "ST_DWithin" in out or "ST_DWITHIN" in out.upper():
        out = out.replace("AL_D198_26260_20250115", "AL_D010_26_20250704")
        out = out.replace("AL_D198_26410_20250115", "AL_D010_26_20250704")
    return out
