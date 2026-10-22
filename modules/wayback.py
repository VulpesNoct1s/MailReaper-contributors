"""
MailReaper - Wayback Machine Module
Internet Archive CDX API ile tarihsel kayıtları arar.
Tamamen ücretsiz, API key yok.
"""

import requests
from urllib.parse import quote, urlparse

CDX_BASE = "http://web.archive.org/cdx/search/cdx"
AVAIL_BASE = "https://archive.org/wayback/available"
HEADERS = {"User-Agent": "Mozilla/5.0 MailReaper OSINT Tool"}


def _cdx_query(url_pattern: str, limit: int = 20) -> list:
    """CDX API ile arama yapar."""
    try:
        params = {
            "url": url_pattern,
            "output": "json",
            "fl": "timestamp,original,statuscode,mimetype",
            "limit": limit,
            "collapse": "urlkey",
            "filter": "statuscode:200",
        }
        resp = requests.get(CDX_BASE, params=params, headers=HEADERS, timeout=12)
        if resp.status_code == 200:
            rows = resp.json()
            if rows and len(rows) > 1:
                keys = rows[0]
                return [dict(zip(keys, row)) for row in rows[1:]]
    except Exception:
        pass
    return []


def _format_snapshot(timestamp: str, original: str) -> dict:
    """CDX timestamp'ini okunabilir formata çevirir."""
    ts = timestamp
    try:
        year = ts[:4]
        month = ts[4:6]
        day = ts[6:8]
        hour = ts[8:10]
        minute = ts[10:12]
        formatted = f"{day}.{month}.{year} {hour}:{minute}"
    except Exception:
        formatted = ts

    return {
        "timestamp": timestamp,
        "date_formatted": formatted,
        "wayback_url": f"https://web.archive.org/web/{timestamp}/{original}",
        "original": original,
    }


def check_availability(url: str) -> dict:
    """Bir URL'nin Wayback Machine'de mevcut olup olmadığını kontrol eder."""
    try:
        resp = requests.get(
            AVAIL_BASE,
            params={"url": url},
            headers=HEADERS,
            timeout=8
        )
        if resp.status_code == 200:
            data = resp.json()
            snapshot = data.get("archived_snapshots", {}).get("closest", {})
            if snapshot and snapshot.get("available"):
                return {
                    "available": True,
                    "url": snapshot.get("url"),
                    "timestamp": snapshot.get("timestamp"),
                    "status": snapshot.get("status"),
                }
    except Exception:
        pass
    return {"available": False}


def search_username_history(username: str) -> dict:
    """Username ile ilgili sosyal medya profillerinin arşiv geçmişini arar."""
    result = {
        "username": username,
        "snapshots": [],
        "platforms_archived": [],
    }

    # Popüler platformlardaki profilleri tara
    profile_urls = [
        f"twitter.com/{username}",
        f"instagram.com/{username}",
        f"github.com/{username}",
        f"reddit.com/u/{username}",
        f"linkedin.com/in/{username}",
        f"facebook.com/{username}",
        f"tiktok.com/@{username}",
        f"twitch.tv/{username}",
        f"youtube.com/@{username}",
        f"medium.com/@{username}",
        f"soundcloud.com/{username}",
        f"pinterest.com/{username}",
        f"tumblr.com/{username}",
        f"deviantart.com/{username}",
        f"behance.net/{username}",
    ]

    for url in profile_urls:
        snaps = _cdx_query(url, limit=5)
        if snaps:
            platform = url.split("/")[0].split(".")[0]
            platform_snaps = [_format_snapshot(s["timestamp"], s["original"]) for s in snaps]
            result["snapshots"].extend(platform_snaps)
            result["platforms_archived"].append({
                "platform": platform.capitalize(),
                "url": url,
                "snapshot_count": len(platform_snaps),
                "latest": platform_snaps[0] if platform_snaps else None,
            })

    result["total_snapshots"] = len(result["snapshots"])
    return result


def search_email_history(email: str) -> dict:
    """Email adresiyle ilgili sayfalardaki arşiv kayıtlarını arar."""
    result = {
        "email": email,
        "direct_snapshots": [],
        "domain_snapshots": [],
    }

    domain = email.split("@")[-1] if "@" in email else email

    # Domain ana sayfası
    domain_snaps = _cdx_query(f"{domain}/*", limit=10)
    result["domain_snapshots"] = [
        _format_snapshot(s["timestamp"], s["original"]) for s in domain_snaps
    ]

    # Domain mail sayfaları
    mail_snaps = _cdx_query(f"{domain}/mail*", limit=5)
    result["domain_snapshots"].extend([
        _format_snapshot(s["timestamp"], s["original"]) for s in mail_snaps
    ])

    result["total_domain_snapshots"] = len(result["domain_snapshots"])
    return result


def search_domain_history(domain: str, limit: int = 30) -> dict:
    """Domain'in tüm Wayback Machine geçmişini çeker."""
    result = {
        "domain": domain,
        "snapshots": [],
        "first_seen": None,
        "last_seen": None,
        "total": 0,
    }

    snaps = _cdx_query(f"{domain}/*", limit=limit)
    if snaps:
        formatted = [_format_snapshot(s["timestamp"], s["original"]) for s in snaps]
        result["snapshots"] = formatted
        result["total"] = len(formatted)

        # İlk ve son görülme
        timestamps = sorted([s["timestamp"] for s in snaps])
        if timestamps:
            result["first_seen"] = _format_snapshot(timestamps[0], domain)["date_formatted"]
            result["last_seen"] = _format_snapshot(timestamps[-1], domain)["date_formatted"]

    return result
