#!/usr/bin/env node
/**
 * Model Context Protocol (MCP) Server for Top 1,000 GitHub Repositories & READMEs (Node.js).
 * Runs over stdio (JSON-RPC 2.0).
 */

const fs = require("node:fs");
const path = require("node:path");
const readline = require("node:readline");
const { DatabaseSync } = require("node:sqlite");

const SCRIPT_DIR = __dirname || process.cwd();
const DB_PATH = path.join(SCRIPT_DIR, "data", "repos.db");

function getDb() {
  if (!fs.existsSync(DB_PATH)) {
    throw new Error(`Database not found at ${DB_PATH}. Run node scrape_readmes.js first.`);
  }
  return new DatabaseSync(DB_PATH);
}

function toolSearchRepos({ query, limit = 10, language, min_stars = 0 }) {
  const db = getDb();
  const cleanLimit = Math.max(1, Math.min(Number(limit) || 10, 50));
  const cleanQuery = String(query).replace(/"/g, '""').trim();

  let sql = `
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
  `;
  const params = [cleanQuery];

  if (language) {
    sql += " AND lower(r.language) = lower(?)";
    params.push(String(language));
  }
  if (min_stars > 0) {
    sql += " AND r.stars >= ?";
    params.push(Number(min_stars));
  }
  sql += " ORDER BY rank LIMIT ?";
  params.push(cleanLimit);

  let rows = [];
  try {
    rows = db.prepare(sql).all(...params);
  } catch {
    // Fallback to LIKE
    let fbSql = `
      SELECT
        id, name, url, stars, forks, language, description,
        substr(readme_text, 1, 250) as readme_snippet,
        0 as rank
      FROM repos
      WHERE name LIKE ? OR description LIKE ? OR readme_text LIKE ?
    `;
    const wc = `%${query}%`;
    const fbParams = [wc, wc, wc];
    if (language) {
      fbSql += " AND lower(language) = lower(?)";
      fbParams.push(String(language));
    }
    fbSql += " ORDER BY stars DESC LIMIT ?";
    fbParams.push(cleanLimit);
    rows = db.prepare(fbSql).all(...fbParams);
  }

  if (!rows || rows.length === 0) {
    return `No repositories found matching query '${query}'.`;
  }

  const results = rows.map((r) => ({
    rank: r.id,
    name: r.name,
    url: r.url,
    stars: r.stars,
    forks: r.forks,
    language: r.language,
    description: r.description,
    readme_excerpt: (r.readme_snippet || "").trim().replace(/\n+/g, " "),
  }));

  return JSON.stringify(results, null, 2);
}

function toolGetRepoReadme({ name_or_id, max_chars = 8000, offset = 0 }) {
  const db = getDb();
  let row = null;
  if (/^\d+$/.test(String(name_or_id).trim())) {
    row = db.prepare("SELECT name, readme_text, readme_size FROM repos WHERE id = ?").get(Number(name_or_id));
  } else {
    row = db.prepare("SELECT name, readme_text, readme_size FROM repos WHERE lower(name) = lower(?)").get(String(name_or_id).trim());
  }

  if (!row) {
    return `Error: Repository '${name_or_id}' not found in top 1,000 dataset.`;
  }

  const readme = row.readme_text || "";
  if (!readme) {
    return `Repository '${row.name}' has no README or it could not be scraped.`;
  }

  const totalLen = readme.length;
  const start = Number(offset) || 0;
  const count = Number(max_chars) || 8000;
  const sliceText = readme.slice(start, start + count);
  const isTruncated = start + count < totalLen;

  let header = `# README: ${row.name} (Total characters: ${totalLen.toLocaleString()})\n`;
  if (start > 0 || isTruncated) {
    header += `*Showing characters ${start.toLocaleString()} to ${Math.min(start + count, totalLen).toLocaleString()}*\n\n`;
  }
  return header + sliceText;
}

function toolGetRepoInfo({ name_or_id }) {
  const db = getDb();
  let row = null;
  if (/^\d+$/.test(String(name_or_id).trim())) {
    row = db.prepare("SELECT * FROM repos WHERE id = ?").get(Number(name_or_id));
  } else {
    row = db.prepare("SELECT * FROM repos WHERE lower(name) = lower(?)").get(String(name_or_id).trim());
  }

  if (!row) {
    return `Error: Repository '${name_or_id}' not found in top 1,000 dataset.`;
  }

  const copy = { ...row };
  delete copy.readme_text;
  return JSON.stringify(copy, null, 2);
}

function toolListTopRepos({ limit = 20, language, sort_by = "stars" }) {
  const db = getDb();
  const cleanLimit = Math.max(1, Math.min(Number(limit) || 20, 100));

  let sortCol = "stars";
  if (sort_by === "forks") sortCol = "forks";
  else if (sort_by === "created") sortCol = "created_at";
  else if (sort_by === "updated") sortCol = "updated_at";
  else if (sort_by === "name") sortCol = "name";

  const order = sort_by === "name" ? "ASC" : "DESC";
  let sql = `SELECT id, name, url, stars, forks, language, description, created_at, updated_at FROM repos`;
  const params = [];
  if (language) {
    sql += " WHERE lower(language) = lower(?)";
    params.push(String(language));
  }
  sql += ` ORDER BY ${sortCol} ${order} LIMIT ?`;
  params.push(cleanLimit);

  const rows = db.prepare(sql).all(...params);
  return JSON.stringify(rows, null, 2);
}

const MCP_TOOLS = [
  {
    name: "search_repos",
    description: "Full-text search across Top 1,000 GitHub repositories and their full README files with BM25 ranking and keyword excerpts.",
    inputSchema: {
      type: "object",
      properties: {
        query: { type: "string", description: "Keywords or search term (e.g. 'agentic workflow', 'react compiler', 'rag vector database')" },
        limit: { type: "integer", description: "Maximum number of results to return (1-50, default 10)" },
        language: { type: "string", description: "Optional programming language filter (e.g. 'Python', 'Rust', 'TypeScript')" },
        min_stars: { type: "integer", description: "Optional minimum stars threshold (e.g. 50000)" },
      },
      required: ["query"],
    },
  },
  {
    name: "get_repo_readme",
    description: "Retrieve verbatim markdown README content for any of the Top 1,000 GitHub repositories by rank ID (1-1000) or owner/repo name.",
    inputSchema: {
      type: "object",
      properties: {
        name_or_id: { type: "string", description: "Repository rank ID (e.g. '1', '121') or full name (e.g. 'earendil-works/pi', 'torvalds/linux')" },
        max_chars: { type: "integer", description: "Maximum characters to return (default: 8000)" },
        offset: { type: "integer", description: "Starting character offset for pagination (default: 0)" },
      },
      required: ["name_or_id"],
    },
  },
  {
    name: "get_repo_info",
    description: "Get detailed metadata, stars, forks, creation date, and language stats for a top 1,000 repository.",
    inputSchema: {
      type: "object",
      properties: {
        name_or_id: { type: "string", description: "Repository rank ID (e.g. '121') or full name (e.g. 'earendil-works/pi')" },
      },
      required: ["name_or_id"],
    },
  },
  {
    name: "list_top_repos",
    description: "List and filter top GitHub repositories by language and sort criteria.",
    inputSchema: {
      type: "object",
      properties: {
        limit: { type: "integer", description: "Number of repositories to return (default 20, max 100)" },
        language: { type: "string", description: "Filter by language (e.g. 'Python', 'Rust', 'Go', 'TypeScript')" },
        sort_by: { type: "string", enum: ["stars", "forks", "created", "updated", "name"], description: "Sort order field (default: 'stars')" },
      },
    },
  },
];

function handleRequest(req) {
  const method = req.method;
  const reqId = req.id;

  if (method === "initialize") {
    return {
      jsonrpc: "2.0",
      id: reqId,
      result: {
        protocolVersion: "2024-11-05",
        capabilities: { tools: {}, resources: {} },
        serverInfo: { name: "github-best-mcp", version: "1.0.0" },
      },
    };
  }

  if (method === "notifications/initialized") {
    return null;
  }

  if (method === "tools/list") {
    return {
      jsonrpc: "2.0",
      id: reqId,
      result: { tools: MCP_TOOLS },
    };
  }

  if (method === "tools/call") {
    const params = req.params || {};
    const toolName = params.name;
    const args = params.arguments || {};

    try {
      let text = "";
      if (toolName === "search_repos") {
        text = toolSearchRepos(args);
      } else if (toolName === "get_repo_readme") {
        text = toolGetRepoReadme(args);
      } else if (toolName === "get_repo_info") {
        text = toolGetRepoInfo(args);
      } else if (toolName === "list_top_repos") {
        text = toolListTopRepos(args);
      } else {
        return {
          jsonrpc: "2.0",
          id: reqId,
          error: { code: -32601, message: `Unknown tool: ${toolName}` },
        };
      }

      return {
        jsonrpc: "2.0",
        id: reqId,
        result: {
          content: [{ type: "text", text }],
        },
      };
    } catch (err) {
      return {
        jsonrpc: "2.0",
        id: reqId,
        result: {
          isError: true,
          content: [{ type: "text", text: `Error: ${err.message}` }],
        },
      };
    }
  }

  return {
    jsonrpc: "2.0",
    id: reqId,
    error: { code: -32601, message: `Method not found: ${method}` },
  };
}

const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout,
  terminal: false,
});

rl.on("line", (line) => {
  const trimmed = line.trim();
  if (!trimmed) return;
  try {
    const req = JSON.parse(trimmed);
    const res = handleRequest(req);
    if (res) {
      process.stdout.write(JSON.stringify(res) + "\n");
    }
  } catch (e) {
    const errRes = {
      jsonrpc: "2.0",
      id: null,
      error: { code: -32700, message: `Parse error: ${e.message}` },
    };
    process.stdout.write(JSON.stringify(errRes) + "\n");
  }
});
