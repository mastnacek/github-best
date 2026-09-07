#!/usr/bin/env python3
"""
Scrapes README.md files for top 1,000 repositories using GitHub API (gh auth token or HTTPS),
stores markdown files in `readmes/`, and indexes them in SQLite FTS5 database `data/repos.db`.
"""

import concurrent.futures
import json
import os
import sqlite3
import subprocess
import sys
import time
import urllib.request

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
READMES_DIR = os.path.join(SCRIPT_DIR, "readmes")
DATA_DIR = os.path.join(SCRIPT_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "repos.db")

os.makedirs(READMES_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)


def get_gh_token() -> str:
    try:
        res = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True,
            text=True,
            check=True,
        )
        return res.stdout.strip()
    except Exception:
        return os.environ.get("GITHUB_TOKEN", "")


def load_repos() -> list:
    html_path = os.path.join(SCRIPT_DIR, "index.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            content = f.read()
        import re

        match = re.search(r"const allRepos = (\[.*?\]);\s+let currentSort", content, re.DOTALL)
        if match:
            return json.loads(match.group(1))
    raise RuntimeError("Could not load allRepos from index.html.")


def init_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS repos (
            id INTEGER PRIMARY KEY,
            db_id INTEGER,
            name TEXT NOT NULL,
            owner TEXT,
            repo_name TEXT,
            url TEXT,
            description TEXT,
            stars INTEGER,
            forks INTEGER,
            language TEXT,
            created_at TEXT,
            updated_at TEXT,
            archived INTEGER,
            readme_filename TEXT,
            readme_size INTEGER,
            readme_text TEXT
        );
    """)
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS repos_fts USING fts5(
            id UNINDEXED,
            name,
            description,
            language,
            readme_text,
            tokenize = 'porter unicode61'
        );
    """)
    return conn


def fetch_readme(repo_name: str, token: str) -> str:
    url = f"https://api.github.com/repos/{repo_name}/readme"
    headers = {
        "User-Agent": "github-best-scraper",
        "Accept": "application/vnd.github.raw+json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, headers=headers)
    for attempt in range(1, 4):
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                if resp.status == 200:
                    return resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return ""
            if e.code in (403, 429):
                time.sleep(2)
                continue
            return ""
        except Exception:
            if attempt == 3:
                return ""
            time.sleep(1)
    return ""


def main():
    token = get_gh_token()
    repos = load_repos()
    print(f"Loaded {len(repos)} repositories.")
    print("Scraping READMEs and populating SQLite FTS5 database...")

    conn = init_db()
    conn.execute("DELETE FROM repos;")
    conn.execute("DELETE FROM repos_fts;")
    conn.commit()

    start_time = time.time()
    results = []

    def process_repo(repo):
        name = repo["name"]
        parts = name.split("/")
        owner = parts[0] if len(parts) > 0 else ""
        repo_name = parts[1] if len(parts) > 1 else ""
        filename = f"{str(repo['id']).zfill(4)}_{owner}__{repo_name}.md"
        filepath = os.path.join(READMES_DIR, filename)

        readme_text = ""
        if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                readme_text = f.read()
        else:
            readme_text = fetch_readme(name, token)
            if readme_text:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(readme_text)

        size = len(readme_text.encode("utf-8"))
        return (repo, owner, repo_name, filename, size, readme_text)

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(process_repo, r) for r in repos]
        completed = 0
        for fut in concurrent.futures.as_completed(futures):
            repo, owner, repo_name, filename, size, readme_text = fut.result()
            results.append((repo, owner, repo_name, filename, size, readme_text))
            completed += 1
            if completed % 100 == 0 or completed == len(repos):
                elapsed = time.time() - start_time
                print(f"Progress: {completed}/{len(repos)} READMEs processed ({elapsed:.1f}s)")

    # Sort by original ID order
    results.sort(key=lambda x: x[0]["id"])

    # Batch insert into DB
    repo_rows = []
    fts_rows = []
    for repo, owner, repo_name, filename, size, readme_text in results:
        repo_rows.append(
            (
                repo["id"],
                repo.get("dbId", repo["id"]),
                repo["name"],
                owner,
                repo_name,
                repo["url"],
                repo.get("desc", ""),
                repo.get("stars", 0),
                repo.get("forks", 0),
                repo.get("lang", "Unknown"),
                repo.get("created", ""),
                repo.get("updated", ""),
                1 if repo.get("archived") else 0,
                filename,
                size,
                readme_text,
            )
        )
        fts_rows.append(
            (
                repo["id"],
                repo["name"],
                repo.get("desc", ""),
                repo.get("lang", "Unknown"),
                readme_text,
            )
        )

    conn.executemany(
        """
        INSERT INTO repos (id, db_id, name, owner, repo_name, url, description, stars, forks, language, created_at, updated_at, archived, readme_filename, readme_size, readme_text)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        repo_rows,
    )

    conn.executemany(
        """
        INSERT INTO repos_fts (id, name, description, language, readme_text)
        VALUES (?, ?, ?, ?, ?)
    """,
        fts_rows,
    )
    conn.commit()
    conn.close()

    db_size = os.path.getsize(DB_PATH) / (1024 * 1024)
    print(f"\nDone! SQLite FTS5 database: {DB_PATH} ({db_size:.2f} MB)")
    print(f"Markdown files stored in: {READMES_DIR}")


if __name__ == "__main__":
    main()
