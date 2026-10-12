"""Download MDD / fact sheet PDFs from fund manager websites."""

from __future__ import annotations

import hashlib
import logging
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

from .config import FundSource

log = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36 FundAllocator/0.1"
)


class ScrapeError(RuntimeError):
    pass


class Scraper:
    def __init__(self, download_dir: str | Path = "data/downloads", delay: float = 1.0,
                 respect_robots: bool = True, timeout: float = 30.0):
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.delay = delay
        self.respect_robots = respect_robots
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self._robots: dict[str, RobotFileParser] = {}
        self._last_request = 0.0

    # -- public API ---------------------------------------------------------

    def fetch(self, source: FundSource) -> Path:
        """Return a local path to the PDF for ``source``, downloading it if needed."""
        if source.file:
            path = Path(source.file)
            if not path.exists():
                raise ScrapeError(f"local file not found: {path}")
            return path
        if source.url:
            return self.download(source.url, source.name)
        if source.page:
            pdf_url = self.find_pdf_link(source.page, source.link_match, source.render)
            return self.download(pdf_url, source.name)
        raise ScrapeError(f"{source.name}: nothing to fetch")

    def find_pdf_link(self, page_url: str, pattern: str, render: bool = False) -> str:
        html = self._render(page_url) if render else self._get(page_url).text
        links = find_matching_links(html, page_url, pattern)
        if not links:
            raise ScrapeError(f"no PDF link matching /{pattern}/ found on {page_url}")
        log.info("found %d candidate link(s) on %s, using %s", len(links), page_url, links[0])
        return links[0]

    def download(self, url: str, name: str) -> Path:
        resp = self._get(url)
        content = resp.content
        if not content.startswith(b"%PDF"):
            raise ScrapeError(f"{url} did not return a PDF (content-type {resp.headers.get('content-type')})")
        digest = hashlib.sha1(content).hexdigest()[:8]
        path = self.download_dir / f"{slugify(name)}-{digest}.pdf"
        path.write_bytes(content)
        log.info("saved %s -> %s", url, path)
        return path

    # -- internals ----------------------------------------------------------

    def _allowed(self, url: str) -> bool:
        if not self.respect_robots:
            return True
        parts = urlparse(url)
        root = f"{parts.scheme}://{parts.netloc}"
        if root not in self._robots:
            rp = RobotFileParser()
            try:
                resp = self.session.get(urljoin(root, "/robots.txt"), timeout=self.timeout)
                rp.parse(resp.text.splitlines() if resp.ok else [])
            except requests.RequestException:
                rp.parse([])
            self._robots[root] = rp
        return self._robots[root].can_fetch(USER_AGENT, url)

    def _get(self, url: str) -> requests.Response:
        if not self._allowed(url):
            raise ScrapeError(f"robots.txt disallows {url} (use --ignore-robots only if you have permission)")
        wait = self.delay - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        try:
            resp = self.session.get(url, timeout=self.timeout)
        except requests.RequestException as exc:
            raise ScrapeError(f"request failed for {url}: {exc}") from exc
        finally:
            self._last_request = time.monotonic()
        if not resp.ok:
            raise ScrapeError(f"HTTP {resp.status_code} for {url}")
        return resp

    def _render(self, url: str) -> str:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise ScrapeError("render: true needs Playwright (pip install playwright)") from exc
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(user_agent=USER_AGENT)
            page.goto(url, wait_until="networkidle", timeout=int(self.timeout * 1000))
            html = page.content()
            browser.close()
        return html


def find_matching_links(html: str, base_url: str, pattern: str) -> list[str]:
    """PDF links on a page whose URL or link text matches ``pattern``.

    Links whose text/URL match are ranked first; plain PDF links are kept as a fallback
    only when nothing matches.
    """
    regex = re.compile(pattern, re.IGNORECASE)
    soup = BeautifulSoup(html, "html.parser")
    matched, other = [], []
    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a["href"])
        text = " ".join(a.get_text(" ").split())
        is_pdf = ".pdf" in href.lower() or "pdf" in text.lower()
        if regex.search(href) or regex.search(text):
            if is_pdf or regex.search(text):
                matched.append(href)
        elif is_pdf:
            other.append(href)
    seen: set[str] = set()
    return [u for u in matched or other if not (u in seen or seen.add(u))]


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "fund"
