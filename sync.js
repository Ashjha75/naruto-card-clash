#!/usr/bin/env node
//
//

// Run command = node sync.js Docs personal
//
//

/**
 * kb-setup.js - Zero-dependency Knowledge Base Automation Script
 *
 * Drop this script into ANY of your projects (like Naruto Card Clash).
 * Run it to automatically:
 * 1. Scan a folder for .md / .txt files.
 * 2. Parse frontmatter (or auto-generate basic metadata if missing).
 * 3. Generate `manifest.json`.
 * 4. Auto-detect your GitHub repository & branch.
 * 5. Provide the EXACT copy-paste configuration for your MCP Knowledge Server.
 *
 * Usage:
 *   node kb-setup.js <target-folder> <profile-name>
 * Example:
 *   node kb-setup.js docs personal
 */

const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");

// ─── UTILS ───────────────────────────────────────────────────────────────────

function getGitInfo() {
	try {
		const remote = execSync("git config --get remote.origin.url")
			.toString()
			.trim();
		const branch = execSync("git branch --show-current").toString().trim();

		// Parse github URL (e.g. https://github.com/Ashish5jha/naruto-card-clash.git or git@github.com:Ashish5jha/naruto-card-clash.git)
		let user = "UNKNOWN_USER",
			repo = "UNKNOWN_REPO";
		const httpsMatch = remote.match(
			/github\.com\/([^\/]+)\/([^\/]+?)(?:\.git)?$/,
		);
		const sshMatch = remote.match(
			/github\.com:([^\/]+)\/([^\/]+?)(?:\.git)?$/,
		);

		if (httpsMatch) {
			user = httpsMatch[1];
			repo = httpsMatch[2];
		} else if (sshMatch) {
			user = sshMatch[1];
			repo = sshMatch[2];
		}

		return { user, repo, branch: branch || "main" };
	} catch (err) {
		return { user: "<YOUR_USER>", repo: "<YOUR_REPO>", branch: "<BRANCH>" };
	}
}

function walkDir(dir, fileList = []) {
	if (!fs.existsSync(dir)) return fileList;
	const files = fs.readdirSync(dir);
	for (const file of files) {
		if (file === "manifest.json" || file.startsWith(".")) continue;
		const fullPath = path.join(dir, file);
		if (fs.statSync(fullPath).isDirectory()) {
			walkDir(fullPath, fileList);
		} else if (file.endsWith(".md") || file.endsWith(".txt")) {
			fileList.push(fullPath);
		}
	}
	return fileList;
}

function parseFrontmatter(content, filePath) {
	const match = content.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n/);
	const fallbackId = path
		.basename(filePath, path.extname(filePath))
		.replace(/\s+/g, "-")
		.toLowerCase();

	if (!match) {
		// Auto-generate basic metadata if frontmatter is missing
		return {
			id: fallbackId,
			title: path.basename(filePath),
			type: "document",
			summary: "Auto-generated document without frontmatter.",
			tags: [],
			keywords: [],
			related: [],
			priority: 5,
			updated_at: new Date().toISOString().split("T")[0],
		};
	}

	const yaml = match[1];
	const lines = yaml.split("\n");
	const data = {};

	for (const line of lines) {
		const sep = line.indexOf(":");
		if (sep === -1) continue;
		const key = line.trim().slice(0, sep).trim();
		let val = line.slice(sep + 1).trim();

		// Simple array parsing: [a, b, c]
		if (val.startsWith("[") && val.endsWith("]")) {
			val = val
				.slice(1, -1)
				.split(",")
				.map((s) => s.trim().replace(/^['"]|['"]$/g, ""))
				.filter(Boolean);
		}
		// String quotes parsing
		else if (val.startsWith('"') && val.endsWith('"')) {
			val = val.slice(1, -1);
		}
		// Number parsing
		else if (!isNaN(Number(val)) && val !== "") {
			val = Number(val);
		}
		data[key] = val;
	}

	return {
		id: data.id || fallbackId,
		title: data.title || path.basename(filePath),
		type: data.type || "document",
		summary: data.summary || "",
		tags: Array.isArray(data.tags) ? data.tags : [],
		keywords: Array.isArray(data.keywords) ? data.keywords : [],
		related: Array.isArray(data.related) ? data.related : [],
		priority: data.priority || 5,
		updated_at: data.updated_at || new Date().toISOString().split("T")[0],
	};
}

// ─── MAIN ────────────────────────────────────────────────────────────────────

const args = process.argv.slice(2);
if (args.length < 2) {
	console.error("Usage: node kb-setup.js <target-folder> <profile-name>");
	console.error("Example: node kb-setup.js docs personal");
	process.exit(1);
}

const targetFolder = args[0];
const profileName = args[1];

const absoluteTarget = path.resolve(targetFolder);
if (!fs.existsSync(absoluteTarget)) {
	console.error(`Error: Folder "${targetFolder}" does not exist.`);
	process.exit(1);
}

console.log(`\n🔍 Scanning folder: ${targetFolder} ...`);
const files = walkDir(absoluteTarget);

const documents = [];
for (const file of files) {
	const content = fs.readFileSync(file, "utf8");
	const relativePath = path
		.relative(absoluteTarget, file)
		.replace(/\\/g, "/");

	const meta = parseFrontmatter(content, relativePath);
	meta.path = relativePath;
	documents.push(meta);
	console.log(`  ✅ Added: ${meta.id} (${relativePath})`);
}

const manifest = {
	profile: profileName,
	version: new Date().toISOString(),
	documents,
};

const manifestPath = path.join(absoluteTarget, "manifest.json");
fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2));

console.log(
	`\n🎉 Success! Wrote manifest.json with ${documents.length} documents.`,
);

// ─── GITHUB URL GENERATION ───────────────────────────────────────────────────

const gitInfo = getGitInfo();

// Generate the rawBase and manifestUrl for GitHub
const rawBase = `https://raw.githubusercontent.com/${gitInfo.user}/${gitInfo.repo}/${gitInfo.branch}/${targetFolder}/`;
const manifestUrl = `${rawBase}manifest.json`;

console.log(`
============================================================
🚀 NEXT STEPS FOR MCP KNOWLEDGE SERVER
============================================================

1️⃣ Add this configuration to your MCP Server Registry!
   You can either add this to your registry.json, or copy-paste
   this exact command into your terminal where wrangler is installed:

npx wrangler kv key put --binding=KNOWLEDGE_CACHE "config:registry" '{"${profileName}":{"manifestUrl":"${manifestUrl}","rawBase":"${rawBase}"}}' --remote

*(Note: If you have other profiles, make sure to merge this JSON with them!)*

2️⃣ After updating the registry and pushing this repo to GitHub,
   tell your AI Assistant (Cursor/Claude):
   "Reindex the ${profileName} profile."
============================================================
`);
