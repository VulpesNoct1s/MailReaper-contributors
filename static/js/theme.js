"use strict";

/* ═══════════════════════════════════════════
   KİŞİSELLEŞTİRME (Win7 "Pencere Rengi ve Görünümü" tarzı)
   Ayarlar tarayıcıda (localStorage) saklanır; CSS değişkenlerini ezer.
═══════════════════════════════════════════ */
(() => {
  const KEY = "mr_theme_v1";
  const DEFAULTS = { accent: "#3d85d6", wall: "aero", wallImg: "", glass: 72, blur: 14, rays: true, round: true, board: "cork", scale: 100, motion: true };

  // ── hazır temalar ──
  const PRESETS = [
    { id: "aero",     name: "Aero Mavi",  accent: "#3d85d6", wall: "aero",     board: "cork" },
    { id: "emerald",  name: "Zümrüt",     accent: "#2f9e5a", wall: "forest",   board: "felt" },
    { id: "rose",     name: "Gül",        accent: "#d6477a", wall: "sunset",   board: "cork" },
    { id: "violet",   name: "Mor Gece",   accent: "#7a5ad6", wall: "night",    board: "slate" },
    { id: "amber",    name: "Amber",      accent: "#e07a1f", wall: "sand",     board: "paper" },
    { id: "graphite", name: "Grafit",     accent: "#6b7a8f", wall: "graphite", board: "slate" },
    { id: "crimson",  name: "Kızıl",      accent: "#c0392b", wall: "night",    board: "cork" },
    { id: "blueprint", name: "Plan",      accent: "#2a6fc8", wall: "night",    board: "blueprint" },
  ];

  const WALLS = {
    aero:     { name: "Aero",       thumb: "linear-gradient(135deg,#0b3d8a,#3aa6e6)" },
    night:    { name: "Gece",       thumb: "linear-gradient(160deg,#050b1c,#14264d)", css: "radial-gradient(1.5px 1.5px at 20% 30%,#fff8,transparent),radial-gradient(1px 1px at 70% 60%,#fff8,transparent),radial-gradient(1.5px 1.5px at 45% 80%,#fff6,transparent),radial-gradient(ellipse 70% 50% at 70% 10%,rgba(90,110,220,.35),transparent 70%),linear-gradient(160deg,#050b1c,#14264d 55%,#0a1330)", c: "#0a1330" },
    sunset:   { name: "Gün batımı", thumb: "linear-gradient(160deg,#3a1c71,#ffaf7b)", css: "radial-gradient(ellipse 60% 40% at 70% 85%,rgba(255,200,120,.55),transparent 70%),linear-gradient(160deg,#3a1c71,#d76d77 55%,#ffaf7b)", c: "#8a3a6e" },
    forest:   { name: "Orman",      thumb: "linear-gradient(135deg,#0f3d2e,#2e8b57)", css: "radial-gradient(ellipse 60% 45% at 78% 8%,rgba(170,255,200,.4),transparent 70%),linear-gradient(135deg,#0b2f23,#1f7a4c 45%,#2e9a62 65%,#0b2a1f)", c: "#14543a" },
    graphite: { name: "Grafit",     thumb: "linear-gradient(135deg,#2b2f36,#4a5160)", css: "radial-gradient(ellipse 60% 45% at 78% 8%,rgba(200,210,230,.25),transparent 70%),linear-gradient(135deg,#1e2127,#3d4452 50%,#252932)", c: "#2b2f36" },
    sand:     { name: "Kum",        thumb: "linear-gradient(135deg,#c9b38a,#efe2c4)", css: "radial-gradient(ellipse 60% 45% at 78% 8%,rgba(255,255,255,.5),transparent 70%),linear-gradient(135deg,#b59a68,#e6d3a8 55%,#a98b57)", c: "#c9b38a" },
    solid:    { name: "Düz",        thumb: "linear-gradient(#2d5f9a,#2d5f9a)" },
  };

  const BOARDS = {
    cork:      { name: "Mantar",      c: "#c8a068", d1: "rgba(90,55,20,.28)",   d2: "rgba(255,240,200,.28)", inset: "rgba(60,30,0,.55)",  e1: "#7a5a30", e2: "#b08a52", ink: "rgba(60,35,10,.75)" },
    felt:      { name: "Yeşil çuha",  c: "#2f6b45", d1: "rgba(0,0,0,.22)",      d2: "rgba(255,255,255,.07)", inset: "rgba(0,25,10,.6)",   e1: "#1b3d28", e2: "#3d7f58", ink: "rgba(230,255,235,.85)" },
    blueprint: { name: "Mavi plan",   c: "#1f4e8c", d1: "rgba(255,255,255,.22)", d2: "rgba(120,190,255,.2)", inset: "rgba(0,20,60,.6)",   e1: "#0f2c55", e2: "#3a74b8", ink: "rgba(220,240,255,.88)" },
    slate:     { name: "Arduvaz",     c: "#444b55", d1: "rgba(0,0,0,.28)",      d2: "rgba(255,255,255,.08)", inset: "rgba(0,0,0,.55)",    e1: "#23272d", e2: "#6a7381", ink: "rgba(230,236,245,.85)" },
    paper:     { name: "Kâğıt",       c: "#e9e4d6", d1: "rgba(120,100,60,.2)",  d2: "rgba(255,255,255,.5)",  inset: "rgba(90,70,30,.3)",  e1: "#a89a78", e2: "#d6cdb4", ink: "rgba(70,55,30,.75)" },
  };

  // ── renk yardımcıları ──
  const hexToHsl = hex => {
    let h = hex.replace("#", ""); if (h.length === 3) h = h.split("").map(c => c + c).join("");
    const r = parseInt(h.slice(0, 2), 16) / 255, g = parseInt(h.slice(2, 4), 16) / 255, b = parseInt(h.slice(4, 6), 16) / 255;
    const mx = Math.max(r, g, b), mn = Math.min(r, g, b), l = (mx + mn) / 2; let hh = 0, s = 0;
    if (mx !== mn) {
      const d = mx - mn; s = l > .5 ? d / (2 - mx - mn) : d / (mx + mn);
      hh = mx === r ? (g - b) / d + (g < b ? 6 : 0) : mx === g ? (b - r) / d + 2 : (r - g) / d + 4; hh *= 60;
    }
    return { h: Math.round(hh), s: Math.round(s * 100), l: Math.round(l * 100) };
  };
  const hsl = (h, s, l, a) => a === undefined ? `hsl(${h},${s}%,${l}%)` : `hsla(${h},${s}%,${l}%,${a})`;

  // ── ayar saklama ──
  function load() {
    try { return { ...DEFAULTS, ...(JSON.parse(localStorage.getItem(KEY)) || {}) }; } catch { return { ...DEFAULTS }; }
  }
  function save(t) {
    try { localStorage.setItem(KEY, JSON.stringify(t)); return true; } catch { return false; }
  }

  // ── uygula ──
  function apply(t) {
    const root = document.documentElement, set = (k, v) => root.style.setProperty(k, v);
    const { h, s: s0 } = hexToHsl(t.accent);
    const s = Math.max(35, Math.min(95, s0));       // gri tonlarda bile okunur palet
    const gray = s0 < 22;
    const S = gray ? Math.max(s0, 8) : s;

    set("--head", hsl(h, Math.round(S * .8), 25));
    set("--hl", hsl(h, Math.round(S * .6), 44));
    set("--hl2", hsl(h, Math.round(S * .55), 62));
    set("--link-d", hsl(h, Math.round(S * .85), 27));
    set("--acc-c", hsl(h, Math.round(S * .7), 46));
    set("--accent2", hsl(h, Math.round(S * .9), 36));
    [97, 90, 82, 75].forEach((l, i) => set(`--hv${i + 1}`, hsl(h, Math.round(S * .9), l)));
    [94, 84, 72, 62].forEach((l, i) => set(`--pr${i + 1}`, hsl(h, Math.round(S * .8), l)));
    [88, 82, 74, 80].forEach((l, i) => set(`--na${i + 1}`, hsl(h, Math.round(S * .75), l)));
    set("--glass", hsl(h, Math.round(S * .5), 74, (t.glass / 100).toFixed(2)));
    set("--blur", t.blur + "px");
    set("--rays", t.rays ? "1" : "0");
    set("--win-r", t.round ? "8px" : "0px");
    set("--ui-scale", String(t.scale / 100));
    set("--tb1", hsl(h, Math.round(S * .35), 56, .78)); set("--tb2", hsl(h, Math.round(S * .5), 24, .88));
    set("--tb3", hsl(h, Math.round(S * .6), 11, .92));   set("--tb4", hsl(h, Math.round(S * .45), 29, .9));
    set("--orb1", hsl(h, Math.round(S * .9), 76)); set("--orb2", hsl(h, Math.round(S * .85), 52));
    set("--orb3", hsl(h, Math.round(S * .9), 30)); set("--orb4", hsl(h, Math.round(S * .9), 16));

    // duvar kağıdı
    if (t.wallImg) {
      set("--wall", `url("${t.wallImg}")`); set("--wall-size", "cover"); set("--wall-c", "#222");
    } else if (t.wall === "aero" || !WALLS[t.wall]) {
      set("--wall-size", "auto"); set("--wall-c", hsl(h, S, 36));
      set("--wall", `radial-gradient(ellipse 60% 45% at 78% 8%, ${hsl(h, 90, 82, .65)} 0%, transparent 70%),
        radial-gradient(ellipse 45% 35% at 18% 92%, ${hsl(h, 90, 62, .55)} 0%, transparent 70%),
        radial-gradient(ellipse 80% 60% at 50% 120%, rgba(255,255,255,.18) 0%, transparent 60%),
        linear-gradient(135deg, ${hsl(h, S, 24)} 0%, ${hsl(h, S, 44)} 38%, ${hsl(h, Math.min(S, 85), 58)} 62%, ${hsl(h, S, 30)} 100%)`);
    } else if (t.wall === "solid") {
      set("--wall-size", "auto"); set("--wall-c", hsl(h, Math.round(S * .6), 34)); set("--wall", "none");
    } else {
      set("--wall-size", "auto"); set("--wall-c", WALLS[t.wall].c); set("--wall", WALLS[t.wall].css);
    }

    // pano
    const b = BOARDS[t.board] || BOARDS.cork;
    set("--board-c", b.c); set("--board-d1", b.d1); set("--board-d2", b.d2); set("--board-in", b.inset);
    set("--board-e1", b.e1); set("--board-e2", b.e2); set("--board-ink", b.ink);

    root.classList.toggle("no-motion", !t.motion);
  }

  let theme = load();
  apply(theme);                                       // <head> içinde çalışır → yanıp sönme yok

  // ═══════════════ AYAR PENCERESİ ═══════════════
  const $ = (s, r = document) => r.querySelector(s);
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  let panel = null;

  function persist(msg) {
    if (!save(theme)) toast("Ayarlar kaydedilemedi (tarayıcı depolaması dolu/kapalı)");
    else if (msg) toast(msg);
  }
  function toast(t) { if (typeof setStatusText === "function") { setStatusText(t); setTimeout(() => setStatusText("Hazır"), 2500); } }

  function open() {
    if (panel) { panel.remove(); panel = null; }
    panel = document.createElement("div");
    panel.className = "wdlg-overlay theme-overlay";
    panel.innerHTML = `
      <div class="wdlg theme-win" role="dialog" aria-label="Kişiselleştirme">
        <div class="wdlg-title"><span>🎨 Kişiselleştirme — Pencere Rengi ve Görünümü</span><button class="wc wc-close wdlg-x" type="button" id="th-x">✕</button></div>
        <div class="wdlg-body theme-body">
          <div class="th-sec">Hazır temalar</div>
          <div class="th-presets">${PRESETS.map(p => `<button type="button" class="th-preset" data-preset="${p.id}" title="${esc(p.name)}">
            <span class="th-swatch" style="background:${p.accent}"></span><span>${esc(p.name)}</span></button>`).join("")}</div>

          <div class="th-sec">Vurgu rengi</div>
          <div class="th-row">
            <input type="color" id="th-accent" value="${theme.accent}">
            <input type="text" id="th-accent-hex" class="th-hex" value="${theme.accent}" maxlength="7" spellcheck="false">
            <span class="th-muted">Pencere camı, düğmeler, başlıklar ve görev çubuğu bu renkten türetilir.</span>
          </div>

          <div class="th-sec">Duvar kağıdı</div>
          <div class="th-walls">${Object.entries(WALLS).map(([k, w]) => `<button type="button" class="th-wall" data-wall="${k}" title="${esc(w.name)}" style="background:${w.thumb}"><span>${esc(w.name)}</span></button>`).join("")}</div>
          <div class="th-row">
            <label class="export-btn th-file">🖼 Resim seç...<input type="file" id="th-img" accept="image/*" hidden></label>
            <button type="button" class="export-btn" id="th-img-clear">Resmi kaldır</button>
            <span class="th-muted" id="th-img-note"></span>
          </div>

          <div class="th-sec">Cam efekti</div>
          <div class="th-grid">
            <label>Saydamlık <output id="o-glass"></output><input type="range" id="th-glass" min="30" max="100"></label>
            <label>Bulanıklık <output id="o-blur"></output><input type="range" id="th-blur" min="0" max="30"></label>
            <label>Arayüz ölçeği <output id="o-scale"></output><input type="range" id="th-scale" min="85" max="130" step="5"></label>
          </div>
          <div class="th-checks">
            <label><input type="checkbox" id="th-rays"> Cam parlaması ve ışık huzmeleri</label>
            <label><input type="checkbox" id="th-round"> Yuvarlak pencere köşeleri (Aero)</label>
            <label><input type="checkbox" id="th-motion"> Animasyonlar</label>
          </div>

          <div class="th-sec">Soruşturma masası zemini</div>
          <div class="th-boards">${Object.entries(BOARDS).map(([k, b]) => `<button type="button" class="th-board" data-board="${k}" title="${esc(b.name)}"><span style="background:${b.c}"></span>${esc(b.name)}</button>`).join("")}</div>

          <div class="wdlg-btns th-btns">
            <button type="button" class="clear-btn" id="th-export">📤 Dışa aktar</button>
            <label class="clear-btn th-file">📥 İçe aktar<input type="file" id="th-import" accept="application/json" hidden></label>
            <span style="flex:1"></span>
            <button type="button" class="clear-btn" id="th-reset">↺ Varsayılan</button>
            <button type="button" class="scan-btn wdlg-ok" id="th-ok">Tamam</button>
          </div>
        </div>
      </div>`;
    document.body.appendChild(panel);
    syncControls();
    wire();
  }

  function close() { panel?.remove(); panel = null; document.removeEventListener("keydown", onKey, true); }
  const onKey = e => { if (e.key === "Escape") { e.stopPropagation(); close(); } };

  function syncControls() {
    $("#th-accent").value = theme.accent; $("#th-accent-hex").value = theme.accent;
    $("#th-glass").value = theme.glass; $("#o-glass").textContent = theme.glass + "%";
    $("#th-blur").value = theme.blur;   $("#o-blur").textContent = theme.blur + "px";
    $("#th-scale").value = theme.scale; $("#o-scale").textContent = theme.scale + "%";
    $("#th-rays").checked = theme.rays; $("#th-round").checked = theme.round; $("#th-motion").checked = theme.motion;
    panel.querySelectorAll(".th-wall").forEach(b => b.classList.toggle("on", !theme.wallImg && b.dataset.wall === theme.wall));
    panel.querySelectorAll(".th-board").forEach(b => b.classList.toggle("on", b.dataset.board === theme.board));
    panel.querySelectorAll(".th-preset").forEach(b => { const p = PRESETS.find(x => x.id === b.dataset.preset); b.classList.toggle("on", p.accent.toLowerCase() === theme.accent.toLowerCase() && p.wall === theme.wall && p.board === theme.board); });
    $("#th-img-note").textContent = theme.wallImg ? "Özel resim kullanılıyor" : "";
  }

  const change = (patch, msg) => { theme = { ...theme, ...patch }; apply(theme); persist(msg); if (panel) syncControls(); };

  function wire() {
    document.addEventListener("keydown", onKey, true);
    panel.addEventListener("mousedown", e => { if (e.target === panel) close(); });
    $("#th-x").onclick = close; $("#th-ok").onclick = close;

    panel.querySelectorAll(".th-preset").forEach(b => b.onclick = () => {
      const p = PRESETS.find(x => x.id === b.dataset.preset);
      change({ accent: p.accent, wall: p.wall, wallImg: "", board: p.board });
    });
    $("#th-accent").addEventListener("input", e => change({ accent: e.target.value }));
    $("#th-accent-hex").addEventListener("change", e => { const v = e.target.value.trim(); if (/^#[0-9a-f]{6}$/i.test(v)) change({ accent: v }); else syncControls(); });
    panel.querySelectorAll(".th-wall").forEach(b => b.onclick = () => change({ wall: b.dataset.wall, wallImg: "" }));
    panel.querySelectorAll(".th-board").forEach(b => b.onclick = () => change({ board: b.dataset.board }));
    $("#th-glass").addEventListener("input", e => change({ glass: +e.target.value }));
    $("#th-blur").addEventListener("input", e => change({ blur: +e.target.value }));
    $("#th-scale").addEventListener("change", e => change({ scale: +e.target.value }));
    $("#th-scale").addEventListener("input", e => { $("#o-scale").textContent = e.target.value + "%"; });
    $("#th-rays").onchange = e => change({ rays: e.target.checked });
    $("#th-round").onchange = e => change({ round: e.target.checked });
    $("#th-motion").onchange = e => change({ motion: e.target.checked });

    $("#th-img").onchange = e => {
      const f = e.target.files[0]; if (!f) return;
      const img = new Image(), url = URL.createObjectURL(f);
      img.onload = () => {                                             // 1920px'e küçült → localStorage'a sığsın
        const k = Math.min(1, 1920 / Math.max(img.width, img.height)), c = document.createElement("canvas");
        c.width = Math.round(img.width * k); c.height = Math.round(img.height * k);
        c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
        URL.revokeObjectURL(url);
        const data = c.toDataURL("image/jpeg", 0.82);
        const before = theme; theme = { ...theme, wallImg: data };
        if (save(theme)) { apply(theme); syncControls(); } else { theme = before; $("#th-img-note").textContent = "Resim çok büyük, kaydedilemedi"; }
      };
      img.onerror = () => { URL.revokeObjectURL(url); $("#th-img-note").textContent = "Resim okunamadı"; };
      img.src = url;
    };
    $("#th-img-clear").onclick = () => change({ wallImg: "" });

    $("#th-reset").onclick = () => { theme = { ...DEFAULTS }; apply(theme); persist("Tema varsayılana döndü"); syncControls(); };
    $("#th-export").onclick = () => {
      const out = { ...theme, wallImg: "" };                          // resim paylaşılmaz
      const a = document.createElement("a");
      a.href = URL.createObjectURL(new Blob([JSON.stringify({ mailreaper_theme: 1, ...out }, null, 2)], { type: "application/json" }));
      a.download = "mailreaper-tema.json"; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 2000);
    };
    $("#th-import").onchange = async e => {
      const f = e.target.files[0]; if (!f) return;
      try {
        const j = JSON.parse(await f.text());
        if (!j.mailreaper_theme) throw new Error("geçersiz dosya");
        const next = {};
        Object.keys(DEFAULTS).forEach(k => { if (k !== "wallImg" && j[k] !== undefined && typeof j[k] === typeof DEFAULTS[k]) next[k] = j[k]; });
        if (!/^#[0-9a-f]{6}$/i.test(next.accent || "")) delete next.accent;
        if (next.wall && !WALLS[next.wall]) delete next.wall;
        if (next.board && !BOARDS[next.board]) delete next.board;
        if (next.glass !== undefined) next.glass = Math.max(30, Math.min(100, next.glass));
        if (next.blur !== undefined) next.blur = Math.max(0, Math.min(30, next.blur));
        if (next.scale !== undefined) next.scale = Math.max(85, Math.min(130, next.scale));
        change({ ...next, wallImg: "" }, "Tema içe aktarıldı");
      } catch { $("#th-img-note").textContent = "Tema dosyası okunamadı"; }
      e.target.value = "";
    };
  }

  // ── tetikleyiciler ──
  function bind() {
    $("#open-theme")?.addEventListener("click", open);
    $("#start-theme")?.addEventListener("click", open);
    const menu = document.createElement("div");
    menu.className = "ctx-menu"; menu.style.display = "none";
    menu.innerHTML = `<button data-a="theme">🎨 Kişiselleştir</button><button data-a="reload">🔄 Yenile</button>`;
    document.body.appendChild(menu);
    document.addEventListener("contextmenu", e => {
      if (e.target.closest(".win, .wdlg, .start-menu, .taskbar, input, textarea")) return;     // sadece masaüstü
      e.preventDefault();
      menu.style.display = "block";
      menu.style.left = Math.min(e.clientX, innerWidth - 170) + "px";
      menu.style.top = Math.min(e.clientY, innerHeight - 80) + "px";
    });
    document.addEventListener("click", () => { menu.style.display = "none"; });
    menu.addEventListener("click", e => { const a = e.target.dataset.a; if (a === "theme") open(); if (a === "reload") location.reload(); });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", bind); else bind();

  window.MRTheme = { open, apply: () => apply(theme), get: () => ({ ...theme }) };
})();
