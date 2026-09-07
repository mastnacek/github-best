#!/usr/bin/env python3
"""
CLI Full-Text & Metadata Search over Top 1,000 GitHub Repositories & READMEs.
Usage:
  python search.py "query" [--limit 10] [--lang Python] [--readmes-only]
"""

import argparse
import os
import sqlite3
import sys

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(SCRIPT_DIR, "data", "repos.db")


def format_snippet(snippet: str) -> str:
    if not snippet:
        return ""
    # Clean up excess whitespace and format
    lines = [l.strip() for l in snippet.split("\n") if l.strip()]
    return "\n    ".join(lines)


def search(query: str, limit: int = 10, lang: str = None, min_stars: int = 0):
    if not os.path.exists(DB_PATH):
        print(f"Error: Database {DB_PATH} not found. Run scrape_readmes first.", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Format FTS5 query terms
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
            snippet(repos_fts, 4, '\033[1;33m', '\033[0m', '...', 25) as readme_snippet,
            bm25(repos_fts) as rank
        FROM repos_fts f
        JOIN repos r ON r.id = f.id
        WHERE repos_fts MATCH ?
    """
    params = [clean_query]

    if lang:
        sql += " AND lower(r.language) = lower(?)"
        params.append(lang)

    if min_stars > 0:
        sql += " AND r.stars >= ?"
        params.append(min_stars)

    sql += " ORDER BY rank LIMIT ?"
    params.append(limit)

    try:
        rows = conn.execute(sql, params).fetchall()
    except sqlite3.OperationalError as e:
        # Fallback to simple LIKE query if FTS5 syntax fails
        print(f"FTS5 exact match error: {e}. Falling back to keyword search...")
        fallback_sql = """
            SELECT
                id, name, url, stars, forks, language, description,
                substr(readme_text, 1, 200) as readme_snippet,
                0 as rank
            FROM repos
            WHERE name LIKE ? OR description LIKE ? OR readme_text LIKE ?
        """
        wildcard = f"%{query}%"
        fallback_params = [wildcard, wildcard, wildcard]
        if lang:
            fallback_sql += " AND lower(language) = lower(?)"
            fallback_params.append(lang)
        fallback_sql += " ORDER BY stars DESC LIMIT ?"
        fallback_params.append(limit)
        rows = conn.execute(fallback_sql, fallback_params).fetchall()

    conn.close()

    print(f"\n🔍 Search results for: \"{query}\" ({len(rows)} matches)\n" + "=" * 70)
    for row in rows:
        stars = f"{row['stars']:,}"
        forks = f"{row['forks']:,}"
        print(f"\033[1;36m#{row['id']}\033[0m \033[1;37m{row['name']}\033[0m [⭐ {stars} | 🍴 {forks} | {row['language']}]")
        print(f"  \033[90mURL:\033[0m {row['url']}")
        if row['description']:
            print(f"  \033[90mDesc:\033[0m {row['description']}")
        snippet = row['readme_snippet']
        if snippet:
            formatted = format_snippet(snippet)
            print(f"  \033[90mREADME match:\033[0m {formatted}")
        print("-" * 70)


def main():
    parser = argparse.ArgumentParser(description="Search Top 1,000 GitHub Repos & READMEs")
    parser.add_argument("query", help="Search terms or FTS5 query")
    parser.add_argument("-n", "--limit", type=int, default=10, help="Max results to display (default: 10)")
    parser.add_argument("-l", "--lang", help="Filter by language (e.g. Python, Rust)")
    parser.add_argument("-s", "--min-stars", type=int, default=0, help="Minimum stars threshold")
    args = parser.parse_args()

    search(args.query, args.limit, args.lang, args.min_stars)


if __name__ == "__main__":
    main()
