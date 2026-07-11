from __future__ import annotations

import html
import shutil
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = REPO_ROOT / "Docs"
SITE_DIR = REPO_ROOT / "_site"
APP_DIST_DIR = REPO_ROOT / "UI" / "dist"
SITE_BASE_URL = "https://ashjha75.github.io/naruto-card-clash"
DOCS_BASE_URL = f"{SITE_BASE_URL}/docs"


def clean_site_dir() -> None:
    if SITE_DIR.exists():
        shutil.rmtree(SITE_DIR)
    SITE_DIR.mkdir(parents=True, exist_ok=True)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text

    meta: dict[str, Any] = {}
    frontmatter_lines: list[str] = []
    end_index: int | None = None

    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_index = index
            break
        frontmatter_lines.append(line)

    if end_index is None:
        return {}, text

    for raw_line in frontmatter_lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue

        key, value = line.split(":", 1)
        key = key.strip().lower()
        value = value.strip()
        meta[key] = parse_value(value)

    body = "\n".join(lines[end_index + 1 :]).lstrip("\n")
    return meta, body


def parse_value(value: str) -> Any:
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [item.strip().strip('"\'') for item in inner.split(",")]

    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1]
    return value


def extract_title(text: str, fallback: str) -> str:
    meta, body = parse_frontmatter(text)
    title = meta.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()

    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return fallback


def html_page(title: str, content: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>
    :root {{ color-scheme: light dark; }}
    body {{
      margin: 0;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.6;
      background: #0f172a;
      color: #e2e8f0;
    }}
    header, main {{ max-width: 1000px; margin: 0 auto; padding: 24px; }}
    header {{ border-bottom: 1px solid rgba(148, 163, 184, 0.25); }}
    a {{ color: #7dd3fc; }}
    .muted {{ color: #94a3b8; }}
    code, pre {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }}
    ul {{ padding-left: 1.25rem; }}
    li {{ margin: 0.35rem 0; }}
    .card {{ padding: 16px; border: 1px solid rgba(148, 163, 184, 0.2); border-radius: 12px; background: rgba(15, 23, 42, 0.55); margin: 12px 0; }}
    .small {{ font-size: 0.95rem; }}
    .meta-grid {{ display: grid; gap: 12px; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); }}
  </style>
</head>
<body>
  <header>
    <div class="muted">Naruto Card Clash Docs</div>
    <h1>{html.escape(title)}</h1>
  </header>
  <main>
    {content}
  </main>
</body>
</html>
"""


def redirect_page(target: str, title: str = "Redirecting") -> str:
    escaped_target = html.escape(target)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta http-equiv="refresh" content="0; url={escaped_target}">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
</head>
<body>
  <p>Redirecting to <a href="{escaped_target}">{escaped_target}</a>...</p>
</body>
</html>
"""


def as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value)


def build_master_text(entries: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    lines.append("Naruto Card Clash Docs")
    lines.append(f"Base URL: {DOCS_BASE_URL}/")
    lines.append(f"Docs index: {DOCS_BASE_URL}/index.txt")
    lines.append("")
    lines.append("Metadata contract:")
    lines.append("- Keep YAML frontmatter at the top of every doc.")
    lines.append("- Recommended fields: id, title, type, tags, keywords, summary.")
    lines.append("- The .txt copy preserves the frontmatter so AI tools can read it immediately.")
    lines.append("")
    lines.append(f"Total docs: {len(entries)}")
    lines.append("")
    lines.append("Documents:")

    for index, entry in enumerate(entries, start=1):
        lines.append(f"{index}. {entry['title']}")
        lines.append(f"   id: {entry.get('id', '')}")
        lines.append(f"   type: {entry.get('type', '')}")
        lines.append(f"   tags: {as_text(entry.get('tags', []))}")
        lines.append(f"   keywords: {as_text(entry.get('keywords', []))}")
        summary = as_text(entry.get('summary', '')).strip()
        if summary:
            lines.append(f"   summary: {summary}")
        lines.append(f"   file: {entry['relative_path']}")
        lines.append(f"   url: {DOCS_BASE_URL}/{entry['relative_path']}")
        lines.append(f"   source: Docs/{entry['source_path']}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def build_docs() -> list[dict[str, Any]]:
    docs_output = SITE_DIR / "docs"
    docs_output.mkdir(parents=True, exist_ok=True)

    entries: list[dict[str, Any]] = []
    for md_file in sorted(DOCS_DIR.rglob("*.md")):
        relative_md = md_file.relative_to(DOCS_DIR)
        relative_txt = relative_md.with_suffix(".txt")
        raw = read_text(md_file)
        meta, _body = parse_frontmatter(raw)
        title = extract_title(raw, relative_md.stem)

        destination = docs_output / relative_txt
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(md_file, destination)

        entries.append(
            {
                "title": title,
                "id": meta.get("id", relative_md.stem),
                "type": meta.get("type", ""),
                "tags": meta.get("tags", []),
                "keywords": meta.get("keywords", []),
                "summary": meta.get("summary", ""),
                "relative_path": relative_txt.as_posix(),
                "source_path": relative_md.as_posix(),
            }
        )

    master_text = build_master_text(entries)
    write_text(docs_output / "index.txt", master_text)
    write_text(docs_output / "index.html", redirect_page("index.txt", "Documentation index"))
    return entries


def build_root_index(doc_count: int, app_copied: bool) -> None:
    docs_link = f"{DOCS_BASE_URL}/index.txt"
    app_state = (
        "The Angular app build has been copied into the Pages root."
        if app_copied
        else "The Angular app is not deployed yet, so this Pages site is docs-first for now."
    )
    content = f"""
    <p>{html.escape(app_state)}</p>
    <p>
      Open the master docs file here:
      <a href="docs/index.txt">docs/index.txt</a>
    </p>
    <p class="small muted">
      Total docs published: {doc_count}. The master file contains metadata, absolute links, and source paths for AI tools.
    </p>
    <p class="small muted">
      Direct URL: <code>{html.escape(docs_link)}</code>
    </p>
    """
    write_text(SITE_DIR / "index.html", html_page("Naruto Card Clash", content))


def find_app_build_root() -> Path | None:
    if not APP_DIST_DIR.exists():
        return None

    if (APP_DIST_DIR / "index.html").exists():
        return APP_DIST_DIR

    index_files = sorted(APP_DIST_DIR.rglob("index.html"))
    if index_files:
        return index_files[0].parent

    return APP_DIST_DIR


def copy_app_build_if_present() -> bool:
    build_root = find_app_build_root()
    if build_root is None or not build_root.exists():
        return False

    copied_any = False
    for item in sorted(build_root.iterdir()):
        destination = SITE_DIR / item.name
        if item.is_dir():
            shutil.copytree(item, destination, dirs_exist_ok=True)
        else:
            shutil.copy2(item, destination)
        copied_any = True
    return copied_any


def main() -> None:
    clean_site_dir()
    docs_entries = build_docs()
    app_copied = copy_app_build_if_present()
    build_root_index(len(docs_entries), app_copied)

    if not app_copied:
        write_text(
            SITE_DIR / "app-placeholder.html",
            html_page(
                "Angular app not deployed yet",
                """
                <p>The Angular build is not present yet. When it is added, its files can be copied into the Pages root.</p>
                <p>For docs, use <a href="docs/index.txt">docs/index.txt</a>.</p>
                """,
            ),
        )

    print(f"Copied {len(docs_entries)} markdown docs into plain-text Pages files")
    if app_copied:
        print("Copied Angular build output into site root")
    else:
        print("No Angular build found; published a docs-only site")


if __name__ == "__main__":
    main()
