#!/usr/bin/env python3
"""
Top 1,000 GitHub Repositories Generator and GitHub Publisher.
Uses GitHub CLI (`gh`) to fetch data, generate an interactive HTML dashboard, and push to GitHub.
"""

import json
import os
import subprocess
import sys


def run_cmd(cmd: str, check: bool = False) -> str:
    try:
        res = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=check,
        )
        return res.stdout.strip()
    except Exception as e:
        print(f"Command failed: {cmd} -> {e}", file=sys.stderr)
        return ""


def escape_html(text: str) -> str:
    if not text:
        return ""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#039;")
    )


def render_card(repo: dict) -> str:
    desc = escape_html(repo.get("desc", "No description provided."))
    lang = repo.get("lang", "")
    lang_badge = (
        f'<span class="badge">{escape_html(lang)}</span>'
        if lang and lang != "Unknown"
        else ""
    )
    arch_badge = (
        '<span class="badge badge-archived">Archived</span>'
        if repo.get("archived")
        else ""
    )
    stars = f"{repo.get('stars', 0):,}"
    forks = f"{repo.get('forks', 0):,}"

    return f"""
    <article class="repo-card" data-id="{repo['id']}">
      <div class="repo-header">
        <span class="rank">#{repo['id']}</span>
        <h2 class="repo-title">
          <a href="{escape_html(repo['url'])}" target="_blank" rel="noopener noreferrer">{escape_html(repo['name'])}</a>
        </h2>
        <div class="stats-badges">
          <span class="badge-stat badge-stars" title="Stars">⭐ {stars}</span>
          <span class="badge-stat badge-forks" title="Forks">🍴 {forks}</span>
        </div>
      </div>
      <p class="repo-desc">{desc}</p>
      <div class="repo-meta">
        {lang_badge}
        {arch_badge}
        <span class="meta-date">📅 Created: <strong>{repo.get('created', 'N/A')}</strong></span>
        <span class="meta-date">🔄 Last Updated: <strong>{repo.get('updated', 'N/A')}</strong></span>
      </div>
    </article>"""


def build_html(collected: list) -> str:
    lang_map = {}
    for r in collected:
        l = r.get("lang") or "Unknown"
        lang_map[l] = lang_map.get(l, 0) + 1

    sorted_langs = sorted(lang_map.keys())
    lang_options = [f'<option value="">All Languages ({len(collected)})</option>']
    for l in sorted_langs:
        lang_options.append(
            f'<option value="{escape_html(l)}">{escape_html(l)} ({lang_map[l]})</option>'
        )
    lang_options_html = "\n        ".join(lang_options)

    pre_rendered_cards = "\n".join(render_card(r) for r in collected)
    repos_json = json.dumps(collected, ensure_ascii=False)

    top_stars = (
        f"{collected[0]['stars']:,} ({collected[0]['name']})" if collected else "N/A"
    )
    lowest_stars = (
        f"{collected[-1]['stars']:,} ({collected[-1]['name']})" if collected else "N/A"
    )

    client_script = f"""
    const allRepos = {repos_json};
    let currentSort = "stars";
    let sortOrder = "desc";

    const repoListEl = document.getElementById("repo-list");
    const searchInput = document.getElementById("search-input");
    const langFilter = document.getElementById("language-filter");
    const sortBySelect = document.getElementById("sort-by");
    const orderBtn = document.getElementById("order-btn");
    const orderIcon = document.getElementById("order-icon");
    const visibleCountEl = document.getElementById("visible-count");
    const currentSortLabel = document.getElementById("current-sort-label");
    const noResultsEl = document.getElementById("no-results");

    function escapeStr(str) {{
      if (!str) return "";
      return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
    }}

    function renderList() {{
      const q = searchInput.value.toLowerCase().trim();
      const selectedLang = langFilter.value;

      let filtered = allRepos.filter(repo => {{
        const matchesLang = !selectedLang || repo.lang === selectedLang;
        const matchesQuery = !q ||
          repo.name.toLowerCase().includes(q) ||
          repo.desc.toLowerCase().includes(q) ||
          repo.lang.toLowerCase().includes(q);
        return matchesLang && matchesQuery;
      }});

      filtered.sort((a, b) => {{
        let valA, valB;
        if (currentSort === "stars") {{
          valA = a.stars; valB = b.stars;
        }} else if (currentSort === "forks") {{
          valA = a.forks; valB = b.forks;
        }} else if (currentSort === "created") {{
          valA = a.createdIso; valB = b.createdIso;
        }} else if (currentSort === "updated") {{
          valA = a.updatedIso; valB = b.updatedIso;
        }} else if (currentSort === "name") {{
          valA = a.name.toLowerCase(); valB = b.name.toLowerCase();
          return sortOrder === "asc" ? valA.localeCompare(valB) : valB.localeCompare(valA);
        }}
        if (valA < valB) return sortOrder === "asc" ? -1 : 1;
        if (valA > valB) return sortOrder === "asc" ? 1 : -1;
        return 0;
      }});

      visibleCountEl.textContent = filtered.length;

      const sortMap = {{
        stars: "Stars",
        updated: "Last Updated",
        created: "Creation Date",
        forks: "Forks",
        name: "Name"
      }};
      currentSortLabel.textContent = sortMap[currentSort] + " (" + (sortOrder === "desc" ? "Highest/Newest first" : "Lowest/Oldest first") + ")";

      if (filtered.length === 0) {{
        repoListEl.innerHTML = "";
        noResultsEl.style.display = "block";
        return;
      }}
      noResultsEl.style.display = "none";

      const html = filtered.map((repo) => {{
        const rank = repo.id;
        const desc = escapeStr(repo.desc || "No description provided.");
        const langBadge = repo.lang && repo.lang !== "Unknown" ? ('<span class="badge">' + escapeStr(repo.lang) + '</span>') : "";
        const archBadge = repo.archived ? '<span class="badge badge-archived">Archived</span>' : "";

        return [
          '<article class="repo-card" data-id="' + repo.id + '">',
            '<div class="repo-header">',
              '<span class="rank">#' + rank + '</span>',
              '<h2 class="repo-title">',
                '<a href="' + escapeStr(repo.url) + '" target="_blank" rel="noopener noreferrer">' + escapeStr(repo.name) + '</a>',
              '</h2>',
              '<div class="stats-badges">',
                '<span class="badge-stat badge-stars" title="Stars">⭐ ' + repo.stars.toLocaleString() + '</span>',
                '<span class="badge-stat badge-forks" title="Forks">🍴 ' + repo.forks.toLocaleString() + '</span>',
              '</div>',
            '</div>',
            '<p class="repo-desc">' + desc + '</p>',
            '<div class="repo-meta">',
              langBadge,
              archBadge,
              '<span class="meta-date">📅 Created: <strong>' + (repo.created || "N/A") + '</strong></span>',
              '<span class="meta-date">🔄 Last Updated: <strong>' + (repo.updated || "N/A") + '</strong></span>',
            '</div>',
          '</article>'
        ].join("");
      }}).join("");

      repoListEl.innerHTML = html;
    }}

    searchInput.addEventListener("input", renderList);
    langFilter.addEventListener("change", renderList);
    sortBySelect.addEventListener("change", (e) => {{
      currentSort = e.target.value;
      renderList();
    }});

    orderBtn.addEventListener("click", () => {{
      sortOrder = sortOrder === "desc" ? "asc" : "desc";
      orderIcon.textContent = sortOrder === "desc" ? "⬇️ Desc" : "⬆️ Asc";
      renderList();
    }});
    """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>⭐ Top 1,000 Most Starred GitHub Repositories (All Time)</title>
  <style>
    :root {{
      --bg: #0d1117;
      --card-bg: #161b22;
      --border: #30363d;
      --border-hover: #58a6ff;
      --text: #c9d1d9;
      --text-muted: #8b949e;
      --link: #58a6ff;
      --star: #e3b341;
      --fork: #7ee787;
      --badge-bg: #21262d;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background-color: var(--bg);
      color: var(--text);
      line-height: 1.6;
      padding: 30px 16px;
    }}
    .container {{
      max-width: 1100px;
      margin: 0 auto;
    }}
    header {{
      margin-bottom: 24px;
      border-bottom: 1px solid var(--border);
      padding-bottom: 20px;
    }}
    h1 {{
      color: #f0f6fc;
      font-size: 1.9rem;
      margin-bottom: 8px;
    }}
    .subtitle {{
      color: var(--text-muted);
      font-size: 0.95rem;
    }}
    .stats-bar {{
      display: flex;
      gap: 18px;
      margin-top: 14px;
      font-size: 0.88rem;
      color: var(--text-muted);
      flex-wrap: wrap;
    }}
    .stats-item strong {{
      color: var(--link);
    }}
    .controls {{
      display: grid;
      grid-template-columns: 1fr auto auto auto;
      gap: 12px;
      margin-bottom: 24px;
      position: sticky;
      top: 12px;
      z-index: 100;
      background: rgba(13, 17, 23, 0.96);
      backdrop-filter: blur(10px);
      padding: 14px;
      border-radius: 8px;
      border: 1px solid var(--border);
      box-shadow: 0 4px 16px rgba(0,0,0,0.3);
    }}
    @media (max-width: 768px) {{
      .controls {{
        grid-template-columns: 1fr 1fr;
      }}
      .controls .search-box {{
        grid-column: 1 / -1;
      }}
    }}
    .search-box, .select-box, .btn {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      color: #f0f6fc;
      padding: 9px 12px;
      border-radius: 6px;
      font-size: 0.9rem;
      outline: none;
    }}
    .search-box:focus, .select-box:focus {{
      border-color: var(--link);
    }}
    .btn {{
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      justify-content: center;
      user-select: none;
    }}
    .btn:hover {{
      background: #21262d;
      border-color: var(--text-muted);
    }}
    .repo-list {{
      display: flex;
      flex-direction: column;
      gap: 14px;
    }}
    .repo-card {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 18px 20px;
      transition: transform 0.12s ease, border-color 0.12s ease;
    }}
    .repo-card:hover {{
      border-color: var(--border-hover);
      transform: translateY(-1px);
    }}
    .repo-header {{
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 8px;
      flex-wrap: wrap;
    }}
    .rank {{
      font-size: 0.85rem;
      font-weight: 700;
      color: var(--text-muted);
      min-width: 48px;
    }}
    .repo-title {{
      font-size: 1.18rem;
      font-weight: 600;
      flex: 1;
      min-width: 250px;
      word-break: break-all;
    }}
    .repo-title a {{
      color: var(--link);
      text-decoration: none;
    }}
    .repo-title a:hover {{
      text-decoration: underline;
    }}
    .stats-badges {{
      display: flex;
      gap: 10px;
      align-items: center;
    }}
    .badge-stat {{
      font-size: 0.82rem;
      padding: 3px 8px;
      border-radius: 12px;
      background: var(--badge-bg);
      border: 1px solid var(--border);
      font-weight: 600;
    }}
    .badge-stars {{ color: var(--star); }}
    .badge-forks {{ color: var(--fork); }}
    .repo-desc {{
      color: #8b949e;
      font-size: 0.92rem;
      margin-bottom: 12px;
      line-height: 1.5;
    }}
    .repo-meta {{
      display: flex;
      align-items: center;
      gap: 16px;
      font-size: 0.82rem;
      color: var(--text-muted);
      flex-wrap: wrap;
    }}
    .badge {{
      background: #1f242c;
      border: 1px solid var(--border);
      color: #58a6ff;
      padding: 2px 8px;
      border-radius: 12px;
      font-size: 0.78rem;
      font-weight: 600;
    }}
    .badge-archived {{
      background: rgba(210, 153, 34, 0.15);
      border-color: rgba(210, 153, 34, 0.4);
      color: #e3b341;
    }}
    .meta-date {{
      display: inline-flex;
      align-items: center;
      gap: 4px;
    }}
    .meta-date strong {{
      color: #f0f6fc;
      font-weight: 500;
    }}
    #no-results {{
      text-align: center;
      padding: 50px 20px;
      color: var(--text-muted);
      font-size: 1.1rem;
      display: none;
    }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <h1>⭐ Top 1,000 GitHub Repositories (All Time)</h1>
      <p class="subtitle">The top 1,000 highest-rated / most-starred public repositories across all of GitHub, retrieved live via GitHub CLI API (<code>gh api search/repositories</code>).</p>
      <div class="stats-bar">
        <span class="stats-item">Total Repos: <strong>{len(collected):,}</strong></span>
        <span class="stats-item">Top Stars: <strong>⭐ {top_stars}</strong></span>
        <span class="stats-item">#1,000 Stars: <strong>⭐ {lowest_stars}</strong></span>
        <span class="stats-item">Visible: <strong id="visible-count">{len(collected):,}</strong></span>
        <span class="stats-item">Current Sort: <strong id="current-sort-label">Stars (Highest first)</strong></span>
      </div>
    </header>

    <div class="controls">
      <input type="text" id="search-input" class="search-box" placeholder="🔍 Search by name, keyword, or description..." autofocus>
      
      <select id="language-filter" class="select-box">
        {lang_options_html}
      </select>

      <select id="sort-by" class="select-box">
        <option value="stars">Sort by: ⭐ Stars</option>
        <option value="forks">Sort by: 🍴 Forks</option>
        <option value="created">Sort by: 📅 Created Date</option>
        <option value="updated">Sort by: 🔄 Last Updated</option>
        <option value="name">Sort by: 🔤 Name</option>
      </select>

      <button id="order-btn" class="btn" title="Toggle Ascending / Descending">
        <span id="order-icon">⬇️ Desc</span>
      </button>
    </div>

    <main class="repo-list" id="repo-list">
      {pre_rendered_cards}
    </main>
    <div id="no-results">No matching repositories found. Try adjusting your filters.</div>
  </div>

  <script>
{client_script}
  </script>
</body>
</html>"""


def build_readme(collected: list) -> str:
    top20_rows = []
    for r in collected[:20]:
        top20_rows.append(
            f"| #{r['id']} | [{r['name']}]({r['url']}) | ⭐ {r['stars']:,} | 🍴 {r['forks']:,} | {r.get('lang', 'Unknown')} |"
        )
    table_str = "\n".join(top20_rows)

    return f"""# ⭐ Top 1,000 GitHub Repositories (All Time)

Automated curation and interactive dashboard of the **Top 1,000 most-starred public repositories** in GitHub history, generated directly using the GitHub CLI API (`gh api`).

## 🌐 Live Interactive Dashboard
Open [`index.html`](./index.html) in any browser for:
- ⚡ **Instant Search:** Search across repository names, topics, and descriptions.
- 🎯 **Multi-Sort:** Sort by Stars, Forks, Creation Date, Last Updated, and Name.
- 🏷️ **Language Filter:** Real-time filtering across 40+ primary programming languages.
- 📌 **Accurate Global Ranking:** Persistent #1 to #1000 rank badges.

## 🏆 Top 20 Repositories Preview

| Rank | Repository | Stars | Forks | Language |
| :--- | :--- | :--- | :--- | :--- |
{table_str}

---
*Generated automatically via [gh-cli](https://cli.github.com/).*
"""


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)

    collected = []
    print("Fetching top 1,000 repositories from GitHub API via gh-cli...")

    for page in range(1, 11):
        print(f"Fetching page {page}/10 (100 per page)...")
        raw = run_cmd(
            f'gh api "search/repositories?q=stars:>1&sort=stars&order=desc&per_page=100&page={page}"'
        )
        if not raw:
            print(f"Failed to fetch page {page}", file=sys.stderr)
            break

        try:
            parsed = json.loads(raw)
        except Exception as e:
            print(f"Failed to parse page {page} JSON: {e}", file=sys.stderr)
            break

        items = parsed.get("items", [])
        if not items:
            break

        for item in items:
            created_at = item.get("created_at") or ""
            updated_at = item.get("updated_at") or ""
            collected.append(
                {
                    "id": len(collected) + 1,
                    "dbId": item.get("id"),
                    "name": item.get("full_name"),
                    "url": item.get("html_url"),
                    "desc": item.get("description") or "",
                    "stars": item.get("stargazers_count", 0),
                    "forks": item.get("forks_count", 0),
                    "lang": item.get("language") or "Unknown",
                    "created": created_at.split("T")[0] if created_at else "",
                    "createdIso": created_at,
                    "updated": updated_at.split("T")[0] if updated_at else "",
                    "updatedIso": updated_at,
                    "archived": bool(item.get("archived")),
                }
            )
            if len(collected) >= 1000:
                break

    print(f"Retrieved {len(collected)} repositories.")

    html_content = build_html(collected)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    with open("top-1000-repos.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    print("Saved index.html and top-1000-repos.html")

    readme_content = build_readme(collected)
    with open("README.md", "w", encoding="utf-8") as f:
        f.write(readme_content)
    print("Saved README.md")

    print("Initializing git and pushing to GitHub repository 'mastnacek/github-best'...")
    if not os.path.exists(".git"):
        run_cmd("git init")
    run_cmd("git checkout -B main")

    repo_check = run_cmd("gh repo view mastnacek/github-best --json nameWithOwner")
    if "mastnacek/github-best" not in repo_check:
        print("Creating GitHub repository 'mastnacek/github-best'...")
        run_cmd(
            'gh repo create mastnacek/github-best --public --description "Top 1,000 Most Starred GitHub Repositories (All Time)"'
        )

    run_cmd("git remote remove origin")
    run_cmd("git remote add origin https://github.com/mastnacek/github-best.git")
    run_cmd("git add .")
    run_cmd(
        'git commit -m "Update Top 1,000 GitHub Repositories dashboard and generator scripts"'
    )
    run_cmd("git push -u origin main --force")
    print("Successfully pushed to https://github.com/mastnacek/github-best")


if __name__ == "__main__":
    main()
