"""공통 테스트 픽스처."""

from __future__ import annotations

import pytest

from txt2sql.domain import D198_BY_GU, reset_d198_coverage, set_d198_coverage

# 부산 시군구 대표 D198 테이블(단위 테스트용). 런타임 discover 와 동일 패턴.
_BUSAN_D198_TEST_COVERAGE: dict[str, str] = {
    "중구": "AL_D198_26110_20260715",
    "서구": "AL_D198_26140_20260715",
    "동구": "AL_D198_26170_20260715",
    "영도구": "AL_D198_26200_20260715",
    "부산진구": "AL_D198_26230_20260715",
    "동래구": "AL_D198_26260_20260715",
    "남구": "AL_D198_26290_20260715",
    "북구": "AL_D198_26320_20260715",
    "해운대구": "AL_D198_26350_20260715",
    "사하구": "AL_D198_26380_20260715",
    "금정구": "AL_D198_26410_20260715",
    "강서구": "AL_D198_26440_20260715",
    "연제구": "AL_D198_26470_20260715",
    "수영구": "AL_D198_26500_20260715",
    "사상구": "AL_D198_26530_20260715",
    "기장군": "AL_D198_26710_20260715",
}


@pytest.fixture(autouse=True)
def _restore_d198_coverage():
    prior = dict(D198_BY_GU)
    set_d198_coverage(dict(_BUSAN_D198_TEST_COVERAGE))
    yield
    if prior:
        set_d198_coverage(prior)
    else:
        reset_d198_coverage()
