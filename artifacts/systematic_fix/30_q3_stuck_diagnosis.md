# Q3(`Q3_agg_rank`) 수정이 안 붙는 이유 — 사례·원인만

- 작성: 2026-08-25
- 범위: `22_pattern_ids.json` → `Q3_agg_rank` 24문항
- 평가 궤적: 20차(`20_post_fix500.json`) → Q3 r1/r2/r3(`25_q3_r*.json`) → 패턴 루프 후 full-500(`28_post_fix500.json`)
- 본 문서는 **진단만** 한다. 코드 수정 없음.
- 분류기 라벨(`PREDICATE_DROPPED` 등)은 참고용이며 원인으로 쓰지 않는다.

## 검증 (2026-08-25, 함수 재실행)

방향(Q3 패치가 남은 20건에 안 닿음)은 맞다. 아래만 문장을 고친다.

- **Q223:** LLM이 모호하다고 판단한 것이 1차가 아니다. `try_heuristic_plan`이 **None**이다. 힌트에는 `place=금정구`, `ratio=True`, `special_land='산'`이 있는데, 질문 본문에 `건물`/`용도` 키워드가 없어 heuristic이 포기한다. 그다음 LLM(~13초) 실패 후 `heuristic_incomplete` clarify. gold SQL은 `A7='산' / 전체`라 heuristic이 타기만 하면 Q230과 같은 비율 규칙으로 맞는다.
- **Q220 full28:** r3의 장소 건수 훔침은 맞다. full에서는 plan까지 가서 **건수 2,344는 맞고**(`A27>0`), 합계를 지하층(`A27`)이 아니라 **연면적 A14**로 집계해 hits=1로 남는다.
- **Q254:** “Q4/Q5 부작용”은 추정이다. 확인된 사실만: Q3 r3는 건물 연면적 rank, full28은 heuristic `group_by=sigungu_name`(plan 1ms). 현재 `try_heuristic_plan`은 구별 집계를 만든다. Q3 ORDER BY 패치가 통과시킨 것은 아니다.
- 본문 “8개 구멍”은 오기다. 유형은 **A–E 다섯**이다.

## 한 줄 결론

Q3 3회 수정은 **이미 계획(plan)까지 들어간 단순 group-rank / 다중 집계 / “전체” 메타 훔침**만 겨냥했다.  
남은 20문항은 그 세 구멍이 아니라 **레거시가 plan 앞에서 가로채기**, **비율 분모·분자 컴파일**, **GROUP BY 키워드 공백**, **집계 함수·술어 미생성**이다. 그래서 ORDER BY/`_MAX_AGG`/메타 키워드 패치가 반복돼도 점수가 거의 안 움직인다.

## 점수 궤적

| 시점 | Q3 24문항 | 통과 ID |
|---|---:|---|
| 20차 full (r0) | **0/24** | — |
| Q3 r1 | **3/24** | Q227, Q232, Q237 |
| Q3 r2 | **3/24** | 동일 |
| Q3 r3 | **4/24** | + Q230 |
| 이후 full-500 (`28`) | **5/24** | + Q254 (Q3 패치가 아님) |

r1에서 붙은 3건이 Q3 패치의 **전부**이고, r2는 0건, r3는 메타 `"전체"` 제거로 **Q230 1건**만 추가됐다.

## Q3에 실제로 넣은 수정과, 그것이 고친 것

| 수정 | 겨냥한 구멍 | 실제로 통과시킨 문항 | 나머지에 안 닿는 이유 |
|---|---|---|---|
| `compiler._order_sql`: `group_by`+`aggregations`이고 `order_by`가 없으면 `ORDER BY <alias> DESC NULLS LAST` | 용도별 상위 집계 SQL에 ORDER BY 없음 → `sql_validator` 거절 | **Q227, Q232** | 전제 `plan.group_by`가 있어야 한다. **Q242**는 `구조별`을 group_by로 안 넣는다. **Q200/Q201/Q254(r3)/Q256**은 plan 전에 레거시가 가져간다. |
| `validator._MAX_AGG` 4→8 | 합계·평균·최대를 한 질의에 넣으면 `too many aggregations` | **Q237** | 다중 집계 거절이 원인인 문항은 Q237뿐이었다. |
| `meta_qa`: 비율 힌트 + `_asks_catalog`에서 단독 `"전체"` 제거 | 비율 질의가 `meta_catalog`로 새김 | **Q230** (r3) | **Q223**은 메타를 빠져나온 뒤 **LLM plan이 clarify**. 비율 SQL 자체의 분모 버그(Q231/Q238/Q222/Q246/Q251)는 손대지 않았다. |

## 원인 유형 (구멍 단위)

남은 실패는 아래 **A–E** 구멍으로 나뉜다. 한 문항이 두 구멍에 걸치면 주원인을 앞에 적는다.

### A. 레거시가 plan보다 먼저 실행 (Q3 패치 미도달)

파이프라인은 `is_profile_question` / `match_route` 조기 라우트가 semantic plan보다 앞이다. Q3 수정은 compiler·validator·meta만 바꿨다.

| ID | 질문 요지 | 실제 라우트 (r3) | 원인 |
|---|---|---|---|
| **Q200** | 해운대구 **용적율 상위 10개** 공동주택 이름·용적율·높이 | `building_profile` | `_wants_far_focus`가 `용적율`만 봐도 프로필로 본다. `is_profile_question`은 `상위`/`이름`을 제외하지 않는다. 실행 SQL은 상위 10 목록이 아니라 AVG/PERCENTILE **요약 집계**. gold 1위 `마린시티두산위브포세이돈`이 답에 없다. r0~full28 동일. |
| **Q201** | 수영구 **건폐율 상위 8개** 숙박시설 이름·건폐율·연면적 | `building_profile` | Q200과 동일. `건폐율` → 프로필. gold의 `호텔아쿠아펠리스` 누락. |
| **Q220** | 동구 **지하층 합계**와 **지하층이 있는 건물 수** | `building_place_count` | `_route_place_building_count`가 `건물`+건수 키워드면 COUNT(*)만 탄다. 제외 목록에 `지상층`/`층수`는 있고 **`지하층`은 없다**. SQL: `COUNT(*) … LIKE '%동구%'`. 답 19,562채. gold는 2,344 / 2,682. |
| **Q239** | 대연동 공동주택 **층수 구간별** (1-5, 6-10, 11-20, 21+) | `d198_value_bins` | `looks_like_value_bin_question`이 `구간별`+`층수`면 D198 A31 등폭 빈으로 보낸다. 대연동은 남구라 D198(동래·금정)에 없고 0건. gold는 D010 지상층 **고정 구간** 4개. |
| **Q252** | 남구 숙박시설이 있는 **법정동별** 채수 | `building_usage_count` | 용도+장소 건수 레거시가 `법정동별` GROUP BY를 무시하고 스칼라 `COUNT(*)`. 답 67채. |
| **Q256** | 사하구 공장 연면적 **상위 10% 경계값(90백분위)** | `building_rank_연면적` | `_extract_top_n`/`상위 10`이 **상위 10채 목록**으로 해석. PERCENTILE_CONT(0.9)가 아니다. SQL `ORDER BY A14 DESC LIMIT 10`. |
| **Q298** | 북구 기초구역 **면적 합계와 개수** | `bas_area_topn` | `_route_basic_zone_area_rank`는 `기초구역`+`면적`이면 합계가 아니라 `ORDER BY BAS_AR LIMIT 1`(default n=1). 답 면적 5.768, 개수 1. gold 154곳 / 39.7834. |

### B. 비율 컴파일: 모든 술어를 FILTER로 올려 분모가 장소 전체가 됨

`compiler`는 `ratio_percent`이면 술어를 WHERE가 아니라 `COUNT(*) FILTER (WHERE …)`에 넣고, 분모는 `COUNT(*)`(장소만).  
형태 **「집합 A 중 조건 B 비율」**은 `B∩A / A`여야 하는데 `A∩B / 장소전체`가 된다.

| ID | 질문 | 나온 SQL 의미 | gold가 요구하는 의미 | 관측값 |
|---|---|---|---|---|
| **Q231** | 영도구 **15층 이상 건물 중** 공동주택 비율 | `(공동주택 ∧ 층≥15) / 영도구 전체` | `공동주택 ∧ 층≥15 / 층≥15` | 0.6051 vs 91.716 |
| **Q238** | 장림동 **공장 중** 연면적 1000㎡ 이상 비율 | `(공장 ∧ 면적≥1000) / 장림동 전체` | `면적≥1000 / 장림동 공장` | 3.5889 vs 24.7444 |
| **Q222** | 사하구 위반 비율 **위반/(위반+N)** | `A20='Y' / 사하구 전체` | 질문이 명시한 `Y / (Y+N)` (기타 A20 제외) | 0.928 vs 1.5357 |
| **Q246** | 우동 **높이 50m 이상 비율과 20층 이상 비율** (두 비율) | 한 비율: `(h≥50 ∧ 층≥20) / 우동` | 두 스칼라: `h≥50 / 전체`, `층≥20 / 전체` | 7.803 하나 vs 2.3586 / 1.7153 |
| **Q251** | 사상구 **산단 안 공장 / 사상구 공장** | 사상구∩산단 **건물 중 공장 비율** (`FILTER 공장` / `COUNT` WHERE EXISTS 산단) | 분자=산단∩공장, 분모=사상구 공장 | 40.6885 vs 42.1833 (가깝지만 분모가 다름) |

Q230이 r3에서 통과한 이유: 분모가 **장소 전체**, 분자가 **용도=공동주택**이라 이 컴파일 규칙과 **우연히 일치**한다. Q231/Q238은 분모가 부분집합이라 같은 규칙이 틀린다.

### C. GROUP BY·순위 plan이 안 만들어져 ORDER BY 패치가 공회전

compiler ORDER BY 주입 조건: `plan.group_by` **그리고** `plan.aggregations`.  
heuristic group_by 트리거는 `"용도별"` / `"층수별"` / `"구별"` 뿐. **`"구조별"` 없음.**

| ID | 질문 | r3 SQL / 라우트 | 원인 |
|---|---|---|---|
| **Q242** | 사상구 공장 **구조별** 건수·평균 연면적 **상위 6** | GROUP BY 없는 `AVG(A14), COUNT(*) WHERE 공장`. route=`None`, `engine-fail: Ranking questions require ORDER BY ... DESC NULLS LAST and LIMIT.` | 질문은 `상위`라 validator가 ORDER BY를 요구. plan은 group_by가 없어 compiler가 ORDER BY를 **넣지 않음**. 구조별 집계 자체가 없음. r0~full28 동일. |
| **Q254** (r3) | 부산 **구별** 위반건축물 수 상위 8개 **구** | `semantic_plan_rank`: 위반 건물을 **연면적 상위 8채** 목록 | r3는 구 단위 COUNT가 아님. full28은 heuristic `group_by=sigungu_name`으로 통과(plan 1ms). Q3 ORDER BY 패치의 결과가 아니다. |

### D. plan은 타지만 술어·함수가 질문과 다름

| ID | 질문 | 나온 SQL | 원인 |
|---|---|---|---|
| **Q221** | 남구 건물동명에 **'상가'가 들어가는** 수와 평균 연면적 | `A25 IS NOT NULL` (남구) | 따옴표 추출 정규식이 `건물동명[이은는가]?`만 허용. 실제 문장은 **`건물동명에 '상가'`** 이라 매칭 실패 → `건물동명`만 보고 `is_not_null`. 답 n=2,587 vs gold 73. |
| **Q243** | 중구 **높이 있는** 건물의 평균·**표준편차** 높이 | `AVG(A16)` only, 높이 존재 필터 없음 | 집계 함수 맵에 **stddev 없음**. `높이 있는` 술어도 안 붙음. 평균 5.52 vs gold 13.87(n=3,081, sd=9.86). |
| **Q261** | 숙박시설 **평균 A12/A14** | `AVG(A14), AVG(A12)` 따로 | 비율의 평균이 아니라 평균의 나열. `AVG(A12)/AVG(A14)`도 `AVG(A12/A14)`도 아님. |
| **Q265** | 해운대구 공동주택 높이 합계 **(1~500m만)** 와 건수 | SUM/COUNT에 질문 구간(1~500) **plus** `_sane_height_sql`(A16≤600, 층수 휴리스틱) | 가드가 gold 집합을 깎음. n 2,876 vs 2,883, 합 80,009 vs 80,450. |
| **Q286** | **대연3동** 교육연구시설 대지면적 **합계** | `SUM(A15)` + 행정동 조인, **`LIMIT 3`**, COUNT 없음 | `_extract_limit`가 `(숫자)동`을 상위 N으로 본다. **`대연3동` → LIMIT 3**. 합계 스칼라는 gold와 맞지만(hits=1) gold의 건수 102가 없어 실패. |

### E. 메타 탈출 후 heuristic 없음 → clarify (Q223만)

| ID | r0–r2 | r3 / full28 | 원인 |
|---|---|---|---|
| **Q223** | `meta_catalog` (`전체`가 카탈로그 키워드) | `semantic_plan_clarify`, SQL 없음. plan 단계 ~13초. 답: 「질문을 완전히 해석하지 못해 확인이 필요합니다」 | `"전체"` 제거는 메타만 끊었다. 힌트는 `special_land='산'`+비율인데, 본문에 `건물`/`용도`가 없어 `try_heuristic_plan`이 None. LLM 실패 후 `heuristic_incomplete` clarify. gold는 `A7='산'/전체`라 heuristic이 타면 비율 규칙과 맞는다. |

## 문항별 한 줄 (24)

| ID | r3 | full28 | 주원인 구멍 |
|---|---|---|---|
| Q200 | FAIL profile | FAIL profile | A 프로필(용적율) |
| Q201 | FAIL profile | FAIL profile | A 프로필(건폐율) |
| Q220 | FAIL place_count | FAIL plan (hits=1) | A 장소 건수 / 지하층 이중 집계 미생성 |
| Q221 | FAIL plan | FAIL plan | D 동명 contains 미추출 |
| Q222 | FAIL plan | FAIL plan | B 분모 전체 vs (Y+N) |
| Q223 | FAIL clarify | FAIL clarify | E 메타→clarify |
| Q227 | **OK** | **OK** | (r1) group-rank ORDER BY |
| Q230 | **OK** | **OK** | (r3) 메타 `"전체"` 제거, 분모=장소 전체라 B와 일치 |
| Q231 | FAIL plan | FAIL plan | B 조건부 비율 분모 |
| Q232 | **OK** | **OK** | (r1) group-rank ORDER BY |
| Q237 | **OK** | **OK** | (r1) `_MAX_AGG` |
| Q238 | FAIL plan | FAIL plan | B 조건부 비율 분모 |
| Q239 | FAIL d198 bins | FAIL d198 bins | A D198 등폭 빈 |
| Q242 | FAIL engine ORDER BY | FAIL 동일 | C `구조별` group_by 없음 |
| Q243 | FAIL plan | FAIL plan | D stddev·높이존재 |
| Q246 | FAIL plan | FAIL plan | B 두 비율 → AND 한 비율 |
| Q251 | FAIL plan | FAIL plan | B 산단비율 분모 |
| Q252 | FAIL usage_count | FAIL 동일 | A 레거시 스칼라 |
| Q254 | FAIL rank 건물 | **OK** aggregate | C r3는 구별 집계 실패; full 통과는 Q3 패치 외 |
| Q256 | FAIL rank 목록 | FAIL 동일 | A 백분위→상위 N채 |
| Q261 | FAIL plan | FAIL plan | D 비(比) vs 두 AVG |
| Q265 | FAIL plan | FAIL plan | D 높이 sane 가드 |
| Q286 | FAIL plan | FAIL plan | D `3동`→LIMIT 3, COUNT 누락 |
| Q298 | FAIL bas topn | FAIL 동일 | A 합계→최대 1건 |

## 왜 “수정을 반복해도” 안 붙는가

1. **구멍 진단이 3문항에 과적합됐다.** 20차에서 눈에 띈 실패 모드(ORDER BY 없음, agg 개수, meta `전체`)로 24문항을 묶었지만, 그 모드의 실제 피해자는 Q227/Q232/Q237/Q230 네 개뿐이다.
2. **패치 지점이 plan 컴파일 이후다.** A유형 7문항은 compiler/validator에 도달하지 않는다. Q242는 도달해도 `group_by`가 없어 ORDER BY 주입이 건너뛴다.
3. **비율은 “plan으로 보낸 것”과 “맞는 비율 SQL”이 다르다.** 메타를 plan으로 돌리는 것만으로는 Q231류가 통과하지 않는다. Q230만 분모 규칙과 맞다.
4. **r2는 공회전이다.** r1 패치 이후 같은 24문항을 다시 돌려도 라우트·SQL이 실패 문항에서 변하지 않았다.
5. **full-500의 Q254 1건은 Q3 루프 성공이 아니다.** r3까지 실패했고, 이후 heuristic 구별 집계가 실행되어 통과했다.

## 근거 산출

- 문항 집합: `artifacts/systematic_fix/22_pattern_ids.json`
- 패턴 정의: `artifacts/systematic_fix/22_patterns.md`
- 부분평가: `25_q3_r1.json` / `25_q3_r2.json` / `25_q3_r3.json` 및 `*_fail.md`
- 전후 full: `20_post_fix500.json`, `28_post_fix500.json`
- 문항별 SQL·라우트 원표: `artifacts/systematic_fix/30_q3_stuck_raw.md`
