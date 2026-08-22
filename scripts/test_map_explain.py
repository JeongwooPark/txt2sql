"""Identify·속성 테이블 LLM 설명 (폴백 포함)."""

from __future__ import annotations

from llm2sql.config import Settings
from llm2sql.map.explain import (
    explain_attributes,
    fallback_identify,
    fallback_table,
    format_attr_value,
    labeled_facts,
    strip_llm_text,
)


class _BoomClient:
    def chat(self, **_kwargs):
        raise RuntimeError("llm down")


class _OkClient:
    def chat(self, **_kwargs):
        return {
            "message": {
                "content": "<think>내부</think>「구서역 포르투나」는 금정구 구서동의 공동주택입니다."
            }
        }


def main() -> int:
    failed: list[str] = []
    passed = 0

    def ok(name: str, cond: bool, detail: str = "") -> None:
        nonlocal passed
        if cond:
            passed += 1
            print(f"[ok] {name}")
        else:
            failed.append(f"{name}: {detail}")
            print(f"[fail] {name} {detail}")

    props = {
        "A24": "구서역 포르투나",
        "A9": "공동주택",
        "A14": 15816.435,
        "A16": 60.95,
        "A26": 20,
        "A34": "20220422",
        "geometry": {"type": "Polygon"},
        "gml_id": "x.1",
    }
    fields = {
        "A24": "건물명",
        "A9": "용도명",
        "A14": "연면적",
        "A16": "높이",
        "A26": "지상층수",
        "A34": "사용승인일자",
    }
    facts = labeled_facts(props, fields)
    names = [n for n, _ in facts]
    ok("skips geometry", "geometry" not in names and "gml_id" not in names)
    ok("keeps building name", any(n == "건물명" and "포르투나" in v for n, v in facts))
    ok("area unit", format_attr_value("연면적", 15816.435).endswith("㎡"))
    ok("height unit", format_attr_value("높이", 60.95).endswith("m"))
    ok("floor unit", "층" in format_attr_value("지상층수", 20))
    ok("date korean", format_attr_value("사용승인일자", "20220422") == "2022년 4월 22일")
    ok(
        "strip think",
        strip_llm_text("<think>a</think> 본문입니다.") == "본문입니다.",
    )

    fb = fallback_identify("조회", facts)
    ok("fallback names building", "구서역 포르투나" in fb)
    ok("fallback no code", "A24" not in fb and "geometry" not in fb)

    tb = fallback_table("구서1동의 아파트는?", total=196, facts_head=facts[:3], row_count=10)
    ok("table fallback count", "196건" in tb)
    ok("table fallback title", "구서1동의 아파트는?" in tb)

    settings = Settings(
        database_url="postgresql://u:p@localhost:5432/gisdb",
        geoserver_url="",
        ollama_host="http://127.0.0.1:9",
    )
    identified = explain_attributes(
        settings,
        kind="identify",
        title="구서역포르투나를 찾아라",
        properties=props,
        fields=fields,
        client=_BoomClient(),
    )
    ok("identify fallback when llm down", identified.get("used_llm") is False)
    ok(
        "identify still explains",
        "포르투나" in (identified.get("explanation") or ""),
        str(identified),
    )

    tabled = explain_attributes(
        settings,
        kind="table",
        title="구서1동의 아파트는?",
        columns=["A24", "A9", "A14"],
        rows=[{"A24": "롯데캐슬", "A9": "공동주택", "A14": 12000}],
        total=196,
        fields=fields,
        client=_BoomClient(),
    )
    ok("table fallback when llm down", tabled.get("used_llm") is False)
    ok("table still explains", "196건" in (tabled.get("explanation") or ""))

    narrated = explain_attributes(
        settings,
        kind="identify",
        title="조회",
        properties=props,
        fields=fields,
        client=_OkClient(),
    )
    ok("llm used", narrated.get("used_llm") is True)
    ok(
        "llm strips think",
        "<think>" not in (narrated.get("explanation") or "")
        and "공동주택" in (narrated.get("explanation") or ""),
        str(narrated.get("explanation")),
    )

    print(f"\npassed={passed} failed={len(failed)}")
    for item in failed:
        print(" ", item)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
