from txt2sql.config import load_settings
from txt2sql.pipeline import ask

s = load_settings()
cases = [
    "송정동 건물 몇 채야?",  # 강서/해운대 모호
    "하동 아파트 특징은?",  # 없는 지명
    "좋은 동네 추천해줘",  # 모호 형용사
    "A14 상위 5개 보여줘",  # 컬럼만, 테이블 불명
    "타워팰리스 건물은 몇 채?",  # 미지 고유명
    "구서동 아파트의 특징은?",  # 정상 통과
    "현재 사용가능한 데이터는 몇개야?",  # 정상 메타
]
for q in cases:
    print("=" * 60)
    print("Q:", q)
    r = ask(q, s)
    print("route:", r.get("route"))
    print((r.get("answer") or "")[:350])
    print("ms:", (r.get("steps") or [{}])[-1].get("elapsed_ms"))
