from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import re
from urllib.parse import parse_qs, urlparse

from .amplitude import generate_symbolic_amplitudes
from .core import DiagramGenerationError, generate_diagrams
from .custom_theory import DEFAULT_CUSTOM_THEORY, generate_custom_theory_diagrams
from .render import RenderOptions, render_diagram_svg


HTML_PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>QED Diagram Editor</title>
  <script>
    window.MathJax = {
      tex: {
        inlineMath: [['\\\\(', '\\\\)']],
        displayMath: [['\\\\[', '\\\\]']],
        processEscapes: true
      },
      svg: {
        fontCache: 'global'
      }
    };
  </script>
  <script defer src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js"></script>
  <style>
    :root{
      --ink:#1f2a1f;
      --accent:#8f2d1b;
      --paper:#f7f1e1;
      --panel:#fffdf5;
      --line:#d6c7a3;
      --muted:#4a5647;
      --shadow:0 22px 60px rgba(79,57,18,.08);
    }
    *{box-sizing:border-box}
    body{
      margin:0;
      min-height:100vh;
      font-family:'Trebuchet MS','Segoe UI',sans-serif;
      color:var(--ink);
      background:
        radial-gradient(circle at top left, rgba(143,45,27,.16), transparent 24%),
        radial-gradient(circle at bottom right, rgba(31,42,31,.12), transparent 24%),
        linear-gradient(180deg, #ede2c3 0%, var(--paper) 100%);
    }
    main{max-width:1280px;margin:0 auto;padding:36px 20px 72px}
    h1{
      margin:0 0 12px;
      font:700 clamp(2.4rem,4vw,4.6rem) 'Iowan Old Style','Palatino Linotype','Book Antiqua',Palatino,serif;
      letter-spacing:-.04em;
    }
    .lede{
      max-width:820px;
      margin:0 0 28px;
      color:var(--muted);
      font-size:1.05rem;
      line-height:1.6;
    }
    .shell{
      display:grid;
      grid-template-columns:minmax(300px,360px) minmax(0,1fr);
      gap:22px;
      align-items:start;
    }
    .mode-switch{
      display:flex;
      gap:10px;
      margin:0 0 20px;
    }
    .mode-chip{
      border:1px solid var(--line);
      border-radius:999px;
      padding:10px 14px;
      background:#fff;
      color:var(--muted);
      cursor:pointer;
      font:700 .95rem 'Trebuchet MS','Segoe UI',sans-serif;
    }
    .mode-chip.active{
      background:linear-gradient(135deg, #8f2d1b 0%, #bf5c26 100%);
      color:#fff;
      border-color:#8f2d1b;
    }
    .card{
      border:1px solid var(--line);
      border-radius:28px;
      background:rgba(255,253,245,.92);
      box-shadow:var(--shadow);
      backdrop-filter:blur(10px);
    }
    .controls{padding:24px}
    .controls label{
      display:block;
      margin-bottom:10px;
      font-weight:700;
      letter-spacing:.06em;
      text-transform:uppercase;
      font-size:.76rem;
      color:var(--accent);
    }
    input[type=text], select{
      width:100%;
      padding:14px 16px;
      border-radius:16px;
      border:1px solid var(--line);
      background:#fff;
      font-size:1rem;
      color:var(--ink);
    }
    textarea{
      width:100%;
      min-height:220px;
      padding:14px 16px;
      border-radius:16px;
      border:1px solid var(--line);
      background:#fff;
      font:500 .92rem/1.5 'Cascadia Code','Consolas',monospace;
      color:var(--ink);
      resize:vertical;
    }
    .field{margin-bottom:16px}
    .row{
      display:grid;
      grid-template-columns:repeat(2, minmax(0,1fr));
      gap:12px;
      margin-bottom:18px;
    }
    .toggles{
      display:flex;
      flex-direction:column;
      gap:10px;
      margin:18px 0 20px;
    }
    .toggles label{
      margin:0;
      display:flex;
      gap:10px;
      align-items:center;
      font-weight:600;
      text-transform:none;
      letter-spacing:0;
      color:var(--muted);
      font-size:.95rem;
    }
    button{
      border:0;
      border-radius:16px;
      padding:14px 18px;
      font:700 1rem 'Trebuchet MS','Segoe UI',sans-serif;
      cursor:pointer;
      color:#fff;
      background:linear-gradient(135deg, #8f2d1b 0%, #bf5c26 100%);
      box-shadow:0 10px 22px rgba(143,45,27,.24);
    }
    button:disabled{
      opacity:.45;
      cursor:not-allowed;
      box-shadow:none;
    }
    .ghost{
      background:#fff;
      color:var(--ink);
      border:1px solid var(--line);
      box-shadow:none;
    }
    .examples{
      margin-top:20px;
      display:flex;
      flex-wrap:wrap;
      gap:10px;
    }
    .example{
      border:1px solid var(--line);
      background:#fff;
      color:var(--ink);
      box-shadow:none;
      padding:10px 12px;
      font-size:.92rem;
      border-radius:999px;
    }
    .results{padding:26px}
    .status{
      min-height:24px;
      margin-bottom:14px;
      color:var(--muted);
    }
    .error{
      color:#8a1f1f;
      font-weight:700;
    }
    .notes{
      display:grid;
      gap:10px;
      margin-bottom:18px;
    }
    .note{
      margin:0;
      padding:12px 14px;
      border-radius:16px;
      background:#fbf6e8;
      color:var(--muted);
      line-height:1.5;
      border:1px solid rgba(214,199,163,.75);
    }
    .viewer{
      border:1px solid var(--line);
      border-radius:24px;
      background:#fffdfa;
      padding:20px;
    }
    .viewer-head{
      display:flex;
      justify-content:space-between;
      gap:18px;
      align-items:start;
      margin-bottom:18px;
    }
    .kicker{
      margin:0 0 6px;
      color:var(--accent);
      font:700 .76rem 'Trebuchet MS','Segoe UI',sans-serif;
      letter-spacing:.1em;
      text-transform:uppercase;
    }
    .viewer h2{
      margin:0 0 8px;
      font:700 1.9rem 'Iowan Old Style','Palatino Linotype','Book Antiqua',Palatino,serif;
    }
    .viewer p{
      margin:0;
      color:var(--muted);
      line-height:1.5;
      max-width:760px;
    }
    .carousel-nav{
      display:flex;
      gap:10px;
      flex-shrink:0;
    }
    .stage-wrap{
      padding:14px;
      border-radius:26px;
      background:
        radial-gradient(circle at top left, rgba(143,45,27,.08), transparent 26%),
        linear-gradient(180deg, #f7efd9 0%, #fbf7ea 100%);
      border:1px solid rgba(214,199,163,.75);
    }
    .stage{
      min-height:520px;
      display:flex;
      align-items:center;
      justify-content:center;
    }
    .stage svg{
      max-width:100%;
      height:auto;
      display:block;
    }
    .actions{
      margin-top:16px;
      display:flex;
      justify-content:space-between;
      gap:12px;
      align-items:center;
      flex-wrap:wrap;
    }
    .counter{
      color:var(--muted);
      font-size:.95rem;
      font-weight:600;
    }
    .formula-block{
      margin-top:18px;
      padding:16px 18px;
      border-radius:18px;
      background:#f8f2e2;
      border:1px solid rgba(214,199,163,.85);
    }
    .formula-block h3{
      margin:0 0 10px;
      font:700 1.05rem 'Trebuchet MS','Segoe UI',sans-serif;
      color:var(--accent);
      letter-spacing:.04em;
      text-transform:uppercase;
    }
    .formula-math{
      margin:0;
      min-height:2.2rem;
      color:var(--ink);
      overflow-x:auto;
      overflow-y:hidden;
    }
    .formula-math mjx-container{
      margin:0 !important;
    }
    .formula-raw{
      margin-top:12px;
    }
    .formula-raw summary{
      cursor:pointer;
      color:var(--muted);
      font:600 .9rem 'Trebuchet MS','Segoe UI',sans-serif;
    }
    .formula-raw pre{
      margin:10px 0 0;
      white-space:pre-wrap;
      word-break:break-word;
      font:500 .9rem/1.6 'Cascadia Code','Consolas',monospace;
      color:var(--ink);
    }
    .hidden{display:none !important}
    @media (max-width: 980px){
      .shell{grid-template-columns:1fr}
      .row{grid-template-columns:1fr}
      .viewer-head{flex-direction:column}
      .stage{min-height:0}
    }
  </style>
</head>
<body>
  <main>
    <h1>QED Diagram Editor</h1>
    <p class="lede">
      Generate lowest-order and selected one-loop QED diagrams, or switch to a custom-theory mode where you define particles and 3-point vertices yourself.
      The viewer keeps one large stage active at a time so the diagram can breathe instead of being squeezed into a stacked list.
    </p>
    <div class="mode-switch" role="tablist" aria-label="Theory mode">
      <button class="mode-chip active" type="button" id="mode-qed" data-mode="qed">QED</button>
      <button class="mode-chip" type="button" id="mode-custom" data-mode="custom">Custom theory</button>
    </div>
    <section class="shell">
      <form class="card controls" id="controls">
        <div class="field">
          <label for="reaction">Reaction</label>
          <input id="reaction" name="reaction" type="text" value="e- + e+ -> mu- + mu+" spellcheck="false">
        </div>
        <div class="row" id="qed-config">
          <div class="field">
            <label for="order">Perturbative order</label>
            <select id="order" name="order">
              <option value="tree">Tree level</option>
              <option value="one-loop">One loop</option>
            </select>
          </div>
          <div class="field">
            <label for="layout">Layout</label>
            <select id="layout" name="layout">
              <option value="roomy">Roomy</option>
              <option value="compact">Compact</option>
            </select>
          </div>
        </div>
        <div class="toggles">
          <label><input id="show-momenta" type="checkbox" checked> Show momentum labels</label>
          <label><input id="show-leg-ids" type="checkbox"> Show leg ids</label>
          <label><input id="show-rule-highlights" type="checkbox"> Highlight rule sources on amplitudes</label>
        </div>
        <div class="field hidden" id="custom-theory-field">
          <label for="custom-theory">Theory definition</label>
          <textarea id="custom-theory" spellcheck="false">__CUSTOM_THEORY__</textarea>
        </div>
        <button type="submit">Generate diagrams</button>
        <div class="examples" id="qed-examples">
          <button class="example" type="button" data-mode="qed" data-reaction="e- + mu- -> e- + mu-" data-order="tree">e- + mu- -&gt; e- + mu-</button>
          <button class="example" type="button" data-mode="qed" data-reaction="e- + e+ -> e- + e+" data-order="one-loop">e- + e+ -&gt; e- + e+ (loop)</button>
          <button class="example" type="button" data-mode="qed" data-reaction="e- + gamma -> e- + gamma" data-order="tree">e- + gamma -&gt; e- + gamma</button>
          <button class="example" type="button" data-mode="qed" data-reaction="e- + e+ -> gamma + gamma" data-order="tree">e- + e+ -&gt; gamma + gamma</button>
        </div>
        <div class="examples hidden" id="custom-examples">
          <button class="example" type="button" data-mode="custom" data-reaction="e+ + e- -> 2phi">e+ + e- -&gt; 2phi</button>
        </div>
      </form>
      <section class="card results">
        <div class="status" id="status">Enter a supported QED reaction and choose the order you want to inspect.</div>
        <div class="notes" id="notes"></div>
        <section class="viewer" id="viewer" hidden>
          <div class="viewer-head">
            <div>
              <p class="kicker" id="diagram-kicker"></p>
              <h2 id="diagram-title"></h2>
              <p id="diagram-description"></p>
            </div>
            <div class="carousel-nav">
              <button class="ghost" type="button" id="prev-button">Previous</button>
              <button class="ghost" type="button" id="next-button">Next</button>
            </div>
          </div>
          <div class="stage-wrap">
            <div class="stage" id="stage"></div>
          </div>
          <div class="actions">
            <div class="counter" id="diagram-counter"></div>
            <button class="ghost" type="button" id="download-button">Download SVG</button>
          </div>
          <div class="formula-block" id="diagram-amplitude-block">
            <h3>Diagram amplitude</h3>
            <div class="formula-math" id="diagram-amplitude"></div>
            <details class="formula-raw">
              <summary>Show raw LaTeX</summary>
              <pre id="diagram-amplitude-raw"></pre>
            </details>
          </div>
          <div class="formula-block" id="total-amplitude-block">
            <h3>Total amplitude</h3>
            <div class="formula-math" id="total-amplitude"></div>
            <details class="formula-raw">
              <summary>Show raw LaTeX</summary>
              <pre id="total-amplitude-raw"></pre>
            </details>
          </div>
        </section>
      </section>
    </section>
  </main>
  <script>
    const controls = document.getElementById("controls");
    const modeQedButton = document.getElementById("mode-qed");
    const modeCustomButton = document.getElementById("mode-custom");
    const reactionInput = document.getElementById("reaction");
    const orderInput = document.getElementById("order");
    const layoutInput = document.getElementById("layout");
    const momentaInput = document.getElementById("show-momenta");
    const legIdsInput = document.getElementById("show-leg-ids");
    const ruleHighlightsInput = document.getElementById("show-rule-highlights");
    const customTheoryFieldEl = document.getElementById("custom-theory-field");
    const customTheoryInput = document.getElementById("custom-theory");
    const qedConfigEl = document.getElementById("qed-config");
    const qedExamplesEl = document.getElementById("qed-examples");
    const customExamplesEl = document.getElementById("custom-examples");
    const statusEl = document.getElementById("status");
    const notesEl = document.getElementById("notes");
    const viewerEl = document.getElementById("viewer");
    const diagramKickerEl = document.getElementById("diagram-kicker");
    const diagramTitleEl = document.getElementById("diagram-title");
    const diagramDescriptionEl = document.getElementById("diagram-description");
    const diagramCounterEl = document.getElementById("diagram-counter");
    const stageEl = document.getElementById("stage");
    const prevButton = document.getElementById("prev-button");
    const nextButton = document.getElementById("next-button");
    const downloadButton = document.getElementById("download-button");
    const diagramAmplitudeEl = document.getElementById("diagram-amplitude");
    const totalAmplitudeEl = document.getElementById("total-amplitude");
    const diagramAmplitudeRawEl = document.getElementById("diagram-amplitude-raw");
    const totalAmplitudeRawEl = document.getElementById("total-amplitude-raw");
    const diagramAmplitudeBlockEl = document.getElementById("diagram-amplitude-block");
    const totalAmplitudeBlockEl = document.getElementById("total-amplitude-block");

    let currentPayload = null;
    let currentIndex = 0;
    let currentMode = "qed";

    function setStatus(message, isError=false){
      statusEl.textContent = message;
      statusEl.className = isError ? "status error" : "status";
    }

    function renderNotes(notes){
      notesEl.innerHTML = "";
      notes.forEach((note) => {
        const p = document.createElement("p");
        p.className = "note";
        p.textContent = note;
        notesEl.appendChild(p);
      });
    }

    function escapeHtml(value){
      return value
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;");
    }

    function setFormula(target, rawTarget, latex, fallbackMessage){
      const hasLatex = Boolean(latex && latex.trim());
      const content = hasLatex ? latex : fallbackMessage;
      rawTarget.textContent = content;
      target.innerHTML = hasLatex ? `\\\\[${escapeHtml(content)}\\\\]` : `<p>${escapeHtml(content)}</p>`;
    }

    function typesetMath(){
      if(window.MathJax && window.MathJax.typesetPromise){
        window.MathJax.typesetClear?.();
        return window.MathJax.typesetPromise();
      }
      return Promise.resolve();
    }

    function renderDiagram(index){
      if(!currentPayload || !currentPayload.diagrams.length){
        viewerEl.hidden = true;
        return;
      }
      currentIndex = index;
      const diagram = currentPayload.diagrams[currentIndex];
      viewerEl.hidden = false;
      diagramKickerEl.textContent = `${currentPayload.order} order`;
      diagramTitleEl.textContent = diagram.title;
      diagramDescriptionEl.textContent = diagram.description;
      diagramCounterEl.textContent = `Diagram ${currentIndex + 1} of ${currentPayload.diagrams.length}`;
      stageEl.innerHTML = diagram.svg;
      const diagramFormula = ruleHighlightsInput.checked ? (diagram.annotated_amplitude || diagram.amplitude) : diagram.amplitude;
      const totalFormula = ruleHighlightsInput.checked ? (currentPayload.total_annotated_amplitude || currentPayload.total_amplitude) : currentPayload.total_amplitude;
      const showAmplitudeBlocks = Boolean((diagram.amplitude && diagram.amplitude.trim()) || (currentPayload.total_amplitude && currentPayload.total_amplitude.trim()));
      diagramAmplitudeBlockEl.classList.toggle("hidden", !showAmplitudeBlocks);
      totalAmplitudeBlockEl.classList.toggle("hidden", !showAmplitudeBlocks);
      setFormula(
        diagramAmplitudeEl,
        diagramAmplitudeRawEl,
        diagramFormula,
        "Symbolic amplitude unavailable for this selection."
      );
      setFormula(
        totalAmplitudeEl,
        totalAmplitudeRawEl,
        totalFormula,
        "Total amplitude unavailable for this selection."
      );
      prevButton.disabled = currentPayload.diagrams.length === 1;
      nextButton.disabled = currentPayload.diagrams.length === 1;
      downloadButton.onclick = () => {
        const blob = new Blob([diagram.svg], {type: "image/svg+xml"});
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = diagram.filename;
        link.click();
        URL.revokeObjectURL(url);
      };
      typesetMath();
    }

    function setMode(mode){
      currentMode = mode;
      const custom = mode === "custom";
      modeQedButton.classList.toggle("active", !custom);
      modeCustomButton.classList.toggle("active", custom);
      customTheoryFieldEl.classList.toggle("hidden", !custom);
      qedConfigEl.classList.toggle("hidden", custom);
      qedExamplesEl.classList.toggle("hidden", custom);
      customExamplesEl.classList.toggle("hidden", !custom);
      ruleHighlightsInput.parentElement.classList.toggle("hidden", custom);
      if(custom){
        orderInput.value = "tree";
        reactionInput.value = "e+ + e- -> 2phi";
      } else if (reactionInput.value === "e+ + e- -> 2phi") {
        reactionInput.value = "e- + e+ -> mu- + mu+";
      }
    }

    function renderResponse(payload){
      currentPayload = payload;
      renderNotes(payload.notes);
      renderDiagram(0);
      setStatus(`Generated ${payload.diagrams.length} diagram${payload.diagrams.length === 1 ? "" : "s"} for ${payload.reaction} at ${payload.order} order.`);
    }

    async function generate(){
      const params = new URLSearchParams({
        mode: currentMode,
        reaction: reactionInput.value,
        order: orderInput.value,
        compact: layoutInput.value === "compact" ? "1" : "0",
        show_leg_ids: legIdsInput.checked ? "1" : "0",
        show_momenta: momentaInput.checked ? "1" : "0"
      });
      if(currentMode === "custom"){
        params.set("theory", customTheoryInput.value);
      }
      setStatus("Generating...");
      notesEl.innerHTML = "";
      viewerEl.hidden = true;
      stageEl.innerHTML = "";
      const response = await fetch(`/api/generate?${params.toString()}`);
      const payload = await response.json();
      if(!response.ok){
        currentPayload = null;
        setStatus(payload.error, true);
        return;
      }
      renderResponse(payload);
    }

    controls.addEventListener("submit", (event) => {
      event.preventDefault();
      generate();
    });

    prevButton.addEventListener("click", () => {
      if(!currentPayload){ return; }
      renderDiagram((currentIndex - 1 + currentPayload.diagrams.length) % currentPayload.diagrams.length);
    });

    nextButton.addEventListener("click", () => {
      if(!currentPayload){ return; }
      renderDiagram((currentIndex + 1) % currentPayload.diagrams.length);
    });

    ruleHighlightsInput.addEventListener("change", () => {
      if(currentPayload){
        renderDiagram(currentIndex);
      }
    });

    document.querySelectorAll(".example").forEach((button) => {
      button.addEventListener("click", () => {
        setMode(button.dataset.mode || "qed");
        reactionInput.value = button.dataset.reaction;
        orderInput.value = button.dataset.order || "tree";
        generate();
      });
    });

    modeQedButton.addEventListener("click", () => setMode("qed"));
    modeCustomButton.addEventListener("click", () => setMode("custom"));
  </script>
</body>
</html>
"""
HTML_PAGE = HTML_PAGE.replace("__CUSTOM_THEORY__", DEFAULT_CUSTOM_THEORY)


class DiagramHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send_html(HTML_PAGE)
            return
        if parsed.path == "/api/generate":
            self._handle_generate(parsed.query)
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def log_message(self, format: str, *args) -> None:
        return

    def _handle_generate(self, query: str) -> None:
        params = parse_qs(query)
        mode = params.get("mode", ["qed"])[0]
        reaction = params.get("reaction", [""])[0]
        order = params.get("order", ["tree"])[0]
        compact = params.get("compact", ["0"])[0] == "1"
        show_leg_ids = params.get("show_leg_ids", ["0"])[0] == "1"
        show_momenta = params.get("show_momenta", ["1"])[0] == "1"
        theory_text = params.get("theory", [DEFAULT_CUSTOM_THEORY])[0]

        try:
            if mode == "custom":
                theory, bundle = generate_custom_theory_diagrams(theory_text, reaction)
                amplitude = None
            else:
                theory = None
                bundle = generate_diagrams(reaction, order=order)
                amplitude = generate_symbolic_amplitudes(reaction, order="tree") if order == "tree" else None
            options = RenderOptions(
                compact=compact,
                show_leg_ids=show_leg_ids,
                show_momenta=show_momenta,
            )
            payload = {
                "mode": mode,
                "reaction": bundle.reaction.raw,
                "order": bundle.order,
                "theory_name": theory.name if theory else "QED",
                "notes": list(bundle.notes),
                "total_amplitude": amplitude.total_expression if amplitude else "",
                "total_annotated_amplitude": amplitude.total_annotated_expression if amplitude else "",
                "diagrams": [
                    {
                        "index": diagram.index,
                        "title": diagram.title,
                        "description": diagram.description,
                        "filename": _diagram_filename(bundle.reaction.raw, diagram.index, diagram.title),
                        "amplitude": (
                            next(term.expression for term in amplitude.terms if term.index == diagram.index)
                            if amplitude
                            else ""
                        ),
                        "annotated_amplitude": (
                            next(term.annotated_expression for term in amplitude.terms if term.index == diagram.index)
                            if amplitude
                            else ""
                        ),
                        "svg": render_diagram_svg(bundle, diagram, options),
                    }
                    for diagram in bundle.diagrams
                ],
            }
            self._send_json(payload)
        except DiagramGenerationError as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

    def _send_html(self, content: str) -> None:
        encoded = content.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    server = ThreadingHTTPServer((host, port), DiagramHandler)
    print(f"Serving QED Diagram Editor on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def _diagram_filename(reaction: str, index: int, title: str) -> str:
    safe_reaction = re.sub(r"-{2,}", "-", "".join(ch if ch.isalnum() else "-" for ch in reaction.lower())).strip("-")
    safe_title = re.sub(r"-{2,}", "-", "".join(ch if ch.isalnum() else "-" for ch in title.lower())).strip("-")
    return f"{safe_reaction}-{index}-{safe_title}.svg"
