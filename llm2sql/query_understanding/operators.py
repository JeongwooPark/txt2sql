"""한국어 논리·집계·정렬·범위 연산자 사전."""

from __future__ import annotations

AND_PATTERNS = ("그리고", "이면서", "동시에", r"\s중\s", r"중$")
OR_PATTERNS = ("또는", "혹은", "둘 중 하나")
NOT_PATTERNS = ("제외", "아닌", "빼고", "이외")
RANGE_PATTERNS = (
    r"(?P<lo>\d+(?:\.\d+)?)\s*(?P<u1>m|미터|㎡|m2|평)?\s*(이상|부터)\s*(?P<hi>\d+(?:\.\d+)?)\s*(?P<u2>m|미터|㎡|m2|평)?\s*(이하|까지|사이)",
    r"(?P<lo>\d+(?:\.\d+)?)\s*(?P<u1>m|미터|㎡|m2|평)?\s*부터\s*(?P<hi>\d+(?:\.\d+)?)\s*(?P<u2>m|미터|㎡|m2|평)?\s*까지",
    r"(?P<lo>\d+(?:\.\d+)?)\s*(?P<u1>m|미터|㎡|m2|평)?\s*사이\s*(?P<hi>\d+(?:\.\d+)?)",
)
SORT_ASC = ("낮은", "작은", "오래된", "낮은 순", "작은 순", "오래된 순")
SORT_DESC = ("높은", "큰", "최신", "높은 순", "큰 순", "최신 순", "가장 높", "가장 큰")
AGG_MAP = {
    "평균": "avg",
    "합계": "sum",
    "총합": "sum",
    "최대": "max",
    "최소": "min",
    "최솟값": "min",
    "최댓값": "max",
    "중앙값": "median",
}
METRIC_MAP = {
    "높이": "height_m",
    "고도": "height_m",
    "연면적": "gross_floor_area_m2",
    "건축면적": "building_area_m2",
    "건물면적": "building_area_m2",
    "대지면적": "site_area_m2",
    "지상층": "ground_floors",
    "층수": "ground_floors",
    "용도": "usage",
}
OUTPUT_HINTS = ("이름", "건물명", "지번", "법정동", "용도", "높이", "연면적", "건축면적")
COMPARE_PATTERNS = (
    r"(?P<left>건축면적|건물면적|연면적|대지면적|높이).{0,6}(?P<rel>보다 큰|보다 작은|보다 높은|보다 낮은).{0,6}(?P<right>건축면적|건물면적|연면적|대지면적|높이)",
    r"(?P<left>건축면적|건물면적).{0,8}(?P<right>연면적|대지면적).{0,4}(보다 큰|보다 작)",
)
GROUP_HINTS = ("용도별", "층수별", "층별")
HAVING_HINTS = ("평균이", "합계가", "건수가")
LIMIT_PATTERN = r"(?P<n>\d+)\s*(개|곳|채|동)\b"
PLACE_PATTERN = r"[가-힣A-Za-z0-9]+(?:구|군|시|동|읍|면|리)"
NUMBER_UNIT_PATTERN = r"(?P<num>\d+(?:\.\d+)?)\s*(?P<unit>m|미터|km|㎡|m2|평|층)?"
