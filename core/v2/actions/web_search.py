"""Search the web via DuckDuckGo."""
import sys, os

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
_CORE_DIR = os.path.join(_PROJECT_ROOT, "core")
if _CORE_DIR not in sys.path:
    sys.path.insert(0, _CORE_DIR)

import web_search


def run(args: dict, session_id: str) -> dict:
    query = args.get("query", "")
    max_results = args.get("max_results", 5)
    try:
        return web_search.search(query, max_results)
    except Exception as e:
        return {"error": str(e)}
