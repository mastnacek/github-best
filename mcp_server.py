#!/usr/bin/env python3
"""
Model Context Protocol (MCP) Server for Top 1,000 GitHub Repositories & READMEs.
Runs over stdio (JSON-RPC 2.0).

Tools:
  - search_repos(query, limit, language, min_stars): Full-text search across READMEs and metadata.
  - get_repo_readme(name_or_id, max_chars, offset): Retrieve raw markdown README for any repo.
  - get_repo_info(name_or_id): Get complete structured metadata for a repository.
  - list_top_repos(limit, language, sort_by): List repos by rank, stars, forks, or date.
"""

import json
import os
import sqlite3
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(SCRIPT_DIR, "data", "repos.db")
READMES_DIR = os.path.join(SCRIPT_DIR, "readmes")


def get_db():
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"Database {DB_PATH} not found. Run scrape_readmes first.")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def tool_search_repos(query: str, limit: int = 10, language: str = None, min_stars: int = 0) -> str:
    conn = get_db()
    limit = max(1, min(limit, 50))
    clean_query = query.replace('"', '""').strip()

    sql = """
        SELECT
            r.id,
            r.name,
            r.url,
            r.stars,
            r.forks,
            r.language,
            r.description,
            snippet(repos_fts, 4, '«', '»', '...', 30) as readme_snippet,
            bm25(repos_fts) as rank
        FROM repos_fts f
        JOIN repos r ON r.id = f.id
        WHERE repos_fts MATCH ?
    """
    params = [clean_query]

    if language:
        sql += " AND lower(r.language) = lower(?)"
        params.append(language)

    if min_stars > 0:
        sql += " AND r.stars >= ?"
        params.append(min_stars)

    sql += " ORDER BY rank LIMIT ?"
    params.append(limit)

    try:
        rows = conn.execute(sql, params).fetchall()
    except sqlite3.OperationalError:
        # Fallback to LIKE
        fallback_sql = """
            SELECT
                id, name, url, stars, forks, language, description,
                substr(readme_text, 1, 250) as readme_snippet,
                0 as rank
            FROM repos
            WHERE name LIKE ? OR description LIKE ? OR readme_text LIKE ?
        """
        wildcard = f"%{query}%"
        fallback_params = [wildcard, wildcard, wildcard]
        if language:
            fallback_sql += " AND lower(language) = lower(?)"
            fallback_params.append(language)
        fallback_sql += " ORDER BY stars DESC LIMIT ?"
        fallback_params.append(limit)
        rows = conn.execute(fallback_sql, fallback_params).fetchall()

    conn.close()

    if not rows:
        return f"No repositories found matching query '{query}'."

    results = []
    for r in rows:
        snippet = r["readme_snippet"].strip().replace("\n", " ") if r["readme_snippet"] else ""
        results.append({
            "rank": r["id"],
            "name": r["name"],
            "url": r["url"],
            "stars": r["stars"],
            "forks": r["forks"],
            "language": r["language"],
            "description": r["description"],
            "readme_excerpt": snippet
        })
    return json.dumps(results, indent=2, ensure_ascii=False)


def tool_get_repo_readme(name_or_id: str, max_chars: int = 8000, offset: int = 0) -> str:
    conn = get_db()
    if str(name_or_id).isdigit():
        row = conn.execute("SELECT name, readme_text, readme_size FROM repos WHERE id = ?", (int(name_or_id),)).fetchone()
    else:
        row = conn.execute("SELECT name, readme_text, readme_size FROM repos WHERE lower(name) = lower(?)", (str(name_or_id).strip(),)).fetchone()
    conn.close()

    if not row:
        return f"Error: Repository '{name_or_id}' not found in top 1,000 dataset."

    readme = row["readme_text"] or ""
    if not readme:
        return f"Repository '{row['name']}' has no README or it could not be scraped."

    total_len = len(readme)
    slice_text = readme[offset:offset + max_chars]
    is_truncated = (offset + max_chars) < total_len

    header = f"# README: {row['name']} (Total characters: {total_len:,})\n"
    if offset > 0 or is_truncated:
        header += f"*Showing characters {offset:,} to {min(offset + max_chars, total_len):,}*\n\n"
    return header + slice_text


def tool_get_repo_info(name_or_id: str) -> str:
    conn = get_db()
    if str(name_or_id).isdigit():
        row = conn.execute("SELECT * FROM repos WHERE id = ?", (int(name_or_id),)).fetchone()
    else:
        row = conn.execute("SELECT * FROM repos WHERE lower(name) = lower(?)", (str(name_or_id).strip(),)).fetchone()
    conn.close()

    if not row:
        return f"Error: Repository '{name_or_id}' not found in top 1,000 dataset."

    info = dict(row)
    del info["readme_text"]  # Exclude massive text in info output
    return json.dumps(info, indent=2, ensure_ascii=False)


def tool_list_top_repos(limit: int = 20, language: str = None, sort_by: str = "stars") -> str:
    conn = get_db()
    limit = max(1, min(limit, 100))

    sort_col = "stars"
    if sort_by == "forks":
        sort_col = "forks"
    elif sort_by == "created":
        sort_col = "created_at"
    elif sort_by == "updated":
        sort_col = "updated_at"
    elif sort_by == "name":
        sort_col = "name"

    order = "ASC" if sort_by == "name" else "DESC"
    sql = f"SELECT id, name, url, stars, forks, language, description, created_at, updated_at FROM repos"
    params = []
    if language:
        sql += " WHERE lower(language) = lower(?)"
        params.append(language)
    sql += f" ORDER BY {sort_col} {order} LIMIT ?"
    params.append(limit)

    rows = conn.execute(sql, params).fetchall()
    conn.close()

    return json.dumps([dict(r) for r in rows], indent=2, ensure_ascii=False)


# MCP Protocol Tool Definitions
MCP_TOOLS = [
    {
        "name": "search_repos",
        "description": "Full-text search across Top 1,000 GitHub repositories and their full README files with BM25 ranking and keyword excerpts.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Keywords or search term (e.g. 'agentic workflow', 'react compiler', 'rag vector database')"},
                "limit": {"type": "integer", "description": "Maximum number of results to return (1-50, default 10)"},
                "language": {"type": "string", "description": "Optional programming language filter (e.g. 'Python', 'Rust', 'TypeScript')"},
                "min_stars": {"type": "integer", "description": "Optional minimum stars threshold (e.g. 50000)"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_repo_readme",
        "description": "Retrieve verbatim markdown README content for any of the Top 1,000 GitHub repositories by rank ID (1-1000) or owner/repo name.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name_or_id": {"type": "string", "description": "Repository rank ID (e.g. '1', '121') or full name (e.g. 'earendil-works/pi', 'torvalds/linux')"},
                "max_chars": {"type": "integer", "description": "Maximum characters to return (default: 8000)"},
                "offset": {"type": "integer", "description": "Starting character offset for pagination (default: 0)"}
            },
            "required": ["name_or_id"]
        }
    },
    {
        "name": "get_repo_info",
        "description": "Get detailed metadata, stars, forks, creation date, and language stats for a top 1,000 repository.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name_or_id": {"type": "string", "description": "Repository rank ID (e.g. '121') or full name (e.g. 'earendil-works/pi')"}
            },
            "required": ["name_or_id"]
        }
    },
    {
        "name": "list_top_repos",
        "description": "List and filter top GitHub repositories by language and sort criteria.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Number of repositories to return (default 20, max 100)"},
                "language": {"type": "string", "description": "Filter by language (e.g. 'Python', 'Rust', 'Go', 'TypeScript')"},
                "sort_by": {"type": "string", "enum": ["stars", "forks", "created", "updated", "name"], "description": "Sort order field (default: 'stars')"}
            }
        }
    }
]


def handle_request(req: dict) -> dict:
    method = req.get("method")
    req_id = req.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {},
                    "resources": {}
                },
                "serverInfo": {
                    "name": "github-best-mcp",
                    "version": "1.0.0"
                }
            }
        }

    if method == "notifications/initialized":
        return None  # Notifications do not return responses

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": MCP_TOOLS
            }
        }

    if method == "tools/call":
        params = req.get("params", {})
        tool_name = params.get("name")
        args = params.get("arguments", {})

        try:
            if tool_name == "search_repos":
                text = tool_search_repos(
                    query=args.get("query", ""),
                    limit=args.get("limit", 10),
                    language=args.get("language"),
                    min_stars=args.get("min_stars", 0)
                )
            elif tool_name == "get_repo_readme":
                text = tool_get_repo_readme(
                    name_or_id=args.get("name_or_id", ""),
                    max_chars=args.get("max_chars", 8000),
                    offset=args.get("offset", 0)
                )
            elif tool_name == "get_repo_info":
                text = tool_get_repo_info(name_or_id=args.get("name_or_id", ""))
            elif tool_name == "list_top_repos":
                text = tool_list_top_repos(
                    limit=args.get("limit", 20),
                    language=args.get("language"),
                    sort_by=args.get("sort_by", "stars")
                )
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"}
                }

            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": text}]
                }
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "isError": True,
                    "content": [{"type": "text", "text": f"Error executing tool: {e}"}]
                }
            }

    if method == "resources/list":
        conn = get_db()
        rows = conn.execute("SELECT id, name, description FROM repos LIMIT 100").fetchall()
        conn.close()
        resources = []
        for r in rows:
            resources.append({
                "uri": f"github-best://repos/{r['id']}",
                "name": f"README: {r['name']}",
                "description": r["description"] or f"README for #{r['id']} {r['name']}",
                "mimeType": "text/markdown"
            })
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"resources": resources}
        }

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"}
    }


def main():
    if sys.platform == "win32":
        try:
            sys.stdin.reconfigure(encoding="utf-8", errors="replace")
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            res = handle_request(req)
            if res:
                sys.stdout.write(json.dumps(res, ensure_ascii=False) + "\n")
                sys.stdout.flush()
        except Exception as e:
            err_res = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Parse error: {e}"}
            }
            sys.stdout.write(json.dumps(err_res) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
