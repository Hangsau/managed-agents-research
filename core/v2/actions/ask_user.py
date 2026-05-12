"""Signal that the agent is waiting for user input."""


def run(args: dict, session_id: str) -> dict:
    return {"status": "waiting", "question": args.get("question", "?")}
