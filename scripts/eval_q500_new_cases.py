"""신규 400문항: DB 속성 결합·논리연산·공간교차·D198전용·다턴 후속.

기존 NL100의 단순 장소건수/단일용도/단일임계 패턴을 반복하지 않는다.
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


def ba4(dong: str) -> str:
    return a4(dong).replace('"A4"', 'b."A4"')


def bgu(name: str) -> str:
    return gu(name).replace('"A3"', 'b."A3"').replace('"A4"', 'b."A4"')


def bnum(col: str) -> str:
    return num(col).replace(f'"{col}"', f'b."{col}"')


def industrial_exists(alias: str = "b") -> str:
    return (
        f'EXISTS (SELECT 1 FROM "{D060}" i WHERE ST_Intersects({alias}.geometry, i.geometry))'
    )


def named_industrial(name: str, alias: str = "b") -> str:
    s = name.replace("'", "''")
    return (
        f"EXISTS (SELECT 1 FROM \"{D060}\" i "
        f"WHERE (i.\"A8\" ILIKE '%{s}%' OR i.\"A9\" ILIKE '%{s}%') "
        f"AND ST_Intersects({alias}.geometry, i.geometry))"
    )


def compound_and() -> list:
    """용도+구조+수치+연도를 한 질문에 겹침 (50)."""
    n = num
    return [
        C("Q101", "복합AND", "해운대구 아파트 중 철근콘크리트이고 높이 70m 이상·연면적 10000㎡ 이상인 건물은 몇 채야?",
          d010_cnt(f"{gu('해운대구')} AND \"A9\"='공동주택' AND {rc('A11','%철근콘크리트%')} AND {n('A16')}>=70 AND {n('A14')}>=10000")),
        C("Q102", "복합AND", "수영구 공동주택 중 지상 20층 이상이면서 높이 60m 이상인 건물 이름과 층수·높이",
          d010_list(f"{gu('수영구')} AND \"A9\"='공동주택' AND {n('A26')}>=20 AND {n('A16')}>=60", '"A24","A4","A26","A16","A14"', n("A16"), 20), "list"),
        C("Q103", "복합AND", "금정구에서 연면적 5000㎡ 이상이고 15층 이상인 철근콘크리트 공동주택 수",
          d010_cnt(f"{gu('금정구')} AND \"A9\"='공동주택' AND {rc('A11','%철근콘크리트%')} AND {n('A14')}>=5000 AND {n('A26')}>=15")),
        C("Q104", "복합AND", "사하구 창고시설 중 연면적 3000㎡ 이상이면서 건축면적 1000㎡ 이상인 채수",
          d010_cnt(f"{gu('사하구')} AND \"A9\"='창고시설' AND {n('A14')}>=3000 AND {n('A12')}>=1000")),
        C("Q105", "복합AND", "강서구 공장 중 일반철골구조이고 연면적 5000㎡ 이상인 건물명과 연면적",
          d010_list(f"{gu('강서구')} AND \"A9\"='공장' AND {rc('A11','%일반철골%')} AND {n('A14')}>=5000", '"A24","A4","A5","A11","A14"', n("A14"), 15), "list"),
        C("Q106", "복합AND", "부산진구 업무시설 중 높이 40m 이상이고 지상 10층 이상인 건물 수",
          d010_cnt(f"{gu('부산진구')} AND \"A9\"='업무시설' AND {n('A16')}>=40 AND {n('A26')}>=10")),
        C("Q107", "복합AND", "연제구 교육연구시설 중 대지면적 2000㎡ 이상이면서 높이 20m 이상인 이름과 대지면적",
          d010_list(f"{gu('연제구')} AND \"A9\"='교육연구시설' AND {n('A15')}>=2000 AND {n('A16')}>=20", '"A24","A4","A15","A16"', n("A15"), 15), "list"),
        C("Q108", "복합AND", "남구 공동주택 중 2000년 이후 사용승인이고 지상 15층 이상인 채수",
          d010_cnt(f"{gu('남구')} AND \"A9\"='공동주택' AND {year_ge('A13', 2000)} AND {n('A26')}>=15")),
        C("Q109", "복합AND", "동래구 숙박시설 중 연면적 2000㎡ 이상이고 높이 25m 이상인 건물",
          d010_list(f"{gu('동래구')} AND \"A9\"='숙박시설' AND {n('A14')}>=2000 AND {n('A16')}>=25", '"A24","A4","A5","A14","A16"', n("A14"), 15), "list"),
        C("Q110", "복합AND", "기장군 단독주택 중 건축면적 200㎡ 이상이면서 벽돌구조인 채수",
          d010_cnt(f"{gu('기장군')} AND \"A9\"='단독주택' AND {n('A12')}>=200 AND {rc('A11','%벽돌%')}")),
        C("Q111", "복합AND", "우동 아파트 중 높이 80m 이상이고 연면적 8000㎡ 이상인 건물명·높이·연면적",
          d010_list(f"{a4('우동')} AND \"A9\"='공동주택' AND {n('A16')}>=80 AND {n('A14')}>=8000", '"A24","A4","A16","A14","A26"', n("A16"), 20), "list"),
        C("Q112", "복합AND", "광안동 숙박시설 중 지상 8층 이상이면서 연면적 1500㎡ 이상인 채수",
          d010_cnt(f"{a4('광안동')} AND \"A9\"='숙박시설' AND {n('A26')}>=8 AND {n('A14')}>=1500")),
        C("Q113", "복합AND", "장림동 공장 중 연면적 3000㎡ 이상이고 높이 15m 이상인 이름과 연면적",
          d010_list(f"{a4('장림동')} AND \"A9\"='공장' AND {n('A14')}>=3000 AND {n('A16')}>=15", '"A24","A4","A5","A14","A16"', n("A14"), 15), "list"),
        C("Q114", "복합AND", "대연동 공동주택 중 철근콘크리트이고 지상 12층 이상인 채수",
          d010_cnt(f"{a4('대연동')} AND \"A9\"='공동주택' AND {rc('A11','%철근콘크리트%')} AND {n('A26')}>=12")),
        C("Q115", "복합AND", "문현동 제2종근린생활시설 중 연면적 500㎡ 이상이면서 높이 12m 이상인 채수",
          d010_cnt(f"{a4('문현동')} AND \"A9\"='제2종근린생활시설' AND {n('A14')}>=500 AND {n('A16')}>=12")),
        C("Q116", "복합AND", "사상구 자동차관련시설 중 연면적 1000㎡ 이상이고 건축면적 400㎡ 이상인 채수",
          d010_cnt(f"{gu('사상구')} AND \"A9\"='자동차관련시설' AND {n('A14')}>=1000 AND {n('A12')}>=400")),
        C("Q117", "복합AND", "북구 종교시설 중 대지면적 1000㎡ 이상이면서 높이 15m 이상인 이름과 대지면적",
          d010_list(f"{gu('북구')} AND \"A9\"='종교시설' AND {n('A15')}>=1000 AND {n('A16')}>=15", '"A24","A4","A15","A16"', n("A15"), 15), "list"),
        C("Q118", "복합AND", "영도구 공동주택 중 1990년대 사용승인이고 지상 10층 이상인 채수",
          d010_cnt(f"{gu('영도구')} AND \"A9\"='공동주택' AND {year_between('A13', 1990, 1999)} AND {n('A26')}>=10")),
        C("Q119", "복합AND", "해운대구 판매시설 중 연면적 2000㎡ 이상이고 높이 20m 이상인 채수",
          d010_cnt(f"{gu('해운대구')} AND \"A9\"='판매시설' AND {n('A14')}>=2000 AND {n('A16')}>=20")),
        C("Q120", "복합AND", "금정구 교육연구시설 중 철근콘크리트이고 연면적 3000㎡ 이상인 이름과 연면적",
          d010_list(f"{gu('금정구')} AND \"A9\"='교육연구시설' AND {rc('A11','%철근콘크리트%')} AND {n('A14')}>=3000", '"A24","A4","A11","A14"', n("A14"), 15), "list"),
        C("Q121", "복합AND", "사하구 공동주택 중 높이 40m 이상·지상 12층 이상·연면적 4000㎡ 이상인 채수",
          d010_cnt(f"{gu('사하구')} AND \"A9\"='공동주택' AND {n('A16')}>=40 AND {n('A26')}>=12 AND {n('A14')}>=4000")),
        C("Q122", "복합AND", "중동 아파트 중 높이 100m 이상이면서 지상 30층 이상인 건물명과 높이·층수",
          d010_list(f"{a4('중동')} AND {gu('해운대구')} AND \"A9\"='공동주택' AND {n('A16')}>=100 AND {n('A26')}>=30", '"A24","A4","A16","A26","A14"', n("A16"), 15), "list"),
        C("Q123", "복합AND", "연산동 업무시설 중 연면적 1500㎡ 이상이고 높이 18m 이상인 채수",
          d010_cnt(f"{a4('연산동')} AND \"A9\"='업무시설' AND {n('A14')}>=1500 AND {n('A16')}>=18")),
        C("Q124", "복합AND", "구서동 공동주택 중 2000년 이후 사용승인·철근콘크리트·15층 이상인 채수",
          d010_cnt(f"{a4('구서동')} AND \"A9\"='공동주택' AND {year_ge('A13', 2000)} AND {rc('A11','%철근콘크리트%')} AND {n('A26')}>=15")),
        C("Q125", "복합AND", "괴정동 단독주택 중 건축면적 150㎡ 이상이면서 블록구조인 채수",
          d010_cnt(f"{a4('괴정동')} AND \"A9\"='단독주택' AND {n('A12')}>=150 AND {rc('A11','%블록%')}")),
        C("Q126", "복합AND", "온천동 공동주택 중 연면적 6000㎡ 이상이고 높이 45m 이상인 이름·연면적·높이",
          d010_list(f"{a4('온천동')} AND \"A9\"='공동주택' AND {n('A14')}>=6000 AND {n('A16')}>=45", '"A24","A4","A14","A16","A26"', n("A14"), 15), "list"),
        C("Q127", "복합AND", "센텀 쪽 우동 업무시설 중 높이 50m 이상이고 연면적 8000㎡ 이상인 채수",
          d010_cnt(f"{a4('우동')} AND \"A9\"='업무시설' AND {n('A16')}>=50 AND {n('A14')}>=8000")),
        C("Q128", "복합AND", "재송동 공동주택 중 지상 18층 이상이면서 연면적 7000㎡ 이상인 채수",
          d010_cnt(f"{a4('재송동')} AND \"A9\"='공동주택' AND {n('A26')}>=18 AND {n('A14')}>=7000")),
        C("Q129", "복합AND", "녹산동 공장 중 연면적 2000㎡ 이상이고 높이 12m 이상인 이름과 연면적",
          d010_list(f"{a4('녹산동')} AND \"A9\"='공장' AND {n('A14')}>=2000 AND {n('A16')}>=12", '"A24","A4","A14","A16"', n("A14"), 15), "list"),
        C("Q130", "복합AND", "정관읍 공동주택 중 높이 35m 이상이고 2000년 이후 사용승인인 채수",
          d010_cnt(f"(\"A4\" LIKE '%정관%' AND {gu('기장군')}) AND \"A9\"='공동주택' AND {n('A16')}>=35 AND {year_ge('A13', 2000)}")),
        C("Q131", "복합AND", "서면 근처 부전동 판매시설 중 연면적 1000㎡ 이상·높이 15m 이상인 채수",
          d010_cnt(f"{a4('부전동')} AND \"A9\"='판매시설' AND {n('A14')}>=1000 AND {n('A16')}>=15")),
        C("Q132", "복합AND", "전포동 제2종근린생활시설 중 연면적 400㎡ 이상이면서 지상 5층 이상인 채수",
          d010_cnt(f"{a4('전포동')} AND \"A9\"='제2종근린생활시설' AND {n('A14')}>=400 AND {n('A26')}>=5")),
        C("Q133", "복합AND", "다대동 공동주택 중 철근콘크리트이고 높이 40m 이상인 이름과 높이",
          d010_list(f"{a4('다대동')} AND \"A9\"='공동주택' AND {rc('A11','%철근콘크리트%')} AND {n('A16')}>=40", '"A24","A4","A16","A14"', n("A16"), 15), "list"),
        C("Q134", "복합AND", "용호동 교육연구시설 중 대지면적 3000㎡ 이상이고 연면적 2000㎡ 이상인 채수",
          d010_cnt(f"{a4('용호동')} AND \"A9\"='교육연구시설' AND {n('A15')}>=3000 AND {n('A14')}>=2000")),
        C("Q135", "복합AND", "민락동 숙박시설 중 연면적 800㎡ 이상이면서 높이 18m 이상인 채수",
          d010_cnt(f"{a4('민락동')} AND \"A9\"='숙박시설' AND {n('A14')}>=800 AND {n('A16')}>=18")),
        C("Q136", "복합AND", "사상구 공장 중 경량철골구조이고 연면적 1500㎡ 이상인 채수",
          d010_cnt(f"{gu('사상구')} AND \"A9\"='공장' AND {rc('A11','%경량철골%')} AND {n('A14')}>=1500")),
        C("Q137", "복합AND", "동구 공동주택 중 지어진지 20년 넘고 지상 10층 이상인 채수",
          d010_cnt(f"{gu('동구')} AND \"A9\"='공동주택' AND {age_gte('A13', 20)} AND {n('A26')}>=10")),
        C("Q138", "복합AND", "서구 의료시설 중 연면적 2000㎡ 이상이고 높이 20m 이상인 이름과 연면적",
          d010_list(f"{gu('서구')} AND \"A9\"='의료시설' AND {n('A14')}>=2000 AND {n('A16')}>=20", '"A24","A4","A14","A16"', n("A14"), 15), "list"),
        C("Q139", "복합AND", "중구 업무시설 중 지상 8층 이상이면서 연면적 2000㎡ 이상인 채수",
          d010_cnt(f"{gu('중구')} AND \"A9\"='업무시설' AND {n('A26')}>=8 AND {n('A14')}>=2000")),
        C("Q140", "복합AND", "반여동 공동주택 중 높이 50m 이상·연면적 5000㎡ 이상·철근콘크리트인 채수",
          d010_cnt(f"{a4('반여동')} AND \"A9\"='공동주택' AND {n('A16')}>=50 AND {n('A14')}>=5000 AND {rc('A11','%철근콘크리트%')}")),
        C("Q141", "복합AND", "구포동 공동주택 중 2000년 이후 사용승인이고 연면적 4000㎡ 이상인 채수",
          d010_cnt(f"{a4('구포동')} AND \"A9\"='공동주택' AND {year_ge('A13', 2000)} AND {n('A14')}>=4000")),
        C("Q142", "복합AND", "화명동 공동주택 중 지상 20층 이상이고 높이 55m 이상인 이름·층수·높이",
          d010_list(f"{a4('화명동')} AND \"A9\"='공동주택' AND {n('A26')}>=20 AND {n('A16')}>=55", '"A24","A4","A26","A16"', n("A26"), 15), "list"),
        C("Q143", "복합AND", "덕천동 제1종근린생활시설 중 연면적 300㎡ 이상이면서 높이 10m 이상인 채수",
          d010_cnt(f"{a4('덕천동')} AND \"A9\"='제1종근린생활시설' AND {n('A14')}>=300 AND {n('A16')}>=10")),
        C("Q144", "복합AND", "안락동 공동주택 중 지어진지 30년 넘고 연면적 2000㎡ 이상인 채수",
          d010_cnt(f"{a4('안락동')} AND \"A9\"='공동주택' AND {age_gte('A13', 30)} AND {n('A14')}>=2000")),
        C("Q145", "복합AND", "사직동 공동주택 중 대지면적 1000㎡ 이상이고 연면적 2000㎡ 이상인 채수",
          d010_cnt(f"{a4('사직동')} AND \"A9\"='공동주택' AND {n('A15')}>=1000 AND {n('A14')}>=2000")),
        C("Q146", "복합AND", "남산동 단독주택 중 목구조이고 건축면적 80㎡ 이상인 채수",
          d010_cnt(f"{a4('남산동')} AND \"A9\"='단독주택' AND {rc('A11','%목%')} AND {n('A12')}>=80")),
        C("Q147", "복합AND", "청학동 공동주택 중 높이 30m 이상이고 지상 10층 이상인 채수",
          d010_cnt(f"{a4('청학동')} AND \"A9\"='공동주택' AND {n('A16')}>=30 AND {n('A26')}>=10")),
        C("Q148", "복합AND", "동삼동 교육연구시설 중 연면적 2500㎡ 이상이면서 높이 15m 이상인 이름과 연면적",
          d010_list(f"{a4('동삼동')} AND \"A9\"='교육연구시설' AND {n('A14')}>=2500 AND {n('A16')}>=15", '"A24","A4","A14","A16"', n("A14"), 15), "list"),
        C("Q149", "복합AND", "감전동 공장 중 연면적 2000㎡ 이상이고 건축면적 800㎡ 이상인 채수",
          d010_cnt(f"{a4('감전동')} AND \"A9\"='공장' AND {n('A14')}>=2000 AND {n('A12')}>=800")),
        C("Q150", "복합AND", "주례동 창고시설 중 연면적 500㎡ 이상이면서 높이 8m 이상인 채수",
          d010_cnt(f"{a4('주례동')} AND \"A9\"='창고시설' AND {n('A14')}>=500 AND {n('A16')}>=8")),
    ]


def logic_or_not_between() -> list:
    n = num
    return [
        C("Q151", "논리OR", "연제구에서 공동주택 또는 단독주택이면서 높이 20m 이상인 건물 수",
          d010_cnt(f"{gu('연제구')} AND \"A9\" IN ('공동주택','단독주택') AND {n('A16')}>=20")),
        C("Q152", "논리OR", "수영구 숙박시설 또는 위락시설 중 연면적 1000㎡ 이상인 채수",
          d010_cnt(f"{gu('수영구')} AND \"A9\" IN ('숙박시설','위락시설') AND {n('A14')}>=1000")),
        C("Q153", "논리OR", "사하구 공장 또는 창고시설 중 연면적 4000㎡ 이상인 이름과 용도·연면적",
          d010_list(f"{gu('사하구')} AND \"A9\" IN ('공장','창고시설') AND {n('A14')}>=4000", '"A24","A4","A9","A14"', n("A14"), 15), "list"),
        C("Q154", "논리OR", "금정구 교육연구시설 또는 노유자시설 중 대지면적 1500㎡ 이상인 채수",
          d010_cnt(f"{gu('금정구')} AND \"A9\" IN ('교육연구시설','노유자시설') AND {n('A15')}>=1500")),
        C("Q155", "논리OR", "해운대구에서 업무시설이거나 판매시설이면서 높이 30m 이상인 채수",
          d010_cnt(f"{gu('해운대구')} AND \"A9\" IN ('업무시설','판매시설') AND {n('A16')}>=30")),
        C("Q156", "논리NOT", "동래구 건물 중 공동주택을 제외하고 높이 40m 이상인 채수",
          d010_cnt(f"{gu('동래구')} AND \"A9\" <> '공동주택' AND {n('A16')}>=40")),
        C("Q157", "논리NOT", "남구 공동주택이 아니면서 지상 15층 이상인 건물 용도별 건수",
          f"""SELECT "A9" AS usage, COUNT(*)::bigint AS n FROM "{D010}"
              WHERE {gu('남구')} AND "A9" <> '공동주택' AND {n('A26')}>=15
              GROUP BY 1 ORDER BY n DESC""", "group"),
        C("Q158", "논리NOT", "강서구 공장·창고를 제외한 건물 중 연면적 5000㎡ 이상인 채수",
          d010_cnt(f"{gu('강서구')} AND \"A9\" NOT IN ('공장','창고시설') AND {n('A14')}>=5000")),
        C("Q159", "논리NOT", "부산진구 제1·2종근린생활시설을 뺀 건물 중 높이 25m 이상인 채수",
          d010_cnt(f"{gu('부산진구')} AND \"A9\" NOT IN ('제1종근린생활시설','제2종근린생활시설') AND {n('A16')}>=25")),
        C("Q160", "논리NOT", "영도구에서 단독주택이 아니고 벽돌·블록구조도 아닌 건물 중 연면적 1000㎡ 이상 채수",
          d010_cnt(f"{gu('영도구')} AND \"A9\" <> '단독주택' AND COALESCE(\"A11\",'') NOT ILIKE '%벽돌%' AND COALESCE(\"A11\",'') NOT ILIKE '%블록%' AND {n('A14')}>=1000")),
        C("Q161", "구간BETWEEN", "부산진구 높이 50m 이상 100m 이하 건물의 이름과 높이",
          d010_list(f"{gu('부산진구')} AND {n('A16')} BETWEEN 50 AND 100", '"A24","A4","A9","A16"', n("A16"), 20), "list"),
        C("Q162", "구간BETWEEN", "해운대구 공동주택 중 연면적 3000㎡ 이상 15000㎡ 이하인 채수",
          d010_cnt(f"{gu('해운대구')} AND \"A9\"='공동주택' AND {n('A14')} BETWEEN 3000 AND 15000")),
        C("Q163", "구간BETWEEN", "금정구 건물 중 지상 8층 이상 20층 이하이면서 높이 25m 이상인 채수",
          d010_cnt(f"{gu('금정구')} AND {n('A26')} BETWEEN 8 AND 20 AND {n('A16')}>=25")),
        C("Q164", "구간BETWEEN", "광안동 숙박시설 중 높이 15m 초과 40m 미만인 이름과 높이",
          d010_list(f"{a4('광안동')} AND \"A9\"='숙박시설' AND {n('A16')} > 15 AND {n('A16')} < 40", '"A24","A4","A16","A14"', n("A16"), 15), "list"),
        C("Q165", "구간BETWEEN", "사하구 공장 연면적 1000㎡ 이상 8000㎡ 이하이고 일반철골인 채수",
          d010_cnt(f"{gu('사하구')} AND \"A9\"='공장' AND {n('A14')} BETWEEN 1000 AND 8000 AND {rc('A11','%일반철골%')}")),
        C("Q166", "구간BETWEEN", "남구 공동주택 사용승인이 1980년 이상 1999년 이하이면서 10층 이상인 채수",
          d010_cnt(f"{gu('남구')} AND \"A9\"='공동주택' AND {year_between('A13', 1980, 1999)} AND {n('A26')}>=10")),
        C("Q167", "구간BETWEEN", "우동 건물 중 높이 80m 이상 200m 이하인 용도·이름·높이",
          d010_list(f"{a4('우동')} AND {n('A16')} BETWEEN 80 AND 200", '"A24","A9","A16","A26"', n("A16"), 20), "list"),
        C("Q168", "구간BETWEEN", "기장군 단독주택 건축면적 80㎡ 이상 200㎡ 이하이고 2000년 이후 사용승인 채수",
          d010_cnt(f"{gu('기장군')} AND \"A9\"='단독주택' AND {n('A12')} BETWEEN 80 AND 200 AND {year_ge('A13', 2000)}")),
        C("Q169", "논리OR", "북구에서 의료시설 또는 노유자시설이면서 연면적 1500㎡ 이상인 이름과 용도",
          d010_list(f"{gu('북구')} AND \"A9\" IN ('의료시설','노유자시설') AND {n('A14')}>=1500", '"A24","A4","A9","A14"', n("A14"), 15), "list"),
        C("Q170", "논리OR", "연제구 문화및집회시설 또는 운동시설 중 대지면적 2000㎡ 이상인 채수",
          d010_cnt(f"{gu('연제구')} AND \"A9\" IN ('문화및집회시설','운동시설') AND {n('A15')}>=2000")),
        C("Q171", "논리NOT", "수영구에서 공동주택·단독주택을 제외한 높이 35m 이상 건물 수",
          d010_cnt(f"{gu('수영구')} AND \"A9\" NOT IN ('공동주택','단독주택') AND {n('A16')}>=35")),
        C("Q172", "논리NOT", "장림동 공장 중 경량철골이 아닌 연면적 2500㎡ 이상 채수",
          d010_cnt(f"{a4('장림동')} AND \"A9\"='공장' AND COALESCE(\"A11\",'') NOT ILIKE '%경량철골%' AND {n('A14')}>=2500")),
        C("Q173", "구간BETWEEN", "사상구 건물 건폐율 20% 이상 70% 이하이면서 연면적 2000㎡ 이상인 채수",
          d010_cnt(f"{gu('사상구')} AND {n('A17')} BETWEEN 20 AND 70 AND {n('A14')}>=2000")),
        C("Q174", "구간BETWEEN", "해운대구 공동주택 용적율 100% 이상 400% 이하이고 15층 이상인 채수",
          d010_cnt(f"{gu('해운대구')} AND \"A9\"='공동주택' AND {n('A18')} BETWEEN 100 AND 400 AND {n('A26')}>=15")),
        C("Q175", "논리OR", "동래구 철근콘크리트 또는 철골철근콘크리트 구조이면서 높이 50m 이상인 채수",
          d010_cnt(f"{gu('동래구')} AND (\"A11\" ILIKE '%철근콘크리트%' OR \"A11\" ILIKE '%철골철근콘크리트%') AND {n('A16')}>=50")),
        C("Q176", "논리OR", "남구 아파트 또는 업무시설 중 지하 1층 이상이면서 지상 10층 이상인 채수",
          d010_cnt(f"{gu('남구')} AND \"A9\" IN ('공동주택','업무시설') AND {n('A27')}>=1 AND {n('A26')}>=10")),
        C("Q177", "구간BETWEEN", "금정구 단독주택 중 사용승인 1970~1989년이고 건축면적 60~150㎡인 채수",
          d010_cnt(f"{gu('금정구')} AND \"A9\"='단독주택' AND {year_between('A13', 1970, 1989)} AND {n('A12')} BETWEEN 60 AND 150")),
        C("Q178", "논리NOT", "강서구 동식물관련시설이 아니면서 산지(특수지)인 건물 중 연면적 500㎡ 이상 채수",
          d010_cnt(f"{gu('강서구')} AND \"A9\" <> '동.식물 관련시설' AND TRIM(COALESCE(\"A7\",'')) = '산' AND {n('A14')}>=500")),
        C("Q179", "논리OR", "부산진구 위험물저장및처리시설 또는 분뇨쓰레기처리시설 중 연면적 500㎡ 이상 채수",
          d010_cnt(f"{gu('부산진구')} AND \"A9\" IN ('위험물저장및처리시설','분뇨.쓰레기처리시설') AND {n('A14')}>=500")),
        C("Q180", "구간BETWEEN", "우동 공동주택 높이 60m 이상 120m 이하이고 연면적 5000㎡ 이상인 이름·높이·연면적",
          d010_list(f"{a4('우동')} AND \"A9\"='공동주택' AND {n('A16')} BETWEEN 60 AND 120 AND {n('A14')}>=5000", '"A24","A16","A14","A26"', n("A16"), 15), "list"),
        C("Q181", "논리NOT", "기장군 공동주택을 제외하고 높이 25m 이상인 건물 용도 상위 8개",
          f"""SELECT "A9" AS usage, COUNT(*)::bigint AS n FROM "{D010}"
              WHERE {gu('기장군')} AND "A9" <> '공동주택' AND {n('A16')}>=25
              GROUP BY 1 ORDER BY n DESC LIMIT 8""", "group"),
        C("Q182", "논리OR", "서구 종교시설 또는 교육연구시설 중 대지면적 2500㎡ 이상인 이름·용도·대지면적",
          d010_list(f"{gu('서구')} AND \"A9\" IN ('종교시설','교육연구시설') AND {n('A15')}>=2500", '"A24","A9","A15"', n("A15"), 15), "list"),
        C("Q183", "구간BETWEEN", "연제구 업무시설 연면적 800㎡ 이상 5000㎡ 이하이고 높이 15~45m인 채수",
          d010_cnt(f"{gu('연제구')} AND \"A9\"='업무시설' AND {n('A14')} BETWEEN 800 AND 5000 AND {n('A16')} BETWEEN 15 AND 45")),
        C("Q184", "논리NOT", "해운대구 위반건축물이 아니면서 높이 80m 이상인 공동주택 채수",
          d010_cnt(f"{gu('해운대구')} AND \"A9\"='공동주택' AND COALESCE(TRIM(\"A20\"::text),'N') <> 'Y' AND {n('A16')}>=80")),
        C("Q185", "논리OR", "사상구 공장 또는 자동차관련시설이면서 산업단지와 교차하는 건물 수",
          f"""SELECT COUNT(*)::bigint AS n FROM "{D010}" b
              WHERE {bgu('사상구')} AND b."A9" IN ('공장','자동차관련시설') AND {industrial_exists()}"""),
    ]


def unused_attrs() -> list:
    """건폐율·용적율·위반·지하·특수지·동명 등 NL100에 없던 속성 (40)."""
    n = num
    return [
        C("Q186", "미사용속성", "해운대구 공동주택 중 건폐율이 30% 이상인 건물 수",
          d010_cnt(f"{gu('해운대구')} AND \"A9\"='공동주택' AND {n('A17')}>=30")),
        C("Q187", "미사용속성", "수영구 공동주택 중 용적율이 250% 이상이고 높이 40m 이상인 채수",
          d010_cnt(f"{gu('수영구')} AND \"A9\"='공동주택' AND {n('A18')}>=250 AND {n('A16')}>=40")),
        C("Q188", "미사용속성", "부산진구 위반건축물(A20=Y) 중 공동주택은 몇 채야?",
          d010_cnt(f"{gu('부산진구')} AND TRIM(\"A20\"::text)='Y' AND \"A9\"='공동주택'")),
        C("Q189", "미사용속성", "남구 위반건축물 중 연면적 1000㎡ 이상인 용도·이름·연면적",
          d010_list(f"{gu('남구')} AND TRIM(\"A20\"::text)='Y' AND {n('A14')}>=1000", '"A24","A9","A14","A4"', n("A14"), 15), "list"),
        C("Q190", "미사용속성", "해운대구 지하 2층 이상이면서 지상 15층 이상인 공동주택 수",
          d010_cnt(f"{gu('해운대구')} AND \"A9\"='공동주택' AND {n('A27')}>=2 AND {n('A26')}>=15")),
        C("Q191", "미사용속성", "금정구 산지(특수지 산) 단독주택 중 건축면적 80㎡ 이상인 채수",
          d010_cnt(f"{gu('금정구')} AND TRIM(COALESCE(\"A7\",''))='산' AND \"A9\"='단독주택' AND {n('A12')}>=80")),
        C("Q192", "미사용속성", "기장군 산지 건물 중 연면적 500㎡ 이상인 용도별 건수",
          f"""SELECT "A9" AS usage, COUNT(*)::bigint AS n FROM "{D010}"
              WHERE {gu('기장군')} AND TRIM(COALESCE("A7",''))='산' AND {n('A14')}>=500
              GROUP BY 1 ORDER BY n DESC""", "group"),
        C("Q193", "미사용속성", "사하구 일반지번이 아닌 건물 중 공장인 채수",
          d010_cnt(f"{gu('사하구')} AND TRIM(COALESCE(\"A7\",'')) <> '일반' AND \"A9\"='공장'")),
        C("Q194", "미사용속성", "동래구 건물동명이 있는 공동주택 중 높이 40m 이상인 이름·동명·높이",
          d010_list(f"{gu('동래구')} AND \"A9\"='공동주택' AND TRIM(COALESCE(\"A25\",''))<>'' AND {n('A16')}>=40", '"A24","A25","A16","A14"', n("A16"), 15), "list"),
        C("Q195", "미사용속성", "우동에서 건물동명이 '101동'인 공동주택 채수",
          d010_cnt(f"{a4('우동')} AND \"A9\"='공동주택' AND TRIM(COALESCE(\"A25\",'')) ILIKE '%101동%'")),
        C("Q196", "미사용속성", "연제구 건폐율 60% 초과이면서 용적율 200% 이상인 건물 수",
          d010_cnt(f"{gu('연제구')} AND {n('A17')}>60 AND {n('A18')}>=200")),
        C("Q197", "미사용속성", "강서구 위반건축물 공장 중 연면적 2000㎡ 이상인 이름과 연면적",
          d010_list(f"{gu('강서구')} AND TRIM(\"A20\"::text)='Y' AND \"A9\"='공장' AND {n('A14')}>=2000", '"A24","A4","A14"', n("A14"), 15), "list"),
        C("Q198", "미사용속성", "북구 지하층이 있고 지상 5층 이상인 제2종근린생활시설 채수",
          d010_cnt(f"{gu('북구')} AND \"A9\"='제2종근린생활시설' AND {n('A27')}>=1 AND {n('A26')}>=5")),
        C("Q199", "미사용속성", "영도구 산지 건물 중 종교시설인 이름과 지번",
          d010_list(f"{gu('영도구')} AND TRIM(COALESCE(\"A7\",''))='산' AND \"A9\"='종교시설'", '"A24","A4","A5","A14"', n("A14"), 15), "list"),
        C("Q200", "미사용속성", "해운대구 용적율 상위 10개 공동주택의 이름·용적율·높이",
          d010_list(f"{gu('해운대구')} AND \"A9\"='공동주택' AND {n('A18')} IS NOT NULL AND {n('A18')}>0", '"A24","A4","A18","A16","A14"', n("A18"), 10), "list"),
        C("Q201", "미사용속성", "수영구 건폐율 상위 8개 숙박시설의 이름·건폐율·연면적",
          d010_list(f"{gu('수영구')} AND \"A9\"='숙박시설' AND {n('A17')} IS NOT NULL AND {n('A17')}>0", '"A24","A4","A17","A14"', n("A17"), 8), "list"),
        C("Q202", "미사용속성", "부산 전체 위반건축물 중 높이 40m 이상인 구별 건수",
          f"""SELECT regexp_replace("A4", '^부산광역시 ', '') AS addr_head, COUNT(*)::bigint AS n
              FROM "{D010}"
              WHERE TRIM("A20"::text)='Y' AND {n('A16')}>=40
              GROUP BY 1 ORDER BY n DESC LIMIT 16""", "group"),
        C("Q203", "미사용속성", "금정구 지하 3층 이상인 건물 용도와 이름",
          d010_list(f"{gu('금정구')} AND {n('A27')}>=3", '"A24","A9","A27","A26","A4"', n("A27"), 15), "list"),
        C("Q204", "미사용속성", "사상구 산지이면서 창고시설인 건물 수",
          d010_cnt(f"{gu('사상구')} AND TRIM(COALESCE(\"A7\",''))='산' AND \"A9\"='창고시설'")),
        C("Q205", "미사용속성", "남구 공동주택 중 건폐율 20~50%이고 용적율 150% 이상인 채수",
          d010_cnt(f"{gu('남구')} AND \"A9\"='공동주택' AND {n('A17')} BETWEEN 20 AND 50 AND {n('A18')}>=150")),
        C("Q206", "미사용속성", "동래구 위반건축물이면서 지어진지 30년 넘은 단독주택 채수",
          d010_cnt(f"{gu('동래구')} AND TRIM(\"A20\"::text)='Y' AND \"A9\"='단독주택' AND {age_gte('A13', 30)}")),
        C("Q207", "미사용속성", "해운대구 건물동명이 비어 있지 않은 아파트 중 20층 이상인 채수",
          d010_cnt(f"{gu('해운대구')} AND \"A9\"='공동주택' AND TRIM(COALESCE(\"A25\",''))<>'' AND {n('A26')}>=20")),
        C("Q208", "미사용속성", "기장군 용적율이 0보다 크고 80% 미만인 공장 채수",
          d010_cnt(f"{gu('기장군')} AND \"A9\"='공장' AND {n('A18')} > 0 AND {n('A18')} < 80")),
        C("Q209", "미사용속성", "사하구 지하층이 있는 공장 중 연면적 3000㎡ 이상인 이름·지하층·연면적",
          d010_list(f"{gu('사하구')} AND \"A9\"='공장' AND {n('A27')}>=1 AND {n('A14')}>=3000", '"A24","A27","A14","A4"', n("A14"), 15), "list"),
        C("Q210", "미사용속성", "중구 위반건축물 전체 채수와 그 중 제2종근린생활시설 채수",
          d010_agg("COUNT(*)::bigint AS violate_n, COUNT(*) FILTER (WHERE \"A9\"='제2종근린생활시설')::bigint AS near_n", f"{gu('중구')} AND TRIM(\"A20\"::text)='Y'"), "scalar"),
        C("Q211", "미사용속성", "연제구 건폐율이 기록된 공동주택의 평균 건폐율과 건수",
          d010_agg(f"COUNT(*)::bigint AS n, AVG({n('A17')}) AS avg_cov", f"{gu('연제구')} AND \"A9\"='공동주택' AND {n('A17')} > 0"), "scalar"),
        C("Q212", "미사용속성", "기장군 산지 단독주택 채수",
          d010_cnt(f"{gu('기장군')} AND TRIM(COALESCE(\"A7\",''))='산' AND \"A9\"='단독주택'")),
        C("Q213", "미사용속성", "광안동 숙박시설 중 지하층이 있는 이름·지하층·지상층",
          d010_list(f"{a4('광안동')} AND \"A9\"='숙박시설' AND {n('A27')}>=1", '"A24","A27","A26","A14"', n("A14"), 15), "list"),
        C("Q214", "미사용속성", "부산진구 용적율 400% 초과 건물 중 업무시설인 이름과 용적율",
          d010_list(f"{gu('부산진구')} AND {n('A18')}>400 AND \"A9\"='업무시설'", '"A24","A18","A16","A4"', n("A18"), 15), "list"),
        C("Q215", "미사용속성", "강서구 건폐율 10% 미만이면서 연면적 3000㎡ 이상인 공장 채수",
          d010_cnt(f"{gu('강서구')} AND \"A9\"='공장' AND {n('A17')} > 0 AND {n('A17')} < 10 AND {n('A14')}>=3000")),
        C("Q216", "미사용속성", "서구 위반건축물 중 높이 20m 이상인 채수",
          d010_cnt(f"{gu('서구')} AND TRIM(\"A20\"::text)='Y' AND {n('A16')}>=20")),
        C("Q217", "미사용속성", "영도구 일반지번 공동주택 중 건폐율 40% 이상인 채수",
          d010_cnt(f"{gu('영도구')} AND TRIM(COALESCE(\"A7\",''))='일반' AND \"A9\"='공동주택' AND {n('A17')}>=40")),
        C("Q218", "미사용속성", "정관 일대(기장군 정관) 산지 건물 용도 상위 6개",
          f"""SELECT "A9" AS usage, COUNT(*)::bigint AS n FROM "{D010}"
              WHERE {gu('기장군')} AND "A4" LIKE '%정관%' AND TRIM(COALESCE("A7",''))='산'
              GROUP BY 1 ORDER BY n DESC LIMIT 6""", "group"),
        C("Q219", "미사용속성", "해운대구 공동주택 중 용적율과 건폐율이 모두 있는 건물의 평균 용적율·평균 건폐율",
          d010_agg(f"COUNT(*)::bigint AS n, AVG({n('A18')}) AS avg_far, AVG({n('A17')}) AS avg_cov",
                   f"{gu('해운대구')} AND \"A9\"='공동주택' AND {n('A18')}>0 AND {n('A17')}>0"), "scalar"),
        C("Q220", "미사용속성", "동구 지하층 합계와 지하층이 있는 건물 수",
          d010_agg(f"COUNT(*) FILTER (WHERE {n('A27')}>=1)::bigint AS n, SUM({n('A27')}) AS sum_basement",
                   f"{gu('동구')}"), "scalar"),
        C("Q221", "미사용속성", "남구 건물동명에 '상가'가 들어가는 건물 수와 평균 연면적",
          d010_agg(f"COUNT(*)::bigint AS n, AVG({n('A14')}) AS avg_gfa",
                   f"{gu('남구')} AND COALESCE(\"A25\",'') ILIKE '%상가%'"), "scalar"),
        C("Q222", "미사용속성", "사하구 위반건축물 비율(위반/(위반+N))",
          d010_agg("""COUNT(*) FILTER (WHERE TRIM("A20"::text)='Y')::float8
                      / NULLIF(COUNT(*) FILTER (WHERE TRIM("A20"::text) IN ('Y','N')),0) * 100 AS pct_violate""",
                   f"{gu('사하구')}"), "scalar", "%"),
        C("Q223", "미사용속성", "금정구 산지 비율(산 / 전체) %",
          d010_agg("COUNT(*) FILTER (WHERE TRIM(COALESCE(\"A7\",''))='산')::float8 / NULLIF(COUNT(*),0) * 100 AS pct_mountain",
                   f"{gu('금정구')}"), "scalar", "%"),
        C("Q224", "미사용속성", "우동 공동주택 중 지하 2층 이상·건폐율 20% 이상·높이 60m 이상인 이름",
          d010_list(f"{a4('우동')} AND \"A9\"='공동주택' AND {n('A27')}>=2 AND {n('A17')}>=20 AND {n('A16')}>=60",
                    '"A24","A27","A17","A16"', n("A16"), 15), "list"),
        C("Q225", "미사용속성", "기장군 농수산 성격의 동식물관련시설 중 산지인 채수",
          d010_cnt(f"{gu('기장군')} AND \"A9\"='동.식물 관련시설' AND TRIM(COALESCE(\"A7\",''))='산'")),
    ]


def agg_ratio() -> list:
    n = num
    return [
        C("Q226", "집계비율", "해운대구 공동주택 평균 높이와 중앙값 높이, 건수",
          d010_agg(f"COUNT(*)::bigint AS n, AVG({n('A16')}) AS avg_h, PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY {n('A16')}) AS med_h",
                   f"{gu('해운대구')} AND \"A9\"='공동주택' AND {n('A16')} IS NOT NULL"), "scalar"),
        C("Q227", "집계비율", "수영구 건물 용도별 평균 연면적 상위 10개 용도",
          f"""SELECT "A9" AS usage, COUNT(*)::bigint AS n, AVG({n('A14')}) AS avg_gfa
              FROM "{D010}" WHERE {gu('수영구')} AND {n('A14')} IS NOT NULL
              GROUP BY 1 ORDER BY avg_gfa DESC NULLS LAST LIMIT 10""", "group"),
        C("Q228", "집계비율", "금정구 구조별 건물 수 상위 8개",
          f"""SELECT "A11" AS structure, COUNT(*)::bigint AS n FROM "{D010}"
              WHERE {gu('금정구')} AND TRIM(COALESCE("A11",''))<>''
              GROUP BY 1 ORDER BY n DESC LIMIT 8""", "group"),
        C("Q229", "집계비율", "사하구 공장 연면적 합계와 평균, 최대",
          d010_agg(f"COUNT(*)::bigint AS n, SUM({n('A14')}) AS sum_gfa, AVG({n('A14')}) AS avg_gfa, MAX({n('A14')}) AS max_gfa",
                   f"{gu('사하구')} AND \"A9\"='공장' AND {n('A14')} IS NOT NULL"), "scalar"),
        C("Q230", "집계비율", "남구에서 공동주택이 전체 건물에서 차지하는 비율 %",
          d010_agg("COUNT(*) FILTER (WHERE \"A9\"='공동주택')::float8 / NULLIF(COUNT(*),0) * 100 AS pct",
                   f"{gu('남구')}"), "scalar", "%"),
        C("Q231", "집계비율", "영도구 15층 이상 건물 중 공동주택 비율 %",
          d010_agg("COUNT(*) FILTER (WHERE \"A9\"='공동주택')::float8 / NULLIF(COUNT(*),0) * 100 AS pct",
                   f"{gu('영도구')} AND {n('A26')}>=15"), "scalar", "%"),
        C("Q232", "집계비율", "부산진구 용도별 평균 높이(높이 있는 건물만) 상위 8",
          f"""SELECT "A9" AS usage, COUNT(*)::bigint AS n, AVG({n('A16')}) AS avg_h
              FROM "{D010}" WHERE {gu('부산진구')} AND {n('A16')} IS NOT NULL AND {n('A16')} BETWEEN 1 AND 500
              GROUP BY 1 HAVING COUNT(*)>=20 ORDER BY avg_h DESC LIMIT 8""", "group"),
        C("Q233", "집계비율", "강서구 공장 vs 창고시설 평균 연면적과 건수",
          d010_agg(f"""COUNT(*) FILTER (WHERE "A9"='공장')::bigint AS factory_n,
                       AVG({n('A14')}) FILTER (WHERE "A9"='공장') AS factory_avg,
                       COUNT(*) FILTER (WHERE "A9"='창고시설')::bigint AS warehouse_n,
                       AVG({n('A14')}) FILTER (WHERE "A9"='창고시설') AS warehouse_avg""",
                   f"{gu('강서구')} AND \"A9\" IN ('공장','창고시설')"), "compare"),
        C("Q234", "집계비율", "연제구 철근콘크리트 건물의 평균 층수와 평균 높이",
          d010_agg(f"COUNT(*)::bigint AS n, AVG({n('A26')}) AS avg_fl, AVG({n('A16')}) AS avg_h",
                   f"{gu('연제구')} AND {rc('A11','%철근콘크리트%')}"), "scalar"),
        C("Q235", "집계비율", "기장군 단독주택 건축면적 합계와 평균",
          d010_agg(f"COUNT(*)::bigint AS n, SUM({n('A12')}) AS sum_area, AVG({n('A12')}) AS avg_area",
                   f"{gu('기장군')} AND \"A9\"='단독주택' AND {n('A12')} IS NOT NULL"), "scalar"),
        C("Q236", "집계비율", "해운대구 구별이 아니라 법정동별 공동주택 수 상위 8동",
          f"""SELECT "A4" AS dong, COUNT(*)::bigint AS n FROM "{D010}"
              WHERE {gu('해운대구')} AND "A9"='공동주택'
              GROUP BY 1 ORDER BY n DESC LIMIT 8""", "group"),
        C("Q237", "집계비율", "광안동 숙박시설 연면적 합계·평균·최대 높이",
          d010_agg(f"COUNT(*)::bigint AS n, SUM({n('A14')}) AS sum_gfa, AVG({n('A14')}) AS avg_gfa, MAX({n('A16')}) AS max_h",
                   f"{a4('광안동')} AND \"A9\"='숙박시설'"), "scalar"),
        C("Q238", "집계비율", "장림동 공장 중 연면적 1000㎡ 이상 비율 %",
          d010_agg(f"COUNT(*) FILTER (WHERE {n('A14')}>=1000)::float8 / NULLIF(COUNT(*),0) * 100 AS pct",
                   f"{a4('장림동')} AND \"A9\"='공장'"), "scalar", "%"),
        C("Q239", "집계비율", "대연동 공동주택 층수 구간별 건수(1-5, 6-10, 11-20, 21+)",
          f"""SELECT CASE
                    WHEN {n('A26')} < 6 THEN '1-5층'
                    WHEN {n('A26')} < 11 THEN '6-10층'
                    WHEN {n('A26')} < 21 THEN '11-20층'
                    ELSE '21층이상' END AS bin,
                  COUNT(*)::bigint AS n
              FROM "{D010}" WHERE {a4('대연동')} AND "A9"='공동주택' AND {n('A26')} IS NOT NULL
              GROUP BY 1 ORDER BY 1""", "group"),
        C("Q240", "집계비율", "문현동 vs 대연동 공동주택 평균 높이 차이(대연-문현)",
          d010_agg(f"""AVG({n('A16')}) FILTER (WHERE {a4('대연동')}) 
                       - AVG({n('A16')}) FILTER (WHERE {a4('문현동')}) AS diff_h,
                       AVG({n('A16')}) FILTER (WHERE {a4('대연동')}) AS daeyeon_h,
                       AVG({n('A16')}) FILTER (WHERE {a4('문현동')}) AS munhyeon_h""",
                   f"\"A9\"='공동주택' AND ({a4('대연동')} OR {a4('문현동')})"), "compare"),
        C("Q241", "집계비율", "북구 교육연구시설 대지면적 합계와 평균 높이",
          d010_agg(f"COUNT(*)::bigint AS n, SUM({n('A15')}) AS sum_land, AVG({n('A16')}) AS avg_h",
                   f"{gu('북구')} AND \"A9\"='교육연구시설'"), "scalar"),
        C("Q242", "집계비율", "사상구 공장 구조별 건수와 평균 연면적 상위 6",
          f"""SELECT "A11" AS structure, COUNT(*)::bigint AS n, AVG({n('A14')}) AS avg_gfa
              FROM "{D010}" WHERE {gu('사상구')} AND "A9"='공장'
              GROUP BY 1 ORDER BY n DESC LIMIT 6""", "group"),
        C("Q243", "집계비율", "중구 건물 중 높이 있는 건물의 평균·표준편차 높이",
          d010_agg(f"COUNT(*)::bigint AS n, AVG({n('A16')}) AS avg_h, STDDEV_POP({n('A16')}) AS sd_h",
                   f"{gu('중구')} AND {n('A16')} IS NOT NULL AND {n('A16')} BETWEEN 1 AND 500"), "scalar"),
        C("Q244", "집계비율", "서구 공동주택 연면적 합계가 단독주택 연면적 합계보다 얼마나 큰가",
          d010_agg(f"""SUM({n('A14')}) FILTER (WHERE "A9"='공동주택') AS apt_sum,
                       SUM({n('A14')}) FILTER (WHERE "A9"='단독주택') AS detached_sum,
                       SUM({n('A14')}) FILTER (WHERE "A9"='공동주택')
                         - SUM({n('A14')}) FILTER (WHERE "A9"='단독주택') AS diff_sum""",
                   f"{gu('서구')} AND \"A9\" IN ('공동주택','단독주택')"), "compare"),
        C("Q245", "집계비율", "동구 용도 종류 수(distinct A9)와 가장 많은 용도 건수",
          f"""SELECT COUNT(*)::bigint AS n_usage, MAX(cnt) AS max_usage_n
              FROM (SELECT "A9", COUNT(*)::bigint AS cnt FROM "{D010}" WHERE {gu('동구')} GROUP BY 1) s""",
          "scalar"),
        C("Q246", "집계비율", "우동 건물 중 높이 50m 이상 비율과 20층 이상 비율",
          d010_agg(f"""COUNT(*) FILTER (WHERE {n('A16')}>=50)::float8 / NULLIF(COUNT(*),0)*100 AS pct_h50,
                       COUNT(*) FILTER (WHERE {n('A26')}>=20)::float8 / NULLIF(COUNT(*),0)*100 AS pct_fl20""",
                   a4("우동")), "scalar", "%"),
        C("Q247", "집계비율", "연산동 용도별 건수 상위 10",
          f"""SELECT "A9" AS usage, COUNT(*)::bigint AS n FROM "{D010}"
              WHERE {a4('연산동')} GROUP BY 1 ORDER BY n DESC LIMIT 10""", "group"),
        C("Q248", "집계비율", "구서동 공동주택 평균 연면적·평균 층수·평균 높이",
          d010_agg(f"COUNT(*)::bigint AS n, AVG({n('A14')}) AS avg_gfa, AVG({n('A26')}) AS avg_fl, AVG({n('A16')}) AS avg_h",
                   f"{a4('구서동')} AND \"A9\"='공동주택'"), "scalar"),
        C("Q249", "집계비율", "해운대구 vs 수영구 공동주택 평균 높이",
          d010_agg(f"""AVG({n('A16')}) FILTER (WHERE {gu('해운대구')}) AS haeundae_h,
                       AVG({n('A16')}) FILTER (WHERE {gu('수영구')}) AS suyeong_h,
                       COUNT(*) FILTER (WHERE {gu('해운대구')})::bigint AS haeundae_n,
                       COUNT(*) FILTER (WHERE {gu('수영구')})::bigint AS suyeong_n""",
                   f"\"A9\"='공동주택' AND ({gu('해운대구')} OR {gu('수영구')})"), "compare"),
        C("Q250", "집계비율", "기장군 연도(사용승인 앞 4자리)별 공동주택 수, 2000년 이후만",
          f"""SELECT LEFT(regexp_replace("A13"::text,'[^0-9]','','g'),4) AS yyyy, COUNT(*)::bigint AS n
              FROM "{D010}"
              WHERE {gu('기장군')} AND "A9"='공동주택' AND {year_ge('A13', 2000)}
              GROUP BY 1 ORDER BY 1""", "group"),
        C("Q251", "집계비율", "사상구 산업단지 안 공장 비율(단지내 공장 / 사상구 공장)",
          f"""SELECT
                (SELECT COUNT(*) FROM "{D010}" b WHERE {bgu('사상구')} AND b."A9"='공장' AND {industrial_exists()})::float8
                / NULLIF((SELECT COUNT(*) FROM "{D010}" WHERE {gu('사상구')} AND "A9"='공장'),0) * 100 AS pct""", "scalar", "%"),
        C("Q252", "집계비율", "남구 숙박시설이 있는 법정동별 숙박시설 채수",
          f"""SELECT "A4" AS dong, COUNT(*)::bigint AS n FROM "{D010}"
              WHERE {gu('남구')} AND "A9"='숙박시설'
              GROUP BY 1 ORDER BY n DESC""", "group"),
        C("Q253", "집계비율", "동래구 공동주택 높이 90백분위와 건수",
          d010_agg(f"COUNT(*)::bigint AS n, PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY {n('A16')}) AS p90_h",
                   f"{gu('동래구')} AND \"A9\"='공동주택' AND {n('A16')} IS NOT NULL"), "scalar"),
        C("Q254", "집계비율", "부산 구별 위반건축물 수 상위 8개 구",
          f"""SELECT split_part("A4", ' ', 2) AS gu_name, COUNT(*)::bigint AS n
              FROM "{D010}"
              WHERE TRIM("A20"::text)='Y' AND "A4" LIKE '부산광역시 %'
              GROUP BY 1 ORDER BY n DESC LIMIT 8""", "group"),
        C("Q255", "집계비율", "금정구 2000년 이후 사용승인 공동주택 평균 층수가 1990년대보다 얼마나 높은가",
          d010_agg(f"""AVG({n('A26')}) FILTER (WHERE {year_ge('A13', 2000)}) AS avg_fl_2000,
                       AVG({n('A26')}) FILTER (WHERE {year_between('A13', 1990, 1999)}) AS avg_fl_1990s,
                       AVG({n('A26')}) FILTER (WHERE {year_ge('A13', 2000)})
                         - AVG({n('A26')}) FILTER (WHERE {year_between('A13', 1990, 1999)}) AS diff_fl""",
                   f"{gu('금정구')} AND \"A9\"='공동주택'"), "compare"),
        C("Q256", "집계비율", "사하구 공장 연면적 상위 10% 경계값(90백분위)",
          d010_agg(f"PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY {n('A14')}) AS p90_gfa, COUNT(*)::bigint AS n",
                   f"{gu('사하구')} AND \"A9\"='공장' AND {n('A14')} IS NOT NULL"), "scalar"),
        C("Q257", "집계비율", "해운대구 아파트 중 높이 결측 비율 %",
          d010_agg(f"COUNT(*) FILTER (WHERE {n('A16')} IS NULL)::float8 / NULLIF(COUNT(*),0)*100 AS pct_null_h",
                   f"{gu('해운대구')} AND \"A9\"='공동주택'"), "scalar", "%"),
        C("Q258", "집계비율", "연제구 업무시설 vs 공동주택 평균 연면적",
          d010_agg(f"""AVG({n('A14')}) FILTER (WHERE "A9"='업무시설') AS office_avg,
                       AVG({n('A14')}) FILTER (WHERE "A9"='공동주택') AS apt_avg,
                       COUNT(*) FILTER (WHERE "A9"='업무시설')::bigint AS office_n,
                       COUNT(*) FILTER (WHERE "A9"='공동주택')::bigint AS apt_n""",
                   f"{gu('연제구')} AND \"A9\" IN ('업무시설','공동주택')"), "compare"),
        C("Q259", "집계비율", "기장군 법정동별 공장 수 상위 6",
          f"""SELECT "A4" AS dong, COUNT(*)::bigint AS n FROM "{D010}"
              WHERE {gu('기장군')} AND "A9"='공장' GROUP BY 1 ORDER BY n DESC LIMIT 6""", "group"),
        C("Q260", "집계비율", "북구 공동주택 지상층 합계와 평균",
          d010_agg(f"COUNT(*)::bigint AS n, SUM({n('A26')}) AS sum_fl, AVG({n('A26')}) AS avg_fl",
                   f"{gu('북구')} AND \"A9\"='공동주택' AND {n('A26')} IS NOT NULL"), "scalar"),
        C("Q261", "집계비율", "수영구 숙박시설 중 연면적 대비 건축면적 비(평균 A12/A14)",
          d010_agg(f"COUNT(*)::bigint AS n, AVG({n('A12')} / NULLIF({n('A14')},0)) AS avg_ratio",
                   f"{gu('수영구')} AND \"A9\"='숙박시설' AND {n('A14')}>0"), "scalar"),
        C("Q262", "집계비율", "남구와 수영구 숙박시설 건수·평균 높이 비교",
          d010_agg(f"""COUNT(*) FILTER (WHERE {gu('남구')})::bigint AS nam_n,
                       AVG({n('A16')}) FILTER (WHERE {gu('남구')}) AS nam_h,
                       COUNT(*) FILTER (WHERE {gu('수영구')})::bigint AS suyeong_n,
                       AVG({n('A16')}) FILTER (WHERE {gu('수영구')}) AS suyeong_h""",
                   f"\"A9\"='숙박시설' AND ({gu('남구')} OR {gu('수영구')})"), "compare"),
        C("Q263", "집계비율", "부산진구 판매시설 연면적 합계 vs 업무시설 연면적 합계",
          d010_agg(f"""SUM({n('A14')}) FILTER (WHERE "A9"='판매시설') AS retail_sum,
                       SUM({n('A14')}) FILTER (WHERE "A9"='업무시설') AS office_sum""",
                   f"{gu('부산진구')} AND \"A9\" IN ('판매시설','업무시설')"), "compare"),
        C("Q264", "집계비율", "강서구 건물 중 연면적 10000㎡ 이상인 용도 구성",
          f"""SELECT "A9" AS usage, COUNT(*)::bigint AS n FROM "{D010}"
              WHERE {gu('강서구')} AND {n('A14')}>=10000 GROUP BY 1 ORDER BY n DESC""", "group"),
        C("Q265", "집계비율", "해운대구 공동주택 높이 합계(1~500m만)와 건수",
          d010_agg(f"COUNT(*)::bigint AS n, SUM({n('A16')}) AS sum_h",
                   f"{gu('해운대구')} AND \"A9\"='공동주택' AND {n('A16')} BETWEEN 1 AND 500"), "scalar"),
    ]


def spatial_compound() -> list:
    n = num
    return [
        C("Q266", "공간복합", "연산동 행정경계 안 공동주택 중 높이 40m 이상이면서 연면적 2000㎡ 이상인 채수",
          f"""SELECT COUNT(*)::bigint AS n FROM "{D010}" b JOIN "{BND}" d ON ST_Intersects(b.geometry, d.geometry)
              WHERE {admin_eq('연산동')} AND b."A9"='공동주택' AND {bnum('A16')}>=40 AND {bnum('A14')}>=2000"""),
        C("Q267", "공간복합", "구서1동 안에 있는 공동주택 중 지상 15층 이상인 이름과 층수",
          f"""SELECT b."A24", b."A26", b."A16", b."A14" FROM "{D010}" b
              JOIN "{BND}" d ON ST_Intersects(b.geometry, d.geometry)
              WHERE {admin_eq('구서1동')} AND b."A9"='공동주택' AND {bnum('A26')}>=15
              ORDER BY {bnum('A26')} DESC NULLS LAST LIMIT 15""", "list"),
        C("Q268", "공간복합", "대연3동과 교차하는 기초구역 중 면적 상위 5개의 번호와 면적",
          f"""SELECT DISTINCT t."BAS_ID", t."BAS_AR" FROM "{BAS}" t
              JOIN "{BND}" d ON t.geometry && d.geometry AND ST_Intersects(t.geometry, d.geometry)
              WHERE {admin_eq('대연3동')} ORDER BY t."BAS_AR" DESC NULLS LAST LIMIT 5""", "list", "개"),
        C("Q269", "공간복합", "우1동 주변 200m 이내 공동주택 중 높이 50m 이상인 채수",
          f"""SELECT COUNT(*)::bigint AS n FROM "{D010}" b
              CROSS JOIN (SELECT ST_Union(d.geometry) AS geom FROM "{BND}" d WHERE {admin_eq('우1동')}) z
              WHERE z.geom IS NOT NULL AND b.geometry && ST_Expand(z.geom, 0.003)
                AND ST_DWithin(b.geometry::geography, z.geom::geography, 200)
                AND b."A9"='공동주택' AND {bnum('A16')}>=50"""),
        C("Q270", "공간복합", "광안2동 주변 100m 이내 숙박시설 채수",
          f"""SELECT COUNT(*)::bigint AS n FROM "{D010}" b
              CROSS JOIN (SELECT ST_Union(d.geometry) AS geom FROM "{BND}" d WHERE {admin_eq('광안2동')}) z
              WHERE z.geom IS NOT NULL AND b.geometry && ST_Expand(z.geom, 0.002)
                AND ST_DWithin(b.geometry::geography, z.geom::geography, 100)
                AND b."A9"='숙박시설'"""),
        C("Q271", "공간복합", "장림동 산업단지 안 공장 중 연면적 3000㎡ 이상인 채수",
          f"""SELECT COUNT(*)::bigint AS n FROM "{D010}" b
              WHERE {ba4('장림동')} AND b."A9"='공장' AND {bnum('A14')}>=3000 AND {industrial_exists()}"""),
        C("Q272", "공간복합", "명지·녹산 국가산업단지 안 공장 또는 창고시설 채수",
          f"""SELECT COUNT(*)::bigint AS n FROM "{D010}" b
              WHERE b."A9" IN ('공장','창고시설') AND {named_industrial('명지')}"""),
        C("Q273", "공간복합", "센텀2지구 도시첨단산업단지와 교차하는 건물 용도별 건수",
          f"""SELECT b."A9" AS usage, COUNT(*)::bigint AS n FROM "{D010}" b
              WHERE {named_industrial('센텀2지구')}
              GROUP BY 1 ORDER BY n DESC LIMIT 10""", "group"),
        C("Q274", "공간복합", "사하구 산업단지와 교차하는 기초구역 개수",
          f"""SELECT COUNT(DISTINCT t."BAS_ID")::bigint AS n FROM "{BAS}" t
              JOIN "{D060}" i ON ST_Intersects(t.geometry, i.geometry)
              WHERE i."A4"='26380'""", "count", "개"),
        C("Q275", "공간복합", "반여1동 안 공동주택 중 2000년 이후 사용승인인 채수",
          f"""SELECT COUNT(*)::bigint AS n FROM "{D010}" b
              JOIN "{BND}" d ON ST_Intersects(b.geometry, d.geometry)
              WHERE {admin_eq('반여1동')} AND b."A9"='공동주택'
                AND b."A13"::text ~ '^[0-9]{{4}}'
                AND LEFT(regexp_replace(b."A13"::text,'[^0-9]','','g'),4) >= '2000'"""),
        C("Q276", "공간복합", "문현1동 안 건물 중 높이 25m 이상이면서 공동주택이 아닌 채수",
          f"""SELECT COUNT(*)::bigint AS n FROM "{D010}" b
              JOIN "{BND}" d ON ST_Intersects(b.geometry, d.geometry)
              WHERE {admin_eq('문현1동')} AND b."A9" <> '공동주택' AND {bnum('A16')}>=25"""),
        C("Q277", "공간복합", "구포1동 안 공장·창고 합산 채수",
          f"""SELECT COUNT(*)::bigint AS n FROM "{D010}" b
              JOIN "{BND}" d ON ST_Intersects(b.geometry, d.geometry)
              WHERE {admin_eq('구포1동')} AND b."A9" IN ('공장','창고시설')"""),
        C("Q278", "공간복합", "감천1동 안 공장 중 산업단지와 교차하는 비율 %",
          f"""SELECT COUNT(*) FILTER (WHERE {industrial_exists()})::float8
                     / NULLIF(COUNT(*),0) * 100 AS pct
              FROM "{D010}" b JOIN "{BND}" d ON ST_Intersects(b.geometry, d.geometry)
              WHERE {admin_eq('감천1동')} AND b."A9"='공장'""", "scalar", "%"),
        C("Q279", "공간복합", "남구 기초구역 중 면적(BAS_AR) 0.3 이상인 개수",
          f'SELECT COUNT(*)::bigint AS n FROM "{BAS}" WHERE "SIG_KOR_NM"=\'남구\' AND "BAS_AR">=0.3', "count", "개"),
        C("Q280", "공간복합", "해운대구 기초구역 이동사유별 개수",
          f"""SELECT COALESCE("MVMN_RESN",'(없음)') AS reason, COUNT(*)::bigint AS n
              FROM "{BAS}" WHERE "SIG_KOR_NM"='해운대구' GROUP BY 1 ORDER BY n DESC""", "group", "개"),
        C("Q281", "공간복합", "연산동 행정경계 안 업무시설 중 연면적 상위 8",
          f"""SELECT b."A24", b."A14", b."A16" FROM "{D010}" b
              JOIN "{BND}" d ON ST_Intersects(b.geometry, d.geometry)
              WHERE {admin_eq('연산동')} AND b."A9"='업무시설'
              ORDER BY {bnum('A14')} DESC NULLS LAST LIMIT 8""", "list"),
        C("Q282", "공간복합", "신호지방산업단지 안 건물 용도별 건수 상위 6",
          f"""SELECT b."A9" AS usage, COUNT(*)::bigint AS n FROM "{D010}" b
              WHERE {named_industrial('신호지방산업단지')}
              GROUP BY 1 ORDER BY n DESC LIMIT 6""", "group"),
        C("Q283", "공간복합", "강서구 산업단지 안 공장 중 연면적 5000㎡ 이상 이름",
          f"""SELECT b."A24", b."A4", b."A14" FROM "{D010}" b
              WHERE {bgu('강서구')} AND b."A9"='공장' AND {bnum('A14')}>=5000 AND {industrial_exists()}
              ORDER BY {bnum('A14')} DESC NULLS LAST LIMIT 15""", "list"),
        C("Q284", "공간복합", "우동과 교차하는 기초구역 개수와 그 중 면적 최대값",
          f"""SELECT COUNT(DISTINCT t."BAS_ID")::bigint AS n, MAX(t."BAS_AR") AS max_ar
              FROM "{BAS}" t JOIN "{BND}" d ON ST_Intersects(t.geometry, d.geometry)
              WHERE {admin_eq('우동')}""", "scalar"),
        C("Q285", "공간복합", "우1동 중심에서 300m 이내 공동주택 중 높이 40m 이상 채수",
          f"""SELECT COUNT(*)::bigint AS n FROM "{D010}" b
              CROSS JOIN (
                SELECT ST_Centroid(ST_Union(d.geometry)) AS geom FROM "{BND}" d WHERE {admin_eq('우1동')}
              ) z
              WHERE z.geom IS NOT NULL
                AND ST_DWithin(b.geometry::geography, z.geom::geography, 300)
                AND b."A9"='공동주택' AND {bnum('A16')}>=40"""),
        C("Q286", "공간복합", "대연3동 안 교육연구시설 대지면적 합계",
          f"""SELECT COUNT(*)::bigint AS n, SUM({bnum('A15')}) AS sum_land
              FROM "{D010}" b JOIN "{BND}" d ON ST_Intersects(b.geometry, d.geometry)
              WHERE {admin_eq('대연3동')} AND b."A9"='교육연구시설'""", "scalar"),
        C("Q287", "공간복합", "온천1동 안 공동주택 vs 단독주택 채수",
          f"""SELECT COUNT(*) FILTER (WHERE b."A9"='공동주택')::bigint AS apt_n,
                     COUNT(*) FILTER (WHERE b."A9"='단독주택')::bigint AS detached_n
              FROM "{D010}" b JOIN "{BND}" d ON ST_Intersects(b.geometry, d.geometry)
              WHERE {admin_eq('온천1동')}""", "compare"),
        C("Q288", "공간복합", "모라도시첨단산업단지 안 건물 수와 평균 연면적",
          f"""SELECT COUNT(*)::bigint AS n, AVG({bnum('A14')}) AS avg_gfa
              FROM "{D010}" b WHERE {named_industrial('모라도시첨단산업단지')}""", "scalar"),
        C("Q289", "공간복합", "남구 기초구역과 교차하는 건물 중 높이 60m 이상인 채수(건물 중복 제거)",
          f"""SELECT COUNT(DISTINCT b."A0")::bigint AS n FROM "{D010}" b
              JOIN "{BAS}" t ON b.geometry && t.geometry AND ST_Intersects(b.geometry, t.geometry)
              WHERE t."SIG_KOR_NM"='남구' AND {bnum('A16')}>=60"""),
        C("Q290", "공간복합", "재송1동 안 공동주택 평균 높이와 건수",
          f"""SELECT COUNT(*)::bigint AS n, AVG({bnum('A16')}) AS avg_h
              FROM "{D010}" b JOIN "{BND}" d ON ST_Intersects(b.geometry, d.geometry)
              WHERE {admin_eq('재송1동')} AND b."A9"='공동주택'""", "scalar"),
        C("Q291", "공간복합", "장안일반산업단지 안 공장 채수",
          f"""SELECT COUNT(*)::bigint AS n FROM "{D010}" b
              WHERE b."A9"='공장' AND {named_industrial('장안일반산업단지')}"""),
        C("Q292", "공간복합", "구서동 주변 300m 이내 공동주택 중 연면적 3000㎡ 이상 채수",
          f"""SELECT COUNT(*)::bigint AS n FROM "{D010}" b
              CROSS JOIN (SELECT ST_Union(d.geometry) AS geom FROM "{BND}" d WHERE {admin_eq('구서동')}) z
              WHERE z.geom IS NOT NULL AND b.geometry && ST_Expand(z.geom, 0.004)
                AND ST_DWithin(b.geometry::geography, z.geom::geography, 300)
                AND b."A9"='공동주택' AND {bnum('A14')}>=3000"""),
        C("Q293", "공간복합", "부산 일반산업단지 도형 중 시군구코드가 강서구(26440)인 개수",
          f"""SELECT COUNT(*)::bigint AS n FROM "{D060}" WHERE "A4"='26440' AND "A6"='일반산업단지'""", "count", "개"),
        C("Q294", "공간복합", "사상재생사업지구와 교차하는 건물 용도 상위 5",
          f"""SELECT b."A9" AS usage, COUNT(*)::bigint AS n FROM "{D010}" b
              WHERE {named_industrial('사상재생')}
              GROUP BY 1 ORDER BY n DESC LIMIT 5""", "group"),
        C("Q295", "공간복합", "대연3동과 문현1동 행정경계에 동시에 걸치는 기초구역 수",
          f"""SELECT COUNT(*)::bigint AS n FROM (
                SELECT t."BAS_ID"
                FROM "{BAS}" t
                JOIN "{BND}" d1 ON ST_Intersects(t.geometry, d1.geometry)
                JOIN "{BND}" d2 ON ST_Intersects(t.geometry, d2.geometry)
                WHERE d1."ADM_NM"='대연3동' AND d1."ADM_CD" LIKE '21%'
                  AND d2."ADM_NM"='문현1동' AND d2."ADM_CD" LIKE '21%'
                GROUP BY 1
              ) s""", "count", "개"),
        C("Q296", "공간복합", "우1동 안 판매시설 또는 업무시설 채수",
          f"""SELECT COUNT(*)::bigint AS n FROM "{D010}" b
              JOIN "{BND}" d ON ST_Intersects(b.geometry, d.geometry)
              WHERE {admin_eq('우1동')} AND b."A9" IN ('판매시설','업무시설')"""),
        C("Q297", "공간복합", "기장대우일반산업단지 안 건물 수",
          f"""SELECT COUNT(*)::bigint AS n FROM "{D010}" b
              WHERE {named_industrial('기장대우일반산업단지')}"""),
        C("Q298", "공간복합", "북구 기초구역 면적 합계와 개수",
          f"""SELECT COUNT(*)::bigint AS n, SUM("BAS_AR") AS sum_ar FROM "{BAS}" WHERE "SIG_KOR_NM"='북구'""", "scalar"),
        C("Q299", "공간복합", "연산동 행정경계 안 위반건축물 채수",
          f"""SELECT COUNT(*)::bigint AS n FROM "{D010}" b
              JOIN "{BND}" d ON ST_Intersects(b.geometry, d.geometry)
              WHERE {admin_eq('연산동')} AND TRIM(b."A20"::text)='Y'"""),
        C("Q300", "공간복합", "명지동 건물 중 산업단지 안에 있으면서 연면적 2000㎡ 이상인 채수",
          f"""SELECT COUNT(*)::bigint AS n FROM "{D010}" b
              WHERE {ba4('명지동')} AND {bnum('A14')}>=2000 AND {industrial_exists()}"""),
    ]


def d198_exclusive() -> list:
    """동래·금정 용도별건물(D198) 전용 속성 (40)."""
    n = num
    return [
        C("Q301", "D198전용", "동래구 집합건축물 중 주건축물이면서 건물높이 30m 이상인 채수",
          f"""SELECT COUNT(*)::bigint AS n FROM "{D198_DR}"
              WHERE "A10"='집합건축물' AND "A16"='주건축물' AND {n('A30')}>=30"""),
        C("Q302", "D198전용", "금정구 집합건축물 중 세부용도가 아파트이고 지상 15층 이상인 채수",
          f"""SELECT COUNT(*)::bigint AS n FROM "{D198_GJ}"
              WHERE "A10"='집합건축물' AND "A27"='아파트' AND {n('A31')}>=15"""),
        C("Q303", "D198전용", "동래구 다세대주택(세부용도) 중 건물연면적 500㎡ 이상인 채수",
          f"""SELECT COUNT(*)::bigint AS n FROM "{D198_DR}" WHERE "A27"='다세대주택' AND {n('A19')}>=500"""),
        C("Q304", "D198전용", "금정구 다가구주택 중 허가일자가 1990년대인 채수",
          f"""SELECT COUNT(*)::bigint AS n FROM "{D198_GJ}"
              WHERE "A27"='다가구주택' AND {year_between('A33', 1990, 1999)}"""),
        C("Q305", "D198전용", "동래구 상업용(용도분류) 건물 중 건물높이 20m 이상인 이름과 높이",
          f"""SELECT "A13" AS name, "A4", {n('A30')} AS h, "A25"
              FROM "{D198_DR}" WHERE "A29"='상업용' AND {n('A30')}>=20
              ORDER BY {n('A30')} DESC NULLS LAST LIMIT 15""", "list"),
        C("Q306", "D198전용", "금정구 문교사회용 건물 수와 평균 건물연면적",
          f"""SELECT COUNT(*)::bigint AS n, AVG({n('A19')}) AS avg_gfa
              FROM "{D198_GJ}" WHERE "A29"='문교사회용'""", "scalar"),
        C("Q307", "D198전용", "동래구 부속건축물 채수와 주건축물 채수",
          f"""SELECT COUNT(*) FILTER (WHERE "A16"='부속건축물')::bigint AS annex_n,
                     COUNT(*) FILTER (WHERE "A16"='주건축물')::bigint AS main_n
              FROM "{D198_DR}" """, "compare"),
        C("Q308", "D198전용", "금정구 일반건축물대장 중 건폐율 50% 이상 80% 이하인 채수",
          f"""SELECT COUNT(*)::bigint AS n FROM "{D198_GJ}"
              WHERE "A12"='일반건축물대장' AND {n('A21')} BETWEEN 50 AND 80"""),
        C("Q309", "D198전용", "동래구 표제부 중 용적율 200% 이상인 공동주택(주요용도) 채수",
          f"""SELECT COUNT(*)::bigint AS n FROM "{D198_DR}"
              WHERE "A12"='표제부' AND "A25"='공동주택' AND {n('A20')}>=200"""),
        C("Q310", "D198전용", "금정구 오피스텔(세부용도) 이름과 지상층·건물높이",
          f"""SELECT "A13" AS name, "A4", {n('A31')} AS fl, {n('A30')} AS h
              FROM "{D198_GJ}" WHERE "A27"='오피스텔'
              ORDER BY {n('A30')} DESC NULLS LAST LIMIT 15""", "list"),
        C("Q311", "D198전용", "동래구 허가일과 사용승인일 연도 차이가 3년 이상인 집합건축물 채수",
          f"""SELECT COUNT(*)::bigint AS n FROM "{D198_DR}"
              WHERE "A10"='집합건축물'
                AND "A33"::text ~ '^[0-9]{{4}}' AND "A34"::text ~ '^[0-9]{{4}}'
                AND (LEFT(regexp_replace("A34"::text,'[^0-9]','','g'),4)::int
                   - LEFT(regexp_replace("A33"::text,'[^0-9]','','g'),4)::int) >= 3"""),
        C("Q312", "D198전용", "금정구 사용승인이 2000년 이후인 아파트(세부용도) 채수",
          f"""SELECT COUNT(*)::bigint AS n FROM "{D198_GJ}"
              WHERE "A27"='아파트' AND {year_ge('A34', 2000)}"""),
        C("Q313", "D198전용", "동래구 지하층 1 이상인 상업용 건물 채수",
          f"""SELECT COUNT(*)::bigint AS n FROM "{D198_DR}" WHERE "A29"='상업용' AND {n('A32')}>=1"""),
        C("Q314", "D198전용", "금정구 공업용 건물 중 건물연면적 3000㎡ 이상인 이름과 연면적",
          f"""SELECT "A13" AS name, "A4", {n('A19')} AS gfa FROM "{D198_GJ}"
              WHERE "A29"='공업용' AND {n('A19')}>=3000
              ORDER BY {n('A19')} DESC NULLS LAST LIMIT 15""", "list"),
        C("Q315", "D198전용", "동래구 주요용도별 건수 상위 8",
          f"""SELECT "A25" AS usage, COUNT(*)::bigint AS n FROM "{D198_DR}"
              WHERE TRIM(COALESCE("A25",''))<>'' GROUP BY 1 ORDER BY n DESC LIMIT 8""", "group"),
        C("Q316", "D198전용", "금정구 세부용도별 건수 상위 8",
          f"""SELECT "A27" AS detail, COUNT(*)::bigint AS n FROM "{D198_GJ}"
              WHERE TRIM(COALESCE("A27",''))<>'' GROUP BY 1 ORDER BY n DESC LIMIT 8""", "group"),
        C("Q317", "D198전용", "동래구 학원(세부용도) 중 건물대지면적 200㎡ 이상인 채수",
          f"""SELECT COUNT(*)::bigint AS n FROM "{D198_DR}" WHERE "A27"='학원' AND {n('A17')}>=200"""),
        C("Q318", "D198전용", "금정구 일반음식점 중 집합건축물인 채수",
          f"""SELECT COUNT(*)::bigint AS n FROM "{D198_GJ}" WHERE "A27"='일반음식점' AND "A10"='집합건축물'"""),
        C("Q319", "D198전용", "동래구 공공용 건물 이름과 주요용도",
          f"""SELECT "A13" AS name, "A25", "A4" FROM "{D198_DR}" WHERE "A29"='공공용'
              ORDER BY {n('A19')} DESC NULLS LAST LIMIT 15""", "list"),
        C("Q320", "D198전용", "금정구 농수산용 건물 수",
          f"""SELECT COUNT(*)::bigint AS n FROM "{D198_GJ}" WHERE "A29"='농수산용'"""),
        C("Q321", "D198전용", "동래구 온천동 집합건축물 중 지상 10층 이상인 채수",
          f"""SELECT COUNT(*)::bigint AS n FROM "{D198_DR}"
              WHERE {a4('온천동')} AND "A10"='집합건축물' AND {n('A31')}>=10"""),
        C("Q322", "D198전용", "금정구 구서동 아파트(세부용도) 평균 건물높이와 건수",
          f"""SELECT COUNT(*)::bigint AS n, AVG({n('A30')}) AS avg_h FROM "{D198_GJ}"
              WHERE {a4('구서동')} AND "A27"='아파트'""", "scalar"),
        C("Q323", "D198전용", "동래구 사직동 상업용 중 허가 1990년대인 채수",
          f"""SELECT COUNT(*)::bigint AS n FROM "{D198_DR}"
              WHERE {a4('사직동')} AND "A29"='상업용' AND {year_between('A33', 1990, 1999)}"""),
        C("Q324", "D198전용", "금정구 장전동 문교사회용 건물연면적 합계",
          f"""SELECT COUNT(*)::bigint AS n, SUM({n('A19')}) AS sum_gfa FROM "{D198_GJ}"
              WHERE {a4('장전동')} AND "A29"='문교사회용'""", "scalar"),
        C("Q325", "D198전용", "동래구 안락동 다세대주택 중 사용승인 2000년 이후인 채수",
          f"""SELECT COUNT(*)::bigint AS n FROM "{D198_DR}"
              WHERE {a4('안락동')} AND "A27"='다세대주택' AND {year_ge('A34', 2000)}"""),
        C("Q326", "D198전용", "금정구 부곡동 주거용 중 건폐율 40% 이상인 채수",
          f"""SELECT COUNT(*)::bigint AS n FROM "{D198_GJ}"
              WHERE {a4('부곡동')} AND "A29"='주거용' AND {n('A21')}>=40"""),
        C("Q327", "D198전용", "동래구 명륜동 오피스텔 또는 사무소(세부용도) 채수",
          f"""SELECT COUNT(*)::bigint AS n FROM "{D198_DR}"
              WHERE {a4('명륜동')} AND "A27" IN ('오피스텔','사무소')"""),
        C("Q328", "D198전용", "금정구 남산동 단독주택(세부용도) 중 지어진지 30년 넘은 채수(사용승인 기준)",
          f"""SELECT COUNT(*)::bigint AS n FROM "{D198_GJ}"
              WHERE {a4('남산동')} AND "A27"='단독주택' AND {age_gte('A34', 30)}"""),
        C("Q329", "D198전용", "동래구 집합 vs 일반건축물 평균 건물높이",
          f"""SELECT AVG({n('A30')}) FILTER (WHERE "A10"='집합건축물') AS jibhap_h,
                     AVG({n('A30')}) FILTER (WHERE "A10"='일반건축물') AS general_h,
                     COUNT(*) FILTER (WHERE "A10"='집합건축물')::bigint AS jibhap_n,
                     COUNT(*) FILTER (WHERE "A10"='일반건축물')::bigint AS general_n
              FROM "{D198_DR}" """, "compare"),
        C("Q330", "D198전용", "금정구 허가일과 사용승인일의 연도 차이가 5년 이상인 건물 수",
          f"""SELECT COUNT(*)::bigint AS n FROM "{D198_GJ}"
              WHERE "A33"::text ~ '^[0-9]{{4}}' AND "A34"::text ~ '^[0-9]{{4}}'
                AND (LEFT(regexp_replace("A34"::text,'[^0-9]','','g'),4)::int
                   - LEFT(regexp_replace("A33"::text,'[^0-9]','','g'),4)::int) >= 5"""),
        C("Q331", "D198전용", "동래구 소매점(세부용도) 중 건물건축면적 100㎡ 이상인 채수",
          f"""SELECT COUNT(*)::bigint AS n FROM "{D198_DR}" WHERE "A27"='소매점' AND {n('A18')}>=100"""),
        C("Q332", "D198전용", "금정구 철근콘크리트 구조이면서 주요용도가 공동주택이고 15층 이상인 채수",
          f"""SELECT COUNT(*)::bigint AS n FROM "{D198_GJ}"
              WHERE "A23" ILIKE '%철근콘크리트%' AND "A25"='공동주택' AND {n('A31')}>=15"""),
        C("Q333", "D198전용", "동래구 용도분류별 평균 건물연면적",
          f"""SELECT "A29" AS cls, COUNT(*)::bigint AS n, AVG({n('A19')}) AS avg_gfa
              FROM "{D198_DR}" WHERE TRIM(COALESCE("A29",''))<>''
              GROUP BY 1 ORDER BY n DESC""", "group"),
        C("Q334", "D198전용", "금정구 주거용 대비 상업용 건수 비",
          f"""SELECT COUNT(*) FILTER (WHERE "A29"='상업용')::float8
                     / NULLIF(COUNT(*) FILTER (WHERE "A29"='주거용'),0) AS commercial_per_resi,
                     COUNT(*) FILTER (WHERE "A29"='주거용')::bigint AS resi_n,
                     COUNT(*) FILTER (WHERE "A29"='상업용')::bigint AS com_n
              FROM "{D198_GJ}" """, "compare"),
        C("Q335", "D198전용", "동래구 수안동 집합건축물 이름 상위(연면적순) 10",
          f"""SELECT "A13" AS name, {n('A19')} AS gfa, "A25" FROM "{D198_DR}"
              WHERE {a4('수안동')} AND "A10"='집합건축물'
              ORDER BY {n('A19')} DESC NULLS LAST LIMIT 10""", "list"),
        C("Q336", "D198전용", "금정구 청룡동 문교사회용 또는 공공용 채수",
          f"""SELECT COUNT(*)::bigint AS n FROM "{D198_GJ}"
              WHERE {a4('청룡동')} AND "A29" IN ('문교사회용','공공용')"""),
        C("Q337", "D198전용", "동래구 명장동 다가구주택 평균 건물건축면적과 건수",
          f"""SELECT COUNT(*)::bigint AS n, AVG({n('A18')}) AS avg_bldg_area FROM "{D198_DR}"
              WHERE {a4('명장동')} AND "A27"='다가구주택'""", "scalar"),
        C("Q338", "D198전용", "금정구 서동 주거용 중 지하층 있는 채수",
          f"""SELECT COUNT(*)::bigint AS n FROM "{D198_GJ}"
              WHERE {a4('서동')} AND "A29"='주거용' AND {n('A32')}>=1"""),
        C("Q339", "D198전용", "동래구 칠산동 일반건축물 중 주요용도 제2종근린생활시설 채수",
          f"""SELECT COUNT(*)::bigint AS n FROM "{D198_DR}"
              WHERE {a4('칠산동')} AND "A10"='일반건축물' AND "A25"='제2종근린생활시설'"""),
        C("Q340", "D198전용", "금정구 금사동 공업용 중 건물높이 15m 이상인 채수",
          f"""SELECT COUNT(*)::bigint AS n FROM "{D198_GJ}"
              WHERE {a4('금사동')} AND "A29"='공업용' AND {n('A30')}>=15"""),
    ]


def compare_year() -> list:
    n = num
    p80 = 80 * PYEONG_M2
    return [
        C("Q341", "비교연도", "해운대구와 수영구 중 높이 80m 이상 공동주택이 더 많은 구와 각각의 채수",
          d010_agg(f"""COUNT(*) FILTER (WHERE {gu('해운대구')})::bigint AS haeundae_n,
                       COUNT(*) FILTER (WHERE {gu('수영구')})::bigint AS suyeong_n""",
                   f"\"A9\"='공동주택' AND {n('A16')}>=80 AND ({gu('해운대구')} OR {gu('수영구')})"), "compare"),
        C("Q342", "비교연도", "사하구 장림동 vs 감천동 공장 평균 연면적",
          d010_agg(f"""AVG({n('A14')}) FILTER (WHERE {a4('장림동')}) AS jangnim_avg,
                       AVG({n('A14')}) FILTER (WHERE {a4('감천동')}) AS gamcheon_avg,
                       COUNT(*) FILTER (WHERE {a4('장림동')})::bigint AS jangnim_n,
                       COUNT(*) FILTER (WHERE {a4('감천동')})::bigint AS gamcheon_n""",
                   f"\"A9\"='공장' AND ({a4('장림동')} OR {a4('감천동')})"), "compare"),
        C("Q343", "비교연도", "남구 대연동과 문현동 중 15층 이상 공동주택 채수 비교",
          d010_agg(f"""COUNT(*) FILTER (WHERE {a4('대연동')})::bigint AS daeyeon_n,
                       COUNT(*) FILTER (WHERE {a4('문현동')})::bigint AS munhyeon_n""",
                   f"\"A9\"='공동주택' AND {n('A26')}>=15 AND ({a4('대연동')} OR {a4('문현동')})"), "compare"),
        C("Q344", "비교연도", "금정구 구서동 vs 장전동 공동주택 평균 높이",
          d010_agg(f"""AVG({n('A16')}) FILTER (WHERE {a4('구서동')}) AS guseo_h,
                       AVG({n('A16')}) FILTER (WHERE {a4('장전동')}) AS jangjeon_h""",
                   f"\"A9\"='공동주택' AND ({a4('구서동')} OR {a4('장전동')})"), "compare"),
        C("Q345", "비교연도", "부산진구 부전동 vs 전포동 제2종근린생활시설 채수",
          d010_agg(f"""COUNT(*) FILTER (WHERE {a4('부전동')})::bigint AS bujeon_n,
                       COUNT(*) FILTER (WHERE {a4('전포동')})::bigint AS jeonpo_n""",
                   f"\"A9\"='제2종근린생활시설' AND ({a4('부전동')} OR {a4('전포동')})"), "compare"),
        C("Q346", "비교연도", "강서구 명지동 vs 대저1동 공장 연면적 합계",
          d010_agg(f"""SUM({n('A14')}) FILTER (WHERE {a4('명지동')}) AS myongji_sum,
                       SUM({n('A14')}) FILTER (WHERE {a4('대저1동')}) AS daejeo_sum""",
                   f"\"A9\"='공장' AND ({a4('명지동')} OR {a4('대저1동')})"), "compare"),
        C("Q347", "비교연도", "영도구 동삼동 vs 청학동 공동주택 평균 층수",
          d010_agg(f"""AVG({n('A26')}) FILTER (WHERE {a4('동삼동')}) AS dongsam_fl,
                       AVG({n('A26')}) FILTER (WHERE {a4('청학동')}) AS cheonghak_fl""",
                   f"\"A9\"='공동주택' AND ({a4('동삼동')} OR {a4('청학동')})"), "compare"),
        C("Q348", "비교연도", "북구 구포동 vs 화명동 2000년 이후 사용승인 공동주택 채수",
          d010_agg(f"""COUNT(*) FILTER (WHERE {a4('구포동')})::bigint AS gupo_n,
                       COUNT(*) FILTER (WHERE {a4('화명동')})::bigint AS hwamyeong_n""",
                   f"\"A9\"='공동주택' AND {year_ge('A13', 2000)} AND ({a4('구포동')} OR {a4('화명동')})"), "compare"),
        C("Q349", "비교연도", "기장군 vs 강서구 산지 건물 비율 %",
          d010_agg("""COUNT(*) FILTER (WHERE "A4" LIKE '%기장군%' AND TRIM(COALESCE("A7",''))='산')::float8
                      / NULLIF(COUNT(*) FILTER (WHERE "A4" LIKE '%기장군%'),0)*100 AS gijang_pct,
                      COUNT(*) FILTER (WHERE "A4" LIKE '%강서구%' AND TRIM(COALESCE("A7",''))='산')::float8
                      / NULLIF(COUNT(*) FILTER (WHERE "A4" LIKE '%강서구%'),0)*100 AS gangseo_pct""",
                   f"{gu('기장군')} OR {gu('강서구')}"), "compare", "%"),
        C("Q350", "비교연도", "해운대구 중동 vs 우동 높이 100m 이상 건물 채수",
          d010_agg(f"""COUNT(*) FILTER (WHERE {a4('중동')})::bigint AS jung_n,
                       COUNT(*) FILTER (WHERE {a4('우동')})::bigint AS u_n""",
                   f"{gu('해운대구')} AND {n('A16')}>=100 AND ({a4('중동')} OR {a4('우동')})"), "compare"),
        C("Q351", "비교연도", "동래구 온천동 공동주택 중 1980년대 vs 2010년대 사용승인 채수",
          d010_agg(f"""COUNT(*) FILTER (WHERE {year_between('A13', 1980, 1989)})::bigint AS n_1980s,
                       COUNT(*) FILTER (WHERE {year_between('A13', 2010, 2019)})::bigint AS n_2010s""",
                   f"{a4('온천동')} AND \"A9\"='공동주택'"), "compare"),
        C("Q352", "비교연도", "남구 공동주택 1990년대 사용승인과 2000년대 사용승인의 평균 층수",
          d010_agg(f"""AVG({n('A26')}) FILTER (WHERE {year_between('A13', 1990, 1999)}) AS fl_1990s,
                       AVG({n('A26')}) FILTER (WHERE {year_between('A13', 2000, 2009)}) AS fl_2000s""",
                   f"{gu('남구')} AND \"A9\"='공동주택'"), "compare"),
        C("Q353", "비교연도", "수영구 광안동 숙박시설 연면적 80평 이상과 미만 채수",
          d010_agg(f"""COUNT(*) FILTER (WHERE {n('A14')} >= {p80})::bigint AS ge_80py,
                       COUNT(*) FILTER (WHERE {n('A14')} < {p80})::bigint AS lt_80py""",
                   f"{a4('광안동')} AND \"A9\"='숙박시설' AND {n('A14')} IS NOT NULL"), "compare"),
        C("Q354", "비교연도", "사상구 감전동 vs 학장동 공장 중 연면적 2000㎡ 이상 채수",
          d010_agg(f"""COUNT(*) FILTER (WHERE {a4('감전동')})::bigint AS gamjeon_n,
                       COUNT(*) FILTER (WHERE {a4('학장동')})::bigint AS hakjang_n""",
                   f"\"A9\"='공장' AND {n('A14')}>=2000 AND ({a4('감전동')} OR {a4('학장동')})"), "compare"),
        C("Q355", "비교연도", "서구 암남동 vs 충무동 공동주택 채수와 평균 높이",
          d010_agg(f"""COUNT(*) FILTER (WHERE {a4('암남동')})::bigint AS amnam_n,
                       AVG({n('A16')}) FILTER (WHERE {a4('암남동')}) AS amnam_h,
                       COUNT(*) FILTER (WHERE {a4('충무동')})::bigint AS chungmu_n,
                       AVG({n('A16')}) FILTER (WHERE {a4('충무동')}) AS chungmu_h""",
                   f"\"A9\"='공동주택' AND ({a4('암남동')} OR {a4('충무동')})"), "compare"),
        C("Q356", "비교연도", "중구 vs 동구 업무시설 평균 연면적",
          d010_agg(f"""AVG({n('A14')}) FILTER (WHERE {gu('중구')}) AS jung_avg,
                       AVG({n('A14')}) FILTER (WHERE {gu('동구')}) AS dong_avg,
                       COUNT(*) FILTER (WHERE {gu('중구')})::bigint AS jung_n,
                       COUNT(*) FILTER (WHERE {gu('동구')})::bigint AS dong_n""",
                   f"\"A9\"='업무시설' AND ({gu('중구')} OR {gu('동구')})"), "compare"),
        C("Q357", "비교연도", "해운대구 공동주택 중 사용승인 2015년 이후 vs 이전의 평균 높이",
          d010_agg(f"""AVG({n('A16')}) FILTER (WHERE {year_ge('A13', 2015)}) AS h_after,
                       AVG({n('A16')}) FILTER (WHERE "A13"::text ~ '^[0-9]{{4}}'
                            AND LEFT(regexp_replace("A13"::text,'[^0-9]','','g'),4) < '2015') AS h_before""",
                   f"{gu('해운대구')} AND \"A9\"='공동주택'"), "compare"),
        C("Q358", "비교연도", "금정구 단독주택 경과 40년 이상 vs 10년 미만 채수",
          d010_agg(f"""COUNT(*) FILTER (WHERE {age_gte('A13', 40)})::bigint AS old40,
                       COUNT(*) FILTER (WHERE "A13" ~ '^[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}$'
                         AND "A13"::date > (CURRENT_DATE - INTERVAL '10 years'))::bigint AS young10""",
                   f"{gu('금정구')} AND \"A9\"='단독주택'"), "compare"),
        C("Q359", "비교연도", "기장군 정관 일대 vs 기장읍 공동주택 채수",
          d010_agg("""COUNT(*) FILTER (WHERE "A4" LIKE '%정관%')::bigint AS jeonggwan_n,
                      COUNT(*) FILTER (WHERE "A4" LIKE '%기장읍%')::bigint AS gijang_eup_n""",
                   f"{gu('기장군')} AND \"A9\"='공동주택'"), "compare"),
        C("Q360", "비교연도", "연제구 연산동 공동주택 vs 업무시설 연면적 합계",
          d010_agg(f"""SUM({n('A14')}) FILTER (WHERE "A9"='공동주택') AS apt_sum,
                       SUM({n('A14')}) FILTER (WHERE "A9"='업무시설') AS office_sum""",
                   f"{a4('연산동')} AND \"A9\" IN ('공동주택','업무시설')"), "compare"),
        C("Q361", "비교연도", "사하구 다대동 vs 괴정동 공동주택 20층 이상 채수",
          d010_agg(f"""COUNT(*) FILTER (WHERE {a4('다대동')})::bigint AS dadae_n,
                       COUNT(*) FILTER (WHERE {a4('괴정동')})::bigint AS goejeong_n""",
                   f"\"A9\"='공동주택' AND {n('A26')}>=20 AND ({a4('다대동')} OR {a4('괴정동')})"), "compare"),
        C("Q362", "비교연도", "부산 구별 높이 100m 이상 건물 수 상위 5구",
          f"""SELECT split_part("A4",' ',2) AS gu_name, COUNT(*)::bigint AS n FROM "{D010}"
              WHERE {n('A16')}>=100 AND "A4" LIKE '부산광역시 %'
              GROUP BY 1 ORDER BY n DESC LIMIT 5""", "group"),
        C("Q363", "비교연도", "동래구 vs 금정구 D198 집합건축물 채수",
          f"""SELECT
                (SELECT COUNT(*) FROM "{D198_DR}" WHERE "A10"='집합건축물')::bigint AS dongnae_n,
                (SELECT COUNT(*) FROM "{D198_GJ}" WHERE "A10"='집합건축물')::bigint AS geumjeong_n""",
          "compare"),
        C("Q364", "비교연도", "해운대구 반여동 vs 반송동 공동주택 평균 연면적",
          d010_agg(f"""AVG({n('A14')}) FILTER (WHERE {a4('반여동')}) AS banye_avg,
                       AVG({n('A14')}) FILTER (WHERE {a4('반송동')}) AS bansong_avg""",
                   f"\"A9\"='공동주택' AND ({a4('반여동')} OR {a4('반송동')})"), "compare"),
        C("Q365", "비교연도", "남구 용호동 vs 감만동 교육연구시설 채수",
          d010_agg(f"""COUNT(*) FILTER (WHERE {a4('용호동')})::bigint AS yongho_n,
                       COUNT(*) FILTER (WHERE {a4('감만동')})::bigint AS gamman_n""",
                   f"\"A9\"='교육연구시설' AND ({a4('용호동')} OR {a4('감만동')})"), "compare"),
        C("Q366", "비교연도", "수영구 민락동 vs 광안동 숙박시설 평균 높이",
          d010_agg(f"""AVG({n('A16')}) FILTER (WHERE {a4('민락동')}) AS millak_h,
                       AVG({n('A16')}) FILTER (WHERE {a4('광안동')}) AS gwangan_h""",
                   f"\"A9\"='숙박시설' AND ({a4('민락동')} OR {a4('광안동')})"), "compare"),
        C("Q367", "비교연도", "강서구 지사동 vs 녹산동 공장 채수와 평균 연면적",
          d010_agg(f"""COUNT(*) FILTER (WHERE {a4('지사동')})::bigint AS jisa_n,
                       AVG({n('A14')}) FILTER (WHERE {a4('지사동')}) AS jisa_avg,
                       COUNT(*) FILTER (WHERE {a4('녹산동')})::bigint AS noksan_n,
                       AVG({n('A14')}) FILTER (WHERE {a4('녹산동')}) AS noksan_avg""",
                   f"\"A9\"='공장' AND ({a4('지사동')} OR {a4('녹산동')})"), "compare"),
        C("Q368", "비교연도", "부산진구 가야동 vs 개금동 공동주택 10층 이상 채수",
          d010_agg(f"""COUNT(*) FILTER (WHERE {a4('가야동')})::bigint AS gaya_n,
                       COUNT(*) FILTER (WHERE {a4('개금동')})::bigint AS gegeum_n""",
                   f"\"A9\"='공동주택' AND {n('A26')}>=10 AND ({a4('가야동')} OR {a4('개금동')})"), "compare"),
        C("Q369", "비교연도", "연제구 거제동 vs 연산동 업무시설 채수",
          d010_agg(f"""COUNT(*) FILTER (WHERE {a4('거제동')})::bigint AS geoje_n,
                       COUNT(*) FILTER (WHERE {a4('연산동')})::bigint AS yeonsan_n""",
                   f"\"A9\"='업무시설' AND ({a4('거제동')} OR {a4('연산동')})"), "compare"),
        C("Q370", "비교연도", "북구 덕천동 vs 만덕동 공동주택 평균 높이",
          d010_agg(f"""AVG({n('A16')}) FILTER (WHERE {a4('덕천동')}) AS deokcheon_h,
                       AVG({n('A16')}) FILTER (WHERE {a4('만덕동')}) AS mandeok_h""",
                   f"\"A9\"='공동주택' AND ({a4('덕천동')} OR {a4('만덕동')})"), "compare"),
        C("Q371", "비교연도", "사하구 신평동 vs 하단동 공장 연면적 합계",
          d010_agg(f"""SUM({n('A14')}) FILTER (WHERE {a4('신평동')}) AS sinpyeong_sum,
                       SUM({n('A14')}) FILTER (WHERE {a4('하단동')}) AS hadan_sum""",
                   f"\"A9\"='공장' AND ({a4('신평동')} OR {a4('하단동')})"), "compare"),
        C("Q372", "비교연도", "금정구 사용승인 연도 구간별 공동주택 수(1970s~2010s)",
          f"""SELECT (LEFT(regexp_replace("A13"::text,'[^0-9]','','g'),4)::int / 10)*10 AS decade,
                     COUNT(*)::bigint AS n
              FROM "{D010}"
              WHERE {gu('금정구')} AND "A9"='공동주택' AND "A13"::text ~ '^[0-9]{{4}}'
                AND LEFT(regexp_replace("A13"::text,'[^0-9]','','g'),4)::int BETWEEN 1970 AND 2019
              GROUP BY 1 ORDER BY 1""", "group"),
        C("Q373", "비교연도", "해운대구 재송동 vs 좌동 공동주택 지상 20층 이상 채수",
          d010_agg(f"""COUNT(*) FILTER (WHERE {a4('재송동')})::bigint AS jaesong_n,
                       COUNT(*) FILTER (WHERE {a4('좌동')})::bigint AS jwa_n""",
                   f"\"A9\"='공동주택' AND {n('A26')}>=20 AND ({a4('재송동')} OR {a4('좌동')})"), "compare"),
        C("Q374", "비교연도", "동래구 명장동 vs 안락동 다세대·다가구(D198 세부용도) 채수",
          f"""SELECT COUNT(*) FILTER (WHERE {a4('명장동')})::bigint AS myeongjang_n,
                     COUNT(*) FILTER (WHERE {a4('안락동')})::bigint AS allak_n
              FROM "{D198_DR}"
              WHERE "A27" IN ('다세대주택','다가구주택') AND ({a4('명장동')} OR {a4('안락동')})""",
          "compare"),
        C("Q375", "비교연도", "영도구 vs 서구 위반건축물 채수",
          d010_agg(f"""COUNT(*) FILTER (WHERE {gu('영도구')})::bigint AS yeongdo_n,
                       COUNT(*) FILTER (WHERE {gu('서구')})::bigint AS seo_n""",
                   f"TRIM(\"A20\"::text)='Y' AND ({gu('영도구')} OR {gu('서구')})"), "compare"),
        C("Q376", "비교연도", "남구 우암동 vs 문현동 제1종근린생활시설 채수",
          d010_agg(f"""COUNT(*) FILTER (WHERE {a4('우암동')})::bigint AS uam_n,
                       COUNT(*) FILTER (WHERE {a4('문현동')})::bigint AS munhyeon_n""",
                   f"\"A9\"='제1종근린생활시설' AND ({a4('우암동')} OR {a4('문현동')})"), "compare"),
        C("Q377", "비교연도", "기장군 철마면 vs 일광읍 단독주택 채수",
          d010_agg("""COUNT(*) FILTER (WHERE "A4" LIKE '%철마%')::bigint AS cheolma_n,
                      COUNT(*) FILTER (WHERE "A4" LIKE '%일광%')::bigint AS ilgwang_n""",
                   f"{gu('기장군')} AND \"A9\"='단독주택'"), "compare"),
        C("Q378", "비교연도", "부산진구 양정동 vs 전포동 업무시설 평균 높이",
          d010_agg(f"""AVG({n('A16')}) FILTER (WHERE {a4('양정동')}) AS yangjeong_h,
                       AVG({n('A16')}) FILTER (WHERE {a4('전포동')}) AS jeonpo_h""",
                   f"\"A9\"='업무시설' AND ({a4('양정동')} OR {a4('전포동')})"), "compare"),
        C("Q379", "비교연도", "해운대구 송정동 vs 중동 숙박시설 채수",
          d010_agg(f"""COUNT(*) FILTER (WHERE {a4('송정동')})::bigint AS songjeong_n,
                       COUNT(*) FILTER (WHERE {a4('중동')})::bigint AS jung_n""",
                   f"{gu('해운대구')} AND \"A9\"='숙박시설' AND ({a4('송정동')} OR {a4('중동')})"), "compare"),
        C("Q380", "비교연도", "금정구 vs 동래구 교육연구시설 대지면적 합계(D010)",
          d010_agg(f"""SUM({n('A15')}) FILTER (WHERE {gu('금정구')}) AS geumjeong_land,
                       SUM({n('A15')}) FILTER (WHERE {gu('동래구')}) AS dongnae_land""",
                   f"\"A9\"='교육연구시설' AND ({gu('금정구')} OR {gu('동래구')})"), "compare"),
    ]


def _fu(sid: str, session: str, parent: str | None, cat: str, q: str, sql: str, kind: str = "count", unit: str = "채") -> object:
    return C(sid, cat, q, sql, kind, unit=unit, session=session, parent=parent)


def followups() -> list:
    """다턴 후속 120문항 (30세션 × 4턴). 정답 SQL은 선행 조건을 누적한다."""
    n = num
    out: list = []

    def add(session: str, turns: list[tuple]):
        """turns: (id, q, sql, kind, unit). parent is previous id."""
        prev = None
        for i, (qid, q, sql, kind, unit) in enumerate(turns):
            cat = "후속앵커" if i == 0 else "후속"
            out.append(_fu(qid, session, prev, cat, q, sql, kind, unit))
            prev = qid

    # F01 해운대 고층 아파트
    w = f"{gu('해운대구')} AND \"A9\"='공동주택' AND {n('A16')}>=50"
    w2 = w + f" AND {n('A14')}>=8000"
    add("F01", [
        ("Q381", "해운대구 공동주택 중 높이 50m 이상인 건물 이름과 높이",
         d010_list(w, '"A24","A4","A16","A14"', n("A16"), 20), "list", "채"),
        ("Q382", "그중 연면적 8000㎡ 이상만",
         d010_cnt(w2), "count", "채"),
        ("Q383", "그 건물들의 평균 높이와 평균 연면적",
         d010_agg(f"COUNT(*)::bigint AS n, AVG({n('A16')}) AS avg_h, AVG({n('A14')}) AS avg_gfa", w2), "scalar", ""),
        ("Q384", "그중 가장 높은 건물의 이름과 지번",
         d010_list(w2, '"A24","A4","A5","A16"', n("A16"), 1), "scalar", ""),
    ])
    # F02 수영 숙박
    w = f"{gu('수영구')} AND \"A9\"='숙박시설' AND {n('A14')}>=1000"
    w2 = w + f" AND {n('A16')}>=20"
    add("F02", [
        ("Q385", "수영구 숙박시설 중 연면적 1000㎡ 이상인 이름과 연면적",
         d010_list(w, '"A24","A4","A14","A16"', n("A14"), 20), "list", "채"),
        ("Q386", "그중 높이 20m 이상만 몇 채야?",
         d010_cnt(w2), "count", "채"),
        ("Q387", "그 건물들 연면적 합계",
         d010_agg(f"COUNT(*)::bigint AS n, SUM({n('A14')}) AS sum_gfa", w2), "scalar", ""),
        ("Q388", "연면적이 가장 큰 것의 법정동과 지번",
         d010_list(w2, '"A24","A4","A5","A14"', n("A14"), 1), "scalar", ""),
    ])
    # F03 금정 철근 공동주택
    w = f"{gu('금정구')} AND \"A9\"='공동주택' AND {rc('A11','%철근콘크리트%')} AND {n('A26')}>=12"
    w2 = w + f" AND {year_ge('A13', 2000)}"
    add("F03", [
        ("Q389", "금정구 철근콘크리트 공동주택 중 12층 이상인 채수",
         d010_cnt(w), "count", "채"),
        ("Q390", "그중 2000년 이후 사용승인만",
         d010_cnt(w2), "count", "채"),
        ("Q391", "그 집합의 평균 층수",
         d010_agg(f"COUNT(*)::bigint AS n, AVG({n('A26')}) AS avg_fl", w2), "scalar", ""),
        ("Q392", "층수가 가장 많은 건물 이름",
         d010_list(w2, '"A24","A4","A26","A16"', n("A26"), 1), "scalar", ""),
    ])
    # F04 사하 창고
    w = f"{gu('사하구')} AND \"A9\"='창고시설' AND {n('A14')}>=2000"
    w2 = w + f" AND {n('A12')}>=800"
    add("F04", [
        ("Q393", "사하구 연면적 2000㎡ 이상 창고 이름과 연면적",
         d010_list(w, '"A24","A4","A14","A12"', n("A14"), 20), "list", "채"),
        ("Q394", "그중 건축면적 800㎡ 이상만",
         d010_cnt(w2), "count", "채"),
        ("Q395", "건물명과 지번도 같이",
         d010_list(w2, '"A24","A4","A5","A14","A12"', n("A14"), 20), "list", "채"),
        ("Q396", "그 중 연면적 합계",
         d010_agg(f"SUM({n('A14')}) AS sum_gfa, COUNT(*)::bigint AS n", w2), "scalar", ""),
    ])
    # F05 강서 공장 산업단지
    w = f"{bgu('강서구')} AND b.\"A9\"='공장' AND {bnum('A14')}>=3000"
    w2 = w + f" AND {industrial_exists()}"
    add("F05", [
        ("Q397", "강서구 공장 중 연면적 3000㎡ 이상인 채수",
         d010_cnt(f"{gu('강서구')} AND \"A9\"='공장' AND {n('A14')}>=3000"), "count", "채"),
        ("Q398", "그중 산업단지 안에 있는 것만",
         f'SELECT COUNT(*)::bigint AS n FROM "{D010}" b WHERE {w2}', "count", "채"),
        ("Q399", "그 공장들 평균 연면적",
         f'SELECT COUNT(*)::bigint AS n, AVG({bnum("A14")}) AS avg_gfa FROM "{D010}" b WHERE {w2}', "scalar", ""),
        ("Q400", "연면적이 가장 큰 공장 이름",
         f"""SELECT b."A24", b."A4", b."A14" FROM "{D010}" b WHERE {w2}
             ORDER BY {bnum('A14')} DESC NULLS LAST LIMIT 1""", "scalar", ""),
    ])
    # F06 남구 공동주택 연도
    w = f"{gu('남구')} AND \"A9\"='공동주택' AND {n('A26')}>=15"
    w2 = w + f" AND {year_ge('A13', 2000)}"
    add("F06", [
        ("Q401", "남구 15층 이상 공동주택 채수", d010_cnt(w), "count", "채"),
        ("Q402", "그중 2000년 이후 사용승인만", d010_cnt(w2), "count", "채"),
        ("Q403", "그 건물들 평균 높이",
         d010_agg(f"COUNT(*)::bigint AS n, AVG({n('A16')}) AS avg_h", w2), "scalar", ""),
        ("Q404", "가장 높은 것의 이름과 층수",
         d010_list(w2, '"A24","A4","A16","A26"', n("A16"), 1), "scalar", ""),
    ])
    # F07 광안 숙박 후속
    w = f"{a4('광안동')} AND \"A9\"='숙박시설'"
    w2 = w + f" AND {n('A16')}>=18 AND {n('A14')}>=800"
    add("F07", [
        ("Q405", "광안동 숙박시설 목록(연면적 큰 순 15개)",
         d010_list(w, '"A24","A4","A14","A16"', n("A14"), 15), "list", "채"),
        ("Q406", "그중 높이 18m 이상이고 연면적 800㎡ 이상만", d010_cnt(w2), "count", "채"),
        ("Q407", "그 건물들 지하층이 있는 것은 몇 채야?",
         d010_cnt(w2 + f" AND {n('A27')}>=1"), "count", "채"),
        ("Q408", "남은 건물 평균 연면적",
         d010_agg(f"AVG({n('A14')}) AS avg_gfa, COUNT(*)::bigint AS n", w2 + f" AND {n('A27')}>=1"), "scalar", ""),
    ])
    # F08 장림 공장
    w = f"{a4('장림동')} AND \"A9\"='공장' AND {n('A14')}>=2000"
    w2 = w + f" AND {rc('A11','%철골%')}"
    add("F08", [
        ("Q409", "장림동 연면적 2000㎡ 이상 공장 채수", d010_cnt(w), "count", "채"),
        ("Q410", "그중 철골구조만", d010_cnt(w2), "count", "채"),
        ("Q411", "이름과 구조·연면적",
         d010_list(w2, '"A24","A11","A14","A4"', n("A14"), 15), "list", "채"),
        ("Q412", "연면적 합계",
         d010_agg(f"SUM({n('A14')}) AS sum_gfa, COUNT(*)::bigint AS n", w2), "scalar", ""),
    ])
    # F09 우동 초고층
    w = f"{a4('우동')} AND {n('A16')}>=80"
    w2 = w + " AND \"A9\"='공동주택'"
    add("F09", [
        ("Q413", "우동에서 높이 80m 이상 건물 이름과 용도·높이",
         d010_list(w, '"A24","A9","A16","A26"', n("A16"), 20), "list", "채"),
        ("Q414", "그중 공동주택만", d010_cnt(w2), "count", "채"),
        ("Q415", "그 아파트들의 평균 층수",
         d010_agg(f"AVG({n('A26')}) AS avg_fl, COUNT(*)::bigint AS n", w2), "scalar", ""),
        ("Q416", "가장 높은 아파트 지번",
         d010_list(w2, '"A24","A5","A4","A16"', n("A16"), 1), "scalar", ""),
    ])
    # F10 연산 행정동
    w = f"""{admin_eq('연산동')} AND b."A9"='공동주택' AND {bnum('A16')}>=40"""
    w2 = w + f" AND {bnum('A14')}>=3000"
    add("F10", [
        ("Q417", "연산동 행정경계 안 공동주택 중 높이 40m 이상",
         f"""SELECT b."A24", b."A16", b."A14" FROM "{D010}" b JOIN "{BND}" d ON ST_Intersects(b.geometry, d.geometry)
             WHERE {w} ORDER BY {bnum('A16')} DESC NULLS LAST LIMIT 20""", "list", "채"),
        ("Q418", "그중 연면적 3000㎡ 이상만 몇 채?",
         f'SELECT COUNT(*)::bigint AS n FROM "{D010}" b JOIN "{BND}" d ON ST_Intersects(b.geometry, d.geometry) WHERE {w2}', "count", "채"),
        ("Q419", "평균 높이",
         f'SELECT COUNT(*)::bigint AS n, AVG({bnum("A16")}) AS avg_h FROM "{D010}" b JOIN "{BND}" d ON ST_Intersects(b.geometry, d.geometry) WHERE {w2}', "scalar", ""),
        ("Q420", "가장 높은 건물명",
         f"""SELECT b."A24", b."A16", b."A5" FROM "{D010}" b JOIN "{BND}" d ON ST_Intersects(b.geometry, d.geometry)
             WHERE {w2} ORDER BY {bnum('A16')} DESC NULLS LAST LIMIT 1""", "scalar", ""),
    ])
    # F11 동래 D198 집합
    w = f'"A10"=\'집합건축물\' AND {n("A30")}>=25'
    w2 = w + " AND \"A25\"='공동주택'"
    add("F11", [
        ("Q421", "동래구 집합건축물 중 건물높이 25m 이상인 채수",
         f'SELECT COUNT(*)::bigint AS n FROM "{D198_DR}" WHERE {w}', "count", "채"),
        ("Q422", "그중 주요용도가 공동주택인 것만",
         f'SELECT COUNT(*)::bigint AS n FROM "{D198_DR}" WHERE {w2}', "count", "채"),
        ("Q423", "평균 지상층",
         f'SELECT COUNT(*)::bigint AS n, AVG({n("A31")}) AS avg_fl FROM "{D198_DR}" WHERE {w2}', "scalar", ""),
        ("Q424", "가장 높은 건물명",
         f"""SELECT "A13" AS name, {n('A30')} AS h, "A4" FROM "{D198_DR}" WHERE {w2}
             ORDER BY {n('A30')} DESC NULLS LAST LIMIT 1""", "scalar", ""),
    ])
    # F12 금정 D198 아파트 세부
    w = f'"A27"=\'아파트\' AND {n("A31")}>=10'
    w2 = w + f" AND {year_ge('A34', 2000)}"
    add("F12", [
        ("Q425", "금정구 세부용도 아파트 중 10층 이상",
         f'SELECT COUNT(*)::bigint AS n FROM "{D198_GJ}" WHERE {w}', "count", "채"),
        ("Q426", "그중 사용승인 2000년 이후만",
         f'SELECT COUNT(*)::bigint AS n FROM "{D198_GJ}" WHERE {w2}', "count", "채"),
        ("Q427", "평균 건물연면적",
         f'SELECT AVG({n("A19")}) AS avg_gfa, COUNT(*)::bigint AS n FROM "{D198_GJ}" WHERE {w2}', "scalar", ""),
        ("Q428", "연면적 상위 5 이름",
         f"""SELECT "A13" AS name, {n('A19')} AS gfa, "A4" FROM "{D198_GJ}" WHERE {w2}
             ORDER BY {n('A19')} DESC NULLS LAST LIMIT 5""", "list", "채"),
    ])
    # F13 위반건축물
    w = f"{gu('부산진구')} AND TRIM(\"A20\"::text)='Y'"
    w2 = w + f" AND {n('A14')}>=500"
    add("F13", [
        ("Q429", "부산진구 위반건축물 채수", d010_cnt(w), "count", "채"),
        ("Q430", "그중 연면적 500㎡ 이상만", d010_cnt(w2), "count", "채"),
        ("Q431", "용도별 건수 상위 6",
         f"""SELECT "A9" AS usage, COUNT(*)::bigint AS n FROM "{D010}" WHERE {w2}
             GROUP BY 1 ORDER BY n DESC LIMIT 6""", "group", "채"),
        ("Q432", "연면적이 가장 큰 위반건축물 이름·용도",
         d010_list(w2, '"A24","A9","A14","A4"', n("A14"), 1), "scalar", ""),
    ])
    # F14 산지
    w = f"{gu('기장군')} AND TRIM(COALESCE(\"A7\",''))='산'"
    w2 = w + " AND \"A9\"='단독주택'"
    add("F14", [
        ("Q433", "기장군 산지 건물 채수", d010_cnt(w), "count", "채"),
        ("Q434", "그중 단독주택만", d010_cnt(w2), "count", "채"),
        ("Q435", "평균 건축면적",
         d010_agg(f"AVG({n('A12')}) AS avg_area, COUNT(*)::bigint AS n", w2), "scalar", ""),
        ("Q436", "건축면적 상위 5",
         d010_list(w2, '"A24","A4","A12","A5"', n("A12"), 5), "list", "채"),
    ])
    # F15 건폐율
    w = f"{gu('연제구')} AND \"A9\"='공동주택' AND {n('A17')}>=30"
    w2 = w + f" AND {n('A18')}>=200"
    add("F15", [
        ("Q437", "연제구 공동주택 중 건폐율 30% 이상", d010_cnt(w), "count", "채"),
        ("Q438", "그중 용적율 200% 이상만", d010_cnt(w2), "count", "채"),
        ("Q439", "평균 건폐율과 평균 용적율",
         d010_agg(f"AVG({n('A17')}) AS avg_cov, AVG({n('A18')}) AS avg_far, COUNT(*)::bigint AS n", w2), "scalar", ""),
        ("Q440", "용적율이 가장 큰 건물명",
         d010_list(w2, '"A24","A18","A17","A4"', n("A18"), 1), "scalar", ""),
    ])
    # F16 지하층
    w = f"{gu('해운대구')} AND {n('A27')}>=2"
    w2 = w + " AND \"A9\"='공동주택'"
    add("F16", [
        ("Q441", "해운대구 지하 2층 이상 건물 채수", d010_cnt(w), "count", "채"),
        ("Q442", "그중 공동주택만", d010_cnt(w2), "count", "채"),
        ("Q443", "평균 지상층",
         d010_agg(f"AVG({n('A26')}) AS avg_fl, COUNT(*)::bigint AS n", w2), "scalar", ""),
        ("Q444", "지상층이 가장 많은 이름",
         d010_list(w2, '"A24","A26","A27","A4"', n("A26"), 1), "scalar", ""),
    ])
    # F17 북구 교육
    w = f"{gu('북구')} AND \"A9\"='교육연구시설' AND {n('A15')}>=1500"
    w2 = w + f" AND {n('A16')}>=15"
    add("F17", [
        ("Q445", "북구 교육연구시설 중 대지면적 1500㎡ 이상",
         d010_list(w, '"A24","A15","A16","A4"', n("A15"), 15), "list", "채"),
        ("Q446", "그중 높이 15m 이상만", d010_cnt(w2), "count", "채"),
        ("Q447", "대지면적 합계",
         d010_agg(f"SUM({n('A15')}) AS sum_land, COUNT(*)::bigint AS n", w2), "scalar", ""),
        ("Q448", "대지면적이 가장 큰 이름",
         d010_list(w2, '"A24","A15","A4","A5"', n("A15"), 1), "scalar", ""),
    ])
    # F18 영도 공동주택 경과년
    w = f"{gu('영도구')} AND \"A9\"='공동주택' AND {age_gte('A13', 25)}"
    w2 = w + f" AND {n('A26')}>=10"
    add("F18", [
        ("Q449", "영도구 지어진지 25년 넘은 공동주택 채수", d010_cnt(w), "count", "채"),
        ("Q450", "그중 10층 이상만", d010_cnt(w2), "count", "채"),
        ("Q451", "평균 연면적",
         d010_agg(f"AVG({n('A14')}) AS avg_gfa, COUNT(*)::bigint AS n", w2), "scalar", ""),
        ("Q452", "가장 오래된(사용승인 빠른) 건물명과 사용승인일",
         f"""SELECT "A24","A13","A4" FROM "{D010}" WHERE {w2} AND "A13" ~ '^[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}$'
             ORDER BY "A13"::date ASC LIMIT 1""", "scalar", ""),
    ])
    # F19 사상 공장
    w = f"{gu('사상구')} AND \"A9\"='공장' AND {n('A14')}>=2500"
    w2 = w + f" AND {n('A16')}>=12"
    add("F19", [
        ("Q453", "사상구 연면적 2500㎡ 이상 공장 채수", d010_cnt(w), "count", "채"),
        ("Q454", "그중 높이 12m 이상만", d010_cnt(w2), "count", "채"),
        ("Q455", "구조별 건수",
         f"""SELECT "A11" AS structure, COUNT(*)::bigint AS n FROM "{D010}" WHERE {w2}
             GROUP BY 1 ORDER BY n DESC""", "group", "채"),
        ("Q456", "연면적 최대 공장 이름",
         d010_list(w2, '"A24","A14","A11","A4"', n("A14"), 1), "scalar", ""),
    ])
    # F20 중동 엘시티 계열
    w = f"{a4('중동')} AND {gu('해운대구')} AND {n('A16')}>=150"
    w2 = w + " AND \"A9\" IN ('공동주택','숙박시설')"
    add("F20", [
        ("Q457", "해운대 중동에서 높이 150m 이상 건물 이름과 높이·용도",
         d010_list(w, '"A24","A9","A16","A26"', n("A16"), 20), "list", "채"),
        ("Q458", "그중 공동주택 또는 숙박시설만", d010_cnt(w2), "count", "채"),
        ("Q459", "평균 층수",
         d010_agg(f"AVG({n('A26')}) AS avg_fl, COUNT(*)::bigint AS n", w2), "scalar", ""),
        ("Q460", "가장 높은 건물의 건물동명과 지번",
         d010_list(w2, '"A24","A25","A5","A16"', n("A16"), 1), "scalar", ""),
    ])
    # F21 대연 공동주택
    w = f"{a4('대연동')} AND \"A9\"='공동주택' AND {n('A14')}>=4000"
    w2 = w + f" AND {n('A26')}>=12"
    add("F21", [
        ("Q461", "대연동 연면적 4000㎡ 이상 공동주택",
         d010_list(w, '"A24","A14","A26","A16"', n("A14"), 15), "list", "채"),
        ("Q462", "그중 12층 이상만", d010_cnt(w2), "count", "채"),
        ("Q463", "높이 합계(1~500m)",
         d010_agg(f"SUM({n('A16')}) AS sum_h, COUNT(*)::bigint AS n", w2 + f" AND {n('A16')} BETWEEN 1 AND 500"), "scalar", ""),
        ("Q464", "층수 1위 이름",
         d010_list(w2, '"A24","A26","A4"', n("A26"), 1), "scalar", ""),
    ])
    # F22 구서 후속
    w = f"{a4('구서동')} AND \"A9\"='공동주택' AND {year_ge('A13', 2000)}"
    w2 = w + f" AND {n('A16')}>=40"
    add("F22", [
        ("Q465", "구서동 2000년 이후 사용승인 공동주택 채수", d010_cnt(w), "count", "채"),
        ("Q466", "그중 높이 40m 이상만", d010_cnt(w2), "count", "채"),
        ("Q467", "평균 연면적과 평균 높이",
         d010_agg(f"AVG({n('A14')}) AS avg_gfa, AVG({n('A16')}) AS avg_h, COUNT(*)::bigint AS n", w2), "scalar", ""),
        ("Q468", "연면적 상위 3 이름",
         d010_list(w2, '"A24","A14","A16","A4"', n("A14"), 3), "list", "채"),
    ])
    # F23 명지 산업단지
    w = f"{ba4('명지동')} AND {industrial_exists()}"
    w2 = w + " AND b.\"A9\"='공동주택'"
    add("F23", [
        ("Q469", "명지동에서 산업단지와 교차하는 건물 수",
         f'SELECT COUNT(*)::bigint AS n FROM "{D010}" b WHERE {w}', "count", "채"),
        ("Q470", "그중 공동주택만",
         f'SELECT COUNT(*)::bigint AS n FROM "{D010}" b WHERE {w2}', "count", "채"),
        ("Q471", "그 공동주택 평균 연면적",
         f'SELECT AVG({bnum("A14")}) AS avg_gfa, COUNT(*)::bigint AS n FROM "{D010}" b WHERE {w2}', "scalar", ""),
        ("Q472", "연면적 최대 공동주택명",
         f"""SELECT b."A24", b."A14", b."A5" FROM "{D010}" b WHERE {w2}
             ORDER BY {bnum('A14')} DESC NULLS LAST LIMIT 1""", "scalar", ""),
    ])
    # F24 온천 D198 상업
    w = f"{a4('온천동')} AND \"A29\"='상업용'"
    w2 = w + f" AND {n('A30')}>=15"
    add("F24", [
        ("Q473", "동래 온천동 상업용(D198) 채수",
         f'SELECT COUNT(*)::bigint AS n FROM "{D198_DR}" WHERE {w}', "count", "채"),
        ("Q474", "그중 건물높이 15m 이상만",
         f'SELECT COUNT(*)::bigint AS n FROM "{D198_DR}" WHERE {w2}', "count", "채"),
        ("Q475", "세부용도 상위 5",
         f"""SELECT "A27" AS detail, COUNT(*)::bigint AS n FROM "{D198_DR}" WHERE {w2}
             GROUP BY 1 ORDER BY n DESC LIMIT 5""", "group", "채"),
        ("Q476", "가장 높은 건물명",
         f"""SELECT "A13" AS name, {n('A30')} AS h, "A27" FROM "{D198_DR}" WHERE {w2}
             ORDER BY {n('A30')} DESC NULLS LAST LIMIT 1""", "scalar", ""),
    ])
    # F25 좌동 공동주택
    w = f"{a4('좌동')} AND \"A9\"='공동주택' AND {n('A26')}>=15"
    w2 = w + f" AND {n('A14')}>=6000"
    add("F25", [
        ("Q477", "좌동 15층 이상 공동주택 이름과 층수",
         d010_list(w, '"A24","A26","A16","A14"', n("A26"), 15), "list", "채"),
        ("Q478", "그중 연면적 6000㎡ 이상만", d010_cnt(w2), "count", "채"),
        ("Q479", "평균 높이",
         d010_agg(f"AVG({n('A16')}) AS avg_h, COUNT(*)::bigint AS n", w2), "scalar", ""),
        ("Q480", "지번 알려줘(연면적 1위)",
         d010_list(w2, '"A24","A5","A4","A14"', n("A14"), 1), "scalar", ""),
    ])
    # F26 전포 근생
    w = f"{a4('전포동')} AND \"A9\"='제2종근린생활시설' AND {n('A14')}>=400"
    w2 = w + f" AND {n('A26')}>=5"
    add("F26", [
        ("Q481", "전포동 제2종근린생활시설 중 연면적 400㎡ 이상", d010_cnt(w), "count", "채"),
        ("Q482", "그중 5층 이상만", d010_cnt(w2), "count", "채"),
        ("Q483", "평균 연면적",
         d010_agg(f"AVG({n('A14')}) AS avg_gfa, COUNT(*)::bigint AS n", w2), "scalar", ""),
        ("Q484", "연면적 상위 5 이름",
         d010_list(w2, '"A24","A14","A26","A4"', n("A14"), 5), "list", "채"),
    ])
    # F27 화명
    w = f"{a4('화명동')} AND \"A9\"='공동주택' AND {n('A16')}>=45"
    w2 = w + f" AND {year_ge('A13', 1995)}"
    add("F27", [
        ("Q485", "화명동 높이 45m 이상 공동주택 채수", d010_cnt(w), "count", "채"),
        ("Q486", "그중 1995년 이후 사용승인만", d010_cnt(w2), "count", "채"),
        ("Q487", "평균 층수와 평균 높이",
         d010_agg(f"AVG({n('A26')}) AS avg_fl, AVG({n('A16')}) AS avg_h, COUNT(*)::bigint AS n", w2), "scalar", ""),
        ("Q488", "가장 높은 건물 이름",
         d010_list(w2, '"A24","A16","A26","A4"', n("A16"), 1), "scalar", ""),
    ])
    # F28 기초구역 남구
    w = '"SIG_KOR_NM"=\'남구\' AND "BAS_AR">=0.2'
    w2 = w + " AND COALESCE(\"MVMN_RESN\",'') ILIKE '%최초%'"
    add("F28", [
        ("Q489", "남구 기초구역 중 면적(BAS_AR) 0.2 이상 개수",
         f'SELECT COUNT(*)::bigint AS n FROM "{BAS}" WHERE {w}', "count", "개"),
        ("Q490", "그중 이동사유가 최초생성인 것만",
         f'SELECT COUNT(*)::bigint AS n FROM "{BAS}" WHERE {w2}', "count", "개"),
        ("Q491", "면적 합계",
         f'SELECT SUM("BAS_AR") AS sum_ar, COUNT(*)::bigint AS n FROM "{BAS}" WHERE {w2}', "scalar", ""),
        ("Q492", "면적 최대 기초구역번호",
         f'SELECT "BAS_ID","BAS_AR","MVMN_RESN" FROM "{BAS}" WHERE {w2} ORDER BY "BAS_AR" DESC LIMIT 1', "scalar", ""),
    ])
    # F29 기장 공동주택 신축
    w = f"{gu('기장군')} AND \"A9\"='공동주택' AND {year_ge('A13', 2010)}"
    w2 = w + f" AND {n('A26')}>=15"
    add("F29", [
        ("Q493", "기장군 2010년 이후 사용승인 공동주택 채수", d010_cnt(w), "count", "채"),
        ("Q494", "그중 15층 이상만", d010_cnt(w2), "count", "채"),
        ("Q495", "법정동별 건수",
         f"""SELECT "A4" AS dong, COUNT(*)::bigint AS n FROM "{D010}" WHERE {w2}
             GROUP BY 1 ORDER BY n DESC""", "group", "채"),
        ("Q496", "가장 높은 건물 이름과 법정동",
         d010_list(w2, '"A24","A4","A16","A26"', n("A16"), 1), "scalar", ""),
    ])
    # F30 서구 의료
    w = f"{gu('서구')} AND \"A9\"='의료시설' AND {n('A14')}>=1500"
    w2 = w + f" AND {n('A16')}>=18"
    add("F30", [
        ("Q497", "서구 의료시설 중 연면적 1500㎡ 이상",
         d010_list(w, '"A24","A14","A16","A4"', n("A14"), 15), "list", "채"),
        ("Q498", "그중 높이 18m 이상만", d010_cnt(w2), "count", "채"),
        ("Q499", "연면적 합계와 건수",
         d010_agg(f"SUM({n('A14')}) AS sum_gfa, COUNT(*)::bigint AS n", w2), "scalar", ""),
        ("Q500", "연면적 1위 이름과 지번",
         d010_list(w2, '"A24","A5","A4","A14"', n("A14"), 1), "scalar", ""),
    ])
    return out


def build_new_cases() -> list:
    cases = (
        compound_and()
        + logic_or_not_between()
        + unused_attrs()
        + agg_ratio()
        + spatial_compound()
        + d198_exclusive()
        + compare_year()
        + followups()
    )
    return cases





