"""Semantic-boundary chunking — ADR-0003 (~512 tokens, ~15% overlap)."""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

_PARA = re.compile(r"\n\s*\n")
_SENT = re.compile(r"(?<=[.!?])\s+")
_WORD = re.compile(r"\S+")


@dataclass
class Chunk:
    index: int
    content: str
    char_start: int
    char_end: int
    token_count: int


def _segments(text: str) -> list[tuple[int, int]]:
    """Atomic spans on semantic boundaries: paragraphs, then sentences. Offsets into `text`."""
    spans: list[tuple[int, int]] = []
    pos = 0
    for para in _PARA.split(text):
        if not para.strip():
            pos += len(para)
            continue
        p_start = text.find(para, pos)
        p_end = p_start + len(para)
        pos = p_end
        last = p_start
        for piece in _SENT.split(text[p_start:p_end]):
            if not piece.strip():
                continue
            s_start = text.find(piece, last)
            s_end = s_start + len(piece)
            spans.append((s_start, s_end))
            last = s_end
    return spans


def _pack(units: list[tuple[int, int]], text: str, count_tokens: Callable[[str], int],
          target: int, overlap_tokens: int) -> list[tuple[int, int]]:
    """Greedily pack ordered spans up to `target` tokens, stepping back for overlap."""
    out: list[tuple[int, int]] = []
    i = 0
    while i < len(units):
        tok, j = 0, i
        while j < len(units):
            t = count_tokens(text[units[j][0]:units[j][1]])
            if tok and tok + t > target:
                break
            tok += t
            j += 1
        out.append((units[i][0], units[j - 1][1]))
        if j >= len(units):
            break
        back, k = 0, j
        while k - 1 > i and back < overlap_tokens:
            back += count_tokens(text[units[k - 1][0]:units[k - 1][1]])
            k -= 1
        i = max(k, i + 1)
    return out


def _word_overlap_start(prev_start: int, prev_end: int, text: str,
                        count_tokens: Callable[[str], int], overlap_tokens: int) -> int:
    """Walk backward word-by-word within [prev_start, prev_end) to find overlap start."""
    accumulated = 0
    new_start = prev_end  # fallback: no overlap
    for m in reversed(list(_WORD.finditer(text[prev_start:prev_end]))):
        abs_pos = prev_start + m.start()
        accumulated += count_tokens(text[abs_pos: prev_start + m.end()])
        if accumulated >= overlap_tokens:
            new_start = abs_pos
            break
    return new_start


def chunk_text(text: str, count_tokens: Callable[[str], int],
               target_tokens: int = 512, overlap_ratio: float = 0.15) -> list[Chunk]:
    text = text or ""
    overlap_tokens = max(0, int(target_tokens * overlap_ratio))
    units: list[tuple[int, int]] = []
    for s, e in _segments(text):
        if count_tokens(text[s:e]) <= target_tokens:
            units.append((s, e))
        else:  # oversized single unit → word-window fallback
            words = [(m.start() + s, m.end() + s) for m in _WORD.finditer(text[s:e])]
            units.extend(_pack(words, text, count_tokens, target_tokens, max(1, overlap_tokens)))
    spans = _pack(units, text, count_tokens, target_tokens, overlap_tokens)
    # When unit-level packing produces no overlap between adjacent chunks, fall back to
    # word-level overlap so the invariant "adjacent chunks share >= overlap_tokens words"
    # holds even when every unit is larger than the overlap budget.
    if overlap_tokens > 0 and len(spans) > 1:
        adjusted: list[tuple[int, int]] = [spans[0]]
        for prev, curr in zip(spans, spans[1:]):
            if curr[0] >= prev[1]:
                new_start = _word_overlap_start(prev[0], prev[1], text,
                                                count_tokens, overlap_tokens)
                adjusted.append((new_start, curr[1]))
            else:
                adjusted.append(curr)
        spans = adjusted
    return [
        Chunk(idx, text[a:b], a, b, count_tokens(text[a:b]))
        for idx, (a, b) in enumerate(spans)
    ]
