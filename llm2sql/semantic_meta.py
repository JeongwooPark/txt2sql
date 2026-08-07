"""한국어 semantic metadata (동의어·핵심 컬럼 힌트).

DB column_metadata에 synonyms 컬럼이 없어도 M-Schema에 한국어 링킹 힌트를 붙인다.
"""

from __future__ import annotations

# table_name -> (동의어 목록)
TABLE_SYNONYMS: dict[str, tuple[str, ...]] = {
    "AL_D010_26_20250704": (
        "건물",
        "건축물",
        "부산 건물",
        "용도별건물",
    ),
    "AL_D198_26260_20250115": (
        "동래구 건물",
        "동래 용도별건물",
        "사용승인",
        "건축년수",
    ),
    "AL_D198_26410_20250115": (
        "금정구 건물",
        "금정 용도별건물",
        "사용승인",
        "건축년수",
    ),
    "BND_ADM_DONG_PG": (
        "행정동",
        "행정구역",
        "동 경계",
        "구 경계",
    ),
    "TL_KODIS_BAS_26_202507": (
        "기초구역",
        "기초구역번호",
    ),
    "AL_D060_00_20250804": (
        "산업단지",
        "산단",
    ),
    "pnu_def": (
        "지번",
        "필지",
        "PNU",
    ),
}

# (table_name or "*") -> column_name -> synonyms
COLUMN_SYNONYMS: dict[str, dict[str, tuple[str, ...]]] = {
    "*": {
        "geometry": ("공간", "도형", "경계", "위치"),
    },
    "AL_D010_26_20250704": {
        "A3": ("법정동코드", "법정동 코드"),
        "A4": ("법정동명", "법정동", "구", "동", "지역", "주소"),
        "A8": ("용도코드", "건축물용도코드"),
        "A9": ("용도", "용도명", "건축물용도명"),
        "A14": ("연면적", "건물면적", "면적"),
        "A16": ("높이", "건물높이", "고도"),
        "A22": ("데이터기준일", "기준일자"),
        "A26": ("지상층", "지상층수", "층수"),
        "A27": ("지하층", "지하층수"),
    },
    "AL_D198_26260_20250115": {
        "A4": ("법정동명", "법정동", "구", "동", "지역"),
        "A19": ("연면적", "건물면적", "면적"),
        "A25": ("주요용도명", "용도", "용도명"),
        "A29": ("건축물용도명", "용도분류"),
        "A30": ("높이", "건물높이"),
        "A31": ("지상층", "지상층수", "층수"),
        "A33": ("허가일", "허가일자"),
        "A34": ("사용승인일", "사용승인일자", "준공일", "건축년", "건축년수"),
        "A35": ("데이터기준일", "기준일자"),
    },
    "AL_D198_26410_20250115": {
        "A4": ("법정동명", "법정동", "구", "동", "지역"),
        "A19": ("연면적", "건물면적", "면적"),
        "A25": ("주요용도명", "용도", "용도명"),
        "A29": ("건축물용도명", "용도분류"),
        "A30": ("높이", "건물높이"),
        "A31": ("지상층", "지상층수", "층수"),
        "A33": ("허가일", "허가일자"),
        "A34": ("사용승인일", "사용승인일자", "준공일", "건축년", "건축년수"),
        "A35": ("데이터기준일", "기준일자"),
    },
    "BND_ADM_DONG_PG": {
        "ADM_CD": ("행정구역코드", "행정동코드", "코드"),
        "ADM_NM": ("행정동명", "행정동", "동", "구"),
    },
    "TL_KODIS_BAS_26_202507": {
        "BAS_ID": ("기초구역ID", "기초구역번호"),
        "SIG_KOR_NM": ("시군구명", "구", "구명"),
        "BAS_AR": ("기초구역면적", "면적"),
    },
    "AL_D060_00_20250804": {
        "A4": ("원천시도시군구코드", "시군구코드"),
        "A6": ("용도지역지구코드명", "용도지역"),
    },
}

# 샘플 값 조회에 쓸 대표 텍스트 컬럼 (테이블별)
SAMPLE_COLUMNS: dict[str, tuple[str, ...]] = {
    "AL_D010_26_20250704": ("A4", "A9"),
    "AL_D198_26260_20250115": ("A4", "A25"),
    "AL_D198_26410_20250115": ("A4", "A25"),
    "BND_ADM_DONG_PG": ("ADM_NM",),
    "TL_KODIS_BAS_26_202507": ("SIG_KOR_NM",),
    "AL_D060_00_20250804": ("A6",),
}


def table_synonyms(table_name: str) -> tuple[str, ...]:
    return TABLE_SYNONYMS.get(table_name, ())


def column_synonyms(table_name: str, column_name: str) -> tuple[str, ...]:
    specific = COLUMN_SYNONYMS.get(table_name, {}).get(column_name, ())
    generic = COLUMN_SYNONYMS.get("*", {}).get(column_name, ())
    seen: list[str] = []
    for item in (*specific, *generic):
        if item not in seen:
            seen.append(item)
    return tuple(seen)


def format_synonyms(syns: tuple[str, ...], *, max_n: int = 6) -> str:
    if not syns:
        return ""
    return ", ".join(syns[:max_n])
