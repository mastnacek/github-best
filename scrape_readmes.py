#!/usr/bin/env python3
"""
Differential Scraper for Top 1,000 GitHub Repositories & READMEs (Python).
Compares `pushed_at` / `updated_at` dates and `description` to skip unnecessary README downloads.
Stores markdown files in `readmes/` and updates SQLite FTS5 database `data/repos.db`.
"""

import concurrent.futures
import json
import os
import re
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
            pushed_at TEXT,
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
    # Migration check for pushed_at column
    try:
        conn.execute("ALTER TABLE repos ADD COLUMN pushed_at TEXT;")
    except Exception:
        pass
    return conn


def sanitize_readme(content: str) -> str:
    if not content:
        return ""
    content = re.sub(
        r"https://hooks\.slack\.com/services/[A-Za-z0-9_/]+",
        "https://hooks.slack.com/services_example/T00/B00/XXXX",
        content,
    )
    content = re.sub(
        r"https://discord\.com/api/webhooks/[0-9]+/[A-Za-z0-9_-]+",
        "https://discord.com/api/webhooks/example/XXXX",
        content,
    )
    content = re.sub(r"gh[pos]_[A-Za-z0-9]{20,}", "ghp_EXAMPLE_TOKEN", content)
    content = re.sub(r"sk-[A-Za-z0-9_-]{20,}", "sk-EXAMPLE_API_KEY", content)
    content = re.sub(r"AKIA[0-9A-Z]{16}", "AKIA_EXAMPLE_KEY", content)
    return content


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
                    text = resp.read().decode("utf-8", errors="replace")
                    return sanitize_readme(text)
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

    conn = init_db()
    conn.row_factory = sqlite3.Row

    # Load existing cached records for date & description comparison
    existing_map = {}
    try:
        rows = conn.execute(
            "SELECT id, name, description, updated_at, pushed_at, readme_filename, readme_size, readme_text FROM repos"
        ).fetchall()
        for r in rows:
            existing_map[r["name"].lower()] = dict(r)
        print(f"Found {len(existing_map)} existing cached repositories in database.")
    except Exception:
        print("No previous database records found. Starting initial sync.")

    start_time = time.time()
    results = []
    unchanged_count = 0
    downloaded_count = 0

    print("Checking for updates (comparing pushed_at / updated_at and description)...")

    def process_repo(repo):
        nonlocal unchanged_count, downloaded_count
        name = repo["name"]
        parts = name.split("/")
        owner = parts[0] if len(parts) > 0 else ""
        repo_name = parts[1] if len(parts) > 1 else ""
        filename = f"{str(repo['id']).zfill(4)}_{owner}__{repo_name}.md"
        filepath = os.path.join(READMES_DIR, filename)

        cached = existing_map.get(name.lower())
        file_exists = os.path.exists(filepath) and os.path.getsize(filepath) > 0

        current_pushed = (
            repo.get("pushedIso")
            or repo.get("pushed")
            or repo.get("updatedIso")
            or repo.get("updated")
            or ""
        )
        cached_pushed = (
            cached.get("pushed_at") if cached else ""
        ) or (cached.get("updated_at") if cached else "")

        current_desc = (repo.get("desc") or "").strip()
        cached_desc = (cached.get("description") or "").strip() if cached else ""

        is_pushed_same = current_pushed and cached_pushed and current_pushed == cached_pushed
        is_desc_same = current_desc == cached_desc

        readme_text = ""
        is_downloaded = False

        if is_pushed_same and is_desc_same and file_exists:
            # Re-use cached without network request
            readme_text = cached.get("readme_text") if cached else ""
            if not readme_text and file_exists:
                with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                    readme_text = f.read()
            unchanged_count += 1
        else:
            # Download fresh README
            readme_text = fetch_readme(name, token)
            if readme_text:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(readme_text)
            downloaded_count += 1
            is_downloaded = True

        size = len(readme_text.encode("utf-8"))
        return (repo, owner, repo_name, filename, size, readme_text, current_pushed, is_downloaded)

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(process_repo, r) for r in repos]
        for fut in concurrent.futures.as_completed(futures):
            res = fut.result()
            results.append(res)

    results.sort(key=lambda x: x[0]["id"])

    # Re-insert into DB
    conn.execute("DELETE FROM repos;")
    conn.execute("DELETE FROM repos_fts;")

    repo_rows = []
    fts_rows = []
    for repo, owner, repo_name, filename, size, readme_text, pushed_at, _ in results:
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
                pushed_at,
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
        INSERT INTO repos (id, db_id, name, owner, repo_name, url, description, stars, forks, language, created_at, updated_at, pushed_at, archived, readme_filename, readme_size, readme_text)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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

    elapsed = time.time() - start_time
    db_size = os.path.getsize(DB_PATH) / (1024 * 1024)

    print(f"\n=== Synchronization Summary ({elapsed:.2f}s) ===")
    print(f"• Total Repositories: {len(repos)}")
    print(f"• Unchanged (Cached, 0 network requests): {unchanged_count}")
    print(f"• Updated / Newly Downloaded: {downloaded_count}")
    print(f"• SQLite FTS5 Database: {DB_PATH} ({db_size:.2f} MB)")


if __name__ == "__main__":
    main()
