"""Matches the reference pages (e.g. the translation) with the original ones, without AI.

Anchors: words identical in both languages (code identifiers, acronyms, surnames) and
normalized figure references. Each anchor weighs by how rare it is (idf). Then a monotonic
dynamic program picks the highest-scoring path: the original page advances 0, 1 or 2 per
reference page. Manual anchors pin the path.
"""

import math
import re
from collections import Counter

WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]{3,}")
FIGURE = re.compile(r"\b(?:Figure|Figura|Fig\.)\s+(\d+\.\d+)")
STEPS = (0, 1, 2)


def anchors(text):
    tokens = {w.lower() for w in WORD.findall(text)}
    tokens |= {"fig:" + n for n in FIGURE.findall(text)}
    return tokens


def compute(ref_texts, orig_texts, fixed=None):
    """For each reference page, the original page (both 1-based).

    `fixed` is {ref_page: orig_page} with manual corrections the path must respect.
    """
    fixed = fixed or {}
    ref = [anchors(t) for t in ref_texts]
    orig = [anchors(t) for t in orig_texts]

    # Only what exists in both books counts: what doesn't get translated.
    common = set().union(*ref) & set().union(*orig)
    ref = [a & common for a in ref]
    orig = [a & common for a in orig]
    df = Counter(t for a in ref + orig for t in a)
    total = len(ref) + len(orig)
    idf = {t: math.log(total / c) for t, c in df.items()}

    R, O = len(ref), len(orig)
    none = float("-inf")
    score = [[none] * O for _ in range(R)]
    back = [[0] * O for _ in range(R)]
    for i in range(R):
        pinned = fixed.get(i + 1)
        columns = [pinned - 1] if pinned and 0 < pinned <= O else range(O)
        for j in columns:
            gain = sum(idf[t] for t in ref[i] & orig[j])
            if i == 0:
                score[i][j] = gain
                continue
            best, prev = none, j
            for k in STEPS:
                if j - k >= 0 and score[i - 1][j - k] > best:
                    best, prev = score[i - 1][j - k], j - k
            if best == none and pinned:
                # A manual anchor may require a bigger jump: allow it from any earlier
                # column so the path isn't cut.
                for k in range(j + 1):
                    if score[i - 1][k] > best:
                        best, prev = score[i - 1][k], k
            if best > none:
                score[i][j] = best + gain
                back[i][j] = prev

    j = max(range(O), key=lambda c: score[R - 1][c])
    path = [0] * R
    for i in range(R - 1, -1, -1):
        path[i] = j + 1
        j = back[i][j]
    return path


def original_range(map, start, end):
    """Original pages covering a reference range."""
    pages = map[start - 1:end]
    return min(pages), max(pages)


def reference_range(map, start, end):
    """Reference pages that fall within an original range."""
    pages = [i + 1 for i, p in enumerate(map) if start <= p <= end]
    return (min(pages), max(pages)) if pages else None
