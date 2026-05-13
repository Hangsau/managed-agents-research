"""Search files by pattern using fnmatch."""
import fnmatch, os


def run(args: dict, session_id: str) -> dict:
    path = args.get("path", "/tmp")
    pattern = args.get("pattern", "")

    try:
        matches = []
        for root, dirs, files in os.walk(path):
            for name in files:
                if fnmatch.fnmatch(name.lower(), pattern.lower()) or fnmatch.fnmatch(name, pattern):
                    matches.append(os.path.join(root, name))
            if len(matches) > 100:
                matches.append("... (truncated at 100)")
                break
        return {"matches": matches[:100], "count": len(matches)}
    except Exception as e:
        return {"error": str(e)}
