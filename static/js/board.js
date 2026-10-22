"use strict";

/* ═══════════════════════════════════════════
   SORUŞTURMA MASASI
   Dosyalar (sekmeler) · kartlar · kırmızı iplikler
   Veri sunucuda (SQLite /api/cases) saklanır.
═══════════════════════════════════════════ */
(() => {
  const NODE_W = 150;
  const TYPES = {
    person:   { ico: "👤", name: "Kişi",          color: "#2a7ac8" },
    email:    { ico: "📧", name: "Email",         color: "#7a5ad6" },
    username: { ico: "🔤", name: "Kullanıcı Adı", color: "#d98a00" },
    account:  { ico: "📱", name: "Hesap",         color: "#1e9a47" },
    domain:   { ico: "🌐", name: "Domain",        color: "#0a8f8f" },
    ip:       { ico: "📡", name: "IP",            color: "#5a6779" },
    phone:    { ico: "📞", name: "Telefon",       color: "#2e7d32" },
    place:    { ico: "📍", name: "Mekan",         color: "#c0281c" },
    org:      { ico: "🏢", name: "Kurum",         color: "#8a5200" },
    evidence: { ico: "📎", name: "Delil",         color: "#a8281b" },
    note:     { ico: "📝", name: "Not",           color: "#b8a100" },
  };
  const STRING_COLORS = { "Kırmızı": "#c0281c", "Mavi": "#2a6fc8", "Yeşil": "#1e8a45", "Siyah": "#2b2b2b", "Sarı": "#d6a400" };

  // ── durum ──
  let cases = [];
  let activeId = null;
  let sel = null;                   // {kind:"node"|"edge", id}
  let undoStack = [];
  let saveTimer = null;
  let boardScanOrigin = null;       // {caseId, nodeId} — bir karttan başlatılan tarama
  const lastCase = () => { try { return Number(localStorage.getItem("mr_active_case")) || null; } catch { return null; } };

  // ── DOM ──
  const $ = id => document.getElementById(id);
  const view = $("board-view"), world = $("board-world"), svg = $("board-svg"), nodesEl = $("board-nodes");
  const side = $("board-side"), tabsEl = $("case-tabs"), emptyEl = $("board-empty");
  if (!view) return;

  const esc2 = s => String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  const uid = () => "n" + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
  const cur = () => cases.find(c => c.id === activeId) || null;
  const nodeById = (c, id) => c.board.nodes.find(n => n.id === id);
  const status = t => { if (typeof setStatusText === "function") setStatusText(t); };

  async function api(method, url, body) {
    const r = await fetch(url, { method, headers: { "Content-Type": "application/json" }, body: body ? JSON.stringify(body) : undefined });
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).error || r.statusText);
    return r.json();
  }

  // ═══════════════ DİYALOG (Win7 penceresi) ═══════════════
  function dlg({ title, fields = [], ok = "Tamam", message = "" }) {
    return new Promise(resolve => {
      const ov = document.createElement("div");
      ov.className = "wdlg-overlay";
      ov.innerHTML = `
        <div class="wdlg" role="dialog">
          <div class="wdlg-title"><span>${esc2(title)}</span><button class="wc wc-close wdlg-x" type="button">✕</button></div>
          <form class="wdlg-body">
            ${message ? `<p class="wdlg-msg">${message}</p>` : ""}
            ${fields.map(f => `
              <label class="wdlg-field"><span>${esc2(f.label)}</span>
              ${f.type === "select"
                ? `<select name="${f.key}">${f.options.map(o => `<option value="${esc2(o.v)}" ${String(o.v) === String(f.value) ? "selected" : ""}>${esc2(o.t)}</option>`).join("")}</select>`
                : f.type === "textarea"
                  ? `<textarea name="${f.key}" rows="3">${esc2(f.value || "")}</textarea>`
                  : `<input name="${f.key}" type="text" value="${esc2(f.value || "")}" autocomplete="off" placeholder="${esc2(f.placeholder || "")}">`}
              </label>`).join("")}
            <div class="wdlg-btns">
              <button type="submit" class="scan-btn wdlg-ok">${esc2(ok)}</button>
              <button type="button" class="clear-btn wdlg-cancel">İptal</button>
            </div>
          </form>
        </div>`;
      document.body.appendChild(ov);
      const form = ov.querySelector("form");
      const close = v => { ov.remove(); document.removeEventListener("keydown", onKey, true); resolve(v); };
      const onKey = e => { if (e.key === "Escape") { e.stopPropagation(); close(null); } };
      document.addEventListener("keydown", onKey, true);
      form.addEventListener("keydown", e => { if (e.key === "Enter" && e.target.tagName === "SELECT") { e.preventDefault(); form.requestSubmit(); } });
      form.addEventListener("submit", e => {
        e.preventDefault();
        const out = {};
        fields.forEach(f => { out[f.key] = form.elements[f.key].value.trim(); });
        close(out);
      });
      ov.querySelector(".wdlg-cancel").onclick = () => close(null);
      ov.querySelector(".wdlg-x").onclick = () => close(null);
      ov.addEventListener("mousedown", e => { if (e.target === ov) close(null); });
      (form.querySelector("input,textarea,select") || form.querySelector("button")).focus();
    });
  }

  // ═══════════════ KAYDETME / GERİ ALMA ═══════════════
  function scheduleSave() {
    clearTimeout(saveTimer);
    status("Değişiklikler kaydediliyor...");
    saveTimer = setTimeout(saveNow, 500);
  }
  async function saveNow() {
    const c = cur();
    if (!c) return;
    try {
      await api("PUT", `/api/cases/${c.id}`, { board: c.board });
      status("Dosya kaydedildi");
    } catch (e) { status("Kayıt hatası: " + e.message); }
  }
  function pushUndo() {
    const c = cur();
    if (!c) return;
    undoStack.push(JSON.stringify({ id: c.id, nodes: c.board.nodes, edges: c.board.edges }));
    if (undoStack.length > 40) undoStack.shift();
  }
  function undo() {
    while (undoStack.length) {
      const snap = JSON.parse(undoStack.pop());
      const c = cases.find(x => x.id === snap.id);
      if (!c) continue;
      c.board.nodes = snap.nodes; c.board.edges = snap.edges;
      if (snap.id !== activeId) activeId = snap.id;
      sel = null; renderAll(); scheduleSave();
      return;
    }
    status("Geri alınacak işlem yok");
  }

  // ═══════════════ DOSYA SEKMELERİ ═══════════════
  function renderTabs() {
    tabsEl.innerHTML = cases.map(c => `
      <div class="case-tab ${c.id === activeId ? "active" : ""}" data-id="${c.id}" title="Çift tıkla: yeniden adlandır">
        <span class="case-ico">📁</span><span class="case-name">${esc2(c.name)}</span>
        <span class="case-count">${c.board.nodes.length}</span>
        <button class="case-x" data-del="${c.id}" title="Dosyayı sil">×</button>
      </div>`).join("") + `<button class="case-add" id="case-add" title="Yeni dosya">＋</button>`;
  }

  tabsEl.addEventListener("click", async e => {
    const del = e.target.closest("[data-del]");
    if (del) {
      e.stopPropagation();
      const c = cases.find(x => x.id === Number(del.dataset.del));
      if (!c || !confirm(`"${c.name}" dosyası ve içindeki ${c.board.nodes.length} kart silinsin mi?`)) return;
      await api("DELETE", `/api/cases/${c.id}`);
      cases = cases.filter(x => x.id !== c.id);
      if (activeId === c.id) activeId = cases[0]?.id ?? null;
      sel = null; renderAll();
      return;
    }
    if (e.target.closest("#case-add")) { newCase(); return; }
    const tab = e.target.closest(".case-tab");
    if (tab) openCase(Number(tab.dataset.id));
  });
  tabsEl.addEventListener("dblclick", async e => {
    const tab = e.target.closest(".case-tab");
    if (!tab) return;
    const c = cases.find(x => x.id === Number(tab.dataset.id));
    const r = await dlg({ title: "Dosyayı yeniden adlandır", fields: [{ key: "name", label: "Dosya adı", value: c.name }] });
    if (r && r.name) { c.name = r.name; await api("PUT", `/api/cases/${c.id}`, { name: c.name }); renderTabs(); }
  });

  async function newCase(name) {
    if (name === undefined) {
      const r = await dlg({ title: "Yeni soruşturma dosyası", fields: [{ key: "name", label: "Dosya adı", value: `Dosya ${cases.length + 1}`, placeholder: "ör. Kişi A araştırması" }], ok: "Oluştur" });
      if (!r) return null;
      name = r.name;
    }
    const c = await api("POST", "/api/cases", { name: name || `Dosya ${cases.length + 1}` });
    cases.push(c);
    openCase(c.id);
    return c;
  }

  function openCase(id) {
    activeId = id; sel = null; undoStack = [];
    try { localStorage.setItem("mr_active_case", String(id)); } catch { /* yoksay */ }
    renderAll();
  }

  // ═══════════════ GÖRÜNÜM (pan / zoom) ═══════════════
  const V = () => { const c = cur(); if (!c) return { x: 0, y: 0, z: 1 }; return (c.board.view = c.board.view || { x: 0, y: 0, z: 1 }); };
  function applyView() {
    const v = V();
    world.style.transform = `translate(${v.x}px, ${v.y}px) scale(${v.z})`;
    view.style.backgroundPosition = `${v.x}px ${v.y}px, ${v.x + 4}px ${v.y + 5}px`;
    view.style.backgroundSize = `${9 * v.z}px ${9 * v.z}px, ${13 * v.z}px ${13 * v.z}px`;
  }
  const toWorld = (cx, cy) => { const r = view.getBoundingClientRect(), v = V(); return { x: (cx - r.left - v.x) / v.z, y: (cy - r.top - v.y) / v.z }; };
  function zoomAt(factor, mx, my) {
    const v = V(), nz = Math.min(2.5, Math.max(0.25, v.z * factor));
    v.x = mx - (mx - v.x) * (nz / v.z); v.y = my - (my - v.y) * (nz / v.z); v.z = nz;
    applyView(); scheduleSave();
  }
  view.addEventListener("wheel", e => {
    e.preventDefault();
    const r = view.getBoundingClientRect();
    zoomAt(e.deltaY < 0 ? 1.1 : 0.9, e.clientX - r.left, e.clientY - r.top);
  }, { passive: false });
  $("bt-zoom-in").onclick = () => zoomAt(1.2, view.clientWidth / 2, view.clientHeight / 2);
  $("bt-zoom-out").onclick = () => zoomAt(1 / 1.2, view.clientWidth / 2, view.clientHeight / 2);

  function fit() {
    const c = cur();
    if (!c || !c.board.nodes.length) { Object.assign(V(), { x: view.clientWidth / 2, y: view.clientHeight / 2, z: 1 }); applyView(); return; }
    let x1 = Infinity, y1 = Infinity, x2 = -Infinity, y2 = -Infinity;
    c.board.nodes.forEach(n => { x1 = Math.min(x1, n.x); y1 = Math.min(y1, n.y); x2 = Math.max(x2, n.x + NODE_W); y2 = Math.max(y2, n.y + 90); });
    const pad = 60, w = view.clientWidth, h = view.clientHeight;
    const z = Math.min(1.4, Math.max(0.25, Math.min((w - pad * 2) / (x2 - x1), (h - pad * 2) / (y2 - y1))));
    Object.assign(V(), { z, x: (w - (x2 - x1) * z) / 2 - x1 * z, y: (h - (y2 - y1) * z) / 2 - y1 * z });
    applyView(); scheduleSave();
  }
  $("bt-fit").onclick = fit;

  // ═══════════════ ÇİZİM ═══════════════
  const rot = id => { let h = 0; for (const ch of id) h = (h * 31 + ch.charCodeAt(0)) | 0; return ((Math.abs(h) % 7) - 3) * 0.55; };
  const pinPoint = n => ({ x: n.x + NODE_W / 2, y: n.y + 7 });

  function nodeHTML(n) {
    const t = TYPES[n.type] || TYPES.note;
    return `
      <div class="bpin" title="Sürükle → başka karta bırak: iplik bağla"></div>
      <div class="bnode-head" style="--c:${t.color}"><span>${t.ico}</span><span class="btype">${t.name}</span>${n.note ? `<span class="bnote-ind" title="${esc2(n.note)}">📝</span>` : ""}</div>
      <div class="bnode-body">
        ${n.img ? `<img class="bimg" src="${esc2(n.img)}" alt="" referrerpolicy="no-referrer" onerror="this.remove()">` : ""}
        <div class="blabel">${esc2(n.label)}</div>
        ${n.sub ? `<div class="bsub">${esc2(n.sub)}</div>` : ""}
      </div>`;
  }

  function renderNodes() {
    const c = cur();
    nodesEl.innerHTML = "";
    if (!c) return;
    c.board.nodes.forEach(n => {
      const el = document.createElement("div");
      el.className = "bnode" + (sel?.kind === "node" && sel.id === n.id ? " sel" : "");
      el.dataset.id = n.id;
      el.style.cssText = `left:${n.x}px;top:${n.y}px;width:${NODE_W}px;transform:rotate(${rot(n.id)}deg)`;
      el.innerHTML = nodeHTML(n);
      nodesEl.appendChild(el);
    });
    applySearch();
    emptyEl.style.display = c.board.nodes.length ? "none" : "";
  }

  function edgePath(a, b) {
    const dx = b.x - a.x, dy = b.y - a.y, dist = Math.hypot(dx, dy);
    const cx = (a.x + b.x) / 2, cy = (a.y + b.y) / 2 + Math.min(70, dist * 0.2);      // iplik sarkması
    return { d: `M${a.x},${a.y} Q${cx},${cy} ${b.x},${b.y}`, mx: 0.25 * a.x + 0.5 * cx + 0.25 * b.x, my: 0.25 * a.y + 0.5 * cy + 0.25 * b.y };
  }

  function renderEdges() {
    const c = cur();
    if (!c) { svg.innerHTML = ""; return; }
    const selNode = sel?.kind === "node" ? sel.id : null;
    svg.classList.toggle("has-sel", !!selNode);
    svg.innerHTML = c.board.edges.map(e => {
      const a = nodeById(c, e.from), b = nodeById(c, e.to);
      if (!a || !b) return "";
      const p = edgePath(pinPoint(a), pinPoint(b));
      const col = e.color || STRING_COLORS["Kırmızı"];
      const rel = selNode && (e.from === selNode || e.to === selNode);
      const isSel = sel?.kind === "edge" && sel.id === e.id;
      const w = (e.label || "").length * 6.4 + 12;
      return `<g class="bedge ${rel ? "rel" : ""} ${isSel ? "sel" : ""}" data-id="${e.id}">
        <path class="bedge-hit" d="${p.d}"/>
        <path class="bedge-shadow" d="${p.d}" transform="translate(2,3)"/>
        <path class="bedge-line" d="${p.d}" stroke="${col}"/>
        ${e.label ? `<g class="bedge-label" transform="translate(${p.mx},${p.my})"><rect x="${-w / 2}" y="-9" width="${w}" height="17" rx="2"/><text text-anchor="middle" y="4">${esc2(e.label)}</text></g>` : ""}
      </g>`;
    }).join("");
  }

  function renderAll() { renderTabs(); renderNodes(); renderEdges(); applyView(); renderSide(); }

  // ═══════════════ ARAMA ═══════════════
  function applySearch() {
    const q = ($("board-search").value || "").trim().toLowerCase();
    const c = cur();
    nodesEl.querySelectorAll(".bnode").forEach(el => {
      const n = c && nodeById(c, el.dataset.id);
      const hit = !q || (n && (`${n.label} ${n.sub || ""} ${n.note || ""} ${n.type}`).toLowerCase().includes(q));
      el.classList.toggle("dim", !hit);
      el.classList.toggle("match", !!q && hit);
    });
  }
  $("board-search").addEventListener("input", applySearch);
  $("board-search").addEventListener("keydown", e => {
    if (e.key !== "Enter") return;
    const c = cur(), q = e.target.value.trim().toLowerCase();
    const n = c && q && c.board.nodes.find(x => (`${x.label} ${x.sub || ""} ${x.note || ""}`).toLowerCase().includes(q));
    if (n) { const v = V(); v.x = view.clientWidth / 2 - (n.x + NODE_W / 2) * v.z; v.y = view.clientHeight / 2 - n.y * v.z; applyView(); select({ kind: "node", id: n.id }); }
  });

  // ═══════════════ SEÇİM ═══════════════
  function select(s) { sel = s; renderNodes(); renderEdges(); renderSide(); }

  // ═══════════════ EKLE / SİL / BAĞLA ═══════════════
  function addNodeRaw(c, { type, label, sub = "", note = "", img = "", x, y }) {
    const n = { id: uid(), type, label, sub, note, img, x: Math.round(x), y: Math.round(y) };
    c.board.nodes.push(n);
    return n;
  }
  function addEdgeRaw(c, from, to, label = "", color = "") {
    if (from === to) return null;
    const dup = c.board.edges.find(e => (e.from === from && e.to === to) || (e.from === to && e.to === from));
    if (dup) { if (label && !dup.label) dup.label = label; return dup; }
    const e = { id: uid(), from, to, label, color };
    c.board.edges.push(e);
    return e;
  }

  async function addNodeDialog(type, at, linkFrom) {
    if (!cur()) { if (!(await newCase())) return; }
    const r = await dlg({
      title: "Yeni kart",
      fields: [
        { key: "type", label: "Tür", type: "select", value: type || "person", options: Object.entries(TYPES).map(([v, t]) => ({ v, t: `${t.ico} ${t.name}` })) },
        { key: "label", label: "Başlık", placeholder: "ör. Ahmet Y. / ahmet@site.com / 1.2.3.4" },
        { key: "sub", label: "Alt bilgi (opsiyonel)" },
        { key: "note", label: "Not (opsiyonel)", type: "textarea" },
      ], ok: "Ekle",
    });
    if (!r || !r.label) return;
    const c = cur();
    pushUndo();
    const pos = at || toWorld(view.getBoundingClientRect().left + view.clientWidth / 2 + (Math.random() - .5) * 160, view.getBoundingClientRect().top + view.clientHeight / 2 + (Math.random() - .5) * 120);
    const n = addNodeRaw(c, { type: r.type, label: r.label, sub: r.sub, note: r.note, x: pos.x - NODE_W / 2, y: pos.y - 20 });
    if (linkFrom) addEdgeRaw(c, linkFrom, n.id);
    sel = { kind: "node", id: n.id };
    renderAll(); scheduleSave();
  }

  function deleteSel() {
    const c = cur();
    if (!c || !sel) return;
    pushUndo();
    if (sel.kind === "node") {
      c.board.nodes = c.board.nodes.filter(n => n.id !== sel.id);
      c.board.edges = c.board.edges.filter(e => e.from !== sel.id && e.to !== sel.id);
    } else {
      c.board.edges = c.board.edges.filter(e => e.id !== sel.id);
    }
    sel = null; renderAll(); scheduleSave();
  }

  document.addEventListener("keydown", e => {
    if (!$("panel-board").classList.contains("active")) return;
    if (e.target.matches("input,textarea,select")) return;
    if (e.key === "Delete" || e.key === "Backspace") { e.preventDefault(); deleteSel(); }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z") { e.preventDefault(); undo(); }
  });

  // araç çubuğu
  $("board-add-btns").innerHTML = Object.entries(TYPES).map(([k, t]) => `<button class="tb-btn" data-add="${k}" title="${t.name} kartı ekle">${t.ico}<span> ${t.name}</span></button>`).join("");
  $("board-add-btns").addEventListener("click", e => { const b = e.target.closest("[data-add]"); if (b) addNodeDialog(b.dataset.add); });
  $("bt-undo").onclick = undo;
  $("bt-layout").onclick = () => { pushUndo(); autoLayout(); renderAll(); fit(); scheduleSave(); };
  $("bt-export").onclick = () => {
    const c = cur(); if (!c) return;
    const blob = new Blob([JSON.stringify({ name: c.name, exported: new Date().toISOString(), board: c.board }, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = `${c.name.replace(/[^\w\-]+/g, "_")}.json`; a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  };

  // ═══════════════ ETKİLEŞİM (sürükle, iplik, pan) ═══════════════
  let drag = null;
  view.addEventListener("pointerdown", e => {
    if (e.button !== 0 && e.button !== 1) return;
    const c = cur();
    if (!c) return;
    const pin = e.target.closest(".bpin");
    const nodeEl = e.target.closest(".bnode");
    const edgeEl = e.target.closest(".bedge");

    if (pin && nodeEl) {                                   // iplik çek
      e.preventDefault();
      const src = nodeById(c, nodeEl.dataset.id);
      const tmp = document.createElementNS("http://www.w3.org/2000/svg", "path");
      tmp.setAttribute("class", "bedge-temp");
      svg.appendChild(tmp);
      drag = { kind: "link", src, tmp };
      view.setPointerCapture(e.pointerId);
      return;
    }
    if (nodeEl) {                                          // kart taşı
      const n = nodeById(c, nodeEl.dataset.id);
      if (!(sel?.kind === "node" && sel.id === n.id)) { sel = { kind: "node", id: n.id }; nodesEl.querySelectorAll(".bnode.sel").forEach(x => x.classList.remove("sel")); nodeEl.classList.add("sel"); renderEdges(); renderSide(); }
      const w = toWorld(e.clientX, e.clientY);
      drag = { kind: "node", n, el: nodeEl, ox: w.x - n.x, oy: w.y - n.y, moved: false };
      nodeEl.classList.add("dragging");
      view.setPointerCapture(e.pointerId);
      return;
    }
    if (edgeEl) { select({ kind: "edge", id: edgeEl.dataset.id }); return; }
    drag = { kind: "pan", sx: e.clientX, sy: e.clientY, vx: V().x, vy: V().y, moved: false };   // panoyu kaydır
    view.classList.add("panning");
    view.setPointerCapture(e.pointerId);
  });

  view.addEventListener("pointermove", e => {
    if (!drag) return;
    const c = cur();
    if (drag.kind === "node") {
      const w = toWorld(e.clientX, e.clientY);
      if (!drag.moved) { pushUndo(); drag.moved = true; }
      drag.n.x = Math.round(w.x - drag.ox); drag.n.y = Math.round(w.y - drag.oy);
      drag.el.style.left = drag.n.x + "px"; drag.el.style.top = drag.n.y + "px";
      renderEdges();
    } else if (drag.kind === "pan") {
      const v = V();
      if (Math.abs(e.clientX - drag.sx) + Math.abs(e.clientY - drag.sy) > 3) drag.moved = true;
      v.x = drag.vx + e.clientX - drag.sx; v.y = drag.vy + e.clientY - drag.sy;
      applyView();
    } else if (drag.kind === "link") {
      const a = pinPoint(drag.src), w = toWorld(e.clientX, e.clientY);
      drag.tmp.setAttribute("d", edgePath(a, w).d);
      const over = document.elementFromPoint(e.clientX, e.clientY)?.closest(".bnode");
      nodesEl.querySelectorAll(".bnode.target").forEach(x => x.classList.remove("target"));
      if (over && over.dataset.id !== drag.src.id) over.classList.add("target");
    }
  });

  view.addEventListener("pointerup", async e => {
    if (!drag) return;
    const d = drag; drag = null;
    view.classList.remove("panning");
    nodesEl.querySelectorAll(".dragging,.target").forEach(x => x.classList.remove("dragging", "target"));
    try { view.releasePointerCapture(e.pointerId); } catch { /* yoksay */ }
    const c = cur();
    if (d.kind === "node" && d.moved) scheduleSave();
    if (d.kind === "pan") { if (!d.moved) { sel = null; renderNodes(); renderEdges(); renderSide(); } else scheduleSave(); }
    if (d.kind === "link") {
      d.tmp.remove();
      const over = document.elementFromPoint(e.clientX, e.clientY)?.closest(".bnode");
      if (over && over.dataset.id !== d.src.id) {
        const other = nodeById(c, over.dataset.id);
        const r = await dlg({
          title: "İplik bağla",
          message: `<b>${esc2(d.src.label)}</b> ↔ <b>${esc2(other.label)}</b>`,
          fields: [
            { key: "label", label: "Bağlantı türü", placeholder: "ör. arkadaşı, aynı IP, çalışıyor, şüpheli" },
            { key: "color", label: "İplik rengi", type: "select", value: "Kırmızı", options: Object.keys(STRING_COLORS).map(k => ({ v: k, t: k })) },
          ], ok: "Bağla",
        });
        if (!r) return;
        pushUndo();
        const edge = addEdgeRaw(c, d.src.id, other.id, r.label, STRING_COLORS[r.color]);
        sel = edge ? { kind: "edge", id: edge.id } : sel;
        renderAll(); scheduleSave();
      } else if (!over) {
        const w = toWorld(e.clientX, e.clientY);
        const moved = Math.hypot(w.x - pinPoint(d.src).x, w.y - pinPoint(d.src).y) > 80;
        if (moved) addNodeDialog("person", w, d.src.id);          // boşluğa bırakıldı → yeni kart + iplik
      }
    }
  });

  view.addEventListener("dblclick", e => {
    const el = e.target.closest(".bnode");
    if (el) { select({ kind: "node", id: el.dataset.id }); side.querySelector("[data-f=label]")?.focus(); return; }
    if (!e.target.closest(".bedge")) addNodeDialog("note", toWorld(e.clientX, e.clientY));
  });

  // ═══════════════ OTOMATİK DÜZEN (kuvvet yönlü) ═══════════════
  function autoLayout() {
    const c = cur();
    if (!c || c.board.nodes.length < 2) return;
    const N = c.board.nodes, idx = new Map(N.map((n, i) => [n.id, i]));
    const P = N.map(n => ({ x: n.x + NODE_W / 2, y: n.y + 30, vx: 0, vy: 0 }));
    const E = c.board.edges.map(e => [idx.get(e.from), idx.get(e.to)]).filter(([a, b]) => a !== undefined && b !== undefined);
    const L = 230;
    // ayrık başlangıç: üst üste binenleri hafifçe dağıt
    P.forEach((p, i) => { p.x += (i % 7) * 3; p.y += (i % 5) * 3; });
    for (let it = 0; it < 320; it++) {
      const cool = 1 - it / 320;
      for (let i = 0; i < P.length; i++) for (let j = i + 1; j < P.length; j++) {
        let dx = P[i].x - P[j].x, dy = P[i].y - P[j].y, d2 = dx * dx + dy * dy || 1;
        const d = Math.sqrt(d2), f = 52000 / d2;
        dx = dx / d * f; dy = dy / d * f;
        P[i].vx += dx; P[i].vy += dy; P[j].vx -= dx; P[j].vy -= dy;
      }
      E.forEach(([a, b]) => {
        const dx = P[b].x - P[a].x, dy = P[b].y - P[a].y, d = Math.hypot(dx, dy) || 1, f = (d - L) * 0.02;
        P[a].vx += dx / d * f * d * 0.05; P[a].vy += dy / d * f * d * 0.05;
        P[b].vx -= dx / d * f * d * 0.05; P[b].vy -= dy / d * f * d * 0.05;
      });
      P.forEach(p => {
        p.vx -= p.x * 0.002; p.vy -= p.y * 0.002;
        p.x += Math.max(-30, Math.min(30, p.vx)) * cool; p.y += Math.max(-30, Math.min(30, p.vy)) * cool;
        p.vx *= 0.5; p.vy *= 0.5;
      });
    }
    N.forEach((n, i) => { n.x = Math.round(P[i].x - NODE_W / 2); n.y = Math.round(P[i].y - 30); });
  }

  // ═══════════════ YAN PANEL (ayrıntılar) ═══════════════
  function sameNodesElsewhere(n) {
    const key = (n.label || "").trim().toLowerCase();
    return cases.filter(c => c.id !== activeId).map(c => ({ c, m: c.board.nodes.find(x => x.type === n.type && (x.label || "").trim().toLowerCase() === key) })).filter(x => x.m);
  }

  function renderSide() {
    const c = cur();
    if (!c) { side.innerHTML = `<div class="side-empty"><p>Henüz dosya yok.</p><button class="scan-btn" id="side-newcase">＋ Yeni Dosya</button></div>`; $("side-newcase").onclick = () => newCase(); return; }

    if (sel?.kind === "node") {
      const n = nodeById(c, sel.id);
      if (!n) { sel = null; return renderSide(); }
      const t = TYPES[n.type] || TYPES.note;
      const links = c.board.edges.filter(e => e.from === n.id || e.to === n.id).map(e => {
        const o = nodeById(c, e.from === n.id ? e.to : e.from);
        return o ? `<div class="side-link" data-goto="${o.id}"><span>${(TYPES[o.type] || TYPES.note).ico} ${esc2(o.label)}</span><em>${esc2(e.label || "—")}</em></div>` : "";
      }).join("");
      const elsewhere = sameNodesElsewhere(n);
      const scannable = ["email", "username", "domain"].includes(n.type);
      side.innerHTML = `
        <div class="side-head" style="--c:${t.color}">${t.ico} ${t.name}</div>
        <label class="side-f"><span>Tür</span><select data-f="type">${Object.entries(TYPES).map(([k, v]) => `<option value="${k}" ${k === n.type ? "selected" : ""}>${v.ico} ${v.name}</option>`).join("")}</select></label>
        <label class="side-f"><span>Başlık</span><input data-f="label" value="${esc2(n.label)}"></label>
        <label class="side-f"><span>Alt bilgi</span><input data-f="sub" value="${esc2(n.sub)}"></label>
        <label class="side-f"><span>Fotoğraf URL</span><input data-f="img" value="${esc2(n.img)}" placeholder="https://..."></label>
        <label class="side-f"><span>Notlar</span><textarea data-f="note" rows="5">${esc2(n.note)}</textarea></label>
        <div class="side-btns">
          ${scannable ? `<button class="export-btn" id="side-scan">🔍 Bu kartı tara</button>` : ""}
          <button class="export-btn" id="side-del">🗑 Kartı sil</button>
        </div>
        ${cases.length > 1 ? `<label class="side-f"><span>Başka dosyaya kopyala</span><select id="side-copy"><option value="">Seç...</option>${cases.filter(x => x.id !== c.id).map(x => `<option value="${x.id}">📁 ${esc2(x.name)}</option>`).join("")}</select></label>` : ""}
        <div class="side-sec">İplikler (${c.board.edges.filter(e => e.from === n.id || e.to === n.id).length})</div>
        ${links || `<div class="side-muted">Bağlantı yok. Kırmızı iğneyi başka karta sürükle.</div>`}
        ${elsewhere.length ? `<div class="side-sec">⚠ Diğer dosyalarda da var</div>${elsewhere.map(x => `<div class="side-link" data-case="${x.c.id}" data-node="${x.m.id}"><span>📁 ${esc2(x.c.name)}</span><em>${esc2(x.m.label)}</em></div>`).join("")}` : ""}`;
      return;
    }

    if (sel?.kind === "edge") {
      const e = c.board.edges.find(x => x.id === sel.id);
      if (!e) { sel = null; return renderSide(); }
      const a = nodeById(c, e.from), b = nodeById(c, e.to);
      side.innerHTML = `
        <div class="side-head" style="--c:#c0281c">🧵 İplik</div>
        <div class="side-edge"><b>${esc2(a?.label)}</b><br>↕<br><b>${esc2(b?.label)}</b></div>
        <label class="side-f"><span>Bağlantı türü</span><input data-e="label" value="${esc2(e.label)}"></label>
        <label class="side-f"><span>Renk</span><select data-e="color">${Object.entries(STRING_COLORS).map(([k, v]) => `<option value="${v}" ${v === (e.color || STRING_COLORS["Kırmızı"]) ? "selected" : ""}>${k}</option>`).join("")}</select></label>
        <div class="side-btns"><button class="export-btn" id="side-swap">⇄ Yönü çevir</button><button class="export-btn" id="side-del">🗑 İpliği kes</button></div>`;
      return;
    }

    // hiçbir şey seçili değil: dosya özeti + ortak öğeler
    const shared = c.board.nodes.map(n => ({ n, hit: sameNodesElsewhere(n) })).filter(x => x.hit.length);
    side.innerHTML = `
      <div class="side-head" style="--c:#2a7ac8">📁 ${esc2(c.name)}</div>
      <div class="side-stats"><div><b>${c.board.nodes.length}</b><span>kart</span></div><div><b>${c.board.edges.length}</b><span>iplik</span></div><div><b>${cases.length}</b><span>dosya</span></div></div>
      <div class="side-sec">İpuçları</div>
      <ul class="side-tips">
        <li>Boşluğa çift tıkla → not kartı</li>
        <li>Kırmızı iğneyi sürükle → iplik</li>
        <li>İpliği boşluğa bırak → yeni kart</li>
        <li>Tekerlek: yakınlaş · boşluğu sürükle: kaydır</li>
        <li><kbd>Del</kbd> sil · <kbd>Ctrl+Z</kbd> geri al</li>
      </ul>
      ${shared.length ? `<div class="side-sec">🔗 Diğer dosyalarla ortak (${shared.length})</div>${shared.slice(0, 12).map(x => `<div class="side-link" data-goto="${x.n.id}"><span>${(TYPES[x.n.type] || TYPES.note).ico} ${esc2(x.n.label)}</span><em>${x.hit.map(h => esc2(h.c.name)).join(", ")}</em></div>`).join("")}` : ""}`;
  }

  // yan panel olayları
  side.addEventListener("input", e => {
    const c = cur(); if (!c || !sel) return;
    if (sel.kind === "node" && e.target.dataset.f) {
      const n = nodeById(c, sel.id), f = e.target.dataset.f;
      if (!e.target._undone) { pushUndo(); e.target._undone = true; }
      n[f] = e.target.value;
      if (f === "type") { renderNodes(); renderEdges(); const h = side.querySelector(".side-head"); const t = TYPES[n.type]; h.style.setProperty("--c", t.color); h.textContent = `${t.ico} ${t.name}`; }
      else { const el = nodesEl.querySelector(`.bnode[data-id="${n.id}"]`); if (el) el.innerHTML = nodeHTML(n); renderEdges(); }
      scheduleSave();
    } else if (sel.kind === "edge" && e.target.dataset.e) {
      const ed = c.board.edges.find(x => x.id === sel.id);
      ed[e.target.dataset.e] = e.target.value; renderEdges(); scheduleSave();
    }
  });
  side.addEventListener("change", async e => {
    const c = cur();
    if (e.target.id === "side-copy" && e.target.value) {
      const dst = cases.find(x => x.id === Number(e.target.value)), n = nodeById(c, sel.id);
      const exists = dst.board.nodes.find(x => x.type === n.type && x.label.toLowerCase() === n.label.toLowerCase());
      if (!exists) {
        dst.board.nodes.push({ ...n, id: uid(), x: n.x, y: n.y });
        await api("PUT", `/api/cases/${dst.id}`, { board: dst.board });
        status(`"${n.label}" → ${dst.name} dosyasına kopyalandı`);
      } else status("Bu kart hedef dosyada zaten var");
      e.target.value = ""; renderTabs();
    }
  });
  side.addEventListener("click", e => {
    const c = cur();
    const go = e.target.closest("[data-goto]");
    if (go) { const n = nodeById(c, go.dataset.goto); if (n) { const v = V(); v.x = view.clientWidth / 2 - (n.x + NODE_W / 2) * v.z; v.y = view.clientHeight / 2 - n.y * v.z; applyView(); select({ kind: "node", id: n.id }); } return; }
    const oc = e.target.closest("[data-case]");
    if (oc) { const id = Number(oc.dataset.case), nid = oc.dataset.node; openCase(id); const n = nodeById(cur(), nid); if (n) { const v = V(); v.x = view.clientWidth / 2 - (n.x + NODE_W / 2) * v.z; v.y = view.clientHeight / 2 - n.y * v.z; applyView(); select({ kind: "node", id: nid }); } return; }
    if (e.target.closest("#side-del")) deleteSel();
    if (e.target.closest("#side-swap")) { const ed = c.board.edges.find(x => x.id === sel.id); pushUndo(); [ed.from, ed.to] = [ed.to, ed.from]; renderAll(); scheduleSave(); }
    if (e.target.closest("#side-scan")) scanNode(nodeById(c, sel.id));
  });

  // ═══════════════ KARTTAN TARAMA ═══════════════
  function scanNode(n) {
    if (!n || typeof startScan !== "function") return;
    boardScanOrigin = { caseId: activeId, nodeId: n.id };
    ["inp-email", "inp-username", "inp-domain", "inp-name"].forEach(id => { $(id).value = ""; });
    $(n.type === "email" ? "inp-email" : n.type === "domain" ? "inp-domain" : "inp-username").value = n.label;
    document.querySelector('.nav-btn[data-panel="scan"]').click();
    startScan();
    status("Tarama bitince 📌 Masaya Aktar ile sonuçları bu karta bağla");
  }

  // ═══════════════ TARAMADAN AKTARMA ═══════════════
  async function chooseCase(defaultName) {
    const opts = [{ v: "new", t: `＋ Yeni dosya: ${defaultName}` }, ...cases.map(c => ({ v: c.id, t: `📁 ${c.name}` }))];
    const r = await dlg({
      title: "Masaya aktar",
      message: "Bulgular hangi soruşturma dosyasına eklensin?",
      fields: [{ key: "case", label: "Dosya", type: "select", options: opts, value: boardScanOrigin?.caseId || activeId || (cases.length ? "new" : "new") }],
      ok: "Aktar",
    });
    if (!r) return null;
    if (r.case === "new") return await newCase(defaultName);
    openCase(Number(r.case));
    return cur();
  }

  async function importScan(results, inp, kind) {
    if (!results || !Object.keys(results).length) { status("Aktarılacak sonuç yok"); return; }
    const title = inp.name || inp.email || inp.username || inp.domain || inp.instagram || inp.github || inp.phone || "Hedef";
    const c = await chooseCase(title);
    if (!c) return;
    pushUndo();

    const created = [];
    const parentOf = new Map();
    const find = (type, label) => c.board.nodes.find(n => n.type === type && n.label.trim().toLowerCase() === String(label).trim().toLowerCase());
    const N = (type, label, extra = {}) => {
      label = String(label || "").trim();
      if (!label) return null;
      let n = find(type, label);
      if (!n) { n = addNodeRaw(c, { type, label, sub: extra.sub || "", img: extra.img || "", x: 0, y: 0 }); created.push(n); }
      else { if (extra.sub && !n.sub) n.sub = extra.sub; if (extra.img && !n.img) n.img = extra.img; }
      return n;
    };
    const L = (a, b, label) => {
      if (!a || !b || a === b) return;
      addEdgeRaw(c, a.id, b.id, label);
      if (created.includes(b) && !parentOf.has(b.id) && !created.includes(a)) parentOf.set(b.id, a.id);
      else if (created.includes(b) && !parentOf.has(b.id)) parentOf.set(b.id, a.id);
    };

    const r = results;
    const person = inp.name ? N("person", inp.name) : null;
    const email  = inp.email ? N("email", inp.email) : null;
    const uname  = inp.username && (!inp.email || inp.username !== inp.email.split("@")[0]) ? N("username", inp.username) : (inp.email && inp.username ? N("username", inp.username) : null);
    const domain = inp.domain && (!inp.email || inp.domain !== inp.email.split("@")[1]) ? N("domain", inp.domain) : null;
    const phone  = inp.phone ? N("phone", inp.phone, { sub: r.phone ? [r.phone.country, (r.phone.possible_carriers || [])[0]].filter(Boolean).join(" · ") : "" }) : null;
    const origin = boardScanOrigin && boardScanOrigin.caseId === c.id ? nodeById(c, boardScanOrigin.nodeId) : null;
    const anchor = origin || person || email || uname || domain || phone;
    const emailDomain = email ? N("domain", email.label.split("@")[1]) : null;

    [email, uname, phone, domain].forEach(n => { if (n && anchor && n !== anchor) L(anchor, n, person || origin ? "" : "aynı kimlik"); });
    if (email && emailDomain) L(email, emailDomain, "posta sunucusu");
    if (email && uname) L(email, uname, "yerel kısım");
    const userHub = uname || origin || anchor;
    const domHub = domain || emailDomain;

    const g = r.gravatar || {};
    if (g.has_gravatar && g.display_name) { const p = N("person", g.display_name, { img: g.avatar_url }); L(email || anchor, p, "Gravatar adı"); if (g.location) L(p, N("place", g.location), "konum"); }

    const co = r.correlation || {};
    (co.identified_names || []).slice(0, 5).forEach(nm => { if (!person || nm !== person.label) L(anchor, N("person", nm, { img: (co.avatar_urls || [])[0]?.url }), "isim"); });
    (co.identified_locations || []).slice(0, 4).forEach(l => L(anchor, N("place", l), "konum"));
    (co.identified_orgs || []).slice(0, 4).forEach(o => L(anchor, N("org", o), "kurum"));
    (co.identified_emails || []).slice(0, 6).forEach(em => { if (!email || em !== email.label) L(anchor, N("email", em), "email"); });
    (co.identified_usernames || []).slice(0, 6).forEach(u => { if (!uname || u.toLowerCase() !== uname.label.toLowerCase()) L(anchor, N("username", u), "alias"); });

    // platform hesapları
    const seenAcc = new Set();
    const addAcc = (name, url, sub, img, hub, lbl) => {
      const key = name.toLowerCase(); if (seenAcc.has(key)) return; seenAcc.add(key);
      L(hub || anchor, N("account", name, { sub: sub || url || "", img }), lbl || "hesap");
    };
    (r.username_osint?.found || []).slice(0, 60).forEach(f => addAcc(f.platform, f.url, f.url.replace(/^https?:\/\/(www\.)?/, ""), "", userHub));
    (r.social?.found || []).slice(0, 40).forEach(f => addAcc(f.platform, f.url, (f.url || "").replace(/^https?:\/\/(www\.)?/, ""), "", userHub));

    // hedef taraması: platform kartları
    const PLAT = { instagram: ["Instagram", "full_name", "followers"], twitter: ["Twitter/X", "full_name", null], youtube: ["YouTube", "name", "subscriber_count"], tiktok: ["TikTok", "nickname", "followers"],
                   spotify: ["Spotify", "display_name", "followers"], steam: ["Steam", "username", "level"], telegram: ["Telegram", "name", null], reddit: ["Reddit", null, null] };
    Object.entries(PLAT).forEach(([k, [label, nameKey, statKey]]) => {
      const d = r[k]; if (!d || !d.found) return;
      const handle = d.username || d.handle || inp[k] || "";
      const nm = (nameKey && d[nameKey]) || handle;
      const stat = statKey ? (d[statKey] ?? d.stats?.followers) : (d.stats?.followers);
      addAcc(label, d.profile_url, `${nm ? nm + " · " : ""}${handle ? "@" + handle : ""}${stat !== undefined && stat !== "" && stat !== null ? " · " + stat : ""}`, d.profile_pic_url, person || anchor, "hesap");
    });
    if (r.github_deep?.found) { const p = r.github_deep.profile || {}; addAcc("GitHub", p.html_url, `${p.name || p.login || ""} · ${p.public_repos || 0} repo`, p.avatar_url, userHub, "hesap"); if (p.location) L(userHub, N("place", p.location), "konum"); if (p.blog) { const b = N("domain", p.blog.replace(/^https?:\/\//, "").split("/")[0]); L(userHub, b, "web sitesi"); } }

    // altyapı
    (r.ip_intel?.ips || []).forEach(i => L(domHub, N("ip", i.ip, { sub: [i.asn, i.org].filter(Boolean).join(" ") }), "çözümlenir"));
    (r.web_recon?.emails || []).slice(0, 8).forEach(em => L(domHub, N("email", em), "sitede geçiyor"));
    (r.web_recon?.social_links || []).slice(0, 8).forEach(u => addAcc(u.replace(/^https?:\/\/(www\.)?/, "").split("/").slice(0, 2).join("/"), u, u, "", domHub, "sitede link"));
    const subs = (r.crt_search?.all_subdomains || []).filter(s => s !== (domHub && domHub.label)).slice(0, 8);
    subs.forEach(s => L(domHub, N("domain", s), "subdomain"));
    const paste = r.pastebin;
    if (paste && paste.total_found > 0) L(email || anchor, N("evidence", `Sızıntı/paste: ${paste.total_found} kayıt`, { sub: (paste.findings || []).map(f => f.source).filter(Boolean).slice(0, 3).join(", ") }), "bulgu");

    // yeni kartları ebeveynleri çevresine diz
    const hubs = created.filter(n => !parentOf.has(n.id));
    const center = origin ? { x: origin.x, y: origin.y } : (c.board.nodes.length > created.length ? { x: Math.max(...c.board.nodes.filter(n => !created.includes(n)).map(n => n.x)) + 520, y: 0 } : { x: 0, y: 0 });
    hubs.forEach((h, i) => { h.x = center.x + i * 320; h.y = center.y + (i % 2) * 120; });
    const kids = new Map();
    created.forEach(n => { const p = parentOf.get(n.id); if (p) (kids.get(p) || kids.set(p, []).get(p)).push(n); });
    const place = (pid, depth) => {
      const parent = nodeById(c, pid), list = kids.get(pid) || [];
      if (!parent) return;
      const R = 230 + 38 * Math.floor(list.length / 10) + depth * 30;
      list.forEach((k, i) => {
        const a = (-90 + (360 / Math.max(list.length, 1)) * i + depth * 20) * Math.PI / 180;
        k.x = Math.round(parent.x + Math.cos(a) * R * 1.25); k.y = Math.round(parent.y + Math.sin(a) * R);
        place(k.id, depth + 1);
      });
    };
    [...kids.keys()].filter(pid => !parentOf.has(pid)).forEach(pid => place(pid, 0));
    created.forEach(n => { if (n.x === 0 && n.y === 0 && !hubs.includes(n)) { const p = nodeById(c, parentOf.get(n.id)); if (p) { n.x = p.x + 200; n.y = p.y + 140; } } });

    boardScanOrigin = null;
    document.querySelector('.nav-btn[data-panel="board"]').click();
    sel = created[0] ? { kind: "node", id: created[0].id } : null;
    renderAll(); fit(); scheduleSave();
    status(`${created.length} yeni kart masaya eklendi`);
  }

  $("to-board-btn")?.addEventListener("click", () => importScan(currentResults, currentInputs, "scan"));
  $("target-to-board-btn")?.addEventListener("click", () => importScan(targetResults, targetInputs, "target"));

  // ═══════════════ BAŞLATMA ═══════════════
  async function init() {
    try {
      cases = await api("GET", "/api/cases");
      if (!cases.length) { cases = [await api("POST", "/api/cases", { name: "Dosya 1" })]; }
      activeId = cases.find(c => c.id === lastCase())?.id ?? cases[0].id;
      renderAll();
    } catch (e) { side.innerHTML = `<div class="side-empty">Pano yüklenemedi: ${esc2(e.message)}</div>`; }
  }
  document.querySelectorAll('[data-panel="board"]').forEach(b => b.addEventListener("click", () => setTimeout(() => { if (cur() && !cur().board.view?.z) fit(); applyView(); }, 30)));
  init();

  window.Board = { importScan, scanNode, cases: () => cases };
})();
