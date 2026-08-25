"""면적·길이 단위 환산."""

from __future__ import annotations

import sys

from txt2sql.d198_attrs import format_value_bin_label, parse_d198_question, parse_value_bin
from txt2sql.units import PYEONG_TO_M2, convert_for_schema, sql_number, with_pyeong


def main() -> int:
    failed: list[str] = []
    passed = 0

    thirty = convert_for_schema(30, "평", "㎡")
    expect = sql_number(30 * PYEONG_TO_M2)
    if thirty is None or thirty.sql != expect or "30평" not in thirty.label:
        failed.append(f"30평 환산: {thirty}")
    else:
        passed += 1
        print("[pyeong] OK ", thirty.label)

    km = convert_for_schema(1, "km", "m")
    if km is None or km.sql != "1000":
        failed.append(f"1km 환산: {km}")
    else:
        passed += 1
        print("[km] OK  1km → 1000m")

    same = convert_for_schema(100, "m2", "㎡")
    if same is None or same.sql != "100":
        failed.append(f"100m2: {same}")
    else:
        passed += 1
        print("[m2] OK  100m2 → 100㎡")

    bad = convert_for_schema(30, "평", "m")
    if bad is not None:
        failed.append("평→높이 환산이 막히지 않음")
    else:
        passed += 1
        print("[skip] OK  평≠m")

    q = "용도별건물에서 동래구에서 연면적이 30평 이상인 건물은 몇 채야?"
    parsed = parse_d198_question(q)
    blob = " ".join(parsed.filters) if parsed else ""
    if parsed is None or expect not in blob:
        failed.append(f"D198 30평 SQL {parsed}")
    else:
        passed += 1
        print("[d198] OK  연면적 30평 필터")

    qh = "용도별건물에서 금정구에서 건물높이가 0.05km 이상인 건물은 몇 채야?"
    parsed_h = parse_d198_question(qh)
    blob_h = " ".join(parsed_h.filters) if parsed_h else ""
    if parsed_h is None or "50" not in blob_h:
        failed.append(f"D198 0.05km 높이 {parsed_h}")
    else:
        passed += 1
        print("[height] OK  0.05km → 50m")

    spec = parse_value_bin("금정구 아파트 30평 단위로")
    if spec is None or abs(spec.bin_width - 30 * PYEONG_TO_M2) > 0.01:
        failed.append(f"30평 구간 {spec}")
    else:
        passed += 1
        print("[bin] OK  30평 단위", spec.bin_width, spec.width_label)

    spec33 = parse_value_bin("구서동 아파트 33평 단위로")
    if spec33 is None or spec33.source_unit != "pyeong" or spec33.source_width != 33:
        failed.append(f"33평 spec {spec33}")
    else:
        period = int(5 * spec33.bin_width)
        label = format_value_bin_label({"period": period, "n": 9}, spec33)
        if "㎡" not in label or "평" not in label or "165" not in label:
            failed.append(f"33평 라벨 {label}")
        else:
            passed += 1
            print("[label] OK ", label)

    dual = with_pyeong("1,000㎡", 1000, question="30평 이상 아파트")
    if "평" not in dual or "㎡" not in dual:
        failed.append(f"면적 병기 {dual}")
    else:
        passed += 1
        print("[area] OK ", dual)

    no_py = with_pyeong("1,000㎡", 1000, question="연면적 1000㎡ 이상")
    if "평" in no_py:
        failed.append(f"㎡ 질문에 평이 붙음 {no_py}")
    else:
        passed += 1
        print("[area-skip] OK")

    total = passed + len(failed)
    print(f"\n=== 결과: {passed}/{total} OK ===")
    if failed:
        print("실패:")
        for item in failed:
            print(" -", item)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
