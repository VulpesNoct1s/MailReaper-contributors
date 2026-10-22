"""
MailReaper - Export Module
Sonuçları JSON ve HTML formatında dışa aktarır
"""

import json
import re
import os
from datetime import datetime


def export_json(email: str, results: dict, output_dir: str = None) -> str:
    """Sonuçları JSON dosyasına kaydeder. Dosya yolunu döner."""
    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "exports")
    os.makedirs(output_dir, exist_ok=True)

    safe_email = re.sub(r"[^A-Za-z0-9_\-]", "_", email.replace("@", "_at_"))[:80] or "target"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"mailreaper_{safe_email}_{timestamp}.json"
    filepath = os.path.join(output_dir, filename)

    export_data = {
        "tool": "MailReaper Email OSINT",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat(),
        "target": email,
        "results": results
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(export_data, f, ensure_ascii=False, indent=2, default=str)

    return filepath


def export_html(email: str, results: dict, output_dir: str = None) -> str:
    """Sonuçları güzel HTML raporuna kaydeder."""
    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "exports")
    os.makedirs(output_dir, exist_ok=True)

    safe_email = re.sub(r"[^A-Za-z0-9_\-]", "_", email.replace("@", "_at_"))[:80] or "target"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"mailreaper_{safe_email}_{timestamp}.html"
    filepath = os.path.join(output_dir, filename)

    risk = results.get("risk_score", {})
    score = risk.get("total", 0)
    grade = risk.get("grade", "?")
    grade_color = risk.get("grade_color", "#888")
    grade_text = risk.get("grade_text", "")

    validator = results.get("email_validator", {})
    smtp = results.get("smtp_probe", {})
    dns = results.get("dns_analysis", {})
    gravatar = results.get("gravatar", {})
    social = results.get("social", {})
    github = results.get("github_search", {})
    paste = results.get("pastebin", {})
    usernames = results.get("username_gen", {})

    def section(title, icon, content_html):
        return f"""
        <div class="section">
            <h2>{icon} {title}</h2>
            {content_html}
        </div>
        """

    def badge(val, true_text="✅ Evet", false_text="❌ Hayır", warn=False):
        if val:
            return f'<span class="badge badge-good">{true_text}</span>'
        else:
            color = "badge-warn" if warn else "badge-bad"
            return f'<span class="badge {color}">{false_text}</span>'

    def kv(key, val):
        return f'<div class="kv"><span class="key">{key}</span><span class="val">{val if val not in (None, "", [], {}) else "—"}</span></div>'

    # Email Validator section
    validator_html = f"""
    {kv("Syntax Geçerli", badge(validator.get('valid_syntax')))}
    {kv("Disposable Email", badge(not validator.get('is_disposable'), "✅ Normal", "⚠️ Disposable/Geçici", warn=True))}
    {kv("MX Kaydı", badge(validator.get('has_mx')))}
    {kv("Provider", validator.get('provider', '—'))}
    {kv("Email Tipi", validator.get('email_type', '—'))}
    {kv("MD5 Hash", f"<code>{validator.get('md5', '—')}</code>")}
    """

    # SMTP section
    smtp_html = f"""
    {kv("SMTP Erişilebilir", badge(smtp.get('smtp_reachable')))}
    {kv("Sunucu", smtp.get('server_used') or '—')}
    {kv("TLS Desteği", badge(smtp.get('supports_tls')))}
    {kv("Catch-All", badge(not smtp.get('catch_all'), "✅ Hayır", "⚠️ Evet (catch-all)"))}
    {kv("Banner", f"<code>{smtp.get('banner', '—')}</code>")}
    """

    # DNS section
    spf = dns.get("spf", {})
    dmarc = dns.get("dmarc", {})
    ssl_info = dns.get("ssl", {})
    whois_info = dns.get("whois", {})

    mx_list = "".join(f"<li><code>{m.get('exchange', m)}</code></li>" for m in (dns.get("mx_records") or []))
    ns_list = "".join(f"<li><code>{n}</code></li>" for n in (dns.get("ns_records") or []))
    txt_list = "".join(f"<li><code>{t}</code></li>" for t in (dns.get("txt_records") or []))
    a_list = "".join(f"<li><code>{a}</code></li>" for a in (dns.get("a_records") or []))

    dns_html = f"""
    <div class="subsection">
        <h3>📋 DNS Kayıtları</h3>
        <div class="grid2">
            <div>{kv("A Kayıtları", f"<ul>{a_list}</ul>" if a_list else "—")}</div>
            <div>{kv("MX Kayıtları", f"<ul>{mx_list}</ul>" if mx_list else "—")}</div>
            <div>{kv("NS Kayıtları", f"<ul>{ns_list}</ul>" if ns_list else "—")}</div>
            <div>{kv("TXT Kayıtları", f"<ul>{txt_list}</ul>" if txt_list else "—")}</div>
        </div>
    </div>
    <div class="subsection">
        <h3>🛡️ Email Güvenlik</h3>
        {kv("SPF", badge(spf.get('exists')))}
        {kv("SPF Kaydı", f"<code>{spf.get('record', '—')}</code>")}
        {kv("DMARC", badge(dmarc.get('exists')))}
        {kv("DMARC Policy", dmarc.get('policy', '—'))}
        {kv("DKIM Selectors", ", ".join(dns.get('dkim_selectors_found', [])) or "—")}
    </div>
    <div class="subsection">
        <h3>🔒 SSL Sertifikası</h3>
        {kv("Geçerli", badge(ssl_info.get('valid') if ssl_info else None))}
        {kv("İssuer", ssl_info.get('issuer') if ssl_info else "—")}
        {kv("Geçerlilik", f"{ssl_info.get('not_before', '—')} → {ssl_info.get('not_after', '—')}" if ssl_info else "—")}
        {kv("Kalan Gün", str(ssl_info.get('days_remaining', '—')) if ssl_info else "—")}
    </div>
    <div class="subsection">
        <h3>📝 WHOIS</h3>
        {kv("Registrar", whois_info.get('registrar') if whois_info else "—")}
        {kv("Kayıt Tarihi", str(whois_info.get('created', '—')) if whois_info else "—")}
        {kv("Bitiş Tarihi", str(whois_info.get('expires', '—')) if whois_info else "—")}
        {kv("Org", whois_info.get('org') if whois_info else "—")}
        {kv("Ülke", whois_info.get('country') if whois_info else "—")}
    </div>
    """

    # Gravatar section
    gravatar_html = f"""
    {kv("Gravatar Var", badge(gravatar.get('has_gravatar')))}
    {kv("Display Name", gravatar.get('display_name') or "—")}
    {kv("Konum", gravatar.get('location') or "—")}
    {kv("Hakkında", gravatar.get('about_me') or "—")}
    {kv("Avatar", f'<img src="{gravatar.get("avatar_url")}" width="80" height="80" style="border-radius:50%;border:2px solid #00ff88">' if gravatar.get('avatar_url') else "—")}
    """

    # Social media section
    found_social = social.get("found", [])
    social_badges = "".join(
        f'<a href="{p["url"]}" target="_blank" class="social-badge"><span>🌐</span> {p["platform"]}</a>'
        for p in found_social
    )
    social_html = f"""
    {kv("Bulunan Profil", f"{social.get('total_found', 0)} platform")}
    <div class="social-grid">{social_badges if social_badges else "<p>Profil bulunamadı</p>"}</div>
    """

    # GitHub section
    github_user = github.get("github_user")
    github_html = f"""
    {kv("GitHub Hesabı", badge(bool(github_user)))}
    """
    if github_user:
        github_html += f"""
        {kv("Kullanıcı Adı", f'<a href="https://github.com/{github_user.get("login", "")}" target="_blank">@{github_user.get("login", "")}</a>')}
        {kv("Ad", github_user.get('name') or "—")}
        {kv("Konum", github_user.get('location') or "—")}
        {kv("Repo Sayısı", github_user.get('public_repos', '—'))}
        {kv("Takipçi", github_user.get('followers', '—'))}
        {kv("Kayıt Tarihi", github_user.get('created_at', '—'))}
        """

    commits = github.get("commits_found", [])
    if commits:
        commit_rows = "".join(f"<tr><td>{c.get('repo','')}</td><td>{c.get('author','')}</td><td><a href='{c.get('url','')}' target='_blank'>Link</a></td></tr>" for c in commits[:5])
        github_html += f"""
        <h3>📦 Commit Geçmişi ({len(commits)} commit)</h3>
        <table><thead><tr><th>Repo</th><th>Yazar</th><th>Link</th></tr></thead><tbody>{commit_rows}</tbody></table>
        """

    # Paste section
    paste_items = paste.get("findings", [])
    paste_html = kv("Bulunan Kayıt", f"{len(paste_items)} kayıt")
    for p in paste_items:
        source = p.get("source", "")
        is_stealer = "Stealer" in source
        color = "#ff0044" if is_stealer else "#ff8800"
        paste_html += f"""
        <div class="paste-item" style="border-left: 3px solid {color}; padding: 8px; margin: 6px 0; background: rgba(255,255,255,0.03); border-radius: 4px;">
            <strong style="color:{color}">{source}</strong><br>
            {f'<a href="{p.get("url", "")}" target="_blank">{p.get("url", "")}</a><br>' if p.get("url") else ""}
            {f'<small>Bilgisayar: {p.get("computer_name","")} | OS: {p.get("operating_system","")}</small><br>' if p.get("computer_name") else ""}
            {f'<small>Tarih: {p.get("date_compromised","")}</small>' if p.get("date_compromised") else ""}
        </div>
        """

    # Usernames section
    un_list = usernames.get("usernames", [])
    username_chips = "".join(f'<span class="chip">{u}</span>' for u in un_list[:40])
    usernames_html = f"""
    {kv("Üretilen Kullanıcı Adı", f"{len(un_list)} adet")}
    <div class="chip-container">{username_chips}</div>
    """

    # Risk factors
    risk_factors_html = "".join(f"<li>{rf}</li>" for rf in risk.get("risk_factors", []))
    recs_html = "".join(f"<li>{r}</li>" for r in risk.get("recommendations", []))

    cat = risk.get("category_scores", {})

    html = f"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MailReaper Report — {email}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0a0a0f; color: #e0e0e0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 20px; }}
  .container {{ max-width: 1100px; margin: 0 auto; }}
  header {{ text-align: center; padding: 40px 0 30px; border-bottom: 1px solid rgba(0,255,136,0.2); margin-bottom: 30px; }}
  header h1 {{ font-size: 2.5rem; color: #00ff88; letter-spacing: 3px; }}
  header .subtitle {{ color: #888; margin-top: 8px; font-size: 0.95rem; }}
  .risk-hero {{ display: flex; align-items: center; justify-content: center; gap: 40px; padding: 30px; background: rgba(255,255,255,0.03); border: 1px solid rgba(0,255,136,0.15); border-radius: 16px; margin-bottom: 30px; }}
  .score-circle {{ width: 120px; height: 120px; border-radius: 50%; border: 4px solid {grade_color}; display: flex; flex-direction: column; align-items: center; justify-content: center; background: rgba(0,0,0,0.5); }}
  .score-num {{ font-size: 2.5rem; font-weight: 900; color: {grade_color}; }}
  .score-label {{ font-size: 0.7rem; color: #888; }}
  .grade-badge {{ font-size: 4rem; font-weight: 900; color: {grade_color}; text-shadow: 0 0 20px {grade_color}66; }}
  .grade-info h2 {{ font-size: 1.4rem; color: {grade_color}; }}
  .grade-info p {{ color: #888; margin-top: 4px; }}
  .cat-bars {{ display: grid; gap: 8px; min-width: 250px; }}
  .cat-bar {{ display: flex; flex-direction: column; gap: 4px; }}
  .cat-bar label {{ font-size: 0.75rem; color: #888; display: flex; justify-content: space-between; }}
  .bar-track {{ height: 6px; background: rgba(255,255,255,0.1); border-radius: 3px; overflow: hidden; }}
  .bar-fill {{ height: 100%; border-radius: 3px; background: {grade_color}; }}
  .section {{ background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.06); border-radius: 12px; padding: 24px; margin-bottom: 20px; }}
  .section h2 {{ font-size: 1.1rem; color: #00ff88; margin-bottom: 16px; border-bottom: 1px solid rgba(0,255,136,0.15); padding-bottom: 10px; }}
  .section h3 {{ font-size: 0.95rem; color: #aaa; margin: 16px 0 8px; }}
  .subsection {{ margin-top: 16px; padding-top: 16px; border-top: 1px solid rgba(255,255,255,0.05); }}
  .kv {{ display: flex; align-items: flex-start; gap: 12px; padding: 6px 0; border-bottom: 1px solid rgba(255,255,255,0.04); }}
  .key {{ min-width: 160px; color: #888; font-size: 0.85rem; }}
  .val {{ color: #e0e0e0; font-size: 0.85rem; flex: 1; word-break: break-all; }}
  .val ul {{ padding-left: 16px; }}
  .val li {{ margin: 2px 0; }}
  .badge {{ padding: 2px 10px; border-radius: 20px; font-size: 0.78rem; font-weight: 600; }}
  .badge-good {{ background: rgba(0,255,136,0.15); color: #00ff88; }}
  .badge-bad {{ background: rgba(255,0,68,0.15); color: #ff0044; }}
  .badge-warn {{ background: rgba(255,200,0,0.15); color: #ffc800; }}
  code {{ background: rgba(0,255,136,0.08); padding: 1px 6px; border-radius: 4px; font-family: monospace; font-size: 0.82rem; color: #00ff88; word-break: break-all; }}
  .grid2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
  .social-grid {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }}
  .social-badge {{ padding: 6px 14px; background: rgba(0,255,136,0.08); border: 1px solid rgba(0,255,136,0.2); border-radius: 20px; color: #00ff88; text-decoration: none; font-size: 0.82rem; transition: all 0.2s; }}
  .social-badge:hover {{ background: rgba(0,255,136,0.2); }}
  .chip-container {{ display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }}
  .chip {{ background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); padding: 3px 10px; border-radius: 12px; font-size: 0.78rem; color: #ccc; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
  th, td {{ padding: 8px 12px; text-align: left; border-bottom: 1px solid rgba(255,255,255,0.06); font-size: 0.83rem; }}
  th {{ color: #888; font-weight: 600; }}
  a {{ color: #00ff88; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  ul.risk-list li {{ margin: 6px 0; font-size: 0.88rem; }}
  footer {{ text-align: center; padding: 30px; color: #444; font-size: 0.82rem; margin-top: 20px; }}
  @media (max-width: 700px) {{ .risk-hero {{ flex-direction: column; }} .grid2 {{ grid-template-columns: 1fr; }} .key {{ min-width: 120px; }} }}
</style>
</head>
<body>
<div class="container">
  <header>
    <h1>⚡ MailReaper</h1>
    <div class="subtitle">Email OSINT Raporu &nbsp;•&nbsp; {datetime.now().strftime("%d.%m.%Y %H:%M:%S")} &nbsp;•&nbsp; <code>{email}</code></div>
  </header>

  <div class="risk-hero">
    <div class="score-circle">
      <span class="score-num">{score}</span>
      <span class="score-label">/ 100</span>
    </div>
    <div class="grade-badge">{grade}</div>
    <div class="grade-info">
      <h2>{grade_text}</h2>
      <p>Risk Seviyesi</p>
    </div>
    <div class="cat-bars">
      <div class="cat-bar"><label><span>Kimlik İfşası</span><span>{cat.get("identity_exposure",0)}/30</span></label><div class="bar-track"><div class="bar-fill" style="width:{min(cat.get('identity_exposure',0)/30*100,100):.0f}%"></div></div></div>
      <div class="cat-bar"><label><span>Email Geçerliliği</span><span>{cat.get("email_validity",0)}/20</span></label><div class="bar-track"><div class="bar-fill" style="width:{min(cat.get('email_validity',0)/20*100,100):.0f}%"></div></div></div>
      <div class="cat-bar"><label><span>Altyapı Riski</span><span>{cat.get("infrastructure_risk",0)}/20</span></label><div class="bar-track"><div class="bar-fill" style="width:{min(cat.get('infrastructure_risk',0)/20*100,100):.0f}%"></div></div></div>
      <div class="cat-bar"><label><span>Sızıntı Riski</span><span>{cat.get("leak_breach_risk",0)}/30</span></label><div class="bar-track"><div class="bar-fill" style="width:{min(cat.get('leak_breach_risk',0)/30*100,100):.0f}%"></div></div></div>
    </div>
  </div>

  {section("Risk Faktörleri & Öneriler", "⚠️", f'<ul class="risk-list">{risk_factors_html}</ul><br><strong>Öneriler:</strong><ul class="risk-list">{recs_html if recs_html else "<li>Kritik öneri yok</li>"}</ul>')}
  {section("Email Doğrulama", "📧", validator_html)}
  {section("SMTP Probe", "🔌", smtp_html)}
  {section("DNS / WHOIS / SSL Analizi", "🌐", dns_html)}
  {section("Gravatar", "🖼️", gravatar_html)}
  {section("Sosyal Medya Varlığı", "📱", social_html)}
  {section("GitHub Analizi", "🐙", github_html)}
  {section("Paste Site / Sızıntı Taraması", "📋", paste_html)}
  {section("Olası Kullanıcı Adları", "👤", usernames_html)}

  <footer>
    MailReaper &copy; 2026 &nbsp;•&nbsp; Bu rapor yalnızca eğitim ve araştırma amaçlıdır.<br>
    Yasal sınırlar içinde, etik kurallara uygun kullanın.
  </footer>
</div>
</body>
</html>"""

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)

    return filepath
