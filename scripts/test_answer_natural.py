"""D198 답변이 스키마 라벨 나열이 아니라 자연어인지 검증."""

from __future__ import annotations

from llm2sql.answer import (
    _is_stiff_answer,
    _natural_threshold_list,
    _prose_without_markdown_table,
    _result_payload,
    _strip_answer_text,
    build_distribution,
    build_share_distribution,
    format_stats_markdown,
    format_success_template,
)


STIFF = (
    "안내: 용도별건물공간정보는 현재 동래구·금정구 자료입니다.\n\n"
    "금정구 아파트(공동주택) 사용승인일자 있음 세부용도명 아파트 "
    "사용승인일자 최근 중에서 해당 조건의 건축물입니다. "
    "예: 「휴림 아르페」 공동주택 일반."
)


def main() -> int:
    failed: list[str] = []
    q = "금정구에서 가장 최근에 지어진 아파트는?"
    rows = [
        {
            "A4": "부산광역시 금정구 구서동",
            "A13": "휴림 아르페",
            "A25": "공동주택",
            "A27": "아파트",
            "A34": "2023-03-22",
            "A6": "일반",
        }
    ]

    if not _is_stiff_answer(STIFF):
        failed.append("뻣뻣한 답을 감지하지 못함")
    stripped = _strip_answer_text(STIFF)
    if stripped.startswith("안내:"):
        failed.append("안내: 머리말이 남아 있음")
    if not _is_stiff_answer(stripped):
        failed.append("안내 제거 후에도 뻣뻣한 답을 감지하지 못함")

    payload = _result_payload(
        rows=rows, row_count=1, route="d198_attr_rank", question=q
    )
    preview = payload.get("preview_rows") or []
    if not preview:
        failed.append("preview_rows 없음")
    else:
        keys = set(preview[0].keys())
        if "세부용도명" in keys or "특수지구분명" in keys:
            failed.append(f"스키마 라벨이 그대로 들어감: {keys}")
        if preview[0].get("건물명") != "휴림 아르페":
            failed.append(f"건물명 누락: {preview[0]}")
        if "2023년 3월 22일" not in str(preview[0].get("사용승인일") or ""):
            failed.append(f"사용승인일 한글 날짜 아님: {preview[0]}")
    if payload.get("coverage_note"):
        failed.append("금정구 질문에 coverage_note가 붙음")

    ans = format_success_template(
        q, sql="SELECT 1", rows=rows, row_count=1, route="d198_attr_rank"
    )
    if _is_stiff_answer(ans):
        failed.append(f"템플릿 답도 뻣뻣함: {ans}")
    if "휴림 아르페" not in ans:
        failed.append(f"건물명 없음: {ans}")
    if "2023년 3월 22일" not in ans:
        failed.append(f"한글 날짜 없음: {ans}")
    if "세부용도명" in ans or "해당 조건의 건축물" in ans or "안내:" in ans:
        failed.append(f"스키마/안내 문구가 남음: {ans}")
    if not ans.startswith("금정구에서"):
        failed.append(f"주어가 자연어가 아님: {ans}")

    list_ans = format_success_template(
        "금정구 아파트 최근 3개를 출력해줘",
        sql="SELECT 1",
        rows=rows
        + [
            {**rows[0], "A13": "헤리티지 우석", "A34": "2022-12-01"},
            {**rows[0], "A13": "구서 더샵 파크", "A34": "2022-06-15"},
        ],
        row_count=3,
        route="d198_attr_list",
    )
    if "세부용도명" in list_ans or "해당 조건" in list_ans:
        failed.append(f"목록 답이 뻣뻣함: {list_ans}")
    if "휴림 아르페" not in list_ans:
        failed.append(f"목록에 건물명 없음: {list_ans}")

    names_only = (
        "금정구에서 사용승인일이 있는 아파트 5개는 다음과 같습니다. "
        "휴림 아르페, 헤리티지 우석, 구서 다움 파크입니다."
    )
    from llm2sql.answer import _list_omits_dates

    if not _list_omits_dates(
        names_only, rows + [{**rows[0], "A13": "헤리티지 우석"}]
    ):
        failed.append("날짜 빠진 목록을 감지하지 못함")
    if _list_omits_dates(ans, rows):
        failed.append("날짜 있는 답을 빠짐으로 오인")

    bin_q = "동래구 단독주택 연면적을 33㎡ 단위로"
    bin_rows = [
        {"period": 0, "n": 313},
        {"period": 33, "n": 1281},
        {"period": 132, "n": 2620},
    ]
    dist = build_distribution(
        bin_q, rows=bin_rows, route="d198_value_bins", row_count=3
    )
    if not dist or dist.get("total") != 4214:
        failed.append(f"구간 표 합계: {dist}")
    else:
        md = format_stats_markdown(dist)
        if "| 연면적 구간 |" not in md or "2,620" not in md or "합계" not in md:
            failed.append(f"마크다운 표 부족: {md}")
        templ = format_success_template(
            bin_q, sql="SELECT 1", rows=bin_rows, row_count=3, route="d198_value_bins"
        )
        if "| 0~32㎡ |" not in templ:
            failed.append(f"템플릿에 표가 없음: {templ[:200]}")
        if templ.count("313동") >= 1 and "\n0~32㎡ 313동" in templ:
            failed.append("줄글 나열이 남아 있음")
        sample = (
            "구서동에는 총 235개의 아파트가 있으며, 가장 많은 건물은 "
            "1000~1999㎡ 구간에 32개입니다.\n\n"
            f"{md}\n\n"
            "이 내용을 차트로도 정리할 수 있어요. 차트로 보시겠어요?"
        )
        prose = _prose_without_markdown_table(sample)
        if "| 연면적 구간 |" in prose or "| --- |" in prose:
            failed.append(f"웹 본문에 파이프 표가 남음: {prose!r}")
        if "235" not in prose or "차트로 보시겠어요" not in prose:
            failed.append(f"표 제거 후 요약/제안이 빠짐: {prose!r}")

    pyeong_dist = build_distribution(
        "구서동 아파트 33평 단위로",
        rows=bin_rows,
        route="d198_value_bins",
        row_count=3,
    )
    if pyeong_dist:
        pmd = format_stats_markdown(pyeong_dist)
        if "평" not in pmd or "㎡" not in pmd:
            failed.append(f"평 구간 표에 환산 없음: {pmd[:240]}")
    else:
        failed.append("33평 구간 표를 만들지 못함")

    share = build_share_distribution(
        [
            {"admin_dong": "구서1동", "n": 196, "pct": 39.0},
            {"admin_dong": "구서2동", "n": 307, "pct": 61.0},
        ]
    )
    if not share or share.get("total") != 503 or not share.get("rows"):
        failed.append(f"행정동 비율 표: {share}")

    from llm2sql.intent_router import try_route

    thr_q = "100평 이상의 건물을 구서동에서 찾아라"
    routed = try_route(thr_q)
    if routed is None or routed.intent != "building_area_threshold_list":
        failed.append(f"100평 목록 라우트: {routed}")
    elif "COUNT(*) OVER()" not in routed.sql:
        failed.append(f"목록 SQL에 전체 건수 없음:\n{routed.sql}")
    thr_sql = 'SELECT 1 FROM t WHERE "A14" >= 330.5785'
    thr_rows = [
        {
            "A24": "구서 협성 엠파이어",
            "A14": 3014.24,
            "A12": 500,
            "total_n": 412,
        },
        {"A24": "이마트 금정점", "A14": 15266.08, "total_n": 412},
    ]
    thr_ans = _natural_threshold_list(
        thr_q,
        sql=thr_sql,
        rows=thr_rows,
        row_count=2,
        route="building_area_threshold_list",
    )
    if "412" not in thr_ans.replace(",", ""):
        failed.append(f"임계 목록 총건수 없음: {thr_ans}")
    if "연면적" not in thr_ans:
        failed.append(f"임계 목록이 연면적이 아님: {thr_ans}")
    if "평" not in thr_ans:
        failed.append(f"임계 목록에 평 환산 없음: {thr_ans}")
    if "협성" not in thr_ans:
        failed.append(f"임계 목록 대표사례 없음: {thr_ans}")
    tmpl = format_success_template(
        thr_q,
        sql=thr_sql,
        rows=thr_rows,
        row_count=2,
        route="building_area_threshold_list",
    )
    if "412" not in tmpl.replace(",", "") or "대표" not in tmpl:
        failed.append(f"임계 목록 템플릿: {tmpl}")

    if failed:
        print("FAIL")
        for item in failed:
            print(" -", item)
        print("template:", ans)
        print("list:", list_ans)
        return 1
    print("OK")
    print(ans)
    print(list_ans)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
