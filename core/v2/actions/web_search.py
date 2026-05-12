"""Search the web via DuckDuckGo."""
import sys, os

def _search(query: str, max_results: int = 5):
    """Search DuckDuckGo and return list of {title, url, snippet}."""
    try:
        from ddgs import DDGS
        with DDGS() as ddgs:
            results = []
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", "")
                })
            return {"results": results, "query": query}
    except Exception as e:
        return {"error": str(e), "query": query}


def run(args: dict, session_id: str) -> dict:
    query = args.get("query", "")
    max_results = args.get("max_results", 5)
    return _search(query, max_results)
