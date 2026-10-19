"""Download MDD / fact sheet PDFs from fund manager websites."""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
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
        self._browser: Browser | None = None
        self._sanlam: dict | None = None
        self._mandg: dict | None = None

    # -- public API ---------------------------------------------------------

    def fetch(self, source: FundSource) -> Path:
        """Return a local path to the PDF for ``source``, downloading it if needed."""
        if source.ignore_robots and self.respect_robots:
            self.respect_robots = False
            try:
                return self.fetch(source)
            finally:
                self.respect_robots = True
        if source.file:
            path = Path(source.file)
            if not path.exists():
                raise ScrapeError(f"local file not found: {path}")
            return path
        headers = {"Referer": source.referer} if source.referer else None
        if source.sanlam_fund:
            url = self.sanlam_mdd_url(source.sanlam_fund)
            return self.download(url, source.name, {"Referer": "https://www.sanlaminvestments.com/"})
        if source.mandg_fund:
            return self.download(self.mandg_mdd_url(source.mandg_fund), source.name, headers)
        if source.url:
            return self.download(source.url, source.name, headers, source.browser, source.page)
        if source.page:
            pdf_url = self.find_pdf_link(source.page, source.link_match, source.render)
            return self.download(pdf_url, source.name, headers, source.browser, source.page)
        raise ScrapeError(f"{source.name}: nothing to fetch")

    def find_pdf_link(self, page_url: str, pattern: str, render: bool = False) -> str:
        html = self._render(page_url) if render else self._get(page_url).text
        # A fund-specific pattern must match: falling back to "any PDF on the page" picked up another
        # fund's MDD when this month's wasn't posted yet. Only the generic default pattern may fall back.
        links = find_matching_links(html, page_url, pattern, fallback=pattern == FundSource.link_match)
        if not links:
            raise ScrapeError(f"no PDF link matching /{pattern}/ found on {page_url}")
        log.info("found %d candidate link(s) on %s, using %s", len(links), page_url, links[0])
        return links[0]

    def download(self, url: str, name: str, headers: dict | None = None, browser: bool = False,
                 page: str | None = None) -> Path:
        """Download a PDF; falls back to the headless browser when the site refuses plain requests."""
        content = b""
        if not browser:
            try:
                content = self._get(url, headers).content
            except ScrapeError as exc:
                if "HTTP 403" not in str(exc) and "HTTP 401" not in str(exc):
                    raise
                log.info("%s refused a plain request, retrying in a browser", url)
        if not as_pdf(content):
            if not self._allowed(url):
                raise ScrapeError(f"robots.txt disallows {url}")
            content = self.browser.fetch(url, page)
        content = as_pdf(content)
        if not content:
            raise ScrapeError(f"{url} did not return a PDF")
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

    def _get(self, url: str, headers: dict | None = None) -> requests.Response:
        if not self._allowed(url):
            raise ScrapeError(f"robots.txt disallows {url} (use --ignore-robots only if you have permission)")
        wait = self.delay - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        for attempt in range(3):  # sites occasionally drop connections - retry before giving up
            try:
                resp = self.session.get(url, timeout=self.timeout, headers=headers)
                break
            except requests.RequestException as exc:
                if attempt == 2:
                    raise ScrapeError(f"request failed for {url}: {exc}") from exc
                time.sleep(3 * (attempt + 1))
            finally:
                self._last_request = time.monotonic()
        if not resp.ok:
            raise ScrapeError(f"HTTP {resp.status_code} for {url}")
        return resp

    def _render(self, url: str) -> str:
        return self.browser.html(url)

    @property
    def browser(self) -> "Browser":
        if self._browser is None:
            self._browser = Browser(self.timeout)
        return self._browser

    def close(self) -> None:
        if self._browser is not None:
            self._browser.close()
            self._browser = None

    def sanlam_mdd_url(self, fund_name: str) -> str:
        """MDD link for a Sanlam Collective Investments fund, from the API behind sanlaminvestments.com."""
        if self._sanlam is None:
            body = self.browser.capture("https://www.sanlaminvestments.com/fund-fact-sheets/", "funds/factsheets")
            self._sanlam = {f["fund_name"].lower(): f for f in json.loads(body)["data"]}
        fund = self._sanlam.get(fund_name.lower())
        if not fund or not fund.get("mdd_urls"):
            raise ScrapeError(f"'{fund_name}' is not in Sanlam's fund fact sheet list")
        urls = fund["mdd_urls"]
        return next((u["url"] for u in urls if u.get("product_code") == "UT"), urls[0]["url"])

    def mandg_mdd_url(self, fund_name: str) -> str:
        """Current fact sheet (MDD) link for an M&G fund, from the fund list embedded in mandg.co.za."""
        if self._mandg is None:
            self._mandg = mandg_fact_sheets(self._get(MANDG_FUNDS_PAGE).text)
        url = self._mandg.get(fund_name.lower())
        if not url:
            raise ScrapeError(f"'{fund_name}' is not in M&G's fund list ({MANDG_FUNDS_PAGE})")
        return url


MANDG_FUNDS_PAGE = "https://www.mandg.co.za/all-funds?type=funds"


def mandg_fact_sheets(html: str) -> dict[str, str]:
    """{lower-case fund name: fact sheet URL} from the JSON M&G's all-funds page embeds."""
    text = html.replace('\\"', '"').replace("\\u0026", "&")
    sheets = {}
    for m in re.finditer(r'"name":"([^"]+)","fundId":"[^"]*".*?"files":\[(.*?)\]', text):
        sheet = re.search(r'"fileType":"FactSheet","path":"([^"]+)"', m.group(2))
        if sheet:
            sheets.setdefault(m.group(1).lower(), sheet.group(1))
    return sheets


class Browser:
    """Headless Chromium for sites that need JavaScript or block plain HTTP clients.

    Uses PLAYWRIGHT_CHROMIUM (path to a Chromium binary) if set, and the HTTPS_PROXY
    environment variable if present.
    """

    def __init__(self, timeout: float = 30.0):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise ScrapeError("this source needs Playwright: pip install playwright && "
                              "python -m playwright install chromium") from exc
        self.timeout_ms = int(timeout * 2000)
        self._pw = sync_playwright().start()
        kwargs = {}
        if os.environ.get("PLAYWRIGHT_CHROMIUM"):
            kwargs["executable_path"] = os.environ["PLAYWRIGHT_CHROMIUM"]
        if os.environ.get("HTTPS_PROXY"):
            kwargs["proxy"] = {"server": os.environ["HTTPS_PROXY"]}
        self._browser = self._pw.chromium.launch(**kwargs)
        self._ctx = self._browser.new_context(user_agent=USER_AGENT.replace(" FundAllocator/0.1", ""),
                                              ignore_https_errors=True)
        self._page = self._ctx.new_page()

    def _goto(self, url: str, settle_ms: int = 4000) -> None:
        self._page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)
        self._page.wait_for_timeout(settle_ms)

    def html(self, url: str) -> str:
        self._goto(url)
        return self._page.content()

    def fetch(self, url: str, referer_page: str | None = None) -> bytes:
        """Download ``url`` from inside a page of the same site, so its cookies/challenge apply."""
        origin = referer_page or "{0.scheme}://{0.netloc}/".format(urlparse(url))
        if not self._page.url.startswith(origin.rstrip("/")):
            self._goto(origin)
        data = self._fetch_in_page(url)
        if data.startswith("ERR"):  # bot checks sometimes need a second page load
            self._goto(origin, settle_ms=8000)
            data = self._fetch_in_page(url)
        if data.startswith("ERR"):
            raise ScrapeError(f"HTTP {data[3:]} for {url} (browser)")
        return base64.b64decode(data)

    def _fetch_in_page(self, url: str) -> str:
        return self._page.evaluate("""async (u) => {
            const r = await fetch(u, {credentials: 'include'});
            if (!r.ok) return 'ERR' + r.status;
            const b = new Uint8Array(await r.arrayBuffer()); let s = '';
            for (let i = 0; i < b.length; i += 0x8000) s += String.fromCharCode(...b.subarray(i, i + 0x8000));
            return btoa(s);
        }""", url)

    def capture(self, page_url: str, url_part: str) -> bytes:
        """Load ``page_url`` and return the body of the first response whose URL contains ``url_part``."""
        with self._page.expect_response(lambda r: url_part in r.url and r.status == 200,
                                        timeout=self.timeout_ms) as info:
            self._page.goto(page_url, wait_until="domcontentloaded", timeout=self.timeout_ms)
        return info.value.body()

    def close(self) -> None:
        self._browser.close()
        self._pw.stop()


def as_pdf(content: bytes) -> bytes:
    """The PDF in a response, or b"" if it isn't one. A 200 is not a PDF: content systems answer a
    missing file with an HTML page and status 200. Some old files wrap the PDF so "%PDF-" starts a
    few hundred bytes in; it is cut from there."""
    at = content[:1024].find(b"%PDF-")
    if len(content) < 1024 or at < 0:
        return b""
    return content[at:]


def find_matching_links(html: str, base_url: str, pattern: str, fallback: bool = True) -> list[str]:
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
    return [u for u in (matched or (other if fallback else [])) if not (u in seen or seen.add(u))]


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "fund"
