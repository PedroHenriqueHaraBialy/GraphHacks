"use strict";

// Edite esta lista para combinar com os nomes de servicos do seu grafo.
const EXEMPLOS = [
  { texto: "O que quebra se o servico pagamentos cair? Quem devo acionar?", agir: false },
  { texto: "E se o banco-de-dados cair?", agir: false },
  { texto: "Registre um incidente de gravidade alta no servico pagamentos: timeout no gateway. Atribua a quem ja resolveu incidentes la.", agir: true },
];

const COR_NOS = { servico: "Serviço", equipe: "Equipe", pessoa: "Pessoa", incidente: "Incidente" };

// ---------- Markdown minimo (escapa HTML antes de formatar) ----------
function esc(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
function inline(s) {
  return esc(s)
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
}
function splitRow(line) {
  const cells = line.trim().split("|").map((c) => c.trim());
  if (cells[0] === "") cells.shift();
  if (cells.length && cells[cells.length - 1] === "") cells.pop();
  return cells;
}
const SEP = /^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$/;

function renderMarkdown(md) {
  const lines = String(md).split(/\r?\n/);
  const out = [];
  let i = 0;
  const tabela = (k) => /^\s*\|/.test(lines[k] || "") && SEP.test(lines[k + 1] || "");
  const especial = (k) =>
    /^\s*$/.test(lines[k]) || /^#{1,4}\s/.test(lines[k]) || /^\s*[-*]\s+/.test(lines[k]) ||
    /^\s*\d+[.)]\s+/.test(lines[k]) || tabela(k);

  while (i < lines.length) {
    const line = lines[i];
    if (/^\s*$/.test(line)) { i++; continue; }

    let m = line.match(/^(#{1,4})\s+(.*)$/);
    if (m) {
      const lv = Math.min(m[1].length + 2, 5);
      out.push(`<h${lv}>${inline(m[2])}</h${lv}>`);
      i++; continue;
    }
    if (tabela(i)) {
      const head = splitRow(lines[i]);
      i += 2;
      const rows = [];
      while (i < lines.length && /^\s*\|/.test(lines[i])) { rows.push(splitRow(lines[i])); i++; }
      out.push(
        '<div class="table-wrap"><table><thead><tr>' +
        head.map((h) => `<th>${inline(h)}</th>`).join("") +
        "</tr></thead><tbody>" +
        rows.map((r) => "<tr>" + r.map((c) => `<td>${inline(c)}</td>`).join("") + "</tr>").join("") +
        "</tbody></table></div>"
      );
      continue;
    }
    if (/^\s*[-*]\s+/.test(line)) {
      const itens = [];
      while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) {
        itens.push(`<li>${inline(lines[i].replace(/^\s*[-*]\s+/, ""))}</li>`); i++;
      }
      out.push(`<ul>${itens.join("")}</ul>`); continue;
    }
    if (/^\s*\d+[.)]\s+/.test(line)) {
      const itens = [];
      while (i < lines.length && /^\s*\d+[.)]\s+/.test(lines[i])) {
        itens.push(`<li>${inline(lines[i].replace(/^\s*\d+[.)]\s+/, ""))}</li>`); i++;
      }
      out.push(`<ol>${itens.join("")}</ol>`); continue;
    }
    const par = [];
    while (i < lines.length && !especial(i)) { par.push(inline(lines[i])); i++; }
    if (!par.length) { par.push(inline(line)); i++; }
    out.push(`<p>${par.join("<br>")}</p>`);
  }
  return out.join("\n");
}

// ---------- Layout do grafo (forcas + separacao de rotulos, deterministico) ----------
// Tamanho do "bloco" de cada no (circulo + rotulo), usado para evitar sobreposicao.
function geometria(nodes) {
  const n = nodes.length, denso = n > 20;
  const fonte = denso ? 12 : 13, lim = denso ? 16 : 20;
  const maior = Math.max(1, ...nodes.map((x) => Math.min(String(x.label).length, lim)));
  return {
    denso, fonte, lim,
    ax: Math.min(150, Math.max(90, maior * fonte * 0.56)),  // largura do bloco
    ay: denso ? 52 : 58,                                    // altura do bloco
  };
}

function separar(nodes, W, H, ax, ay) {
  const m = 50;
  for (let rodada = 0; rodada < 200; rodada++) {
    let mexeu = false;
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const a = nodes[i], b = nodes[j];
        let dx = b.x - a.x, dy = b.y - a.y;
        if (dx === 0 && dy === 0) { dx = 0.01 * (i + 1); dy = 0.01; }
        const nx = dx / ax, ny = dy / ay, d = Math.hypot(nx, ny);
        if (d < 1) {
          const f = (1 - d) / d / 2;
          a.x -= nx * f * ax; a.y -= ny * f * ay;
          b.x += nx * f * ax; b.y += ny * f * ay;
          mexeu = true;
        }
      }
    }
    for (const nd of nodes) {
      nd.x = Math.max(m, Math.min(W - m, nd.x));
      nd.y = Math.max(m, Math.min(H - m, nd.y));
    }
    if (!mexeu) break;
  }
}

function layout(nodes, edges, W, H, iteracoes = 320, geo = null) {
  const n = nodes.length;
  if (n === 0) return;
  if (n === 1) { nodes[0].x = W / 2; nodes[0].y = H / 2; return; }
  const r0 = Math.min(W, H) / 3;
  nodes.forEach((nd, i) => {
    const a = (2 * Math.PI * i) / n;
    nd.x = W / 2 + Math.cos(a) * r0;
    nd.y = H / 2 + Math.sin(a) * r0;
    nd.vx = 0; nd.vy = 0;
  });
  const porId = new Map(nodes.map((nd) => [nd.id, nd]));
  const ligacoes = edges.map((e) => [porId.get(e.source), porId.get(e.target)]).filter(([a, b]) => a && b);
  const repulsao = 14000, mola = 0.02, repouso = 140, gravidade = 0.012;

  for (let it = 0; it < iteracoes; it++) {
    const t = 1 - it / iteracoes;
    for (let i = 0; i < n; i++) {
      for (let j = i + 1; j < n; j++) {
        const a = nodes[i], b = nodes[j];
        let dx = a.x - b.x, dy = a.y - b.y;
        const d2 = dx * dx + dy * dy + 0.01, d = Math.sqrt(d2);
        const f = repulsao / d2;
        dx /= d; dy /= d;
        a.vx += dx * f; a.vy += dy * f; b.vx -= dx * f; b.vy -= dy * f;
      }
    }
    for (const [a, b] of ligacoes) {
      let dx = b.x - a.x, dy = b.y - a.y;
      const d = Math.sqrt(dx * dx + dy * dy) + 0.01;
      const f = (d - repouso) * mola;
      dx /= d; dy /= d;
      a.vx += dx * f; a.vy += dy * f; b.vx -= dx * f; b.vy -= dy * f;
    }
    for (const nd of nodes) {
      nd.vx += (W / 2 - nd.x) * gravidade;
      nd.vy += (H / 2 - nd.y) * gravidade;
      const passo = 0.85 * (0.15 + t);
      nd.x += Math.max(-30, Math.min(30, nd.vx * passo));
      nd.y += Math.max(-30, Math.min(30, nd.vy * passo));
      nd.vx *= 0.6; nd.vy *= 0.6;
    }
  }
  const g = geo || geometria(nodes);
  separar(nodes, W, H, g.ax, g.ay);
}

if (typeof module !== "undefined") module.exports = { renderMarkdown, layout, geometria };

// ---------- Interface (so no navegador) ----------
if (typeof document !== "undefined") {
  const $ = (id) => document.getElementById(id);
  const SVG = "http://www.w3.org/2000/svg";
  const svgEl = (tag, attrs = {}) => {
    const el = document.createElementNS(SVG, tag);
    for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
    return el;
  };
  const el = (tag, props = {}, ...filhos) => {
    const e = document.createElement(tag);
    Object.assign(e, props);
    filhos.forEach((f) => e.append(f));
    return e;
  };

  function desenharGrafo(grafo) {
    const alvo = $("grafo"), legenda = $("legenda");
    alvo.innerHTML = ""; legenda.innerHTML = "";
    if (!grafo || !grafo.nodes || !grafo.nodes.length) {
      alvo.append(el("span", { className: "placeholder", textContent: "Esta pergunta não percorreu relações do grafo." }));
      return;
    }
    const nodes = grafo.nodes.map((n) => ({ ...n }));
    const edges = grafo.edges.map((e) => ({ ...e }));
    const geo = geometria(nodes);
    const W = 900, H = Math.min(1300, 520 + Math.max(0, nodes.length - 12) * 30);
    layout(nodes, edges, W, H, 320, geo);
    const porId = new Map(nodes.map((n) => [n.id, n]));
    const raio = (n) => (n.foco ? 26 : geo.denso ? 15 : 20);
    const comRotulos = edges.length <= 14;  // com muitas setas, o nome da relacao fica no mouse (tooltip)

    const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Subgrafo consultado no FalkorDB" });
    const defs = svgEl("defs");
    const marker = svgEl("marker", { id: "seta", viewBox: "0 0 10 10", refX: "8", refY: "5", markerWidth: "7", markerHeight: "7", orient: "auto-start-reverse" });
    marker.append(svgEl("path", { d: "M0,0 L10,5 L0,10 z", fill: "#7d889c" }));
    defs.append(marker); svg.append(defs);

    const itensAresta = [], itensNo = [];
    for (const e of edges) {
      const a = porId.get(e.source), b = porId.get(e.target);
      if (!a || !b) continue;
      const dx = b.x - a.x, dy = b.y - a.y, d = Math.sqrt(dx * dx + dy * dy) || 1;
      const ux = dx / d, uy = dy / d;
      const x1 = a.x + ux * (raio(a) + 3), y1 = a.y + uy * (raio(a) + 3);
      const x2 = b.x - ux * (raio(b) + 6), y2 = b.y - uy * (raio(b) + 6);
      const g = svgEl("g", { class: "aresta" });
      const linha = svgEl("line", { x1, y1, x2, y2, class: "edge" + (e.novo ? " novo" : ""), "marker-end": "url(#seta)" });
      const tip = svgEl("title"); tip.textContent = e.label || e.rel;
      linha.append(tip); g.append(linha);
      if (comRotulos) {
        const t = svgEl("text", { x: (x1 + x2) / 2, y: (y1 + y2) / 2 - 5, class: "edge-label" });
        t.textContent = e.label || e.rel;
        g.append(t);
      }
      svg.append(g);
      itensAresta.push({ g, a, b });
    }
    for (const n of nodes) {
      const g = svgEl("g", { class: "no" });
      const c = svgEl("circle", { cx: n.x, cy: n.y, r: raio(n), class: `k-${n.kind}${n.foco ? " foco" : ""}${n.novo ? " novo" : ""}` });
      const tip = svgEl("title");
      tip.textContent = n.detalhe ? `${n.label}\n${n.detalhe}` : n.label;
      c.append(tip);
      const rot = n.label.length > geo.lim ? n.label.slice(0, geo.lim - 1) + "…" : n.label;
      const t = svgEl("text", { x: n.x, y: n.y + raio(n) + 15, class: "node-label", "font-size": geo.fonte });
      t.textContent = rot;
      g.append(c, t); svg.append(g);
      itensNo.push({ g, n });
    }
    alvo.append(svg);

    // passar o mouse num no destaca ele e seus vizinhos
    const vizinhos = new Map(nodes.map((n) => [n.id, new Set([n.id])]));
    edges.forEach((e) => {
      if (vizinhos.has(e.source) && vizinhos.has(e.target)) {
        vizinhos.get(e.source).add(e.target); vizinhos.get(e.target).add(e.source);
      }
    });
    itensNo.forEach(({ g, n }) => {
      g.addEventListener("mouseenter", () => {
        const viz = vizinhos.get(n.id);
        itensNo.forEach((o) => o.g.classList.toggle("apagado", !viz.has(o.n.id)));
        itensAresta.forEach((o) => o.g.classList.toggle("apagado", !(o.a.id === n.id || o.b.id === n.id)));
      });
      g.addEventListener("mouseleave", () => {
        itensNo.forEach((o) => o.g.classList.remove("apagado"));
        itensAresta.forEach((o) => o.g.classList.remove("apagado"));
      });
    });

    // legenda clicavel: oculta/mostra um tipo de no (e as setas ligadas a ele)
    const ocultos = new Set();
    const aplicar = () => {
      itensNo.forEach(({ g, n }) => { g.style.display = ocultos.has(n.kind) ? "none" : ""; });
      itensAresta.forEach(({ g, a, b }) => { g.style.display = ocultos.has(a.kind) || ocultos.has(b.kind) ? "none" : ""; });
    };
    for (const k of [...new Set(nodes.map((n) => n.kind))]) {
      const marca = el("i"); marca.style.background = `var(--c-${k})`;
      const bt = el("button", { type: "button", className: "leg", title: "Clique para ocultar ou mostrar" }, marca, COR_NOS[k] || k);
      bt.setAttribute("aria-pressed", "true");
      bt.addEventListener("click", () => {
        if (ocultos.has(k)) ocultos.delete(k); else ocultos.add(k);
        bt.setAttribute("aria-pressed", String(!ocultos.has(k)));
        aplicar();
      });
      legenda.append(bt);
    }
    legenda.append(el("span", {}, "Contorno branco = serviço consultado"));
    if (nodes.some((n) => n.novo) || edges.some((e) => e.novo)) {
      legenda.append(el("span", {}, "Verde tracejado = gravado agora no grafo"));
    }
    if (nodes.length > 12) legenda.append(el("span", {}, "Passe o mouse num nó para destacar as ligações"));
  }

  function mostrarTrace(trace) {
    const alvo = $("trace");
    alvo.innerHTML = "";
    if (!trace || !trace.length) {
      alvo.append(el("span", { className: "placeholder", textContent: "Nenhuma consulta executada." }));
      return;
    }
    trace.forEach((p, i) => {
      const resumo = el("summary", {}, `${i + 1}. ${p.ferramenta}`, el("span", { textContent: JSON.stringify(p.entrada) }));
      const det = el("details", {}, resumo);
      if (i === 0) det.open = true;
      const corpo = el("div", { className: "consulta" });
      (p.consultas || []).forEach((c) => {
        if (c.escrita) corpo.append(el("span", { className: "badge", textContent: "ESCRITA NO GRAFO" }));
        corpo.append(
          el("pre", { textContent: c.cypher }),
          el("div", { className: "meta", textContent: `parâmetros: ${JSON.stringify(c.params)} → ${c.rows.length} linha(s)` })
        );
      });
      if (p.erro) corpo.append(el("div", { className: "meta", textContent: `Erro: ${p.erro}` }));
      det.append(corpo); alvo.append(det);
    });
  }

  async function perguntar(texto, agir) {
    const botao = $("botao"), status = $("status");
    status.className = ""; status.textContent = "Consultando o grafo e raciocinando…";
    botao.disabled = true;
    try {
      const r = await fetch("/api/ask", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pergunta: texto, agir }),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.erro || "Erro desconhecido");
      $("resposta").innerHTML = renderMarkdown(d.answer);
      desenharGrafo(d.grafo);
      mostrarTrace(d.trace);
      status.textContent = "";
    } catch (e) {
      status.className = "erro"; status.textContent = "Erro: " + e.message;
    } finally {
      botao.disabled = false;
    }
  }

  EXEMPLOS.forEach((ex) => {
    const b = el("button", { type: "button", className: "chip" + (ex.agir ? " acao" : ""), textContent: (ex.agir ? "✎ " : "") + ex.texto });
    b.addEventListener("click", () => {
      $("pergunta").value = ex.texto;
      $("agir").checked = ex.agir;
      perguntar(ex.texto, ex.agir);
    });
    $("exemplos").append(b);
  });
  $("form").addEventListener("submit", (ev) => {
    ev.preventDefault();
    const q = $("pergunta").value.trim();
    if (q) perguntar(q, $("agir").checked);
  });
}
