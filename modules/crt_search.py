"""
MailReaper - Certificate Transparency Search (crt.sh)
Email, domain veya isim üzerinden SSL sertifikası geçmişi arar.
Tamamen ücretsiz, API key gerektirmez.
"""

import requests
import json
from datetime import datetime

BASE = "https://crt.sh"
HEADERS = {"User-Agent": "Mozilla/5.0 MailReaper OSINT Tool"}


def _query(q: str):
    """crt.sh sık sık 502/timeout verir: 3 deneme, üstel bekleme. (json, hata) döner."""
    import time
    last = None
    for attempt in range(3):
        try:
            resp = requests.get(BASE, params={"q": q, "output": "json"}, headers=HEADERS, timeout=25)
            if resp.status_code == 200:
                return resp.json(), None
            last = f"HTTP {resp.status_code}"
        except Exception as e:
            last = str(e)
        time.sleep(1.5 * (attempt + 1))
    return None, last


def _parse_entries(data: list) -> list:
    """Ham crt.sh JSON'ını sadeleştirir."""
    seen = set()
    results = []
    for entry in data:
        cn = entry.get("common_name", "")
        name_value = entry.get("name_value", "")
        issuer = entry.get("issuer_name", "")
        not_before = entry.get("not_before", "")
        not_after = entry.get("not_after", "")
        logged = entry.get("entry_timestamp", "")

        # name_value içindeki tüm alan adlarını çıkar
        names = set()
        for line in (name_value + "\n" + cn).split("\n"):
            line = line.strip()
            if line and line not in ("", "*"):
                names.add(line)

        for name in names:
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            results.append({
                "name": name,
                "common_name": cn,
                "issuer": issuer,
                "not_before": not_before,
                "not_after": not_after,
                "logged": logged,
            })

    return sorted(results, key=lambda x: x.get("logged", ""), reverse=True)


def search_by_email(email: str) -> dict:
    """Email adresine göre sertifika kaydı arar."""
    result = {"query": email, "type": "email", "entries": [], "error": None}
    try:
        data, err = _query(f"{email}")
        result["error"] = err
        if data is not None:
            result["entries"] = _parse_entries(data)
            result["total"] = len(result["entries"])
    except Exception as e:
        result["error"] = str(e)
    return result


def search_by_domain(domain: str) -> dict:
    """Domain'e göre tüm subdomainleri ve sertifikaları bulur."""
    result = {"query": domain, "type": "domain", "entries": [], "subdomains": [], "error": None}
    try:
        data, err = _query(f"%.{domain}")
        result["error"] = err
        if data is not None:
            entries = _parse_entries(data)
            result["entries"] = entries[:50]
            result["total"] = len(entries)

            # Unique subdomain listesi
            subdomains = set()
            for e in entries:
                name = e.get("name", "")
                if name.endswith(f".{domain}") or name == domain:
                    subdomains.add(name.lower().lstrip("*."))
            result["subdomains"] = sorted(list(subdomains))
    except Exception as e:
        result["error"] = str(e)
    return result


def search_by_name(name: str) -> dict:
    """İsme (organization/CN) göre sertifika arar."""
    result = {"query": name, "type": "name", "entries": [], "error": None}
    try:
        data, err = _query(f"{name}")
        result["error"] = err
        if data is not None:
            result["entries"] = _parse_entries(data)[:30]
            result["total"] = len(result["entries"])
    except Exception as e:
        result["error"] = str(e)
    return result


def full_search(email: str = None, domain: str = None, name: str = None) -> dict:
    """
    Tek seferinde email + domain + name araması yapar.
    En az biri verilmeli.
    """
    output = {
        "email_results": None,
        "domain_results": None,
        "name_results": None,
        "all_domains": [],
        "all_subdomains": [],
    }

    if email:
        output["email_results"] = search_by_email(email)
        # Email sonuçlarından domain topla
        for e in output["email_results"].get("entries", []):
            n = e.get("name", "")
            if n and not n.startswith("*"):
                output["all_domains"].append(n)

    if domain:
        output["domain_results"] = search_by_domain(domain)
        output["all_subdomains"] = output["domain_results"].get("subdomains", [])

    if name:
        output["name_results"] = search_by_name(name)

    # Benzersiz domain listesi
    output["all_domains"] = sorted(list(set(output["all_domains"])))

    return output
