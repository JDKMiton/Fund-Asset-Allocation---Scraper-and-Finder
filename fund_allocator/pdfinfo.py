"""Read what the collector needs from an MDD, in a worker process with a time limit.

One corrupt PDF can make a PDF library spin forever, so every MDD is read in a separate
process: if it takes longer than the limit, the worker is killed and the MDD is treated as
unreadable instead of hanging the weekly run.
"""

from __future__ import annotations

import hashlib
import multiprocessing
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from concurrent.futures.process import BrokenProcessPool
from pathlib import Path

import pdfplumber

MASTHEAD_FRACTION = 0.15  # the masthead is the top 15% of page 1
TEXT_PAGES = 6            # the month, ISIN and fund name are always on the first pages


class PdfTimeout(RuntimeError):
    pass


def sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def masthead_text(page, fraction: float = MASTHEAD_FRACTION) -> str:
    """Words printed in the top part of a page, top to bottom. Position, not text order:
    a PDF's text order is its drawing order, which often starts with a side panel."""
    cut = page.height * fraction
    words = [w for w in page.extract_words(use_text_flow=False) if w["bottom"] <= cut]
    words.sort(key=lambda w: (round(w["top"]), w["x0"]))
    return " ".join(w["text"] for w in words)


def analyse(path: str) -> dict:
    """Text of the first pages, the page-1 masthead and the Fund AUM / Inception / Benchmark facts."""
    from .facts import mdd_facts
    with pdfplumber.open(path) as pdf:
        pages = pdf.pages[:TEXT_PAGES]
        text = "\n".join(p.extract_text() or "" for p in pages)
        masthead = masthead_text(pdf.pages[0]) if pdf.pages else ""
    return {"text": text, "masthead": masthead, "facts": mdd_facts(path, text)}


_pool: ProcessPoolExecutor | None = None


def _executor() -> ProcessPoolExecutor:
    global _pool
    if _pool is None:
        _pool = ProcessPoolExecutor(max_workers=1, mp_context=multiprocessing.get_context("spawn"))
    return _pool


def _reset() -> None:
    global _pool
    if _pool is not None:
        for proc in list(getattr(_pool, "_processes", {}).values()):
            proc.kill()
        _pool.shutdown(wait=False, cancel_futures=True)
        _pool = None


def analyse_with_timeout(path: str | Path, timeout: float = 120) -> dict:
    """analyse() in a worker process; raises PdfTimeout if the PDF takes longer than ``timeout``."""
    future = _executor().submit(analyse, str(path))
    try:
        return future.result(timeout=timeout)
    except FutureTimeout:
        _reset()
        raise PdfTimeout(f"reading {Path(path).name} took longer than {timeout:.0f}s") from None
    except BrokenProcessPool:  # the worker died (e.g. out of memory): start a fresh one next time
        _reset()
        raise


def shutdown() -> None:
    _reset()
