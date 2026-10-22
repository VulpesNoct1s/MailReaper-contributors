"""
MailReaper - Gravatar Lookup Module
Email MD5 hash üzerinden Gravatar profili sorgular
"""

import hashlib
import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}


def lookup_gravatar(email: str) -> dict:
    """
    Gravatar profili sorgular.
    API key gerektirmez — public endpoint kullanır.
    """
    result = {
        "has_gravatar": False,
        "hash": "",
        "avatar_url": None,
        "profile_url": None,
        "display_name": None,
        "about_me": None,
        "location": None,
        "accounts": [],
        "urls": [],
    }

    email = email.strip().lower()
    email_hash = hashlib.md5(email.encode()).hexdigest()
    result["hash"] = email_hash

    avatar_url = f"https://www.gravatar.com/avatar/{email_hash}?d=404&s=200"
    profile_url = f"https://www.gravatar.com/{email_hash}.json"

    # Avatar kontrolü
    try:
        resp = requests.head(avatar_url, headers=HEADERS, timeout=8, allow_redirects=True)
        if resp.status_code == 200:
            result["has_gravatar"] = True
            result["avatar_url"] = f"https://www.gravatar.com/avatar/{email_hash}?s=200"
    except Exception:
        pass

    # Profil bilgisi
    try:
        resp = requests.get(profile_url, headers=HEADERS, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            result["has_gravatar"] = True
            entry = data.get("entry", [{}])[0] if data.get("entry") else {}

            result["display_name"] = entry.get("displayName") or entry.get("name", {}).get("formatted")
            result["about_me"] = entry.get("aboutMe")
            result["profile_url"] = entry.get("profileUrl", f"https://www.gravatar.com/{email_hash}")

            # Konum
            result["location"] = entry.get("currentLocation")

            # Bağlı hesaplar
            accounts = entry.get("accounts", [])
            result["accounts"] = [
                {
                    "shortname": a.get("shortname", ""),
                    "display": a.get("display", ""),
                    "url": a.get("url", ""),
                }
                for a in accounts
            ]

            # URL listesi
            urls = entry.get("urls", [])
            result["urls"] = [{"title": u.get("title", ""), "value": u.get("value", "")} for u in urls]

    except Exception:
        pass

    return result
