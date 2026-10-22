"""
MailReaper - Email OSINT Tool
Tüm modüller için ortak yardımcı fonksiyonlar
"""

import time
import hashlib
import re

def get_email_parts(email: str) -> dict:
    """Email adresini parçalara ayırır."""
    email = email.strip().lower()
    if "@" not in email:
        return {}
    local, domain = email.rsplit("@", 1)
    return {
        "email": email,
        "local": local,
        "domain": domain,
        "tld": domain.split(".")[-1] if "." in domain else "",
        "subdomain": ".".join(domain.split(".")[:-2]) if domain.count(".") > 1 else "",
        "root_domain": ".".join(domain.split(".")[-2:]) if "." in domain else domain,
        "md5": hashlib.md5(email.encode()).hexdigest(),
        "sha1": hashlib.sha1(email.encode()).hexdigest(),
        "sha256": hashlib.sha256(email.encode()).hexdigest(),
    }

def is_valid_email(email: str) -> bool:
    pattern = r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email.strip()))

def safe_request(url: str, headers: dict = None, timeout: int = 8) -> tuple:
    """Güvenli HTTP isteği yapar, hata yönetimi ile."""
    import requests
    default_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }
    if headers:
        default_headers.update(headers)
    try:
        resp = requests.get(url, headers=default_headers, timeout=timeout, allow_redirects=True)
        return resp, None
    except Exception as e:
        return None, str(e)
