"""
Tavily Search Tool
Performs real-time web searches using the Tavily Search API.
Provides context enrichment for research tasks in SYNQ.
"""

import logging
import os
from typing import Any, Dict, List, Optional
import httpx
from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class TavilySearchClient:
    """Async client for querying the Tavily Search API."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("TAVILY_API_KEY", "")
        self.base_url = "https://api.tavily.com/search"

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and "PASTE" not in self.api_key)

    async def search(
        self,
        query: str,
        max_results: int = 5,
        search_depth: str = "basic",
        include_answer: bool = True,
    ) -> Dict[str, Any]:
        """
        Execute web search for the given query.
        Returns a dictionary with 'answer' and 'results'.
        """
        if not self.is_configured:
            logger.debug("Tavily API key not configured. Skipping web search.")
            return {"answer": None, "results": []}

        payload = {
            "api_key": self.api_key,
            "query": query,
            "max_results": max_results,
            "search_depth": search_depth,
            "include_answer": include_answer,
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(self.base_url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    logger.info("Tavily search succeeded for query: %s (%d results)", query, len(data.get("results", [])))
                    return {
                        "answer": data.get("answer"),
                        "results": [
                            {
                                "title": r.get("title", ""),
                                "url": r.get("url", ""),
                                "content": r.get("content", ""),
                            }
                            for r in data.get("results", [])
                        ],
                    }
                else:
                    logger.warning("Tavily search failed (HTTP %s): %s", resp.status_code, resp.text)
                    return {"answer": None, "results": []}
        except Exception as exc:
            logger.warning("Tavily search network error: %s", exc)
            return {"answer": None, "results": []}


# Singleton instance
tavily_client = TavilySearchClient()
