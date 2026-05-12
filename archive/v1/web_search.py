#!/usr/bin/env python3
"""Web search via DuckDuckGo (no API key required)."""
import json, sys

def search(query: str, max_results: int = 5):
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

if __name__ == "__main__":
    query = sys.argv[1] if len(sys.argv) > 1 else "Python programming"
    print(json.dumps(search(query), ensure_ascii=False, indent=2))
