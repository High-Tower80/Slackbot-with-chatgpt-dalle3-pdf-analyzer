"""Notion Company Wiki index and Slack /wiki search helpers."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlparse, urlunparse
import re
import threading

import requests


NOTION_VERSION = "2025-09-03"
NOTION_API_BASE = "https://api.notion.com/v1"
DEFAULT_WIKI_BASE_URL = "https://wiki.intertrendhub.com"
DEFAULT_DATA_SOURCE_ID = "30840c6a-9bad-4534-9b41-3f216c7062da"
DEFAULT_DATABASE_ID = "7dd88efc-5462-43e9-985c-8b401f23a5ad"
DEFAULT_SEARCH_LIMIT = 8
PAGE_ID_RE = re.compile(r"[0-9a-fA-F]{32}")
SLUG_STRIP_RE = re.compile(r"[^A-Za-z0-9]+")


@dataclass
class WikiPage:
    """One indexed Company Wiki page."""

    page_id: str
    title: str
    tags: List[str] = field(default_factory=list)
    url: str = ""
    last_edited_time: str = ""
    snippet: str = ""

    @property
    def compact_id(self) -> str:
        return compact_page_id(self.page_id)


@dataclass
class WikiSearchResult:
    page: WikiPage
    score: int
    matched_on: List[str] = field(default_factory=list)


def compact_page_id(page_id: str) -> str:
    """Return a Notion page id without dashes."""
    return (page_id or "").replace("-", "").lower()


def extract_page_id(value: str) -> str:
    """Pull a 32-char Notion id from a URL, UUID, or raw id."""
    if not value:
        return ""
    compact = compact_page_id(value)
    match = PAGE_ID_RE.search(compact)
    if match:
        return match.group(0).lower()
    match = PAGE_ID_RE.search(value.replace("-", ""))
    return match.group(0).lower() if match else ""


def slugify_title(title: str) -> str:
    """Match Intertrend wiki public slugs: keep case, drop punctuation, hyphenate."""
    if not title:
        return ""
    cleaned = title.replace("–", " ").replace("—", " ").replace("“", " ").replace("”", " ")
    parts = [part for part in SLUG_STRIP_RE.split(cleaned) if part]
    return "-".join(parts)


def clean_wiki_url(url: str) -> str:
    """Drop tracking query params from a public wiki URL."""
    if not url:
        return ""
    parsed = urlparse(url.strip())
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))


def format_public_wiki_url(
    title: str,
    page_id: str,
    stored_url: Optional[str] = None,
    base_url: str = DEFAULT_WIKI_BASE_URL,
) -> str:
    """Build a public wiki.intertrendhub.com link.

    Prefer a stored Notion URL property only when it points at this same page.
    Otherwise compose `{slug}-{compactId}` so Slack always gets a stable link.
    """
    compact_id = extract_page_id(page_id)
    if stored_url and "wiki.intertrendhub.com" in stored_url:
        stored_id = extract_page_id(stored_url)
        if stored_id and stored_id == compact_id:
            return clean_wiki_url(stored_url)

    base = (base_url or DEFAULT_WIKI_BASE_URL).rstrip("/")
    slug = slugify_title(title)
    if slug and compact_id:
        return f"{base}/{slug}-{compact_id}"
    if compact_id:
        return f"{base}/{compact_id}"
    return base


def escape_slack_text(text: str) -> str:
    """Escape characters that break Slack mrkdwn links."""
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def format_slack_link(title: str, url: str) -> str:
    """Return Slack mrkdwn for a titled link."""
    label = escape_slack_text(title or "Wiki page")
    return f"<{url}|{label}>"


def tokenize_query(query: str) -> List[str]:
    tokens = [token.lower() for token in SLUG_STRIP_RE.split(query or "") if token]
    return tokens


def _plain_text_from_rich(rich_text: Iterable[Dict[str, Any]]) -> str:
    return "".join(item.get("plain_text", "") for item in rich_text or [])


def parse_notion_page(
    page: Dict[str, Any],
    base_url: str = DEFAULT_WIKI_BASE_URL,
) -> Optional[WikiPage]:
    """Convert a Notion page object (or a simplified dict) into a WikiPage."""
    if not page:
        return None

    page_id = page.get("id") or page.get("page_id") or extract_page_id(page.get("url", ""))
    if not page_id:
        return None

    properties = page.get("properties") or {}
    title = page.get("title") or ""
    tags = list(page.get("tags") or [])
    stored_url = page.get("stored_url")
    snippet = page.get("snippet") or ""
    last_edited = page.get("last_edited_time") or page.get("last_edited") or ""

    if properties:
        for prop in properties.values():
            if prop.get("type") == "title":
                title = _plain_text_from_rich(prop.get("title")) or title
                break

        tag_prop = properties.get("Tags") or {}
        if tag_prop.get("type") == "multi_select":
            tags = [opt.get("name", "").strip() for opt in tag_prop.get("multi_select") or [] if opt.get("name")]

        url_prop = properties.get("URL") or properties.get("userDefined:URL") or {}
        if url_prop.get("type") == "url":
            stored_url = url_prop.get("url") or stored_url

        edited_prop = properties.get("Last edited time") or {}
        if edited_prop.get("type") == "last_edited_time":
            last_edited = edited_prop.get("last_edited_time") or last_edited

    title = (title or "").strip()
    tags = [tag.strip() for tag in tags if tag and tag.strip()]
    if not title and not tags:
        return None

    display_title = title or "Wiki page"
    url = format_public_wiki_url(display_title, page_id, stored_url=stored_url, base_url=base_url)
    return WikiPage(
        page_id=page_id,
        title=display_title,
        tags=tags,
        url=url,
        last_edited_time=last_edited,
        snippet=snippet,
    )


def score_page(page: WikiPage, tokens: List[str]) -> WikiSearchResult:
    """Rank a page for keyword search across title and tags."""
    if not tokens:
        return WikiSearchResult(page=page, score=0)

    title = page.title.lower()
    tags = [tag.lower().strip() for tag in page.tags]
    snippet = (page.snippet or "").lower()
    phrase = " ".join(tokens)
    matched_on: List[str] = []
    score = 0
    token_hits = 0

    if title == phrase:
        score += 100
        matched_on.append("title")
    elif title.startswith(phrase):
        score += 70
        matched_on.append("title")
    elif phrase in title:
        score += 55
        matched_on.append("title")

    for token in tokens:
        token_matched = False
        if token in title.split() or token in title:
            score += 20
            token_matched = True
            if "title" not in matched_on:
                matched_on.append("title")
        if token in tags:
            score += 40
            token_matched = True
            if "tag" not in matched_on:
                matched_on.append("tag")
        elif any(token in tag for tag in tags):
            score += 18
            token_matched = True
            if "tag" not in matched_on:
                matched_on.append("tag")
        if token and token in snippet:
            score += 8
            token_matched = True
            if "snippet" not in matched_on:
                matched_on.append("snippet")
        if token_matched:
            token_hits += 1

    if token_hits == 0:
        return WikiSearchResult(page=page, score=0)

    if token_hits == len(tokens):
        score += 15

    return WikiSearchResult(page=page, score=score, matched_on=matched_on)


def search_pages(pages: Iterable[WikiPage], query: str, limit: int = DEFAULT_SEARCH_LIMIT) -> List[WikiSearchResult]:
    tokens = tokenize_query(query)
    if not tokens:
        return []

    results = [score_page(page, tokens) for page in pages]
    ranked = [result for result in results if result.score > 0]
    ranked.sort(key=lambda item: (-item.score, item.page.title.lower()))
    return ranked[:limit]


def format_tag_line(tags: List[str], limit: int = 6) -> str:
    if not tags:
        return ""
    shown = tags[:limit]
    rendered = " ".join(f"`{escape_slack_text(tag)}`" for tag in shown)
    extra = len(tags) - len(shown)
    if extra > 0:
        rendered += f" +{extra} more"
    return rendered


def build_search_blocks(query: str, results: List[WikiSearchResult]) -> List[Dict[str, Any]]:
    """Slack Block Kit for /wiki results, with formatted public wiki links."""
    heading = f"Wiki results for “{query}”"
    blocks: List[Dict[str, Any]] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": heading[:150], "emoji": True},
        }
    ]

    if not results:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"No Company Wiki pages matched *{escape_slack_text(query)}*. "
                    "Try a tag like `wifi`, `pto`, `holidays`, or `phishing`."
                ),
            },
        })
        return blocks

    for result in results:
        page = result.page
        tag_line = format_tag_line(page.tags)
        matched = ", ".join(result.matched_on) if result.matched_on else "wiki"
        body = f"*{format_slack_link(page.title, page.url)}*\nMatched on {matched}"
        if tag_line:
            body += f"\n{tag_line}"

        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": body},
            "accessory": {
                "type": "button",
                "text": {"type": "plain_text", "text": "Open", "emoji": True},
                "url": page.url,
                "action_id": f"wiki_open_{page.compact_id}",
            },
        })

    return blocks


def build_help_blocks() -> List[Dict[str, Any]]:
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    "*Search the Intertrend wiki*\n"
                    "Use `/wiki <keyword>` — for example `/wiki wifi`, `/wiki pto`, or `/wiki phishing`.\n"
                    "You can also type `wiki: holidays` in a DM or channel."
                ),
            },
        }
    ]


def fallback_text(query: str, results: List[WikiSearchResult]) -> str:
    if not results:
        return f"No Company Wiki pages matched “{query}”."
    lines = [f"Wiki results for “{query}”:"]
    for result in results:
        lines.append(f"• {format_slack_link(result.page.title, result.page.url)}")
    return "\n".join(lines)


class NotionWikiClient:
    """Thin Notion API client using the 2025-09-03 data source APIs."""

    def __init__(self, token: str, timeout: int = 15):
        self.token = token
        self.timeout = timeout

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        }

    def request(self, method: str, path: str, json_body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{NOTION_API_BASE}/{path.lstrip('/')}"
        response = requests.request(
            method,
            url,
            headers=self._headers(),
            json=json_body,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def resolve_data_source_id(self, database_id: str) -> str:
        payload = self.request("GET", f"databases/{database_id}")
        sources = payload.get("data_sources") or []
        if not sources:
            raise ValueError(f"No data sources found for database {database_id}")
        return sources[0]["id"]

    def query_data_source(self, data_source_id: str) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        cursor = None
        while True:
            body: Dict[str, Any] = {
                "page_size": 100,
                "result_type": "page",
            }
            if cursor:
                body["start_cursor"] = cursor
            payload = self.request("POST", f"data_sources/{data_source_id}/query", body)
            results.extend(payload.get("results") or [])
            if not payload.get("has_more"):
                break
            cursor = payload.get("next_cursor")
            if not cursor:
                break
        return results


class WikiIndex:
    """In-memory Notion wiki index used by /wiki search."""

    def __init__(
        self,
        token: Optional[str] = None,
        data_source_id: str = DEFAULT_DATA_SOURCE_ID,
        database_id: str = DEFAULT_DATABASE_ID,
        base_url: str = DEFAULT_WIKI_BASE_URL,
        client: Optional[NotionWikiClient] = None,
    ):
        self.token = token or ""
        self.data_source_id = data_source_id
        self.database_id = database_id
        self.base_url = base_url
        self.client = client or (NotionWikiClient(self.token) if self.token else None)
        self.pages: List[WikiPage] = []
        self.last_refreshed_at: Optional[datetime] = None
        self.last_error: Optional[str] = None
        self._lock = threading.Lock()

    @property
    def configured(self) -> bool:
        return bool(self.token and self.client)

    def load_pages(self, raw_pages: Iterable[Dict[str, Any]]) -> List[WikiPage]:
        loaded = []
        for raw in raw_pages:
            parsed = parse_notion_page(raw, base_url=self.base_url)
            if parsed:
                loaded.append(parsed)
        with self._lock:
            self.pages = loaded
            self.last_refreshed_at = datetime.now(timezone.utc)
            self.last_error = None
        return loaded

    def refresh(self) -> List[WikiPage]:
        if not self.configured:
            self.last_error = "NOTION_TOKEN is not configured"
            return []
        try:
            data_source_id = self.data_source_id
            if not data_source_id and self.database_id:
                data_source_id = self.client.resolve_data_source_id(self.database_id)
                self.data_source_id = data_source_id
            raw_pages = self.client.query_data_source(data_source_id)
            return self.load_pages(raw_pages)
        except Exception as exc:
            self.last_error = str(exc)
            raise

    def search(self, query: str, limit: int = DEFAULT_SEARCH_LIMIT) -> List[WikiSearchResult]:
        with self._lock:
            pages = list(self.pages)
        return search_pages(pages, query, limit=limit)


def build_command_response(index: WikiIndex, query: str) -> Dict[str, Any]:
    """Payload for Slack slash-command respond()."""
    cleaned = (query or "").strip()
    if not cleaned:
        return {
            "text": "Search the Intertrend wiki with /wiki <keyword>.",
            "blocks": build_help_blocks(),
            "response_type": "ephemeral",
        }

    if not index.configured:
        return {
            "text": "Wiki search is not configured. Add NOTION_TOKEN and share the Company Wiki with the integration.",
            "response_type": "ephemeral",
        }

    if not index.pages and index.last_error:
        return {
            "text": f"Wiki index is empty ({index.last_error}).",
            "response_type": "ephemeral",
        }

    results = index.search(cleaned)
    return {
        "text": fallback_text(cleaned, results),
        "blocks": build_search_blocks(cleaned, results),
        "response_type": "ephemeral",
    }


def start_background_refresh(index: WikiIndex, interval_seconds: int, logger) -> Optional[threading.Thread]:
    """Refresh the wiki index on a timer. Returns the daemon thread if started."""
    if not index.configured or interval_seconds <= 0:
        return None

    def _loop():
        while True:
            threading.Event().wait(interval_seconds)
            try:
                pages = index.refresh()
                logger.info(f"Refreshed Notion wiki index ({len(pages)} pages)")
            except Exception as exc:
                logger.error(f"Wiki index refresh failed: {exc}")

    thread = threading.Thread(target=_loop, name="wiki-index-refresh", daemon=True)
    thread.start()
    return thread
