from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from resolver import resolve


HTML = r"""<!doctype html>
<html lang="tr">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>NACE Halk Dili Resolver</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f6f7f9;
      --panel: #ffffff;
      --text: #17202a;
      --muted: #667085;
      --line: #d8dee8;
      --accent: #155eef;
      --accent-soft: #e7efff;
      --ok: #067647;
      --warn: #b54708;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--text);
      background: var(--bg);
    }
    main {
      width: min(1080px, calc(100% - 32px));
      margin: 36px auto;
    }
    header {
      display: flex;
      justify-content: space-between;
      gap: 24px;
      align-items: flex-start;
      margin-bottom: 24px;
    }
    h1 {
      font-size: 30px;
      line-height: 1.15;
      margin: 0 0 8px;
      letter-spacing: 0;
    }
    .subtitle {
      margin: 0;
      color: var(--muted);
      max-width: 720px;
      line-height: 1.5;
    }
    .badge {
      border: 1px solid var(--line);
      background: var(--panel);
      border-radius: 8px;
      padding: 8px 10px;
      color: var(--muted);
      white-space: nowrap;
      font-size: 13px;
    }
    .search {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px;
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 12px;
      box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);
    }
    input {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px 14px;
      font-size: 17px;
      outline: none;
    }
    input:focus {
      border-color: var(--accent);
      box-shadow: 0 0 0 3px var(--accent-soft);
    }
    button {
      border: 0;
      border-radius: 8px;
      background: var(--accent);
      color: white;
      padding: 0 22px;
      font-weight: 650;
      font-size: 15px;
      cursor: pointer;
    }
    button:disabled {
      cursor: wait;
      opacity: .65;
    }
    .examples {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin: 14px 0 26px;
    }
    .chip {
      border: 1px solid var(--line);
      background: #fff;
      color: #344054;
      border-radius: 999px;
      padding: 7px 10px;
      font-size: 13px;
      cursor: pointer;
    }
    .layout {
      display: grid;
      grid-template-columns: 1.6fr .9fr;
      gap: 18px;
      align-items: start;
    }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
    }
    .panel h2 {
      margin: 0;
      padding: 14px 16px;
      font-size: 16px;
      border-bottom: 1px solid var(--line);
    }
    .empty {
      color: var(--muted);
      padding: 28px 16px;
      line-height: 1.5;
    }
    .candidate {
      padding: 16px;
      border-bottom: 1px solid var(--line);
      display: grid;
      gap: 10px;
    }
    .candidate:last-child { border-bottom: 0; }
    .topline {
      display: flex;
      gap: 10px;
      justify-content: space-between;
      align-items: start;
    }
    .code {
      font-size: 20px;
      font-weight: 760;
    }
    .label {
      color: #344054;
      line-height: 1.45;
    }
    .meta {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }
    .pill {
      border-radius: 999px;
      padding: 5px 9px;
      background: #f2f4f7;
      color: #344054;
      font-size: 12px;
      font-weight: 620;
    }
    .pill.bucket { background: #ecfdf3; color: var(--ok); }
    .pill.llm { background: #fff6e5; color: var(--warn); }
    .score {
      min-width: 74px;
      text-align: right;
      color: var(--muted);
      font-size: 13px;
    }
    .meter {
      height: 7px;
      width: 74px;
      border-radius: 999px;
      background: #eef2f6;
      overflow: hidden;
      margin-top: 6px;
    }
    .bar {
      height: 100%;
      background: var(--accent);
    }
    .side {
      padding: 16px;
      display: grid;
      gap: 14px;
      color: #344054;
      line-height: 1.45;
    }
    .side strong { color: var(--text); }
    .error {
      color: #b42318;
      padding: 16px;
    }
    @media (max-width: 780px) {
      header, .layout { display: block; }
      .badge { display: inline-block; margin-top: 14px; }
      .search { grid-template-columns: 1fr; }
      button { height: 48px; }
      .panel + .panel { margin-top: 18px; }
    }
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <h1>NACE halk dili resolver</h1>
        <p class="subtitle">Türkçe serbest iş tanımını resmi NACE Rev 2.1 adaylarına ve kaba sektör kovasına eşler. Demo mevcut `resolver.py` fonksiyonunu kullanır.</p>
      </div>
      <div class="badge">local demo · cached LLM fallback</div>
    </header>

    <form class="search" id="form">
      <input id="query" name="q" autocomplete="off" placeholder="Örn. oto galericisiyim" value="oto galericisiyim" />
      <button id="submit" type="submit">Çözümle</button>
    </form>

    <div class="examples" id="examples">
      <span class="chip">bakkalım</span>
      <span class="chip">nalburum</span>
      <span class="chip">kuafor</span>
      <span class="chip">drone ile düğün çekiyorum</span>
      <span class="chip">evden pasta yapıp satıyorum</span>
      <span class="chip">servisçi</span>
    </div>

    <section class="layout">
      <div class="panel">
        <h2>Top NACE adayları</h2>
        <div id="results" class="empty">Bir ifade yazıp çözümleyin.</div>
      </div>
      <aside class="panel">
        <h2>Nasıl okunur?</h2>
        <div class="side">
          <div><strong>exact</strong>: normalize edilmiş alias birebir eşleşti.</div>
          <div><strong>fuzzy</strong>: alias/NACE metni üzerinde RapidFuzz benzerliği.</div>
          <div><strong>llm</strong>: sadece gerçek NACE shortlist içinden seçim yapan cached fallback.</div>
          <div>Skor yüksek ve ikinci adaydan açık ara öndeyse otomatik atama düşünülebilir; aksi halde top-3 gösterilir.</div>
        </div>
      </aside>
    </section>
  </main>

  <script>
    const form = document.getElementById("form");
    const input = document.getElementById("query");
    const button = document.getElementById("submit");
    const results = document.getElementById("results");

    function escapeHtml(value) {
      return String(value).replace(/[&<>"']/g, c => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
      }[c]));
    }

    function render(items) {
      if (!items.length) {
        results.className = "empty";
        results.textContent = "Aday bulunamadı.";
        return;
      }
      results.className = "";
      results.innerHTML = items.map((item, idx) => {
        const pct = Math.max(0, Math.min(100, Math.round(item.score * 100)));
        const matchClass = item.match_type === "llm" ? "pill llm" : "pill";
        return `
          <article class="candidate">
            <div class="topline">
              <div>
                <div class="code">${idx + 1}. ${escapeHtml(item.nace_code)}</div>
                <div class="label">${escapeHtml(item.nace_label)}</div>
              </div>
              <div class="score">
                ${pct}%
                <div class="meter"><div class="bar" style="width:${pct}%"></div></div>
              </div>
            </div>
            <div class="meta">
              <span class="pill bucket">${escapeHtml(item.bucket)}</span>
              <span class="${matchClass}">${escapeHtml(item.match_type)}</span>
            </div>
          </article>
        `;
      }).join("");
    }

    async function resolveQuery(value) {
      const q = value.trim();
      if (!q) return;
      button.disabled = true;
      button.textContent = "Çözülüyor";
      results.className = "empty";
      results.textContent = "Adaylar hesaplanıyor...";
      try {
        const response = await fetch(`/api/resolve?q=${encodeURIComponent(q)}`);
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.error || "İstek başarısız");
        render(payload.candidates || []);
      } catch (err) {
        results.className = "error";
        results.textContent = err.message;
      } finally {
        button.disabled = false;
        button.textContent = "Çözümle";
      }
    }

    form.addEventListener("submit", event => {
      event.preventDefault();
      resolveQuery(input.value);
    });

    document.getElementById("examples").addEventListener("click", event => {
      if (!event.target.classList.contains("chip")) return;
      input.value = event.target.textContent;
      resolveQuery(input.value);
    });

    resolveQuery(input.value);
  </script>
</body>
</html>
"""


class DemoHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send(200, HTML.encode("utf-8"), "text/html; charset=utf-8")
            return
        if parsed.path == "/api/resolve":
            query = parse_qs(parsed.query).get("q", [""])[0]
            try:
                candidates = [asdict(c) for c in resolve(query, k=3)]
                payload = {"query": query, "candidates": candidates}
                self._send_json(200, payload)
            except Exception as exc:
                self._send_json(500, {"error": str(exc)})
            return
        self._send_json(404, {"error": "not found"})

    def log_message(self, fmt: str, *args) -> None:
        print(f"{self.address_string()} - {fmt % args}")

    def _send_json(self, status: int, payload: dict) -> None:
        self._send(status, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    parser = argparse.ArgumentParser(description="Local demo UI for the NACE resolver")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), DemoHandler)
    url = f"http://{args.host}:{args.port}"
    print(f"Demo UI running at {url}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
