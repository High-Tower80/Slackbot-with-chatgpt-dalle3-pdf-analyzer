"""Notion Company Wiki index and Slack /wiki search helpers."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlparse, urlunparse
import os
import re
import threading

import requests


NOTION_VERSION = "2025-09-03"
NOTION_API_BASE = "https://api.notion.com/v1"
DEFAULT_WIKI_BASE_URL = "https://wiki.example.com"
DEFAULT_DATA_SOURCE_ID = ""
DEFAULT_TOOLKIT_DATA_SOURCE_ID = ""
DEFAULT_DATABASE_ID = ""
DEFAULT_SEARCH_LIMIT = 8
DIGESTIBLE_MAX_CHARS = 1200
PREVIEW_TEASER_CHARS = 220
PAGE_ID_RE = re.compile(r"[0-9a-fA-F]{32}")
SLUG_STRIP_RE = re.compile(r"[^A-Za-z0-9]+")
HINT_LINE_RE = re.compile(r"triple click|click to highlight|click here to", re.I)
SKIP_BLOCK_TYPES = {
    "unsupported",
    "divider",
    "column_list",
    "column",
    "child_database",
    "child_page",
    "image",
    "video",
    "file",
    "pdf",
    "embed",
    "bookmark",
    "table_of_contents",
    "breadcrumb",
    "link_preview",
}


@dataclass
class WikiPage:
    """One indexed Company Wiki page."""

    page_id: str
    title: str
    tags: List[str] = field(default_factory=list)
    url: str = ""
    last_edited_time: str = ""
    snippet: str = ""
    description: str = ""

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
    """Match public wiki slugs: keep case, drop punctuation, hyphenate."""
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
    """Build a public wiki page link.

    Prefer a stored Notion URL property only when it points at this same page.
    Otherwise compose `{slug}-{compactId}` so Slack always gets a stable link.
    """
    compact_id = extract_page_id(page_id)
    if stored_url:
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


QUERY_STOPWORDS = {"a", "an", "the", "and", "or", "of", "for", "to", "in", "on", "at"}
QUERY_SYNONYMS = {
    "ai": ("gemini", "chatgpt", "gpt", "notebooklm"),
}

# Optional workplace-specific tag tweaks. Keep empty in the public repo.
SEARCH_TAG_HIDE = {}
SEARCH_TAG_EXTRAS = {}
_WORD_PATTERN_CACHE = {}


def normalize_title_key(title: str) -> str:
    return re.sub(r"\s+", " ", (title or "").strip().lower())


def apply_search_tag_overrides(title: str, tags: List[str]) -> List[str]:
    """Adjust tags used for search when Notion tags are misleading or incomplete."""
    key = normalize_title_key(title)
    hidden = {item.lower() for item in SEARCH_TAG_HIDE.get(key, ())}
    adjusted = [tag for tag in tags if tag.lower() not in hidden]
    seen = {tag.lower() for tag in adjusted}
    for extra in SEARCH_TAG_EXTRAS.get(key, ()):
        if extra.lower() not in seen:
            adjusted.append(extra)
            seen.add(extra.lower())
    return adjusted


def tokenize_query(query: str) -> List[str]:
    tokens = [token.lower() for token in SLUG_STRIP_RE.split(query or "") if token]
    meaningful = [token for token in tokens if token not in QUERY_STOPWORDS]
    return meaningful or tokens


def expand_query_tokens(tokens: List[str]) -> List[str]:
    expanded: List[str] = []
    for token in tokens:
        if token not in expanded:
            expanded.append(token)
        for alias in QUERY_SYNONYMS.get(token, ()):
            if alias not in expanded:
                expanded.append(alias)
    return expanded


def _word_pattern(token: str, prefix: bool = False):
    key = (token, prefix)
    cached = _WORD_PATTERN_CACHE.get(key)
    if cached is not None:
        return cached
    escaped = re.escape(token)
    if prefix:
        pattern = re.compile(rf"(?<![a-z0-9]){escaped}[a-z0-9]+", re.I)
    else:
        pattern = re.compile(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])", re.I)
    _WORD_PATTERN_CACHE[key] = pattern
    return pattern


def contains_word(token: str, text: str) -> bool:
    """True when token appears as its own word, not a substring like ai in Training."""
    if not token or not text:
        return False
    return bool(_word_pattern(token).search(text))


def contains_word_prefix(token: str, text: str) -> bool:
    """Allow phish to match phishing. Skip short tokens so ai does not match air."""
    if not token or not text or len(token) < 4:
        return False
    return bool(_word_pattern(token, prefix=True).search(text))


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
    description = page.get("description") or ""
    last_edited = page.get("last_edited_time") or page.get("last_edited") or ""

    if properties:
        for prop in properties.values():
            if prop.get("type") == "title":
                title = _plain_text_from_rich(prop.get("title")) or title
                break

        tag_prop = properties.get("Tags") or properties.get("tags") or {}
        if tag_prop.get("type") == "multi_select":
            tags = [opt.get("name", "").strip() for opt in tag_prop.get("multi_select") or [] if opt.get("name")]

        desc_prop = properties.get("Description") or properties.get("description") or {}
        if desc_prop.get("type") == "rich_text":
            description = _plain_text_from_rich(desc_prop.get("rich_text")) or description

        url_prop = properties.get("URL") or properties.get("userDefined:URL") or {}
        if url_prop.get("type") == "url":
            stored_url = url_prop.get("url") or stored_url

        edited_prop = properties.get("Last edited time") or {}
        if edited_prop.get("type") == "last_edited_time":
            last_edited = edited_prop.get("last_edited_time") or last_edited

    title = (title or "").strip()
    tags = [tag.strip() for tag in tags if tag and tag.strip()]
    tags = apply_search_tag_overrides(title, tags)
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
        description=(description or "").strip(),
    )


def score_page(page: WikiPage, tokens: List[str]) -> WikiSearchResult:
    """Rank a page for keyword search across title and tags."""
    if not tokens:
        return WikiSearchResult(page=page, score=0)

    title = page.title.lower()
    tags = [tag.lower().strip() for tag in page.tags]
    description = page.description or ""
    phrase = " ".join(tokens)
    search_tokens = expand_query_tokens(tokens)
    matched_on: List[str] = []
    score = 0
    original_hits = 0

    if title == phrase:
        score += 100
        matched_on.append("title")
    elif contains_word(phrase, title) or title.startswith(phrase + " "):
        score += 70
        matched_on.append("title")

    for token in search_tokens:
        token_matched = False
        if contains_word(token, title):
            score += 20
            token_matched = True
            if "title" not in matched_on:
                matched_on.append("title")
        elif contains_word_prefix(token, title):
            score += 12
            token_matched = True
            if "title" not in matched_on:
                matched_on.append("title")
        if token in tags:
            score += 40
            token_matched = True
            if "tag" not in matched_on:
                matched_on.append("tag")
        elif any(contains_word(token, tag) for tag in tags):
            score += 32
            token_matched = True
            if "tag" not in matched_on:
                matched_on.append("tag")
        elif any(contains_word_prefix(token, tag) for tag in tags):
            score += 14
            token_matched = True
            if "tag" not in matched_on:
                matched_on.append("tag")
        if contains_word(token, description):
            score += 16
            token_matched = True
            if "description" not in matched_on:
                matched_on.append("description")
        elif contains_word_prefix(token, description):
            score += 8
            token_matched = True
            if "description" not in matched_on:
                matched_on.append("description")
        if token_matched and token in tokens:
            original_hits += 1

    if score <= 0:
        return WikiSearchResult(page=page, score=0)

    if original_hits == len(tokens):
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


def extract_preview_from_blocks(blocks: Iterable[Dict[str, Any]]) -> str:
    """Turn Notion blocks into a short, Slack-ready page preview."""
    lines: List[str] = []
    numbered = 0
    for block in blocks or []:
        btype = block.get("type", "")
        if btype in SKIP_BLOCK_TYPES:
            continue
        data = block.get(btype) or {}
        if not isinstance(data, dict):
            continue
        raw = _plain_text_from_rich(data.get("rich_text")).strip()
        if not raw or HINT_LINE_RE.search(raw):
            continue
        if btype == "numbered_list_item":
            numbered += 1
            lines.append(f"{numbered}. {raw}")
            continue
        numbered = 0
        if btype == "bulleted_list_item":
            lines.append(f"• {raw}")
        elif btype == "to_do":
            mark = "✓" if data.get("checked") else "•"
            lines.append(f"{mark} {raw}")
        elif btype == "code":
            lines.append(raw)
        else:
            lines.append(raw)
    return "\n".join(lines).strip()


def is_useful_preview(snippet: str) -> bool:
    text = (snippet or "").strip()
    if len(text) < 8:
        return False
    if HINT_LINE_RE.search(text) and len(text) < 40:
        return False
    return True


def clip_preview(snippet: str) -> str:
    text = (snippet or "").strip()
    if len(text) <= DIGESTIBLE_MAX_CHARS:
        return text
    clipped = text[:PREVIEW_TEASER_CHARS].rsplit("\n", 1)[0].rstrip()
    if len(clipped) < 40:
        clipped = text[:PREVIEW_TEASER_CHARS].rstrip()
    return clipped.rstrip(" .;,:") + "…"



def emoji_for_fact_label(label: str) -> str:
    """Slack emoji prefix for wifi and holiday fact lines."""
    key = (label or "").lower()
    if "password" in key:
        return ":key: "
    if "ssid" in key:
        return ":signal_strength: "
    if "lunar" in key:
        return ":lantern: "
    if "new year" in key:
        return ":tada: "
    if "luther" in key or "king day" in key or key.startswith("mlk"):
        return ":star: "
    if "president" in key or "memorial" in key:
        return ":us: "
    if "juneteenth" in key:
        return ":sparkles: "
    if "july" in key or "4th" in key:
        return ":fireworks: "
    if "labor" in key:
        return ":hammer_and_wrench: "
    if "thanksgiving" in key:
        return ":turkey: "
    if "christmas" in key:
        return ":christmas_tree: "
    if "holiday" in key:
        return ":calendar: "
    return ""



def format_wifi_fact_line(label: str, value: str) -> Optional[str]:
    """Optional custom wifi line. Public repo keeps this generic."""
    return None


def format_preview_for_slack(snippet: str) -> str:
    """Format short wiki facts for Slack, pill-quoting compact values."""
    text = clip_preview(snippet)
    if not text:
        return ""
    formatted: List[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if "company holiday" in line.lower():
            formatted.append(f":calendar: *{escape_slack_text(line)}*")
            continue
        if line.endswith("…") and ": " not in line:
            formatted.append(escape_slack_text(line))
            continue
        if ": " in line and not line.lower().startswith("http"):
            label, value = line.split(": ", 1)
            label = re.sub(r"^\d+\.\s*", "", label.lstrip("• ")).strip()
            value = value.strip()
            if 0 < len(label) <= 48 and 0 < len(value) <= 80:
                wifi_line = format_wifi_fact_line(label, value)
                if wifi_line:
                    formatted.append(wifi_line)
                    continue
                if " " not in value or len(value) <= 28:
                    value_fmt = f"`{escape_slack_text(value)}`"
                else:
                    value_fmt = escape_slack_text(value)
                emoji = emoji_for_fact_label(label)
                formatted.append(f"{emoji}*{escape_slack_text(label)}:* {value_fmt}")
                continue
        formatted.append(escape_slack_text(line))
    return "\n".join(formatted)


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
        title_emoji = ""
        if is_wifi_page(page):
            title_emoji = ":signal_strength: "
        elif is_holidays_page(page):
            title_emoji = ":calendar: "
        body = f"{title_emoji}*{format_slack_link(page.title, page.url)}*\nMatched on {matched}"
        if tag_line:
            body += f"\n{tag_line}"
        preview_source = page.snippet
        if page.description and not is_wifi_page(page) and not is_holidays_page(page):
            preview_source = page.description
        preview = format_preview_for_slack(preview_source) if is_useful_preview(preview_source) else ""
        if preview:
            body += f"\n\n{preview}"

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
                    "*Search the company wiki*\n"
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
        if is_useful_preview(result.page.snippet):
            preview = clip_preview(result.page.snippet)
            first = preview.splitlines()[0]
            lines.append(f"  {first}")
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

    def list_block_children(self, block_id: str, page_size: int = 30) -> List[Dict[str, Any]]:
        if not block_id:
            return []
        payload = self.request("GET", f"blocks/{block_id}/children?page_size={page_size}")
        return payload.get("results") or []


class WikiIndex:
    """In-memory Notion wiki index used by /wiki search."""

    def __init__(
        self,
        token: Optional[str] = None,
        data_source_id: str = DEFAULT_DATA_SOURCE_ID,
        data_source_ids: Optional[List[str]] = None,
        database_id: str = DEFAULT_DATABASE_ID,
        base_url: str = DEFAULT_WIKI_BASE_URL,
        client: Optional[NotionWikiClient] = None,
    ):
        self.token = token or ""
        self.data_source_id = data_source_id
        extra_ids = [item.strip() for item in (data_source_ids or []) if item and item.strip()]
        merged = [data_source_id] + extra_ids if data_source_id else extra_ids
        seen_ids = []
        for item in merged:
            if item and item not in seen_ids:
                seen_ids.append(item)
        self.data_source_ids = seen_ids
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
            source_ids = list(self.data_source_ids)
            if not source_ids and self.database_id:
                resolved = self.client.resolve_data_source_id(self.database_id)
                self.data_source_id = resolved
                source_ids = [resolved]
                self.data_source_ids = source_ids
            raw_pages: List[Dict[str, Any]] = []
            seen_page_ids = set()
            for source_id in source_ids:
                for raw in self.client.query_data_source(source_id):
                    page_id = raw.get("id")
                    if page_id and page_id in seen_page_ids:
                        continue
                    if page_id:
                        seen_page_ids.add(page_id)
                    raw_pages.append(raw)
            raw_pages = self._attach_snippets(raw_pages)
            return self.load_pages(raw_pages)
        except Exception as exc:
            self.last_error = str(exc)
            raise

    def _attach_snippets(self, raw_pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not raw_pages or not self.client:
            return list(raw_pages)

        def _one(raw: Dict[str, Any]) -> Dict[str, Any]:
            page = dict(raw)
            if page.get("snippet"):
                return page
            try:
                blocks = self.client.list_block_children(page.get("id") or "")
                snippet = extract_preview_from_blocks(blocks)
                holiday = holiday_facts_from_child_databases(self.client, blocks)
                if holiday:
                    snippet = holiday if not snippet else f"{snippet}\n{holiday}"
                page["snippet"] = snippet
            except Exception:
                page.setdefault("snippet", "")
            return page

        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=5) as pool:
            return list(pool.map(_one, raw_pages))

    def search(self, query: str, limit: int = DEFAULT_SEARCH_LIMIT) -> List[WikiSearchResult]:
        with self._lock:
            pages = list(self.pages)
        return search_pages(pages, query, limit=limit)



WIFI_SLACK_TAGS = {"wifi", "internet", "ssid"}
WIFI_SLACK_QUERY_TOKENS = {
    "wifi", "internet", "ssid", "password", "guest",
}
HOLIDAY_SLACK_TAGS = {"holidays", "holiday"}
HOLIDAY_SLACK_QUERY_TOKENS = {
    "holiday", "holidays", "thanksgiving", "christmas", "juneteenth",
    "memorial", "labor", "lunar", "president", "mlk", "july", "4th",
    "newyear", "newyears",
}



def format_holiday_date(start: str, end: Optional[str] = None) -> str:
    def parse(value: str) -> datetime:
        return datetime.strptime(value[:10], "%Y-%m-%d")

    begin = parse(start)
    label = f"{begin.strftime('%b')} {begin.day}, {begin.year}"
    if not end:
        return label
    finish = parse(end)
    if begin.year == finish.year and begin.month == finish.month:
        return f"{begin.strftime('%b')} {begin.day}-{finish.day}, {begin.year}"
    if begin.year == finish.year:
        return f"{begin.strftime('%b')} {begin.day} - {finish.strftime('%b')} {finish.day}, {begin.year}"
    return f"{label} - {finish.strftime('%b')} {finish.day}, {finish.year}"


def holiday_facts_from_pages(raw_pages: Iterable[Dict[str, Any]]) -> str:
    items = []
    for raw in raw_pages or []:
        title = ""
        start = None
        end = None
        for prop in (raw.get("properties") or {}).values():
            ptype = prop.get("type")
            if ptype == "title":
                title = _plain_text_from_rich(prop.get("title")).strip()
            elif ptype == "date" and prop.get("date"):
                start = prop["date"].get("start")
                end = prop["date"].get("end")
        if raw.get("title") and not title:
            title = str(raw.get("title") or "").strip()
        if raw.get("start") and not start:
            start = raw.get("start")
            end = raw.get("end")
        if title and start:
            items.append((start, end, title))
    items.sort(key=lambda item: item[0])
    if not items:
        return ""
    year = items[0][0][:4]
    lines = [f"{year} company holidays"]
    for start, end, title in items:
        lines.append(f"{title}: {format_holiday_date(start, end)}")
    return "\n".join(lines)


def holiday_facts_from_child_databases(client: Optional["NotionWikiClient"], blocks: Iterable[Dict[str, Any]]) -> str:
    if not client:
        return ""
    for block in blocks or []:
        if block.get("type") != "child_database":
            continue
        try:
            data_source_id = client.resolve_data_source_id(block.get("id") or "")
            rows = client.query_data_source(data_source_id)
            facts = holiday_facts_from_pages(rows)
            if facts:
                return facts
        except Exception:
            continue
    return ""


def slack_only_holiday_facts() -> str:
    text = (os.getenv("WIKI_SLACK_HOLIDAYS_TEXT") or "").strip()
    return text.replace("\\n", "\n") if text else ""


def is_holidays_page(page: WikiPage) -> bool:
    title = (page.title or "").lower()
    tags = {tag.lower() for tag in page.tags}
    return title.strip() == "holidays" or "holidays" in tags or bool(tags & HOLIDAY_SLACK_TAGS)


def query_wants_holidays(query: str) -> bool:
    tokens = set(tokenize_query(query))
    joined = "".join(tokens)
    if "newyear" in joined or "newyears" in joined:
        return True
    return bool(tokens & HOLIDAY_SLACK_QUERY_TOKENS)


def slack_only_wifi_facts() -> str:
    """Return Slack-only wifi logins from env. Never read these from Notion."""
    text = (os.getenv("WIKI_SLACK_WIFI_TEXT") or "").strip()
    if text:
        return text.replace("\\n", "\n")
    lines = []
    pairs = (
        ("SSID", os.getenv("WIKI_SLACK_WIFI_SSID", "")),
        ("Password", os.getenv("WIKI_SLACK_WIFI_PASSWORD", "")),
        ("5G SSID", os.getenv("WIKI_SLACK_WIFI_SSID_5G", "")),
        ("5G Password", os.getenv("WIKI_SLACK_WIFI_PASSWORD_5G", "")),
    )
    for label, value in pairs:
        value = (value or "").strip()
        if value:
            lines.append(f"{label}: {value}")
    return "\n".join(lines)


def is_wifi_page(page: WikiPage) -> bool:
    title = (page.title or "").lower()
    tags = {tag.lower() for tag in page.tags}
    return "wifi" in title or bool(tags & WIFI_SLACK_TAGS)


def query_wants_wifi(query: str) -> bool:
    return bool(set(tokenize_query(query)) & WIFI_SLACK_QUERY_TOKENS)


def apply_slack_only_facts(results: List[WikiSearchResult], query: str = "") -> None:
    """Overlay Slack-only facts onto matching pages. Leaves Notion index unchanged."""
    wifi = slack_only_wifi_facts()
    holidays = slack_only_holiday_facts()
    for result in results:
        if wifi and is_wifi_page(result.page):
            result.page.snippet = wifi
        if holidays and is_holidays_page(result.page):
            result.page.snippet = holidays


def build_command_response(index: WikiIndex, query: str) -> Dict[str, Any]:
    """Payload for Slack slash-command respond()."""
    cleaned = (query or "").strip()
    if not cleaned:
        return {
            "text": "Search the company wiki with /wiki <keyword>.",
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
    if query_wants_wifi(cleaned) and slack_only_wifi_facts():
        if not any(is_wifi_page(result.page) for result in results):
            for page in index.pages:
                if is_wifi_page(page):
                    results = [WikiSearchResult(page=page, score=50, matched_on=["wifi"])] + list(results)
                    break
    if query_wants_holidays(cleaned):
        if not any(is_holidays_page(result.page) for result in results):
            for page in index.pages:
                if is_holidays_page(page):
                    results = [WikiSearchResult(page=page, score=50, matched_on=["holidays"])] + list(results)
                    break
    apply_slack_only_facts(results, cleaned)
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
