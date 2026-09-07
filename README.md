# ⭐ Top 1,000 GitHub Repositories (All Time) + README Search & MCP Server

Automated curation, interactive dashboard, full-text README search engine, and Model Context Protocol (MCP) server for the **Top 1,000 most-starred public repositories** in GitHub history.

---

## 🚀 Features

- 🌐 **Interactive Web Dashboard (`index.html`)**: Pre-rendered static HTML with instant search, multi-sort (Stars, Forks, Created, Updated, Name), dynamic language filters, and persistent global rankings (#1 to #1000).
- 📚 **1,000 Scraped READMEs (`readmes/`)**: Verbatim markdown README documentation scraped and stored locally for every repository.
- ⚡ **SQLite FTS5 Search Engine (`search.py` / `search.js`)**: Sub-millisecond BM25 ranked full-text search across all 1,000 repository READMEs with match highlighting and snippet generation.
- 🤖 **Model Context Protocol (MCP) Server (`mcp_server.py` / `mcp-server.js`)**: Connect the repository database and README search engine directly to Claude, Pi, OpenCode, Cursor, and any MCP-compatible agent.

---

## 🔍 CLI Search (BM25 Full-Text Search)

Search across repository titles, descriptions, and full README texts directly from your terminal:

```bash
# Search using Python
python search.py "vector database"
python search.py "agentic workflow" --lang Python --limit 5

# Search using Node.js
node search.js "transformer model"
node search.js "coding agent" -n 10
```

---

## 🤖 MCP Server Setup

Add this MCP server to your AI assistants (Claude Desktop, Pi Agent, Cursor, OpenCode):

### Claude Desktop (`claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "github-best": {
      "command": "python",
      "args": ["D:/01_programovani/gihub-best/mcp_server.py"]
    }
  }
}
```

### Pi Agent / Custom MCP (`mcp.json`):
```json
{
  "mcpServers": {
    "github-best": {
      "command": "node",
      "args": ["D:/01_programovani/gihub-best/mcp-server.js"]
    }
  }
}
```

### MCP Tools Available:
- `search_repos(query, limit, language, min_stars)`: Full-text search with BM25 ranking across 1,000 READMEs.
- `get_repo_readme(name_or_id, max_chars, offset)`: Retrieve full or paginated markdown README by rank ID (e.g. `121`) or repo name.
- `get_repo_info(name_or_id)`: Detailed metadata, stars, forks, and language information.
- `list_top_repos(limit, language, sort_by)`: Filter and sort top repositories.

---

## 📦 Data Scraping & Regeneration

To re-fetch repository rankings and re-index all READMEs:

```bash
# 1. Fetch latest top 1,000 repos from GitHub CLI
node generate-and-push.ts
# or
python generate_and_push.py

# 2. Scrape & re-index all READMEs into SQLite FTS5 database
node scrape_readmes.js
# or
python scrape_readmes.py
```

---

## 🏆 Top 20 Repositories Preview

| Rank | Repository | Stars | Forks | Language |
| :--- | :--- | :--- | :--- | :--- |
| #1 | [codecrafters-io/build-your-own-x](https://github.com/codecrafters-io/build-your-own-x) | ⭐ 545,703 | 🍴 51,378 | Markdown |
| #2 | [sindresorhus/awesome](https://github.com/sindresorhus/awesome) | ⭐ 503,795 | 🍴 36,766 | Unknown |
| #3 | [public-apis/public-apis](https://github.com/public-apis/public-apis) | ⭐ 476,696 | 🍴 52,632 | Python |
| #4 | [freeCodeCamp/freeCodeCamp](https://github.com/freeCodeCamp/freeCodeCamp) | ⭐ 455,150 | 🍴 46,145 | TypeScript |
| #5 | [EbookFoundation/free-programming-books](https://github.com/EbookFoundation/free-programming-books) | ⭐ 396,160 | 🍴 66,742 | Python |
| #6 | [openclaw/openclaw](https://github.com/openclaw/openclaw) | ⭐ 389,080 | 🍴 81,757 | TypeScript |
| #7 | [donnemartin/system-design-primer](https://github.com/donnemartin/system-design-primer) | ⭐ 368,437 | 🍴 58,273 | Python |
| #8 | [nilbuild/developer-roadmap](https://github.com/nilbuild/developer-roadmap) | ⭐ 366,456 | 🍴 44,899 | TypeScript |
| #9 | [jwasham/coding-interview-university](https://github.com/jwasham/coding-interview-university) | ⭐ 360,473 | 🍴 84,807 | Unknown |
| #10 | [vinta/awesome-python](https://github.com/vinta/awesome-python) | ⭐ 318,954 | 🍴 28,677 | Python |
| #11 | [awesome-selfhosted/awesome-selfhosted](https://github.com/awesome-selfhosted/awesome-selfhosted) | ⭐ 317,624 | 🍴 14,939 | Unknown |
| #12 | [obra/superpowers](https://github.com/obra/superpowers) | ⭐ 282,582 | 🍴 25,321 | Shell |
| #13 | [practical-tutorials/project-based-learning](https://github.com/practical-tutorials/project-based-learning) | ⭐ 282,404 | 🍴 36,168 | Python |
| #14 | [996icu/996.ICU](https://github.com/996icu/996.ICU) | ⭐ 276,908 | 🍴 20,724 | Unknown |
| #15 | [mattpocock/skills](https://github.com/mattpocock/skills) | ⭐ 255,458 | 🍴 21,523 | Shell |
| #16 | [affaan-m/ECC](https://github.com/affaan-m/ECC) | ⭐ 252,079 | 🍴 37,847 | JavaScript |
| #17 | [react/react](https://github.com/react/react) | ⭐ 249,621 | 🍴 51,294 | JavaScript |
| #18 | [torvalds/linux](https://github.com/torvalds/linux) | ⭐ 247,309 | 🍴 64,361 | C |
| #19 | [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) | ⭐ 242,777 | 🍴 49,934 | Python |
| #20 | [trimstray/the-book-of-secret-knowledge](https://github.com/trimstray/the-book-of-secret-knowledge) | ⭐ 242,456 | 🍴 14,292 | Unknown |

---
*Generated automatically via [gh-cli](https://cli.github.com/).*
