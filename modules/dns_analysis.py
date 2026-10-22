"""
MailReaper - DNS & WHOIS Analysis Module
Performs comprehensive DNS, WHOIS, and SSL certificate analysis for a domain.
"""

import ssl
import socket
import datetime
from typing import Any

import dns.resolver
import dns.exception
import whois


# DKIM selectors to probe
DKIM_SELECTORS = [
    "google", "default", "mail", "dkim", "selector1", "selector2",
    "k1", "k2", "smtp", "mailjet", "sendgrid", "amazonses",
    "mandrill", "mailgun",
]

DNS_TIMEOUT = 10  # seconds per query


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _resolve(domain: str, record_type: str) -> list:
    """Resolves a DNS record type for the domain, returning a list of string values."""
    try:
        answers = dns.resolver.resolve(domain, record_type, lifetime=DNS_TIMEOUT)
        return [str(r) for r in answers]
    except (
        dns.resolver.NoAnswer,
        dns.resolver.NXDOMAIN,
        dns.resolver.NoNameservers,
        dns.exception.Timeout,
        dns.exception.DNSException,
    ):
        return []
    except Exception:
        return []


def _resolve_mx(domain: str) -> list:
    """
    Resolves MX records for the domain.

    Returns:
        List of dicts: [{'exchange': str, 'preference': int}, ...]
    """
    try:
        answers = dns.resolver.resolve(domain, "MX", lifetime=DNS_TIMEOUT)
        records = sorted(answers, key=lambda r: r.preference)
        return [
            {"exchange": str(r.exchange).rstrip("."), "preference": r.preference}
            for r in records
        ]
    except Exception:
        return []


def _parse_spf(txt_records: list) -> dict:
    """
    Finds and parses the SPF record from a list of TXT record strings.

    Returns:
        {'exists': bool, 'record': str or None, 'policy': str or None}
    """
    result = {"exists": False, "record": None, "policy": None}
    for txt in txt_records:
        clean = txt.strip('"')
        if clean.startswith("v=spf1"):
            result["exists"] = True
            result["record"] = clean
            # Extract the 'all' qualifier as the policy indicator
            for part in clean.split():
                if part.lower() in ("+all", "-all", "~all", "?all"):
                    result["policy"] = part.lower()
                    break
                if part.lower() == "all":
                    result["policy"] = "all"
            break
    return result


def _query_dmarc(domain: str) -> dict:
    """
    Queries the _dmarc TXT record for the given domain.

    Returns:
        {'exists': bool, 'record': str or None, 'policy': str or None, 'rua': str or None}
    """
    result = {"exists": False, "record": None, "policy": None, "rua": None}
    dmarc_domain = f"_dmarc.{domain}"
    try:
        answers = dns.resolver.resolve(dmarc_domain, "TXT", lifetime=DNS_TIMEOUT)
        for rdata in answers:
            raw = "".join(part.decode() if isinstance(part, bytes) else part
                          for part in rdata.strings)
            if "v=DMARC1" in raw:
                result["exists"] = True
                result["record"] = raw
                # Parse tags
                for tag in raw.split(";"):
                    tag = tag.strip()
                    if tag.startswith("p="):
                        result["policy"] = tag[2:].strip()
                    elif tag.startswith("rua="):
                        result["rua"] = tag[4:].strip()
                break
    except Exception:
        pass
    return result


def _query_dkim_selectors(domain: str) -> list:
    """
    Probes common DKIM selectors for the domain.

    Returns:
        List of selector names for which a DKIM TXT record was found.
    """
    found = []
    for selector in DKIM_SELECTORS:
        dkim_domain = f"{selector}._domainkey.{domain}"
        try:
            answers = dns.resolver.resolve(dkim_domain, "TXT", lifetime=DNS_TIMEOUT)
            for rdata in answers:
                raw = "".join(
                    part.decode() if isinstance(part, bytes) else part
                    for part in rdata.strings
                )
                if "v=DKIM1" in raw or "p=" in raw:
                    found.append(selector)
                    break
        except Exception:
            pass
    return found


def _query_whois(domain: str) -> dict:
    """
    Fetches WHOIS information for the domain.

    Returns:
        Dict with registrar, dates, name_servers, org, country, etc.
    """
    result = {
        "registrar": None,
        "created": None,
        "expires": None,
        "updated": None,
        "name_servers": [],
        "org": None,
        "country": None,
        "registrant_name": None,
        "emails": [],
    }

    def _fmt_date(val: Any) -> str | None:
        if val is None:
            return None
        if isinstance(val, list):
            val = val[0]
        if isinstance(val, datetime.datetime):
            return val.isoformat()
        return str(val)

    def _as_list(val: Any) -> list:
        if val is None:
            return []
        if isinstance(val, list):
            return [str(v) for v in val]
        return [str(val)]

    try:
        w = whois.whois(domain)
        result["registrar"] = w.registrar
        result["created"] = _fmt_date(w.creation_date)
        result["expires"] = _fmt_date(w.expiration_date)
        result["updated"] = _fmt_date(w.updated_date)
        result["name_servers"] = [ns.lower() for ns in _as_list(w.name_servers)]
        result["org"] = w.org
        result["country"] = w.country
        result["registrant_name"] = w.name
        result["emails"] = _as_list(w.emails)
    except Exception:
        pass

    return result


def _query_ssl(domain: str, port: int = 443) -> dict:
    """
    Fetches and parses the SSL/TLS certificate for the given domain.

    Returns:
        Dict with issuer, subject, SAN, validity dates, and days remaining.
    """
    result = {
        "valid": False,
        "issuer": None,
        "subject": None,
        "san": [],
        "not_before": None,
        "not_after": None,
        "days_remaining": None,
        "expired": True,
    }

    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((domain, port), timeout=10) as sock:
            with ctx.wrap_socket(sock, server_hostname=domain) as ssock:
                cert = ssock.getpeercert()

        # Issuer
        issuer_dict = {k: v for tup in cert.get("issuer", []) for k, v in tup}
        result["issuer"] = issuer_dict.get("organizationName") or issuer_dict.get("commonName")

        # Subject / CN
        subject_dict = {k: v for tup in cert.get("subject", []) for k, v in tup}
        result["subject"] = subject_dict.get("commonName")

        # SAN
        san_list = []
        for san_type, san_value in cert.get("subjectAltName", []):
            if san_type == "DNS":
                san_list.append(san_value)
        result["san"] = san_list

        # Validity dates
        fmt = "%b %d %H:%M:%S %Y %Z"
        not_before_str = cert.get("notBefore")
        not_after_str = cert.get("notAfter")

        if not_before_str:
            result["not_before"] = not_before_str
        if not_after_str:
            result["not_after"] = not_after_str
            try:
                expiry = datetime.datetime.strptime(not_after_str, fmt)
                now = datetime.datetime.utcnow()
                remaining = (expiry - now).days
                result["days_remaining"] = remaining
                result["expired"] = remaining < 0
            except Exception:
                pass

        result["valid"] = True

    except ssl.SSLCertVerificationError as exc:
        result["valid"] = False
        result["issuer"] = f"SSL verification error: {exc}"
    except ssl.SSLError as exc:
        result["valid"] = False
        result["issuer"] = f"SSL error: {exc}"
    except (socket.timeout, socket.gaierror, OSError) as exc:
        result["valid"] = False
        result["issuer"] = f"Connection error: {exc}"
    except Exception as exc:
        result["valid"] = False
        result["issuer"] = f"Unexpected error: {exc}"

    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze_domain(domain: str) -> dict:
    """
    Entry point. Performs full DNS, WHOIS, and SSL analysis for the given domain.

    Args:
        domain: Domain name to analyse, e.g. 'example.com'.

    Returns:
        {
            'a_records': list[str],
            'aaaa_records': list[str],
            'mx_records': list[{'exchange': str, 'preference': int}],
            'ns_records': list[str],
            'txt_records': list[str],
            'spf': {'exists': bool, 'record': str, 'policy': str},
            'dmarc': {'exists': bool, 'record': str, 'policy': str, 'rua': str},
            'dkim_selectors_found': list[str],
            'whois': { ... },
            'ssl': { ... },
        }
    """
    domain = domain.strip().lower()

    txt_records = _resolve(domain, "TXT")

    return {
        "a_records":           _resolve(domain, "A"),
        "aaaa_records":        _resolve(domain, "AAAA"),
        "mx_records":          _resolve_mx(domain),
        "ns_records":          _resolve(domain, "NS"),
        "txt_records":         txt_records,
        "spf":                 _parse_spf(txt_records),
        "dmarc":               _query_dmarc(domain),
        "dkim_selectors_found": _query_dkim_selectors(domain),
        "whois":               _query_whois(domain),
        "ssl":                 _query_ssl(domain),
    }


# ---------------------------------------------------------------------------
# Quick CLI test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import json
    import sys

    targets = sys.argv[1:] if len(sys.argv) > 1 else ["example.com"]

    for dom in targets:
        print(f"\n{'='*60}")
        print(f"  Analysing domain: {dom}")
        print(f"{'='*60}")
        print(json.dumps(analyze_domain(dom), indent=2, default=str))
