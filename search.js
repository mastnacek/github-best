#!/usr/bin/env node
/**
 * CLI Full-Text Search over Top 1,000 GitHub Repos & READMEs (Node.js).
 * Usage: node search.js <query> [-n limit] [-l lang]
 */

const path = require("node:path");
const fs = require("node:fs");
const { DatabaseSync } = require("node:sqlite");

const SCRIPT_DIR = __dirname || process.cwd();
const DB_PATH = path.join(SCRIPT_DIR, "data", "repos.db");

if (!fs.existsSync(DB_PATH)) {
  console.error(`Error: Database ${DB_PATH} not found. Run node scrape_readmes.js first.`);
  process.exit(1);
}

const args = process.argv.slice(2);
if (args.length === 0) {
  console.log("Usage: node search.js <query> [-n limit] [-l lang] [-s min_stars]");
  process.exit(0);
}

let query = "";
let limit = 10;
let lang = null;
let minStars = 0;

for (let i = 0; i < args.length; i++) {
  if (args[i] === "-n" && args[i + 1]) {
    limit = parseInt(args[i + 1], 10) || 10;
    i++;
  } else if (args[i] === "-l" && args[i + 1]) {
    lang = args[i + 1];
    i++;
  } else if (args[i] === "-s" && args[i + 1]) {
    minStars = parseInt(args[i + 1], 10) || 0;
    i++;
  } else if (!query) {
    query = args[i];
  } else {
    query += " " + args[i];
  }
}

const db = new DatabaseSync(DB_PATH);
const cleanQuery = query.replace(/"/g, '""').trim();

let sql = `
  SELECT
    r.id,
    r.name,
    r.url,
    r.stars,
    r.forks,
    r.language,
    r.description,
    snippet(repos_fts, 4, '\x1b[1;33m', '\x1b[0m', '...', 25) as readme_snippet,
    bm25(repos_fts) as rank
  FROM repos_fts f
  JOIN repos r ON r.id = f.id
  WHERE repos_fts MATCH ?
`;
const params = [cleanQuery];

if (lang) {
  sql += " AND lower(r.language) = lower(?)";
  params.push(lang);
}
if (minStars > 0) {
  sql += " AND r.stars >= ?";
  params.push(minStars);
}
sql += " ORDER BY rank LIMIT ?";
params.push(limit);

let rows = [];
try {
  rows = db.prepare(sql).all(...params);
} catch (e) {
  console.log(`FTS5 exact match fallback for '${query}'...`);
  let fbSql = `
    SELECT
      id, name, url, stars, forks, language, description,
      substr(readme_text, 1, 200) as readme_snippet,
      0 as rank
    FROM repos
    WHERE name LIKE ? OR description LIKE ? OR readme_text LIKE ?
  `;
  const wc = `%${query}%`;
  const fbParams = [wc, wc, wc];
  if (lang) {
    fbSql += " AND lower(language) = lower(?)";
    fbParams.push(lang);
  }
  fbSql += " ORDER BY stars DESC LIMIT ?";
  fbParams.push(limit);
  rows = db.prepare(fbSql).all(...fbParams);
}

console.log(`\n🔍 Search results for: "${query}" (${rows.length} matches)\n` + "=".repeat(70));
for (const row of rows) {
  console.log(`\x1b[1;36m#${row.id}\x1b[0m \x1b[1;37m${row.name}\x1b[0m [⭐ ${row.stars.toLocaleString()} | 🍴 ${row.forks.toLocaleString()} | ${row.language}]`);
  console.log(`  \x1b[90mURL:\x1b[0m ${row.url}`);
  if (row.description) {
    console.log(`  \x1b[90mDesc:\x1b[0m ${row.description}`);
  }
  if (row.readme_snippet) {
    const cleanSnippet = row.readme_snippet.trim().split("\n").map(l => l.trim()).filter(Boolean).join("\n    ");
    console.log(`  \x1b[90mREADME match:\x1b[0m ${cleanSnippet}`);
  }
  console.log("-".repeat(70));
}
