"""평가문항 500개 생성: 기존 NL100 + 신규 복합·후속 400.

정답은 KorDB 실쿼리 결과이며, SQL 토큰 일치만으로는 정답으로 보지 않는다.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv
import psycopg
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
URL = os.environ.get("DATABASE_URL", "").strip()

D010 = "AL_D010_26_20250704"
D060 = "AL_D060_00_20250804"
BND = "BND_ADM_DONG_PG"
BAS = "TL_KODIS_BAS_26_202507"
def _resolve_d198_tables() -> tuple[str, str]:
    """금정·동래 D198 — DB에 등록된 최신 스냅샷."""
    fallback = ("AL_D198_26410_20260715", "AL_D198_26260_20260715")
    try:
        from txt2sql.config import load_settings
        from txt2sql.data.coverage import discover_d198_coverage

        cov = discover_d198_coverage(load_settings())
        gj = cov.get("금정구")
        dr = cov.get("동래구")
        if gj and dr:
            return gj, dr
    except Exception:
        pass
    return fallback


D198_GJ, D198_DR = _resolve_d198_tables()

OUT_MD = ROOT / "docs" / "평가문항_500.md"
OUT_JSON = ROOT / "docs" / "평가문항_500.json"
NL100 = ROOT / "scripts" / "smoke_nl100.json"

PYEONG_M2 = 400.0 / 121.0  # 법정 1평


GU_CODES = {
    "중구": "26110",
    "서구": "26140",
    "동구": "26170",
    "영도구": "26200",
    "부산진구": "26230",
    "동래구": "26260",
    "남구": "26290",
    "북구": "26320",
    "해운대구": "26350",
    "사하구": "26380",
    "금정구": "26410",
    "강서구": "26440",
    "연제구": "26470",
    "수영구": "26500",
    "사상구": "26530",
    "기장군": "26710",
}


def a4(dong: str) -> str:
    s = dong.replace("'", "''")
    return f'("A4" LIKE \'% {s}\' OR "A4" = \'{s}\')'


def gu(name: str) -> str:
    code = GU_CODES.get(name)
    if code:
        return f'"A3" LIKE \'{code}%\''
    s = name.replace("'", "''")
    return f'"A4" LIKE \'%{s}%\''


def num(col: str) -> str:
    return f'NULLIF(TRIM("{col}"::text), \'\')::float8'


def admin_eq(name: str) -> str:
    s = name.replace("'", "''")
    if re.fullmatch(r"[가-힣]+\d+동", s):
        return f'd."ADM_NM" = \'{s}\' AND d."ADM_CD" LIKE \'21%\''
    stem = s[:-1] if s.endswith("동") else s
    return (
        f"(d.\"ADM_NM\" = '{s}' OR d.\"ADM_NM\" ~ '^{stem}[0-9]+동$') "
        f"AND d.\"ADM_CD\" LIKE '21%'"
    )


def d010_cnt(where: str) -> str:
    return f'SELECT COUNT(*)::bigint AS n FROM "{D010}" WHERE {where}'


def d010_list(where: str, cols: str, order: str, limit: int = 10) -> str:
    return (
        f"SELECT {cols}\nFROM \"{D010}\"\nWHERE {where}\n"
        f"ORDER BY {order} DESC NULLS LAST\nLIMIT {limit}"
    )


def d010_agg(select: str, where: str) -> str:
    return f'SELECT {select} FROM "{D010}" WHERE {where}'


def age_lt(col: str, years: int) -> str:
    from txt2sql.query_understanding.temporal import reference_date_sql

    ref = reference_date_sql()
    return (
        f"\"{col}\" ~ '^[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}$' "
        f"AND \"{col}\"::date > ({ref} - INTERVAL '{years} years')"
    )


def age_gte(col: str, years: int) -> str:
    from txt2sql.query_understanding.temporal import reference_date_sql

    ref = reference_date_sql()
    return (
        f"\"{col}\" ~ '^[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}$' "
        f"AND \"{col}\"::date <= ({ref} - INTERVAL '{years} years')"
    )


def year_ge(col: str, year: int) -> str:
    return (
        f"\"{col}\"::text ~ '^[0-9]{{4}}' "
        f"AND LEFT(regexp_replace(\"{col}\"::text, '[^0-9]', '', 'g'), 4) >= '{year}'"
    )


def year_between(col: str, lo: int, hi: int) -> str:
    return (
        f"\"{col}\"::text ~ '^[0-9]{{4}}' "
        f"AND LEFT(regexp_replace(\"{col}\"::text, '[^0-9]', '', 'g'), 4)::int "
        f"BETWEEN {lo} AND {hi}"
    )


def rc(col: str, pat: str) -> str:
    return f'"{col}" ILIKE \'{pat}\''


def fmt_num(v) -> str:
    if v is None:
        return "없음"
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, int):
        return f"{v:,}"
    if isinstance(v, float):
        if abs(v - round(v)) < 1e-9:
            return f"{int(round(v)):,}"
        return f"{v:,.4f}".rstrip("0").rstrip(".")
    return str(v)


def fmt_rows_inline(rows: list[dict], limit: int = 12) -> str:
    if not rows:
        return "해당 조건에 맞는 결과가 없습니다."
    parts = []
    for i, row in enumerate(rows[:limit], 1):
        bits = []
        for k, v in row.items():
            if k.lower() in {"geometry", "geom"}:
                continue
            bits.append(f"{k}={fmt_num(v)}")
        parts.append(f"{i}. " + ", ".join(bits))
    extra = f" 외 {len(rows) - limit}건" if len(rows) > limit else ""
    return " / ".join(parts) + extra


@dataclass
class Case:
    id: str
    cat: str
    q: str
    sql: str | None
    kind: str
    unit: str = "채"
    session: str | None = None
    parent: str | None = None
    gold_text: str | None = None
    source: str = "new"
    note: str = ""
    result: dict = field(default_factory=dict)


def C(
    id: str,
    cat: str,
    q: str,
    sql: str | None,
    kind: str = "count",
    unit: str = "채",
    session: str | None = None,
    parent: str | None = None,
    gold_text: str | None = None,
    source: str = "new",
    note: str = "",
) -> Case:
    return Case(
        id=id,
        cat=cat,
        q=q,
        sql=sql,
        kind=kind,
        unit=unit,
        session=session,
        parent=parent,
        gold_text=gold_text,
        source=source,
        note=note,
    )


def n100_cases() -> list[Case]:
    """기존 smoke_nl100 100문항 + 정답 쿼리."""
    p80 = 80 * PYEONG_M2
    meta = {
        "N001": ("안내", "부산 GIS(건물·행정구역·기초구역·산업단지)를 자연어로 조회하는 질의 도우미이다."),
        "N002": ("안내", "가능한 질문: 데이터셋/컬럼 설명, 건수·순위·공간 조회, 동·용도 특징 요약, 모호 표현 확인."),
        "N003": ("안내", "예: 해운대구 건물 몇 채, 구서동 주변 100m, A16 의미, 구서동 아파트 특징."),
        "N004": ("범위외", "범위 외. 기상 예보는 보유 데이터에 없다."),
        "N005": ("범위외", "범위 외. 항공편 현황은 보유 데이터에 없다."),
        "N006": ("범위외", "범위 외. 환율은 보유 데이터에 없다."),
        "N007": ("범위외", "범위 외. 점심 메뉴 추천은 보유 데이터에 없다."),
        "N026": ("모호", "확인 필요. 중앙동은 여러 구에 있어 구를 지정해야 한다."),
        "N027": ("모호", "확인 필요. 신흥동은 여러 구에 있어 구를 지정해야 한다."),
        "N030": ("오탐방지", "자동문은 건물 구조/지명이 아니다. 건물 구조(철근콘크리트 등)나 장소가 있는 질문으로 바꿔야 한다."),
        "N076": ("주관", "주관 평가('제일 괜찮은')는 데이터로 확정할 수 없다. 높이·연면적·층수 등 객관 지표 기준을 확인해야 한다."),
        "N077": ("주관", "주관 평가('살기 좋은')는 데이터로 확정할 수 없다. 객관 지표 기준을 확인해야 한다."),
        "N078": ("주관", "주관 평가('예쁜')는 데이터로 확정할 수 없다. 객관 지표 기준을 확인해야 한다."),
        "N099": ("연도", "확인 필요. '오래된'의 경과년수 기준(예: 30년)이 없다."),
    }
    sqls: dict[str, tuple[str, str, str]] = {}
    # id -> (sql, kind, unit)

    def add(i, sql, kind="count", unit="채"):
        sqls[i] = (sql, kind, unit)

    add("N008", 'SELECT table_name, display_name, category FROM table_metadata ORDER BY table_name', "group", "개")
    add("N009", "SELECT table_name, display_name, LEFT(COALESCE(description,''), 400) AS description FROM table_metadata WHERE display_name ILIKE '%GIS건물통합%' OR table_name ILIKE 'AL_D010%' ORDER BY table_name", "group", "")
    add("N010", "SELECT DISTINCT table_name FROM information_schema.columns WHERE table_schema='public' AND table_name LIKE 'AL_D198%' ORDER BY 1", "group", "")
    add("N011", "SELECT column_name, display_name, unit, LEFT(COALESCE(description,''), 240) AS description FROM column_metadata WHERE table_name LIKE 'AL_D010%' AND column_name = 'A16'", "scalar", "")
    add("N012", "SELECT column_name, display_name, unit FROM column_metadata WHERE table_name LIKE 'AL_D010%' AND (display_name ILIKE '%연면적%' OR column_name = 'A14')", "scalar", "")
    add("N013", "SELECT column_name, display_name FROM column_metadata WHERE table_name LIKE 'AL_D010%' AND (display_name ILIKE '%지상%' OR column_name = 'A26')", "scalar", "")
    add("N014", f'SELECT column_name FROM information_schema.columns WHERE table_schema=\'public\' AND table_name = \'{BAS}\' ORDER BY ordinal_position', "group", "")
    add("N015", f'SELECT MIN("A3") AS min_base, MAX("A3") AS max_base, COUNT(*)::bigint AS n FROM "{D060}" WHERE "A4" LIKE \'26%\'', "scalar", "")
    add("N016", "SELECT '법정동명(A4)은 토지·건물 대장 주소, 행정동명(ADM_NM)은 센서스 행정구역 경계' AS diff", "scalar", "")

    add("N017", d010_cnt(a4("대연동")))
    add("N018", d010_cnt(a4("문현동")))
    add("N019", d010_cnt(a4("광안동")))
    add("N020", d010_cnt(a4("반송동")))
    add("N021", d010_cnt(a4("구포동")))
    add("N022", d010_cnt(a4("감천동")))
    add("N023", d010_cnt(a4("장림동")))
    add("N024", d010_cnt(a4("동삼동")))
    add("N025", d010_cnt(a4("반여동")))
    add("N028", d010_list(f"{a4('광안동')} AND {rc('A11','%철근콘크리트%')}", '"A24","A4","A5","A11","A16","A14"', '"A14"', 20), "list", "채")
    add("N029", d010_list("\"A24\" ILIKE '%엘시티%'", '"A24","A25","A4","A5","A16","A26","A14"', num("A16"), 20), "list", "")
    add("N031", d010_cnt(gu("남구")))
    add("N032", d010_cnt(gu("강서구")))
    add("N033", d010_cnt(gu("영도구")))
    add("N034", d010_cnt(gu("북구")))
    add("N035", d010_cnt(gu("부산진구")))
    add("N036", d010_cnt("TRUE"), "count", "채")
    add("N037", d010_cnt("\"A9\" = '공동주택'"))
    add("N038", d010_cnt("\"A9\" = '공장'"))
    add("N039", d010_cnt(f"{a4('대연동')} AND \"A9\" = '공동주택'"))
    add("N040", d010_cnt(f"{a4('광안동')} AND \"A9\" = '숙박시설'"))
    add("N041", d010_cnt(f"{a4('장림동')} AND \"A9\" = '공장'"))
    add("N042", d010_cnt(f"{gu('남구')} AND \"A9\" = '창고시설'"))
    add("N043", d010_cnt(f"{gu('영도구')} AND \"A9\" = '종교시설'"))
    add("N044", d010_cnt(f"{gu('북구')} AND \"A9\" = '교육연구시설'"))
    add("N045", d010_cnt(f"{gu('부산진구')} AND \"A9\" = '제2종근린생활시설'"))
    add("N046", d010_cnt(f"{gu('강서구')} AND \"A9\" = '자동차관련시설'"))
    add(
        "N047",
        f'SELECT COUNT(*)::bigint AS n FROM "{D010}" b JOIN "{BND}" d ON ST_Intersects(b.geometry, d.geometry) WHERE {admin_eq("대연3동")}',
    )
    add(
        "N048",
        f'SELECT COUNT(*)::bigint AS n FROM "{D010}" b JOIN "{BND}" d ON ST_Intersects(b.geometry, d.geometry) WHERE {admin_eq("광안2동")}',
    )
    add(
        "N049",
        f'SELECT COUNT(*)::bigint AS n FROM "{D010}" b JOIN "{BND}" d ON ST_Intersects(b.geometry, d.geometry) WHERE {admin_eq("우1동")}',
    )
    add(
        "N050",
        f'SELECT COUNT(*)::bigint AS n FROM "{D010}" b JOIN "{BND}" d ON ST_Intersects(b.geometry, d.geometry) WHERE {admin_eq("문현1동")}',
    )
    add(
        "N051",
        f'SELECT COUNT(*)::bigint AS n FROM "{D010}" b JOIN "{BND}" d ON ST_Intersects(b.geometry, d.geometry) WHERE {admin_eq("구포1동")}',
    )
    add(
        "N052",
        f'SELECT COUNT(*)::bigint AS n FROM "{D010}" b JOIN "{BND}" d ON ST_Intersects(b.geometry, d.geometry) WHERE {admin_eq("감천1동")}',
    )
    add(
        "N053",
        f'SELECT COUNT(*)::bigint AS n FROM "{D010}" b JOIN "{BND}" d ON ST_Intersects(b.geometry, d.geometry) WHERE {admin_eq("반여1동")} AND b."A9" = \'공동주택\'',
    )
    add(
        "N054",
        f'SELECT COUNT(*)::bigint AS n FROM "{D010}" b JOIN "{BND}" d ON ST_Intersects(b.geometry, d.geometry) WHERE {admin_eq("대연1동")} AND b."A9" = \'공동주택\'',
    )
    add("N055", d010_cnt(f"{gu('남구')} AND {num('A16')} >= 30"))
    add("N056", d010_list(f"{a4('광안동')} AND {num('A16')} > 20", '"A24","A4","A5","A16","A9"', num("A16"), 30), "list", "채")
    add("N057", d010_cnt(f"{gu('북구')} AND {num('A26')} >= 12"))
    add("N058", d010_cnt(f"{a4('우동')} AND {num('A26')} > 20"))
    add("N059", d010_cnt(f"{a4('대연동')} AND {num('A14')} >= 500"))
    add("N060", d010_cnt(f"{a4('문현동')} AND {num('A14')} >= {p80}"))
    add("N061", d010_cnt(f"{gu('강서구')} AND \"A9\" = '공장' AND {num('A12')} >= 200"))
    add("N062", d010_cnt(f"{gu('영도구')} AND {num('A16')} < 15 AND {num('A16')} IS NOT NULL"))
    add("N063", d010_list(f"{a4('광안동')} AND \"A9\" = '숙박시설'", '"A24","A4","A5","A14","A16"', num("A14"), 1), "scalar", "")
    add("N064", d010_agg(f'{num("A16")} AS height_m, "A24","A5"', f"{a4('광안동')} AND \"A9\" = '숙박시설' ORDER BY {num('A14')} DESC NULLS LAST LIMIT 1"), "scalar", "m")
    add("N065", d010_list(f"{gu('남구')} AND \"A9\" = '공동주택'", '"A24","A4","A5","A12","A14"', num("A12"), 1), "scalar", "")
    add("N066", d010_agg('"A5" AS lot, "A24","A4"', f"{gu('남구')} AND \"A9\" = '공동주택' ORDER BY {num('A12')} DESC NULLS LAST LIMIT 1"), "scalar", "")
    add("N067", d010_list(f"{a4('장림동')} AND \"A9\" = '공장'", '"A24","A4","A5","A16","A14"', num("A16"), 1), "scalar", "")
    add("N068", d010_list(f"{a4('우동')}", '"A24","A4","A5","A26","A16"', num("A26"), 1), "scalar", "")
    add(
        "N069",
        f"""
        SELECT "A24" AS name, MAX({num("A16")}) AS height_m
        FROM "{D010}"
        WHERE "A24" ILIKE '%엘시티%' OR "A24" ILIKE '%엘크루%블루오션%'
        GROUP BY 1
        ORDER BY height_m DESC NULLS LAST
        """,
        "compare",
        "m",
    )
    add(
        "N070",
        f"""
        SELECT
          COUNT(*) FILTER (WHERE "A24" ILIKE '%부산대학교%') AS pusan_n,
          COUNT(*) FILTER (WHERE "A24" ILIKE '%부경대학교%') AS pukyong_n
        FROM "{D010}"
        """,
        "compare",
        "채",
    )
    add("N071", d010_agg(f"COUNT(*)::bigint AS n, AVG({num('A16')}) AS avg_h, AVG({num('A14')}) AS avg_gfa, AVG({num('A26')}) AS avg_fl", f"{a4('광안동')} AND \"A9\" = '숙박시설'"), "scalar", "")
    add("N072", d010_agg(f"COUNT(*)::bigint AS n, AVG({num('A16')}) AS avg_h, AVG({num('A14')}) AS avg_gfa", f"{a4('장림동')} AND \"A9\" = '공장'"), "scalar", "")
    add("N073", d010_agg(f"COUNT(*)::bigint AS n, AVG({num('A16')}) AS avg_h, AVG({num('A14')}) AS avg_gfa, AVG({num('A26')}) AS avg_fl", f"{a4('대연동')} AND \"A9\" = '공동주택'"), "scalar", "")
    add(
        "N074",
        f"""
        SELECT
          COUNT(*) FILTER (WHERE {a4('대연동')}) AS daeyeon_n,
          AVG({num('A14')}) FILTER (WHERE {a4('대연동')}) AS daeyeon_avg_gfa,
          COUNT(*) FILTER (WHERE {a4('문현동')}) AS munhyeon_n,
          AVG({num('A14')}) FILTER (WHERE {a4('문현동')}) AS munhyeon_avg_gfa
        FROM "{D010}"
        WHERE {a4('대연동')} OR {a4('문현동')}
        """,
        "compare",
        "",
    )
    add(
        "N075",
        f"""
        SELECT
          COUNT(*) FILTER (WHERE {gu('남구')}) AS nam_n,
          AVG({num('A16')}) FILTER (WHERE {gu('남구')}) AS nam_avg_h,
          AVG({num('A14')}) FILTER (WHERE {gu('남구')}) AS nam_avg_gfa,
          COUNT(*) FILTER (WHERE {gu('영도구')}) AS yeongdo_n,
          AVG({num('A16')}) FILTER (WHERE {gu('영도구')}) AS yeongdo_avg_h,
          AVG({num('A14')}) FILTER (WHERE {gu('영도구')}) AS yeongdo_avg_gfa
        FROM "{D010}"
        WHERE ("A9" = '공동주택') AND ({gu('남구')} OR {gu('영도구')})
        """,
        "compare",
        "",
    )
    add(
        "N079",
        f'SELECT COUNT(DISTINCT t."BAS_ID")::bigint AS n FROM "{BAS}" t JOIN "{BND}" d ON t.geometry && d.geometry AND ST_Intersects(t.geometry, d.geometry) WHERE {admin_eq("대연3동")}',
        "count",
        "개",
    )
    add("N080", f'SELECT COUNT(*)::bigint AS n FROM "{BAS}" WHERE "SIG_KOR_NM" = \'남구\'', "count", "개")
    add(
        "N081",
        f"""
        SELECT COUNT(*)::bigint AS n
        FROM "{D010}" b
        CROSS JOIN (
          SELECT ST_Union(d.geometry) AS geom FROM "{BND}" d WHERE {admin_eq("광안2동")}
        ) z
        WHERE z.geom IS NOT NULL
          AND b.geometry && ST_Expand(z.geom, 0.002)
          AND ST_DWithin(b.geometry::geography, z.geom::geography, 100)
        """,
    )
    add(
        "N082",
        f"""
        SELECT COUNT(*)::bigint AS n
        FROM "{D010}" b
        WHERE ST_DWithin(
          b.geometry::geography,
          ST_SetSRID(ST_MakePoint(129.12, 35.15), 4326)::geography,
          200
        )
        """,
    )
    add(
        "N083",
        f"""
        WITH legal AS (
          SELECT geometry FROM "{D010}" WHERE {a4('반여동')}
        ),
        admin AS (
          SELECT d."ADM_NM", COUNT(*)::bigint AS n
          FROM legal b
          JOIN "{BND}" d ON ST_Intersects(b.geometry, d.geometry)
          WHERE {admin_eq("반여동")}
          GROUP BY 1
        ),
        tot AS (SELECT SUM(n)::float8 AS t FROM admin)
        SELECT a."ADM_NM", a.n, ROUND((a.n / NULLIF(t.t,0) * 100)::numeric, 2) AS pct
        FROM admin a, tot t
        ORDER BY a.n DESC
        """,
        "group",
        "%",
    )
    add(
        "N084",
        f"""
        SELECT DISTINCT t."BAS_ID", t."SIG_KOR_NM", t."BAS_AR"
        FROM "{BAS}" t
        JOIN "{BND}" d ON t.geometry && d.geometry AND ST_Intersects(t.geometry, d.geometry)
        WHERE {admin_eq("우동")}
        ORDER BY t."BAS_AR" DESC NULLS LAST
        LIMIT 30
        """,
        "list",
        "개",
    )
    add(
        "N085",
        f'SELECT "BAS_ID","SIG_KOR_NM","BAS_AR" FROM "{BAS}" WHERE "SIG_KOR_NM" = \'북구\' ORDER BY "BAS_AR" DESC NULLS LAST LIMIT 1',
        "scalar",
        "㎡",
    )
    add(
        "N086",
        f"""
        SELECT COUNT(*)::bigint AS n FROM (
          SELECT DISTINCT COALESCE(NULLIF(TRIM("A8"),''), NULLIF(TRIM("A9"),'')) AS name
          FROM "{D060}"
          WHERE "A4" = '26380'
        ) t WHERE name IS NOT NULL
        """,
        "count",
        "개",
    )
    add(
        "N087",
        f"""
        SELECT DISTINCT name FROM (
          SELECT TRIM("A8") AS name FROM "{D060}" WHERE "A4" = '26440' AND "A8" ILIKE '%산업단지%'
          UNION
          SELECT TRIM("A9") AS name FROM "{D060}" WHERE "A4" = '26440' AND "A9" ILIKE '%산업단지%'
        ) t WHERE name IS NOT NULL AND BTRIM(name) <> '' AND name <> '일반산업단지'
        ORDER BY name
        """,
        "list",
        "개",
    )
    add(
        "N088",
        f"""
        SELECT COUNT(*)::bigint AS n FROM "{D010}" b
        WHERE {a4('장림동')}
          AND EXISTS (SELECT 1 FROM "{D060}" i WHERE ST_Intersects(b.geometry, i.geometry))
        """,
    )
    add(
        "N089",
        f'SELECT COUNT(*)::bigint AS n FROM "{D060}" WHERE "A4" LIKE \'26%\' AND "A6" = \'일반산업단지\'',
        "count",
        "개",
    )
    add(
        "N090",
        f"""
        SELECT COUNT(DISTINCT t."BAS_ID")::bigint AS n
        FROM "{BAS}" t
        JOIN "{D060}" i ON ST_Intersects(t.geometry, i.geometry)
        WHERE i."A4" = '26380'
        """,
        "count",
        "개",
    )
    add(
        "N091",
        f"""
        SELECT b."A24", b."A4", b."A5", b."A9", b."A14"
        FROM "{D010}" b
        WHERE {a4('감천동').replace('"A4"', 'b."A4"')}
          AND b."A9" = '공장'
          AND EXISTS (SELECT 1 FROM "{D060}" i WHERE ST_Intersects(b.geometry, i.geometry))
        ORDER BY {num('A14').replace('"A14"', 'b."A14"')} DESC NULLS LAST
        LIMIT 30
        """,
        "list",
        "채",
    )
    add(
        "N092",
        f"""
        SELECT COUNT(*)::bigint AS n FROM "{D010}" b
        WHERE EXISTS (
          SELECT 1 FROM "{D060}" i
          WHERE (i."A8" ILIKE '%명지국가산업단지%' OR i."A9" ILIKE '%명지국가산업단지%')
            AND ST_Intersects(b.geometry, i.geometry)
        )
        """,
    )
    add(
        "N093",
        f"""
        SELECT LEFT(regexp_replace("A13"::text, '[^0-9]', '', 'g'), 4) AS yyyy, COUNT(*)::bigint AS n
        FROM "{D010}"
        WHERE {gu('금정구')} AND "A9" = '단독주택' AND "A13"::text ~ '^[0-9]{{4}}'
        GROUP BY 1
        ORDER BY 1
        """,
        "group",
        "채",
    )
    add(
        "N094",
        f"""
        SELECT (LEFT(regexp_replace("A13"::text, '[^0-9]', '', 'g'), 4)::int / 3) * 3 AS y0,
               COUNT(*)::bigint AS n
        FROM "{D010}"
        WHERE {gu('금정구')} AND "A9" = '단독주택' AND "A13"::text ~ '^[0-9]{{4}}'
        GROUP BY 1
        ORDER BY 1
        """,
        "group",
        "채",
    )
    add(
        "N095",
        f"""
        SELECT LEFT(regexp_replace("A34"::text, '[^0-9]', '', 'g'), 4) AS yyyy, COUNT(*)::bigint AS n
        FROM "{D198_DR}"
        WHERE "A29" = '상업용' AND "A34"::text ~ '^[0-9]{{4}}'
        GROUP BY 1
        ORDER BY 1
        """,
        "group",
        "채",
    )
    add(
        "N096",
        f"""
        SELECT
          CASE
            WHEN {num('A14')} < 60 THEN '60㎡미만'
            WHEN {num('A14')} < 85 THEN '60-85㎡'
            WHEN {num('A14')} < 130 THEN '85-130㎡'
            ELSE '130㎡이상'
          END AS bin,
          COUNT(*)::bigint AS n
        FROM "{D010}"
        WHERE {gu('금정구')} AND "A9" IN ('단독주택','공동주택') AND {num('A14')} IS NOT NULL
        GROUP BY 1
        ORDER BY 1
        """,
        "group",
        "채",
    )
    add("N097", d010_cnt(f"{a4('안락동')} AND {age_gte('A13', 30)}"))
    add("N098", d010_list(f"{a4('사직동')} AND \"A9\" = '공동주택' AND {year_ge('A13', 2000)}", '"A24","A4","A5","A13","A14"', num("A14"), 30), "list", "채")
    add(
        "N100",
        f"""
        SELECT COUNT(*)::bigint AS n
        FROM "{D198_DR}"
        WHERE "A10" = '집합건축물'
          AND {year_between('A33', 1990, 1999)}
        """,
    )

    fixture = json.loads(NL100.read_text(encoding="utf-8"))
    out: list[Case] = []
    for item in fixture["questions"]:
        qid = item["id"]
        q = item["q"]
        cat = item["category"]
        session = item.get("session")
        if qid in meta:
            kind_name, text = meta[qid]
            out.append(C(qid, kind_name, q, None, "meta", gold_text=text, session=session, source="nl100"))
            continue
        if qid in sqls:
            sql, kind, unit = sqls[qid]
            parent = None
            if qid == "N064":
                parent = "N063"
            if qid == "N066":
                parent = "N065"
            if qid == "N094":
                parent = "N093"
            out.append(C(qid, cat, q, sql, kind, unit=unit, session=session, parent=parent, source="nl100"))
            continue
        out.append(C(qid, cat, q, None, "meta", gold_text="(정답 SQL 미지정)", session=session, source="nl100"))
    return out


def new_cases() -> list[Case]:
    """기존 NL100 단순 건수·단일임계 패턴이 아닌 복합·후속 400문항."""
    from eval_q500_new_cases import build_new_cases

    return build_new_cases()


def format_gold(case: Case, rows: list[dict] | None, error: str | None) -> str:
    if case.gold_text and case.sql is None:
        return case.gold_text
    if error:
        return f"쿼리 실패: {error}"
    if rows is None:
        return "실행 안 함"
    if case.kind == "count":
        if not rows:
            return f"0{case.unit}"
        key = next(iter(rows[0].keys()))
        return f"{fmt_num(rows[0][key])}{case.unit}"
    if case.kind in {"scalar", "compare"}:
        if not rows:
            return "해당 조건에 맞는 결과가 없습니다."
        row = rows[0]
        bits = [f"{k}={fmt_num(v)}" for k, v in row.items()]
        extra = ""
        if len(rows) > 1:
            extra = " | " + " / ".join(
                ", ".join(f"{k}={fmt_num(v)}" for k, v in r.items()) for r in rows[1:8]
            )
            if len(rows) > 8:
                extra += f" 외 {len(rows) - 8}행"
        return "; ".join(bits) + extra
    if case.kind in {"list", "group"}:
        return fmt_rows_inline(rows, 15)
    return fmt_rows_inline(rows, 10)


def run_sql(cur, sql: str) -> list[dict]:
    cur.execute(sql)
    rows = cur.fetchall()
    out = []
    for row in rows:
        clean = {}
        for k, v in dict(row).items():
            name = type(v).__name__.lower()
            if v is None:
                clean[k] = None
            elif "geometry" in name or isinstance(v, (memoryview, bytes, bytearray)):
                continue
            else:
                clean[k] = v
        out.append(clean)
    return out


def to_md(cases: list[Case], meta: dict) -> str:
    lines = [
        "# 평가 문항 500 (쿼리 정답 포함)",
        "",
        f"- 생성 시각: {meta['when']}",
        f"- 데이터베이스: gisdb (KorDB)",
        f"- 기존 100: `scripts/smoke_nl100.json` (N001–N100)",
        f"- 신규 400: DB·속성 기반 복합 질의 및 후속 질의 (Q101–Q500)",
        f"- 실행 성공: {meta['ok']} / {meta['total']}",
        f"- 쿼리 실패: {meta['fail']}",
        "",
        "## 평가 원칙",
        "",
        "1. **답까지 같아야 정답이다.** SQL에 COUNT/JOIN 토큰이 있어도 수치가 다르면 오답이다.",
        "2. 건수·합계·평균·비율은 아래 정답의 숫자와 일치해야 한다 (천 단위 콤마·단위 표기 차이는 허용).",
        "3. 목록·순위는 1위(또는 요청한 Top-N의 구성원)가 같아야 한다. 정렬 키가 다르면 오답이다.",
        "4. 후속 질문은 선행 질문의 결과 집합을 유지한 채 추가 조건만 적용한 정답과 비교한다.",
        "5. 안내·범위외·모호·주관 문항은 아래 정답 요지(거절/확인/도움말)와 같아야 한다.",
        "",
        "## 신규 400의 설계",
        "",
        "기존 100의 단순 패턴(한 장소 건수, 한 용도 건수, 단일 임계, 단순 최고값)을 반복하지 않는다.",
        "건폐율·용적율·위반건축물·지하층·특수지·집합건물·세부용도·허가일자 등 속성을 결합하고,",
        "AND/OR/NOT/구간, 공간 교차, 비율·그룹 집계, 두 지역 비교, 다턴 후속을 쓴다.",
        "",
    ]

    current_src = None
    current_cat = None
    for case in cases:
        src = "기존 100문항 (N001–N100)" if case.source == "nl100" else "신규 400문항 (Q101–Q500)"
        if src != current_src:
            lines.append(f"## {src}")
            lines.append("")
            current_src = src
            current_cat = None
        if case.cat != current_cat:
            lines.append(f"### {case.cat}")
            lines.append("")
            current_cat = case.cat
        lines.append(f"#### {case.id}")
        lines.append("")
        lines.append(f"- **질문:** {case.q}")
        if case.session:
            lines.append(f"- **세션:** `{case.session}`")
        if case.parent:
            lines.append(f"- **선행:** {case.parent}")
        if case.note:
            lines.append(f"- **비고:** {case.note}")
        lines.append(f"- **유형:** {case.kind}")
        gold = case.result.get("gold") or case.gold_text or ""
        lines.append(f"- **정답:** {gold}")
        if case.sql:
            lines.append("- **정답 SQL:**")
            lines.append("")
            lines.append("```sql")
            lines.append(case.sql.strip())
            lines.append("```")
            rc = case.result.get("row_count")
            ms = case.result.get("ms")
            err = case.result.get("error")
            extra = []
            if rc is not None:
                extra.append(f"행 {rc}")
            if ms is not None:
                extra.append(f"{ms}ms")
            if err:
                extra.append(f"오류: {err}")
            if extra:
                lines.append("")
                lines.append(f"- **실행:** {', '.join(extra)}")
        lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if not URL:
        print("DATABASE_URL missing")
        return 1

    from eval_q500_new_cases import build_new_cases

    cases = n100_cases() + build_new_cases()
    if len(cases) != 500:
        print(f"WARNING: case count={len(cases)} (expected 500)")

    ok = fail = 0
    t0 = time.perf_counter()
    with psycopg.connect(URL, row_factory=dict_row, connect_timeout=20) as conn:
        conn.execute("SET statement_timeout = '120s'")
        conn.execute("SET work_mem = '256MB'")
        cur = conn.cursor()
        for i, case in enumerate(cases, 1):
            t1 = time.perf_counter()
            error = None
            rows = None
            if case.sql:
                try:
                    rows = run_sql(cur, case.sql)
                except Exception as exc:
                    conn.rollback()
                    error = f"{type(exc).__name__}: {exc}"[:400]
                    fail += 1
                else:
                    ok += 1
            else:
                ok += 1
            ms = int((time.perf_counter() - t1) * 1000)
            gold = format_gold(case, rows, error)
            case.result = {
                "gold": gold,
                "row_count": 0 if rows is None else len(rows),
                "ms": ms,
                "error": error,
            }
            status = "ERR" if error else "OK"
            print(f"[{i:03}/{len(cases)}] {status} {case.id} {ms}ms {case.q[:48]}")
            if error:
                print(f"    {error}")
            if i % 25 == 0:
                payload = _payload(cases, ok, fail, t0)
                OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    payload = _payload(cases, ok, fail, t0)
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    OUT_MD.write_text(to_md(cases, payload), encoding="utf-8")
    print(f"wrote {OUT_MD}")
    print(f"wrote {OUT_JSON}")
    print(f"ok={ok} fail={fail} n={len(cases)} elapsed={payload['elapsed_s']}s")
    return 0 if fail == 0 and len(cases) == 500 else 1


def _payload(cases: list[Case], ok: int, fail: int, t0: float) -> dict:
    return {
        "when": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total": len(cases),
        "ok": ok,
        "fail": fail,
        "elapsed_s": round(time.perf_counter() - t0, 1),
        "evaluation": "answer_must_match_gold_not_sql_tokens_only",
        "questions": [
            {
                "id": c.id,
                "cat": c.cat,
                "q": c.q,
                "kind": c.kind,
                "source": c.source,
                "session": c.session,
                "parent": c.parent,
                "sql": c.sql,
                "gold": c.result.get("gold") or c.gold_text,
                "row_count": c.result.get("row_count"),
                "error": c.result.get("error"),
                "ms": c.result.get("ms"),
                "note": c.note,
            }
            for c in cases
        ],
    }


if __name__ == "__main__":
    # allow `uv run python scripts/gen_eval_q500.py`
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    sys.path.insert(0, str(ROOT))
    raise SystemExit(main())
