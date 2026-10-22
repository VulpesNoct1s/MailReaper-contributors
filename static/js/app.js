"use strict";

// ═══════════════════════════════════════════
//  STATE
// ═══════════════════════════════════════════
let currentResults = {};
let currentInputs  = {};
let scanStart      = null;
let evtSource      = null;

// ═══════════════════════════════════════════
//  AERO RENKLERİ (açık zemin için koyulaştırılmış tonlar)
// ═══════════════════════════════════════════
const AERO = {
  "#00ff88":"#1e9a47", "#88ff00":"#6aa81a", "#ffcc00":"#d19a00", "#ff8800":"#d96a00",
  "#ff0044":"#c0281c", "#00d4ff":"#2a7ac8", "#ff88aa":"#d9548a", "#ffaa00":"#d98a00",
  "#aa88ff":"#7a5ad6", "#ff6644":"#d9482a", "#ff2255":"#c0281c", "#888":"#7b8696"
};
const aero = c => AERO[String(c || "").toLowerCase()] || c;

// ═══════════════════════════════════════════
//  NAV
// ═══════════════════════════════════════════
document.querySelectorAll(".nav-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".panel").forEach(p => p.classList.remove("active"));
    btn.classList.add("active");
    const panel = document.getElementById(`panel-${btn.dataset.panel}`);
    if (panel) panel.classList.add("active");
    if (btn.dataset.panel === "history") loadHistory();
  });
});

// ═══════════════════════════════════════════
//  INPUTS
// ═══════════════════════════════════════════
const inpEmail    = document.getElementById("inp-email");
const inpUsername = document.getElementById("inp-username");
const inpDomain   = document.getElementById("inp-domain");
const inpName     = document.getElementById("inp-name");
const scanBtn     = document.getElementById("scan-btn");
const clearBtn    = document.getElementById("clear-btn");

// Enter key
[inpEmail, inpUsername, inpDomain, inpName].forEach(el => {
  el.addEventListener("keydown", e => { if (e.key === "Enter") startScan(); });
});

// Auto-fill domain from email
inpEmail.addEventListener("blur", () => {
  const email = inpEmail.value.trim();
  if (email.includes("@") && !inpDomain.value) {
    inpDomain.value = email.split("@")[1];
  }
  if (email.includes("@") && !inpUsername.value) {
    inpUsername.value = email.split("@")[0];
  }
});

scanBtn.addEventListener("click", () => {
  if (scanBtn.classList.contains("scanning")) stopScan();
  else startScan();
});

clearBtn.addEventListener("click", () => {
  [inpEmail, inpUsername, inpDomain, inpName].forEach(el => el.value = "");
  resetUI();
});

// ═══════════════════════════════════════════
//  SCAN
// ═══════════════════════════════════════════
function startScan() {
  const email    = inpEmail.value.trim().toLowerCase();
  const username = inpUsername.value.trim().replace(/^@/, "");
  const domain   = inpDomain.value.trim().toLowerCase();
  const name     = inpName.value.trim();

  if (!email && !username && !domain) {
    shake(inpEmail);
    addLog("En az bir hedef girin (email / kullanıcı adı / domain)", "error", "system");
    return;
  }

  currentInputs = { email, username, domain, name };
  currentResults = {};
  scanStart = Date.now();

  resetUI();
  document.getElementById("progress-section").style.display = "block";
  document.getElementById("results-area").style.display = "block";
  document.getElementById("log-section").style.display = "block";

  scanBtn.classList.add("scanning");
  scanBtn.querySelector(".scan-btn-text").textContent = "DURDUR";
  scanBtn.querySelector(".scan-btn-icon").textContent = "■";

  if (evtSource) evtSource.close();

  const params = new URLSearchParams();
  if (email)    params.set("email",    email);
  if (username) params.set("username", username);
  if (domain)   params.set("domain",   domain);
  if (name)     params.set("name",     name);

  evtSource = new EventSource(`/api/analyze?${params.toString()}`);
  evtSource.onmessage = handleSSE;
  evtSource.onerror   = () => { if (evtSource) { evtSource.close(); evtSource = null; } addLog("Bağlantı kesildi", "error", "system"); finishScan(); };
}

function stopScan() {
  if (evtSource) { evtSource.close(); evtSource = null; }
  finishScan();
}

function finishScan() {
  scanBtn.classList.remove("scanning");
  scanBtn.querySelector(".scan-btn-text").textContent = "TARA";
  scanBtn.querySelector(".scan-btn-icon").textContent = "⚡";
  const elapsed = ((Date.now() - scanStart) / 1000).toFixed(1);
  const el = document.getElementById("scan-time");
  if (el) el.textContent = `⏱ ${elapsed}s`;
  setProgress(100, "Tamamlandı!");
}

// ═══════════════════════════════════════════
//  SSE HANDLER
// ═══════════════════════════════════════════
function handleSSE(event) {
  let msg;
  try { msg = JSON.parse(event.data); } catch { return; }
  const { type, data } = msg;

  switch (type) {
    case "start":
      addLog(`Tarama başlatıldı: ${Object.entries(data.inputs).filter(([,v])=>v).map(([k,v])=>`${k}=${v}`).join(" | ")}`, "info", "system");
      break;
    case "log":
      addLog(data.message, data.level, data.module);
      break;
    case "progress":
      setProgress(data.percent, data.module);
      break;
    case "result":
      currentResults[data.module] = data.data;
      renderModule(data.module, data.data);
      break;
    case "complete":
      currentResults = data.results || currentResults;
      finishScan();
      if (evtSource) { evtSource.close(); evtSource = null; }
      // Re-render correlation + risk with final data
      if (currentResults.correlation) renderModule("correlation", currentResults.correlation);
      if (currentResults.risk_score)  renderModule("risk_score",  currentResults.risk_score);
      showExportBar();
      break;
  }
}

// ═══════════════════════════════════════════
//  PROGRESS
// ═══════════════════════════════════════════
function setStatusText(t) {
  const el = document.getElementById("status-text");
  if (el) el.textContent = t;
}

function setProgress(pct, label) {
  setStatusText(pct >= 100 ? "Hazır" : `Taranıyor: ${label || ""} (%${pct})`);
  document.getElementById("progress-fill").style.width = `${pct}%`;
  document.getElementById("progress-label").textContent = label || "";
  document.getElementById("progress-pct").textContent   = `${pct}%`;
}

// ═══════════════════════════════════════════
//  LOG
// ═══════════════════════════════════════════
function addLog(msg, level = "info", mod = "") {
  const lb = document.getElementById("log-body");
  const entry = document.createElement("div");
  entry.className = `log-entry ${level}`;
  const now = new Date().toLocaleTimeString("tr-TR", { hour12: false });
  entry.innerHTML = `<span class="log-time">${now}</span><span class="log-mod">${esc(mod)}</span><span class="log-msg">${esc(msg)}</span>`;
  lb.appendChild(entry);
  lb.scrollTop = lb.scrollHeight;
}
document.getElementById("log-clear-btn").addEventListener("click", () => {
  document.getElementById("log-body").innerHTML = "";
});

// ═══════════════════════════════════════════
//  MODULE ROUTER
// ═══════════════════════════════════════════
function renderModule(mod, data) {
  switch (mod) {
    case "email_validator":  renderEmailValidator(data); break;
    case "email_parts":      renderEmailParts(data); break;
    case "dns_analysis":     renderDNS(data); break;
    case "web_recon":        renderWebRecon(data); break;
    case "ip_intel":         renderIPIntel(data); break;
    case "smtp_probe":       renderSMTP(data); break;
    case "gravatar":         renderGravatar(data); break;
    case "github_search":    renderGitHubSearch(data); break;
    case "github_deep":      renderGitHubDeep(data); break;
    case "reddit":           renderReddit(data); break;
    case "hackernews":       renderHN(data); break;
    case "username_osint":   renderSherlock(data); break;
    case "social":           renderSocial(data); break;
    case "crt_search":       renderCRT(data); break;
    case "wayback":          renderWayback(data); break;
    case "pastebin":         renderPaste(data); break;
    case "dork_gen":         renderDorks(data); break;
    case "username_gen":     renderUsernameGen(data); break;
    case "exif_analysis":    renderEXIF(data); break;
    case "correlation":      renderCorrelation(data); break;
    case "risk_score":       renderRisk(data); break;
  }
}

// ═══════════════════════════════════════════
//  RENDERERS
// ═══════════════════════════════════════════

function renderEmailValidator(d) {
  show("card-email_validator");
  const b = document.getElementById("badge-email_validator");
  const body = document.getElementById("body-email_validator");
  const ok = d.valid_syntax && d.has_mx && !d.is_disposable;
  b.innerHTML = badge(ok ? "✅ Geçerli" : d.is_disposable ? "⚠️ Disposable" : "❌", ok ? "bg" : d.is_disposable ? "by" : "br");
  body.innerHTML = `
    ${kv("Syntax", badge(d.valid_syntax ? "✅ Geçerli" : "❌", d.valid_syntax ? "bg" : "br"))}
    ${kv("MX Kaydı", badge(d.has_mx ? "✅ Var" : "❌ Yok", d.has_mx ? "bg" : "br"))}
    ${kv("Disposable", badge(d.is_disposable ? "⚠️ Evet" : "✅ Normal", d.is_disposable ? "by" : "bg"))}
    ${kv("Provider", `<span style="color:var(--accent2)">${esc(d.provider || "—")}</span>`)}
    ${kv("Email Tipi", esc(d.email_type || "—"))}
    ${d.md5 ? kv("MD5", mono(d.md5)) : ""}
  `;
}

function renderEmailParts(d) {
  show("card-email_parts");
  document.getElementById("body-email_parts").innerHTML = `
    ${kv("Email", mono(d.email))}
    ${kv("Yerel Kısım", mono(d.local))}
    ${kv("Domain", mono(d.domain))}
    ${kv("TLD", mono(d.tld))}
    ${kv("MD5 Hash", mono(d.md5))}
    ${kv("SHA1", mono(d.sha1))}
    ${kv("SHA256", mono((d.sha256||"").substring(0,32)+"…"))}
  `;
}

function renderDNS(d) {
  show("card-dns_analysis");
  const spf = d.spf || {}; const dmarc = d.dmarc || {}; const ssl = d.ssl || {}; const whois = d.whois || {};
  const b = document.getElementById("badge-dns_analysis");
  b.innerHTML = badge(spf.exists && dmarc.exists ? "✅ Güvenli" : "⚠️ Eksik", spf.exists && dmarc.exists ? "bg" : "by");
  const rl = arr => arr?.length ? `<ul class="record-list">${arr.slice(0,5).map(r=>`<li>${esc(typeof r==="string"?r:(r.exchange||JSON.stringify(r)))}</li>`).join("")}</ul>` : "—";
  document.getElementById("body-dns_analysis").innerHTML = `
    <div class="dns-tabs">
      <button class="dns-tab active" data-t="rec">📋 Kayıtlar</button>
      <button class="dns-tab" data-t="sec">🛡️ Güvenlik</button>
      <button class="dns-tab" data-t="ssl">🔒 SSL</button>
      <button class="dns-tab" data-t="who">📝 WHOIS</button>
    </div>
    <div class="dns-tc active" id="dt-rec">
      ${kv("A",rl(d.a_records))} ${kv("MX",rl(d.mx_records))} ${kv("NS",rl(d.ns_records))}
      ${kv("TXT",d.txt_records?.length?`<ul class="record-list">${d.txt_records.slice(0,4).map(t=>`<li>${esc(t.substring(0,80))}</li>`).join("")}</ul>`:"—")}
    </div>
    <div class="dns-tc" id="dt-sec">
      ${kv("SPF",badge(spf.exists?"✅":"❌",spf.exists?"bg":"br"))}
      ${spf.record?kv("SPF Kaydı",mono(spf.record.substring(0,80))):""}
      ${kv("DMARC",badge(dmarc.exists?"✅":"❌",dmarc.exists?"bg":"br"))}
      ${dmarc.policy?kv("DMARC Policy",badge(dmarc.policy,dmarc.policy==="reject"?"bg":dmarc.policy==="quarantine"?"by":"br")):""}
      ${kv("DKIM",d.dkim_selectors_found?.length?d.dkim_selectors_found.map(s=>`<span class="badge bb">${esc(s)}</span>`).join(" "):"Bulunamadı")}
    </div>
    <div class="dns-tc" id="dt-ssl">
      ${ssl.valid!==undefined?`
        ${kv("Durum",badge(ssl.valid?"✅":"❌",ssl.valid?"bg":"br"))}
        ${ssl.issuer?kv("Yayıncı",esc(ssl.issuer)):""}
        ${ssl.not_after?kv("Bitiş",esc(ssl.not_after)):""}
        ${ssl.days_remaining!==undefined?kv("Kalan",`<span style="color:${ssl.days_remaining<30?"var(--danger)":ssl.days_remaining<90?"var(--warn)":"var(--accent)"}">${ssl.days_remaining} gün</span>`):""}
      `:"<span style='color:var(--muted)'>SSL bilgisi yok</span>"}
    </div>
    <div class="dns-tc" id="dt-who">
      ${whois.registrar?kv("Registrar",esc(whois.registrar)):""}
      ${whois.created?kv("Kayıt",esc(String(whois.created).substring(0,10))):""}
      ${whois.expires?kv("Bitiş",esc(String(whois.expires).substring(0,10))):""}
      ${whois.org?kv("Org",esc(whois.org)):""}
      ${whois.country?kv("Ülke",esc(whois.country)):""}
      ${whois.registrant_name?kv("Kayıtlı Kişi",esc(whois.registrant_name)):""}
      ${whois.emails?.length?kv("WHOIS Email",whois.emails.map(e=>`<span class="badge by">${esc(e)}</span>`).join(" ")):""}
    </div>
  `;
  // Tab switching
  document.getElementById("body-dns_analysis").querySelectorAll(".dns-tab").forEach(tab => {
    tab.addEventListener("click", () => {
      document.getElementById("body-dns_analysis").querySelectorAll(".dns-tab,.dns-tc").forEach(el=>el.classList.remove("active"));
      tab.classList.add("active");
      const tc = document.getElementById(`dt-${tab.dataset.t}`);
      if (tc) tc.classList.add("active");
    });
  });
}

function renderSMTP(d) {
  show("card-smtp_probe");
  const b = document.getElementById("badge-smtp_probe");
  b.innerHTML = badge(d.smtp_reachable?(d.catch_all?"⚠️ Catch-all":"✅"):"❌", d.smtp_reachable?(d.catch_all?"by":"bg"):"br");
  document.getElementById("body-smtp_probe").innerHTML = `
    ${kv("Erişilebilir",badge(d.smtp_reachable?"✅":"❌",d.smtp_reachable?"bg":"br"))}
    ${kv("Sunucu",mono(d.server_used||"—"))}
    ${kv("TLS",badge(d.supports_tls?"✅":"❌",d.supports_tls?"bg":"by"))}
    ${kv("Catch-All",badge(d.catch_all?"⚠️ Evet":"✅ Hayır",d.catch_all?"by":"bg"))}
    ${d.banner?kv("Banner",mono(d.banner.substring(0,70))):""}
    ${d.error?kv("Hata",`<span style="color:var(--muted);font-size:0.77rem">${esc(d.error)}</span>`):""}
  `;
}

function renderGravatar(d) {
  show("card-gravatar");
  document.getElementById("badge-gravatar").innerHTML = badge(d.has_gravatar?"✅ Bulundu":"❌ Yok",d.has_gravatar?"bg":"br");
  let html = d.has_gravatar && d.avatar_url ? `<img src="${esc(d.avatar_url)}" class="avatar-img" onerror="this.style.display='none'">` : "";
  html += `
    ${kv("Hash",mono(d.hash||"—"))}
    ${d.display_name?kv("Ad",esc(d.display_name)):""}
    ${d.location?kv("Konum",esc(d.location)):""}
    ${d.about_me?kv("Hakkında",`<span style="font-size:.78rem">${esc(d.about_me.substring(0,100))}</span>`):""}
    ${d.profile_url?kv("Profil",`<a href="${esc(d.profile_url)}" target="_blank" style="color:var(--accent2)">${esc(d.profile_url)}</a>`):""}
    ${d.accounts?.length?kv("Hesaplar",d.accounts.map(a=>`<span class="badge bb">${esc(a.shortname||a.display)}</span>`).join(" ")):""}
  `;
  document.getElementById("body-gravatar").innerHTML = html;
}

function renderGitHubSearch(d) {
  show("card-github_search");
  const u = d.github_user;
  document.getElementById("badge-github_search").innerHTML = badge(u?"✅ Bulundu":d.commits_found?.length?"⚠️ Commit":"❌",u?"bg":d.commits_found?.length?"by":"br");
  let html = "";
  if (u) {
    html += `${u.avatar_url?`<img src="${esc(u.avatar_url)}" class="avatar-img" onerror="this.style.display='none'">`:""}
      ${kv("Username",`<a href="https://github.com/${esc(u.login)}" target="_blank" style="color:var(--accent2)">@${esc(u.login)}</a>`)}
      ${u.name?kv("Ad",esc(u.name)):""}
      ${u.bio?kv("Bio",`<span style="font-size:.77rem">${esc(u.bio)}</span>`):""}
      ${u.location?kv("Konum",esc(u.location)):""}
      ${kv("Repo",String(u.public_repos||0))} ${kv("Takipçi",String(u.followers||0))}
      ${u.created_at?kv("Kayıt",esc(u.created_at.substring(0,10))):""}`;
  }
  if (d.commits_found?.length) {
    html += `<div style="margin-top:10px"><strong style="color:var(--warn)">⚠️ ${d.commits_found.length} commit'te email:</strong>
    <table class="commit-table"><thead><tr><th>Repo</th><th>Tarih</th><th></th></tr></thead><tbody>`;
    d.commits_found.slice(0,6).forEach(c => {
      html += `<tr><td>${esc(c.repo||"")}</td><td>${esc((c.date||"").substring(0,10))}</td><td><a href="${esc(c.url||"")}" target="_blank">→</a></td></tr>`;
    });
    html += `</tbody></table></div>`;
  }
  if (!u && !d.commits_found?.length) html = `<span style="color:var(--muted)">Bulunamadı</span>`;
  document.getElementById("body-github_search").innerHTML = html;
}

function renderGitHubDeep(d) {
  show("card-github_deep");
  document.getElementById("badge-github_deep").innerHTML = badge(d.found?"✅":"❌", d.found?"bg":"br");
  if (!d.found) {
    document.getElementById("body-github_deep").innerHTML = `<span style="color:var(--muted)">Kullanıcı bulunamadı</span>`;
    return;
  }
  const p = d.profile || {};
  const langs = Object.entries(d.languages||{}).map(([l,c])=>`<span class="lang-badge">${esc(l)}<span style="color:var(--muted);font-size:.65rem"> ${c}</span></span>`).join(" ");
  const orgs = (d.orgs||[]).map(o=>`<a href="${esc(o.url)}" target="_blank" class="badge bb">${esc(o.login)}</a>`).join(" ");
  let html = `
    ${kv("Repo",String(p.public_repos||0))} ${kv("Gist",String(p.public_gists||0))}
    ${kv("Takipçi",String(p.followers||0))} ${kv("Blog",p.blog?`<a href="${esc(p.blog)}" target="_blank" style="color:var(--accent2)">${esc(p.blog)}</a>`:"—")}
    ${langs?kv("Diller",langs):""}
    ${orgs?kv("Organizasyonlar",orgs):""}
  `;
  if (d.repos?.length) {
    html += `<div class="repo-grid">`;
    d.repos.slice(0,6).forEach(r => {
      html += `<div class="repo-item"><div class="repo-name"><a href="${esc(r.url||"")}" target="_blank">${esc(r.name)}</a></div>
        <div class="repo-meta"><span>${r.language||""}</span><span>⭐${r.stars||0}</span><span>🍴${r.forks||0}</span></div></div>`;
    });
    html += `</div>`;
  }
  document.getElementById("body-github_deep").innerHTML = html;
}

function renderReddit(d) {
  show("card-reddit");
  document.getElementById("badge-reddit").innerHTML = badge(d.found?"✅ Bulundu":"❌",d.found?"bg":"br");
  if (!d.found) {
    document.getElementById("body-reddit").innerHTML = `<span style="color:var(--muted)">u/${esc(d.username)} bulunamadı</span>`;
    return;
  }
  const p = d.profile || {};
  const subs = (d.subreddits||[]).slice(0,15).map(s=>`<span class="sub-chip">r/${esc(s)}</span>`).join("");
  let html = `
    ${p.icon_img?`<img src="${esc(p.icon_img)}" class="avatar-img" onerror="this.style.display='none'">` :""}
    ${kv("Kullanıcı",`<a href="${esc(p.profile_url||"")}" target="_blank" style="color:var(--accent2)">u/${esc(p.username||"")}</a>`)}
    ${kv("Toplam Karma",String(p.total_karma||0))}
    ${kv("Link Karma",String(p.link_karma||0))}
    ${kv("Yorum Karma",String(p.comment_karma||0))}
    ${kv("Kayıt",esc(p.created_utc||"—"))}
    ${kv("Gold",badge(p.is_gold?"✅":"❌",p.is_gold?"bg":"br"))}
    ${subs?`<div style="margin-top:8px"><span style="font-size:.73rem;color:var(--muted)">Aktif Subredditler:</span><div class="subreddit-cloud">${subs}</div></div>`:""}
  `;
  if (d.recent_posts?.length) {
    html += `<div style="margin-top:10px"><span style="font-size:.73rem;color:var(--muted)">Son Gönderiler:</span>`;
    d.recent_posts.slice(0,4).forEach(post => {
      html += `<div class="reddit-post">
        <div class="reddit-post-title"><a href="${esc(post.url||"")}" target="_blank" style="color:var(--text)">${esc((post.title||"").substring(0,80))}</a></div>
        <div class="reddit-post-meta">r/${esc(post.subreddit)} • ⬆${post.score} • ${esc(post.created||"")}</div>
      </div>`;
    });
    html += `</div>`;
  }
  document.getElementById("body-reddit").innerHTML = html;
}

function renderHN(d) {
  show("card-hackernews");
  document.getElementById("badge-hackernews").innerHTML = badge(d.found?"✅":"❌",d.found?"bg":"br");
  if (!d.found) {
    document.getElementById("body-hackernews").innerHTML = `<span style="color:var(--muted)">Bulunamadı</span>`;
    return;
  }
  const p = d.profile || {};
  let html = `
    ${kv("Kullanıcı",`<a href="${esc(p.profile_url||"")}" target="_blank" style="color:var(--accent2)">${esc(p.username||"")}</a>`)}
    ${kv("Karma",String(p.karma||0))}
    ${kv("Kayıt",esc(p.created||"—"))}
    ${kv("Gönderi",String(p.submitted_count||0))}
    ${p.about?kv("Hakkında",`<span style="font-size:.77rem">${esc(p.about.replace(/<[^>]*>/g,"").substring(0,150))}</span>`):""}
  `;
  document.getElementById("body-hackernews").innerHTML = html;
}

function renderSherlock(d) {
  show("card-username_osint");
  const found = d.found || [];
  document.getElementById("sherlock-count").innerHTML = badge(`${d.found_count}/${d.total_checked}`, d.found_count > 10 ? "br" : d.found_count > 0 ? "by" : "bb");
  const confCls = c => c >= 85 ? "conf-hi" : c >= 65 ? "conf-mid" : "conf-lo";
  const byCat = {};
  found.forEach(p => { (byCat[p.category || "Diğer"] = byCat[p.category || "Diğer"] || []).push(p); });
  const groups = Object.entries(byCat).map(([cat, items]) => `
    <div class="cat-title">${esc(cat)} (${items.length})</div>
    <div class="platform-grid">
      ${items.map(p => `<a href="${esc(p.url)}" target="_blank" rel="noopener" class="platform-chip found" title="${esc(p.title || "")}">🌐 ${esc(p.platform)}${p.confidence ? ` <span class="conf ${confCls(p.confidence)}">%${p.confidence}</span>` : ""}</a>`).join("")}
    </div>`).join("");
  document.getElementById("body-username_osint").innerHTML = `
    <div class="sherlock-stats">
      <div class="sherlock-stat"><div class="sherlock-stat-num" style="color:var(--accent)">${d.found_count}</div><div class="sherlock-stat-label">Bulunan</div></div>
      <div class="sherlock-stat"><div class="sherlock-stat-num" style="color:var(--muted)">${d.not_found_count}</div><div class="sherlock-stat-label">Bulunamayan</div></div>
      <div class="sherlock-stat"><div class="sherlock-stat-num" style="color:var(--accent2)">${d.total_checked}</div><div class="sherlock-stat-label">Taranan</div></div>
      <div style="font-size:11px;color:var(--muted);max-width:340px">Yüzde, eşleşmenin güvenilirliğidir: site, var olmayan rastgele bir kullanıcı adına verdiği yanıtla karşılaştırılır (soft-404 elemesi).</div>
    </div>
    ${groups || `<span style="color:var(--muted)">Profil bulunamadı</span>`}
    ${(d.possible || []).length ? `<details class="possible-box"><summary>Olası eşleşmeler (${d.possible.length}) — düşük güven, doğrulanmadı</summary>
      <div class="platform-grid" style="margin-top:6px">${d.possible.map(p => `<a href="${esc(p.url)}" target="_blank" rel="noopener" class="platform-chip found" title="${esc(p.title || "")}">🌐 ${esc(p.platform)} <span class="conf conf-lo">%${p.confidence}</span></a>`).join("")}</div></details>` : ""}
  `;
}

function renderWebRecon(d) {
  show("card-web_recon");
  const bd = document.getElementById("badge-web_recon");
  if (!d.reachable) {
    bd.innerHTML = badge("Erişilemedi", "br");
    document.getElementById("body-web_recon").innerHTML = `<span style="color:var(--muted)">${esc(d.error || "Siteye bağlanılamadı")}</span>`;
    return;
  }
  const gcol = { A:"#1e9a47", B:"#6aa81a", C:"#d19a00", D:"#d96a00", F:"#c0281c" }[d.security_grade] || "#7b8696";
  bd.innerHTML = badge(`${d.status} · ${(d.technologies || []).length} teknoloji`, d.https ? "bg" : "by");
  const sec = Object.entries(d.security_headers || {}).map(([k, v]) =>
    `<div class="sec-item ${v.present ? "ok" : "miss"}" title="${esc(v.value)}">${v.present ? "✔" : "✖"} ${esc(k)}</div>`).join("");
  const files = Object.entries(d.files || {}).map(([k, v]) => `
    <div class="file-row"><span class="kk" style="min-width:110px">${esc(k)}</span>
      <span>${v.exists ? `${badge("var", "bg")} <a href="${esc(v.url)}" target="_blank" rel="noopener" class="search-link">aç</a>` : badge("yok", "bb")}
      ${v.disallowed?.length ? `<div style="font-size:11px;color:var(--muted);margin-top:2px">Disallow: ${v.disallowed.slice(0, 8).map(esc).join(" · ")}${v.disallowed.length > 8 ? " …" : ""}</div>` : ""}
      ${v.contacts?.length ? `<div style="font-size:11px;color:var(--muted)">İletişim: ${v.contacts.map(esc).join(", ")}</div>` : ""}</span></div>`).join("");
  document.getElementById("body-web_recon").innerHTML = `
    <div class="recon-head"><div class="grade-big" style="color:${gcol}">${esc(d.security_grade)}</div>
      <div><div style="font-weight:600">${esc(d.title || d.domain)}</div>
      <div style="font-size:11.5px;color:var(--muted)">${esc(d.description || "")}</div></div></div>
    ${kv("Son URL", `<a href="${esc(d.final_url)}" target="_blank" rel="noopener" style="color:var(--accent2)">${esc(d.final_url)}</a>`)}
    ${kv("Sunucu", mono(d.server || "—"))}
    ${d.powered_by ? kv("X-Powered-By", mono(d.powered_by)) : ""}
    ${(d.redirects || []).length ? kv("Yönlendirme", d.redirects.map(r => `${r.status} → ${esc(r.url)}`).join("<br>")) : ""}
    ${(d.technologies || []).length ? kv("Teknolojiler", d.technologies.map(t => `<span class="lang-badge">${esc(t)}</span>`).join(" ")) : ""}
    <div class="cat-title">Güvenlik başlıkları (${d.security_score}/100)</div>
    <div class="sec-grid">${sec}</div>
    <div class="cat-title">Standart dosyalar</div>${files}
    ${(d.emails || []).length ? `<div class="cat-title">Sayfada bulunan email'ler</div><div class="chip-wrap">${d.emails.map(e => `<span class="chip">${esc(e)}</span>`).join("")}</div>` : ""}
    ${(d.social_links || []).length ? `<div class="cat-title">Sosyal bağlantılar</div><div class="search-links">${d.social_links.map(u => `<a class="search-link" target="_blank" rel="noopener" href="${esc(u)}">${esc(u)}</a>`).join("")}</div>` : ""}
    ${d.favicon ? kv("Favicon hash", mono(d.favicon.mmh3)) : ""}
    <div class="reverse-links">${(d.dork_links || []).map(l => `<a class="reverse-link" target="_blank" rel="noopener" href="${esc(l.url)}">${esc(l.label)}</a>`).join("")}</div>`;
}

function renderIPIntel(d) {
  show("card-ip_intel");
  document.getElementById("badge-ip_intel").innerHTML = badge(`${(d.ips || []).length} IP`, d.behind_cdn ? "by" : "bb");
  if (!(d.ips || []).length) {
    document.getElementById("body-ip_intel").innerHTML = `<span style="color:var(--muted)">${esc(d.error || "IP bulunamadı")}</span>`;
    return;
  }
  document.getElementById("body-ip_intel").innerHTML = `
    <table class="ip-table"><tr><th>IP</th><th>PTR</th><th>ASN</th><th>Ağ sahibi</th><th>Ülke</th><th>Prefix</th></tr>
    ${d.ips.map(i => `<tr><td>${esc(i.ip)}</td><td>${esc(i.ptr || "—")}</td><td>${esc(i.asn || "—")}</td><td>${esc(i.org || "—")}</td><td>${esc(i.country || "—")}</td><td>${esc(i.prefix || "—")}</td></tr>`).join("")}</table>
    ${(d.ipv6 || []).length ? kv("IPv6", d.ipv6.map(mono).join(" ")) : ""}
    ${d.behind_cdn ? `<div style="margin-top:8px">${badge("CDN / bulut sağlayıcı arkasında — gerçek sunucu IP'si gizli olabilir", "by")}</div>` : ""}
    <div class="reverse-links">${(d.links || []).map(l => `<a class="reverse-link" target="_blank" rel="noopener" href="${esc(l.url)}">${esc(l.label)}</a>`).join("")}</div>`;
}

function renderSocial(d) {
  show("card-social");
  const found = d.found || [];
  document.getElementById("badge-social").innerHTML = badge(`${found.length} profil`, found.length > 5 ? "br" : found.length > 0 ? "by" : "bb");
  document.getElementById("body-social").innerHTML = `
    <div class="social-grid">
      ${found.map(p=>`<a href="${esc(p.url)}" target="_blank" class="platform-chip found">🌐 ${esc(p.platform)}</a>`).join("")}
    </div>
    ${!found.length ? `<span style="color:var(--muted)">Profil bulunamadı</span>` : ""}
  `;
}

function renderCRT(d) {
  show("card-crt_search");
  const emailEntries = d.email_results?.entries || [];
  const subdomains   = d.all_subdomains || [];
  document.getElementById("badge-crt_search").innerHTML = badge(`${emailEntries.length} cert | ${subdomains.length} subdomain`, emailEntries.length > 0 ? "by" : "bb");
  let html = `${kv("Email Sertifika Kaydı",String(emailEntries.length))} ${kv("Subdomain",String(subdomains.length))}`;
  if (emailEntries.length > 0) {
    html += `<div style="margin-top:8px"><span style="font-size:.73rem;color:var(--muted)">Son sertifikalar:</span>`;
    emailEntries.slice(0,8).forEach(e => {
      html += `${kv(esc(e.name||""),`<span style="color:var(--muted);font-size:.73rem">${esc(e.issuer?.substring(0,40)||"")} | ${esc((e.not_before||"").substring(0,10))} → ${esc((e.not_after||"").substring(0,10))}</span>`)}`;
    });
    html += `</div>`;
  }
  if (subdomains.length > 0) {
    html += `<div style="margin-top:10px"><span style="font-size:.73rem;color:var(--muted)">Subdomainler:</span><div class="subdomain-list">`;
    subdomains.slice(0,30).forEach(s => { html += `<span class="subdomain-chip">${esc(s)}</span>`; });
    html += `</div></div>`;
  }
  document.getElementById("body-crt_search").innerHTML = html;
}

function renderWayback(d) {
  show("card-wayback");
  const uh = d.username_history || {};
  const dh = d.domain_history   || {};
  const snaps = uh.platforms_archived || [];
  document.getElementById("badge-wayback").innerHTML = badge(`${snaps.length} platform`, snaps.length > 0 ? "by" : "bb");
  let html = `${kv("Arşivlenen Platform",String(snaps.length))} ${kv("Domain Snapshot",String(dh.total||0))}`;
  if (dh.first_seen) html += `${kv("Domain İlk Görülme",esc(dh.first_seen))} ${kv("Domain Son Görülme",esc(dh.last_seen||"—"))}`;
  if (snaps.length) {
    html += `<div style="margin-top:10px">`;
    snaps.forEach(p => {
      const latest = p.latest || {};
      html += `<div class="wayback-platform">
        <span><strong>${esc(p.platform)}</strong> <span class="wb-latest">(${p.snapshot_count} snapshot)</span></span>
        ${latest.wayback_url ? `<a href="${esc(latest.wayback_url)}" target="_blank" class="wb-link">📸 ${esc(latest.date_formatted||"")} →</a>` : ""}
      </div>`;
    });
    html += `</div>`;
  }
  document.getElementById("body-wayback").innerHTML = html;
}

function renderPaste(d) {
  show("card-pastebin");
  const findings = d.findings || [];
  const hasStealer = findings.some(f => (f.source||"").includes("Stealer"));
  document.getElementById("badge-pastebin").innerHTML = badge(hasStealer?"🔴 Stealer!":findings.length>0?"⚠️ Sızıntı":"✅ Temiz", hasStealer?"br":findings.length?"by":"bg");
  let html = "";
  if (hasStealer) html += `<div class="stealer-alert">🔴 STEALER LOG BULUNDU! Şifrelerinizi hemen değiştirin!</div>`;
  html += kv("Bulunan",String(findings.length));
  findings.forEach(f => {
    const isS = (f.source||"").includes("Stealer");
    html += `<div class="paste-item ${isS?"stealer":""}">
      <div class="paste-source" style="color:${isS?"var(--danger)":"var(--warn)"}">${esc(f.source||"")}</div>
      ${f.url?`<div><a href="${esc(f.url)}" target="_blank" class="paste-link">${esc(f.url)}</a></div>`:""}
      ${f.computer_name?`<div class="paste-detail">💻 ${esc(f.computer_name)} | ${esc(f.operating_system||"")}</div>`:""}
      ${f.date_compromised?`<div class="paste-detail">📅 ${esc(f.date_compromised)}</div>`:""}
      ${f.credentials_count>0?`<div class="paste-detail" style="color:var(--danger)">🔑 ${f.credentials_count} kimlik bilgisi</div>`:""}
    </div>`;
  });
  if (d.search_urls?.length) {
    html += `<div class="search-links">`;
    d.search_urls.forEach(u => { html += `<a href="${esc(u.url)}" target="_blank" class="search-link">🔗 ${esc(u.name)}</a>`; });
    html += `</div>`;
  }
  document.getElementById("body-pastebin").innerHTML = html;
}

function renderDorks(d) {
  show("card-dork_gen");
  const all = d.all_queries || [];
  document.getElementById("badge-dork_gen").innerHTML = badge(`${all.length} sorgu`, "bb");

  const categories = ["google", "github", "paste_dorks", "shodan", "specialized"];
  const catLabels  = {google:"Google",github:"GitHub",paste_dorks:"Paste",shodan:"Shodan",specialized:"Diğer"};

  let tabsHtml = `<div class="dork-tabs">`;
  let contentHtml = "";

  categories.forEach((cat, i) => {
    const items = d[cat] || [];
    if (!items.length) return;
    tabsHtml += `<button class="dork-tab${i===0?" active":""}" data-dcat="${cat}">${catLabels[cat]||cat} (${items.length})</button>`;
    contentHtml += `<div class="dork-tc${i===0?" active":""}" id="dc-${cat}">`;
    items.forEach(item => {
      if (item.query) {
        contentHtml += `<div class="dork-item">
          <span class="dork-label">${esc(item.label||"")}</span>
          <span class="dork-query">${esc(item.query)}</span>
          <a href="https://www.google.com/search?q=${encodeURIComponent(item.query)}" target="_blank" class="dork-open">Ara →</a>
        </div>`;
      } else if (item.url) {
        contentHtml += `<div class="dork-item">
          <span class="dork-label">${esc(item.label||"")}</span>
          <a href="${esc(item.url)}" target="_blank" class="dork-open">Aç →</a>
        </div>`;
      }
    });
    contentHtml += `</div>`;
  });

  tabsHtml += `</div>`;
  document.getElementById("body-dork_gen").innerHTML = tabsHtml + contentHtml;

  document.getElementById("body-dork_gen").querySelectorAll(".dork-tab").forEach(tab => {
    tab.addEventListener("click", () => {
      document.getElementById("body-dork_gen").querySelectorAll(".dork-tab,.dork-tc").forEach(el=>el.classList.remove("active"));
      tab.classList.add("active");
      const tc = document.getElementById(`dc-${tab.dataset.dcat}`);
      if (tc) tc.classList.add("active");
    });
  });
}

function renderUsernameGen(d) {
  show("card-username_gen");
  const uns = d.usernames || [];
  document.getElementById("badge-username_gen").innerHTML = badge(`${uns.length} adet`, "bb");
  let html = `${kv("Yerel Kısım",mono(d.local_part||""))} ${kv("Üretilen",String(uns.length))}
    <div class="chip-wrap">`;
  uns.slice(0,60).forEach(u => { html += `<span class="chip" onclick="navigator.clipboard.writeText('${esc(u)}')" title="Kopyala">${esc(u)}</span>`; });
  if (uns.length > 60) html += `<span style="color:var(--muted);font-size:.73rem">+${uns.length-60} daha...</span>`;
  html += `</div>`;
  document.getElementById("body-username_gen").innerHTML = html;
}

function renderEXIF(data) {
  if (!Array.isArray(data) || !data.length) return;
  show("card-exif_analysis");
  document.getElementById("badge-exif_analysis").innerHTML = badge(`${data.length} fotoğraf`, "bb");
  let html = "";
  data.forEach(r => {
    const info = r.image_info || {};
    const exif = r.exif || {};
    html += `<div class="exif-item">
      <div style="overflow:hidden;margin-bottom:6px">
        <img src="${esc(r.url)}" class="exif-img" onerror="this.style.display='none'">
        <div style="font-size:.75rem;color:var(--muted)">${esc(r.url?.substring(0,60)||"")}...</div>
        ${info.format?kv("Format",`${esc(info.format)} ${info.width?`${info.width}×${info.height}`:""}`):""}
        ${info.file_size_kb?kv("Boyut",`${info.file_size_kb} KB`):""}
        ${info.md5?kv("MD5",mono(info.md5)):""}
        ${exif.has_exif?`<span class="badge by">⚠️ EXIF Verisi Var</span>`:""}
        ${exif.xmp_software?kv("Yazılım",esc(exif.xmp_software)):""}
        ${exif.xmp_create_date?kv("Oluşturma",esc(exif.xmp_create_date)):""}
        ${exif.comment?kv("Yorum",esc(exif.comment)):""}
      </div>
      ${r.reverse_search_urls?.length?`<div><span style="font-size:.72rem;color:var(--muted)">Tersine Görüntü Arama:</span><div class="reverse-links">${r.reverse_search_urls.map(u=>`<a href="${esc(u.url)}" target="_blank" class="reverse-link">${esc(u.name)}</a>`).join("")}</div></div>`:""}
    </div>`;
  });
  document.getElementById("body-exif_analysis").innerHTML = html;
}

function renderCorrelation(d) {
  show("card-correlation");
  const body = document.getElementById("body-correlation");
  const items = [
    { label: "İsimler",       val: d.identified_names?.join(", ")          || "—" },
    { label: "Kullanıcı Adı", val: d.identified_usernames?.join(", ")      || "—", hl: true },
    { label: "Konumlar",      val: d.identified_locations?.join(", ")      || "—" },
    { label: "Organizasyon",  val: d.identified_orgs?.join(", ")           || "—" },
    { label: "Platformlar",   val: d.identified_platforms?.length ? `${d.identified_platforms.length} platform` : "—", hl: true },
    { label: "Domainler",     val: d.identified_domains?.slice(0,5).join(", ") || "—" },
    { label: "Bağlı Email",   val: d.identified_emails?.join(", ")         || "—" },
    { label: "Diller",        val: d.identified_languages?.join(", ")      || "—" },
  ];

  let html = items.map(i => `<div class="intel-item">
    <span class="intel-item-label">${esc(i.label)}</span>
    <span class="intel-item-value${i.hl?" highlight":""}">${esc(i.val)}</span>
  </div>`).join("");

  if (d.summary) {
    html += `<div class="intel-summary">${esc(d.summary)}</div>`;
  }

  if (d.connections?.length) {
    html += `<div class="intel-connections" style="grid-column:1/-1">
      <div style="font-size:.73rem;color:var(--muted);margin-bottom:6px">Tespit Edilen Bağlantılar:</div>`;
    d.connections.forEach(c => {
      html += `<div class="intel-conn-item">🔗 ${esc(c.description)} <span style="color:var(--accent);font-size:.72rem">(Güven: ${c.confidence}%)</span></div>`;
    });
    html += `</div>`;
  }

  if (d.timeline?.length) {
    html += `<div style="grid-column:1/-1">
      <div style="font-size:.73rem;color:var(--muted);margin-bottom:6px;margin-top:10px">Timeline:</div>
      <div class="timeline">`;
    d.timeline.forEach(e => {
      html += `<div class="tl-item">
        <span class="tl-dot"></span>
        <span class="tl-date">${esc(e.date||"—")}</span>
        <span class="tl-source">${esc(e.source||"")}</span>
        <span class="tl-event">${esc(e.event||"")}</span>
      </div>`;
    });
    html += `</div></div>`;
  }

  body.innerHTML = html;

  // Network graph
  if (d.graph?.nodes?.length > 1) {
    renderGraph(d.graph);
  }
}

function renderRisk(d) {
  if (!d || d.total === undefined) return;
  show("card-risk");

  const score = d.total;
  const gc    = aero(d.grade_color || "#888");

  animCounter(document.getElementById("risk-num"), 0, score, 1200);

  const arc  = document.getElementById("risk-arc");
  const circ = 326.7;
  arc.style.strokeDashoffset = circ - (score / 100) * circ;
  arc.style.stroke = gc;
  document.getElementById("risk-num").style.color = gc;

  document.getElementById("risk-grade").textContent     = d.grade || "?";
  document.getElementById("risk-grade").style.color     = gc;
  document.getElementById("risk-grade-text").textContent = d.grade_text || "";

  const cats = [
    { key:"identity_exposure",   label:"Kimlik İfşası",   max:30 },
    { key:"email_validity",      label:"Email Geçerliliği",max:20 },
    { key:"infrastructure_risk", label:"Altyapı",          max:20 },
    { key:"leak_breach_risk",    label:"Sızıntı",          max:30 },
  ];
  const cat = d.category_scores || {};
  document.getElementById("risk-cat-bars").innerHTML = cats.map(c => `
    <div class="cat-bar-item">
      <label><span>${c.label}</span><span>${cat[c.key]||0}/${c.max}</span></label>
      <div class="cat-bar-track"><div class="cat-bar-fill" style="width:${Math.min((cat[c.key]||0)/c.max*100,100).toFixed(0)}%;background:${gc}"></div></div>
    </div>`).join("");

  const fl = document.getElementById("risk-factors-list");
  fl.innerHTML = (d.risk_factors || []).map(f => `<div class="risk-factor-item">${esc(f)}</div>`).join("");
}

// ═══════════════════════════════════════════
//  SIMPLE NETWORK GRAPH (canvas)
// ═══════════════════════════════════════════
function renderGraph(graphData) {
  show("card-graph");
  document.getElementById("graph-node-count").innerHTML = badge(`${graphData.nodes.length} node`, "bb");

  const container = document.getElementById("graph-container");
  container.innerHTML = `<canvas id="graph-canvas" class="graph-canvas"></canvas>`;
  const canvas = document.getElementById("graph-canvas");
  canvas.width = container.clientWidth;
  canvas.height = 300;
  const ctx = canvas.getContext("2d");

  const W = canvas.width, H = canvas.height;
  const nodes = graphData.nodes.map((n, i) => ({
    ...n,
    x: W/2 + Math.cos(i / graphData.nodes.length * Math.PI * 2) * (Math.min(W,H)*0.35),
    y: H/2 + Math.sin(i / graphData.nodes.length * Math.PI * 2) * (H*0.35),
    vx: 0, vy: 0,
  }));
  // Center node
  if (nodes.length > 0) { nodes[0].x = W/2; nodes[0].y = H/2; }

  const colorMap = Object.fromEntries(Object.entries({
    center:"#00ff88", platform:"#00d4ff", name:"#ff88aa",
    username:"#ffaa00", location:"#aa88ff", org:"#ff6644",
  }).map(([k, v]) => [k, aero(v)]));

  function draw() {
    ctx.clearRect(0, 0, W, H);
    // Edges
    graphData.edges.forEach(e => {
      const s = nodes.find(n => n.id === e.source);
      const t = nodes.find(n => n.id === e.target);
      if (!s || !t) return;
      ctx.beginPath();
      ctx.moveTo(s.x, s.y);
      ctx.lineTo(t.x, t.y);
      ctx.strokeStyle = "rgba(42,122,200,0.35)";
      ctx.lineWidth = 1;
      ctx.stroke();
    });
    // Nodes
    nodes.forEach(n => {
      const r = n.group === "center" ? 14 : 9;
      const color = colorMap[n.group] || "#888";
      ctx.beginPath();
      ctx.arc(n.x, n.y, r, 0, Math.PI * 2);
      ctx.fillStyle = color + "33";
      ctx.fill();
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.stroke();
      // Label
      ctx.fillStyle = color;
      ctx.font = `${n.group==="center"?"700 11px":"9px"} Segoe UI`;
      ctx.textAlign = "center";
      ctx.fillText((n.label || "").substring(0,18), n.x, n.y + r + 12);
    });
  }
  draw();
}

// ═══════════════════════════════════════════
//  EXPORT
// ═══════════════════════════════════════════
function showExportBar() {
  const bar = document.getElementById("card-correlation");
  if (bar) bar.style.display = "block";
}

document.getElementById("export-json-btn").addEventListener("click", () => exportData("json"));
document.getElementById("export-html-btn").addEventListener("click", () => exportData("html"));

async function exportData(fmt) {
  try {
    const resp = await fetch(`/api/export/${fmt}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: currentInputs.email || currentInputs.username || "target", inputs: currentInputs, results: currentResults })
    });
    if (!resp.ok) throw new Error(await resp.text());
    const blob = await resp.blob();
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement("a");
    a.href = url;
    a.download = `mailreaper_${(currentInputs.email || currentInputs.username || "target").replace("@","_at_")}.${fmt === "html" ? "html" : "json"}`;
    a.click();
    URL.revokeObjectURL(url);
  } catch(e) { addLog(`Export hatası: ${e.message}`, "error", "export"); }
}

// ═══════════════════════════════════════════
//  HISTORY
// ═══════════════════════════════════════════
let histTimer = null;
async function loadHistory(q = "") {
  const el = document.getElementById("history-list");
  el.innerHTML = `<div class="empty-state">Yükleniyor...</div>`;
  try {
    const data = await (await fetch("/api/history" + (q ? `?q=${encodeURIComponent(q)}` : ""))).json();
    if (!data.length) { el.innerHTML = `<div class="empty-state">📭 ${q ? "Eşleşen kayıt yok." : "Henüz arama yok."}</div>`; return; }
    el.innerHTML = data.map(item => {
      const gc = gradeColor(item.risk_grade);
      const target = item.email || item.username || item.domain || "?";
      const meta   = [item.email, item.username, item.domain].filter(Boolean).join(" | ");
      return `<div class="history-item" onclick="loadHistoryItem(${item.id})">
        <div class="hist-grade" style="background:${gc}22;color:${gc}">${item.risk_grade||"?"}</div>
        <div>
          <div class="hist-email">${item.scan_type === "target" ? "🎯 " : ""}${esc(target)}</div>
          <div class="hist-meta">${esc(meta)} — ${esc(fmtDate(item.timestamp))}</div>
        </div>
        <div class="hist-score">Risk: ${item.risk_score??"-"}/100</div>
        <button class="hist-del" title="Sil" onclick="delHistory(event,${item.id})">×</button>
      </div>`;
    }).join("");
  } catch(e) { el.innerHTML = `<div class="empty-state">Hata: ${esc(e.message)}</div>`; }
}

document.getElementById("hist-search")?.addEventListener("input", e => {
  clearTimeout(histTimer);
  histTimer = setTimeout(() => loadHistory(e.target.value.trim()), 250);
});
document.getElementById("hist-clear-all")?.addEventListener("click", async () => {
  if (!confirm("Tüm geçmiş silinsin mi?")) return;
  await fetch("/api/history", { method: "DELETE" });
  loadHistory();
});

async function loadHistoryItem(id) {
  try {
    const results = await (await fetch(`/api/history/${id}`)).json();
    if (results._scan_type === "target") { loadTargetHistoryItem(results); return; }
    // Switch to scan panel
    document.querySelectorAll(".nav-btn").forEach(b=>b.classList.remove("active"));
    document.querySelectorAll(".panel").forEach(p=>p.classList.remove("active"));
    document.querySelector('[data-panel="scan"]').classList.add("active");
    document.getElementById("panel-scan").classList.add("active");

    currentResults = results;
    resetUI();
    document.getElementById("results-area").style.display = "block";
    document.getElementById("log-section").style.display = "none";

    // Populate inputs
    if (results.email_parts) {
      inpEmail.value    = results.email_parts.email    || "";
      inpDomain.value   = results.email_parts.domain   || "";
      inpUsername.value = results.email_parts.local    || "";
    }

    // Render all modules
    Object.entries(results).forEach(([mod, data]) => { renderModule(mod, data); });
    showExportBar();
    document.getElementById("scan-time").textContent = "📜 Geçmişten yüklendi";
  } catch(e) { console.error(e); }
}

async function delHistory(event, id) {
  event.stopPropagation();
  if (!confirm("Sil?")) return;
  await fetch(`/api/history/${id}`, { method: "DELETE" });
  loadHistory();
}

// ═══════════════════════════════════════════
//  HELPERS
// ═══════════════════════════════════════════
function show(id) {
  const el = document.getElementById(id);
  if (el) el.style.display = "";
}

function resetUI() {
  document.querySelectorAll(".result-card, #card-correlation, #card-risk, #card-graph").forEach(c => c.style.display = "none");
  document.getElementById("results-area").style.display = "none";
  document.getElementById("progress-section").style.display = "none";
  document.getElementById("log-section").style.display = "none";
  document.getElementById("log-body").innerHTML = "";
  setProgress(0, "");
}

function kv(key, val) {
  return `<div class="kv"><span class="kk">${key}</span><span class="kv-val">${val}</span></div>`;
}

function badge(text, cls = "bb") {
  return `<span class="badge ${cls}">${text}</span>`;
}

function mono(text) {
  return `<span class="mono">${esc(String(text||""))}</span>`;
}

function esc(str) {
  return String(str||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}

function gradeColor(g) {
  return aero({ A:"#00ff88", B:"#88ff00", C:"#ffcc00", D:"#ff8800", F:"#ff0044", "?":"#888" }[g] || "#888");
}

function fmtDate(iso) {
  if (!iso) return "—";
  try { return new Date(iso).toLocaleString("tr-TR"); } catch { return iso; }
}

function animCounter(el, from, to, ms) {
  const start = Date.now();
  const step = () => {
    const p = Math.min((Date.now()-start)/ms, 1);
    el.textContent = Math.round(from + (to-from)*(1-Math.pow(1-p,3)));
    if (p < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

function shake(el) {
  el.style.animation = "none"; el.offsetHeight;
  el.style.animation = "shake .4s ease";
  setTimeout(() => el.style.animation = "", 400);
}

// Shake keyframe
const s = document.createElement("style");
s.textContent = `@keyframes shake{0%,100%{transform:translateX(0)}20%{transform:translateX(-8px)}40%{transform:translateX(8px)}60%{transform:translateX(-6px)}80%{transform:translateX(6px)}}`;
document.head.appendChild(s);

// ═══════════════════════════════════════════
//  TARGET PROFILE PANEL
// ═══════════════════════════════════════════

let targetResults  = {};
let targetInputs   = {};
let targetStart    = null;
let targetEvtSrc   = null;

// Input field map
const TARGET_FIELDS = [
  "name","email","phone","domain",
  "instagram","twitter","youtube","tiktok","spotify",
  "reddit","github","steam","telegram","discord","linkedin","facebook","username"
];

// Count filled fields & update indicator
function updateFilledCount() {
  let count = 0;
  TARGET_FIELDS.forEach(id => {
    const el = document.getElementById(`t-${id}`);
    if (!el) return;
    const filled = el.value.trim().length > 0;
    el.classList.toggle("filled", filled);
    if (filled) count++;
  });
  const fc = document.getElementById("target-filled-count");
  if (fc) fc.textContent = count > 0 ? `${count} alan dolduruldu` : "";
}

TARGET_FIELDS.forEach(id => {
  const el = document.getElementById(`t-${id}`);
  if (el) el.addEventListener("input", updateFilledCount);
});

// Scan button
const targetScanBtn  = document.getElementById("target-scan-btn");
const targetClearBtn = document.getElementById("target-clear-btn");

if (targetScanBtn) {
  targetScanBtn.addEventListener("click", () => {
    if (targetScanBtn.classList.contains("scanning")) stopTargetScan();
    else startTargetScan();
  });
}
if (targetClearBtn) {
  targetClearBtn.addEventListener("click", () => {
    TARGET_FIELDS.forEach(id => {
      const el = document.getElementById(`t-${id}`);
      if (el) el.value = "";
    });
    resetTargetUI();
    updateFilledCount();
  });
}
document.getElementById("target-log-clear")?.addEventListener("click", () => {
  document.getElementById("target-log-body").innerHTML = "";
});

function startTargetScan() {
  const params = new URLSearchParams();
  let hasAny = false;
  TARGET_FIELDS.forEach(id => {
    const el = document.getElementById(`t-${id}`);
    if (el && el.value.trim()) {
      params.set(id === "username" ? "username" : id, el.value.trim());
      hasAny = true;
    }
  });

  if (!hasAny) {
    alert("En az bir alan doldur!");
    return;
  }

  targetInputs  = Object.fromEntries(params.entries());
  targetResults = {};
  targetStart   = Date.now();

  resetTargetUI();
  document.getElementById("target-progress").style.display     = "block";
  document.getElementById("target-results").style.display      = "block";
  document.getElementById("target-log-section").style.display  = "block";

  targetScanBtn.classList.add("scanning");
  targetScanBtn.querySelector(".scan-btn-text").textContent = "DURDURULUYOR...";
  targetScanBtn.querySelector(".scan-btn-icon").textContent  = "■";

  if (targetEvtSrc) targetEvtSrc.close();
  targetEvtSrc = new EventSource(`/api/target-scan?${params.toString()}`);
  targetEvtSrc.onmessage = handleTargetSSE;
  targetEvtSrc.onerror   = () => { if (targetEvtSrc) { targetEvtSrc.close(); targetEvtSrc = null; } addTargetLog("Bağlantı kesildi", "error", "system"); finishTargetScan(); };
}

function stopTargetScan() {
  if (targetEvtSrc) { targetEvtSrc.close(); targetEvtSrc = null; }
  finishTargetScan();
}

function finishTargetScan() {
  targetScanBtn.classList.remove("scanning");
  targetScanBtn.querySelector(".scan-btn-text").textContent = "HEDEFİ TARA";
  targetScanBtn.querySelector(".scan-btn-icon").textContent  = "🎯";
  const elapsed = ((Date.now() - targetStart) / 1000).toFixed(1);
  const el = document.getElementById("target-scan-time");
  if (el) el.textContent = `⏱ ${elapsed}s`;
  setTargetProgress(100, "Tamamlandı!");
}

function handleTargetSSE(event) {
  let msg;
  try { msg = JSON.parse(event.data); } catch { return; }
  const { type, data } = msg;

  switch (type) {
    case "start":
      addTargetLog("Hedef taraması başlatıldı", "info", "system");
      break;
    case "log":
      addTargetLog(data.message, data.level, data.module);
      break;
    case "progress":
      setTargetProgress(data.percent, data.module);
      break;
    case "result":
      targetResults[data.module] = data.data;
      renderTargetModule(data.module, data.data);
      break;
    case "complete":
      targetResults = data.results || targetResults;
      finishTargetScan();
      if (targetEvtSrc) { targetEvtSrc.close(); targetEvtSrc = null; }
      if (targetResults.correlation) renderTargetModule("correlation", targetResults.correlation);
      showTargetExportBar();
      break;
  }
}

function setTargetProgress(pct, label) {
  const fill  = document.getElementById("target-progress-fill");
  const lbl   = document.getElementById("target-progress-label");
  const pctEl = document.getElementById("target-progress-pct");
  if (fill)  fill.style.width     = `${pct}%`;
  if (lbl)   lbl.textContent      = label || "";
  if (pctEl) pctEl.textContent    = `${pct}%`;
}

function addTargetLog(msg, level = "info", mod = "") {
  const lb = document.getElementById("target-log-body");
  if (!lb) return;
  const entry = document.createElement("div");
  entry.className = `log-entry ${level}`;
  const now = new Date().toLocaleTimeString("tr-TR", { hour12: false });
  entry.innerHTML = `<span class="log-time">${now}</span><span class="log-mod">${esc(mod)}</span><span class="log-msg">${esc(msg)}</span>`;
  lb.appendChild(entry);
  lb.scrollTop = lb.scrollHeight;
}

function showTargetExportBar() {
  const el = document.getElementById("tcrd-correlation");
  if (el) el.style.display = "";
}

// ── TARGET MODULE ROUTER ──
function renderTargetModule(mod, data) {
  switch (mod) {
    case "instagram":      renderTargetInstagram(data);    break;
    case "twitter":        renderTargetTwitter(data);      break;
    case "youtube":        renderTargetYouTube(data);      break;
    case "tiktok":         renderTargetTikTok(data);       break;
    case "spotify":        renderTargetSpotify(data);      break;
    case "steam":          renderTargetSteam(data);        break;
    case "telegram":       renderTargetTelegram(data);     break;
    case "phone":          renderTargetPhone(data);        break;
    case "reddit":         renderTargetReddit(data);       break;
    case "github_deep":    renderTargetGitHub(data);       break;
    case "gravatar":       renderTargetGravatar(data);     break;
    case "email_validator":renderTargetEmail(data);        break;
    case "pastebin":       renderTargetPaste(data);        break;
    case "crt_search":     renderTargetCRT(data);          break;
    case "dork_gen":       renderTargetDorks(data);        break;
    case "exif_analysis":  renderTargetEXIF(data);         break;
    case "correlation":    renderTargetCorrelation(data);  break;
  }
}

function tshow(id) {
  const el = document.getElementById(id);
  if (el) el.style.display = "";
}

function setStatus(id, found, text) {
  const el = document.getElementById(`pst-${id}`);
  if (el) {
    el.textContent = text || (found ? "✅ Bulundu" : "❌ Yok");
    el.style.background = found ? "rgba(255,255,255,.3)" : "rgba(0,0,0,.25)";
    el.style.color = "#fff";
  }
}

// ── INSTAGRAM ──
function renderTargetInstagram(d) {
  tshow("tcrd-instagram");
  setStatus("instagram", d.found, d.found ? `✅ ${d.followers||""} takipçi` : "❌ Bulunamadı");
  const body = document.getElementById("tbody-instagram");
  if (!body) return;
  let html = "";
  if (d.profile_pic_url) html += `<img src="${esc(d.profile_pic_url)}" class="avatar-img" onerror="this.style.display='none'">`;
  if (d.full_name)   html += kv("Ad",       esc(d.full_name));
  if (d.bio)         html += kv("Bio",      `<span style="font-size:.77rem">${esc(d.bio.substring(0,120))}</span>`);
  if (d.followers)   html += kv("Takipçi",  esc(String(d.followers)));
  if (d.following)   html += kv("Takip",    esc(String(d.following)));
  if (d.posts)       html += kv("Gönderi",  esc(String(d.posts)));
  html += kv("Hesap",  badge(d.is_private?"🔒 Gizli":"🌐 Açık", d.is_private?"by":"bg"));
  if (d.is_verified) html += kv("Onaylı", badge("✅ Evet","bg"));
  if (d.is_business) html += kv("İşletme", badge("🏢 Evet","bb"));
  if (d.external_url) html += kv("Link", `<a href="${esc(d.external_url)}" target="_blank" style="color:var(--accent2);font-size:.77rem">${esc(d.external_url.substring(0,50))}</a>`);
  if (d.category)    html += kv("Kategori", esc(d.category));
  if (d.contact_email) html += kv("İletişim Email", `<span class="badge by">${esc(d.contact_email)}</span>`);
  if (d.contact_phone) html += kv("İletişim Tel", `<span class="badge by">${esc(d.contact_phone)}</span>`);
  html += kv("Profil", `<a href="${esc(d.profile_url)}" target="_blank" class="search-link">→ Aç</a>`);
  body.innerHTML = html;
}

// ── TWITTER ──
function renderTargetTwitter(d) {
  tshow("tcrd-twitter");
  const s = d.stats || {};
  setStatus("twitter", d.found, d.found ? `✅ ${s.followers||""} takipçi` : "❌ Bulunamadı");
  const body = document.getElementById("tbody-twitter");
  if (!body) return;
  let html = "";
  if (d.profile_pic_url) html += `<img src="${esc(d.profile_pic_url)}" class="avatar-img" onerror="this.style.display='none'">`;
  if (d.full_name)   html += kv("Ad",        esc(d.full_name));
  if (d.bio)         html += kv("Bio",       `<span style="font-size:.77rem">${esc(d.bio.substring(0,120))}</span>`);
  if (s.followers)   html += kv("Takipçi",   esc(String(s.followers)));
  if (s.following)   html += kv("Takip",     esc(String(s.following)));
  if (s.tweets)      html += kv("Tweet",     esc(String(s.tweets)));
  if (s.likes)       html += kv("Beğeni",    esc(String(s.likes)));
  if (d.location)    html += kv("Konum",     esc(d.location));
  if (d.website)     html += kv("Website",   `<a href="${esc(d.website)}" target="_blank" style="color:var(--accent2)">${esc(d.website.substring(0,40))}</a>`);
  if (d.joined)      html += kv("Katılım",   esc(d.joined));
  if (d.is_verified) html += kv("Onaylı",    badge("✅","bg"));
  html += kv("Profil", `<a href="${esc(d.profile_url)}" target="_blank" class="search-link">→ Twitter</a>`);
  if (d.nitter_url)  html += kv("Nitter",    `<a href="${esc(d.nitter_url)}" target="_blank" class="search-link">→ Nitter</a>`);
  if (d.recent_tweets?.length) {
    html += `<div style="margin-top:8px;border-top:1px solid #d3deed;padding-top:8px">`;
    d.recent_tweets.slice(0,3).forEach(t => {
      html += `<div class="tweet-item"><div class="tweet-text">${esc(t.text||"")}</div><div class="tweet-date">${esc(t.date||"")}</div></div>`;
    });
    html += `</div>`;
  }
  body.innerHTML = html;
}

// ── YOUTUBE ──
function renderTargetYouTube(d) {
  tshow("tcrd-youtube");
  setStatus("youtube", d.found, d.found ? `✅ ${d.subscriber_count||""} abone` : "❌ Bulunamadı");
  const body = document.getElementById("tbody-youtube");
  if (!body) return;
  let html = "";
  if (d.profile_pic_url) html += `<img src="${esc(d.profile_pic_url)}" class="avatar-img" onerror="this.style.display='none'">`;
  if (d.name)             html += kv("Kanal Adı",  esc(d.name));
  if (d.subscriber_count) html += kv("Abone",      esc(String(d.subscriber_count)));
  if (d.video_count)      html += kv("Video",      esc(String(d.video_count)));
  if (d.country)          html += kv("Ülke",       esc(d.country));
  if (d.channel_id)       html += kv("Channel ID", mono(d.channel_id));
  if (d.description)      html += kv("Açıklama",   `<span style="font-size:.76rem">${esc(d.description.substring(0,120))}</span>`);
  if (d.links?.length)    html += kv("Linkler",    d.links.slice(0,3).map(l=>`<a href="${esc(l)}" target="_blank" class="search-link">${esc(l.substring(0,40))}</a>`).join("<br>"));
  if (d.keywords?.length) html += kv("Anahtar",    d.keywords.slice(0,6).map(k=>`<span class="badge bb">${esc(k)}</span>`).join(" "));
  html += kv("Profil", `<a href="${esc(d.channel_url)}" target="_blank" class="search-link">→ YouTube'da Aç</a>`);
  if (d.recent_videos?.length) {
    html += `<div style="margin-top:10px"><span style="font-size:.72rem;color:var(--muted)">Son Videolar:</span><div class="yt-video-list">`;
    d.recent_videos.slice(0,4).forEach(v => {
      html += `<div class="yt-video-item">
        ${v.thumbnail?`<img src="${esc(v.thumbnail)}" class="yt-thumb" onerror="this.style.display='none'">` : ""}
        <div>
          <div class="yt-title"><a href="${esc(v.url||"")}" target="_blank" style="color:var(--text)">${esc((v.title||"").substring(0,60))}</a></div>
          <div class="yt-meta">${esc(v.published||"")}${v.views?` · ${v.views} izlenme`:""}</div>
        </div>
      </div>`;
    });
    html += `</div></div>`;
  }
  body.innerHTML = html;
}

// ── TIKTOK ──
function renderTargetTikTok(d) {
  tshow("tcrd-tiktok");
  setStatus("tiktok", d.found, d.found ? `✅ ${d.followers||""} takipçi` : "❌ Bulunamadı");
  const body = document.getElementById("tbody-tiktok");
  if (!body) return;
  let html = "";
  if (d.profile_pic_url) html += `<img src="${esc(d.profile_pic_url)}" class="avatar-img" onerror="this.style.display='none'">`;
  if (d.nickname)    html += kv("Nick",       esc(d.nickname));
  if (d.followers)   html += kv("Takipçi",   esc(String(d.followers)));
  if (d.following)   html += kv("Takip",     esc(String(d.following)));
  if (d.likes)       html += kv("Toplam Beğeni", esc(String(d.likes)));
  if (d.videos)      html += kv("Video",     esc(String(d.videos)));
  if (d.region)      html += kv("Bölge",     esc(d.region));
  if (d.is_verified) html += kv("Onaylı",    badge("✅","bg"));
  html += kv("Profil", `<a href="${esc(d.profile_url)}" target="_blank" class="search-link">→ TikTok'ta Aç</a>`);
  body.innerHTML = html;
}

// ── SPOTIFY ──
function renderTargetSpotify(d) {
  tshow("tcrd-spotify");
  setStatus("spotify", d.found, d.found ? `✅ ${d.followers||""} takipçi` : "❌ Bulunamadı");
  const body = document.getElementById("tbody-spotify");
  if (!body) return;
  let html = "";
  if (d.profile_pic_url) html += `<img src="${esc(d.profile_pic_url)}" class="avatar-img" onerror="this.style.display='none'">`;
  if (d.display_name)    html += kv("Ad",          esc(d.display_name));
  if (d.followers)       html += kv("Takipçi",     esc(String(d.followers)));
  if (d.playlist_count)  html += kv("Playlist",    esc(String(d.playlist_count)));
  html += kv("Profil", `<a href="${esc(d.profile_url)}" target="_blank" class="search-link">→ Spotify'da Aç</a>`);
  if (d.public_playlists?.length) {
    html += `<div style="margin-top:8px"><span style="font-size:.72rem;color:var(--muted)">Herkese Açık Playlistler:</span><div style="margin-top:4px">`;
    d.public_playlists.slice(0,5).forEach(p => {
      html += `<div class="kv"><span class="kk">${esc((p.name||"?").substring(0,25))}</span><span class="kv-val"><a href="${esc(p.url)}" target="_blank" class="search-link">${p.track_count||"?"} parça →</a></span></div>`;
    });
    html += `</div></div>`;
  }
  body.innerHTML = html;
}

// ── STEAM ──
function renderTargetSteam(d) {
  tshow("tcrd-steam");
  setStatus("steam_status", d.found, d.found ? `✅ Seviye ${d.level||"?"}` : "❌ Bulunamadı");
  const pst = document.getElementById("pst-steam");
  if (pst) {
    pst.textContent = d.found ? `✅ Lv.${d.level||"?"}${d.is_vac_banned?" | ⚠️VAC":""}` : "❌";
    pst.style.background = d.is_vac_banned ? "rgba(192,40,28,.75)" : d.found ? "rgba(255,255,255,.3)" : "rgba(0,0,0,.25)";
    pst.style.color = "#fff";
  }
  const body = document.getElementById("tbody-steam");
  if (!body) return;
  let html = "";
  if (d.is_vac_banned) html += `<div class="vac-alert">⚠️ VAC BANI TESPİT EDİLDİ!</div>`;
  if (d.profile_pic_url) html += `<img src="${esc(d.profile_pic_url)}" class="avatar-img" onerror="this.style.display='none'">`;
  if (d.username)     html += kv("Kullanıcı",  esc(d.username));
  if (d.real_name)    html += kv("Gerçek Ad",  esc(d.real_name));
  if (d.location)     html += kv("Konum",      esc(d.location));
  if (d.steam_id64)   html += kv("SteamID64",  mono(d.steam_id64));
  if (d.level)        html += kv("Seviye",     esc(d.level));
  if (d.games_count)  html += kv("Oyun",       esc(d.games_count));
  if (d.friends_count)html += kv("Arkadaş",    esc(d.friends_count));
  if (d.badges_count) html += kv("Rozet",      esc(d.badges_count));
  if (d.member_since) html += kv("Üyelik",     esc(d.member_since));
  if (d.state)        html += kv("Durum",      esc(d.state));
  html += kv("Hesap", badge(d.is_private ? "🔒 Gizli":"🌐 Açık", d.is_private?"by":"bg"));
  if (d.summary)      html += kv("Bio",        `<span style="font-size:.76rem">${esc(d.summary.substring(0,120))}</span>`);
  html += kv("Profil", `<a href="${esc(d.profile_url)}" target="_blank" class="search-link">→ Steam'de Aç</a>`);
  body.innerHTML = html;
}

// ── TELEGRAM ──
function renderTargetTelegram(d) {
  tshow("tcrd-telegram");
  setStatus("telegram", d.found, d.found ? `✅ ${d.name||d.username}` : "❌ Bulunamadı");
  const body = document.getElementById("tbody-telegram");
  if (!body) return;
  let html = "";
  if (d.profile_pic_url) html += `<img src="${esc(d.profile_pic_url)}" class="avatar-img" onerror="this.style.display='none'">`;
  if (d.name)        html += kv("Ad",        esc(d.name));
  if (d.description) html += kv("Bio",       `<span style="font-size:.77rem">${esc(d.description.substring(0,150))}</span>`);
  if (d.info)        html += kv("Bilgi",     esc(d.info));
  html += kv("Profil", `<a href="${esc(d.profile_url)}" target="_blank" class="search-link">→ Telegram'da Aç</a>`);
  body.innerHTML = html;
}

// ── PHONE ──
function renderTargetPhone(d) {
  tshow("tcrd-phone");
  setStatus("phone", d.valid_format, d.valid_format ? `✅ ${d.country||"Bilinmiyor"}` : "⚠️ Geçersiz");
  const body = document.getElementById("tbody-phone");
  if (!body) return;
  let html = kv("Numara", mono(d.normalized||d.original));
  if (d.country)           html += kv("Ülke",      esc(d.country));
  if (d.iso2)              html += kv("ISO",        esc(d.iso2));
  if (d.possible_carriers?.length) html += kv("Operatör", d.possible_carriers.slice(0,3).map(c=>`<span class="badge bg">${esc(c)}</span>`).join(" "));
  if (d.is_mobile !== null && d.is_mobile !== undefined) html += kv("Hat Tipi", badge(d.is_mobile?"📱 GSM":"📞 Sabit",d.is_mobile?"bg":"bb"));
  if (d.formats) {
    html += `<div style="margin-top:6px"><span style="font-size:.71rem;color:var(--muted)">Format Varyasyonları:</span><div class="phone-formats">`;
    Object.values(d.formats).filter((v,i,a)=>a.indexOf(v)===i).forEach(f => {
      html += `<span class="phone-format-item" onclick="navigator.clipboard.writeText('${esc(f)}')" title="Kopyala">${esc(f)}</span>`;
    });
    html += `</div></div>`;
  }
  if (d.search_links?.length) {
    html += `<div style="margin-top:8px"><span style="font-size:.71rem;color:var(--muted)">Kontrol Linkleri:</span><div class="phone-dork-links">`;
    d.search_links.forEach(l => { html += `<a href="${esc(l.url)}" target="_blank" class="phone-dork-link">🔗 ${esc(l.label)}</a>`; });
    html += `</div></div>`;
  }
  body.innerHTML = html;
}

// ── REDDIT (target) ──
function renderTargetReddit(d) {
  tshow("tcrd-reddit");
  setStatus("reddit", d.found, d.found ? `✅ Karma: ${d.profile?.total_karma||0}` : "❌");
  const body = document.getElementById("tbody-reddit");
  if (body) body.innerHTML = document.getElementById("body-reddit")?.innerHTML || "";
  // Reuse existing renderer
  renderReddit(d);
  const destBody = document.getElementById("tbody-reddit");
  const srcBody  = document.getElementById("body-reddit");
  if (destBody && srcBody) destBody.innerHTML = srcBody.innerHTML;
}

// ── GITHUB (target) ──
function renderTargetGitHub(d) {
  tshow("tcrd-github_deep");
  const p = d.profile || {};
  setStatus("github_deep", d.found, d.found ? `✅ ${p.public_repos||0} repo` : "❌");
  const body = document.getElementById("tbody-github_deep");
  if (!body) return;
  renderGitHubDeep(d);
  const src = document.getElementById("body-github_deep");
  if (src) body.innerHTML = src.innerHTML;
}

// ── GRAVATAR (target) ──
function renderTargetGravatar(d) {
  tshow("tcrd-gravatar");
  setStatus("gravatar", d.has_gravatar, d.has_gravatar ? "✅ Profil Var" : "❌ Yok");
  const body = document.getElementById("tbody-gravatar");
  if (!body) return;
  renderGravatar(d);
  const src = document.getElementById("body-gravatar");
  if (src) body.innerHTML = src.innerHTML;
}

// ── EMAIL (target) ──
function renderTargetEmail(d) {
  tshow("tcrd-email_validator");
  setStatus("email_validator", d.valid_syntax && d.has_mx, d.is_disposable?"⚠️ Disposable":d.valid_syntax?"✅ Geçerli":"❌");
  const body = document.getElementById("tbody-email_validator");
  if (!body) return;
  renderEmailValidator(d);
  const src = document.getElementById("body-email_validator");
  if (src) body.innerHTML = src.innerHTML;
}

// ── PASTE (target) ──
function renderTargetPaste(d) {
  tshow("tcrd-pastebin");
  const badge_el = document.getElementById("tbadge-pastebin");
  if (badge_el) badge_el.innerHTML = badge(d.total_found>0?`⚠️ ${d.total_found} kayıt`:"✅ Temiz", d.total_found>0?"br":"bg");
  const body = document.getElementById("tbody-pastebin");
  if (!body) return;
  renderPaste(d);
  const src = document.getElementById("body-pastebin");
  if (src) body.innerHTML = src.innerHTML;
}

// ── CRT (target) ──
function renderTargetCRT(d) {
  tshow("tcrd-crt_search");
  const badge_el = document.getElementById("tbadge-crt_search");
  const subs = d.all_subdomains?.length || 0;
  if (badge_el) badge_el.innerHTML = badge(`${subs} subdomain`,"bb");
  const body = document.getElementById("tbody-crt_search");
  if (!body) return;
  renderCRT(d);
  const src = document.getElementById("body-crt_search");
  if (src) body.innerHTML = src.innerHTML;
}

// ── DORKS (target) ──
function renderTargetDorks(d) {
  tshow("tcrd-dork_gen");
  const badge_el = document.getElementById("tbadge-dork_gen");
  if (badge_el) badge_el.innerHTML = badge(`${d.all_queries?.length||0} sorgu`,"bb");
  const body = document.getElementById("tbody-dork_gen");
  if (!body) return;
  renderDorks(d);
  const src = document.getElementById("body-dork_gen");
  if (src) body.innerHTML = src.innerHTML;
}

// ── EXIF (target) ──
function renderTargetEXIF(data) {
  if (!Array.isArray(data) || !data.length) return;
  tshow("tcrd-exif_analysis");
  const badge_el = document.getElementById("tbadge-exif_analysis");
  if (badge_el) badge_el.innerHTML = badge(`${data.length} fotoğraf`,"bb");
  const body = document.getElementById("tbody-exif_analysis");
  if (!body) return;
  renderEXIF(data);
  const src = document.getElementById("body-exif_analysis");
  if (src) body.innerHTML = src.innerHTML;
}

// ── CORRELATION (target) ──
function renderTargetCorrelation(d) {
  tshow("tcrd-correlation");
  const body = document.getElementById("tbody-correlation");
  if (!body) return;
  // Reuse main correlation renderer output
  renderCorrelation(d);
  const src = document.getElementById("body-correlation");
  if (src) body.innerHTML = src.innerHTML;
}

function resetTargetUI() {
  document.querySelectorAll("[id^='tcrd-']").forEach(c => c.style.display = "none");
  document.getElementById("target-results").style.display     = "none";
  document.getElementById("target-progress").style.display    = "none";
  document.getElementById("target-log-section").style.display = "none";
  document.getElementById("target-log-body").innerHTML        = "";
  setTargetProgress(0, "");
}

// Export for target panel
document.getElementById("target-export-json")?.addEventListener("click", () => exportTargetData("json"));
document.getElementById("target-export-html")?.addEventListener("click", () => exportTargetData("html"));

async function exportTargetData(fmt) {
  try {
    const target_name = targetInputs.email || targetInputs.username || targetInputs.name || "target";
    const resp = await fetch(`/api/export/${fmt}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: target_name, inputs: targetInputs, results: targetResults })
    });
    if (!resp.ok) throw new Error(await resp.text());
    const blob = await resp.blob();
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement("a");
    a.href = url;
    a.download = `target_${target_name.replace(/[@\s]/g,"_")}.${fmt === "html" ? "html" : "json"}`;
    a.click();
    URL.revokeObjectURL(url);
  } catch(e) { addTargetLog(`Export hatası: ${e.message}`, "error", "export"); }
}


// ═══════════════════════════════════════════
//  WIN7 PENCERE / GÖREV ÇUBUĞU
// ═══════════════════════════════════════════
(function winChrome() {
  const win = document.getElementById("win");
  const orb = document.getElementById("start-orb");
  const menu = document.getElementById("start-menu");
  const taskBtn = document.getElementById("task-main");

  document.getElementById("wc-max")?.addEventListener("click", () => win.classList.toggle("maximized"));
  document.getElementById("wc-min")?.addEventListener("click", () => {
    win.classList.toggle("minimized");
    taskBtn?.classList.toggle("active", !win.classList.contains("minimized"));
  });
  document.getElementById("wc-close")?.addEventListener("click", () => {
    win.animate([{ transform: "translateX(0)" }, { transform: "translateX(-6px)" }, { transform: "translateX(6px)" }, { transform: "translateX(0)" }], { duration: 220 });
    setStatusText("Bu pencere kapatılamaz — sekmeyi tarayıcıdan kapatın");
    setTimeout(() => setStatusText("Hazır"), 2500);
  });
  document.querySelector(".header")?.addEventListener("dblclick", () => win.classList.toggle("maximized"));
  taskBtn?.addEventListener("click", () => {
    win.classList.toggle("minimized");
    taskBtn.classList.toggle("active", !win.classList.contains("minimized"));
  });

  const closeMenu = () => { menu.style.display = "none"; orb.classList.remove("open"); };
  orb?.addEventListener("click", e => {
    e.stopPropagation();
    const open = menu.style.display !== "none";
    menu.style.display = open ? "none" : "flex";
    orb.classList.toggle("open", !open);
  });
  document.addEventListener("click", e => { if (!menu.contains(e.target)) closeMenu(); });
  document.addEventListener("keydown", e => { if (e.key === "Escape") closeMenu(); });
  menu?.querySelectorAll(".start-item").forEach(btn => btn.addEventListener("click", () => {
    document.querySelector(`.nav-btn[data-panel="${btn.dataset.panel}"]`)?.click();
    win.classList.remove("minimized");
    closeMenu();
  }));

  function tick() {
    const d = new Date();
    document.getElementById("clock-time").textContent = d.toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" });
    document.getElementById("clock-date").textContent = d.toLocaleDateString("tr-TR");
  }
  tick();
  setInterval(tick, 15000);
})();

function loadTargetHistoryItem(results) {
  document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("active"));
  document.querySelectorAll(".panel").forEach(p => p.classList.remove("active"));
  document.querySelector('[data-panel="target"]').classList.add("active");
  document.getElementById("panel-target").classList.add("active");
  targetResults = results;
  resetTargetUI();
  document.getElementById("target-results").style.display = "block";
  Object.entries(results).forEach(([mod, data]) => { if (mod !== "target_inputs" && mod !== "_scan_type") renderTargetModule(mod, data); });
  showTargetExportBar();
  const el = document.getElementById("target-scan-time");
  if (el) el.textContent = "📜 Geçmişten yüklendi";
}
