"""Configuration and constants."""
import os, sys

# Project root for imports
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Load .env
_ENV_PATH = os.path.join(_PROJECT_ROOT, ".env")
if os.path.exists(_ENV_PATH):
    with open(_ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ.setdefault(key, val)

DB_PATH = os.path.join(_PROJECT_ROOT, "sessions.db")
API_KEY = os.environ.get("MANAGED_AGENTS_API_KEY", "")
API_URL = os.environ.get("MANAGED_AGENTS_API_URL", "https://opencode.ai/zen/go/v1/chat/completions")
MODEL = os.environ.get("MANAGED_AGENTS_MODEL", "kimi-k2.6")

MODEL_FALLBACKS = {
    "kimi-k2.6": "kimi-k2.5",
    "kimi-k2.5": "deepseek-v4-flash",
    "deepseek-v4-flash": "deepseek-v4-pro",
}

MAX_TURNS = 20
MAX_HISTORY_EVENTS = 10
MAX_TOOL_RESULT_CHARS = 400
MAX_THOUGHT_CHARS = 80
MAX_READ_FILE_BYTES = 8000

_SYSTEM_PROMPT_CORE = """You are a planner. Use available tools to complete tasks.

Available tools:
- bash: {"cmd":"...","workdir":"/tmp"} — Runs on host directly.
- read_file: {"path":"/absolute/path"}
- write_file: {"path":"/absolute/path","content":"..."}
- complete: {"summary":"..."}
- ask_user: {"question":"..."}
- web_search: {"query":"...","max_results":5}
- search_files: {"path":"/dir","pattern":"*.py"}

Rules:
1. Think concisely. Never repeat past results.
2. Trust read_file output. Do NOT verify with bash.
3. bash runs directly on host. Use with care.
4. For code/files, ALWAYS use read_file/search_files. NEVER bash.
5. read_file uses key "path" (NOT "file_path").
6. write_file uses key "path" (NOT "file_path").
7. Use absolute paths starting with /root/ or /tmp/ for read_file/search_files."""



def get_system_prompt() -> str:
    return _SYSTEM_PROMPT_CORE
