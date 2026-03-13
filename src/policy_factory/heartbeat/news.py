"""Yle.fi news fetcher for heartbeat skim.

Fetches recent headlines from Yle's public RSS feeds and formats them
for the heartbeat skim agent.  This replaces the need for any web search
tool — the agent receives pre-fetched headlines and just needs to
analyse them against the current situational awareness.

Two feeds are combined:
- **Major headlines** — the top editorial picks
- **Recent news** — the full chronological feed (truncated)
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

# Yle RSS feed URLs
_MAJOR_HEADLINES_URL = (
    "https://feeds.yle.fi/uutiset/v1/majorHeadlines/YLE_UUTISET.rss"
)
_RECENT_NEWS_URL = (
    "https://feeds.yle.fi/uutiset/v1/recent.rss?publisherIds=YLE_UUTISET"
)

# How many items to keep from the recent feed (major headlines are all kept)
_MAX_RECENT_ITEMS = 30

# HTTP timeout in seconds
_FETCH_TIMEOUT = 15.0


@dataclass
class NewsItem:
    """A single news headline from the RSS feed."""

    title: str
    link: str
    description: str
    published: str
    categories: list[str]


def _parse_rss(xml_text: str, max_items: int | None = None) -> list[NewsItem]:
    """Parse an RSS 2.0 feed into NewsItem objects.

    Args:
        xml_text: Raw XML string from the RSS feed.
        max_items: Maximum number of items to return (``None`` for all).

    Returns:
        List of parsed news items.
    """
    items: list[NewsItem] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        logger.warning("Failed to parse RSS XML")
        return items

    for item_el in root.iter("item"):
        title = (item_el.findtext("title") or "").strip()
        link = (item_el.findtext("link") or "").strip()
        description = (item_el.findtext("description") or "").strip()
        pub_date = (item_el.findtext("pubDate") or "").strip()
        categories = [
            cat.text.strip()
            for cat in item_el.findall("category")
            if cat.text
        ]

        if title:
            items.append(
                NewsItem(
                    title=title,
                    link=link,
                    description=description,
                    published=pub_date,
                    categories=categories,
                )
            )

        if max_items is not None and len(items) >= max_items:
            break

    return items


async def fetch_yle_news() -> list[NewsItem]:
    """Fetch recent headlines from Yle's RSS feeds.

    Combines major headlines and recent news into a single deduplicated
    list (major headlines first, then recent items not already included).

    Returns:
        List of ``NewsItem`` objects.  Returns an empty list on network
        errors (the heartbeat skim should still run with whatever it gets).
    """
    all_items: list[NewsItem] = []
    seen_links: set[str] = set()

    async with httpx.AsyncClient(timeout=_FETCH_TIMEOUT) as client:
        # Fetch major headlines first (editorial picks)
        try:
            resp = await client.get(_MAJOR_HEADLINES_URL)
            resp.raise_for_status()
            for item in _parse_rss(resp.text):
                if item.link not in seen_links:
                    all_items.append(item)
                    seen_links.add(item.link)
        except Exception:
            logger.warning("Failed to fetch Yle major headlines", exc_info=True)

        # Fetch recent news
        try:
            resp = await client.get(_RECENT_NEWS_URL)
            resp.raise_for_status()
            for item in _parse_rss(resp.text, max_items=_MAX_RECENT_ITEMS):
                if item.link not in seen_links:
                    all_items.append(item)
                    seen_links.add(item.link)
        except Exception:
            logger.warning("Failed to fetch Yle recent news", exc_info=True)

    logger.info("Fetched %d Yle headlines for heartbeat skim", len(all_items))
    return all_items


def format_news_for_prompt(items: list[NewsItem]) -> str:
    """Format news items into a markdown block for the skim prompt.

    Args:
        items: List of news items to format.

    Returns:
        A markdown-formatted string with headlines, or a fallback message
        if no items were fetched.
    """
    if not items:
        return (
            "(Failed to fetch news from Yle. Respond with NOTHING_NOTEWORTHY "
            "since no headlines are available to assess.)"
        )

    lines: list[str] = []
    for i, item in enumerate(items, 1):
        cats = ", ".join(item.categories[:5]) if item.categories else "uncategorised"
        line = f"{i}. **{item.title}**"
        if item.description:
            line += f"\n   {item.description}"
        line += f"\n   Categories: {cats} | {item.published}"
        line += f"\n   {item.link}"
        lines.append(line)

    return "\n\n".join(lines)
