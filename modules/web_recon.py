"""
MailReaper - Web Recon
Domain'in web yüzü: yönlendirme zinciri, güvenlik başlıkları, teknoloji parmak izi,
robots.txt / sitemap / security.txt, sayfadan çıkan email ve sosyal linkler, favicon hash.
Sadece herkese açık sayfalara normal GET isteği yapar.
"""

import re
import html as htmllib
import base64
import struct
import requests
from urllib.parse import urljoin, urlparse

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
}

SEC_HEADERS = {
    "strict-transport-security": ("HSTS", 20),
    "content-security-policy": ("CSP", 25),
    "x-frame-options": ("X-Frame-Options", 15),
    "x-content-type-options": ("X-Content-Type-Options", 15),
    "referrer-policy": ("Referrer-Policy", 10),
    "permissions-policy": ("Permissions-Policy", 10),
    "cross-origin-opener-policy": ("COOP", 5),
}

TECH_SIGS = [
    ("WordPress", r"wp-content|wp-includes|wordpress"),
    ("Joomla", r"/media/jui/|joomla"),
    ("Drupal", r"drupal-settings-json|/sites/default/files"),
    ("Shopify", r"cdn\.shopify\.com|shopify\.theme"),
    ("Wix", r"static\.wixstatic\.com|wix\.com"),
    ("Squarespace", r"squarespace\.com|static1\.squarespace"),
    ("Webflow", r"webflow\.com|data-wf-page"),
    ("React", r"data-reactroot|react(?:-dom)?\.(?:production|development)|__REACT"),
    ("Next.js", r"/_next/static|__NEXT_DATA__"),
    ("Nuxt", r"/_nuxt/|__NUXT__"),
    ("Vue.js", r"vue(?:\.runtime)?(?:\.min)?\.js|data-v-[0-9a-f]{6}"),
    ("Angular", r"ng-version=|angular(?:\.min)?\.js"),
    ("jQuery", r"jquery[-.\d]*(?:\.min)?\.js"),
    ("Bootstrap", r"bootstrap(?:\.min)?\.(?:css|js)"),
    ("Tailwind CSS", r"tailwind"),
    ("Google Analytics", r"google-analytics\.com|gtag\("),
    ("Google Tag Manager", r"googletagmanager\.com/gtm\.js"),
    ("Facebook Pixel", r"connect\.facebook\.net/.*/fbevents\.js"),
    ("reCAPTCHA", r"google\.com/recaptcha"),
    ("Stripe", r"js\.stripe\.com"),
    ("Hotjar", r"static\.hotjar\.com"),
]

SOCIAL_RE = re.compile(
    r"https?://(?:www\.)?(?:twitter\.com|x\.com|instagram\.com|facebook\.com|linkedin\.com/(?:in|company)|"
    r"github\.com|youtube\.com/(?:@|channel|c|user)|t\.me|tiktok\.com/@|medium\.com/@|discord\.gg|"
    r"pinterest\.com|reddit\.com/(?:user|r))/?[\w.\-@/]*", re.I)
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
NOISE_EXT = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".css", ".js")


def _get(url, **kw):
    try:
        return requests.get(url, headers=HEADERS, timeout=kw.pop("timeout", 8),
                            allow_redirects=kw.pop("allow_redirects", True), **kw)
    except Exception:
        return None


def _murmur3_32(data: bytes) -> int:
    """Shodan favicon hash için MurmurHash3 (32-bit, signed)."""
    c1, c2 = 0xCC9E2D51, 0x1B873593
    h = 0
    rounded = len(data) & ~3
    for i in range(0, rounded, 4):
        k = struct.unpack("<I", data[i:i + 4])[0]
        k = (k * c1) & 0xFFFFFFFF
        k = ((k << 15) | (k >> 17)) & 0xFFFFFFFF
        k = (k * c2) & 0xFFFFFFFF
        h ^= k
        h = ((h << 13) | (h >> 19)) & 0xFFFFFFFF
        h = (h * 5 + 0xE6546B64) & 0xFFFFFFFF
    tail = data[rounded:]
    k = 0
    if len(tail) >= 3:
        k ^= tail[2] << 16
    if len(tail) >= 2:
        k ^= tail[1] << 8
    if len(tail) >= 1:
        k ^= tail[0]
        k = (k * c1) & 0xFFFFFFFF
        k = ((k << 15) | (k >> 17)) & 0xFFFFFFFF
        k = (k * c2) & 0xFFFFFFFF
        h ^= k
    h ^= len(data)
    h ^= h >> 16
    h = (h * 0x85EBCA6B) & 0xFFFFFFFF
    h ^= h >> 13
    h = (h * 0xC2B2AE35) & 0xFFFFFFFF
    h ^= h >> 16
    return h - (1 << 32) if h & 0x80000000 else h


def _favicon_hash(base_url: str, html: str):
    m = re.search(r'<link[^>]+rel=["\'](?:shortcut )?icon["\'][^>]*href=["\']([^"\']+)', html, re.I) \
        or re.search(r'<link[^>]+href=["\']([^"\']+)["\'][^>]*rel=["\'](?:shortcut )?icon', html, re.I)
    icon_url = urljoin(base_url, m.group(1)) if m else urljoin(base_url, "/favicon.ico")
    r = _get(icon_url, timeout=6)
    if r is None or r.status_code != 200 or not r.content or len(r.content) > 500_000:
        return None
    b64 = base64.encodebytes(r.content)
    return {"url": icon_url, "mmh3": _murmur3_32(b64), "bytes": len(r.content)}


def web_recon(domain: str) -> dict:
    domain = domain.strip().lower().strip("/")
    out = {"domain": domain, "reachable": False, "redirects": [], "security_headers": {},
           "security_score": 0, "technologies": [], "emails": [], "social_links": [],
           "files": {}, "dork_links": []}

    resp = None
    for scheme in ("https", "http"):
        resp = _get(f"{scheme}://{domain}")
        if resp is not None:
            break
    if resp is None:
        out["error"] = "Siteye bağlanılamadı"
        return out

    out["reachable"] = True
    out["final_url"] = resp.url
    out["status"] = resp.status_code
    out["redirects"] = [{"status": h.status_code, "url": h.url} for h in resp.history]
    hdr = {k.lower(): v for k, v in resp.headers.items()}
    out["server"] = hdr.get("server")
    out["powered_by"] = hdr.get("x-powered-by")
    out["https"] = resp.url.startswith("https://")

    # Güvenlik başlıkları
    score = 0
    for key, (label, weight) in SEC_HEADERS.items():
        present = key in hdr
        out["security_headers"][label] = {"present": present, "value": (hdr.get(key) or "")[:140]}
        if present:
            score += weight
    if not out["https"]:
        score = max(score - 30, 0)
    out["security_score"] = min(score, 100)
    out["security_grade"] = ("A" if score >= 80 else "B" if score >= 60 else
                             "C" if score >= 40 else "D" if score >= 20 else "F")

    html = resp.text[:400_000] if "text" in hdr.get("content-type", "text") else ""
    t = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    out["title"] = htmllib.unescape(re.sub(r"\s+", " ", t.group(1))).strip()[:160] if t else None
    d = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']*)', html, re.I)
    out["description"] = htmllib.unescape(d.group(1))[:240] if d else None
    g = re.search(r'<meta[^>]+name=["\']generator["\'][^>]+content=["\']([^"\']*)', html, re.I)

    techs = set()
    if g:
        techs.add(g.group(1)[:40])
    blob = html + " " + " ".join(f"{k}:{v}" for k, v in hdr.items())
    for name, pat in TECH_SIGS:
        if re.search(pat, blob, re.I):
            techs.add(name)
    if "cf-ray" in hdr or "cloudflare" in (hdr.get("server") or "").lower():
        techs.add("Cloudflare")
    if hdr.get("x-powered-by"):
        techs.add(hdr["x-powered-by"][:40])
    if "x-vercel-id" in hdr:
        techs.add("Vercel")
    if "x-nf-request-id" in hdr:
        techs.add("Netlify")
    out["technologies"] = sorted(techs)

    # Sayfadan email ve sosyal link
    placeholder = ("@domain.com", "@example.com", "@email.com", "@yourdomain", "@sentry", "@2x", "@3x")
    emails = {e.lower() for e in EMAIL_RE.findall(html)
              if not e.lower().endswith(NOISE_EXT) and not any(x in e.lower() for x in placeholder)}
    out["emails"] = sorted(emails)[:25]
    own = domain.removeprefix("www.")
    out["social_links"] = sorted({m.group(0).rstrip("/") for m in SOCIAL_RE.finditer(html)
                                  if own not in m.group(0).lower()})[:25]

    # Standart dosyalar
    parsed = urlparse(resp.url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    for label, path in (("robots.txt", "/robots.txt"), ("security.txt", "/.well-known/security.txt"),
                        ("sitemap.xml", "/sitemap.xml"), ("humans.txt", "/humans.txt")):
        r = _get(base + path, timeout=6, allow_redirects=False)
        ok = bool(r is not None and r.status_code == 200 and "<html" not in r.text[:300].lower())
        entry = {"exists": ok, "url": base + path}
        if ok:
            entry["preview"] = r.text[:600]
            if label == "robots.txt":
                entry["disallowed"] = [ln.split(":", 1)[1].strip() for ln in r.text.splitlines()
                                       if ln.lower().startswith("disallow:") and ln.split(":", 1)[1].strip()][:30]
                entry["sitemaps"] = [ln.split(":", 1)[1].strip() for ln in r.text.splitlines()
                                     if ln.lower().startswith("sitemap:")][:5]
            if label == "security.txt":
                entry["contacts"] = re.findall(r"(?im)^contact:\s*(.+)$", r.text)[:5]
            out["emails"] = sorted(set(out["emails"]) | {e.lower() for e in EMAIL_RE.findall(r.text)})[:30]
        out["files"][label] = entry

    out["favicon"] = _favicon_hash(base, html)
    if out["favicon"]:
        out["dork_links"].append({"label": "Shodan — aynı favicon",
                                  "url": f"https://www.shodan.io/search?query=http.favicon.hash%3A{out['favicon']['mmh3']}"})
    out["dork_links"] += [
        {"label": "URLScan", "url": f"https://urlscan.io/search/#domain%3A{domain}"},
        {"label": "SecurityHeaders.com", "url": f"https://securityheaders.com/?q={domain}&followRedirects=on"},
        {"label": "BuiltWith", "url": f"https://builtwith.com/{domain}"},
    ]
    return out
