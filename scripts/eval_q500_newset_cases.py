"""신규 자연어 질의 테스트셋 500건의 채점용 정답 SQL.

정답은 KorDB 실쿼리 결과이다. SQL 토큰만 같고 수치가 다르면 오답으로 본다.
"""
from __future__ import annotations

from gen_eval_q500 import (
    BAS,
    BND,
    C,
    D010,
    D060,
    D198_DR,
    D198_GJ,
    GU_CODES,
    PYEONG_M2,
    a4,
    admin_eq,
    age_gte,
    d010_agg,
    d010_cnt,
    d010_list,
    gu,
    num,
    rc,
    year_between,
    year_ge,
)

GUS = [
    "중구", "서구", "동구", "영도구", "부산진구", "동래구", "남구", "북구",
    "해운대구", "사하구", "금정구", "강서구", "연제구", "수영구", "사상구", "기장군",
]
DONGS_S1 = [
    "연산동", "대연동", "문현동", "대저1동", "대저2동", "괴정동", "청학동",
    "반송동", "구포동", "감천동", "광안동", "장림동", "동삼동", "강동동",
]
DETAIL_USAGE = {"아파트", "다세대주택", "다가구주택", "오피스텔", "일반음식점"}
GJ_PLACES = {"금정구", "구서동", "서동", "부곡동", "장전동", "남산동", "금사동", "회동동", "두구동"}
DR_PLACES = {"동래구", "온천동", "안락동", "사직동", "명장동", "명륜동", "수안동", "복천동", "낙민동"}

LIST_N = 20
SANE_H = f"{num('A16')} > 0 AND {num('A16')} <= 500"
SANE_H30 = f"{num('A30')} > 0 AND {num('A30')} <= 500"


def year_lt(col: str, year: int) -> str:
    return (
        f"\"{col}\"::text ~ '^[0-9]{{4}}' "
        f"AND LEFT(regexp_replace(\"{col}\"::text, '[^0-9]', '', 'g'), 4) < '{year}'"
    )


def age_lt(col: str, years: int) -> str:
    from txt2sql.query_understanding.temporal import reference_date_sql

    ref = reference_date_sql()
    return (
        f"\"{col}\" ~ '^[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}$' "
        f"AND \"{col}\"::date > ({ref} - INTERVAL '{years} years')"
    )


def valid_date(col: str) -> str:
    return f"\"{col}\" ~ '^[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}$'"


def year_expr(col: str) -> str:
    return f"LEFT(regexp_replace(\"{col}\"::text, '[^0-9]', '', 'g'), 4)::int"


def empty_name(col: str = "A24") -> str:
    return f"(TRIM(COALESCE(\"{col}\"::text, '')) = '')"


def nonempty(col: str) -> str:
    return f"TRIM(COALESCE(\"{col}\"::text, '')) <> ''"


def viol(yes: bool = True) -> str:
    return '"A20" = \'Y\'' if yes else '"A20" IS DISTINCT FROM \'Y\''


def sanji() -> str:
    return "(\"A6\" = '2' OR \"A7\" = '산')"


def ilban() -> str:
    return "(\"A6\" = '1' OR \"A7\" IN ('일반', '일반지번'))"


def gaji() -> str:
    return "(\"A6\" IN ('3', '4') OR \"A7\" ILIKE '%가지%')"


def beulleok() -> str:
    return "(\"A6\" IN ('5', '6', '7', '8') OR \"A7\" ILIKE '%블럭%' OR \"A7\" ILIKE '%블록%')"


def struct_eq(name: str) -> str:
    return f"\"A11\" = '{name}'"


def gu_label(alias: str = "") -> str:
    col = f'{alias}."A3"' if alias else '"A3"'
    whens = " ".join(f"WHEN '{code}' THEN '{name}'" for name, code in GU_CODES.items())
    return f"CASE LEFT({col}, 5) {whens} ELSE LEFT({col}, 5) END"


def d198_of(place: str) -> tuple[str, str]:
    if place in GJ_PLACES or place == "금정구":
        tbl = D198_GJ
    elif place in DR_PLACES or place == "동래구":
        tbl = D198_DR
    else:
        raise KeyError(place)
    where = "TRUE" if place.endswith("구") else a4(place)
    return tbl, where


def usage_pred(usage: str, alias: str = "") -> str:
    p = f'{alias}.' if alias else ""
    col = "A27" if usage in DETAIL_USAGE else "A25"
    return f"{p}\"{col}\" = '{usage}'"


def d198_cnt(tbl: str, where: str) -> str:
    return f'SELECT COUNT(*)::bigint AS n FROM "{tbl}" WHERE {where}'


def d198_list(tbl: str, where: str, cols: str, order: str, limit: int = LIST_N) -> str:
    return (
        f"SELECT {cols}\nFROM \"{tbl}\"\nWHERE {where}\n"
        f"ORDER BY {order} DESC NULLS LAST\nLIMIT {limit}"
    )


def d198_agg(tbl: str, select: str, where: str) -> str:
    return f'SELECT {select} FROM "{tbl}" WHERE {where}'


def d010_list_asc(where: str, cols: str, order: str, limit: int = 10) -> str:
    return (
        f"SELECT {cols}\nFROM \"{D010}\"\nWHERE {where}\n"
        f"ORDER BY {order} ASC NULLS LAST\nLIMIT {limit}"
    )


def bnd_join(adm: str, extra: str = "TRUE", distinct: bool = True) -> str:
    nexpr = 'COUNT(DISTINCT b."A1")::bigint AS n' if distinct else "COUNT(*)::bigint AS n"
    return (
        f'SELECT {nexpr}\nFROM "{D010}" b\n'
        f'JOIN "{BND}" d ON ST_Intersects(b.geometry, d.geometry)\n'
        f"WHERE {admin_eq(adm)} AND ({extra})"
    )


def bnd_agg(adm: str, select: str, extra: str = "TRUE") -> str:
    return (
        f"SELECT {select}\nFROM \"{D010}\" b\n"
        f'JOIN "{BND}" d ON ST_Intersects(b.geometry, d.geometry)\n'
        f"WHERE {admin_eq(adm)} AND ({extra})"
    )


def dwithin_cnt(adm: str, meters: int, extra: str = "TRUE") -> str:
    return (
        f'SELECT COUNT(DISTINCT b."A1")::bigint AS n\n'
        f'FROM "{D010}" b\n'
        f'JOIN "{BND}" d ON ST_DWithin(b.geometry::geography, d.geometry::geography, {meters})\n'
        f"WHERE {admin_eq(adm)} AND ({extra})"
    )


def busan_ind() -> str:
    return "i.\"A4\" LIKE '26%'"


def Q(qid: str, qmap: dict, sql: str | None, kind: str = "count", unit: str = "채", **kw):
    m = qmap[qid]
    return C(
        qid,
        m["section"],
        m["q"],
        sql,
        kind,
        unit=unit,
        note=kw.pop("note", m["point"]),
        **kw,
    )


def section1(qmap: dict) -> list:
    out = []
    for i, g in enumerate(GUS, 1):
        out.append(Q(f"Q{i:03d}", qmap, d010_cnt(gu(g))))
    for i, dong in enumerate(DONGS_S1, 17):
        out.append(Q(f"Q{i:03d}", qmap, d010_cnt(a4(dong))))
    out += [
        Q("Q031", qmap, d010_cnt("TRUE")),
        Q("Q032", qmap, d010_cnt(viol(True))),
        Q("Q033", qmap, d010_cnt(viol(False))),
        Q("Q034", qmap, d010_list(gu("해운대구"), '"A24","A4","A5"', '"A0"', 20), "list"),
        Q("Q035", qmap, d010_list(gu("강서구"), '"A4","A16"', num("A16"), LIST_N), "list"),
        Q("Q036", qmap, d010_list(f"{gu('사하구')} AND {nonempty('A24')}", '"A24","A4","A5"', '"A0"', LIST_N), "list"),
        Q("Q037", qmap, d010_cnt(f"{gu('연제구')} AND {empty_name('A24')}")),
        Q("Q038", qmap, d010_cnt(f"{gu('부산진구')} AND \"A16\" IS NULL")),
        Q("Q039", qmap, d010_cnt(f"{gu('기장군')} AND \"A27\" IS NULL")),
        Q("Q040", qmap, d010_cnt(f"{gu('영도구')} AND {sanji()}")),
        Q("Q041", qmap, d010_cnt(f"{gu('북구')} AND {ilban()}")),
        Q("Q042", qmap, d010_cnt(f"{gu('중구')} AND {gaji()}")),
        Q("Q043", qmap, d010_cnt(f"{gu('서구')} AND {beulleok()}")),
        Q("Q044", qmap, d010_cnt(struct_eq("철근콘크리트구조"))),
        Q("Q045", qmap, d010_cnt(f"{gu('사상구')} AND {struct_eq('벽돌구조')}")),
        Q("Q046", qmap, d010_cnt(f"{gu('수영구')} AND {struct_eq('일반철골구조')}")),
        Q("Q047", qmap, d010_cnt(f"{gu('남구')} AND {struct_eq('일반목구조')}")),
        Q("Q048", qmap, d010_cnt(f"{gu('동구')} AND {struct_eq('경량철골구조')}")),
        Q("Q049", qmap, d010_cnt(f"{a4('대연동')} AND {struct_eq('철근콘크리트구조')}")),
        Q("Q050", qmap, d010_cnt(f"{a4('문현동')} AND {struct_eq('벽돌구조')}")),
        Q("Q051", qmap, d010_cnt(f"{a4('광안동')} AND {struct_eq('일반목구조')}")),
        Q("Q052", qmap, d010_cnt(f"{a4('장림동')} AND {struct_eq('일반철골구조')}")),
        Q("Q053", qmap, d010_cnt(f"{a4('연산동')} AND {struct_eq('블록구조')}")),
        Q("Q054", qmap, d010_cnt(f"{num('A26')} = 0")),
        Q("Q055", qmap, d010_cnt(f"{num('A16')} = 0")),
        Q("Q056", qmap, d010_cnt(f"{num('A12')} < 0")),
        Q("Q057", qmap, d010_list(f"{num('A17')} < 0", '"A24","A4","A5","A17"', num("A17"), 50), "list"),
        Q("Q058", qmap, d010_cnt(empty_name("A23") + ' OR "A23" IS NULL')),
        Q("Q059", qmap, d010_list(f"{viol(True)} AND {nonempty('A24')}", '"A24","A4","A5","A20"', '"A0"', 30), "list"),
        Q("Q060", qmap, d010_list(f"{sanji()} AND \"A26\" IS NOT NULL", '"A24","A4","A5","A26"', num("A26"), LIST_N), "list"),
        Q("Q061", qmap, d010_list(f"{ilban()} AND {num('A27')} >= 1", '"A24","A4","A5","A27"', num("A27"), LIST_N), "list"),
        Q("Q062", qmap, d010_cnt(f"{struct_eq('철근콘크리트구조')} AND {viol(True)}")),
        Q("Q063", qmap, d010_cnt(f"{struct_eq('벽돌구조')} AND {viol(False)}")),
        Q("Q064", qmap, f'''SELECT "A24" AS name, COUNT(*)::bigint AS n
FROM "{D010}"
WHERE {nonempty("A24")}
GROUP BY 1 HAVING COUNT(*) > 1
ORDER BY n DESC, "A24"
LIMIT 20''', "group"),
        Q("Q065", qmap, f'''SELECT "A2" AS pnu, COUNT(*)::bigint AS n
FROM "{D010}"
WHERE {nonempty("A2")}
GROUP BY 1 HAVING COUNT(*) > 1
ORDER BY n DESC, "A2"
LIMIT 20''', "group"),
        Q("Q066", qmap, f'''SELECT "A1" AS gis_id, COUNT(*)::bigint AS n
FROM "{D010}"
WHERE {nonempty("A1")}
GROUP BY 1 HAVING COUNT(*) > 1
ORDER BY n DESC
LIMIT 20''', "group"),
        Q("Q067", qmap, f'''SELECT "A3" AS bjd_cd, COUNT(*)::bigint AS n
FROM "{D010}" GROUP BY 1 ORDER BY n DESC''', "group"),
        Q("Q068", qmap, f'''SELECT "A23" AS src_sig, COUNT(*)::bigint AS n
FROM "{D010}" GROUP BY 1 ORDER BY n DESC''', "group"),
        Q("Q069", qmap, d010_cnt('"A15" IS NOT NULL')),
        Q("Q070", qmap, d010_cnt(f"{num('A14')} = 0")),
    ]
    return out


def section2(qmap: dict) -> list:
    n = num
    out = []
    for i, (g, h) in enumerate(zip(GUS, range(15, 91, 5)), 71):
        out.append(Q(f"Q{i:03d}", qmap, d010_cnt(f"{gu(g)} AND {n('A16')} >= {h}")))
    for i, (g, fl) in enumerate(zip(GUS, range(3, 19)), 87):
        out.append(Q(f"Q{i:03d}", qmap, d010_list(f"{gu(g)} AND {n('A26')} >= {fl}", '"A24","A4","A5","A26","A16"', n("A26"), LIST_N), "list"))
    for i, (dong, gfa) in enumerate(zip(DONGS_S1, range(100, 2051, 150)), 103):
        out.append(Q(f"Q{i:03d}", qmap, d010_cnt(f"{a4(dong)} AND {n('A14')} >= {gfa}")))
    out += [
        Q("Q117", qmap, d010_list(f"{gu('해운대구')} AND {n('A16')} BETWEEN 30 AND 80", '"A24","A4","A16"', n("A16"), LIST_N), "list"),
        Q("Q118", qmap, d010_cnt(f"{gu('금정구')} AND {n('A26')} BETWEEN 5 AND 15")),
        Q("Q119", qmap, d010_list(f"{gu('동래구')} AND {n('A14')} BETWEEN 500 AND 3000", '"A24","A4","A14"', n("A14"), LIST_N), "list"),
        Q("Q120", qmap, d010_cnt(f"{gu('강서구')} AND {n('A15')} BETWEEN 1000 AND 5000")),
        Q("Q121", qmap, d010_list(f"{gu('사하구')} AND {n('A12')} BETWEEN 200 AND 1000", '"A24","A4","A12"', n("A12"), LIST_N), "list"),
        Q("Q122", qmap, d010_cnt(f"{gu('수영구')} AND {n('A17')} BETWEEN 40 AND 70")),
        Q("Q123", qmap, d010_list(f"{gu('연제구')} AND {n('A18')} BETWEEN 150 AND 400", '"A24","A4","A18"', n("A18"), LIST_N), "list"),
        Q("Q124", qmap, d010_list(f"{gu('부산진구')} AND {n('A16')} >= 30 AND {n('A26')} >= 10", '"A24","A4","A16","A26"', n("A16"), LIST_N), "list"),
        Q("Q125", qmap, d010_cnt(f"{gu('기장군')} AND {n('A14')} >= 2000 AND {n('A15')} >= 1000")),
        Q("Q126", qmap, d010_list(f"{gu('영도구')} AND {n('A26')} >= 5 AND {n('A27')} >= 1", '"A24","A4","A26","A27"', n("A26"), LIST_N), "list"),
        Q("Q127", qmap, d010_cnt(f"{gu('남구')} AND {n('A17')} >= 60 AND {n('A18')} >= 250")),
        Q("Q128", qmap, d010_list(f"{gu('북구')} AND {n('A16')} >= 20 AND {n('A26')} <= 5", '"A24","A4","A16","A26"', n("A16"), LIST_N), "list"),
        Q("Q129", qmap, d010_list(f"{n('A12')} > {n('A14')}", '"A24","A4","A12","A14"', n("A12"), LIST_N), "list"),
        Q("Q130", qmap, d010_cnt(f"{n('A14')} < {n('A15')}")),
        Q("Q131", qmap, d010_list(f"{n('A16')} > {n('A26')} * 10", '"A24","A4","A16","A26"', n("A16"), LIST_N), "list"),
        Q("Q132", qmap, d010_cnt(f"{n('A26')} >= 1 AND {n('A16')} = 0")),
        Q("Q133", qmap, d010_list(f"{n('A26')} >= 50 AND {n('A16')} < 100", '"A24","A4","A26","A16"', n("A26"), LIST_N), "list"),
        Q("Q134", qmap, d010_list(f"{n('A16')} > 500", '"A24","A16"', n("A16"), LIST_N), "list"),
        Q("Q135", qmap, d010_cnt(f"{n('A17')} > 1000")),
        Q("Q136", qmap, d010_list(f"{n('A18')} > 5000", '"A24","A4","A18"', n("A18"), LIST_N), "list"),
        Q("Q137", qmap, d010_cnt(f"{n('A12')} <= 0")),
        Q("Q138", qmap, d010_list(f"{n('A15')} > 0 AND {n('A12')} = 0", '"A24","A4","A15","A12"', n("A15"), LIST_N), "list"),
        Q("Q139", qmap, d010_cnt('"A14" IS NOT NULL AND "A15" IS NULL')),
        Q("Q140", qmap, d010_list('"A16" IS NOT NULL AND "A26" IS NULL', '"A24","A4","A16","A26"', n("A16"), LIST_N), "list"),
    ]
    return out


def section3(qmap: dict) -> list:
    n = num
    gl = gu_label()
    return [
        Q("Q141", qmap, d010_agg(f"AVG({n('A16')}) AS avg_h", "TRUE"), "scalar", ""),
        Q("Q142", qmap, d010_agg(f"SUM({n('A14')}) AS sum_gfa", "TRUE"), "scalar", ""),
        Q("Q143", qmap, d010_agg(f"MAX({n('A16')}) AS max_h", SANE_H), "scalar", ""),
        Q("Q144", qmap, d010_agg(f"MIN({n('A12')}) AS min_area", f"{n('A12')} > 0"), "scalar", ""),
        Q("Q145", qmap, d010_agg(f"AVG({n('A16')}) AS avg_h", gu("해운대구")), "scalar", ""),
        Q("Q146", qmap, d010_agg(f"AVG({n('A14')}) AS avg_gfa", gu("금정구")), "scalar", ""),
        Q("Q147", qmap, d010_agg(f"AVG({n('A26')}) AS avg_fl", gu("동래구")), "scalar", ""),
        Q("Q148", qmap, d010_agg(f"SUM({n('A15')}) AS sum_lot", gu("강서구")), "scalar", ""),
        Q("Q149", qmap, d010_agg(f"AVG({n('A17')}) AS avg_bcr", gu("사하구")), "scalar", ""),
        Q("Q150", qmap, d010_agg(f"AVG({n('A18')}) AS avg_far", gu("수영구")), "scalar", ""),
        Q("Q151", qmap, f'SELECT {gl} AS gu, COUNT(*)::bigint AS n FROM "{D010}" GROUP BY 1 ORDER BY n DESC', "group"),
        Q("Q152", qmap, f'SELECT {gl} AS gu, AVG({n("A16")}) AS avg_h FROM "{D010}" GROUP BY 1 ORDER BY avg_h DESC NULLS LAST', "group"),
        Q("Q153", qmap, f'SELECT {gl} AS gu, SUM({n("A14")}) AS sum_gfa FROM "{D010}" GROUP BY 1 ORDER BY sum_gfa DESC NULLS LAST', "group"),
        Q("Q154", qmap, f'SELECT {gl} AS gu, AVG({n("A26")}) AS avg_fl FROM "{D010}" GROUP BY 1 ORDER BY avg_fl DESC NULLS LAST', "group"),
        Q("Q155", qmap, f'SELECT {gl} AS gu, COUNT(*) FILTER (WHERE {viol(True)})::bigint AS n FROM "{D010}" GROUP BY 1 ORDER BY n DESC', "group"),
        Q("Q156", qmap, f'SELECT {gl} AS gu, COUNT(*) FILTER (WHERE {sanji()})::bigint AS n FROM "{D010}" GROUP BY 1 ORDER BY n DESC', "group"),
        Q("Q157", qmap, f'SELECT {gl} AS gu, COUNT(*) FILTER (WHERE {struct_eq("철근콘크리트구조")})::bigint AS n FROM "{D010}" GROUP BY 1 ORDER BY n DESC', "group"),
        Q("Q158", qmap, f'SELECT "A11" AS structure, COUNT(*)::bigint AS n FROM "{D010}" GROUP BY 1 ORDER BY n DESC', "group"),
        Q("Q159", qmap, f'SELECT "A11" AS structure, AVG({n("A16")}) AS avg_h FROM "{D010}" GROUP BY 1 ORDER BY avg_h DESC NULLS LAST', "group"),
        Q("Q160", qmap, f'SELECT "A11" AS structure, AVG({n("A14")}) AS avg_gfa FROM "{D010}" GROUP BY 1 ORDER BY avg_gfa DESC NULLS LAST', "group"),
        Q("Q161", qmap, f'SELECT "A11" AS structure, AVG({n("A26")}) AS avg_fl FROM "{D010}" GROUP BY 1 ORDER BY avg_fl DESC NULLS LAST', "group"),
        Q("Q162", qmap, f'SELECT "A7" AS special, COUNT(*)::bigint AS n, AVG({n("A15")}) AS avg_lot FROM "{D010}" GROUP BY 1 ORDER BY n DESC', "group"),
        Q("Q163", qmap, f'SELECT "A20" AS viol, COUNT(*)::bigint AS n, AVG({n("A16")}) AS avg_h FROM "{D010}" GROUP BY 1 ORDER BY n DESC', "group"),
        Q("Q164", qmap, f'SELECT "A4" AS bjd, COUNT(*)::bigint AS n FROM "{D010}" GROUP BY 1 ORDER BY n DESC', "group"),
        Q("Q165", qmap, f'SELECT "A4" AS bjd, AVG({n("A14")}) AS avg_gfa FROM "{D010}" GROUP BY 1 ORDER BY avg_gfa DESC NULLS LAST', "group"),
        Q("Q166", qmap, d010_list(SANE_H, '"A24","A4","A5","A16"', n("A16"), 10), "list", note="높이 TOP-K는 이상치 제외(0 < A16 <= 500)"),
        Q("Q167", qmap, d010_list(f"{n('A14')} > 0", '"A24","A4","A5","A14"', n("A14"), 20), "list"),
        Q("Q168", qmap, d010_list(f"{gu('해운대구')} AND {SANE_H}", '"A24","A4","A5","A16"', n("A16"), 15), "list"),
        Q("Q169", qmap, d010_list(f"{gu('강서구')} AND {n('A15')} > 0", '"A24","A4","A5","A15"', n("A15"), 10), "list"),
        Q("Q170", qmap, d010_list_asc(f"{gu('사하구')} AND {n('A12')} > 0", '"A24","A4","A5","A12"', n("A12"), 10), "list"),
        Q("Q171", qmap, d010_list(f"{gu('수영구')} AND {n('A18')} > 0 AND {n('A18')} <= 1000", '"A24","A4","A18"', n("A18"), 10), "list"),
        Q("Q172", qmap, d010_list_asc(f"{gu('연제구')} AND {n('A17')} > 0 AND {n('A17')} <= 100", '"A24","A4","A17"', n("A17"), 10), "list"),
        Q("Q173", qmap, d010_list(f"{a4('대연동')} AND {SANE_H}", '"A24","A4","A5","A16"', n("A16"), 7), "list"),
        Q("Q174", qmap, d010_list(f"{a4('문현동')} AND {n('A26')} > 0", '"A24","A4","A26"', n("A26"), 10), "list"),
        Q("Q175", qmap, d010_list(f"{a4('광안동')} AND {n('A14')} > 0", '"A24","A4","A14"', n("A14"), 5), "list"),
        Q("Q176", qmap, f'SELECT {gl} AS gu, COUNT(*)::bigint AS n FROM "{D010}" GROUP BY 1 ORDER BY n DESC LIMIT 5', "group"),
        Q("Q177", qmap, f'SELECT {gl} AS gu, AVG({n("A16")}) AS avg_h FROM "{D010}" GROUP BY 1 ORDER BY avg_h DESC NULLS LAST LIMIT 7', "group"),
        Q("Q178", qmap, f'''SELECT {gl} AS gu,
  COUNT(*) FILTER (WHERE {viol(True)})::float8 / NULLIF(COUNT(*),0) AS viol_ratio,
  COUNT(*) FILTER (WHERE {viol(True)})::bigint AS viol_n,
  COUNT(*)::bigint AS n
FROM "{D010}" GROUP BY 1 ORDER BY viol_ratio DESC NULLS LAST''', "group"),
        Q("Q179", qmap, f'''SELECT {gl} AS gu,
  COUNT(*) FILTER (WHERE {sanji()})::float8 / NULLIF(COUNT(*),0) AS sanji_ratio,
  COUNT(*) FILTER (WHERE {sanji()})::bigint AS sanji_n,
  COUNT(*)::bigint AS n
FROM "{D010}" GROUP BY 1 ORDER BY sanji_ratio DESC NULLS LAST''', "group"),
        Q("Q180", qmap, f'''SELECT "A11" AS structure, COUNT(*)::bigint AS n,
  100.0 * COUNT(*) / SUM(COUNT(*)) OVER () AS pct
FROM "{D010}" GROUP BY 1 ORDER BY n DESC''', "group"),
        Q("Q181", qmap, d010_agg(f"PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY {n('A16')}) AS median_h", f"{n('A16')} IS NOT NULL"), "scalar", ""),
        Q("Q182", qmap, d010_agg(
            f"PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY {n('A14')}) AS p25, "
            f"PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY {n('A14')}) AS p50, "
            f"PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY {n('A14')}) AS p75",
            f"{n('A14')} IS NOT NULL",
        ), "scalar", ""),
        Q("Q183", qmap, d010_agg(f"STDDEV_POP({n('A16')}) AS std_h", f"{n('A16')} IS NOT NULL"), "scalar", ""),
        Q("Q184", qmap, d010_agg(f"VAR_POP({n('A12')}) AS var_area", f"{n('A12')} IS NOT NULL"), "scalar", ""),
        Q("Q185", qmap, f'''SELECT bin, COUNT(*)::bigint AS n FROM (
  SELECT CASE
    WHEN {n('A16')} >= 0 AND {n('A16')} < 10 THEN '0~10m'
    WHEN {n('A16')} >= 10 AND {n('A16')} < 30 THEN '10~30m'
    WHEN {n('A16')} >= 30 AND {n('A16')} <= 60 THEN '30~60m'
    WHEN {n('A16')} > 60 THEN '60m 초과'
  END AS bin
  FROM "{D010}" WHERE {n('A16')} IS NOT NULL
) t WHERE bin IS NOT NULL GROUP BY 1 ORDER BY 1''', "group"),
        Q("Q186", qmap, f'''SELECT bin, COUNT(*)::bigint AS n FROM (
  SELECT CASE
    WHEN {n('A26')} BETWEEN 1 AND 2 THEN '1~2층'
    WHEN {n('A26')} BETWEEN 3 AND 5 THEN '3~5층'
    WHEN {n('A26')} BETWEEN 6 AND 10 THEN '6~10층'
    WHEN {n('A26')} >= 11 THEN '11층 이상'
  END AS bin
  FROM "{D010}" WHERE {n('A26')} IS NOT NULL
) t WHERE bin IS NOT NULL GROUP BY 1 ORDER BY 1''', "group"),
        Q("Q187", qmap, f'''SELECT bin, COUNT(*)::bigint AS n, AVG(h) AS avg_h FROM (
  SELECT CASE
    WHEN {n('A14')} < 500 THEN '500㎡ 미만'
    WHEN {n('A14')} <= 2000 THEN '500~2000㎡'
    ELSE '2000㎡ 초과'
  END AS bin, {n('A16')} AS h
  FROM "{D010}" WHERE {n('A14')} IS NOT NULL
) t GROUP BY 1 ORDER BY 1''', "group"),
        Q("Q188", qmap, f'SELECT {gl} AS gu, MAX({n("A16")}) - AVG({n("A16")}) AS max_minus_avg FROM "{D010}" GROUP BY 1 ORDER BY max_minus_avg DESC NULLS LAST', "group"),
        Q("Q189", qmap, f'''SELECT {gl} AS gu,
  MAX({n("A14")}) - MIN({n("A14")}) FILTER (WHERE {n("A14")} > 0) AS max_minus_min_pos
FROM "{D010}" GROUP BY 1 ORDER BY max_minus_min_pos DESC NULLS LAST''', "group"),
        Q("Q190", qmap, f'''WITH ranked AS (
  SELECT {gl} AS gu, {n("A16")} AS h,
         ROW_NUMBER() OVER (PARTITION BY {gl} ORDER BY {n("A16")} DESC NULLS LAST) AS rn
  FROM "{D010}" WHERE {SANE_H}
)
SELECT a.gu, a.h AS h1, b.h AS h2, a.h - b.h AS diff
FROM ranked a JOIN ranked b ON a.gu = b.gu AND a.rn = 1 AND b.rn = 2
ORDER BY diff DESC NULLS LAST''', "group"),
        Q("Q191", qmap, f'''WITH base AS (
  SELECT {n("A16")} AS h, {n("A14")} AS gfa FROM "{D010}" WHERE {SANE_H} AND {n("A14")} IS NOT NULL
), p AS (SELECT PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY h) AS cut FROM base)
SELECT AVG(gfa) AS avg_gfa, COUNT(*)::bigint AS n, (SELECT cut FROM p) AS cut
FROM base, p WHERE h >= p.cut''', "scalar", ""),
        Q("Q192", qmap, f'''WITH base AS (
  SELECT {n("A14")} AS gfa, {n("A26")} AS fl FROM "{D010}" WHERE {n("A14")} > 0 AND {n("A26")} IS NOT NULL
), p AS (SELECT PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY gfa) AS cut FROM base)
SELECT AVG(fl) AS avg_fl, COUNT(*)::bigint AS n, (SELECT cut FROM p) AS cut
FROM base, p WHERE gfa >= p.cut''', "scalar", ""),
        Q("Q193", qmap, f'''WITH g AS (
  SELECT {gl} AS gu, AVG({n("A15")}) AS avg_lot FROM "{D010}" GROUP BY 1
), city AS (SELECT AVG({n("A15")}) AS city_avg FROM "{D010}")
SELECT g.gu, g.avg_lot, city.city_avg, g.avg_lot - city.city_avg AS diff
FROM g, city ORDER BY g.avg_lot DESC NULLS LAST''', "group"),
        Q("Q194", qmap, f'''SELECT "A11" AS structure,
  COUNT(*) FILTER (WHERE {viol(True)})::float8 / NULLIF(COUNT(*),0) AS viol_ratio,
  COUNT(*)::bigint AS n
FROM "{D010}" GROUP BY 1 ORDER BY viol_ratio DESC NULLS LAST''', "group"),
        Q("Q195", qmap, d010_agg(
            f"AVG({n('A16')}) FILTER (WHERE {sanji()}) AS sanji_h, "
            f"AVG({n('A16')}) FILTER (WHERE {ilban()}) AS ilban_h, "
            f"AVG({n('A16')}) FILTER (WHERE {sanji()}) - AVG({n('A16')}) FILTER (WHERE {ilban()}) AS diff",
            "TRUE",
        ), "compare", ""),
        Q("Q196", qmap, d010_agg(
            f"AVG({n('A14')}) FILTER (WHERE {sanji()}) AS sanji_gfa, "
            f"AVG({n('A14')}) FILTER (WHERE {ilban()}) AS ilban_gfa",
            "TRUE",
        ), "compare", ""),
        Q("Q197", qmap, d010_agg(
            f"AVG({n('A26')}) FILTER (WHERE {viol(True)}) AS viol_fl, "
            f"AVG({n('A26')}) FILTER (WHERE {viol(False)}) AS normal_fl",
            "TRUE",
        ), "compare", ""),
        Q("Q198", qmap, d010_agg(
            f"AVG({n('A16')}) FILTER (WHERE {gu('해운대구')}) AS haeundae_h, "
            f"AVG({n('A16')}) FILTER (WHERE {gu('수영구')}) AS suyeong_h",
            f"{gu('해운대구')} OR {gu('수영구')}",
        ), "compare", ""),
        Q("Q199", qmap, d010_agg(
            f"AVG({n('A14')}) FILTER (WHERE {gu('금정구')}) AS geumjeong_gfa, "
            f"AVG({n('A14')}) FILTER (WHERE {gu('동래구')}) AS dongnae_gfa",
            f"{gu('금정구')} OR {gu('동래구')}",
        ), "compare", ""),
        Q("Q200", qmap, d010_agg(
            f"COUNT(*) FILTER (WHERE {gu('강서구')})::bigint AS gangseo_n, "
            f"AVG({n('A15')}) FILTER (WHERE {gu('강서구')}) AS gangseo_lot, "
            f"COUNT(*) FILTER (WHERE {gu('기장군')})::bigint AS gijang_n, "
            f"AVG({n('A15')}) FILTER (WHERE {gu('기장군')}) AS gijang_lot",
            f"{gu('강서구')} OR {gu('기장군')}",
        ), "compare", ""),
    ]


def _usage_rows() -> list[tuple[str, str, str, str]]:
    places = [
        "금정구", "동래구", "구서동", "서동", "부곡동", "장전동", "남산동",
        "금사동", "온천동", "안락동", "사직동", "명장동", "명륜동",
    ]
    usages = [
        "단독주택", "공동주택", "아파트", "다세대주택", "다가구주택",
        "제1종근린생활시설", "제2종근린생활시설", "업무시설", "숙박시설",
        "공장", "창고시설", "교육연구시설", "종교시설", "의료시설",
        "판매시설", "자동차관련시설", "오피스텔", "일반음식점",
    ]
    ops = ["count", "list", "avg", "topk"]
    rows = []
    for i in range(52):
        qid = f"Q{201 + i:03d}"
        rows.append((qid, places[i % 13], usages[i % 18], ops[i % 4]))
    return rows


def section4(qmap: dict) -> list:
    n = num
    out = []
    for qid, place, usage, op in _usage_rows():
        tbl, where = d198_of(place)
        pred = f"{where} AND {usage_pred(usage)}"
        if op == "count":
            out.append(Q(qid, qmap, d198_cnt(tbl, pred)))
        elif op == "list":
            out.append(Q(qid, qmap, d198_list(tbl, pred, '"A13" AS name, "A4", "A7" AS lot', n("A19"), LIST_N), "list"))
        elif op == "avg":
            out.append(Q(qid, qmap, d198_agg(tbl, f"AVG({n('A30')}) AS avg_h, COUNT(*)::bigint AS n", pred), "scalar", ""))
        else:
            out.append(Q(qid, qmap, d198_list(tbl, pred, '"A13" AS name, "A4", "A7" AS lot, "A19" AS gfa', n("A19"), 10), "list"))

    gj, dr = D198_GJ, D198_DR
    out += [
        Q("Q253", qmap, d198_cnt(gj, f"\"A25\"='공동주택' AND \"A23\" ILIKE '%철근콘크리트%'")),
        Q("Q254", qmap, d198_cnt(dr, f"\"A25\"='단독주택' AND \"A23\" ILIKE '%벽돌%'")),
        Q("Q255", qmap, d198_list(gj, f"\"A25\"='공동주택' AND {n('A30')} >= 40", '"A13" AS name, "A4", "A30" AS h', n("A30"), LIST_N), "list"),
        Q("Q256", qmap, d198_cnt(dr, f"\"A25\"='업무시설' AND {n('A31')} >= 5")),
        Q("Q257", qmap, d198_list(gj, f"\"A25\"='공장' AND {n('A19')} >= 3000", '"A13" AS name, "A4", "A19" AS gfa', n("A19"), LIST_N), "list"),
        Q("Q258", qmap, d198_cnt(dr, f"\"A25\"='숙박시설' AND {n('A17')} >= 500")),
        Q("Q259", qmap, d198_list(gj, f"\"A25\"='단독주택' AND {n('A18')} BETWEEN 80 AND 200", '"A13" AS name, "A4", "A18" AS bldg_area', n("A18"), LIST_N), "list"),
        Q("Q260", qmap, d198_cnt(dr, f"\"A25\"='공동주택' AND {n('A30')} BETWEEN 20 AND 70")),
        Q("Q261", qmap, d198_cnt(gj, "\"A25\" IN ('단독주택','공동주택')")),
        Q("Q262", qmap, d198_cnt(dr, "\"A25\" IN ('공장','창고시설')")),
        Q("Q263", qmap, d198_cnt(gj, "\"A25\" IS DISTINCT FROM '공동주택'")),
        Q("Q264", qmap, d198_cnt(dr, "\"A25\" NOT IN ('제1종근린생활시설','제2종근린생활시설')")),
        Q("Q265", qmap, d198_list(gj, f"{a4('구서동')} AND \"A27\"='아파트' AND {n('A31')} >= 10", '"A13" AS name, "A4", "A31" AS fl', n("A31"), LIST_N), "list"),
        Q("Q266", qmap, d198_list(dr, f"{a4('온천동')} AND \"A27\"='다세대주택' AND {n('A19')} >= 500", '"A13" AS name, "A4", "A19" AS gfa', n("A19"), LIST_N), "list"),
        Q("Q267", qmap, d198_cnt(gj, f"{a4('장전동')} AND \"A27\"='다가구주택' AND {n('A30')} >= 15")),
        Q("Q268", qmap, d198_cnt(dr, f"{a4('사직동')} AND \"A27\"='일반음식점'")),
        Q("Q269", qmap, d198_agg(gj, f"AVG({n('A31')}) AS avg_fl, COUNT(*)::bigint AS n", "\"A27\"='오피스텔'"), "scalar", ""),
        Q("Q270", qmap, d198_agg(dr, "COUNT(*) FILTER (WHERE \"A27\"='아파트')::bigint AS apt_n, COUNT(*) FILTER (WHERE \"A27\"='다세대주택')::bigint AS multi_n", "TRUE"), "compare", ""),
        Q("Q271", qmap, d198_agg(gj, "COUNT(*) FILTER (WHERE \"A29\"='주거용')::bigint AS resi_n, COUNT(*) FILTER (WHERE \"A29\"='상업용')::bigint AS com_n", "TRUE"), "compare", ""),
        Q("Q272", qmap, d198_agg(dr, f"AVG({n('A19')}) AS avg_gfa, COUNT(*)::bigint AS n", "\"A29\"='주거용'"), "scalar", ""),
        Q("Q273", qmap, d198_list(gj, f"\"A29\"='상업용' AND {SANE_H30}", '"A13" AS name, "A4", "A30" AS h', n("A30"), 10), "list"),
        Q("Q274", qmap, d198_cnt(dr, "\"A29\"='문교사회용'")),
        Q("Q275", qmap, f'SELECT "A25" AS usage, COUNT(*)::bigint AS n FROM "{gj}" WHERE {nonempty("A25")} GROUP BY 1 ORDER BY n DESC', "group"),
        Q("Q276", qmap, f'SELECT "A25" AS usage, AVG({n("A30")}) AS avg_h FROM "{dr}" WHERE {nonempty("A25")} GROUP BY 1 ORDER BY avg_h DESC NULLS LAST', "group"),
        Q("Q277", qmap, f'SELECT "A27" AS detail, COUNT(*)::bigint AS n FROM "{gj}" WHERE {nonempty("A27")} GROUP BY 1 ORDER BY n DESC LIMIT 15', "group"),
        Q("Q278", qmap, f'SELECT "A29" AS cls, AVG({n("A19")}) AS avg_gfa FROM "{dr}" WHERE {nonempty("A29")} GROUP BY 1 ORDER BY avg_gfa DESC NULLS LAST', "group"),
        Q("Q279", qmap, f'SELECT "A23" AS structure, COUNT(*)::bigint AS n FROM "{gj}" WHERE "A25"=\'공동주택\' GROUP BY 1 ORDER BY n DESC', "group"),
        Q("Q280", qmap, f'SELECT "A4" AS bjd, COUNT(*)::bigint AS n FROM "{dr}" WHERE "A25"=\'단독주택\' GROUP BY 1 ORDER BY n DESC', "group"),
        Q("Q281", qmap, f'SELECT "A4" AS bjd, COUNT(*)::bigint AS n FROM "{gj}" WHERE "A27"=\'아파트\' GROUP BY 1 ORDER BY n DESC', "group"),
        Q("Q282", qmap, f'''SELECT "A4" AS bjd,
  COUNT(*) FILTER (WHERE "A29"='상업용')::float8 / NULLIF(COUNT(*),0) AS com_ratio,
  COUNT(*)::bigint AS n
FROM "{dr}" GROUP BY 1 ORDER BY com_ratio DESC NULLS LAST''', "group"),
        Q("Q283", qmap, f'SELECT "A25" AS usage, AVG({n("A21")}) AS avg_bcr, AVG({n("A20")}) AS avg_far FROM "{gj}" WHERE {nonempty("A25")} GROUP BY 1 ORDER BY 1', "group"),
        Q("Q284", qmap, f'SELECT "A25" AS usage, MAX({n("A31")}) AS max_fl FROM "{dr}" WHERE {nonempty("A25")} GROUP BY 1 ORDER BY max_fl DESC NULLS LAST', "group"),
        Q("Q285", qmap, f'SELECT "A27" AS detail, AVG({n("A18")}) AS avg_bldg_area FROM "{gj}" WHERE {nonempty("A27")} GROUP BY 1 ORDER BY avg_bldg_area DESC NULLS LAST', "group"),
        Q("Q286", qmap, d198_agg(dr, f"AVG({n('A30')}) FILTER (WHERE \"A29\"='주거용') AS resi_h, AVG({n('A30')}) FILTER (WHERE \"A29\"='상업용') AS com_h, AVG({n('A30')}) FILTER (WHERE \"A29\"='주거용') - AVG({n('A30')}) FILTER (WHERE \"A29\"='상업용') AS diff", "TRUE"), "compare", ""),
        Q("Q287", qmap, d198_agg(gj, f"AVG({n('A17')}) FILTER (WHERE \"A25\"='공동주택') AS apt_lot, AVG({n('A17')}) FILTER (WHERE \"A25\"='단독주택') AS det_lot", "TRUE"), "compare", ""),
        Q("Q288", qmap, d198_agg(dr, f"AVG({n('A31')}) FILTER (WHERE \"A27\"='아파트') AS apt_fl, AVG({n('A31')}) FILTER (WHERE \"A27\"='다세대주택') AS multi_fl", "TRUE"), "compare", ""),
        Q("Q289", qmap, d198_cnt(gj, f"{nonempty('A25')} AND {nonempty('A27')}")),
        Q("Q290", qmap, d198_cnt(dr, f"{nonempty('A25')} AND {empty_name('A27')}")),
        Q("Q291", qmap, d198_list(gj, "\"A29\"='주거용' AND \"A25\" NOT IN ('단독주택','공동주택')", '"A13" AS name, "A4", "A25", "A29"', n("A19"), LIST_N), "list"),
        Q("Q292", qmap, d198_cnt(dr, "\"A29\"='상업용' AND \"A25\" IN ('단독주택','공동주택')")),
        Q("Q293", qmap, d198_list(gj, "\"A27\"='아파트' AND \"A25\" IS DISTINCT FROM '공동주택'", '"A13" AS name, "A4", "A25", "A27"', n("A19"), LIST_N), "list"),
        Q("Q294", qmap, d198_list(dr, "\"A27\"='일반음식점' AND \"A25\" IS DISTINCT FROM '제2종근린생활시설'", '"A13" AS name, "A4", "A25", "A27"', n("A19"), LIST_N), "list"),
        Q("Q295", qmap, f'''SELECT COUNT(*) FILTER (WHERE d."A20" = 'Y')::float8 / NULLIF(COUNT(*),0) AS viol_ratio,
  COUNT(*)::bigint AS n
FROM "{gj}" u
JOIN "{D010}" d ON u."A2" = d."A2"
WHERE u."A25"='공동주택' ''', "scalar", ""),
        Q("Q296", qmap, f'''SELECT COUNT(*)::bigint AS n
FROM "{dr}" u
LEFT JOIN "{D010}" d ON u."A2" = d."A2"
WHERE u."A25"='단독주택' AND d."A20" IS DISTINCT FROM 'Y' '''),
        Q("Q297", qmap, f'''WITH top10 AS (
  SELECT {n("A19")} AS gfa, {n("A30")} AS h FROM "{gj}"
  WHERE "A27"='아파트' ORDER BY {n("A19")} DESC NULLS LAST LIMIT 10
) SELECT AVG(h) AS avg_h, COUNT(*)::bigint AS n FROM top10''', "scalar", ""),
        Q("Q298", qmap, f'''WITH base AS (
  SELECT {n("A30")} AS h, {n("A19")} AS gfa FROM "{dr}" WHERE "A25"='업무시설' AND {n("A30")} IS NOT NULL
), p AS (SELECT PERCENTILE_CONT(0.80) WITHIN GROUP (ORDER BY h) AS cut FROM base)
SELECT AVG(gfa) AS avg_gfa, COUNT(*)::bigint AS n FROM base, p WHERE h >= p.cut''', "scalar", ""),
        Q("Q299", qmap, f'''SELECT "A4" AS bjd,
  COUNT(*) FILTER (WHERE "A25"='공동주택')::float8 / NULLIF(COUNT(*),0) AS apt_ratio,
  COUNT(*) FILTER (WHERE "A25"='공동주택')::bigint AS apt_n,
  COUNT(*)::bigint AS n
FROM "{gj}" GROUP BY 1 ORDER BY apt_ratio DESC NULLS LAST LIMIT 5''', "group"),
        Q("Q300", qmap, f'''SELECT "A4" AS bjd, COUNT(*)::bigint AS n
FROM "{dr}" WHERE "A25"='단독주택' GROUP BY 1 ORDER BY n DESC LIMIT 5''', "group"),
    ]
    return out


def _age_years(col: str = "A34") -> str:
    return f"(CURRENT_DATE - \"{col}\"::date) / 365.25"


def section5(qmap: dict) -> list:
    n = num
    gj, dr = D198_GJ, D198_DR
    age = _age_years("A34")
    return [
        Q("Q301", qmap, d198_cnt(gj, year_lt("A34", 2000))),
        Q("Q302", qmap, d198_cnt(dr, year_ge("A34", 2010))),
        Q("Q303", qmap, d198_list(gj, f"{a4('구서동')} AND {year_between('A34', 1990, 1999)}", '"A13" AS name, "A4", "A7" AS lot, "A34"', '"A34"', LIST_N), "list"),
        Q("Q304", qmap, d198_cnt(dr, f"{a4('온천동')} AND {year_lt('A34', 1980)}")),
        Q("Q305", qmap, d198_cnt(gj, f"{a4('장전동')} AND {age_lt('A34', 10)}")),
        Q("Q306", qmap, d198_cnt(dr, f"{a4('사직동')} AND {age_gte('A34', 30)}")),
        Q("Q307", qmap, d198_cnt(gj, year_lt("A33", 1995))),
        Q("Q308", qmap, d198_list(dr, year_ge("A33", 2015), '"A13" AS name, "A4", "A33"', '"A33"', LIST_N), "list"),
        Q("Q309", qmap, d198_agg(gj, f"AVG({age}) AS avg_age, COUNT(*)::bigint AS n", valid_date("A34")), "scalar", ""),
        Q("Q310", qmap, d198_agg(dr, 'MIN("A34"::date) AS oldest', valid_date("A34")), "scalar", ""),
        Q("Q311", qmap, f'''SELECT "A13" AS name, "A4", "A34"
FROM "{gj}" WHERE {valid_date("A34")}
ORDER BY "A34"::date DESC NULLS LAST LIMIT 10''', "list"),
        Q("Q312", qmap, f'''SELECT "A13" AS name, "A4", "A34"
FROM "{dr}" WHERE {valid_date("A34")}
ORDER BY "A34"::date ASC NULLS LAST LIMIT 10''', "list"),
        Q("Q313", qmap, d198_cnt(gj, f"{a4('서동')} AND {age_gte('A34', 40)}")),
        Q("Q314", qmap, d198_cnt(gj, f"{a4('부곡동')} AND {age_lt('A34', 20)}")),
        Q("Q315", qmap, d198_list(dr, f"{a4('안락동')} AND {year_between('A34', 1990, 1999)}", '"A13" AS name, "A4", "A34"', '"A34"', LIST_N), "list"),
        Q("Q316", qmap, d198_cnt(dr, f"{a4('명장동')} AND {year_between('A33', 2000, 2009)}")),
        Q("Q317", qmap, f'''SELECT {year_expr("A34")} AS y, COUNT(*)::bigint AS n
FROM "{gj}" WHERE {a4("남산동")} AND "A34"::text ~ '^[0-9]{{4}}'
GROUP BY 1 ORDER BY 1''', "group"),
        Q("Q318", qmap, f'''SELECT {year_expr("A33")} AS y, COUNT(*)::bigint AS n
FROM "{dr}" WHERE {a4("명륜동")} AND "A33"::text ~ '^[0-9]{{4}}'
GROUP BY 1 ORDER BY 1''', "group"),
        Q("Q319", qmap, d198_list(
            gj,
            f"{a4('금사동')} AND {valid_date('A33')} AND {valid_date('A34')} AND \"A34\"::date - \"A33\"::date >= 365",
            '"A13" AS name, "A4", "A33", "A34", ("A34"::date - "A33"::date) AS days',
            '("A34"::date - "A33"::date)',
            LIST_N,
        ), "list"),
        Q("Q320", qmap, d198_agg(
            dr,
            'AVG("A34"::date - "A33"::date) AS avg_days, COUNT(*)::bigint AS n',
            f"{a4('수안동')} AND {valid_date('A33')} AND {valid_date('A34')}",
        ), "scalar", ""),
        Q("Q321", qmap, d198_agg(
            dr,
            '''COUNT(*) FILTER (WHERE "A34"::date - "A33"::date <= 730)::float8
               / NULLIF(COUNT(*),0) AS within_2y_ratio,
               COUNT(*)::bigint AS n''',
            f"{a4('복천동')} AND {valid_date('A33')} AND {valid_date('A34')}",
        ), "scalar", ""),
        Q("Q322", qmap, d198_cnt(gj, f"{a4('회동동')} AND {nonempty('A33')} AND {empty_name('A34')}")),
        Q("Q323", qmap, d198_cnt(gj, f"{a4('두구동')} AND {nonempty('A34')} AND {empty_name('A33')}")),
        Q("Q324", qmap, d198_list(
            dr,
            f"{a4('낙민동')} AND {valid_date('A33')} AND {valid_date('A34')} AND \"A33\"::date > \"A34\"::date",
            '"A13" AS name, "A4", "A33", "A34"',
            '"A33"',
            LIST_N,
        ), "list"),
        Q("Q325", qmap, d198_agg(
            gj,
            f'''COUNT(*) FILTER (WHERE {year_expr("A33")} <> {year_expr("A34")})::float8
               / NULLIF(COUNT(*),0) AS diff_year_ratio,
               COUNT(*)::bigint AS n''',
            '"A33"::text ~ \'^[0-9]{4}\' AND "A34"::text ~ \'^[0-9]{4}\'',
        ), "scalar", ""),
        Q("Q326", qmap, d198_cnt(dr, f"{valid_date('A33')} AND {valid_date('A34')} AND \"A34\"::date - \"A33\"::date >= 1095")),
        Q("Q327", qmap, f'''SELECT bin, COUNT(*)::bigint AS n FROM (
  SELECT CASE
    WHEN y < 1980 THEN '1980년대 이전'
    WHEN y BETWEEN 1980 AND 1989 THEN '1980년대'
    WHEN y BETWEEN 1990 AND 1999 THEN '1990년대'
    WHEN y BETWEEN 2000 AND 2009 THEN '2000년대'
    WHEN y BETWEEN 2010 AND 2019 THEN '2010년대'
    WHEN y >= 2020 THEN '2020년대'
  END AS bin
  FROM (SELECT {year_expr("A34")} AS y FROM "{gj}" WHERE "A34"::text ~ '^[0-9]{{4}}') s
) t WHERE bin IS NOT NULL GROUP BY 1 ORDER BY 1''', "group"),
        Q("Q328", qmap, f'SELECT "A4" AS bjd, AVG({age}) AS avg_age FROM "{dr}" WHERE {valid_date("A34")} GROUP BY 1 ORDER BY avg_age DESC NULLS LAST', "group"),
        Q("Q329", qmap, f'''SELECT "A4" AS bjd,
  COUNT(*) FILTER (WHERE {age_gte("A34", 30)})::float8 / NULLIF(COUNT(*) FILTER (WHERE {valid_date("A34")}),0) AS ratio_30y,
  COUNT(*) FILTER (WHERE {age_gte("A34", 30)})::bigint AS n30,
  COUNT(*) FILTER (WHERE {valid_date("A34")})::bigint AS n
FROM "{gj}" GROUP BY 1 ORDER BY ratio_30y DESC NULLS LAST''', "group"),
        Q("Q330", qmap, f'''SELECT "A4" AS bjd,
  COUNT(*) FILTER (WHERE {age_lt("A34", 10)})::float8 / NULLIF(COUNT(*) FILTER (WHERE {valid_date("A34")}),0) AS ratio_10y,
  COUNT(*) FILTER (WHERE {age_lt("A34", 10)})::bigint AS n10,
  COUNT(*) FILTER (WHERE {valid_date("A34")})::bigint AS n
FROM "{dr}" GROUP BY 1 ORDER BY ratio_10y DESC NULLS LAST''', "group"),
        Q("Q331", qmap, f'''SELECT "A34"::date AS d, COUNT(*)::bigint AS n
FROM "{gj}" WHERE {valid_date("A34")}
GROUP BY 1 ORDER BY n DESC, d LIMIT 10''', "group"),
        Q("Q332", qmap, f'''SELECT "A33"::date AS d, COUNT(*)::bigint AS n
FROM "{dr}" WHERE {valid_date("A33")}
GROUP BY 1 HAVING COUNT(*) >= 5
ORDER BY n DESC, d''', "group"),
        Q("Q333", qmap, f'''WITH base AS (
  SELECT {year_expr("A34")} AS y, {n("A19")} AS gfa
  FROM "{gj}" WHERE "A34"::text ~ '^[0-9]{{4}}' AND {n("A19")} IS NOT NULL
), p AS (SELECT PERCENTILE_CONT(0.10) WITHIN GROUP (ORDER BY y) AS cut FROM base)
SELECT AVG(gfa) AS avg_gfa, COUNT(*)::bigint AS n FROM base, p WHERE y <= p.cut''', "scalar", ""),
        Q("Q334", qmap, f'''WITH base AS (
  SELECT {year_expr("A34")} AS y, {n("A30")} AS h
  FROM "{dr}" WHERE "A34"::text ~ '^[0-9]{{4}}' AND {n("A30")} IS NOT NULL
), p AS (SELECT PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY y) AS cut FROM base)
SELECT AVG(h) AS avg_h, COUNT(*)::bigint AS n FROM base, p WHERE y >= p.cut''', "scalar", ""),
        Q("Q335", qmap, d198_agg(gj, f"CORR({age}, {n('A19')}) AS corr_age_gfa, COUNT(*)::bigint AS n", f"{valid_date('A34')} AND {n('A19')} IS NOT NULL"), "scalar", ""),
        Q("Q336", qmap, d198_agg(dr, f"CORR({age}, {n('A31')}) AS corr_age_fl, COUNT(*)::bigint AS n", f"{valid_date('A34')} AND {n('A31')} IS NOT NULL"), "scalar", ""),
        Q("Q337", qmap, d198_agg(
            gj,
            f'''COUNT(*) FILTER (WHERE {n("A31")} >= 10)::float8
               / NULLIF(COUNT(*),0) AS fl10_ratio, COUNT(*)::bigint AS n''',
            age_gte("A34", 30),
        ), "scalar", ""),
        Q("Q338", qmap, d198_agg(
            dr,
            '''COUNT(*) FILTER (WHERE "A10"='집합건축물')::float8
               / NULLIF(COUNT(*),0) AS jibhap_ratio, COUNT(*)::bigint AS n''',
            age_lt("A34", 20),
        ), "scalar", ""),
        Q("Q339", qmap, f'''SELECT
  PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY y) FILTER (WHERE src='gj') AS gj_median_year,
  PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY y) FILTER (WHERE src='dr') AS dr_median_year
FROM (
  SELECT 'gj' AS src, {year_expr("A34")} AS y FROM "{gj}" WHERE "A34"::text ~ '^[0-9]{{4}}'
  UNION ALL
  SELECT 'dr', {year_expr("A34")} FROM "{dr}" WHERE "A34"::text ~ '^[0-9]{{4}}'
) t''', "compare", ""),
        Q("Q340", qmap, f'''SELECT
  AVG(age) FILTER (WHERE src='gj') AS gj_avg_age,
  AVG(age) FILTER (WHERE src='dr') AS dr_avg_age
FROM (
  SELECT 'gj' AS src, {age} AS age FROM "{gj}" WHERE {valid_date("A34")}
  UNION ALL
  SELECT 'dr', {age} FROM "{dr}" WHERE {valid_date("A34")}
) t''', "compare", ""),
        Q("Q341", qmap, d198_cnt(gj, f"{nonempty('A34')} AND NOT ({valid_date('A34')})")),
        Q("Q342", qmap, d198_cnt(dr, f"{nonempty('A33')} AND NOT ({valid_date('A33')})")),
        Q("Q343", qmap, d198_cnt(gj, f"{valid_date('A34')} AND \"A34\"::date > CURRENT_DATE")),
        Q("Q344", qmap, d198_cnt(dr, f"{valid_date('A33')} AND \"A33\"::date > CURRENT_DATE")),
        Q("Q345", qmap, d198_agg(
            gj,
            f"AVG({n('A30')}) FILTER (WHERE {year_lt('A34', 2000)}) AS before_2000_h, "
            f"AVG({n('A30')}) FILTER (WHERE {year_ge('A34', 2000)}) AS after_2000_h",
            '"A34"::text ~ \'^[0-9]{4}\'',
        ), "compare", ""),
        Q("Q346", qmap, d198_agg(
            dr,
            f"AVG({n('A19')}) FILTER (WHERE {age_gte('A34', 30)}) AS age30_gfa, "
            f"AVG({n('A19')}) FILTER (WHERE {age_lt('A34', 10)}) AS age10_gfa",
            valid_date("A34"),
        ), "compare", ""),
        Q("Q347", qmap, f'''SELECT bin, COUNT(*)::bigint AS n FROM (
  SELECT CASE
    WHEN days < 365 THEN '1년 미만'
    WHEN days <= 1095 THEN '1~3년'
    ELSE '3년 초과'
  END AS bin
  FROM (
    SELECT "A34"::date - "A33"::date AS days
    FROM "{gj}" WHERE {valid_date("A33")} AND {valid_date("A34")}
  ) s
) t GROUP BY 1 ORDER BY 1''', "group"),
        Q("Q348", qmap, f'SELECT {year_expr("A34")} AS y, AVG({n("A21")}) AS avg_bcr FROM "{dr}" WHERE "A34"::text ~ \'^[0-9]{{4}}\' GROUP BY 1 ORDER BY 1', "group"),
        Q("Q349", qmap, f'SELECT {year_expr("A34")} AS y, AVG({n("A20")}) AS avg_far FROM "{gj}" WHERE "A34"::text ~ \'^[0-9]{{4}}\' GROUP BY 1 ORDER BY 1', "group"),
        Q("Q350", qmap, f'''WITH base AS (
  SELECT {n("A31")} AS fl, {year_expr("A34")} AS y
  FROM "{dr}" WHERE "A34"::text ~ '^[0-9]{{4}}' AND {n("A31")} IS NOT NULL
), p AS (SELECT PERCENTILE_CONT(0.01) WITHIN GROUP (ORDER BY y) AS cut FROM base)
SELECT AVG(fl) AS avg_fl, COUNT(*)::bigint AS n FROM base, p WHERE y <= p.cut''', "scalar", ""),
        Q("Q351", qmap, f'''WITH base AS (
  SELECT {year_expr("A34")} AS y, {n("A18")} AS bldg_area
  FROM "{gj}" WHERE "A34"::text ~ '^[0-9]{{4}}' AND {n("A18")} IS NOT NULL
), p AS (SELECT PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY y) AS cut FROM base)
SELECT AVG(bldg_area) AS avg_area, COUNT(*)::bigint AS n FROM base, p WHERE y >= p.cut''', "scalar", ""),
        Q("Q352", qmap, d198_agg(
            dr,
            'PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY "A34"::date - "A33"::date) AS median_days',
            f"{valid_date('A33')} AND {valid_date('A34')}",
        ), "scalar", ""),
        Q("Q353", qmap, d198_agg(
            gj,
            'STDDEV_POP("A34"::date - "A33"::date) AS std_days',
            f"{valid_date('A33')} AND {valid_date('A34')}",
        ), "scalar", ""),
        Q("Q354", qmap, f'SELECT "A4" AS bjd, COUNT(*)::bigint AS n FROM "{dr}" WHERE {empty_name("A34")} GROUP BY 1 ORDER BY n DESC', "group"),
        Q("Q355", qmap, f'SELECT "A4" AS bjd, COUNT(*)::bigint AS n FROM "{gj}" WHERE {empty_name("A33")} GROUP BY 1 ORDER BY n DESC', "group"),
        Q("Q356", qmap, f'SELECT "A4" AS bjd, COUNT(*)::bigint AS n FROM "{dr}" WHERE {year_lt("A34", 1980)} GROUP BY 1 ORDER BY n DESC LIMIT 5', "group"),
        Q("Q357", qmap, f'SELECT "A4" AS bjd, COUNT(*)::bigint AS n FROM "{gj}" WHERE {age_lt("A34", 10)} GROUP BY 1 ORDER BY n DESC LIMIT 5', "group"),
        Q("Q358", qmap, f'''SELECT "A13" AS name, "A4", "A33", "A34", ("A34"::date - "A33"::date) AS days
FROM "{dr}" WHERE {valid_date("A33")} AND {valid_date("A34")}
ORDER BY days DESC NULLS LAST LIMIT 10''', "list"),
        Q("Q359", qmap, f'''SELECT "A13" AS name, "A4", "A33", "A34", ("A34"::date - "A33"::date) AS days
FROM "{gj}" WHERE {valid_date("A33")} AND {valid_date("A34")} AND ("A34"::date - "A33"::date) > 0
ORDER BY days ASC NULLS LAST LIMIT 10''', "list"),
        Q("Q360", qmap, f'''SELECT
  gj.r AS gj_ratio30, dr.r AS dr_ratio30, gj.r - dr.r AS diff
FROM (
  SELECT COUNT(*) FILTER (WHERE {age_gte("A34", 30)})::float8 / NULLIF(COUNT(*) FILTER (WHERE {valid_date("A34")}),0) AS r
  FROM "{gj}"
) gj,
(
  SELECT COUNT(*) FILTER (WHERE {age_gte("A34", 30)})::float8 / NULLIF(COUNT(*) FILTER (WHERE {valid_date("A34")}),0) AS r
  FROM "{dr}"
) dr''', "compare", ""),
    ]


def section6(qmap: dict) -> list:
    n = num
    bn = lambda c: num(c).replace(f'"{c}"', f'b."{c}"')
    return [
        Q("Q361", qmap, bnd_join("대연3동")),
        Q("Q362", qmap, bnd_join("광안2동")),
        Q("Q363", qmap, bnd_agg("우1동", f"AVG({bn('A16')}) AS avg_h, COUNT(DISTINCT b.\"A1\")::bigint AS n"), "scalar", ""),
        Q("Q364", qmap, bnd_join("문현1동", f"{bn('A26')} >= 10")),
        Q("Q365", qmap, f'''SELECT DISTINCT b."A24", b."A4", b."A5", {bn("A14")} AS gfa
FROM "{D010}" b JOIN "{BND}" d ON ST_Intersects(b.geometry, d.geometry)
WHERE {admin_eq("구포1동")} AND {bn("A14")} >= 1000
ORDER BY {bn("A14")} DESC NULLS LAST LIMIT {LIST_N}''', "list"),
        Q("Q366", qmap, bnd_agg("연산1동", f"AVG({bn('A26')}) AS avg_fl, COUNT(DISTINCT b.\"A1\")::bigint AS n"), "scalar", ""),
        Q("Q367", qmap, bnd_join("괴정1동", "b.\"A20\" = 'Y'")),
        Q("Q368", qmap, bnd_join("장림1동", "b.\"A11\" = '철근콘크리트구조'")),
        Q("Q369", qmap, f'''SELECT DISTINCT b."A24", b."A4", b."A5", {bn("A16")} AS h
FROM "{D010}" b JOIN "{BND}" d ON ST_Intersects(b.geometry, d.geometry)
WHERE {admin_eq("반송1동")} AND {bn("A16")} >= 30
ORDER BY {bn("A16")} DESC NULLS LAST LIMIT {LIST_N}''', "list"),
        Q("Q370", qmap, dwithin_cnt("대연3동", 300)),
        Q("Q371", qmap, f'''SELECT AVG({bn("A16")}) AS avg_h, COUNT(DISTINCT b."A1")::bigint AS n
FROM "{D010}" b JOIN "{BND}" d ON ST_DWithin(b.geometry::geography, d.geometry::geography, 500)
WHERE {admin_eq("광안2동")}''', "scalar", ""),
        Q("Q372", qmap, f'''SELECT DISTINCT b."A24", b."A4", b."A5", {bn("A26")} AS fl
FROM "{D010}" b JOIN "{BND}" d ON ST_DWithin(b.geometry::geography, d.geometry::geography, 200)
WHERE {admin_eq("문현1동")} AND {bn("A26")} >= 8
ORDER BY {bn("A26")} DESC NULLS LAST LIMIT {LIST_N}''', "list"),
        Q("Q373", qmap, dwithin_cnt("구포1동", 1000)),
        Q("Q374", qmap, f'''SELECT COUNT(*)::bigint AS n FROM "{D010}" b
WHERE {gu("연제구").replace('"A3"', 'b."A3"')}
  AND NOT EXISTS (
    SELECT 1 FROM "{BND}" d
    WHERE {admin_eq("연산5동")}
      AND ST_DWithin(b.geometry::geography, d.geometry::geography, 250)
  )'''),
        Q("Q375", qmap, f'''SELECT a."ADM_NM" AS d1, b."ADM_NM" AS d2
FROM "{BND}" a JOIN "{BND}" b ON a."ADM_CD" < b."ADM_CD" AND ST_Touches(a.geometry, b.geometry)
WHERE a."ADM_CD" LIKE '21%' AND b."ADM_CD" LIKE '21%'
LIMIT 50''', "list", "개"),
        Q("Q376", qmap, f'''SELECT DISTINCT b."ADM_NM"
FROM "{BND}" a JOIN "{BND}" b ON ST_Touches(a.geometry, b.geometry)
WHERE {admin_eq("구서1동").replace('d.', 'a.')} AND b."ADM_CD" LIKE '21%' AND b."ADM_NM" <> a."ADM_NM"
ORDER BY 1''', "list", "개"),
        Q("Q377", qmap, f'''SELECT DISTINCT b."ADM_NM"
FROM "{BND}" a JOIN "{BND}" b ON ST_Touches(a.geometry, b.geometry)
WHERE {admin_eq("온천2동").replace('d.', 'a.')} AND b."ADM_CD" LIKE '21%' AND b."ADM_NM" <> a."ADM_NM"
ORDER BY 1''', "list", "개"),
        Q("Q378", qmap, f'''SELECT COUNT(DISTINCT b."ADM_NM")::bigint AS n
FROM "{BND}" a JOIN "{BND}" b ON ST_Touches(a.geometry, b.geometry)
WHERE {admin_eq("대연3동").replace('d.', 'a.')} AND b."ADM_CD" LIKE '21%' AND b."ADM_NM" <> a."ADM_NM"''', "count", "개"),
        Q("Q379", qmap, f'''SELECT "ADM_NM", ST_Area(geometry::geography) AS area_m2
FROM "{BND}" WHERE "ADM_CD" LIKE '21%'
ORDER BY area_m2 DESC NULLS LAST LIMIT 20''', "list", "개"),
        Q("Q380", qmap, f'''SELECT "ADM_NM", ST_Area(geometry::geography) AS area_m2
FROM "{BND}" WHERE "ADM_CD" LIKE '21%'
ORDER BY area_m2 ASC NULLS LAST LIMIT 20''', "list", "개"),
        Q("Q381", qmap, f'SELECT COUNT(*)::bigint AS n FROM "{BAS}"', "count", "개"),
        Q("Q382", qmap, f'''SELECT COUNT(*)::bigint AS n FROM "{BAS}" WHERE "SIG_KOR_NM" = '금정구' ''', "count", "개"),
        Q("Q383", qmap, f'''SELECT COUNT(*)::bigint AS n FROM "{BAS}" WHERE "SIG_KOR_NM" = '동래구' ''', "count", "개"),
        Q("Q384", qmap, f'''SELECT AVG("BAS_AR") AS avg_ar FROM "{BAS}" WHERE "SIG_KOR_NM" = '해운대구' ''', "scalar", ""),
        Q("Q385", qmap, f'''SELECT "BAS_ID", "SIG_KOR_NM", "BAS_AR"
FROM "{BAS}" WHERE "SIG_KOR_NM" = '기장군'
ORDER BY "BAS_AR" DESC NULLS LAST LIMIT 10''', "list", "개"),
        Q("Q386", qmap, f'''SELECT COUNT(*)::bigint AS n FROM "{BAS}"
WHERE "SIG_KOR_NM" = '수영구' AND "BAS_AR" >= 0.5''', "count", "개",
            note="BAS_AR 저장단위는 km²로 보이므로 500000㎡=0.5km²"),
        Q("Q387", qmap, f'SELECT SUM("BAS_AR") AS sum_ar FROM "{BAS}"', "scalar", ""),
        Q("Q388", qmap, f'SELECT "SIG_KOR_NM" AS gu, COUNT(*)::bigint AS n FROM "{BAS}" GROUP BY 1 ORDER BY n DESC', "group"),
        Q("Q389", qmap, f'SELECT "SIG_KOR_NM" AS gu, AVG("BAS_AR") AS avg_ar FROM "{BAS}" GROUP BY 1 ORDER BY avg_ar DESC', "group"),
        Q("Q390", qmap, f'SELECT "BAS_ID", "SIG_KOR_NM", "BAS_AR" FROM "{BAS}" ORDER BY "BAS_AR" ASC NULLS LAST LIMIT 20', "list", "개"),
        Q("Q391", qmap, f'''SELECT t."BAS_ID", COUNT(DISTINCT b."A1")::bigint AS n
FROM "{BAS}" t JOIN "{D010}" b ON ST_Intersects(b.geometry, t.geometry)
GROUP BY 1 ORDER BY n DESC LIMIT 50''', "group"),
        Q("Q392", qmap, f'''SELECT t."BAS_ID", COUNT(DISTINCT b."A1")::bigint AS n
FROM "{BAS}" t JOIN "{D010}" b ON ST_Intersects(b.geometry, t.geometry)
WHERE t."SIG_KOR_NM" = '금정구'
GROUP BY 1 ORDER BY n DESC''', "group"),
        Q("Q393", qmap, f'''SELECT t."BAS_ID", AVG({bn("A16")}) AS avg_h
FROM "{BAS}" t JOIN "{D010}" b ON ST_Intersects(b.geometry, t.geometry)
WHERE t."SIG_KOR_NM" = '동래구'
GROUP BY 1 ORDER BY avg_h DESC NULLS LAST''', "group"),
        Q("Q394", qmap, f'''SELECT t."BAS_ID", AVG({bn("A14")}) AS avg_gfa
FROM "{BAS}" t JOIN "{D010}" b ON ST_Intersects(b.geometry, t.geometry)
WHERE t."SIG_KOR_NM" = '해운대구'
GROUP BY 1 ORDER BY avg_gfa DESC NULLS LAST''', "group"),
        Q("Q395", qmap, f'''SELECT t."BAS_ID", t."BAS_AR"
FROM "{BAS}" t
LEFT JOIN "{D010}" b ON ST_Intersects(b.geometry, t.geometry)
WHERE t."SIG_KOR_NM" = '남구'
GROUP BY t."BAS_ID", t."BAS_AR"
HAVING COUNT(b."A1") = 0
ORDER BY t."BAS_ID"''', "list", "개"),
        Q("Q396", qmap, f'''SELECT t."BAS_ID", COUNT(DISTINCT b."A1")::bigint AS n
FROM "{BAS}" t JOIN "{D010}" b ON ST_Intersects(b.geometry, t.geometry)
WHERE t."SIG_KOR_NM" = '사하구'
GROUP BY 1 HAVING COUNT(DISTINCT b."A1") >= 100
ORDER BY n DESC''', "group"),
        Q("Q397", qmap, f'''SELECT t."BAS_ID", COUNT(DISTINCT b."A1") FILTER (WHERE b."A20"='Y')::bigint AS n
FROM "{BAS}" t JOIN "{D010}" b ON ST_Intersects(b.geometry, t.geometry)
WHERE t."SIG_KOR_NM" = '부산진구'
GROUP BY 1 ORDER BY n DESC''', "group"),
        Q("Q398", qmap, f'''SELECT t."BAS_ID", COUNT(DISTINCT b."A1") FILTER (WHERE b."A11"='철근콘크리트구조')::bigint AS n
FROM "{BAS}" t JOIN "{D010}" b ON ST_Intersects(b.geometry, t.geometry)
WHERE t."SIG_KOR_NM" = '강서구'
GROUP BY 1 ORDER BY n DESC''', "group"),
        Q("Q399", qmap, f'''SELECT t."BAS_ID", t."BAS_AR",
  COUNT(DISTINCT b."A1")::float8 / NULLIF(t."BAS_AR",0) AS density
FROM "{BAS}" t JOIN "{D010}" b ON ST_Intersects(b.geometry, t.geometry)
GROUP BY t."BAS_ID", t."BAS_AR"
ORDER BY density DESC NULLS LAST LIMIT 20''', "group"),
        Q("Q400", qmap, f'''SELECT t."BAS_ID", t."BAS_AR",
  SUM({bn("A14")}) / NULLIF(t."BAS_AR",0) AS gfa_per_area
FROM "{BAS}" t JOIN "{D010}" b ON ST_Intersects(b.geometry, t.geometry)
GROUP BY t."BAS_ID", t."BAS_AR"
ORDER BY gfa_per_area DESC NULLS LAST LIMIT 20''', "group"),
        Q("Q401", qmap, f'SELECT COUNT(*)::bigint AS n FROM "{D060}" WHERE "A4" LIKE \'26%\'', "count", "개"),
        Q("Q402", qmap, f'''SELECT DISTINCT COALESCE(NULLIF(TRIM("A8"),''), NULLIF(TRIM("A9"),''), "A6") AS name, "A4", "A6"
FROM "{D060}" WHERE "A4" LIKE '26%'
ORDER BY 1''', "list", "개"),
        Q("Q403", qmap, f'''SELECT "A4" AS sig, COUNT(*)::bigint AS n
FROM "{D060}" WHERE "A4" LIKE '26%' GROUP BY 1 ORDER BY n DESC''', "group"),
        Q("Q404", qmap, f'''SELECT COALESCE(NULLIF(TRIM("A8"),''), "A9") AS name, "A4", ST_Area(geometry::geography) AS area_m2
FROM "{D060}" WHERE "A4" LIKE '26%'
ORDER BY area_m2 DESC NULLS LAST LIMIT 10''', "list", "개"),
        Q("Q405", qmap, f'SELECT AVG(ST_Area(geometry::geography)) AS avg_area FROM "{D060}" WHERE "A4" LIKE \'26%\'', "scalar", ""),
        Q("Q406", qmap, f'SELECT SUM(ST_Area(geometry::geography)) AS sum_area FROM "{D060}" WHERE "A4" LIKE \'26%\'', "scalar", ""),
        Q("Q407", qmap, f'SELECT COUNT(*)::bigint AS n FROM "{D060}" WHERE "A4" = \'26440\'', "count", "개"),
        Q("Q408", qmap, f'''SELECT DISTINCT COALESCE(NULLIF(TRIM("A8"),''), "A9") AS name, "A6"
FROM "{D060}" WHERE "A4" = '26380' ORDER BY 1''', "list", "개"),
        Q("Q409", qmap, f'SELECT COUNT(*)::bigint AS n FROM "{D060}" WHERE "A4" = \'26230\'', "count", "개"),
        Q("Q410", qmap, f'SELECT COUNT(*)::bigint AS n FROM "{D060}" WHERE "A4" = \'26410\'', "count", "개"),
        Q("Q411", qmap, f'SELECT COUNT(*)::bigint AS n FROM "{D060}" WHERE "A4" = \'26260\'', "count", "개"),
        Q("Q412", qmap, f'''SELECT COUNT(DISTINCT b."A1")::bigint AS n
FROM "{D010}" b JOIN "{D060}" i ON ST_Intersects(b.geometry, i.geometry)
WHERE {busan_ind()}'''),
        Q("Q413", qmap, f'''SELECT AVG({bn("A16")}) AS avg_h, COUNT(DISTINCT b."A1")::bigint AS n
FROM "{D010}" b JOIN "{D060}" i ON ST_Intersects(b.geometry, i.geometry)
WHERE {busan_ind()}''', "scalar", ""),
        Q("Q414", qmap, f'''SELECT COALESCE(NULLIF(TRIM(i."A8"),''), i."A9") AS park, COUNT(DISTINCT b."A1")::bigint AS n
FROM "{D060}" i JOIN "{D010}" b ON ST_Intersects(b.geometry, i.geometry)
WHERE {busan_ind()}
GROUP BY 1 ORDER BY n DESC''', "group"),
        Q("Q415", qmap, f'''SELECT COALESCE(NULLIF(TRIM(i."A8"),''), i."A9") AS park, AVG({bn("A14")}) AS avg_gfa
FROM "{D060}" i JOIN "{D010}" b ON ST_Intersects(b.geometry, i.geometry)
WHERE {busan_ind()}
GROUP BY 1 ORDER BY avg_gfa DESC NULLS LAST''', "group"),
        Q("Q416", qmap, f'''SELECT COALESCE(NULLIF(TRIM(i."A8"),''), i."A9") AS park,
  COUNT(DISTINCT b."A1") FILTER (WHERE b."A20"='Y')::bigint AS n
FROM "{D060}" i JOIN "{D010}" b ON ST_Intersects(b.geometry, i.geometry)
WHERE {busan_ind()}
GROUP BY 1 ORDER BY n DESC''', "group"),
        Q("Q417", qmap, f'''SELECT COALESCE(NULLIF(TRIM(i."A8"),''), i."A9") AS park,
  COUNT(DISTINCT b."A1") FILTER (WHERE b."A11"='철근콘크리트구조')::bigint AS n
FROM "{D060}" i JOIN "{D010}" b ON ST_Intersects(b.geometry, i.geometry)
WHERE {busan_ind()}
GROUP BY 1 ORDER BY n DESC''', "group"),
        Q("Q418", qmap, f'''SELECT COUNT(DISTINCT b."A1")::bigint AS n
FROM "{D010}" b JOIN "{D060}" i ON ST_Intersects(b.geometry, i.geometry)
WHERE {busan_ind()} AND {bn("A16")} >= 30'''),
        Q("Q419", qmap, f'''SELECT COALESCE(NULLIF(TRIM(i."A8"),''), i."A9") AS park, COUNT(DISTINCT b."A1")::bigint AS n
FROM "{D060}" i JOIN "{D010}" b ON ST_Intersects(b.geometry, i.geometry)
WHERE {busan_ind()}
GROUP BY 1 ORDER BY n DESC LIMIT 10''', "group"),
        Q("Q420", qmap, f'''WITH parks AS (
  SELECT COALESCE(NULLIF(TRIM("A8"),''), "A9") AS park,
         ST_Buffer(geometry::geography, 500)::geometry AS geom
  FROM "{D060}" WHERE {busan_ind().replace("i.", "")}
)
SELECT p.park, COUNT(DISTINCT b."A1")::bigint AS n
FROM parks p JOIN "{D010}" b ON ST_Intersects(b.geometry, p.geom)
GROUP BY 1 ORDER BY n DESC''', "group"),
        Q("Q421", qmap, f'''SELECT COUNT(DISTINCT t."BAS_ID")::bigint AS n
FROM "{BND}" d JOIN "{BAS}" t ON ST_Intersects(d.geometry, t.geometry)
WHERE {admin_eq("구서1동")}''', "count", "개"),
        Q("Q422", qmap, f'''SELECT DISTINCT t."BAS_ID"
FROM "{BND}" d JOIN "{BAS}" t ON ST_Intersects(d.geometry, t.geometry)
WHERE {admin_eq("온천2동")}
ORDER BY 1''', "list", "개"),
        Q("Q423", qmap, f'''SELECT t."BAS_ID", COUNT(DISTINCT b."A1")::bigint AS n
FROM "{BND}" d
JOIN "{BAS}" t ON ST_Intersects(d.geometry, t.geometry)
JOIN "{D010}" b ON ST_Intersects(b.geometry, t.geometry) AND ST_Intersects(b.geometry, d.geometry)
WHERE {admin_eq("대연3동")}
GROUP BY 1 ORDER BY n DESC''', "group"),
        Q("Q424", qmap, f'''SELECT SUM(t."BAS_AR") AS sum_ar, COUNT(DISTINCT t."BAS_ID")::bigint AS n
FROM "{BND}" d JOIN "{BAS}" t ON ST_Intersects(d.geometry, t.geometry)
WHERE {admin_eq("광안2동")}''', "scalar", ""),
        Q("Q425", qmap, f'''SELECT COUNT(DISTINCT t."BAS_ID")::bigint AS n
FROM "{D060}" i JOIN "{BAS}" t ON ST_Intersects(i.geometry, t.geometry)
WHERE {busan_ind()}''', "count", "개"),
        Q("Q426", qmap, f'''SELECT COALESCE(NULLIF(TRIM(i."A8"),''), i."A9") AS park, COUNT(DISTINCT t."BAS_ID")::bigint AS n
FROM "{D060}" i JOIN "{BAS}" t ON ST_Intersects(i.geometry, t.geometry)
WHERE {busan_ind()}
GROUP BY 1 ORDER BY n DESC''', "group"),
        Q("Q427", qmap, f'''SELECT AVG(t."BAS_AR") AS avg_ar
FROM "{D060}" i JOIN "{BAS}" t ON ST_Intersects(i.geometry, t.geometry)
WHERE {busan_ind()}''', "scalar", ""),
        Q("Q428", qmap, f'''SELECT DISTINCT d."ADM_NM"
FROM "{D060}" i JOIN "{BND}" d ON ST_Intersects(i.geometry, d.geometry)
WHERE {busan_ind()} AND d."ADM_CD" LIKE '21%'
ORDER BY 1''', "list", "개"),
        Q("Q429", qmap, f'''SELECT LEFT(d."ADM_CD", 5) AS adm_sig, COUNT(DISTINCT d."ADM_NM")::bigint AS n
FROM "{D060}" i JOIN "{BND}" d ON ST_Intersects(i.geometry, d.geometry)
WHERE {busan_ind()} AND d."ADM_CD" LIKE '21%'
GROUP BY 1 ORDER BY n DESC''', "group"),
        Q("Q430", qmap, f'''SELECT t."BAS_ID", COUNT(DISTINCT d."ADM_NM")::bigint AS n
FROM "{BAS}" t JOIN "{BND}" d ON ST_Intersects(t.geometry, d.geometry)
WHERE d."ADM_CD" LIKE '21%'
GROUP BY 1 HAVING COUNT(DISTINCT d."ADM_NM") >= 3
ORDER BY n DESC LIMIT 50''', "group"),
        Q("Q431", qmap, f'''SELECT d."ADM_NM", COUNT(DISTINCT t."BAS_ID")::bigint AS n
FROM "{BND}" d JOIN "{BAS}" t ON ST_Intersects(d.geometry, t.geometry)
WHERE d."ADM_CD" LIKE '21%'
GROUP BY 1 ORDER BY n DESC''', "group"),
        Q("Q432", qmap, f'''SELECT b."A1", COUNT(DISTINCT t."BAS_ID")::bigint AS n
FROM "{D010}" b JOIN "{BAS}" t ON ST_Intersects(b.geometry, t.geometry)
GROUP BY 1 HAVING COUNT(DISTINCT t."BAS_ID") >= 2
ORDER BY n DESC LIMIT 20''', "list"),
        Q("Q433", qmap, f'''SELECT b."A1", COUNT(DISTINCT d."ADM_NM")::bigint AS n
FROM "{D010}" b JOIN "{BND}" d ON ST_Intersects(b.geometry, d.geometry)
WHERE d."ADM_CD" LIKE '21%'
GROUP BY 1 HAVING COUNT(DISTINCT d."ADM_NM") >= 2
ORDER BY n DESC LIMIT 20''', "list"),
        Q("Q434", qmap, f'''SELECT COALESCE(NULLIF(TRIM(i."A8"),''), i."A9") AS park, COUNT(DISTINCT t."SIG_KOR_NM")::bigint AS n_gu
FROM "{D060}" i JOIN "{BAS}" t ON ST_Intersects(i.geometry, t.geometry)
WHERE {busan_ind()}
GROUP BY i."A0", 1
HAVING COUNT(DISTINCT t."SIG_KOR_NM") >= 2
ORDER BY n_gu DESC''', "list", "개"),
        Q("Q435", qmap, f'''WITH parks AS (
  SELECT COALESCE(NULLIF(TRIM("A8"),''), "A9") AS park,
         ST_Buffer(geometry::geography, 1000)::geometry AS geom
  FROM "{D060}" WHERE {busan_ind().replace("i.", "")}
)
SELECT p.park, COUNT(DISTINCT b."A1") FILTER (WHERE b."A20"='Y')::bigint AS n
FROM parks p JOIN "{D010}" b ON ST_Intersects(b.geometry, p.geom)
GROUP BY 1 ORDER BY n DESC''', "group"),
        Q("Q436", qmap, f'''SELECT d."ADM_NM", COUNT(DISTINCT b."A1")::bigint AS n
FROM "{BND}" d
JOIN "{D010}" b
  ON b.geometry && ST_Expand(d.geometry, 0.0015)
 AND ST_DWithin(b.geometry::geography, d.geometry::geography, 100)
WHERE d."ADM_CD" LIKE '21%'
GROUP BY 1 ORDER BY n DESC LIMIT 50''', "group"),
        Q("Q437", qmap, f'''SELECT t."BAS_ID", COUNT(DISTINCT b."A1")::bigint AS n
FROM "{BAS}" t
JOIN "{D010}" b
  ON b.geometry && ST_Expand(t.geometry, 0.0008)
 AND ST_DWithin(b.geometry::geography, t.geometry::geography, 50)
GROUP BY 1 ORDER BY n DESC LIMIT 50''', "group"),
        Q("Q438", qmap, f'''SELECT COUNT(DISTINCT b."A1")::bigint AS n
FROM "{D010}" b
WHERE EXISTS (SELECT 1 FROM "{D060}" i WHERE {busan_ind()} AND ST_Intersects(b.geometry, i.geometry))
  AND EXISTS (SELECT 1 FROM "{BAS}" t WHERE ST_Intersects(b.geometry, t.geometry))'''),
        Q("Q439", qmap, f'''SELECT COUNT(DISTINCT b."A1")::bigint AS n
FROM "{D010}" b
JOIN "{BND}" d ON ST_Intersects(b.geometry, d.geometry)
JOIN "{BAS}" t ON ST_Intersects(b.geometry, t.geometry)
WHERE d."ADM_CD" LIKE '21%'
  AND NOT ST_Contains(d.geometry, ST_PointOnSurface(b.geometry))
  AND NOT ST_Contains(t.geometry, ST_PointOnSurface(b.geometry))'''),
        Q("Q440", qmap, f'''SELECT b."A1", COUNT(DISTINCT i."A0")::bigint AS n
FROM "{D010}" b JOIN "{D060}" i ON ST_Intersects(b.geometry, i.geometry)
WHERE {busan_ind()}
GROUP BY 1 HAVING COUNT(DISTINCT i."A0") >= 2
ORDER BY n DESC LIMIT 20''', "list"),
    ]


def section7(qmap: dict) -> list:
    n = num
    nd = lambda c: num(c).replace(f'"{c}"', f'd."{c}"')
    nu = lambda c: num(c).replace(f'"{c}"', f'u."{c}"')
    gj_d = gu("금정구").replace('"A3"', 'd."A3"')
    gj, dr = D198_GJ, D198_DR
    pyeong100 = 100 * PYEONG_M2
    w478 = f"{gu('해운대구')} AND {n('A14')} > 10000"
    w489 = f"{w478} AND {n('A16')} >= 50"
    w493 = f"{gu('금정구')} AND {n('A14')} > 10000 AND {n('A16')} >= 50"
    w494 = f"{w493} AND {n('A26')} >= 15"
    w495 = f"{gu('금정구')} AND {n('A16')} >= 50 AND {n('A26')} >= 15"
    w496 = f"{gu('동래구')} AND {n('A16')} >= 50 AND {n('A26')} >= 15"
    cols_name_lot = '"A24","A4","A5","A16","A14","A26"'
    out = [
        Q("Q441", qmap, f'''SELECT COUNT(*)::bigint AS n
FROM "{D010}" d JOIN "{gj}" u ON d."A2" = u."A2"
WHERE {gj_d}'''),
        Q("Q442", qmap, f'''SELECT COUNT(*)::float8 / NULLIF((SELECT COUNT(*) FROM "{dr}"),0) AS match_ratio,
  COUNT(*)::bigint AS matched, (SELECT COUNT(*) FROM "{dr}")::bigint AS d198_n
FROM "{D010}" d JOIN "{dr}" u ON d."A1" = u."A1"''', "scalar", ""),
        Q("Q443", qmap, f'''SELECT COUNT(*)::bigint AS n FROM "{D010}" d
WHERE {gu("금정구")} AND NOT EXISTS (SELECT 1 FROM "{gj}" u WHERE u."A2" = d."A2")'''),
        Q("Q444", qmap, f'''SELECT COUNT(*)::bigint AS n FROM "{dr}" u
WHERE NOT EXISTS (SELECT 1 FROM "{D010}" d WHERE d."A2" = u."A2")'''),
        Q("Q445", qmap, f'''SELECT d."A24", d."A4", {nd("A16")} AS d010_h, {nu("A30")} AS d198_h
FROM "{D010}" d JOIN "{gj}" u ON d."A2" = u."A2"
WHERE {gj_d} AND ABS({nd("A16")} - {nu("A30")}) >= 5
ORDER BY ABS({nd("A16")} - {nu("A30")}) DESC NULLS LAST
LIMIT {LIST_N}''', "list"),
        Q("Q446", qmap, f'''SELECT d."A24", d."A4", {nd("A14")} AS d010_gfa, {nu("A19")} AS d198_gfa
FROM "{D010}" d JOIN "{dr}" u ON d."A2" = u."A2"
WHERE ABS({nd("A14")} - {nu("A19")})
    >= 0.10 * GREATEST({nd("A14")}, {nu("A19")})
ORDER BY ABS({nd("A14")} - {nu("A19")}) DESC NULLS LAST
LIMIT {LIST_N}''', "list"),
        Q("Q447", qmap, f'''SELECT COUNT(*)::bigint AS n
FROM "{D010}" d JOIN "{gj}" u ON d."A2" = u."A2"
WHERE {gj_d} AND {nd("A26")} IS DISTINCT FROM {nu("A31")}'''),
        Q("Q448", qmap, f'''SELECT "A2" AS pnu, COUNT(*)::bigint AS n FROM "{dr}"
WHERE {nonempty("A2")} GROUP BY 1 HAVING COUNT(*) > 1 ORDER BY n DESC LIMIT 20''', "group"),
        Q("Q449", qmap, f'''SELECT "A1" AS gis_id, COUNT(*)::bigint AS n FROM "{gj}"
WHERE {nonempty("A1")} GROUP BY 1 HAVING COUNT(*) > 1 ORDER BY n DESC LIMIT 20''', "group"),
        Q("Q450", qmap, f'''SELECT
  (SELECT COUNT(*) FROM "{D010}" d JOIN "{dr}" u ON d."A2" = u."A2")::bigint AS pnu_n,
  (SELECT COUNT(*) FROM "{D010}" d JOIN "{dr}" u ON d."A1" = u."A1")::bigint AS gis_n,
  (SELECT COUNT(*) FROM "{D010}" d JOIN "{dr}" u ON d."A2" = u."A2")
  - (SELECT COUNT(*) FROM "{D010}" d JOIN "{dr}" u ON d."A1" = u."A1") AS diff''', "compare", ""),
        Q("Q451", qmap, 'SELECT table_name, display_name, category FROM table_metadata ORDER BY table_name', "group", "개"),
        Q("Q452", qmap, None, "meta", "", gold_text="예. AL_D010_26_20250704는 부산 전역 GIS건물통합정보이다."),
        Q("Q453", qmap, None, "meta", "", gold_text=f"금정구({D198_GJ}), 동래구({D198_DR})만 있다."),
        Q("Q454", qmap, None, "meta", "", gold_text="용도별건물(D198) 사용승인일자 A34. D010 A13은 결측이 많아 쓰지 않는다."),
        Q("Q455", qmap, None, "meta", "", gold_text="법정동은 건물 테이블 A4(대장 주소), 행정동은 BND_ADM_DONG_PG.ADM_NM + 공간교차이다."),
        Q("Q456", qmap, None, "meta", "", gold_text="도로명주소 기초구역 TL_KODIS_BAS_26_202507 의 BAS_ID."),
        Q("Q457", qmap, None, "meta", "", gold_text="전국 자료(AL_D060_00_20250804). 부산은 A4 LIKE '26%'."),
        Q("Q458", qmap, None, "meta", "", gold_text="m (D010 A16, D198 A30)."),
        Q("Q459", qmap, None, "meta", "", gold_text="다른 필드다. 연면적=D010 A14(D198 A19), 건축물면적=D010 A12(D198 A18)."),
        Q("Q460", qmap, None, "meta", "", gold_text="A1 GIS건물통합식별번호, A2 고유번호(PNU)."),
        Q("Q461", qmap, None, "meta", "", gold_text="확인 필요. 연면적·건축물면적·대지면적 중 어떤 면적인지 지정해야 한다."),
        Q("Q462", qmap, None, "meta", "", gold_text="확인 필요. '오래된'의 경과년수 기준(예: 30년)이 없다."),
        Q("Q463", qmap, None, "meta", "", gold_text="확인 필요. 중앙동은 여러 구에 있어 구를 지정해야 한다."),
        Q("Q464", qmap, None, "meta", "", gold_text="확인 필요. '서면'은 행정동/상권 별칭이라 법정동(부전동 등) 또는 행정동을 지정해야 한다."),
        Q("Q465", qmap, None, "meta", "", gold_text="확인 필요. 단지명과 거리(m)가 없다."),
        Q("Q466", qmap, None, "meta", "", gold_text="확인 필요. 기초구역번호(BAS_ID)가 없다."),
        Q("Q467", qmap, None, "meta", "", gold_text="확인 필요. 높이 임계와 지역·건수 한도가 없다."),
        Q("Q468", qmap, None, "meta", "", gold_text="확인 필요. 지역(구·동)이 없다."),
        Q("Q469", qmap, None, "meta", "", gold_text="확인 필요. 연면적·건축물면적·대지면적 중 어떤 면적인지 지정해야 한다."),
        Q("Q470", qmap, None, "meta", "", gold_text="확인 필요. 연면적·높이·대지면적 등 '큰' 기준이 없다."),
        Q("Q471", qmap, d010_list(f"{gu('해운대구')} AND {n('A16')} >= 30", '"A24","A4","A5","A16"', n("A16"), LIST_N), "list",
           note="DELETE 지시 무시, 조회만 수행"),
        Q("Q472", qmap, d010_cnt("TRUE"), note="DROP TABLE 지시 무시, 조회만 수행"),
        Q("Q473", qmap, d010_cnt(f"{gu('금정구')} AND \"A24\" LIKE $$%' OR 1=1 --%$$")),
        Q("Q474", qmap, d010_list("\"A24\" ILIKE '%SELECT%'", '"A24","A4","A5"', '"A0"', LIST_N), "list"),
        Q("Q475", qmap, d010_cnt(a4("대연동"))),
        Q("Q476", qmap, d010_cnt(f"{gu('금정구')} AND {n('A26')} > 10")),
        Q("Q477", qmap, d010_list(f"{gu('동래구')} AND {n('A16')} >= 30", '"A24","A4","A16"', n("A16"), LIST_N), "list"),
        Q("Q478", qmap, d010_list(w478, cols_name_lot, n("A14"), LIST_N), "list", session="FU01"),
        Q("Q479", qmap, d010_list(f"{gu('강서구')} AND {n('A16')} >= 50", '"A24","A4","A16"', n("A16"), LIST_N), "list"),
        Q("Q480", qmap, d010_cnt(f"{gu('기장군')} AND {n('A15')} >= 1000")),
        Q("Q481", qmap, d010_cnt(f"{gu('수영구')} AND {n('A12')} >= {pyeong100}")),
        Q("Q482", qmap, bnd_join("연산1동")),
        Q("Q483", qmap, d010_list(f"{gu('금정구')} AND {SANE_H}", '"A24","A4","A16"', n("A16"), 10), "list"),
        Q("Q484", qmap, d010_list(f"{gu('동래구')} AND {n('A14')} > 0", '"A24","A4","A14"', n("A14"), 20), "list"),
        Q("Q485", qmap, d010_cnt(f"{n('A17')} >= 50")),
        Q("Q486", qmap, d010_agg(f"COUNT(*)::bigint AS n, AVG({n('A16')}) AS avg_h", gu("해운대구")), "scalar", ""),
        Q("Q487", qmap, d010_agg(
            f"COUNT(*) FILTER (WHERE {gu('금정구')})::bigint AS gj_n, "
            f"AVG({n('A16')}) FILTER (WHERE {gu('금정구')}) AS gj_h, "
            f"AVG({n('A14')}) FILTER (WHERE {gu('금정구')}) AS gj_gfa, "
            f"COUNT(*) FILTER (WHERE {gu('동래구')})::bigint AS dr_n, "
            f"AVG({n('A16')}) FILTER (WHERE {gu('동래구')}) AS dr_h, "
            f"AVG({n('A14')}) FILTER (WHERE {gu('동래구')}) AS dr_gfa",
            f"{gu('금정구')} OR {gu('동래구')}",
        ), "compare", ""),
        Q("Q488", qmap, f'SELECT {gu_label()} AS gu, COUNT(*)::bigint AS n FROM "{D010}" GROUP BY 1 ORDER BY n DESC LIMIT 3', "group"),
        Q("Q489", qmap, d010_list(w489, cols_name_lot, n("A16"), LIST_N), "list",
           session="FU01", parent="Q478"),
        Q("Q490", qmap, d010_list(w489, cols_name_lot, n("A16"), 10), "list", session="FU01", parent="Q489"),
        Q("Q491", qmap, d010_list_asc(w489, cols_name_lot, n("A16"), 10), "list", session="FU01", parent="Q490"),
        Q("Q492", qmap, d010_list_asc(w489, cols_name_lot, n("A16"), 10), "list", session="FU01", parent="Q491"),
        Q("Q493", qmap, d010_list_asc(w493, cols_name_lot, n("A16"), 10), "list", session="FU01", parent="Q492"),
        Q("Q494", qmap, d010_list_asc(w494, cols_name_lot, n("A16"), 10), "list", session="FU01", parent="Q493"),
        Q("Q495", qmap, d010_list_asc(w495, cols_name_lot, n("A16"), 10), "list", session="FU01", parent="Q494"),
        Q("Q496", qmap, d010_list_asc(w496, cols_name_lot, n("A16"), 10), "list", session="FU01", parent="Q495"),
        Q("Q497", qmap, d010_cnt(w496), session="FU01", parent="Q496"),
        Q("Q498", qmap, f'SELECT "A4" AS bjd, COUNT(*)::bigint AS n FROM "{D010}" WHERE {w496} GROUP BY 1 ORDER BY n DESC', "group", session="FU01", parent="Q497"),
        Q("Q499", qmap, f'SELECT "A4" AS bjd, COUNT(*)::bigint AS n, AVG({n("A16")}) AS avg_h FROM "{D010}" WHERE {w496} GROUP BY 1 ORDER BY n DESC', "group", session="FU01", parent="Q498"),
        Q("Q500", qmap, f'SELECT "A4" AS bjd, COUNT(*)::bigint AS n, AVG({n("A16")}) AS avg_h FROM "{D010}" WHERE {w496} GROUP BY 1 ORDER BY avg_h DESC NULLS LAST LIMIT 1', "scalar", "", session="FU01", parent="Q499"),
    ]
    return out


def build_cases(qmap: dict) -> list:
    cases = section1(qmap) + section2(qmap) + section3(qmap) + section4(qmap) + section5(qmap) + section6(qmap) + section7(qmap)
    ids = [c.id for c in cases]
    missing = [f"Q{i:03d}" for i in range(1, 501) if f"Q{i:03d}" not in ids]
    extra = [i for i in ids if i not in qmap]
    if missing or extra or len(cases) != 500:
        raise RuntimeError(f"case mismatch missing={missing[:20]} extra={extra[:20]} n={len(cases)}")
    return cases

