"""Action dispatcher: routes action names to their v2 handlers."""
import json
import sys, os

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
_CORE_DIR = os.path.join(_PROJECT_ROOT, "core")
if _CORE_DIR not in sys.path:
    sys.path.insert(0, _CORE_DIR)

from .actions import bash, read_file, write_file, complete, ask_user, web_search, search_files

_ACTIONS = {
    "bash": bash,
    "read_file": read_file,
    "write_file": write_file,
    "complete": complete,
    "ask_user": ask_user,
    "web_search": web_search,
    "search_files": search_files,
}

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "Run a shell command on the host directly.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cmd": {"type": "string", "description": "The shell command to run"},
                    "workdir": {"type": "string", "description": "Working directory"},
                },
                "required": ["cmd"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file from disk.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute file path"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute file path"},
                    "content": {"type": "string", "description": "File content"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "complete",
            "description": "Signal task completion.",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string", "description": "Completion summary"},
                },
                "required": ["summary"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ask_user",
            "description": "Ask the user a question.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "Question to ask"},
                },
                "required": ["question"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web via DuckDuckGo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "max_results": {"type": "integer", "description": "Maximum results"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": "Search files by pattern.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path"},
                    "pattern": {"type": "string", "description": "File pattern"},
                },
                "required": ["path", "pattern"],
            },
        },
    },
]


def run(action: str, args: dict, session_id: str) -> dict:
    mod = _ACTIONS.get(action)
    if mod is None:
        return {"error": "unknown action"}
    return mod.run(args, session_id)


def dispatch(tool_call: dict, session_id: str) -> dict:
    """Dispatch a tool_call object to the appropriate action handler."""
    func = tool_call.get("function", {})
    action = func.get("name")
    try:
        args = json.loads(func.get("arguments", "{}"))
    except json.JSONDecodeError as e:
        return {"error": f"Invalid arguments JSON: {e}"}
    return run(action, args, session_id)
