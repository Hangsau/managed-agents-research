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
            return resp.read().decode()[:40000]
    except:
        # Try master branch
        url = f"https://raw.githubusercontent.com/{full_name}/master/README.md"
        req = urllib.request.Request(url, headers={"User-Agent": "DeepDive/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.read().decode()[:40000]
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

def generate_skill_draft(evaluation, readme=""):
    """Generate a skill draft if score is high enough."""
    if evaluation["final_score"] < 5:
        return None
    
    name = evaluation["name"].split("/")[-1].lower().replace("_", "-").replace(" ", "-")
    name = re.sub(r'[^a-z0-9-]', '', name)
    
    # Extract install command from README (search in all text including code blocks)
    install_cmd = ""
    for line in readme.splitlines():
        line_stripped = line.strip().strip('`').strip()
        if any(line_stripped.startswith(cmd) for cmd in ["npm install", "pip install", "cargo install", "brew install", "go install", "yarn add", "pnpm add", "npx ", "curl ", "wget ", "git clone", "docker run"]):
            install_cmd = line_stripped
            break
    
    # Extract first code example (prefer non-install, but fallback to any)
    usage_example = ""
    code_blocks = re.findall(r"```(?:\w+)?\n(.*?)```", readme, re.DOTALL)
    for block in code_blocks:
        block_stripped = block.strip()
        if not block_stripped:
            continue
        # Skip install commands for usage example
        if any(block_stripped.startswith(cmd) for cmd in ["npm install", "pip install", "cargo install", "brew install", "go install", "yarn add", "pnpm add", "npx ", "curl ", "wget ", "git clone", "docker run"]):
            continue
        usage_example = block_stripped[:800]
        break
    
    # If no non-install code block found, take first code block
    if not usage_example and code_blocks:
        usage_example = code_blocks[0].strip()[:800]
    
    # Extract description from README first meaningful paragraph (skip HTML, badges, images)
    readme_desc = ""
    for line in readme.splitlines():
        line = line.strip()
        if not line:
            continue
        # Skip HTML tags, markdown images, badges, headings
        if line.startswith("<") or line.startswith("!") or line.startswith("[") or line.startswith("#") or line.startswith("|") or line.startswith("-") or line.startswith("*"):
            continue
        # Skip lines that are just badges or shields
        if "shields.io" in line or "badge" in line.lower() or "img.shields" in line:
            continue
        readme_desc = line[:200]
        break
    
    desc = readme_desc or evaluation.get("description", "")
    
    draft = f"""---
name: {name}
description: |
  {desc}
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
{install_cmd or '# TODO: Add install command after reviewing repo'}
```

## Usage

```bash
{usage_example or '# TODO: Add usage examples after testing'}
```

## Notes

- Auto-discovered by daily research agent (deep-dive analysis)
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
        
        draft = generate_skill_draft(eval_result, readme)
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
