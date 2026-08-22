"""Identify·속성 테이블 값을 사용자가 읽기 쉬운 한국어 설명으로 바꾼다."""

from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from typing import Any

from llm2sql.config import Settings
from llm2sql.llm import chat
from llm2sql.map.labels import labels_for_layer, normalize_field_key

_SKIP = frozenset(
    {
        "geometry",
        "geom",
        "the_geom",
        "shape",
        "wkt",
        "boundedby",
        "bbox",
        "fid",
        "gml_id",
        "id",
        "objectid",
    }
)
_THINK_RE = re.compile(r"<think>[\s\S]*?</think>", re.I)
_DATE8_RE = re.compile(r"^(\d{4})(\d{2})(\d{2})$")
_MAX_FACTS = 28
_MAX_ROWS = 10
_MAX_VALUE = 180
_LLM_TIMEOUT_S = 18.0
_EXEC = ThreadPoolExecutor(max_workers=2, thread_name_prefix="map-explain")

IDENTIFY_SYSTEM = """당신은 부산 GIS 지도의 속성 안내원입니다.
사용자가 맵에서 클릭한 한 피처의 속성을 일반인이 바로 이해하도록 설명합니다.
규칙:
- 2~4문장, 한국어 문단만 출력하세요. 제목·불릿·마크다운 금지.
- A24, AL_D010, GeoServer 같은 코드·스키마 이름을 쓰지 마세요.
- 숫자에는 단위를 붙이세요. 면적은 ㎡, 높이는 m, 층수는 층입니다. 평으로 환산하지 마세요.
- 주어진 값에 없는 사실·평균·비율을 지어내지 마세요.
- 건물명이 있으면 「」로 감싸 먼저 소개하세요."""

TABLE_SYSTEM = """당신은 부산 GIS 지도의 속성 테이블 안내원입니다.
레이어 목록이 무엇을 보여주는지 일반인이 바로 이해하도록 요약합니다.
규칙:
- 2~4문장, 한국어 문단만 출력하세요. 제목·불릿·마크다운 금지.
- 전체 건수와 장소·용도 경향을 말하세요. 행을 모두 나열하지 마세요.
- 면적은 ㎡로만 말하세요. 평으로 환산하지 마세요.
- A24, AL_D010 같은 코드·스키마 이름을 쓰지 마세요.
- 주어진 값에 없는 사실·평균·비율을 지어내지 마세요."""


def strip_llm_text(text: str) -> str:
    cleaned = _THINK_RE.sub("", text or "").strip()
    fence = re.search(r"```(?:\w+)?\s*(.*?)```", cleaned, re.I | re.S)
    if fence:
        cleaned = fence.group(1).strip()
    cleaned = re.sub(r"^(설명|요약|답변)\s*[:：]\s*", "", cleaned)
    return re.sub(r"\s+\n", "\n", cleaned).strip()


def is_geom_key(key: str) -> bool:
    low = (key or "").lower()
    if low in _SKIP:
        return True
    return "geom" in low


def format_attr_value(label: str, value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "예" if value else "아니오"
    text = str(value).strip()
    if not text or text.lower() in {"none", "null"}:
        return ""
    if len(text) > _MAX_VALUE:
        text = text[: _MAX_VALUE - 1] + "…"
    match = _DATE8_RE.match(text)
    if match and any(token in label for token in ("일자", "날짜", "승인", "허가")):
        y, m, d = match.groups()
        return f"{int(y)}년 {int(m)}월 {int(d)}일"
    try:
        number = float(text.replace(",", ""))
    except ValueError:
        return text
    if not number.is_integer() or abs(number) >= 1000:
        shown = f"{number:,.2f}".rstrip("0").rstrip(".")
    else:
        shown = f"{int(number):,}"
    if "면적" in label:
        return f"{shown}㎡"
    if "높이" in label:
        return f"{shown}m"
    if "층" in label:
        return f"{shown}층"
    return shown


def labeled_facts(
    properties: dict[str, Any] | None,
    fields: dict[str, str] | None = None,
    *,
    limit: int = _MAX_FACTS,
) -> list[tuple[str, str]]:
    fields = fields or {}
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for raw_key, raw_val in (properties or {}).items():
        if is_geom_key(str(raw_key)):
            continue
        if raw_val is None or isinstance(raw_val, (dict, list)):
            continue
        logical = normalize_field_key(str(raw_key))
        label = (
            fields.get(str(raw_key))
            or fields.get(logical)
            or fields.get(logical.upper())
            or logical
        )
        if label in seen:
            continue
        value = format_attr_value(str(label), raw_val)
        if not value:
            continue
        seen.add(label)
        out.append((str(label), value))
        if len(out) >= limit:
            break
    return out


def facts_payload(facts: list[tuple[str, str]]) -> list[dict[str, str]]:
    return [{"name": name, "value": value} for name, value in facts]


def fallback_identify(title: str, facts: list[tuple[str, str]]) -> str:
    if not facts:
        subject = title.strip() or "선택한 피처"
        return f"「{subject}」에서 표시할 속성 값을 찾지 못했습니다."
    by_name = {name: value for name, value in facts}
    name = by_name.get("건물명") or by_name.get("행정동명") or by_name.get("시군구명")
    if name:
        lead = f"이 피처는 「{name}」입니다."
    else:
        subject = title.strip() or "선택한 피처"
        lead = f"「{subject}」의 속성입니다."
    skip = {"건물명"}
    extras: list[str] = []
    for label, value in facts:
        if label in skip:
            continue
        extras.append(f"{label} {value}")
        if len(extras) >= 5:
            break
    if extras:
        return f"{lead} 주요 값은 {', '.join(extras)}입니다."
    return lead


def fallback_table(
    title: str,
    *,
    total: int,
    facts_head: list[tuple[str, str]],
    row_count: int,
) -> str:
    subject = title.strip() or "이 레이어"
    count = f"{total:,}건" if total else f"{row_count}행"
    lead = f"「{subject}」 속성 테이블입니다. 모두 {count}입니다."
    if not facts_head:
        return lead + " 열 이름과 값을 표에서 확인할 수 있습니다."
    preview = ", ".join(f"{n} {v}" for n, v in facts_head[:4])
    return f"{lead} 예를 들면 {preview} 같은 값이 있습니다."


def resolve_fields(
    settings: Settings,
    layer: str,
    keys: list[str],
    client_fields: dict[str, str] | None,
) -> tuple[dict[str, str], str]:
    merged = dict(client_fields or {})
    title = ""
    if layer:
        try:
            data = labels_for_layer(settings, layer, columns=keys or None)
        except Exception:
            data = {}
        for key, label in (data.get("fields") or {}).items():
            if label:
                merged[key] = label
        title = str(data.get("title") or "")
    return merged, title


def explain_identify(
    settings: Settings,
    *,
    title: str = "",
    layer: str = "",
    properties: dict[str, Any] | None = None,
    fields: dict[str, str] | None = None,
    client: Any | None = None,
) -> dict[str, Any]:
    keys = [str(k) for k in (properties or {}) if not is_geom_key(str(k))][:40]
    merged, meta_title = resolve_fields(settings, layer, keys, fields)
    heading = (title or meta_title or layer or "").strip()
    facts = labeled_facts(properties, merged)
    fallback = fallback_identify(heading, facts)
    text, used_llm = _narrate(
        settings,
        system=IDENTIFY_SYSTEM,
        user=(
            f"레이어: {heading or '피처'}\n"
            f"속성(JSON):\n{json.dumps(facts_payload(facts), ensure_ascii=False)}\n"
            "위 속성만으로 이 피처를 설명하세요."
        ),
        fallback=fallback,
        client=client,
    )
    return {
        "kind": "identify",
        "explanation": text,
        "used_llm": used_llm,
        "facts": facts_payload(facts),
    }


def explain_table(
    settings: Settings,
    *,
    title: str = "",
    layer: str = "",
    columns: list[str] | None = None,
    rows: list[dict[str, Any]] | None = None,
    total: int | None = None,
    fields: dict[str, str] | None = None,
    client: Any | None = None,
) -> dict[str, Any]:
    sample = list(rows or [])[:_MAX_ROWS]
    keys = [str(c) for c in (columns or []) if not is_geom_key(str(c))][:20]
    if not keys and sample:
        keys = [str(k) for k in sample[0].keys() if not is_geom_key(str(k))][:20]
    merged, meta_title = resolve_fields(settings, layer, keys, fields)
    heading = (title or meta_title or layer or "").strip()
    first = labeled_facts(sample[0] if sample else {}, merged, limit=8)
    n_total = int(total) if total is not None else len(sample)
    fallback = fallback_table(
        heading, total=n_total, facts_head=first, row_count=len(sample)
    )
    preview_rows = []
    for row in sample[:6]:
        preview_rows.append(facts_payload(labeled_facts(row, merged, limit=8)))
    text, used_llm = _narrate(
        settings,
        system=TABLE_SYSTEM,
        user=(
            f"레이어: {heading or '속성 테이블'}\n"
            f"전체 건수: {n_total}\n"
            f"열: {json.dumps([merged.get(c, c) for c in keys], ensure_ascii=False)}\n"
            f"앞부분 행(JSON):\n{json.dumps(preview_rows, ensure_ascii=False)}\n"
            "이 테이블이 무엇을 보여주는지 요약하세요."
        ),
        fallback=fallback,
        client=client,
    )
    return {
        "kind": "table",
        "explanation": text,
        "used_llm": used_llm,
        "total": n_total,
    }


def explain_attributes(
    settings: Settings,
    *,
    kind: str,
    title: str = "",
    layer: str = "",
    properties: dict[str, Any] | None = None,
    columns: list[str] | None = None,
    rows: list[dict[str, Any]] | None = None,
    total: int | None = None,
    fields: dict[str, str] | None = None,
    client: Any | None = None,
) -> dict[str, Any]:
    mode = (kind or "").strip().lower()
    if mode == "table":
        return explain_table(
            settings,
            title=title,
            layer=layer,
            columns=columns,
            rows=rows,
            total=total,
            fields=fields,
            client=client,
        )
    return explain_identify(
        settings,
        title=title,
        layer=layer,
        properties=properties,
        fields=fields,
        client=client,
    )


def _narrate(
    settings: Settings,
    *,
    system: str,
    user: str,
    fallback: str,
    client: Any | None,
) -> tuple[str, bool]:
    def _call() -> str:
        raw = chat(
            model=settings.ollama_model,
            host=None if client is not None else settings.ollama_host,
            client=client,
            temperature=0.2,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return strip_llm_text(raw)

    try:
        text = _EXEC.submit(_call).result(timeout=_LLM_TIMEOUT_S)
        if text:
            return text, True
    except (FuturesTimeout, Exception):
        pass
    return fallback, False
