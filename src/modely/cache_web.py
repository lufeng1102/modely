"""Read-only local web UI for browsing the modely cache."""

from __future__ import annotations

import html
import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .catalog import scan_catalog
from .common import cache
from .files import format_file_size

_DEFAULT_HOST = "127.0.0.1"
_DEFAULT_PORT = 8765


def build_cache_browser_data(cache_dir: str | None = None) -> dict:
    """Build a JSON-ready view model for the cache browser."""
    info = cache.cache_info(cache_dir)
    report = scan_catalog(cache_dir=cache_dir, from_cache=True)
    entries = []
    for entry in sorted(report.entries, key=lambda item: ((item.source or ""), (item.repo_type or ""), (item.repo_id or ""))):
        files = sorted((entry.metadata or {}).get("files") or [], key=lambda item: item.get("size", 0), reverse=True)
        size = entry.size or 0
        entries.append({
            "id": entry.id,
            "source": entry.source or "unknown",
            "repo_type": entry.repo_type or "unknown",
            "repo_id": entry.repo_id or entry.id,
            "revision": entry.revision or "unknown",
            "local_path": entry.local_path,
            "size": size,
            "size_str": format_file_size(size),
            "file_count": entry.file_count,
            "files": files,
            "categories": _file_categories(files),
        })
    return {
        "cache": info,
        "summary": report.summary,
        "entries": entries,
        "filters": {
            "sources": sorted({entry["source"] for entry in entries}),
            "repo_types": sorted({entry["repo_type"] for entry in entries}),
            "revisions": sorted({entry["revision"] for entry in entries}),
        },
        "warnings": report.warnings,
    }


def render_cache_index(data: dict) -> str:
    """Render the cache browser as a self-contained HTML page."""
    entries_html = "\n".join(_render_entry_card(entry) for entry in data.get("entries", []))
    if not entries_html:
        entries_html = "<section class='empty'>No cached repositories found. Run <code>modely-ai get ...</code> first.</section>"
    summary = data.get("summary") or {}
    cache_info = data.get("cache") or {}
    filters = data.get("filters") or {}
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>modely cache browser</title>
  <style>{_CSS}</style>
</head>
<body>
  <header class="hero">
    <div>
      <p class="eyebrow">modely cache</p>
      <h1>Local model and dataset cache</h1>
      <p class="muted">Browse cached assets by source, type, revision, size, and files. This local UI is read-only.</p>
    </div>
    <div class="cache-path" title="{_esc(cache_info.get('cache_dir', ''))}">{_esc(cache_info.get('cache_dir', '-'))}</div>
  </header>
  <main class="layout">
    <aside class="sidebar">
      <div class="stat"><span>Total entries</span><strong>{summary.get('total_entries', 0)}</strong></div>
      <div class="stat"><span>Total size</span><strong>{_esc(format_file_size(summary.get('total_size', 0)))}</strong></div>
      {_render_filter_group('Sources', 'source', filters.get('sources', []))}
      {_render_filter_group('Types', 'repoType', filters.get('repo_types', []))}
      {_render_filter_group('Revisions', 'revision', filters.get('revisions', []))}
      <button id="clear-filters" class="clear-filters" type="button" onclick="clearFilters()" hidden>Clear filters</button>
    </aside>
    <section class="content">
      <div class="toolbar">
        <input id="search" type="search" placeholder="Search cached repos..." oninput="filterCards()">
        <a class="api-link" href="/api/catalog">JSON catalog</a>
      </div>
      <div id="cards" class="cards">{entries_html}</div>
    </section>
  </main>
  <script>{_JS}</script>
</body>
</html>
"""


def serve_cache_browser(
    cache_dir: str | None = None,
    *,
    host: str = _DEFAULT_HOST,
    port: int = _DEFAULT_PORT,
    open_browser: bool = False,
) -> None:
    """Serve the read-only cache browser until interrupted."""
    server = make_cache_browser_server(cache_dir=cache_dir, host=host, port=port)
    url = f"http://{host}:{server.server_port}"
    print(f"Serving modely cache browser at {url}")
    print(f"Cache directory: {cache.cache_info(cache_dir)['cache_dir']}")
    if open_browser:
        threading.Timer(0.2, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping cache browser.")
    finally:
        server.server_close()


def make_cache_browser_server(cache_dir: str | None = None, *, host: str = _DEFAULT_HOST, port: int = _DEFAULT_PORT) -> ThreadingHTTPServer:
    """Create a configured cache browser HTTP server."""

    class CacheBrowserHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
            parsed = urlparse(self.path)
            if parsed.path == "/":
                data = build_cache_browser_data(_cache_dir_from_query(parsed.query, cache_dir))
                self._send_text(render_cache_index(data), "text/html; charset=utf-8")
                return
            if parsed.path in {"/api/catalog", "/api/cache"}:
                data = build_cache_browser_data(_cache_dir_from_query(parsed.query, cache_dir))
                self._send_text(json.dumps(data, indent=2, ensure_ascii=False), "application/json; charset=utf-8")
                return
            self.send_error(404, "Not found")

        def log_message(self, format: str, *args) -> None:  # noqa: A002 - stdlib name
            return

        def _send_text(self, text: str, content_type: str) -> None:
            body = text.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return ThreadingHTTPServer((host, port), CacheBrowserHandler)


def _cache_dir_from_query(query: str, default: str | None) -> str | None:
    values = parse_qs(query).get("cache_dir") or []
    return values[0] if values else default


def _file_categories(files: list[dict]) -> dict:
    categories = {}
    for file_info in files:
        name = (file_info.get("name") or "").lower()
        category = _file_category(name)
        categories[category] = categories.get(category, 0) + 1
    return categories


def _file_category(name: str) -> str:
    if name.startswith("readme") or name.endswith(".md"):
        return "card"
    if name.endswith((".safetensors", ".bin", ".pt", ".pth", ".gguf", ".onnx")):
        return "weights"
    if "tokenizer" in name or name.endswith(("vocab.txt", "merges.txt")):
        return "tokenizer"
    if name.endswith((".json", ".yaml", ".yml")):
        return "metadata"
    return "other"


def _render_filter_group(title: str, kind: str, values: list[str]) -> str:
    if not values:
        return ""
    chips = "".join(
        f"<button class='chip' type='button' data-filter-kind='{_esc(kind)}' "
        f"data-filter-value='{_esc(value)}' onclick='toggleFilter(this)'>{_esc(value)}</button>"
        for value in values
    )
    return f"<div class='filter'><h2>{_esc(title)}</h2><div class='chips'>{chips}</div></div>"


def _render_entry_card(entry: dict) -> str:
    files = entry.get("files") or []
    top_files = "".join(
        f"<li><span>{_esc(file_info.get('name', ''))}</span><em>{_esc(file_info.get('size_str') or format_file_size(file_info.get('size', 0)))}</em></li>"
        for file_info in files[:8]
    )
    if not top_files:
        top_files = "<li><span>No file details</span><em>-</em></li>"
    categories = "".join(f"<span>{_esc(name)} {count}</span>" for name, count in sorted((entry.get("categories") or {}).items()))
    return f"""
<article class="card" data-search="{_esc((entry.get('repo_id') or '').lower())} {_esc(entry.get('source', ''))} {_esc(entry.get('repo_type', ''))}" data-source="{_esc(entry.get('source', 'unknown'))}" data-repo-type="{_esc(entry.get('repo_type', 'unknown'))}" data-revision="{_esc(entry.get('revision', 'unknown'))}">
  <div class="card-head">
    <div>
      <h2>{_esc(entry.get('repo_id', '-'))}</h2>
      <p>{_esc(entry.get('local_path', '-'))}</p>
    </div>
    <div class="badges"><span>{_esc(entry.get('source', 'unknown'))}</span><span>{_esc(entry.get('repo_type', 'unknown'))}</span></div>
  </div>
  <div class="meta">
    <span>Revision <strong>{_esc(entry.get('revision', '-'))}</strong></span>
    <span>Size <strong>{_esc(entry.get('size_str', '-'))}</strong></span>
    <span>Files <strong>{entry.get('file_count', 0)}</strong></span>
  </div>
  <div class="categories">{categories}</div>
  <details>
    <summary>Show files</summary>
    <ul class="files">{top_files}</ul>
  </details>
</article>
"""


def _esc(value) -> str:
    return html.escape(str(value), quote=True)


_CSS = """
:root { color-scheme: light; --bg: #f7f7f4; --panel: #ffffff; --line: #e5e2da; --text: #171717; --muted: #6b665f; --accent: #ff9d00; }
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text); font: 14px/1.5 -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }
.hero { display: flex; justify-content: space-between; gap: 24px; align-items: center; padding: 32px 40px; border-bottom: 1px solid var(--line); background: linear-gradient(135deg, #fff, #fff7e8); }
.eyebrow { margin: 0 0 8px; color: #b66b00; font-weight: 700; text-transform: uppercase; letter-spacing: .08em; }
h1 { margin: 0; font-size: 34px; letter-spacing: -0.03em; }
.muted { color: var(--muted); max-width: 720px; }
.cache-path { max-width: 440px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; border: 1px solid var(--line); border-radius: 999px; padding: 10px 14px; background: #fff; color: var(--muted); }
.layout { display: grid; grid-template-columns: 280px 1fr; gap: 24px; padding: 24px 40px 40px; }
.sidebar { display: flex; flex-direction: column; gap: 16px; }
.stat, .filter, .card { background: var(--panel); border: 1px solid var(--line); border-radius: 18px; box-shadow: 0 1px 2px rgba(0,0,0,.03); }
.stat { padding: 16px; display: flex; justify-content: space-between; align-items: center; }
.stat span { color: var(--muted); }
.stat strong { font-size: 22px; }
.filter { padding: 16px; }
.filter h2 { margin: 0 0 10px; font-size: 13px; color: var(--muted); text-transform: uppercase; letter-spacing: .06em; }
.chips, .badges, .categories { display: flex; flex-wrap: wrap; gap: 8px; }
.chip, .badges span, .categories span { border-radius: 999px; background: #f2f0ea; padding: 5px 9px; color: #514c45; font-size: 12px; }
button.chip { border: 1px solid transparent; cursor: pointer; font: inherit; }
button.chip:hover, button.chip:focus { border-color: var(--accent); outline: none; }
button.chip.active { background: #fff1d6; border-color: var(--accent); color: #7a4a00; font-weight: 650; }
.clear-filters { border: 1px solid var(--line); border-radius: 999px; background: #fff; padding: 8px 12px; color: #7a4a00; cursor: pointer; font-weight: 650; }
.clear-filters[hidden] { display: none; }
.content { min-width: 0; }
.toolbar { display: flex; justify-content: space-between; gap: 16px; margin-bottom: 16px; }
input[type=search] { width: min(520px, 100%); border: 1px solid var(--line); border-radius: 999px; padding: 12px 16px; background: #fff; font: inherit; }
.api-link { align-self: center; color: #7a4a00; text-decoration: none; font-weight: 600; }
.cards { display: grid; gap: 16px; }
.card { padding: 18px; }
.card-head { display: flex; justify-content: space-between; gap: 18px; }
.card h2 { margin: 0; font-size: 20px; }
.card p { margin: 6px 0 0; color: var(--muted); word-break: break-all; }
.meta { display: flex; flex-wrap: wrap; gap: 18px; margin: 16px 0; color: var(--muted); }
.meta strong { color: var(--text); }
details { margin-top: 14px; }
summary { cursor: pointer; font-weight: 650; }
.files { list-style: none; padding: 0; margin: 12px 0 0; border-top: 1px solid var(--line); }
.files li { display: flex; justify-content: space-between; gap: 16px; padding: 8px 0; border-bottom: 1px solid var(--line); }
.files span { word-break: break-all; }
.files em { color: var(--muted); font-style: normal; white-space: nowrap; }
.empty { padding: 32px; background: var(--panel); border: 1px solid var(--line); border-radius: 18px; color: var(--muted); }
@media (max-width: 820px) { .hero, .card-head, .toolbar { flex-direction: column; align-items: stretch; } .layout { grid-template-columns: 1fr; padding: 20px; } .hero { padding: 24px 20px; } }
"""

_JS = """
const activeFilters = { source: new Set(), repoType: new Set(), revision: new Set() };

function toggleFilter(button) {
  const kind = button.dataset.filterKind;
  const value = button.dataset.filterValue;
  if (!activeFilters[kind]) return;
  if (activeFilters[kind].has(value)) {
    activeFilters[kind].delete(value);
    button.classList.remove('active');
  } else {
    activeFilters[kind].add(value);
    button.classList.add('active');
  }
  filterCards();
}

function clearFilters() {
  for (const values of Object.values(activeFilters)) values.clear();
  for (const chip of document.querySelectorAll('button.chip.active')) chip.classList.remove('active');
  filterCards();
}

function filterCards() {
  const query = document.getElementById('search').value.toLowerCase();
  let hasFilters = false;
  for (const values of Object.values(activeFilters)) {
    if (values.size) hasFilters = true;
  }
  for (const card of document.querySelectorAll('.card')) {
    const searchMatch = card.dataset.search.includes(query);
    const filterMatch = matchesFilter(card, 'source') && matchesFilter(card, 'repoType') && matchesFilter(card, 'revision');
    card.style.display = searchMatch && filterMatch ? '' : 'none';
  }
  const clearButton = document.getElementById('clear-filters');
  if (clearButton) clearButton.hidden = !hasFilters;
}

function matchesFilter(card, kind) {
  const values = activeFilters[kind];
  return !values || values.size === 0 || values.has(card.dataset[kind]);
}
"""
