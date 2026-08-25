"""라우터에 없는 질의어를 닫힌 라우터 어휘에 대응한다."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from functools import lru_cache
from typing import Any

from txt2sql.catalog_attrs import DATASETS
from txt2sql.d198_attrs import (
    D198_ATTRS,
    DATASET_HINTS,
    DECADE_GRAIN_HINTS,
    SIZE_BIN_HINTS,
    YEAR_GRAIN_HINTS,
)
from txt2sql.domain import STRUCTURE_ALIASES, USAGE_ALIASES
from txt2sql.llm import chat as _chat

# 고신뢰만. 세대수·가격·주차 등은 넣지 않는다.
_DETERMINISTIC: dict[str, str] = {
    "평수별": "면적별",
    "평수로": "연면적",
    "평수": "연면적",
    "규모별": "크기별",
    "규모로": "크기별",
    "구간으로": "구간별",
    "구간으로묶어": "구간별",
    "준공연도": "사용승인일",
    "준공년도": "사용승인일",
    "준공연도별": "연도별",
    "건축년도": "사용승인일",
    "건축연도": "사용승인일",
    "건축년도별": "연도별",
    "건축연도별": "연도별",
    "건설년도": "사용승인일",
    "건설연도": "사용승인일",
    "건립연도": "사용승인일",
    "건립년도": "사용승인일",
    "건립연도별": "연도별",
    "시공연도": "사용승인일",
    "시공년도": "사용승인일",
    "사용승인연도": "사용승인일",
    "사용승인년도": "사용승인일",
    "사용승인연도별": "연도별",
    "사용승인년도별": "연도별",
    "동수": "건수",
    "채수": "건수",
    "층고": "높이",
    "건물층수": "지상층",
    "지상층수별": "층수별",
    "연면적별": "면적별",
    "건축면적별": "면적별",
    "대지면적별": "면적별",
}

_EXTRA_TERMS: tuple[tuple[str, str], ...] = (
    ("면적", "연면적"),
    ("면적", "건축면적"),
    ("면적", "대지면적"),
    ("면적", "건물면적"),
    ("면적", "면적별"),
    ("높이", "건물높이"),
    ("높이", "높이별"),
    ("층수", "지상층"),
    ("층수", "지하층"),
    ("층수", "층수별"),
    ("층수", "층별"),
    ("집계", "건수"),
    ("집계", "크기별"),
    ("집계", "구간별"),
    ("집계", "단위별"),
    ("집계", "단위로"),
    ("시간", "건립"),
    ("시간", "지어진"),
    ("시간", "준공"),
    ("시간", "연도별"),
    ("시간", "년도별"),
    ("시간", "연대별"),
    ("시간", "년대별"),
    ("장소", "법정동"),
    ("장소", "행정동"),
    ("장소", "기초구역"),
    ("용도", "산업단지"),
    ("속성", "건물명"),
    ("속성", "지번"),
    ("속성", "특징"),
)

_SKIP_VALUES = {
    "1",
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "0",
    "Y",
    "N",
    "일반",
    "기타",
}

# 라우터에 없는 도메인 밖 개념 — 유사어로 바꾸지 않고 보완 질문
_OUT_OF_SCOPE = {
    "매매가",
    "전세가",
    "월세가",
    "분양가",
    "시세",
    "실거래",
    "실거래가",
    "세대수",
    "세대",
    "인구",
    "주차대수",
}

_HANGUL_TERM = re.compile(r"[가-힣]{2,16}")
_OVERLAP_MIN = 3
_FUZZY_RATIO = 0.84
_FUZZY_MARGIN = 0.08
_SCHEMA_LABELS = frozenset(
    {
        "법정동",
        "법정동명",
        "건물명",
        "건물동명",
        "행정동",
        "행정동명",
        "건축물용도명",
        "세부용도명",
    }
)


def _looks_like_entity_name(token: str) -> bool:
    """단지명·역명 등 고유명사는 스키마 라벨로 바꾸지 않는다."""
    if not token or token in _DETERMINISTIC:
        return False
    if token.endswith("역") and len(token) >= 3:
        return True
    if "역" in token and len(token) >= 4 and not token.endswith(("지역", "구역")):
        return True
    return len(token) >= 4

_LLM_SYSTEM = """당신은 부산 GIS 자연어 질의 라우터의 용어 정규화기입니다.
사용자 질문의 미지 단어를, 아래 라우터 어휘에 있는 단어로만 대응하세요.

규칙:
- to 값은 목록 문자열과 글자 단위로 일치해야 합니다. 새 단어를 만들지 마세요.
- 의미가 불분명하거나 데이터에 없는 개념(매매가, 전세, 월세, 세대수, 인구, 주차 대수 등)은 unmapped에 넣으세요.
- 세대수와 건물 동수, 평(3.3㎡)과 연면적은 같지 않습니다. 확신이 없으면 unmapped.
- 단지명·역명·아파트 고유명사(예: 구서역, 포르투나)는 매핑하지 마세요. 법정동·건물명 같은 스키마 라벨로 바꾸지 마세요.
- JSON만 출력하세요.
형식: {"mappings": [{"from": "미지단어", "to": "라우터단어"}], "unmapped": ["단어"]}
"""


@dataclass(frozen=True)
class SynonymRewrite:
    question: str
    mappings: tuple[tuple[str, str], ...]
    unmapped: tuple[str, ...]
    source: str  # lexicon | overlap | fuzzy | llm | mixed | none


def _accept_term(raw: str) -> str | None:
    text = str(raw or "").strip()
    if not text or text in _SKIP_VALUES or text.isdigit():
        return None
    if len(text) < 2 or len(text) > 16:
        return None
    if not _HANGUL_TERM.fullmatch(text) and not _HANGUL_TERM.search(text):
        return None
    return text


def _category_for_attr(label: str, unit: str = "") -> str:
    blob = f"{label} {unit}"
    if any(k in blob for k in ("면적", "㎡")):
        return "면적"
    if "높이" in blob or blob.endswith("m"):
        return "높이"
    if "층" in blob:
        return "층수"
    if any(k in blob for k in ("일자", "승인", "허가", "준공", "기준일")):
        return "시간"
    if any(k in blob for k in ("용도", "주택", "시설")):
        return "용도"
    if "구조" in blob:
        return "구조"
    if any(k in blob for k in ("동", "구", "구역", "법정", "행정")):
        return "장소"
    return "속성"


def _add(cats: dict[str, list[str]], category: str, term: str | None) -> None:
    accepted = _accept_term(term or "")
    if not accepted:
        return
    bucket = cats.setdefault(category, [])
    if accepted not in bucket:
        bucket.append(accepted)


@lru_cache(maxsize=1)
def router_terms_by_category() -> dict[str, tuple[str, ...]]:
    cats: dict[str, list[str]] = {}
    for attr in D198_ATTRS:
        cat = _category_for_attr(attr.label, attr.unit)
        _add(cats, cat, attr.label)
        for alias in attr.aliases:
            _add(cats, cat, alias)
        if attr.kind in {"text", "code"}:
            for alias, _stored in attr.values:
                _add(cats, cat, alias)
    for ds in DATASETS:
        for attr in ds.attrs:
            cat = _category_for_attr(attr.label, attr.unit)
            _add(cats, cat, attr.label)
            for alias in attr.aliases:
                _add(cats, cat, alias)
        for hint in ds.hints:
            _add(cats, "속성", hint)
    for alias, canonical in USAGE_ALIASES.items():
        _add(cats, "용도", alias)
        _add(cats, "용도", canonical)
    for alias in STRUCTURE_ALIASES:
        _add(cats, "구조", alias)
    for hint in SIZE_BIN_HINTS:
        _add(cats, "집계", hint.replace(" ", ""))
        _add(cats, "집계", hint)
    for hint in (*YEAR_GRAIN_HINTS, *DECADE_GRAIN_HINTS):
        _add(cats, "시간", hint.replace(" ", ""))
        _add(cats, "시간", hint)
    for hint in DATASET_HINTS:
        _add(cats, "속성", hint)
    for cat, term in _EXTRA_TERMS:
        _add(cats, cat, term)
    for _src, dst in _DETERMINISTIC.items():
        _add(cats, "집계" if dst.endswith(("별", "로")) else "속성", dst)
    return {k: tuple(v) for k, v in cats.items() if v}


@lru_cache(maxsize=1)
def all_router_terms() -> tuple[str, ...]:
    seen: list[str] = []
    for terms in router_terms_by_category().values():
        for term in terms:
            if term not in seen:
                seen.append(term)
    return tuple(sorted(seen, key=len, reverse=True))


def apply_router_mappings(question: str, mappings: list[tuple[str, str]]) -> str:
    rewritten = question
    for src, dst in sorted(mappings, key=lambda p: len(p[0]), reverse=True):
        if src and src in rewritten and src != dst:
            rewritten = rewritten.replace(src, dst)
    return rewritten


def _map_deterministic(unknown: list[str]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    terms = set(all_router_terms())
    for token in unknown:
        mapped = _DETERMINISTIC.get(token)
        if mapped and mapped in terms and mapped != token:
            out.append((token, mapped))
    return out


def _map_by_overlap(token: str, lexicon: tuple[str, ...]) -> str | None:
    hits = [
        term
        for term in lexicon
        if term != token
        and len(term) >= _OVERLAP_MIN
        and (term in token or token in term)
    ]
    if not hits:
        return None
    hits.sort(key=len, reverse=True)
    if len(hits) >= 2 and len(hits[0]) == len(hits[1]):
        return None
    return hits[0]


def _map_fuzzy(token: str, lexicon: tuple[str, ...]) -> str | None:
    scored: list[tuple[float, str]] = []
    for term in lexicon:
        if term == token or abs(len(term) - len(token)) > 4:
            continue
        ratio = SequenceMatcher(None, token, term).ratio()
        if ratio >= _FUZZY_RATIO:
            scored.append((ratio, term))
    if not scored:
        return None
    scored.sort(reverse=True)
    if len(scored) >= 2 and scored[0][0] - scored[1][0] < _FUZZY_MARGIN:
        return None
    return scored[0][1]


def _lexicon_prompt_block() -> str:
    lines: list[str] = []
    for cat, terms in router_terms_by_category().items():
        compact = terms[:24]
        lines.append(f"{cat}: {', '.join(compact)}")
    return "\n".join(lines)


def _parse_mapping_json(text: str, allowed: set[str], unknown: list[str]) -> tuple[list[tuple[str, str]], list[str]]:
    if not text:
        return [], list(unknown)
    cleaned = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.I).strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", cleaned, re.I | re.S)
    if fence:
        cleaned = fence.group(1).strip()
    match = re.search(r"\{[\s\S]*\}", cleaned)
    if not match:
        return [], list(unknown)
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return [], list(unknown)
    want = set(unknown)
    mapped: list[tuple[str, str]] = []
    seen: set[str] = set()
    for item in data.get("mappings") or []:
        if not isinstance(item, dict):
            continue
        src = str(item.get("from") or "").strip()
        dst = str(item.get("to") or "").strip()
        if src not in want or dst not in allowed or src == dst or src in seen:
            continue
        mapped.append((src, dst))
        seen.add(src)
    reported = [str(x).strip() for x in (data.get("unmapped") or []) if str(x).strip()]
    leftover = [u for u in unknown if u not in seen]
    if reported:
        leftover = [u for u in leftover if u in reported or u not in seen]
        leftover = [u for u in unknown if u not in seen]
    return mapped, leftover


def _map_with_llm(
    unknown: list[str],
    *,
    model: str,
    host: str | None,
    client: Any | None,
) -> list[tuple[str, str]]:
    allowed = set(all_router_terms())
    raw = _chat(
        model=model,
        host=host,
        client=client,
        temperature=0.0,
        messages=[
            {"role": "system", "content": _LLM_SYSTEM},
            {
                "role": "user",
                "content": (
                    "라우터 어휘:\n"
                    f"{_lexicon_prompt_block()}\n\n"
                    f"미지 단어: {', '.join(unknown)}"
                ),
            },
        ],
    )
    mapped, _leftover = _parse_mapping_json(raw, allowed, unknown)
    return mapped


def map_unknown_to_router(
    question: str,
    unknown: list[str],
    *,
    model: str | None = None,
    host: str | None = None,
    client: Any | None = None,
) -> SynonymRewrite:
    """미지 토큰을 라우터 단어로 바꾸고 질문을 다시 쓴다."""
    tokens = [u for u in unknown if u and u not in set(all_router_terms())]
    if not tokens:
        return SynonymRewrite(question, (), (), "none")

    forced = [t for t in tokens if t in _OUT_OF_SCOPE]
    tokens = [t for t in tokens if t not in _OUT_OF_SCOPE]
    tokens = [t for t in tokens if not _looks_like_entity_name(t)]

    mappings: list[tuple[str, str]] = _map_deterministic(tokens)
    sources: set[str] = {"lexicon"} if mappings else set()
    mapped_src = {src for src, _dst in mappings}
    leftover = [t for t in tokens if t not in mapped_src]
    lexicon = all_router_terms()

    still: list[str] = []
    for token in leftover:
        hit = _map_by_overlap(token, lexicon)
        if hit:
            mappings.append((token, hit))
            sources.add("overlap")
            continue
        hit = _map_fuzzy(token, lexicon)
        if hit:
            mappings.append((token, hit))
            sources.add("fuzzy")
            continue
        still.append(token)

    mappings = [
        (src, dst)
        for src, dst in mappings
        if dst not in _SCHEMA_LABELS or src in _DETERMINISTIC
    ]

    if still and (client is not None or (model and host)):
        try:
            llm_maps = _map_with_llm(
                still, model=model or "", host=host, client=client
            )
        except Exception:
            llm_maps = []
        if llm_maps:
            llm_maps = [
                (src, dst)
                for src, dst in llm_maps
                if dst not in _SCHEMA_LABELS
            ]
            mappings.extend(llm_maps)
            sources.add("llm")
            mapped_src = {src for src, _dst in mappings}
            still = [t for t in still if t not in mapped_src]

    still.extend(forced)
    source = "none"
    if mappings and not still:
        source = next(iter(sources)) if len(sources) == 1 else "mixed"
    elif mappings:
        source = "mixed"
    rewritten = apply_router_mappings(question, mappings) if mappings else question
    return SynonymRewrite(
        question=rewritten,
        mappings=tuple(mappings),
        unmapped=tuple(still),
        source=source,
    )
