"""
MailReaper v4 — Flask Ana Uygulama
Email + Username + Domain + Hedef profili
Paralel modül çalıştırma, canlı SSE akışı, geçmiş, export.
"""

import json
import os
import re
import sqlite3
import queue
import threading
from contextlib import contextmanager
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, render_template, request, jsonify, Response, send_file
from flask_cors import CORS

# ── v1 Modüller ──
from modules.email_validator import validate_email
from modules.smtp_probe import probe_smtp
from modules.dns_analysis import analyze_domain
from modules.gravatar import lookup_gravatar
from modules.social import check_social_media
from modules.github_search import search_github
from modules.pastebin import search_paste_sites
from modules.username_gen import generate_usernames
from modules.risk_scorer import calculate_risk_score
from modules import get_email_parts, is_valid_email

# ── v2 Modüller ──
from modules.username_osint import username_osint
from modules.crt_search import full_search as crt_full_search
from modules.wayback import search_username_history, search_email_history, search_domain_history
from modules.profile_scraper import scrape_reddit, scrape_hackernews, scrape_github_deep
from modules.dork_gen import generate_dorks
from modules.exif_analyzer import analyze_image_url
from modules.correlation import correlate
from modules import exporter

# ── v3 Platform Scrapers ──
from modules.instagram_osint import scrape_instagram
from modules.twitter_osint    import scrape_twitter
from modules.youtube_osint    import scrape_youtube
from modules.tiktok_osint     import scrape_tiktok
from modules.spotify_osint    import scrape_spotify
from modules.phone_osint      import analyze_phone
from modules.steam_osint      import scrape_steam

# ── v4 Modüller ──
from modules.web_recon import web_recon
from modules.ip_intel import ip_intel

app = Flask(__name__)
CORS(app, origins=[r"http://127\.0\.0\.1:\d+", r"http://localhost:\d+"])

DB_PATH = os.environ.get("MAILREAPER_DB") or os.path.join(os.path.dirname(__file__), "database", "history.db")
VERSION = "4.0"

DOMAIN_RE   = re.compile(r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9\-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
USERNAME_RE = re.compile(r"^[\w.\-]{1,64}$")


# ═══════════════════════════════════════════
#  GİRDİ DOĞRULAMA
# ═══════════════════════════════════════════

def clean_domain(raw: str) -> str:
    """URL / path / port verilse bile saf domain'i çıkarır."""
    d = (raw or "").strip().lower()
    d = re.sub(r"^[a-z]+://", "", d)
    d = d.split("/")[0].split("?")[0].split("#")[0].split(":")[0]
    return d.removeprefix("www.")


def clean_username(raw: str) -> str:
    return (raw or "").strip().removeprefix("@").removeprefix("u/")


def validate_inputs(email: str, username: str, domain: str):
    """Hata mesajı döner, sorun yoksa None."""
    if email and not is_valid_email(email):
        return "Geçersiz email formatı"
    if domain and not DOMAIN_RE.match(domain):
        return "Geçersiz domain (örn: example.com)"
    if username and not USERNAME_RE.match(username):
        return "Geçersiz kullanıcı adı (harf, rakam, . _ - ve en fazla 64 karakter)"
    return None


# ═══════════════════════════════════════════
#  VERİTABANI
# ═══════════════════════════════════════════

@contextmanager
def db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with db() as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS searches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT,
                username TEXT,
                domain TEXT,
                scan_type TEXT DEFAULT 'multi',
                timestamp TEXT NOT NULL,
                risk_score INTEGER,
                risk_grade TEXT,
                results_json TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_searches_created ON searches(created_at)")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                board_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)


def save_search(inputs: dict, results: dict, scan_type: str = "multi"):
    try:
        risk = results.get("risk_score", {})
        with db() as conn:
            conn.execute(
                """INSERT INTO searches
                   (email, username, domain, scan_type, timestamp, risk_score, risk_grade, results_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (inputs.get("email", ""), inputs.get("username", ""), inputs.get("domain", ""),
                 scan_type, datetime.now().isoformat(), risk.get("total", 0), risk.get("grade", "?"),
                 json.dumps(results, ensure_ascii=False, default=str)))
    except Exception as e:
        print(f"[DB] Kayıt hatası: {e}")


def get_history(q: str = ""):
    try:
        sql = """SELECT id, email, username, domain, scan_type, timestamp, risk_score, risk_grade
                 FROM searches"""
        args = ()
        if q:
            sql += " WHERE email LIKE ? OR username LIKE ? OR domain LIKE ?"
            args = (f"%{q}%",) * 3
        sql += " ORDER BY created_at DESC LIMIT 200"
        with db() as conn:
            rows = conn.execute(sql, args).fetchall()
        return [{"id": r[0], "email": r[1], "username": r[2], "domain": r[3], "scan_type": r[4],
                 "timestamp": r[5], "risk_score": r[6], "risk_grade": r[7]} for r in rows]
    except Exception:
        return []


def get_search_by_id(search_id: int):
    try:
        with db() as conn:
            row = conn.execute("SELECT results_json, scan_type FROM searches WHERE id = ?", (search_id,)).fetchone()
        if row:
            data = json.loads(row[0])
            data["_scan_type"] = row[1]
            return data
    except Exception:
        pass
    return None


# ═══════════════════════════════════════════
#  SSE + PARALEL ÇALIŞTIRICI
# ═══════════════════════════════════════════

def sse_event(event_type: str, data: dict) -> str:
    payload = json.dumps({"type": event_type, "data": data}, ensure_ascii=False, default=str)
    return f"data: {payload}\n\n"


def sse_log(message: str, level: str = "info", module: str = "") -> str:
    return sse_event("log", {"message": message, "level": level, "module": module,
                             "time": datetime.now().strftime("%H:%M:%S")})


def sse_result(module: str, data) -> str:
    return sse_event("result", {"module": module, "data": data})


SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"}


class Task:
    """Tek modül: fn(ctx) -> {sonuç_anahtarı: veri}. ctx.log() canlı log yollar."""
    def __init__(self, label, fn):
        self.label, self.fn = label, fn


class Ctx:
    def __init__(self, q: queue.Queue, module: str):
        self._q, self.module = q, module

    def log(self, msg, level="info"):
        self._q.put(sse_log(msg, level, self.module))

    def result(self, key, data):
        """Modül bitmeden ara sonuç göndermek için."""
        self._q.put(sse_result(key, data))


def run_tasks(tasks: dict, results: dict, total_offset: int = 0, total: int = None, workers: int = 12):
    """
    tasks: {modül_adı: Task}. Hepsini paralel çalıştırır, sonuçları geldikçe yield eder.
    Her task bir dict döner; anahtarlar results'a yazılır ve istemciye gönderilir.
    """
    if not tasks:
        return
    q: queue.Queue = queue.Queue()
    total = total or (total_offset + len(tasks))
    done = 0
    ex = ThreadPoolExecutor(max_workers=workers)
    futures = {}
    for name, t in tasks.items():
        futures[ex.submit(t.fn, Ctx(q, name))] = (name, t)

    pending = set(futures)
    try:
        while pending or not q.empty():
            try:
                yield q.get(timeout=0.4)
                continue
            except queue.Empty:
                pass
            finished = [f for f in pending if f.done()]
            for f in finished:
                pending.discard(f)
                name, t = futures[f]
                done += 1
                try:
                    out = f.result() or {}
                    for key, data in out.items():
                        results[key] = data
                        yield sse_result(key, data)
                except Exception as e:
                    yield sse_log(f"{t.label} hatası: {e}", "error", name)
                pct = min(int((total_offset + done) / total * 100), 99)
                yield sse_event("progress", {"current": total_offset + done, "total": total,
                                             "module": t.label, "percent": pct})
            if not finished and pending:
                yield ": ping\n\n"          # bağlantıyı canlı tut
    finally:
        ex.shutdown(wait=False, cancel_futures=True)


# ═══════════════════════════════════════════
#  ROUTES
# ═══════════════════════════════════════════

@app.route("/")
def index():
    return render_template("index.html", version=VERSION)


@app.route("/api/health")
def api_health():
    return jsonify({"status": "ok", "version": VERSION, "time": datetime.now().isoformat()})


@app.route("/api/history")
def api_history():
    return jsonify(get_history(request.args.get("q", "").strip()))


@app.route("/api/history/<int:sid>")
def api_history_detail(sid):
    r = get_search_by_id(sid)
    return jsonify(r) if r else (jsonify({"error": "Bulunamadı"}), 404)


@app.route("/api/history/<int:sid>", methods=["DELETE"])
def api_delete_history(sid):
    try:
        with db() as conn:
            conn.execute("DELETE FROM searches WHERE id = ?", (sid,))
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/history", methods=["DELETE"])
def api_clear_history():
    try:
        with db() as conn:
            conn.execute("DELETE FROM searches")
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── MAIN ANALYZE ENDPOINT (SSE) ──
@app.route("/api/analyze")
def analyze():
    """GET /api/analyze?email=&username=&domain=&name="""
    email    = request.args.get("email", "").strip().lower()
    username = clean_username(request.args.get("username", ""))
    domain   = clean_domain(request.args.get("domain", ""))
    name     = request.args.get("name", "").strip()[:100]

    if not any([email, username, domain]):
        return jsonify({"error": "En az bir hedef (email / username / domain) gerekli"}), 400

    err = validate_inputs(email, username, domain)
    if err:
        return jsonify({"error": err}), 400

    if email and not domain:
        domain = email.split("@")[-1]
    if email and not username:
        local = email.split("@")[0]
        username = local if USERNAME_RE.match(local) else ""

    inputs = {"email": email, "username": username, "domain": domain, "name": name}

    def generate():
        results = {}
        yield sse_event("start", {"inputs": inputs, "timestamp": datetime.now().isoformat()})
        yield sse_log(f"MailReaper v{VERSION} başlatıldı — modüller paralel çalışıyor", "info", "system")
        yield sse_log("Hedefler: " + " | ".join(f"{k}={v}" for k, v in inputs.items() if v), "info", "system")

        tasks = {}

        if email:
            def t_email(c):
                val = validate_email(email)
                c.log(f"Email: {'geçerli' if val.get('valid_syntax') else 'geçersiz'}"
                      f"{' | Disposable!' if val.get('is_disposable') else ''} | Provider: {val.get('provider', '?')}", "success")
                return {"email_validator": val, "email_parts": get_email_parts(email)}
            tasks["email_validator"] = Task("Email Validator", t_email)

            def t_gravatar(c):
                g = lookup_gravatar(email)
                c.log("Gravatar profili bulundu: " + str(g.get("display_name", "")) if g.get("has_gravatar")
                      else "Gravatar profili yok", "success" if g.get("has_gravatar") else "info")
                return {"gravatar": g}
            tasks["gravatar"] = Task("Gravatar", t_gravatar)

            def t_paste(c):
                p = search_paste_sites(email)
                n = p.get("total_found", 0)
                stealer = any("Stealer" in f.get("source", "") for f in p.get("findings", []))
                c.log(f"STEALER LOG BULUNDU! {n} kayıt" if stealer else (f"Paste: {n} kayıt" if n else "Paste: temiz"),
                      "error" if stealer else "warning" if n else "info")
                return {"pastebin": p}
            tasks["pastebin"] = Task("Paste & Stealer Logs", t_paste)

        if domain:
            def t_dns(c):
                d = analyze_domain(domain)
                c.log(f"DNS: {'SPF ✓' if d.get('spf', {}).get('exists') else 'SPF ✗'} | "
                      f"{'DMARC ✓' if d.get('dmarc', {}).get('exists') else 'DMARC ✗'} | "
                      f"{len(d.get('mx_records') or [])} MX", "success")
                out = {"dns_analysis": d}
                if email:                     # SMTP probe MX bilgisine ihtiyaç duyar
                    c.log("SMTP bağlantısı test ediliyor...")
                    try:
                        s = probe_smtp(email, d)
                        out["smtp_probe"] = s
                        c.log(f"SMTP: {s.get('server_used', '')}{' | Catch-all!' if s.get('catch_all') else ''}"
                              if s.get("smtp_reachable") else f"SMTP erişilemiyor: {s.get('error', '')}",
                              "success" if s.get("smtp_reachable") else "warning")
                    except Exception as e:
                        c.log(f"SMTP hatası: {e}", "error")
                return out
            tasks["dns_analysis"] = Task("DNS / WHOIS / SSL", t_dns)

            def t_web(c):
                w = web_recon(domain)
                if w.get("reachable"):
                    c.log(f"Web: {w.get('status')} | Güvenlik {w.get('security_grade')} | "
                          f"{len(w.get('technologies', []))} teknoloji | {len(w.get('emails', []))} email", "success")
                else:
                    c.log("Web: siteye bağlanılamadı", "warning")
                return {"web_recon": w}
            tasks["web_recon"] = Task("Web Recon", t_web)

            def t_ip(c):
                r = ip_intel(domain)
                if r.get("ips"):
                    first = r["ips"][0]
                    c.log(f"IP: {first['ip']} | {first.get('asn', '?')} {first.get('org', '')}", "success")
                else:
                    c.log("IP çözümlenemedi", "warning")
                return {"ip_intel": r}
            tasks["ip_intel"] = Task("IP / ASN", t_ip)

        if email or username:
            def t_github(c):
                gh = search_github(email or "", username or "")
                if gh.get("github_user"):
                    c.log(f"GitHub: @{gh['github_user'].get('login', '')} ({gh['github_user'].get('public_repos', 0)} repo)", "success")
                if gh.get("commits_found"):
                    c.log(f"{len(gh['commits_found'])} commit'te email bulundu", "warning")
                return {"github_search": gh}
            tasks["github_search"] = Task("GitHub", t_github)

        if username:
            def t_ghdeep(c):
                g = scrape_github_deep(username)
                if g.get("found"):
                    c.log(f"GitHub Deep: {len(g.get('repos', []))} repo | "
                          f"{', '.join(list(g.get('languages', {}))[:4])}", "success")
                return {"github_deep": g}
            tasks["github_deep"] = Task("GitHub Deep", t_ghdeep)

            def t_reddit(c):
                r = scrape_reddit(username)
                if r.get("found"):
                    c.log(f"Reddit: u/{r.get('profile', {}).get('username', '')} | Karma {r.get('profile', {}).get('total_karma', 0)}", "success")
                else:
                    c.log("Reddit: kullanıcı yok")
                return {"reddit": r}
            tasks["reddit"] = Task("Reddit", t_reddit)

            def t_hn(c):
                h = scrape_hackernews(username)
                if h.get("found"):
                    c.log(f"HN: karma {h.get('profile', {}).get('karma', 0)}", "success")
                return {"hackernews": h}
            tasks["hackernews"] = Task("HackerNews", t_hn)

            def t_sherlock(c):
                state = {"last": 0}

                def cb(done, total, platform, hit):
                    if hit:
                        c.log(f"✔ {hit['platform']} (%{hit['confidence']})", "success")
                    elif done - state["last"] >= 25:
                        state["last"] = done
                        c.log(f"Taranıyor... {done}/{total}")
                un = username_osint(username, cb)
                c.log(f"Username OSINT: {un.get('found_count', 0)}/{un.get('total_checked', 0)} sitede bulundu",
                      "success" if un.get("found_count") else "info")
                return {"username_osint": un}
            tasks["username_osint"] = Task("Sherlock (125+ site)", t_sherlock)

            def t_social(c):
                s = check_social_media(email or f"{username}@example.com")
                c.log(f"Sosyal medya: {s.get('total_found', 0)} profil", "success")
                return {"social": s}
            tasks["social"] = Task("Sosyal Medya", t_social)

            def t_ungen(c):
                u = generate_usernames(email or f"{username}@example.com")
                c.log(f"{len(u.get('usernames', []))} kullanıcı adı varyasyonu üretildi", "success")
                return {"username_gen": u}
            tasks["username_gen"] = Task("Username Generator", t_ungen)

        if domain or email:
            def t_crt(c):
                crt = crt_full_search(email=email or None, domain=domain or None, name=name or None)
                c.log(f"crt.sh: {len((crt.get('email_results') or {}).get('entries', []))} kayıt | "
                      f"{len(crt.get('all_subdomains', []))} subdomain", "success")
                return {"crt_search": crt}
            tasks["crt_search"] = Task("crt.sh", t_crt)

        if username or email:
            def t_wayback(c):
                wb = {}
                if username:
                    wb["username_history"] = search_username_history(username)
                if email:
                    wb["email_history"] = search_email_history(email)
                if domain:
                    wb["domain_history"] = search_domain_history(domain, limit=15)
                c.log("Wayback arşivi tarandı", "success")
                return {"wayback": wb}
            tasks["wayback"] = Task("Wayback Machine", t_wayback)

        def t_dork(c):
            d = generate_dorks(email=email or None, username=username or None,
                               name=name or None, domain=domain or None)
            c.log(f"{len(d.get('all_queries', []))} dork üretildi", "success")
            return {"dork_gen": d}
        tasks["dork_gen"] = Task("Dork Generator", t_dork)

        total = len(tasks) + 2          # + korelasyon/risk, + EXIF
        yield from run_tasks(tasks, results, total=total)

        # ─── 2. Aşama: tüm sonuçlara bağlı modüller ───
        yield sse_log("Bulgular birleştiriliyor...", "info", "correlation")
        try:
            corr = correlate(results)
            results["correlation"] = corr
            yield sse_result("correlation", corr)
            yield sse_log(f"Korelasyon: {len(corr.get('connections', []))} bağlantı | "
                          f"{len(corr.get('identified_platforms', []))} platform", "success", "correlation")
        except Exception as e:
            yield sse_log(f"Korelasyon hatası: {e}", "error", "correlation")
        try:
            risk = calculate_risk_score(results)
            results["risk_score"] = risk
            yield sse_result("risk_score", risk)
            yield sse_log(f"Risk: {risk['total']}/100 — Grade {risk['grade']} ({risk['grade_text']})",
                          "success" if risk['total'] < 40 else "warning" if risk['total'] < 70 else "error", "risk_scorer")
        except Exception as e:
            yield sse_log(f"Risk hatası: {e}", "error", "risk_scorer")
        yield sse_event("progress", {"current": total - 1, "total": total, "module": "Avatar / EXIF", "percent": 95})

        urls = [a["url"] for a in results.get("correlation", {}).get("avatar_urls", []) if a.get("url")][:3]
        if urls:
            yield sse_log(f"{len(urls)} profil fotoğrafı analiz ediliyor...", "info", "exif")
            exif_results = []
            with ThreadPoolExecutor(max_workers=3) as ex:
                for r in ex.map(lambda u: _safe(analyze_image_url, u), urls):
                    if r:
                        exif_results.append(r)
            results["exif_analysis"] = exif_results
            yield sse_result("exif_analysis", exif_results)

        save_search(inputs, results)
        yield sse_log("Sonuçlar kaydedildi.", "info", "system")
        yield sse_event("complete", {"inputs": inputs, "timestamp": datetime.now().isoformat(), "results": results})
        yield sse_log("Analiz tamamlandı!", "success", "system")

    return Response(generate(), mimetype="text/event-stream", headers=SSE_HEADERS)


def _safe(fn, *a):
    try:
        return fn(*a)
    except Exception:
        return None


# ═══════════════════════════════════════════
#  SORUŞTURMA MASASI — dosyalar (case) + pano
# ═══════════════════════════════════════════

MAX_BOARD_BYTES = 5_000_000
EMPTY_BOARD = {"nodes": [], "edges": [], "view": {"x": 0, "y": 0, "z": 1}}


def _case_row(r):
    try:
        board = json.loads(r[2]) or {}
    except Exception:
        board = {}
    board.setdefault("nodes", [])
    board.setdefault("edges", [])
    return {"id": r[0], "name": r[1], "board": board, "created_at": r[3], "updated_at": r[4]}


@app.route("/api/cases", methods=["GET"])
def api_cases():
    with db() as conn:
        rows = conn.execute("SELECT id, name, board_json, created_at, updated_at FROM cases ORDER BY id").fetchall()
    return jsonify([_case_row(r) for r in rows])


@app.route("/api/cases", methods=["POST"])
def api_case_create():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name") or "Yeni Dosya").strip()[:80] or "Yeni Dosya"
    board = data.get("board") if isinstance(data.get("board"), dict) else EMPTY_BOARD
    now = datetime.now().isoformat()
    with db() as conn:
        cur = conn.execute("INSERT INTO cases (name, board_json, created_at, updated_at) VALUES (?, ?, ?, ?)",
                           (name, json.dumps(board, ensure_ascii=False), now, now))
        cid = cur.lastrowid
        row = conn.execute("SELECT id, name, board_json, created_at, updated_at FROM cases WHERE id=?", (cid,)).fetchone()
    return jsonify(_case_row(row)), 201


@app.route("/api/cases/<int:cid>", methods=["PUT"])
def api_case_update(cid):
    data = request.get_json(silent=True) or {}
    sets, args = [], []
    if "name" in data:
        sets.append("name = ?")
        args.append(str(data["name"]).strip()[:80] or "Adsız Dosya")
    if "board" in data:
        if not isinstance(data["board"], dict):
            return jsonify({"error": "Geçersiz pano verisi"}), 400
        blob = json.dumps(data["board"], ensure_ascii=False)
        if len(blob.encode("utf-8")) > MAX_BOARD_BYTES:
            return jsonify({"error": "Pano çok büyük"}), 413
        sets.append("board_json = ?")
        args.append(blob)
    if not sets:
        return jsonify({"error": "Güncellenecek alan yok"}), 400
    now = datetime.now().isoformat()
    sets.append("updated_at = ?")
    args.append(now)
    with db() as conn:
        cur = conn.execute(f"UPDATE cases SET {', '.join(sets)} WHERE id = ?", (*args, cid))
        if cur.rowcount == 0:
            return jsonify({"error": "Dosya bulunamadı"}), 404
    return jsonify({"status": "ok", "updated_at": now})


@app.route("/api/cases/<int:cid>", methods=["DELETE"])
def api_case_delete(cid):
    with db() as conn:
        conn.execute("DELETE FROM cases WHERE id = ?", (cid,))
    return jsonify({"status": "ok"})


# ── EXPORT ──
@app.route("/api/export/json", methods=["POST"])
def export_json():
    data = request.get_json(silent=True) or {}
    email = data.get("email") or data.get("inputs", {}).get("email") or data.get("inputs", {}).get("username") or "target"
    try:
        filepath = exporter.export_json(email, data.get("results", {}))
        return send_file(filepath, as_attachment=True, download_name=os.path.basename(filepath))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/export/html", methods=["POST"])
def export_html():
    data = request.get_json(silent=True) or {}
    email = data.get("email") or data.get("inputs", {}).get("email") or data.get("inputs", {}).get("username") or "target"
    try:
        filepath = exporter.export_html(email, data.get("results", {}))
        return send_file(filepath, as_attachment=True, download_name=os.path.basename(filepath))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ═══════════════════════════════════════════
#  TARGET SCAN — Manuel hedef profili tarama
# ═══════════════════════════════════════════

def scrape_telegram(handle: str) -> dict:
    import requests as req
    from bs4 import BeautifulSoup
    url = f"https://t.me/{handle}"
    resp = req.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
    found = resp.status_code == 200 and "tgme_page" in resp.text
    soup = BeautifulSoup(resp.text, "html.parser")

    def txt(cls):
        el = soup.find(class_=cls)
        return el.get_text(strip=True) if el else None
    img = soup.find(class_="tgme_page_photo_image")
    return {"username": handle, "found": found, "profile_url": url,
            "name": txt("tgme_page_title"), "description": txt("tgme_page_description"),
            "profile_pic_url": img.get("src") if img else None, "info": txt("tgme_page_extra")}


@app.route("/api/target-scan")
def target_scan():
    """GET /api/target-scan?instagram=&twitter=&youtube=&tiktok=&spotify=&phone=&steam=&email=&..."""
    g = lambda k: request.args.get(k, "").strip()
    target = {
        "name": g("name")[:100], "email": g("email").lower(), "phone": g("phone")[:32],
        "username": clean_username(g("username")), "domain": clean_domain(g("domain")),
        "instagram": clean_username(g("instagram")), "twitter": clean_username(g("twitter")),
        "youtube": g("youtube"), "tiktok": clean_username(g("tiktok")), "spotify": g("spotify"),
        "steam": g("steam"), "reddit": clean_username(g("reddit")), "github": clean_username(g("github")),
        "telegram": clean_username(g("telegram")), "discord": g("discord"),
        "linkedin": g("linkedin"), "facebook": g("facebook"), "custom_urls": g("custom_urls"),
    }
    if target["email"] and not target["domain"] and "@" in target["email"]:
        target["domain"] = target["email"].split("@")[-1]
    if target["email"] and not target["username"] and "@" in target["email"]:
        target["username"] = target["email"].split("@")[0]

    if not any(v for k, v in target.items() if k != "custom_urls"):
        return jsonify({"error": "En az bir hedef bilgisi girin"}), 400
    err = validate_inputs(target["email"], "", target["domain"])
    if err:
        return jsonify({"error": err}), 400

    def generate():
        results = {"target_inputs": target}
        yield sse_event("start", {"target": target, "timestamp": datetime.now().isoformat()})
        yield sse_log("Hedef taraması başlatıldı: " +
                      (target.get("name") or target.get("email") or target.get("username") or "Hedef"), "info", "system")

        tasks = {}

        def platform(key, label, fn, ok_msg):
            """Standart platform görevi: bulundu/bulunamadı logu ile."""
            def run(c):
                r = fn(target[key])
                if isinstance(r, dict) and r.get("found"):
                    c.log(ok_msg(r), "success")
                else:
                    c.log(f"{label}: bulunamadı {('— ' + str(r.get('error'))) if isinstance(r, dict) and r.get('error') else ''}", "warning")
                return {key: r}
            tasks[key] = Task(label, run)

        if target["instagram"]:
            platform("instagram", "Instagram", scrape_instagram,
                     lambda r: f"Instagram: {r.get('full_name', '')} | {r.get('followers', '')} takipçi | {'gizli' if r.get('is_private') else 'açık'}")
        if target["twitter"]:
            platform("twitter", "Twitter/X", scrape_twitter,
                     lambda r: f"Twitter: {r.get('full_name', '')} | {r.get('stats', {}).get('followers', '')} takipçi")
        if target["youtube"]:
            platform("youtube", "YouTube", scrape_youtube,
                     lambda r: f"YouTube: {r.get('name', '')} | {r.get('subscriber_count', '')} abone")
        if target["tiktok"]:
            platform("tiktok", "TikTok", scrape_tiktok,
                     lambda r: f"TikTok: {r.get('nickname', '')} | {r.get('followers', '')} takipçi")
        if target["spotify"]:
            platform("spotify", "Spotify", scrape_spotify,
                     lambda r: f"Spotify: {r.get('display_name', '')} | {r.get('followers', '')} takipçi")
        if target["steam"]:
            platform("steam", "Steam", scrape_steam,
                     lambda r: f"Steam: {r.get('username', '')} | Seviye {r.get('level', '')}"
                               f"{' | VAC BAN' if r.get('is_vac_banned') else ''}")
        if target["reddit"]:
            platform("reddit", "Reddit", scrape_reddit,
                     lambda r: f"Reddit: u/{r.get('profile', {}).get('username', '')} | Karma {r.get('profile', {}).get('total_karma', 0)}")
        if target["github"]:
            def t_gh(c):
                r = scrape_github_deep(target["github"])
                if r.get("found"):
                    p = r.get("profile", {})
                    c.log(f"GitHub: {p.get('name', '')} | {p.get('public_repos', 0)} repo | {p.get('followers', 0)} takipçi", "success")
                return {"github_deep": r}
            tasks["github_deep"] = Task("GitHub", t_gh)
        if target["telegram"]:
            platform("telegram", "Telegram", scrape_telegram, lambda r: f"Telegram: {r.get('name') or r.get('username')}")

        if target["phone"]:
            def t_phone(c):
                ph = analyze_phone(target["phone"])
                c.log(f"Telefon: {ph.get('country', '')} | Olası: {', '.join(ph.get('possible_carriers', [])[:2])}"
                      if ph.get("valid_format") else f"Telefon: {ph.get('error', 'Geçersiz format')}",
                      "success" if ph.get("valid_format") else "warning")
                return {"phone": ph}
            tasks["phone"] = Task("Telefon Analizi", t_phone)

        if target["email"]:
            def t_email(c):
                val = validate_email(target["email"])
                out = {"email_validator": val, "email_parts": get_email_parts(target["email"]),
                       "gravatar": lookup_gravatar(target["email"]),
                       "pastebin": search_paste_sites(target["email"])}
                n = out["pastebin"].get("total_found", 0)
                c.log(f"Email: {val.get('provider', '')} | {'Disposable!' if val.get('is_disposable') else 'Normal'}"
                      f"{f' | {n} paste/sızıntı kaydı' if n else ''}", "warning" if n else "success")
                return out
            tasks["email"] = Task("Email", t_email)

        if target["domain"]:
            def t_dom(c):
                out = {"dns_analysis": analyze_domain(target["domain"]),
                       "crt_search": crt_full_search(email=target.get("email") or None, domain=target["domain"])}
                c.log(f"DNS/crt.sh: {len(out['crt_search'].get('all_subdomains', []))} subdomain", "success")
                return out
            tasks["domain"] = Task("DNS / crt.sh", t_dom)

        if target["username"] and not (target["email"] and target["username"] == target["email"].split("@")[0]):
            def t_sher(c):
                un = username_osint(target["username"])
                c.log(f"Sherlock: {un.get('found_count', 0)}/{un.get('total_checked', 0)} sitede bulundu", "success")
                return {"username_osint": un}
            tasks["username_osint"] = Task("Sherlock", t_sher)

        def t_dork(c):
            d = generate_dorks(email=target.get("email") or None,
                               username=target.get("username") or target.get("github") or target.get("instagram") or None,
                               name=target.get("name") or None, domain=target.get("domain") or None)
            c.log(f"{len(d.get('all_queries', []))} dork üretildi", "success")
            return {"dork_gen": d}
        tasks["dork_gen"] = Task("Dork Generator", t_dork)

        total = len(tasks) + 1
        yield from run_tasks(tasks, results, total=total)

        # Avatar EXIF
        urls = []
        for mod in ("instagram", "twitter", "youtube", "tiktok", "spotify", "steam", "telegram", "gravatar", "github_deep"):
            r = results.get(mod)
            if isinstance(r, dict):
                u = r.get("profile_pic_url") or r.get("avatar_url")
                if u:
                    urls.append((mod, u))
        if urls:
            yield sse_log(f"{len(urls[:4])} avatar analiz ediliyor...", "info", "exif")
            exif_results = []
            for src, u in urls[:4]:
                er = _safe(analyze_image_url, u)
                if er:
                    er["source"] = src
                    exif_results.append(er)
            results["exif_analysis"] = exif_results
            yield sse_result("exif_analysis", exif_results)

        try:
            corr = correlate(results)
            results["correlation"] = corr
            yield sse_result("correlation", corr)
            yield sse_log(f"Korelasyon: {len(corr.get('connections', []))} bağlantı | "
                          f"{len(corr.get('identified_platforms', []))} platform", "success", "correlation")
        except Exception as e:
            yield sse_log(f"Korelasyon hatası: {e}", "error", "correlation")

        save_search(target, results, scan_type="target")
        yield sse_event("complete", {"target": target, "timestamp": datetime.now().isoformat(), "results": results})
        yield sse_log("Hedef taraması tamamlandı!", "success", "system")

    return Response(generate(), mimetype="text/event-stream", headers=SSE_HEADERS)


init_db()


if __name__ == "__main__":
    print(f"""
    ==========================================
       MailReaper v{VERSION} - OSINT Workstation
       http://127.0.0.1:5001
       Paralel tarama | API-free | Yerel
    ==========================================
    """)
    # Sadece yerel makineden erişilir; debug kapalı (Werkzeug konsolu uzaktan kod çalıştırır)
    app.run(host=os.environ.get("MAILREAPER_HOST", "127.0.0.1"),
            port=int(os.environ.get("MAILREAPER_PORT", "5001")), debug=False, threaded=True)
