#!/usr/bin/env python3
"""
Deep-dive analyzer: fetches repo README + key files, evaluates skill-worthiness.
"""
import json, urllib.request, re, os, sys

SKILLS_QUEUE = "/root/managed-agents/research/skills-queue"
SKILLS_DRAFTS = "/root/managed-agents/research/skills-drafts"
os.makedirs(SKILLS_DRAFTS, exist_ok=True)

def fetch_readme(full_name):
    """Fetch raw README.md from GitHub."""
    url = f"https://raw.githubusercontent.com/{full_name}/main/README.md"
    req = urllib.request.Request(url, headers={"User-Agent": "DeepDive/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read().decode()[:5000]
    except:
        # Try master branch
        url = f"https://raw.githubusercontent.com/{full_name}/master/README.md"
        req = urllib.request.Request(url, headers={"User-Agent": "DeepDive/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.read().decode()[:5000]
        except Exception as e:
            return f"[ERROR fetching README: {e}]"

def evaluate_skill_potential(repo, readme):
    """Score a repo for skill-worthiness based on README content."""
    score = repo.get("skill_score", 0)
    reasons = []
    
    readme_lower = readme.lower()
    
    # Check for actionable content
    if "install" in readme_lower or "setup" in readme_lower or "quick start" in readme_lower:
        score += 1
        reasons.append("has setup instructions")
    
    if "api" in readme_lower or "cli" in readme_lower or "command" in readme_lower:
        score += 1
        reasons.append("has API/CLI interface")
    
    # Check for concrete examples
    code_blocks = len(re.findall(r"```\w+", readme))
    if code_blocks >= 3:
        score += 1
        reasons.append(f"{code_blocks} code examples")
    
    # Check for configuration files
    if any(x in readme_lower for x in ["config", "yaml", "json", "toml"]):
        score += 0.5
        reasons.append("has configuration")
    
    # Penalty for vague marketing
    buzzwords = ["revolutionary", "game-changing", "cutting-edge", "next-gen"]
    buzz_count = sum(1 for b in buzzwords if b in readme_lower)
    if buzz_count > 2:
        score -= 1
        reasons.append("too much marketing fluff")
    
    return {
        "name": repo["name"],
        "url": repo["url"],
        "stars": repo["stars"],
        "final_score": min(score, 7),  # cap at 7
        "reasons": reasons,
        "readme_length": len(readme),
        "code_blocks": code_blocks,
        "description": repo.get("description", "")[:200],
    }

def generate_skill_draft(evaluation):
    """Generate a skill draft if score is high enough."""
    if evaluation["final_score"] < 5:
        return None
    
    name = evaluation["name"].split("/")[-1].lower().replace("_", "-").replace(" ", "-")
    # sanitize further
    name = re.sub(r'[^a-z0-9-]', '', name)
    
    draft = f"""---
name: {name}
description: |
  Auto-discovered skill from {evaluation['name']}.
  {evaluation['description']}
trigger: |
  User mentions {name} or related functionality.
  Keywords: {name}, {evaluation['name'].split('/')[0]}
---

# {evaluation['name']}

Source: {evaluation['url']}
Stars: {evaluation['stars']}
Discovery score: {evaluation['final_score']}/7

## Quick Start

```bash
# TODO: Add install command after reviewing repo
```

## Usage

```bash
# TODO: Add usage examples after testing
```

## Notes

- Auto-discovered by daily research agent
- Needs manual review before activation
- Original repo: {evaluation['url']}
"""
    
    draft_path = os.path.join(SKILLS_DRAFTS, f"{name}.md")
    with open(draft_path, "w") as f:
        f.write(draft)
    
    return draft_path

def main():
    """Process all queued skill candidates."""
    processed = []
    created = []
    
    for fname in os.listdir(SKILLS_QUEUE):
        if not fname.endswith(".json"):
            continue
        
        path = os.path.join(SKILLS_QUEUE, fname)
        with open(path) as f:
            repo = json.load(f)
        
        print(f"\n[🔍] Deep-diving: {repo['name']}...")
        readme = fetch_readme(repo["name"])
        
        if readme.startswith("[ERROR"):
            print(f"    ⚠️  {readme}")
            continue
        
        eval_result = evaluate_skill_potential(repo, readme)
        print(f"    Score: {eval_result['final_score']}/7 ({', '.join(eval_result['reasons'])})")
        
        draft = generate_skill_draft(eval_result)
        if draft:
            print(f"    ✅ Skill draft created: {draft}")
            created.append({
                "name": repo["name"],
                "score": eval_result["final_score"],
                "draft": draft,
            })
        
        processed.append(eval_result)
        
        # Clean up queue
        os.remove(path)
    
    # Summary
    print(f"\n{'='*50}")
    print(f"Processed: {len(processed)} | Skill drafts: {len(created)}")
    if created:
        print("\nCreated drafts:")
        for c in created:
            print(f"  - {c['name']} (score {c['score']}): {c['draft']}")
    
    return created

if __name__ == "__main__":
    main()
