const fs = require("node:fs");
const path = require("node:path");
const { execSync } = require("node:child_process");
const { DatabaseSync } = require("node:sqlite");

const SCRIPT_DIR = __dirname || process.cwd();
const READMES_DIR = path.join(SCRIPT_DIR, "readmes");
const DATA_DIR = path.join(SCRIPT_DIR, "data");
const DB_PATH = path.join(DATA_DIR, "repos.db");

if (!fs.existsSync(READMES_DIR)) fs.mkdirSync(READMES_DIR, { recursive: true });
if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true });

function getGhToken() {
  try {
    return execSync("gh auth token", { encoding: "utf8", stdio: ["pipe", "pipe", "ignore"] }).trim();
  } catch {
    return process.env.GITHUB_TOKEN || "";
  }
}

const token = getGhToken();
const headers = {
  "User-Agent": "github-best-scraper",
  "Accept": "application/vnd.github.raw+json",
};
if (token) {
  headers.Authorization = `Bearer ${token}`;
}

function loadRepos() {
  const htmlPath = path.join(SCRIPT_DIR, "index.html");
  if (fs.existsSync(htmlPath)) {
    const content = fs.readFileSync(htmlPath, "utf8");
    const match = content.match(/const allRepos = (\[.*?\]);\s+let currentSort/s);
    if (match) {
      return JSON.parse(match[1]);
    }
  }
  throw new Error("Could not find allRepos in index.html. Run generate-and-push first.");
}

function initDb() {
  const db = new DatabaseSync(DB_PATH);
  db.exec(`
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

    CREATE VIRTUAL TABLE IF NOT EXISTS repos_fts USING fts5(
      id UNINDEXED,
      name,
      description,
      language,
      readme_text,
      tokenize = 'porter unicode61'
    );
  `);

  // Migration check for pushed_at column if older table
  try {
    db.exec("ALTER TABLE repos ADD COLUMN pushed_at TEXT;");
  } catch {
    // Column already exists
  }

  return db;
}

function sanitizeReadme(content) {
  if (!content) return "";
  return content
    .replace(/https:\/\/hooks\.slack\.com\/services\/[A-Za-z0-9_\/]+/g, "https://hooks.slack.com/services_example/T00/B00/XXXX")
    .replace(/https:\/\/discord\.com\/api\/webhooks\/[0-9]+\/[A-Za-z0-9_-]+/g, "https://discord.com/api/webhooks/example/XXXX")
    .replace(/ghp_[A-Za-z0-9]{20,}/g, "ghp_EXAMPLE_TOKEN")
    .replace(/gho_[A-Za-z0-9]{20,}/g, "gho_EXAMPLE_TOKEN")
    .replace(/ghs_[A-Za-z0-9]{20,}/g, "ghs_EXAMPLE_TOKEN")
    .replace(/sk-[A-Za-z0-9_-]{20,}/g, "sk-EXAMPLE_API_KEY")
    .replace(/AKIA[0-9A-Z]{16}/g, "AKIA_EXAMPLE_KEY");
}

async function fetchReadme(repoName) {
  const url = `https://api.github.com/repos/${repoName}/readme`;
  for (let attempt = 1; attempt <= 3; attempt++) {
    try {
      const res = await fetch(url, { headers });
      if (res.status === 200) {
        const text = await res.text();
        return sanitizeReadme(text);
      }
      if (res.status === 404) {
        return "";
      }
      if (res.status === 403 || res.status === 429) {
        console.warn(`Rate limit hit on attempt ${attempt}, waiting 3s...`);
        await new Promise((r) => setTimeout(r, 3000));
        continue;
      }
      return "";
    } catch {
      if (attempt === 3) return "";
      await new Promise((r) => setTimeout(r, 1000));
    }
  }
  return "";
}

async function asyncPool(limit, items, iteratorFn) {
  const ret = [];
  const executing = new Set();
  for (const item of items) {
    const p = Promise.resolve().then(() => iteratorFn(item));
    ret.push(p);
    executing.add(p);
    const clean = () => executing.delete(p);
    p.then(clean, clean);
    if (executing.size >= limit) {
      await Promise.race(executing);
    }
  }
  return Promise.all(ret);
}

async function main() {
  const repos = loadRepos();
  console.log(`Loaded ${repos.length} repositories from index.html.`);

  const db = initDb();

  // Load existing cached records for differential comparison
  const existingMap = new Map();
  try {
    const existingRows = db.prepare("SELECT id, name, description, updated_at, pushed_at, readme_filename, readme_size, readme_text FROM repos").all();
    for (const r of existingRows) {
      existingMap.set(r.name.toLowerCase(), r);
    }
    console.log(`Found ${existingMap.size} existing cached repositories in database.`);
  } catch (e) {
    console.log("No previous database records found. Starting initial sync.");
  }

  let unchangedCount = 0;
  let downloadedCount = 0;
  const startTime = Date.now();
  const processedData = [];

  console.log("Checking for updates (comparing pushed_at / updated_at and description)...");

  await asyncPool(20, repos, async (repo) => {
    const parts = repo.name.split("/");
    const owner = parts[0] || "";
    const repoName = parts[1] || "";
    const safeFilename = `${String(repo.id).padStart(4, "0")}_${owner}__${repoName}.md`;
    const readmeFile = path.join(READMES_DIR, safeFilename);

    const cached = existingMap.get(repo.name.toLowerCase());
    const fileExists = fs.existsSync(readmeFile) && fs.statSync(readmeFile).size > 0;

    const currentPushed = repo.pushedIso || repo.pushed || repo.updatedIso || repo.updated || "";
    const cachedPushed = cached?.pushed_at || cached?.updated_at || "";

    const currentDesc = (repo.desc || "").trim();
    const cachedDesc = (cached?.description || "").trim();

    // Check if both dates and description are unchanged AND file exists
    const isPushedUnchanged = currentPushed && cachedPushed && currentPushed === cachedPushed;
    const isDescUnchanged = currentDesc === cachedDesc;

    let readmeContent = "";
    let isDownloaded = false;

    if (isPushedUnchanged && isDescUnchanged && fileExists) {
      // Unchanged -> Use local cache without network call
      readmeContent = cached?.readme_text || fs.readFileSync(readmeFile, "utf8");
      unchangedCount++;
    } else {
      // Changed or missing -> Download fresh README
      readmeContent = await fetchReadme(repo.name);
      if (readmeContent) {
        fs.writeFileSync(readmeFile, readmeContent, "utf8");
      }
      downloadedCount++;
      isDownloaded = true;
    }

    const readmeSize = Buffer.byteLength(readmeContent, "utf8");
    processedData.push({
      repo,
      owner,
      repoName,
      safeFilename,
      readmeSize,
      readmeContent,
      pushedAt: currentPushed,
      isDownloaded,
    });
  });

  // Re-populate SQLite tables in order of ranking
  processedData.sort((a, b) => a.repo.id - b.repo.id);

  db.exec("DELETE FROM repos; DELETE FROM repos_fts;");

  const insertRepoStmt = db.prepare(`
    INSERT INTO repos (id, db_id, name, owner, repo_name, url, description, stars, forks, language, created_at, updated_at, pushed_at, archived, readme_filename, readme_size, readme_text)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  `);

  const insertFtsStmt = db.prepare(`
    INSERT INTO repos_fts (id, name, description, language, readme_text)
    VALUES (?, ?, ?, ?, ?)
  `);

  for (const item of processedData) {
    insertRepoStmt.run(
      item.repo.id,
      item.repo.dbId || item.repo.id,
      item.repo.name,
      item.owner,
      item.repoName,
      item.repo.url,
      item.repo.desc || "",
      item.repo.stars || 0,
      item.repo.forks || 0,
      item.repo.lang || "Unknown",
      item.repo.created || "",
      item.repo.updated || "",
      item.pushedAt || "",
      item.repo.archived ? 1 : 0,
      item.safeFilename,
      item.readmeSize,
      item.readmeContent
    );

    insertFtsStmt.run(
      item.repo.id,
      item.repo.name,
      item.repo.desc || "",
      item.repo.lang || "Unknown",
      item.readmeContent
    );
  }

  const elapsed = ((Date.now() - startTime) / 1000).toFixed(2);
  const totalBytes = fs.statSync(DB_PATH).size;

  console.log(`\n=== Synchronization Summary (${elapsed}s) ===`);
  console.log(`• Total Repositories: ${repos.length}`);
  console.log(`• Unchanged (Cached, 0 network requests): ${unchangedCount}`);
  console.log(`• Updated / Newly Downloaded: ${downloadedCount}`);
  console.log(`• SQLite FTS5 Database: ${DB_PATH} (${(totalBytes / 1024 / 1024).toFixed(2)} MB)`);
}

main().catch((err) => {
  console.error("Fatal error:", err);
  process.exit(1);
});
