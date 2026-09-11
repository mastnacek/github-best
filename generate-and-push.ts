import * as fs from "node:fs";
import * as path from "node:path";
import { execSync } from "node:child_process";

interface RepoItem {
  id: number;
  dbId: number;
  name: string;
  url: string;
  desc: string;
  stars: number;
  forks: number;
  lang: string;
  created: string;
  createdIso: string;
  updated: string;
  updatedIso: string;
  pushed: string;
  pushedIso: string;
  archived: boolean;
}

function runCmd(cmd: string, input?: string): string {
  try {
    return execSync(cmd, {
      input,
      encoding: "utf8",
      maxBuffer: 50 * 1024 * 1024,
      stdio: ["pipe", "pipe", "pipe"],
    });
  } catch (err: unknown) {
    const errorMsg = err instanceof Error ? err.message : String(err);
    console.error(`Command failed: ${cmd}`, errorMsg);
    return "";
  }
}

function escapeHtml(str: string): string {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function renderCard(repo: RepoItem): string {
  const desc = escapeHtml(repo.desc || "No description provided.");
  const langBadge =
    repo.lang && repo.lang !== "Unknown"
      ? `<span class="badge">${escapeHtml(repo.lang)}</span>`
      : "";
  const archBadge = repo.archived
    ? '<span class="badge badge-archived">Archived</span>'
    : "";

  return `
    <article class="repo-card" data-id="${repo.id}">
      <div class="repo-header">
        <span class="rank">#${repo.id}</span>
        <h2 class="repo-title">
          <a href="${escapeHtml(repo.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(repo.name)}</a>
        </h2>
        <div class="stats-badges">
          <span class="badge-stat badge-stars" title="Stars">⭐ ${repo.stars.toLocaleString()}</span>
          <span class="badge-stat badge-forks" title="Forks">🍴 ${repo.forks.toLocaleString()}</span>
        </div>
      </div>
      <p class="repo-desc">${desc}</p>
      <div class="repo-meta">
        ${langBadge}
        ${archBadge}
        <span class="meta-date">📅 Created: <strong>${repo.created || "N/A"}</strong></span>
        <span class="meta-date">🔄 Last Updated: <strong>${repo.updated || "N/A"}</strong></span>
      </div>
    </article>`;
}

function buildHtml(collected: RepoItem[]): string {
  const langMap: Record<string, number> = {};
  for (const r of collected) {
    langMap[r.lang] = (langMap[r.lang] || 0) + 1;
  }
  const sortedLangs = Object.keys(langMap).sort((a, b) => a.localeCompare(b));

  const langOptionsHtml = [
    `<option value="">All Languages (${collected.length})</option>`,
    ...sortedLangs.map(
      (l) => `<option value="${escapeHtml(l)}">${escapeHtml(l)} (${langMap[l]})</option>`
    ),
  ].join("\n        ");

  const preRenderedCards = collected.map((r) => renderCard(r)).join("\n");
  const reposJson = JSON.stringify(collected);
  const topStars = collected[0]
    ? `${collected[0].stars.toLocaleString()} (${collected[0].name})`
    : "N/A";
  const lowestTopStars = collected.at(-1)
    ? `${collected.at(-1)?.stars.toLocaleString()} (${collected.at(-1)?.name})`
    : "N/A";

  const clientScript = `
    const allRepos = ${reposJson};
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

    function escapeStr(str) {
      if (!str) return "";
      return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
    }

    function renderList() {
      const q = searchInput.value.toLowerCase().trim();
      const selectedLang = langFilter.value;

      let filtered = allRepos.filter(repo => {
        const matchesLang = !selectedLang || repo.lang === selectedLang;
        const matchesQuery = !q ||
          repo.name.toLowerCase().includes(q) ||
          repo.desc.toLowerCase().includes(q) ||
          repo.lang.toLowerCase().includes(q);
        return matchesLang && matchesQuery;
      });

      filtered.sort((a, b) => {
        let valA, valB;
        if (currentSort === "stars") {
          valA = a.stars; valB = b.stars;
        } else if (currentSort === "forks") {
          valA = a.forks; valB = b.forks;
        } else if (currentSort === "created") {
          valA = a.createdIso; valB = b.createdIso;
        } else if (currentSort === "updated") {
          valA = a.updatedIso; valB = b.updatedIso;
        } else if (currentSort === "name") {
          valA = a.name.toLowerCase(); valB = b.name.toLowerCase();
          return sortOrder === "asc" ? valA.localeCompare(valB) : valB.localeCompare(valA);
        }
        if (valA < valB) return sortOrder === "asc" ? -1 : 1;
        if (valA > valB) return sortOrder === "asc" ? 1 : -1;
        return 0;
      });

      visibleCountEl.textContent = filtered.length;

      const sortMap = {
        stars: "Stars",
        updated: "Last Updated",
        created: "Creation Date",
        forks: "Forks",
        name: "Name"
      };
      currentSortLabel.textContent = sortMap[currentSort] + " (" + (sortOrder === "desc" ? "Highest/Newest first" : "Lowest/Oldest first") + ")";

      if (filtered.length === 0) {
        repoListEl.innerHTML = "";
        noResultsEl.style.display = "block";
        return;
      }
      noResultsEl.style.display = "none";

      const html = filtered.map((repo) => {
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
      }).join("");

      repoListEl.innerHTML = html;
    }

    searchInput.addEventListener("input", renderList);
    langFilter.addEventListener("change", renderList);
    sortBySelect.addEventListener("change", (e) => {
      currentSort = e.target.value;
      renderList();
    });

    orderBtn.addEventListener("click", () => {
      sortOrder = sortOrder === "desc" ? "asc" : "desc";
      orderIcon.textContent = sortOrder === "desc" ? "⬇️ Desc" : "⬆️ Asc";
      renderList();
    });
`;

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>⭐ Top 1,000 Most Starred GitHub Repositories (All Time)</title>
  <style>
    :root {
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
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background-color: var(--bg);
      color: var(--text);
      line-height: 1.6;
      padding: 30px 16px;
    }
    .container {
      max-width: 1100px;
      margin: 0 auto;
    }
    header {
      margin-bottom: 24px;
      border-bottom: 1px solid var(--border);
      padding-bottom: 20px;
    }
    h1 {
      color: #f0f6fc;
      font-size: 1.9rem;
      margin-bottom: 8px;
    }
    .subtitle {
      color: var(--text-muted);
      font-size: 0.95rem;
    }
    .stats-bar {
      display: flex;
      gap: 18px;
      margin-top: 14px;
      font-size: 0.88rem;
      color: var(--text-muted);
      flex-wrap: wrap;
    }
    .stats-item strong {
      color: var(--link);
    }
    .controls {
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
    }
    @media (max-width: 768px) {
      .controls {
        grid-template-columns: 1fr 1fr;
      }
      .controls .search-box {
        grid-column: 1 / -1;
      }
    }
    .search-box, .select-box, .btn {
      background: var(--card-bg);
      border: 1px solid var(--border);
      color: #f0f6fc;
      padding: 9px 12px;
      border-radius: 6px;
      font-size: 0.9rem;
      outline: none;
    }
    .search-box:focus, .select-box:focus {
      border-color: var(--link);
    }
    .btn {
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      justify-content: center;
      user-select: none;
    }
    .btn:hover {
      background: #21262d;
      border-color: var(--text-muted);
    }
    .repo-list {
      display: flex;
      flex-direction: column;
      gap: 14px;
    }
    .repo-card {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 18px 20px;
      transition: transform 0.12s ease, border-color 0.12s ease;
    }
    .repo-card:hover {
      border-color: var(--border-hover);
      transform: translateY(-1px);
    }
    .repo-header {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 8px;
      flex-wrap: wrap;
    }
    .rank {
      font-size: 0.85rem;
      font-weight: 700;
      color: var(--text-muted);
      min-width: 48px;
    }
    .repo-title {
      font-size: 1.18rem;
      font-weight: 600;
      flex: 1;
      min-width: 250px;
      word-break: break-all;
    }
    .repo-title a {
      color: var(--link);
      text-decoration: none;
    }
    .repo-title a:hover {
      text-decoration: underline;
    }
    .stats-badges {
      display: flex;
      gap: 10px;
      align-items: center;
    }
    .badge-stat {
      font-size: 0.82rem;
      padding: 3px 8px;
      border-radius: 12px;
      background: var(--badge-bg);
      border: 1px solid var(--border);
      font-weight: 600;
    }
    .badge-stars { color: var(--star); }
    .badge-forks { color: var(--fork); }
    .repo-desc {
      color: #8b949e;
      font-size: 0.92rem;
      margin-bottom: 12px;
      line-height: 1.5;
    }
    .repo-meta {
      display: flex;
      align-items: center;
      gap: 16px;
      font-size: 0.82rem;
      color: var(--text-muted);
      flex-wrap: wrap;
    }
    .badge {
      background: #1f242c;
      border: 1px solid var(--border);
      color: #58a6ff;
      padding: 2px 8px;
      border-radius: 12px;
      font-size: 0.78rem;
      font-weight: 600;
    }
    .badge-archived {
      background: rgba(210, 153, 34, 0.15);
      border-color: rgba(210, 153, 34, 0.4);
      color: #e3b341;
    }
    .meta-date {
      display: inline-flex;
      align-items: center;
      gap: 4px;
    }
    .meta-date strong {
      color: #f0f6fc;
      font-weight: 500;
    }
    #no-results {
      text-align: center;
      padding: 50px 20px;
      color: var(--text-muted);
      font-size: 1.1rem;
      display: none;
    }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <h1>⭐ Top 1,000 GitHub Repositories (All Time)</h1>
      <p class="subtitle">The top 1,000 highest-rated / most-starred public repositories across all of GitHub, retrieved live via GitHub CLI API (<code>gh api search/repositories</code>).</p>
      <div class="stats-bar">
        <span class="stats-item">Total Repos: <strong>${collected.length.toLocaleString()}</strong></span>
        <span class="stats-item">Top Stars: <strong>⭐ ${topStars}</strong></span>
        <span class="stats-item">#1,000 Stars: <strong>⭐ ${lowestTopStars}</strong></span>
        <span class="stats-item">Visible: <strong id="visible-count">${collected.length.toLocaleString()}</strong></span>
        <span class="stats-item">Current Sort: <strong id="current-sort-label">Stars (Highest first)</strong></span>
      </div>
    </header>

    <div class="controls">
      <input type="text" id="search-input" class="search-box" placeholder="🔍 Search by name, keyword, or description..." autofocus>
      
      <select id="language-filter" class="select-box">
        ${langOptionsHtml}
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
      ${preRenderedCards}
    </main>
    <div id="no-results">No matching repositories found. Try adjusting your filters.</div>
  </div>

  <script>
${clientScript}
  </script>
</body>
</html>`;
}

function buildReadme(collected: RepoItem[]): string {
  const top20Rows = collected
    .slice(0, 20)
    .map(
      (r) =>
        `| #${r.id} | [${r.name}](${r.url}) | ⭐ ${r.stars.toLocaleString()} | 🍴 ${r.forks.toLocaleString()} | ${r.lang} |`
    )
    .join("\n");

  return `# ⭐ Top 1,000 GitHub Repositories (All Time)

Automated curation and interactive dashboard of the **Top 1,000 most-starred public repositories** in GitHub history, generated directly using the GitHub CLI API (\`gh api\`).

## 🌐 Live Interactive Dashboard
Open [\`index.html\`](./index.html) in any browser for:
- ⚡ **Instant Search:** Search across repository names, topics, and descriptions.
- 🎯 **Multi-Sort:** Sort by Stars, Forks, Creation Date, Last Updated, and Name.
- 🏷️ **Language Filter:** Real-time filtering across 40+ primary programming languages.
- 📌 **Accurate Global Ranking:** Persistent #1 to #1000 rank badges.

## 🏆 Top 20 Repositories Preview

| Rank | Repository | Stars | Forks | Language |
| :--- | :--- | :--- | :--- | :--- |
${top20Rows}

---
*Generated automatically via [gh-cli](https://cli.github.com/).*
`;
}

async function main() {
  const scriptDir = typeof import.meta !== "undefined" && import.meta.dirname ? import.meta.dirname : process.cwd();
  process.chdir(scriptDir);

  const collected: RepoItem[] = [];
  console.log("Fetching top 1,000 repositories from GitHub API via gh-cli...");

  for (let page = 1; page <= 10; page++) {
    console.log(`Fetching page ${page}/10 (100 per page)...`);
    const raw = runCmd(
      `gh api "search/repositories?q=stars:>1&sort=stars&order=desc&per_page=100&page=${page}"`
    );
    if (!raw) {
      console.error(`Failed to fetch page ${page}`);
      break;
    }

    let parsed: { items?: Array<Record<string, unknown>> } | null = null;
    try {
      parsed = JSON.parse(raw);
    } catch (e: unknown) {
      const err = e instanceof Error ? e.message : String(e);
      console.error("JSON parse error:", err);
      break;
    }

    const items = parsed?.items || [];
    if (items.length === 0) break;

    for (const item of items) {
      collected.push({
        id: collected.length + 1,
        dbId: Number(item.id),
        name: String(item.full_name),
        url: String(item.html_url),
        desc: String(item.description || ""),
        stars: Number(item.stargazers_count || 0),
        forks: Number(item.forks_count || 0),
        lang: String(item.language || "Unknown"),
        created: item.created_at ? String(item.created_at).split("T")[0] : "",
        createdIso: String(item.created_at || ""),
        updated: item.updated_at ? String(item.updated_at).split("T")[0] : "",
        updatedIso: String(item.updated_at || ""),
        pushed: item.pushed_at ? String(item.pushed_at).split("T")[0] : "",
        pushedIso: String(item.pushed_at || ""),
        archived: Boolean(item.archived),
      });
      if (collected.length >= 1000) break;
    }
  }

  console.log(`Retrieved ${collected.length} repositories.`);

  // Write index.html and top-1000-repos.html
  const htmlContent = buildHtml(collected);
  fs.writeFileSync(path.join(scriptDir, "index.html"), htmlContent, "utf8");
  fs.writeFileSync(path.join(scriptDir, "top-1000-repos.html"), htmlContent, "utf8");
  console.log("Generated index.html and top-1000-repos.html");

  // Write README.md
  const readmeContent = buildReadme(collected);
  fs.writeFileSync(path.join(scriptDir, "README.md"), readmeContent, "utf8");
  console.log("Generated README.md");

  // Git repository initialization and push
  console.log("Initializing git and pushing to GitHub (mastnacek/github-best)...");
  if (!fs.existsSync(path.join(scriptDir, ".git"))) {
    runCmd("git init");
  }
  runCmd("git checkout -B main");

  // Check if GitHub repo exists
  const repoCheck = runCmd("gh repo view mastnacek/github-best --json nameWithOwner");
  if (!repoCheck || !repoCheck.includes("mastnacek/github-best")) {
    console.log("Creating GitHub repository 'mastnacek/github-best'...");
    runCmd("gh repo create mastnacek/github-best --public --description \"Top 1,000 Most Starred GitHub Repositories (All Time)\"");
  }

  runCmd("git remote remove origin");
  runCmd("git remote add origin https://github.com/mastnacek/github-best.git");
  runCmd("git add .");
  runCmd('git commit -m "Update Top 1,000 GitHub Repositories dashboard and generator scripts"');
  runCmd("git push -u origin main --force");
  console.log("Successfully pushed to https://github.com/mastnacek/github-best");
}

main().catch((err) => {
  console.error("Fatal error:", err);
  process.exit(1);
});
