"""
MailReaper - SMTP Probe Module
Probes SMTP servers associated with an email address to test reachability,
VRFY support, RCPT TO acceptance, catch-all detection, TLS support, and
server banners.
"""

import smtplib
import socket
import dns.resolver
import dns.exception


# Sender address used during RCPT TO probing
PROBE_SENDER = "probe@mailreaper.local"
# A clearly nonexistent address used for catch-all detection
CANARY_LOCAL = "zzz_no_such_user_xyz_canary_9183756"
SMTP_TIMEOUT = 10  # seconds


def _get_mx_hosts(domain: str) -> list:
    """
    Resolves MX records for the given domain, sorted by preference (lowest first).

    Returns:
        List of MX hostnames as strings.
    """
    try:
        answers = dns.resolver.resolve(domain, "MX", lifetime=10)
        records = sorted(answers, key=lambda r: r.preference)
        return [str(r.exchange).rstrip(".") for r in records]
    except (
        dns.resolver.NoAnswer,
        dns.resolver.NXDOMAIN,
        dns.resolver.NoNameservers,
        dns.exception.Timeout,
        dns.exception.DNSException,
    ):
        return []


def _try_vrfy(smtp: smtplib.SMTP, local_part: str) -> tuple:
    """
    Attempts the SMTP VRFY command.

    Returns:
        (supported: bool, result_str: str)
    """
    try:
        code, message = smtp.verify(local_part)
        msg = message.decode(errors="replace") if isinstance(message, bytes) else message
        if code in (250, 251, 252):
            return True, f"{code} {msg}"
        if code == 502:
            # 502 = Command not implemented
            return False, f"{code} {msg}"
        return True, f"{code} {msg}"
    except smtplib.SMTPException as exc:
        return False, str(exc)
    except Exception as exc:
        return False, str(exc)


def _try_rcpt(smtp: smtplib.SMTP, email: str, sender: str) -> tuple:
    """
    Attempts a MAIL FROM / RCPT TO sequence without actually sending mail.

    Returns:
        (accepted: bool, result_str: str)
    """
    try:
        smtp.mail(sender)
        code, message = smtp.rcpt(email)
        msg = message.decode(errors="replace") if isinstance(message, bytes) else message
        smtp.rset()
        return code in (250, 251), f"{code} {msg}"
    except smtplib.SMTPRecipientsRefused as exc:
        return False, str(exc)
    except smtplib.SMTPSenderRefused as exc:
        smtp.rset()
        return False, f"Sender refused: {exc}"
    except smtplib.SMTPException as exc:
        return False, str(exc)
    except Exception as exc:
        return False, str(exc)


def _detect_catch_all(smtp: smtplib.SMTP, domain: str) -> bool:
    """
    Probes a clearly nonexistent address to detect catch-all servers.

    A server is considered a catch-all if it accepts the canary address.

    Returns:
        True if the server appears to be a catch-all, False otherwise.
    """
    canary = f"{CANARY_LOCAL}@{domain}"
    try:
        smtp.mail(PROBE_SENDER)
        code, _ = smtp.rcpt(canary)
        smtp.rset()
        return code in (250, 251)
    except smtplib.SMTPRecipientsRefused:
        return False
    except smtplib.SMTPSenderRefused:
        return False
    except Exception:
        return False


def _probe_server(host: str, email: str, local_part: str, domain: str) -> dict:
    """
    Connects to a single SMTP server and performs all probes.

    Args:
        host:       MX hostname.
        email:      Full target email address.
        local_part: The local part of the target email (before @).
        domain:     The domain part of the target email (after @).

    Returns:
        Populated result dict on success, or partial dict with error set.
    """
    result = {
        "smtp_reachable": False,
        "server_used": host,
        "catch_all": False,
        "vrfy_supported": False,
        "vrfy_result": None,
        "rcpt_result": None,
        "banner": None,
        "supports_tls": False,
        "error": None,
    }

    try:
        smtp = smtplib.SMTP(host, 25, timeout=SMTP_TIMEOUT)
        result["smtp_reachable"] = True

        # Capture banner
        banner = smtp.getwelcome()
        result["banner"] = (
            banner.decode(errors="replace") if isinstance(banner, bytes) else str(banner)
        )

        # Check STARTTLS support
        try:
            smtp.ehlo_or_helo_if_needed()
            if smtp.has_extn("STARTTLS"):
                result["supports_tls"] = True
                smtp.starttls()
                smtp.ehlo()
        except Exception:
            pass  # TLS negotiation failure is non-fatal

        # VRFY probe
        vrfy_supported, vrfy_result = _try_vrfy(smtp, local_part)
        result["vrfy_supported"] = vrfy_supported
        result["vrfy_result"] = vrfy_result

        # RCPT TO probe
        _accepted, rcpt_result = _try_rcpt(smtp, email, PROBE_SENDER)
        result["rcpt_result"] = rcpt_result

        # Catch-all detection
        result["catch_all"] = _detect_catch_all(smtp, domain)

        try:
            smtp.quit()
        except Exception:
            pass

    except smtplib.SMTPConnectError as exc:
        result["error"] = f"SMTPConnectError: {exc}"
    except smtplib.SMTPException as exc:
        result["error"] = f"SMTPException: {exc}"
    except socket.timeout:
        result["error"] = f"Connection to {host}:25 timed out after {SMTP_TIMEOUT}s"
    except OSError as exc:
        result["error"] = f"OSError: {exc}"
    except Exception as exc:
        result["error"] = f"Unexpected error: {exc}"

    return result


def probe_smtp(email: str) -> dict:
    """
    Entry point. Probes the SMTP servers for the given email address.

    Tries each MX server in priority order and returns the result from the
    first server that was reachable, or the last error if none were reachable.

    Args:
        email: Full email address to probe, e.g. 'user@example.com'.

    Returns:
        {
            'smtp_reachable': bool,
            'server_used': str,
            'catch_all': bool,
            'vrfy_supported': bool,
            'vrfy_result': str or None,
            'rcpt_result': str or None,
            'banner': str or None,
            'supports_tls': bool,
            'error': str or None,
        }
    """
    default_result = {
        "smtp_reachable": False,
        "server_used": None,
        "catch_all": False,
        "vrfy_supported": False,
        "vrfy_result": None,
        "rcpt_result": None,
        "banner": None,
        "supports_tls": False,
        "error": "No MX records found or email could not be parsed",
    }

    # Parse email into parts
    if "@" not in email:
        default_result["error"] = f"Invalid email address (no '@'): {email}"
        return default_result

    local_part, domain = email.rsplit("@", 1)
    domain = domain.lower().strip()

    # Resolve MX records
    mx_hosts = _get_mx_hosts(domain)
    if not mx_hosts:
        default_result["error"] = f"No MX records found for domain: {domain}"
        return default_result

    last_result = default_result
    for host in mx_hosts:
        result = _probe_server(host, email, local_part, domain)
        last_result = result
        if result["smtp_reachable"]:
            return result  # Return on first successful connection

    return last_result  # All servers failed; return last attempt


# ---------------------------------------------------------------------------
# Quick CLI test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import json
    import sys

    targets = sys.argv[1:] if len(sys.argv) > 1 else ["user@gmail.com"]

    for addr in targets:
        print(f"\n{'='*60}")
        print(f"  Probing: {addr}")
        print(f"{'='*60}")
        print(json.dumps(probe_smtp(addr), indent=2, default=str))
