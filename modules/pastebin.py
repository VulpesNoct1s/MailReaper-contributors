"""
MailReaper - Paste Site Search Module
Pastebin ve diğer paste sitelerinde email arar (API'siz, web scrape)
"""

import requests
import re
import time
from urllib.parse import quote
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

def search_paste_sites(email: str) -> dict:
    """Birden fazla paste sitesinde email arar."""
    results = {
        "email": email,
        "findings": [],
        "search_urls": [],
        "total_found": 0,
        "error": None
    }

    # Google ile paste siteleri hedefle
    paste_dorks = [
        f'site:pastebin.com "{email}"',
        f'site:paste.ee "{email}"',
        f'site:pastecode.io "{email}"',
        f'site:ghostbin.co "{email}"',
        f'site:controlc.com "{email}"',
        f'site:paster.pl "{email}"',
    ]

    # Doğrudan arama linkleri kullanıcıya göster
    results["search_urls"] = [
        {"name": "Pastebin Google Dork", "url": f'https://www.google.com/search?q=site:pastebin.com+"{quote(email)}"'},
        {"name": "IntelX Paste Search", "url": f'https://intelx.io/?s={quote(email)}'},
        {"name": "Psbdmp Search", "url": f'https://psbdmp.ws/api/search/{quote(email)}'},
        {"name": "Paste.ee Search", "url": f'https://paste.ee/search?q={quote(email)}'},
        {"name": "Google All Paste Sites", "url": f'https://www.google.com/search?q="site:pastebin.com+OR+site:paste.ee+OR+site:hastebin.com"+"{quote(email)}"'},
    ]

    # psbdmp API (ücretsiz, giriş gerekmez)
    try:
        resp = requests.get(
            f"https://psbdmp.ws/api/v3/search/{quote(email)}",
            headers=HEADERS,
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict) and "data" in data:
                for item in data["data"][:10]:
                    results["findings"].append({
                        "source": "psbdmp.ws (Pastebin index)",
                        "id": item.get("id", ""),
                        "url": f"https://pastebin.com/{item.get('id', '')}",
                        "tags": item.get("tags", ""),
                        "time": item.get("time", ""),
                        "context": item.get("text", "")[:200] if item.get("text") else ""
                    })
    except Exception as e:
        results["error"] = f"psbdmp error: {str(e)}"

    # Paste.ee arama
    try:
        time.sleep(0.5)
        resp = requests.get(
            f"https://paste.ee/search?q={quote(email)}",
            headers=HEADERS,
            timeout=8
        )
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            # Paste.ee sonuçlarını parse et
            paste_links = soup.find_all("a", href=re.compile(r"/p/[a-zA-Z0-9]+"))
            for link in paste_links[:5]:
                url = "https://paste.ee" + link["href"] if link["href"].startswith("/") else link["href"]
                title = link.get_text(strip=True)
                results["findings"].append({
                    "source": "paste.ee",
                    "url": url,
                    "title": title,
                    "context": ""
                })
    except Exception:
        pass

    # HudsonRock ücretsiz endpoint (stealer log kontrolü)
    try:
        time.sleep(0.5)
        resp = requests.get(
            f"https://cavalier.hudsonrock.com/api/json/v2/osint-tools/search-by-email?email={quote(email)}",
            headers=HEADERS,
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("stealers"):
                for s in data["stealers"][:5]:
                    results["findings"].append({
                        "source": "HudsonRock (Stealer Logs)",
                        "computer_name": s.get("computer_name", ""),
                        "operating_system": s.get("operating_system", ""),
                        "malware_path": s.get("malware_path", ""),
                        "date_compromised": s.get("date_compromised", ""),
                        "antiviruses": s.get("antiviruses", []),
                        "credentials_count": len(s.get("credentials", [])),
                        "credentials": s.get("credentials", [])[:5],
                    })
    except Exception:
        pass

    results["total_found"] = len(results["findings"])
    return results
