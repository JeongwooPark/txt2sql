# SQP v1.1 결정 기록

## ADR-0001 작업트리를 원 저장소와 분리한다

- 상태: accepted
- 맥락: `D:\py_workspace\llm2sql`에 사용자 untracked 스크립트 5개가 있음
- 결정: `git worktree add D:\py_workspace\llm2sql-sqp-v11 -b feat/sqp-v11-roadmap`
- 결과: 사용자 파일을 커밋하지 않음

## ADR-0002 정적 분석 도구를 새로 도입하지 않는다

- 상태: accepted
- 맥락: 저장소에 ruff/mypy/CI가 없음
- 결정: `uv run pytest`와 `git diff --check`만 사용

## ADR-0003 카탈로그 테이블 식별은 대소문자 보존 이름으로 기록한다

- 상태: accepted
- 맥락: `to_regclass('public.AL_D010_26_20250704')`는 소문자 fold 때문에 false를 반환할 수 있음
- 결정: `pg_class.relname` 실측 목록을 snapshot 식별자로 사용
- 식별자: `public.AL_D010_26_20250704`, `public.BND_ADM_DONG_PG`, `public.TL_KODIS_BAS_26_202507`, `public.AL_D060_00_20250804`
