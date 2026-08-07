"""한글/영문 자판 오타(IME 미전환) 정규화."""

from __future__ import annotations

# 두벌식: 한글 자모 → 사용자가 누른 영문 키
_JAMO_TO_KEY: dict[str, str] = {
    "ㄱ": "r",
    "ㄲ": "R",
    "ㄴ": "s",
    "ㄷ": "e",
    "ㄸ": "E",
    "ㄹ": "f",
    "ㅁ": "a",
    "ㅂ": "q",
    "ㅃ": "Q",
    "ㅅ": "t",
    "ㅆ": "T",
    "ㅇ": "d",
    "ㅈ": "w",
    "ㅉ": "W",
    "ㅊ": "c",
    "ㅋ": "z",
    "ㅌ": "x",
    "ㅍ": "v",
    "ㅎ": "g",
    "ㅏ": "k",
    "ㅐ": "o",
    "ㅑ": "i",
    "ㅒ": "O",
    "ㅓ": "j",
    "ㅔ": "p",
    "ㅕ": "u",
    "ㅖ": "P",
    "ㅗ": "h",
    "ㅘ": "hk",
    "ㅙ": "ho",
    "ㅚ": "hl",
    "ㅛ": "y",
    "ㅜ": "n",
    "ㅝ": "nj",
    "ㅞ": "np",
    "ㅟ": "nl",
    "ㅠ": "b",
    "ㅡ": "m",
    "ㅢ": "ml",
    "ㅣ": "l",
    "ㄳ": "rt",
    "ㄵ": "sw",
    "ㄶ": "sg",
    "ㄺ": "fr",
    "ㄻ": "fa",
    "ㄼ": "fq",
    "ㄽ": "ft",
    "ㄾ": "fx",
    "ㄿ": "fv",
    "ㅀ": "fg",
    "ㅄ": "qt",
}

_CHO = [
    "ㄱ",
    "ㄲ",
    "ㄴ",
    "ㄷ",
    "ㄸ",
    "ㄹ",
    "ㅁ",
    "ㅂ",
    "ㅃ",
    "ㅅ",
    "ㅆ",
    "ㅇ",
    "ㅈ",
    "ㅉ",
    "ㅊ",
    "ㅋ",
    "ㅌ",
    "ㅍ",
    "ㅎ",
]
_JUNG = [
    "ㅏ",
    "ㅐ",
    "ㅑ",
    "ㅒ",
    "ㅓ",
    "ㅔ",
    "ㅕ",
    "ㅖ",
    "ㅗ",
    "ㅘ",
    "ㅙ",
    "ㅚ",
    "ㅛ",
    "ㅜ",
    "ㅝ",
    "ㅞ",
    "ㅟ",
    "ㅠ",
    "ㅡ",
    "ㅢ",
    "ㅣ",
]
_JONG = [
    "",
    "ㄱ",
    "ㄲ",
    "ㄳ",
    "ㄴ",
    "ㄵ",
    "ㄶ",
    "ㄷ",
    "ㄹ",
    "ㄺ",
    "ㄻ",
    "ㄼ",
    "ㄽ",
    "ㄾ",
    "ㄿ",
    "ㅀ",
    "ㅁ",
    "ㅂ",
    "ㅄ",
    "ㅅ",
    "ㅆ",
    "ㅇ",
    "ㅈ",
    "ㅊ",
    "ㅋ",
    "ㅌ",
    "ㅍ",
    "ㅎ",
]

_EXIT_COMMANDS = frozenset(
    {
        "exit",
        "quit",
        "q",
        "종료",
        "나가기",
        "끝",
    }
)


def hangul_keyboard_to_latin(text: str) -> str:
    """한글 자판으로 친 글을 눌린 영문 키열로 복원 (예: 벼ㅑㅅ → quit)."""
    out: list[str] = []
    for ch in text:
        if "가" <= ch <= "힣":
            code = ord(ch) - 0xAC00
            cho = _CHO[code // 588]
            jung = _JUNG[(code % 588) // 28]
            jong = _JONG[code % 28]
            for jamo in (cho, jung, jong):
                if not jamo:
                    continue
                out.append(_JAMO_TO_KEY.get(jamo, jamo))
        elif ch in _JAMO_TO_KEY:
            out.append(_JAMO_TO_KEY[ch])
        else:
            out.append(ch)
    return "".join(out)


def is_exit_command(text: str) -> bool:
    """exit/quit/종료 및 한글자판 오타(/벼ㅑㅅ 등)를 종료로 인식."""
    raw = text.strip()
    if not raw:
        return False
    candidates = {raw, raw.lstrip("/\\").strip()}
    lowered: set[str] = set()
    for c in candidates:
        if not c:
            continue
        lowered.add(c.lower())
        lowered.add(hangul_keyboard_to_latin(c).lower())
        # 슬래시만 제거한 뒤 자판 복원
        stripped = c.lstrip("/\\").strip()
        if stripped != c:
            lowered.add(hangul_keyboard_to_latin(stripped).lower())
    return bool(lowered & _EXIT_COMMANDS)
