#!/usr/bin/env python3
"""
Daily AI Agent Research Engine.
Collects, analyzes, and produces actionable intelligence.
"""
import json, urllib.request, urllib.parse, datetime, os, re, sys
from daily_topics import get_today_topic

REPORTS_DIR = "/root/managed-agents/research/reports"
SKILLS_QUEUE = "/root/managed-agents/internal/skills-queue"
USER_REPORTS_DIR = "/root/managed-agents/reports"
os.makedirs(REPORTS_DIR, exist_ok=True)
os.makedirs(SKILLS_QUEUE, exist_ok=True)
os.makedirs(USER_REPORTS_DIR, exist_ok=True)

# --- Collectors ---

def github_search(topic, per_page=5):
    """Search GitHub repos by topic, sorted by updated."""
    q = urllib.parse.quote(f"topic:{topic} stars:>10")
    url = f"https://api.github.com/search/repositories?q={q}&sort=updated&order=desc&per_page={per_page}"
    req = urllib.request.Request(url, headers={"User-Agent": "DailyResearch/1.0", "Accept": "application/vnd.github.v3+json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())
            items = data.get("items", [])
            results = []
            for item in items:
                results.append({
                    "name": item["full_name"],
                    "url": item["html_url"],
                    "description": item.get("description", "") or "",
                    "stars": item["stargazers_count"],
                    "updated": item["updated_at"][:10],
                    "language": item.get("language", "N/A"),
                })
            return results
    except Exception as e:
        return [{"error": str(e)}]


def arxiv_search(query, max_results=3):
    """Search arXiv via API."""
    q = urllib.parse.quote(query)
    url = f"http://export.arxiv.org/api/query?search_query={q}&start=0&max_results={max_results}&sortBy=submittedDate&sortOrder=descending"
    req = urllib.request.Request(url, headers={"User-Agent": "DailyResearch/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            text = resp.read().decode()
            entries = []
            for block in text.split("<entry>")[1:]:
                title = re.search(r"<title>(.*?)</title>", block, re.DOTALL)
                summary = re.search(r"<summary>(.*?)</summary>", block, re.DOTALL)
                link = re.search(r"<id>(.*?)</id>", block)
                published = re.search(r"<published>(.*?)</published>", block)
                if title and link:
                    entries.append({
                        "title": title.group(1).replace("\n", " ").strip(),
                        "summary": (summary.group(1).replace("\n", " ").strip()[:300] + "...") if summary else "",
                        "url": link.group(1).strip(),
                        "date": published.group(1)[:10] if published else "",
                    })
            return entries
    except Exception as e:
        return [{"error": str(e)}]


def web_search_ddg(query, max_results=3):
    """DuckDuckGo lite search (HTML scraping)."""
    q = urllib.parse.quote(query)
    url = f"https://html.duckduckgo.com/html/?q={q}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (DailyResearch)"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode()
            results = []
            for m in re.finditer(r'<a rel="nofollow" class="result__a" href="(.*?)">(.*?)</a>', html):
                href, title = m.group(1), re.sub(r'<.*?>', '', m.group(2))
                results.append({"title": title.strip(), "url": href.strip()})
                if len(results) >= max_results:
                    break
            return results
    except Exception as e:
        return [{"error": str(e)}]


# --- Analysis ---

def analyze_findings(findings):
    """Score findings for skill-potential."""
    scored = []
    for f in findings:
        score = 0
        reasons = []
        if f.get("stars", 0) > 100:
            score += 2
            reasons.append(f"popular ({f['stars']} stars)")
        if f.get("language") in ["Python", "TypeScript", "Go"]:
            score += 1
            reasons.append(f"practical language ({f['language']})")
        if f.get("description", "") and len(f["description"]) > 50:
            desc = f["description"].lower()
            if any(k in desc for k in ["agent", "autonomous", "orchestration", "mcp", "sandbox"]):
                score += 2
                reasons.append("relevant keywords")
        f["skill_score"] = score
        f["skill_reasons"] = reasons
        scored.append(f)
    return sorted(scored, key=lambda x: x["skill_score"], reverse=True)


# --- Report Generation ---

def generate_report(topic, github_results, arxiv_results, web_results):
    today = datetime.date.today().isoformat()
    report_path = os.path.join(REPORTS_DIR, f"{today}.md")
    
    scored = analyze_findings(github_results)
    high_potential = [r for r in scored if r.get("skill_score", 0) >= 3]
    
    lines = [
        f"# Daily Research: {topic['name']}",
        f"Date: {today}  ",
        f"Weekday: {datetime.date.today().strftime('%A')}",
        "",
        "## Search Queries",
        *[f"- {q}" for q in topic["queries"]],
        "",
        "## GitHub Discoveries",
    ]
    
    if not github_results or "error" in github_results[0]:
        lines.append("- GitHub API error or no results.")
    else:
        for r in scored:
            lines.append(f"### [{r['name']}]({r['url']})")
            lines.append(f"- ⭐ {r['stars']} | {r['language']} | Updated: {r['updated']}")
            lines.append(f"- {r['description']}")
            lines.append(f"- Skill score: {r['skill_score']}/5 ({', '.join(r['skill_reasons'])})")
            lines.append("")
    
    lines.extend([
        "## arXiv Papers",
    ])
    if not arxiv_results or "error" in arxiv_results[0]:
        lines.append("- arXiv error or no results.")
    else:
        for p in arxiv_results:
            lines.append(f"### [{p['title']}]({p['url']})")
            lines.append(f"- Date: {p['date']}")
            lines.append(f"- {p['summary']}")
            lines.append("")
    
    lines.extend([
        "## Web Search Results",
    ])
    if not web_results or "error" in web_results[0]:
        lines.append("- Search error or no results.")
    else:
        for w in web_results:
            lines.append(f"- [{w['title']}]({w['url']})")
        lines.append("")
    
    lines.extend([
        "## Skill Candidates",
        "These repos scored high for practical value. Consider creating skills from them:",
    ])
    if high_potential:
        for r in high_potential:
            lines.append(f"- **{r['name']}** (score {r['skill_score']}) — {r['description'][:80]}")
    else:
        lines.append("- No high-potential candidates today.")
    lines.append("")
    
    lines.extend([
        "## Action Items",
        "- [ ] Review skill candidates",
        "- [ ] Deep-dive top-scoring repo if applicable",
        "- [ ] Update relevant memory entries",
        "",
    ])
    
    with open(report_path, "w") as f:
        f.write("\n".join(lines))
    
    # --- Generate user-friendly Traditional Chinese report ---
    user_path = generate_user_report(today, topic, scored, high_potential, arxiv_results, web_results)
    
    return report_path, user_path, high_potential


def generate_user_report(today, topic, scored, high_potential, arxiv_results, web_results):
    """Generate a concise Traditional Chinese report for human review."""
    path = os.path.join(USER_REPORTS_DIR, f"{today}.md")
    
    weekday_cn = {"Monday":"週一","Tuesday":"週二","Wednesday":"週三","Thursday":"週四",
                  "Friday":"週五","Saturday":"週六","Sunday":"週日"}
    weekday = weekday_cn.get(datetime.date.today().strftime('%A'), "")
    
    lines = [
        f"# AI Agent 每日研究速報：{topic['name']}",
        f"**日期**：{today}（{weekday}）  ",
        f"**主題**：{topic['name']}",
        "",
        "---",
        "",
        "## 今日重點",
        "",
        f"今日搜索主題為 **{topic['name']}**。共找到 {len(scored)} 個相關專案，其中 {len(high_potential)} 個評分較高。",
        "",
        "---",
        "",
        "## 🚀 值得關注的發現",
        "",
    ]
    
    for i, r in enumerate(high_potential[:5], 1):
        desc = r.get('description', '') or ''
        lines.append(f"### {i}. {r['name']} ({r['stars']} ⭐)")
        lines.append(f"- **語言**：{r['language']}")
        lines.append(f"- **簡介**：{desc}")
        lines.append(f"- **對我們的用處**：{r['skill_reasons'][0] if r.get('skill_reasons') else '值得研究'}")
        lines.append(f"- **連結**：{r['url']}")
        lines.append("")
    
    lines.extend([
        "---",
        "",
        "## 📖 arXiv 論文",
        "",
    ])
    if not arxiv_results or "error" in arxiv_results[0]:
        lines.append("今日未找到相關論文，下次會換個關鍵字再試。")
    else:
        for p in arxiv_results:
            lines.append(f"- [{p['title']}]({p['url']}) ({p['date']})")
            lines.append(f"  {p['summary'][:120]}...")
            lines.append("")
    
    lines.extend([
        "---",
        "",
        "## 🌐 網路相關",
        "",
    ])
    if not web_results or "error" in web_results[0]:
        lines.append("今日網路搜尋無結果。")
    else:
        for w in web_results:
            lines.append(f"- [{w['title']}]({w['url']})")
        lines.append("")
    
    lines.extend([
        "---",
        "",
        "## ✅ 今日行動",
        "",
        "- [x] 完成今日主題搜索",
        "- [x] 選出高分專案",
        "- [ ] 深度分析 top 專案",
        "- [ ] 審核 skill drafts",
        "",
        "---",
        "",
        "*報告由自動研究系統產生 | 有問題請直接回覆*",
        "",
    ])
    
    with open(path, "w") as f:
        f.write("\n".join(lines))
    return path


def queue_skill_candidate(repo):
    """Write a skill candidate to the queue for later review."""
    path = os.path.join(SKILLS_QUEUE, f"{repo['name'].replace('/', '-')}.json")
    with open(path, "w") as f:
        json.dump(repo, f, ensure_ascii=False, indent=2)
    return path


# --- Main ---

def main():
    topic = get_today_topic()
    print(f"[🔍] Topic: {topic['name']}")
    
    all_github = []
    for t in topic["github_topics"]:
        print(f"  GitHub: topic={t}...", end=" ", flush=True)
        results = github_search(t)
        print(f"{len(results)} repos")
        all_github.extend(results)
    
    print(f"  arXiv: {topic['arxiv_query'][:50]}...", end=" ", flush=True)
    arxiv = arxiv_search(topic["arxiv_query"])
    print(f"{len(arxiv)} papers")
    
    all_web = []
    for q in topic["queries"][:2]:
        print(f"  Web: {q[:40]}...", end=" ", flush=True)
        results = web_search_ddg(q)
        print(f"{len(results)} results")
        all_web.extend(results)
    
    report_path, user_path, candidates = generate_report(topic, all_github, arxiv, all_web)
    print(f"[📝] Report: {report_path}")
    print(f"[📋] User report: {user_path}")
    
    for c in candidates[:3]:
        queue_path = queue_skill_candidate(c)
        print(f"[🚀] Queued skill candidate: {c['name']} → {queue_path}")
    
    # Summary for Telegram
    summary = f"""{datetime.date.today().isoformat()} 研究報告: {topic['name']}

GitHub: {len(all_github)} repos | arXiv: {len(arxiv)} papers | Web: {len(all_web)} links
Skill candidates: {len(candidates)}

Top pick: {candidates[0]['name'] if candidates else 'None'} ({candidates[0]['stars'] if candidates else 0} ⭐)

全文: {report_path}"""
    
    print("=" * 50)
    print(summary)
    return summary


if __name__ == "__main__":
    summary = main()
    # Write summary for external pickup
    with open("/root/managed-agents/research/last_summary.txt", "w") as f:
        f.write(summary)
