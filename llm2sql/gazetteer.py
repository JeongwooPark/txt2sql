"""부산 시도·구군·법정동·행정동 지명 사전.

정규식(~동) 대신 등록된 명칭만 최장일치로 찾아, 구서역·공동주택 같은 오탐을 줄인다.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
from typing import Iterable


class _TrieNode:
    """지명 최장일치용 트라이 노드."""

    __slots__ = ("children", "term")

    def __init__(self) -> None:
        self.children: dict[str, _TrieNode] = {}
        self.term: str | None = None


def _build_name_trie(names: tuple[str, ...]) -> _TrieNode:
    root = _TrieNode()
    for name in names:
        node = root
        for ch in name:
            nxt = node.children.get(ch)
            if nxt is None:
                nxt = _TrieNode()
                node.children[ch] = nxt
            node = nxt
        node.term = name
    return root


KIND_SIDO = "sido"
KIND_SIGUNGU = "sigungu"
KIND_LEGAL = "legal_dong"
KIND_ADMIN = "admin_dong"

_DATA_NAME = "gazetteer_data.json"


@dataclass(frozen=True)
class PlaceHit:
    name: str
    kinds: frozenset[str]
    start: int
    end: int

    @property
    def is_admin_only(self) -> bool:
        """법정동 주소(A4)에 없고 행정동 경계로만 집계해야 하는 동."""
        return KIND_ADMIN in self.kinds and KIND_LEGAL not in self.kinds

    @property
    def is_dong(self) -> bool:
        return bool(self.kinds & {KIND_LEGAL, KIND_ADMIN})

    @property
    def is_sigungu(self) -> bool:
        return KIND_SIGUNGU in self.kinds


@dataclass(frozen=True)
class Gazetteer:
    sido: frozenset[str]
    sigungu: frozenset[str]
    legal_dong: frozenset[str]
    admin_dong: frozenset[str]
    names_by_len: tuple[str, ...]
    kinds_of: dict[str, frozenset[str]]
    name_trie: _TrieNode


def _kinds_map(
    sido: Iterable[str],
    sigungu: Iterable[str],
    legal: Iterable[str],
    admin: Iterable[str],
) -> dict[str, frozenset[str]]:
    acc: dict[str, set[str]] = {}
    for name, kind in (
        *((n, KIND_SIDO) for n in sido),
        *((n, KIND_SIGUNGU) for n in sigungu),
        *((n, KIND_LEGAL) for n in legal),
        *((n, KIND_ADMIN) for n in admin),
    ):
        if not name:
            continue
        acc.setdefault(name, set()).add(kind)
    return {k: frozenset(v) for k, v in acc.items()}


@lru_cache(maxsize=1)
def load_gazetteer() -> Gazetteer:
    raw = json.loads(
        files("llm2sql").joinpath(_DATA_NAME).read_text(encoding="utf-8")
    )
    sido = tuple(raw.get("sido") or ()) + tuple(raw.get("sido_aliases") or ())
    sigungu = tuple(raw.get("sigungu") or ())
    legal = tuple(raw.get("legal_dong") or ())
    admin = tuple(raw.get("admin_dong") or ())
    kinds = _kinds_map(sido, sigungu, legal, admin)
    # 시도 별칭(부산)은 건물명(부산대학교) 오탐이 커서 지명 스캔에서 뺀다.
    scan = {
        n
        for n, ks in kinds.items()
        if KIND_SIDO not in ks or n in set(raw.get("sido") or ())
    }
    names = tuple(sorted(scan, key=len, reverse=True))
    return Gazetteer(
        sido=frozenset(sido),
        sigungu=frozenset(sigungu),
        legal_dong=frozenset(legal),
        admin_dong=frozenset(admin),
        names_by_len=names,
        kinds_of=kinds,
        name_trie=_build_name_trie(names),
    )


def classify_place(name: str) -> frozenset[str]:
    if not name:
        return frozenset()
    return load_gazetteer().kinds_of.get(name.strip(), frozenset())


def is_known_place(name: str) -> bool:
    return bool(classify_place(name))


def is_admin_dong(name: str | None) -> bool:
    return bool(name) and KIND_ADMIN in classify_place(str(name))


def is_legal_dong(name: str | None) -> bool:
    return bool(name) and KIND_LEGAL in classify_place(str(name))


def uses_admin_boundary(name: str | None) -> bool:
    """번호 행정동·행정전용 동은 경계 교차, 법정동은 A4."""
    if not name:
        return False
    kinds = classify_place(str(name))
    if KIND_ADMIN in kinds and KIND_LEGAL not in kinds:
        return True
    return False


def is_locality(name: str | None) -> bool:
    """법정동·행정동·리·가·읍·면 (구·군·시도 제외)."""
    if not name:
        return False
    return bool(classify_place(str(name)) & {KIND_LEGAL, KIND_ADMIN})


_HANGUL_SYL = re.compile(r"[가-힣]")
_SHORT_RI_PARTICLES = (
    "으로",
    "에서",
    "까지",
    "부터",
    "이랑",
    "이나",
    "은",
    "는",
    "이",
    "가",
    "을",
    "를",
    "의",
    "에",
    "와",
    "과",
    "도",
    "만",
    "로",
    "랑",
)


def _short_ri_ok(text: str, start: int, end: int, name: str) -> bool:
    """2글자 리(원리·고리)는 단어 경계일 때만. 원리원칙·고리원자력 오탐 방지."""
    if len(name) > 2 or not name.endswith("리"):
        return True
    if start > 0 and _HANGUL_SYL.match(text[start - 1]):
        return False
    rest = text[end:]
    if not rest:
        return True
    if not _HANGUL_SYL.match(rest[0]):
        return True
    for p in _SHORT_RI_PARTICLES:
        if rest.startswith(p):
            return True
    return False


def _scan_places(text: str) -> tuple[PlaceHit, ...]:
    """트라이 최장일치. 2글자 리(원리·고리)는 단어 경계일 때만 채택."""
    gaz = load_gazetteer()
    hits: list[PlaceHit] = []
    i = 0
    n = len(text)
    root = gaz.name_trie
    kinds_of = gaz.kinds_of
    while i < n:
        node: _TrieNode | None = root
        j = i
        best: str | None = None
        while node is not None and j < n:
            node = node.children.get(text[j])
            if node is None:
                break
            j += 1
            if node.term is not None and _short_ri_ok(text, i, j, node.term):
                best = node.term
        if best is None:
            i += 1
            continue
        hits.append(PlaceHit(best, kinds_of.get(best, frozenset()), i, i + len(best)))
        i += len(best)
    return tuple(hits)


@lru_cache(maxsize=1024)
def find_places(text: str) -> tuple[PlaceHit, ...]:
    """질문에 등장하는 등록 지명을 왼쪽부터 최장일치로 찾는다."""
    if not text:
        return ()
    return _scan_places(text)


def extract_gazetteer_places(text: str) -> list[str]:
    """동(법정·행정)을 먼저, 없으면 구·군. 등장 순서."""
    dongs: list[str] = []
    gus: list[str] = []
    seen: set[str] = set()
    for hit in find_places(text):
        if hit.name in seen:
            continue
        if hit.is_dong:
            seen.add(hit.name)
            dongs.append(hit.name)
        elif hit.is_sigungu:
            seen.add(hit.name)
            gus.append(hit.name)
    return dongs or gus
