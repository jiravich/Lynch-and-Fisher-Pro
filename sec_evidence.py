"""Utilities for extracting reviewable evidence candidates from SEC filing HTML."""

from __future__ import annotations

import re
from html.parser import HTMLParser

import requests
import streamlit as st


class _TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            text = data.strip()
            if text:
                self.parts.append(text)


def html_to_text(html: str) -> str:
    parser = _TextParser()
    parser.feed(html)
    parser.close()
    return re.sub(r"\s+", " ", " ".join(parser.parts)).strip()


def _sentences(text: str) -> list[str]:
    cleaned = re.sub(r"\s+", " ", text).strip()
    chunks = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", cleaned)
    return [chunk.strip() for chunk in chunks if len(chunk.strip()) >= 40]


def _clip(text: str, max_chars: int = 500) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= max_chars:
        return text
    clipped = text[: max_chars - 1].rsplit(" ", 1)[0]
    return clipped + "…"


def _keyword_candidates(
    sentences: list[str],
    keywords: tuple[str, ...],
    limit: int,
) -> list[str]:
    results: list[str] = []
    seen: set[str] = set()
    for sentence in sentences:
        low = sentence.lower()
        if any(keyword.lower() in low for keyword in keywords):
            clipped = _clip(sentence)
            key = re.sub(r"\W+", "", clipped.lower())
            if key and key not in seen:
                results.append(clipped)
                seen.add(key)
        if len(results) >= limit:
            break
    return results


def build_evidence_candidates(text: str, limit_per_topic: int = 2) -> list[dict]:
    """Create short, reviewable candidate excerpts; never invents text."""
    sentences = _sentences(text)
    groups = [
        (
            "Lynch",
            "Business / story type",
            ("business", "products", "services", "customers", "strategy"),
        ),
        (
            "Lynch",
            "Sales growth",
            ("revenue growth", "revenue increased", "net sales", "sales increased"),
        ),
        (
            "Lynch",
            "What could break the story?",
            ("risk", "competition", "uncertain", "volatility", "regulatory"),
        ),
        (
            "Fisher",
            "Market potential / sales runway",
            ("market opportunity", "market size", "demand", "addressable market"),
        ),
        (
            "Fisher",
            "Competitive position",
            ("competition", "competitive", "market share", "differentiation"),
        ),
        (
            "Fisher",
            "R&D / product pipeline",
            ("research and development", "research & development", "r&d", "product development"),
        ),
        (
            "Fisher",
            "Profit margins / economics",
            ("gross margin", "operating margin", "profit margin", "cost of revenue"),
        ),
        (
            "Fisher",
            "Management / capital allocation",
            ("capital allocation", "share repurchase", "dividend", "acquisition", "management"),
        ),
        (
            "Fisher",
            "Financial position",
            ("liquidity", "cash and cash equivalents", "indebtedness", "debt", "cash flow"),
        ),
        (
            "General",
            "Accounting / footnotes",
            ("accounting policies", "accounting policy", "significant accounting", "note "),
        ),
        (
            "General",
            "Regulatory / legal",
            ("legal proceedings", "regulatory", "government regulation", "litigation"),
        ),
    ]

    candidates: list[dict] = []
    for framework, topic, keywords in groups:
        for excerpt in _keyword_candidates(sentences, keywords, limit_per_topic):
            candidates.append(
                {
                    "framework": framework,
                    "topic": topic,
                    "statement": excerpt,
                    "fact_or_inference": "Fact",
                    "polarity": "Neutral",
                }
            )
    return candidates


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_filing_text(url: str, user_agent: str) -> str:
    headers = {
        "User-Agent": user_agent,
        "Accept-Encoding": "gzip, deflate",
    }
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    return html_to_text(response.text)


def extract_filing_candidates(
    filing_url: str,
    user_agent: str,
    limit_per_topic: int = 2,
) -> list[dict]:
    text = fetch_filing_text(filing_url, user_agent)
    return build_evidence_candidates(text, limit_per_topic=limit_per_topic)
