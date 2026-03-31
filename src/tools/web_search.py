"""Web search tool — wraps Tavily or SerpAPI for agent use."""

from __future__ import annotations

import logging

from src.config import settings

logger = logging.getLogger(__name__)


async def search_web(query: str, max_results: int = 5) -> str:
    """Search the web and return concatenated snippet text.

    Supports two providers via settings.search_provider:
      - 'tavily'  → Tavily Search API
      - 'serpapi' → SerpAPI Google Search

    Returns a plain-text summary of search results.
    """
    provider = settings.search_provider.lower()

    if provider == "tavily":
        return await _search_tavily(query, max_results)
    elif provider == "serpapi":
        return await _search_serpapi(query, max_results)
    else:
        logger.warning("Unknown search provider '%s', returning empty.", provider)
        return ""


async def _search_tavily(query: str, max_results: int) -> str:
    try:
        from tavily import AsyncTavilyClient

        client = AsyncTavilyClient(api_key=settings.search_api_key)
        resp = await client.search(query=query, max_results=max_results)

        snippets: list[str] = []
        for result in resp.get("results", []):
            title = result.get("title", "")
            content = result.get("content", "")
            url = result.get("url", "")
            snippets.append(f"[{title}]({url})\n{content}")

        return "\n\n".join(snippets)
    except Exception as e:
        logger.warning("Tavily search failed: %s", e)
        return ""


async def _search_serpapi(query: str, max_results: int) -> str:
    try:
        import httpx

        params = {
            "q": query,
            "api_key": settings.search_api_key,
            "engine": "google",
            "num": max_results,
        }
        async with httpx.AsyncClient() as client:
            resp = await client.get("https://serpapi.com/search", params=params)
            resp.raise_for_status()
            data = resp.json()

        snippets: list[str] = []
        for result in data.get("organic_results", [])[:max_results]:
            title = result.get("title", "")
            snippet = result.get("snippet", "")
            link = result.get("link", "")
            snippets.append(f"[{title}]({link})\n{snippet}")

        return "\n\n".join(snippets)
    except Exception as e:
        logger.warning("SerpAPI search failed: %s", e)
        return ""
