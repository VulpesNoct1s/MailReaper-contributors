"""
MailReaper - IP Intel
Domain -> IP çözümleme, reverse DNS ve ASN/ağ bilgisi.
Sadece DNS kullanır (Team Cymru DNS servisi) — API anahtarı gerekmez.
"""

import socket
import dns.resolver
import dns.reversename

_res = dns.resolver.Resolver()
_res.lifetime = 5
_res.timeout = 3

CDN_ORGS = ("cloudflare", "akamai", "fastly", "amazon", "google", "microsoft", "incapsula", "sucuri")


def _txt(name: str):
    try:
        return [r.to_text().strip('"') for r in _res.resolve(name, "TXT")]
    except Exception:
        return []


def _asn_v4(ip: str) -> dict:
    rev = ".".join(reversed(ip.split(".")))
    rows = _txt(f"{rev}.origin.asn.cymru.com")
    if not rows:
        return {}
    asn, prefix, cc, registry, allocated = [x.strip() for x in (rows[0].split("|") + [""] * 5)[:5]]
    asn = asn.split()[0] if asn else ""
    info = _txt(f"AS{asn}.asn.cymru.com") if asn else []
    name = info[0].split("|")[-1].strip() if info else ""
    return {"asn": f"AS{asn}", "prefix": prefix, "country": cc, "registry": registry,
            "allocated": allocated, "org": name}


def _ptr(ip: str):
    try:
        ans = _res.resolve(dns.reversename.from_address(ip), "PTR")
        return str(ans[0]).rstrip(".")
    except Exception:
        return None


def ip_intel(domain: str) -> dict:
    out = {"domain": domain, "ips": [], "ipv6": []}
    try:
        out["ipv6"] = [r.address for r in _res.resolve(domain, "AAAA")][:4]
    except Exception:
        pass
    try:
        v4 = [r.address for r in _res.resolve(domain, "A")][:6]
    except Exception as e:
        out["error"] = f"A kaydı çözülemedi: {e.__class__.__name__}"
        return out
    for ip in v4:
        entry = {"ip": ip, "ptr": _ptr(ip)}
        entry.update(_asn_v4(ip))
        out["ips"].append(entry)
    out["behind_cdn"] = any(any(c in (e.get("org") or "").lower() for c in CDN_ORGS) for e in out["ips"])
    out["links"] = ([{"label": f"Shodan {e['ip']}", "url": f"https://www.shodan.io/host/{e['ip']}"} for e in out["ips"][:3]]
                    + [{"label": f"Censys {e['ip']}", "url": f"https://search.censys.io/hosts/{e['ip']}"} for e in out["ips"][:3]])
    return out
