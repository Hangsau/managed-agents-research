#!/usr/bin/env python3
"""
Skill activation workflow.
Reviews drafted skills, lets user approve/reject, then creates real skills.
"""
import json, os, sys, re
from datetime import datetime

DRAFTS_DIR = "/root/managed-agents/internal/skills-drafts"
APPROVED_DIR = "/root/managed-agents/internal/skills-approved"
REJECTED_DIR = "/root/managed-agents/internal/skills-rejected"

os.makedirs(APPROVED_DIR, exist_ok=True)
os.makedirs(REJECTED_DIR, exist_ok=True)


def list_drafts():
    drafts = []
    for fname in sorted(os.listdir(DRAFTS_DIR)):
        if fname.endswith(".md"):
            path = os.path.join(DRAFTS_DIR, fname)
            with open(path) as f:
                content = f.read()
            # Extract name from frontmatter
            name_match = re.search(r"^name:\s*(\S+)", content, re.MULTILINE)
            name = name_match.group(1) if name_match else fname[:-3]
            drafts.append({
                "file": fname,
                "name": name,
                "path": path,
                "preview": content[:500] + "..." if len(content) > 500 else content,
            })
    return drafts


def approve(draft_file):
    """Move draft to approved, return instructions for activation."""
    src = os.path.join(DRAFTS_DIR, draft_file)
    dst = os.path.join(APPROVED_DIR, draft_file)
    os.rename(src, dst)
    
    # Read to get the name
    with open(dst) as f:
        content = f.read()
    name_match = re.search(r"^name:\s*(\S+)", content, re.MULTILINE)
    name = name_match.group(1) if name_match else draft_file[:-3]
    
    return {
        "status": "approved",
        "name": name,
        "path": dst,
        "next_step": f"Use `skill_manage(action='create', name='{name}', content=...) to activate",
    }


def reject(draft_file, reason=""):
    src = os.path.join(DRAFTS_DIR, draft_file)
    dst = os.path.join(REJECTED_DIR, draft_file)
    os.rename(src, dst)
    
    # Log reason
    log_path = os.path.join(REJECTED_DIR, f"{draft_file}.reason")
    with open(log_path, "w") as f:
        f.write(f"{datetime.now().isoformat()}: {reason or 'No reason given'}")
    
    return {"status": "rejected", "reason": reason}


def auto_review():
    """Auto-review: approve high-confidence drafts, flag low-confidence ones."""
    results = []
    for draft in list_drafts():
        with open(draft["path"]) as f:
            content = f.read()
        
        # Check if README was successfully fetched
        has_todo = "TODO" in content
        has_error = "[ERROR" in content
        score_match = re.search(r"Discovery score:\s*(\d+)/(\d+)", content)
        score = int(score_match.group(1)) if score_match else 0
        max_score = int(score_match.group(2)) if score_match else 7
        
        if has_error:
            results.append({
                "draft": draft["file"],
                "action": "flag",
                "reason": "README fetch failed, needs manual review",
            })
        elif score >= 6 and not has_todo:
            # Almost complete, approve
            result = approve(draft["file"])
            results.append({
                "draft": draft["file"],
                "action": "approved",
                "name": result["name"],
            })
        elif score >= 5:
            results.append({
                "draft": draft["file"],
                "action": "needs_review",
                "reason": f"Score {score}/{max_score}, has TODOs",
            })
        else:
            result = reject(draft["file"], f"Score too low: {score}/{max_score}")
            results.append({
                "draft": draft["file"],
                "action": "rejected",
                "reason": result["reason"],
            })
    
    return results


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python activate_skill.py list              # List all pending drafts")
        print("  python activate_skill.py auto              # Auto-review all drafts")
        print("  python activate_skill.py approve <file>    # Approve a draft")
        print("  python activate_skill.py reject <file>     # Reject a draft")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "list":
        drafts = list_drafts()
        if not drafts:
            print("No pending drafts.")
            return
        print(f"\nPending drafts ({len(drafts)}):")
        for d in drafts:
            print(f"  • {d['file']} (name: {d['name']})")
    
    elif cmd == "auto":
        results = auto_review()
        print("\nAuto-review results:")
        for r in results:
            print(f"  {r['draft']}: {r['action']}")
            if "reason" in r:
                print(f"    Reason: {r['reason']}")
    
    elif cmd == "approve":
        if len(sys.argv) < 3:
            print("Usage: python activate_skill.py approve <filename.md>")
            sys.exit(1)
        result = approve(sys.argv[2])
        print(f"\n✅ Approved: {result['name']}")
        print(f"   Path: {result['path']}")
        print(f"   {result['next_step']}")
    
    elif cmd == "reject":
        if len(sys.argv) < 3:
            print("Usage: python activate_skill.py reject <filename.md>")
            sys.exit(1)
        result = reject(sys.argv[2])
        print(f"\n❌ Rejected: {result['reason']}")
    
    else:
        print(f"Unknown command: {cmd}")


if __name__ == "__main__":
    main()
