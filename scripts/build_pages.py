from __future__ import annotations

import html
import re
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = REPO_ROOT / "Docs"
SITE_DIR = REPO_ROOT / "_site"
APP_DIST_DIR = REPO_ROOT / "UI" / "dist"


def clean_site_dir() -> None:
    if SITE_DIR.exists():
        shutil.rmtree(SITE_DIR)
    SITE_DIR.mkdir(parents=True, exist_ok=True)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def extract_title(markdown_text: str, fallback: str) -> str:
    for line in markdown_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return fallback


HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    :root {{ color-scheme: light dark; }}
    body {{
      margin: 0;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.6;
      background: #0f172a;
      color: #e2e8f0;
    }}
    header, main {{ max-width: 960px; margin: 0 auto; padding: 24px; }}
    header {{ border-bottom: 1px solid rgba(148, 163, 184, 0.25); }}
    a {{ color: #7dd3fc; }}
    .muted {{ color: #94a3b8; }}
    .card-grid {{ display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); }}
    .card {{ padding: 16px; border: 1px solid rgba(148, 163, 184, 0.2); border-radius: 12px; background: rgba(15, 23, 42, 0.55); }}
    code {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }}
    pre {{ overflow: auto; padding: 16px; background: rgba(15, 23, 42, 0.8); border-radius: 12px; }}
  </style>
</head>
<body>
  <header>
    <div class="muted">Naruto Card Clash Docs</div>
    <h1>{title}</h1>
  </header>
  <main>
    {content}
  </main>
</body>
</html>
"""


INDEX_TEMPLATE = """<section>
  <p>
    This site serves the original Markdown files directly for easy AI access.
    Use the links below to open each document as <code>.md</code>.
  </p>
</section>
<section class="card-grid">
  {cards}
</section>
"""


def build_docs() -> list[tuple[str, str]]:
    docs_output = SITE_DIR / "docs"
    docs_output.mkdir(parents=True, exist_ok=True)

    generated: list[tuple[str, str]] = []
    for md_file in sorted(DOCS_DIR.glob("*.md")):
        title = extract_title(read_text(md_file), md_file.stem)
        destination = docs_output / md_file.name
        shutil.copy2(md_file, destination)
        generated.append((title, md_file.name))

    cards = "\n  ".join(
        f'<div class="card"><h2><a href="docs/{html.escape(file_name)}">{html.escape(title)}</a></h2>'
        f'<p class="muted">Open the original Markdown file.</p></div>'
        for title, file_name in generated
    )
    index_html = HTML_TEMPLATE.format(
        title="Naruto Card Clash Docs",
        content=INDEX_TEMPLATE.format(cards=cards),
    )
    write_text(SITE_DIR / "index.html", index_html)

    docs_index = HTML_TEMPLATE.format(
        title="Documentation Index",
        content="""
        <p class="muted">Pick a document below.</p>
        <ul>
          {items}
        </ul>
        """.format(
            items="\n          ".join(
                f'<li><a href="{html.escape(file_name)}">{html.escape(title)}</a></li>'
                for title, file_name in generated
            )
        ),
    )
    write_text(docs_output / "index.html", docs_index)

    return generated


def find_app_build_root() -> Path | None:
    if not APP_DIST_DIR.exists():
        return None

    flat_index = APP_DIST_DIR / "index.html"
    if flat_index.exists():
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
    generated_docs = build_docs()
    app_copied = copy_app_build_if_present()

    if not app_copied:
        # Keep a simple landing page when Angular has not been built yet.
        write_text(
            SITE_DIR / "app-placeholder.html",
            HTML_TEMPLATE.format(
                title="Angular app not deployed yet",
                content=(
                    "<p>The Angular build is not present yet. When it is added, "
                    "its files can be copied into the Pages root and this page "
                    "can be replaced by the app.</p>"
                    '<p>Meanwhile, use the docs index: <a href="docs/index.html">docs/index.html</a>.</p>'
                ),
            ),
        )

    print(f"Copied {len(generated_docs)} markdown docs into {SITE_DIR / 'docs'}")
    if app_copied:
        print("Copied Angular build output into site root")
    else:
        print("No Angular build found; published a docs-only site")


if __name__ == "__main__":
    main()
