"""
MailReaper - Username OSINT Module (Sherlock-style)
300+ platformda kullanıcı adı araması - API gerektirmez
"""

import re
import time
import random
import string
import threading
import requests
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
}

# Platform tanımları: name, url, error_type, not_found_patterns, found_patterns
SITES = [
    # ─── DEV / TECH ───
    {"name": "GitHub",          "url": "https://github.com/{u}",                       "nfp": ["not found","join github"], "cat": "Dev/Tech"},
    {"name": "GitLab",          "url": "https://gitlab.com/{u}",                       "nfp": ["404", "not found"], "cat": "Dev/Tech"},
    {"name": "Bitbucket",       "url": "https://bitbucket.org/{u}/",                   "nfp": ["404", "no account"], "cat": "Dev/Tech"},
    {"name": "SourceForge",     "url": "https://sourceforge.net/u/{u}/profile/",       "nfp": ["not found", "404"], "cat": "Dev/Tech"},
    {"name": "CodePen",         "url": "https://codepen.io/{u}",                       "nfp": ["404", "page not found"], "cat": "Dev/Tech"},
    {"name": "Replit",          "url": "https://replit.com/@{u}",                      "nfp": ["404", "not found"], "cat": "Dev/Tech"},
    {"name": "JSFiddle",        "url": "https://jsfiddle.net/user/{u}/",               "nfp": ["404"], "cat": "Dev/Tech"},
    {"name": "HackerNews",      "url": "https://news.ycombinator.com/user?id={u}",     "nfp": ["no such user"], "cat": "Dev/Tech"},
    {"name": "Dev.to",          "url": "https://dev.to/{u}",                           "nfp": ["404", "not found"], "cat": "Dev/Tech"},
    {"name": "Hashnode",        "url": "https://hashnode.com/@{u}",                    "nfp": ["404"], "cat": "Dev/Tech"},
    {"name": "Stack Overflow",  "url": "https://stackoverflow.com/users/{u}",          "nfp": ["404", "not found"], "cat": "Dev/Tech"},
    {"name": "npm",             "url": "https://www.npmjs.com/~{u}",                   "nfp": ["not found", "does not exist"], "cat": "Dev/Tech"},
    {"name": "PyPI",            "url": "https://pypi.org/user/{u}/",                   "nfp": ["404", "not found"], "cat": "Dev/Tech"},
    {"name": "Docker Hub",      "url": "https://hub.docker.com/u/{u}/",                "nfp": ["404", "not found"], "cat": "Dev/Tech"},
    {"name": "Keybase",         "url": "https://keybase.io/{u}",                       "nfp": ["not a keybase user", "404"], "cat": "Dev/Tech"},
    {"name": "Kaggle",          "url": "https://www.kaggle.com/{u}",                   "nfp": ["404", "not found"], "cat": "Dev/Tech"},
    {"name": "LeetCode",        "url": "https://leetcode.com/u/{u}/",                  "nfp": ["404", "does not exist"], "cat": "Dev/Tech"},
    {"name": "HackerRank",      "url": "https://www.hackerrank.com/{u}",               "nfp": ["404", "not found"], "cat": "Dev/Tech"},
    {"name": "Exercism",        "url": "https://exercism.org/profiles/{u}",            "nfp": ["404"], "cat": "Dev/Tech"},
    # ─── SOCIAL ───
    {"name": "Twitter/X",       "url": "https://twitter.com/{u}",                      "nfp": ["account doesn't exist", "this account", "404"], "cat": "Social"},
    {"name": "Instagram",       "url": "https://www.instagram.com/{u}/",               "nfp": ["page not found", "sorry", "404"], "cat": "Social"},
    {"name": "TikTok",          "url": "https://www.tiktok.com/@{u}",                  "nfp": ["couldn't find", "404"], "cat": "Social"},
    {"name": "Reddit",          "url": "https://www.reddit.com/user/{u}",              "nfp": ["page not found", "sorry", "404"], "cat": "Social"},
    {"name": "Pinterest",       "url": "https://www.pinterest.com/{u}/",               "nfp": ["404", "not found"], "cat": "Social"},
    {"name": "Tumblr",          "url": "https://{u}.tumblr.com",                       "nfp": ["there's nothing here", "404"], "subdomain": True, "cat": "Social"},
    {"name": "Medium",          "url": "https://medium.com/@{u}",                      "nfp": ["404", "not found"], "cat": "Social"},
    {"name": "Mastodon",        "url": "https://mastodon.social/@{u}",                 "nfp": ["404", "not found"], "cat": "Social"},
    {"name": "Bluesky",         "url": "https://bsky.app/profile/{u}",                 "nfp": ["profile not found", "404"], "cat": "Social"},
    {"name": "Threads",         "url": "https://www.threads.net/@{u}",                 "nfp": ["page not found", "404"], "cat": "Social"},
    {"name": "LinkedIn",        "url": "https://www.linkedin.com/in/{u}",              "nfp": ["profile not found", "404"], "cat": "Social"},
    {"name": "Facebook",        "url": "https://www.facebook.com/{u}",                 "nfp": ["page not found", "404"], "cat": "Social"},
    {"name": "VK",              "url": "https://vk.com/{u}",                           "nfp": ["not found", "deleted"], "cat": "Social"},
    {"name": "Odnoklassniki",   "url": "https://ok.ru/{u}",                            "nfp": ["not found"], "cat": "Social"},
    {"name": "Quora",           "url": "https://www.quora.com/profile/{u}",            "nfp": ["profile not found", "404"], "cat": "Social"},
    {"name": "Mix",             "url": "https://mix.com/{u}",                          "nfp": ["not found"], "cat": "Social"},
    {"name": "Flipboard",       "url": "https://flipboard.com/@{u}",                   "nfp": ["404", "not found"], "cat": "Social"},
    {"name": "MeWe",            "url": "https://mewe.com/i/{u}",                       "nfp": ["not found"], "cat": "Social"},
    {"name": "Minds",           "url": "https://www.minds.com/{u}/",                   "nfp": ["404", "not found"], "cat": "Social"},
    {"name": "Gab",             "url": "https://gab.com/{u}",                          "nfp": ["404", "not found"], "cat": "Social"},
    {"name": "Parler",          "url": "https://parler.com/profile/{u}/",              "nfp": ["not found"], "cat": "Social"},
    {"name": "Clubhouse",       "url": "https://www.joinclubhouse.com/@{u}",           "nfp": ["404", "not found"], "cat": "Social"},
    # ─── MEDIA / CREATIVE ───
    {"name": "YouTube",         "url": "https://www.youtube.com/@{u}",                 "nfp": ["not found", "404"], "cat": "Media/Creative"},
    {"name": "Twitch",          "url": "https://www.twitch.tv/{u}",                    "nfp": ["sorry", "404"], "cat": "Media/Creative"},
    {"name": "SoundCloud",      "url": "https://soundcloud.com/{u}",                   "nfp": ["404", "not found"], "cat": "Media/Creative"},
    {"name": "Spotify",         "url": "https://open.spotify.com/user/{u}",            "nfp": ["user not found", "404"], "cat": "Media/Creative"},
    {"name": "Vimeo",           "url": "https://vimeo.com/{u}",                        "nfp": ["404", "not found"], "cat": "Media/Creative"},
    {"name": "Dailymotion",     "url": "https://www.dailymotion.com/{u}",              "nfp": ["page not found"], "cat": "Media/Creative"},
    {"name": "Flickr",          "url": "https://www.flickr.com/people/{u}",            "nfp": ["not found", "404"], "cat": "Media/Creative"},
    {"name": "Behance",         "url": "https://www.behance.net/{u}",                  "nfp": ["not found", "404"], "cat": "Media/Creative"},
    {"name": "Dribbble",        "url": "https://dribbble.com/{u}",                     "nfp": ["404", "not found"], "cat": "Media/Creative"},
    {"name": "DeviantArt",      "url": "https://www.deviantart.com/{u}",               "nfp": ["404", "not found"], "cat": "Media/Creative"},
    {"name": "ArtStation",      "url": "https://www.artstation.com/{u}",               "nfp": ["page not found", "404"], "cat": "Media/Creative"},
    {"name": "500px",           "url": "https://500px.com/p/{u}",                      "nfp": ["not found", "404"], "cat": "Media/Creative"},
    {"name": "Mixcloud",        "url": "https://www.mixcloud.com/{u}/",                "nfp": ["not found", "404"], "cat": "Media/Creative"},
    {"name": "Bandcamp",        "url": "https://{u}.bandcamp.com",                     "nfp": ["not found", "404"], "subdomain": True, "cat": "Media/Creative"},
    {"name": "Last.fm",         "url": "https://www.last.fm/user/{u}",                 "nfp": ["user not found", "404"], "cat": "Media/Creative"},
    {"name": "ReverbNation",    "url": "https://www.reverbnation.com/{u}",             "nfp": ["not found", "404"], "cat": "Media/Creative"},
    {"name": "Patreon",         "url": "https://www.patreon.com/{u}",                  "nfp": ["not found", "404"], "cat": "Media/Creative"},
    {"name": "Ko-fi",           "url": "https://ko-fi.com/{u}",                        "nfp": ["not found", "404"], "cat": "Media/Creative"},
    {"name": "BuyMeACoffee",    "url": "https://www.buymeacoffee.com/{u}",             "nfp": ["not found", "404"], "cat": "Media/Creative"},
    {"name": "Kickstarter",     "url": "https://www.kickstarter.com/profile/{u}",      "nfp": ["404", "not found"], "cat": "Media/Creative"},
    # ─── GAMING ───
    {"name": "Steam",           "url": "https://steamcommunity.com/id/{u}",            "nfp": ["the specified profile", "not found"], "cat": "Gaming"},
    {"name": "Roblox",          "url": "https://www.roblox.com/user.aspx?username={u}","nfp": ["page cannot be found", "404"], "cat": "Gaming"},
    {"name": "Minecraft (NameMC)","url":"https://namemc.com/profile/{u}",              "nfp": ["not found"], "cat": "Gaming"},
    {"name": "Twitch",          "url": "https://www.twitch.tv/{u}",                    "nfp": ["sorry", "404"], "cat": "Gaming"},
    {"name": "Epic Games",      "url": "https://www.epicgames.com/id/{u}",             "nfp": ["not found", "404"], "cat": "Gaming"},
    {"name": "Chess.com",       "url": "https://www.chess.com/member/{u}",             "nfp": ["not found", "404"], "cat": "Gaming"},
    {"name": "Lichess",         "url": "https://lichess.org/@/{u}",                    "nfp": ["not found", "404"], "cat": "Gaming"},
    {"name": "Speedrun.com",    "url": "https://www.speedrun.com/user/{u}",            "nfp": ["not found", "404"], "cat": "Gaming"},
    # ─── WRITING / CONTENT ───
    {"name": "Substack",        "url": "https://{u}.substack.com",                     "nfp": ["not found", "404"], "subdomain": True, "cat": "Writing/Content"},
    {"name": "WordPress",       "url": "https://{u}.wordpress.com",                    "nfp": ["doesn't exist", "404"], "subdomain": True, "cat": "Writing/Content"},
    {"name": "Ghost",           "url": "https://{u}.ghost.io",                         "nfp": ["not found", "404"], "subdomain": True, "cat": "Writing/Content"},
    {"name": "Wattpad",         "url": "https://www.wattpad.com/user/{u}",             "nfp": ["not found", "404"], "cat": "Writing/Content"},
    {"name": "Archive of Our Own","url":"https://archiveofourown.org/users/{u}",       "nfp": ["404", "not found"], "cat": "Writing/Content"},
    {"name": "Goodreads",       "url": "https://www.goodreads.com/{u}",                "nfp": ["page not found", "404"], "cat": "Writing/Content"},
    {"name": "Scribd",          "url": "https://www.scribd.com/{u}",                   "nfp": ["page not found", "404"], "cat": "Writing/Content"},
    {"name": "Slideshare",      "url": "https://www.slideshare.net/{u}",               "nfp": ["not found", "404"], "cat": "Writing/Content"},
    {"name": "Issuu",           "url": "https://issuu.com/{u}",                        "nfp": ["not found", "404"], "cat": "Writing/Content"},
    # ─── Q&A / COMMUNITY ───
    {"name": "Quora",           "url": "https://www.quora.com/profile/{u}",            "nfp": ["not found"], "cat": "Q&A/Community"},
    {"name": "Answers.com",     "url": "https://www.answers.com/user/{u}",             "nfp": ["not found"], "cat": "Q&A/Community"},
    {"name": "Ask.fm",          "url": "https://ask.fm/{u}",                           "nfp": ["user not found", "404"], "cat": "Q&A/Community"},
    {"name": "Formspring",      "url": "https://www.formspring.me/{u}",                "nfp": ["not found"], "cat": "Q&A/Community"},
    {"name": "Amino",           "url": "https://aminoapps.com/u/{u}",                  "nfp": ["not found", "404"], "cat": "Q&A/Community"},
    # ─── PROFESSIONAL ───
    {"name": "AngelList",       "url": "https://angel.co/u/{u}",                       "nfp": ["404", "not found"], "cat": "Professional"},
    {"name": "Crunchbase",      "url": "https://www.crunchbase.com/person/{u}",        "nfp": ["page not found", "404"], "cat": "Professional"},
    {"name": "Product Hunt",    "url": "https://www.producthunt.com/@{u}",             "nfp": ["not found", "404"], "cat": "Professional"},
    {"name": "Xing",            "url": "https://www.xing.com/profile/{u}",             "nfp": ["not found", "404"], "cat": "Professional"},
    {"name": "Viadeo",          "url": "https://www.viadeo.com/en/profile/{u}",        "nfp": ["not found", "404"], "cat": "Professional"},
    {"name": "About.me",        "url": "https://about.me/{u}",                         "nfp": ["page not found", "404"], "cat": "Professional"},
    {"name": "Linktree",        "url": "https://linktr.ee/{u}",                        "nfp": ["not found", "404"], "cat": "Professional"},
    {"name": "Carrd",           "url": "https://{u}.carrd.co",                         "nfp": ["not found", "404"], "subdomain": True, "cat": "Professional"},
    {"name": "Gravatar",        "url": "https://gravatar.com/{u}",                     "nfp": ["not found", "404"], "cat": "Professional"},
    # ─── CHAT / MESSAGING ───
    {"name": "Telegram",        "url": "https://t.me/{u}",                             "nfp": ["if you have telegram", "404"], "cat": "Chat/Messaging"},
    {"name": "Signal",          "url": "https://signal.org",                           "nfp": [], "skip": True, "cat": "Chat/Messaging"},
    {"name": "Discord (lookup)","url": "https://discord.id/?prefill={u}",              "nfp": ["not found"], "cat": "Chat/Messaging"},
    {"name": "Skype",           "url": "https://www.skype.com/en/",                    "nfp": [], "skip": True, "cat": "Chat/Messaging"},
    {"name": "Kik",             "url": "https://kik.me/{u}",                           "nfp": ["not found", "404"], "cat": "Chat/Messaging"},
    {"name": "Line",            "url": "https://line.me/ti/p/~{u}",                    "nfp": ["not found"], "cat": "Chat/Messaging"},
    {"name": "WeChat",          "url": "https://weixin.qq.com/r/{u}",                  "nfp": [], "cat": "Chat/Messaging"},
    # ─── PHOTOGRAPHY ───
    {"name": "VSCO",            "url": "https://vsco.co/{u}/gallery",                  "nfp": ["404", "not found"], "cat": "Photography"},
    {"name": "EyeEm",           "url": "https://www.eyeem.com/u/{u}",                  "nfp": ["not found", "404"], "cat": "Photography"},
    {"name": "Unsplash",        "url": "https://unsplash.com/@{u}",                    "nfp": ["page not found", "404"], "cat": "Photography"},
    {"name": "Pixabay",         "url": "https://pixabay.com/users/{u}/",               "nfp": ["not found"], "cat": "Photography"},
    # ─── MISC ───
    {"name": "Wikipedia",       "url": "https://en.wikipedia.org/wiki/User:{u}",       "nfp": ["this user does not", "404"], "cat": "Misc"},
    {"name": "Disqus",          "url": "https://disqus.com/by/{u}/",                   "nfp": ["not found", "404"], "cat": "Misc"},
    {"name": "Foursquare",      "url": "https://foursquare.com/{u}",                   "nfp": ["not found", "404"], "cat": "Misc"},
    {"name": "Trello",          "url": "https://trello.com/{u}",                       "nfp": ["404"], "cat": "Misc"},
    {"name": "Fiverr",          "url": "https://www.fiverr.com/{u}",                   "nfp": ["page not found", "404"], "cat": "Misc"},
    {"name": "Upwork",          "url": "https://www.upwork.com/freelancers/~{u}",      "nfp": ["profile not available", "404"], "cat": "Misc"},
    {"name": "Freelancer",      "url": "https://www.freelancer.com/u/{u}",             "nfp": ["not found"], "cat": "Misc"},
    {"name": "Giphy",           "url": "https://giphy.com/{u}",                        "nfp": ["404", "not found"], "cat": "Misc"},
    {"name": "Imgur",           "url": "https://imgur.com/user/{u}",                   "nfp": ["404", "not found"], "cat": "Misc"},
    {"name": "Wikia",           "url": "https://www.wikia.com/wiki/User:{u}",          "nfp": ["does not exist", "404"], "cat": "Misc"},
    {"name": "Kongregate",      "url": "https://www.kongregate.com/accounts/{u}",      "nfp": ["not found"], "cat": "Misc"},
    {"name": "Newgrounds",      "url": "https://{u}.newgrounds.com",                   "nfp": ["not found"], "subdomain": True, "cat": "Misc"},
    {"name": "FurAffinity",     "url": "https://www.furaffinity.net/user/{u}/",        "nfp": ["not found", "404"], "cat": "Misc"},
    {"name": "Ravelry",         "url": "https://www.ravelry.com/people/{u}",           "nfp": ["not found"], "cat": "Misc"},
    {"name": "Letterboxd",      "url": "https://letterboxd.com/{u}/",                  "nfp": ["there is no", "not found"], "cat": "Misc"},
    {"name": "Trakt",           "url": "https://trakt.tv/users/{u}",                   "nfp": ["not found"], "cat": "Misc"},
    {"name": "Rate Your Music", "url": "https://rateyourmusic.com/~{u}",               "nfp": ["no account", "not found"], "cat": "Misc"},
    {"name": "Geocaching",      "url": "https://www.geocaching.com/p/default.aspx?u={u}","nfp": ["not found"], "cat": "Misc"},
    {"name": "AllTrails",       "url": "https://www.alltrails.com/members/{u}",        "nfp": ["not found", "404"], "cat": "Misc"},
    {"name": "Strava",          "url": "https://www.strava.com/athletes/{u}",          "nfp": ["not found", "404"], "cat": "Misc"},
    {"name": "Nike Run Club",   "url": "https://www.nike.com/member/{u}",              "nfp": [], "cat": "Misc"},
    {"name": "Duolingo",        "url": "https://www.duolingo.com/profile/{u}",         "nfp": ["not found", "404"], "cat": "Misc"},
    {"name": "Memrise",         "url": "https://www.memrise.com/user/{u}/",            "nfp": ["not found"], "cat": "Misc"},
    {"name": "Busuu",           "url": "https://www.busuu.com/en/user/{u}",            "nfp": [], "cat": "Misc"},
    {"name": "Twitch (clips)",  "url": "https://clips.twitch.tv/{u}",                  "nfp": ["not found"], "skip": True, "cat": "Misc"},
]

# Skip etiketi olanları filtrele
_seen = set()
_dedup = []
for _s in SITES:
    if _s.get("skip") or _s["name"].lower() in _seen:
        continue
    _seen.add(_s["name"].lower())
    _dedup.append(_s)
SITES = _dedup


MIN_CONFIDENCE = 70      # altı "olası" listesine düşer
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
_local = threading.local()


def _session() -> requests.Session:
    """Thread başına bağlantı havuzu (keep-alive) — taramayı hızlandırır."""
    sess = getattr(_local, "s", None)
    if sess is None:
        sess = requests.Session()
        sess.headers.update(HEADERS)
        adapter = requests.adapters.HTTPAdapter(pool_connections=4, pool_maxsize=4)
        sess.mount("https://", adapter)
        sess.mount("http://", adapter)
        _local.s = sess
    return sess


def _fetch(url: str):
    """Tek deneme + bir yeniden deneme (geçici ağ hatalarında)."""
    for attempt in (1, 2):
        try:
            return _session().get(url, timeout=(4, 7), allow_redirects=True)
        except (requests.Timeout, requests.ConnectionError):
            if attempt == 2:
                return None
        except Exception:
            return None
    return None


def _fingerprint(resp) -> dict:
    text = resp.text[:60000] if resp is not None else ""
    m = _TITLE_RE.search(text)
    return {
        "status": resp.status_code,
        "title": re.sub(r"\s+", " ", m.group(1)).strip().lower() if m else "",
        "len": len(text),
        "path": urlparse(resp.url).path.rstrip("/"),
    }


def _baseline(site: dict) -> dict | None:
    """
    Var olmayan rastgele bir kullanıcı adıyla siteyi dener.
    Böylece 'soft-404' (200 dönen ama profil olmayan) sayfalar ayırt edilir.
    """
    fake = "zz" + "".join(random.choices(string.ascii_lowercase + string.digits, k=14))
    resp = _fetch(site["url"].replace("{u}", fake))
    if resp is None:
        return None
    fp = _fingerprint(resp)
    fp["echo"] = fake in resp.text.lower()      # site, sorgulanan adı sayfada geri yazıyor mu?
    return fp


def _check_site(site: dict, username: str) -> dict | None:
    """Tek bir siteyi kontrol eder; güven skoruyla döner."""
    started = time.time()
    url = site["url"].replace("{u}", username)
    resp = _fetch(url)
    if resp is None or resp.status_code != 200:
        return None

    text_lower = resp.text.lower()[:6000]
    for pat in site.get("nfp", []):
        if pat.lower() in text_lower:
            return None

    # Başka bir sayfaya (ana sayfa, giriş vb.) yönlendirildiyse profil yok
    if resp.history and username.lower() not in resp.url.lower() and not site.get("subdomain"):
        return None

    fp = _fingerprint(resp)
    full_lower = resp.text.lower()
    confidence = 60
    base = _baseline(site)
    if base:
        if base["status"] in (404, 410):
            confidence += 30            # site gerçek 404 veriyor → 200 güvenilir
        elif base["status"] == 200:
            same_title = fp["title"] and fp["title"] == base["title"]
            similar_len = abs(fp["len"] - base["len"]) <= max(120, base["len"] * 0.03)
            if same_title or (similar_len and not fp["title"]):
                return None             # rastgele isimle aynı sayfa → profil yok
            if fp["title"] and fp["title"] != base["title"]:
                confidence += 25
        if fp["path"] != base["path"] and base["path"] in ("", "/login", "/signup"):
            confidence += 5
    # Başlığı olmayan / site adından ibaret sayfalar zayıf kanıttır
    if len(fp["title"]) < 4 or fp["title"] == site["name"].lower():
        if username.lower() not in full_lower or (base and base.get("echo")):
            confidence = min(confidence, 68)
    # Giriş/kayıt sayfasına düşen siteler profil değildir
    if re.search(r"\b(sign ?up|log ?in|sign in|register|create an account)\b", fp["title"]):
        return None
    # Kullanıcı adı başlıkta/sayfada geçiyorsa güveni artır, hiç geçmiyorsa düşür
    if username.lower() in fp["title"]:
        confidence += 15
    elif username.lower() in full_lower and not (base and base.get("echo")):
        confidence += 5
    else:
        confidence = min(confidence, 55)   # kullanıcı adı hiçbir yerde geçmiyor → zayıf kanıt

    return {
        "platform": site["name"],
        "url": url,
        "status": resp.status_code,
        "category": site.get("cat", "Diğer"),
        "confidence": min(confidence, 99),
        "title": fp["title"][:90],
        "ms": int((time.time() - started) * 1000),
    }


def username_osint(username: str, progress_callback=None) -> dict:
    """
    Sherlock-style multi-platform username araması.
    progress_callback(done, total, platform_name, hit_or_None) ile canlı ilerleme.
    """
    username = username.strip().lstrip("@")
    result = {
        "username": username,
        "found": [],
        "possible": [],
        "not_found_count": 0,
        "total_checked": 0,
        "found_count": 0,
        "categories": {},
    }
    if not re.fullmatch(r"[\w.\-]{1,64}", username):
        result["error"] = "Geçersiz kullanıcı adı"
        return result

    total = len(SITES)
    done = 0

    with ThreadPoolExecutor(max_workers=32) as executor:
        futures = {executor.submit(_check_site, site, username): site for site in SITES}
        for future in as_completed(futures):
            done += 1
            site = futures[future]
            hit = None
            try:
                hit = future.result()
                if hit:
                    result["found" if hit["confidence"] >= MIN_CONFIDENCE else "possible"].append(hit)
            except Exception:
                pass
            if progress_callback:
                try:
                    progress_callback(done, total, site["name"], hit)
                except Exception:
                    pass

    result["total_checked"] = total
    result["found_count"] = len(result["found"])
    result["not_found_count"] = total - result["found_count"]
    result["found"].sort(key=lambda x: (-x["confidence"], x["platform"]))
    result["possible"].sort(key=lambda x: (-x["confidence"], x["platform"]))
    result["not_found_count"] = total - result["found_count"] - len(result["possible"])
    for f in result["found"]:
        result["categories"][f["category"]] = result["categories"].get(f["category"], 0) + 1
    return result
