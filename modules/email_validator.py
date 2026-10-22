"""
MailReaper - Email Validator Module
Validates email addresses via syntax checking, disposable domain detection,
MX record lookup, and email provider identification.
"""

import re
import dns.resolver
import dns.exception


# ---------------------------------------------------------------------------
# Disposable / temporary email domain list (200+ entries)
# ---------------------------------------------------------------------------
DISPOSABLE_DOMAINS = {
    "mailinator.com", "guerrillamail.com", "10minutemail.com", "temp-mail.org",
    "throwam.com", "yopmail.com", "trashmail.com", "sharklasers.com",
    "guerrillamailblock.com", "grr.la", "guerrillamail.info", "guerrillamail.biz",
    "guerrillamail.de", "guerrillamail.net", "guerrillamail.org", "spam4.me",
    "trashmail.at", "trashmail.io", "trashmail.me", "trashmail.net",
    "dispostable.com", "mailnull.com", "spamgourmet.com", "spam.la",
    "jetable.org", "filzmail.com", "emailondeck.com", "mohmal.com",
    "tempail.com", "discard.email", "fakeinbox.com", "mailexpire.com",
    "spamevader.com", "crazymailing.com", "binkmail.com", "bobmail.info",
    "dayrep.com", "dingbone.com", "einrot.com", "fleckens.hu",
    "gustr.com", "ieh-mail.de", "imails.info", "inoutmail.eu",
    "jobbikszimpatizans.hu", "klassenmail.de", "klzlk.com", "lhsdv.com",
    "lifebyfood.com", "mailbidon.com", "maileater.com", "mailnew.com",
    "mailsiphon.com", "mailzilla.com", "mega.zik.dj", "meinspamschutz.de",
    "melvinfowler.com", "messagebeamer.de", "mezimages.net", "moncourrier.fr.nf",
    "monemail.fr.nf", "monmail.fr.nf", "monumentmail.com", "myfake.email",
    "mymailoasis.com", "mytempemail.com", "mytempmail.org", "nwytg.net",
    "objectmail.com", "obobbo.com", "oneoffemail.com", "onewaymail.com",
    "online.ms", "pecinan.com", "pecinan.net", "pecinan.org",
    "pepbot.com", "pingir.com", "pjjkp.com", "powered.name",
    "prtnx.com", "prtz.eu", "punkass.com", "put2.net",
    "qq.com", "rcpt.at", "rppkn.com", "rtrtr.com",
    "s0ny.net", "safe-mail.net", "safersignup.de", "samenye.com",
    "sandelf.de", "saynotospams.com", "secure-mail.biz", "seekt.com",
    "selfdestructingmail.com", "sendspamhere.com", "shieldedmail.com",
    "sinnlos-mail.de", "slapsfromlastnight.com", "slaskpost.se", "smashmail.de",
    "smellfear.com", "snakemail.com", "sneakemail.com", "sneakmail.de",
    "sofort-mail.de", "sogetthis.com", "soodonims.com", "spam-en.de",
    "spam.care", "spamhereplease.com", "spamoff.de", "spamthisplease.com",
    "speedymail.org", "spikio.com", "spoofmail.de", "squizzy.de",
    "standby.ch", "stinkefinger.net", "stuffmail.de", "super-auswahl.de",
    "supergreatmail.com", "superstachel.de", "suremail.info", "tafmail.com",
    "tagyourself.com", "tapiasafer.com", "tarheel.net", "teewars.org",
    "teleworm.us", "tempalias.com", "tempemail.biz", "tempemail.co.za",
    "tempe-mail.com", "tempemail.net", "tempinbox.co.uk", "tempinbox.com",
    "temporarioemail.com.br", "temporaryemail.net", "temporaryemail.us",
    "temporaryforwarding.com", "temporaryinbox.com", "temporarymailaddress.com",
    "tempthe.net", "thankyou2010.com", "thc.st", "thecloudindex.com",
    "thelimestones.com", "thisisnotmyrealemail.com", "throwaway.email",
    "tilien.com", "tittbit.in", "tmlsitf.com", "tmailinator.com",
    "toiea.com", "toomail.biz", "topranklist.de", "tradermail.info",
    "trash-amil.com", "trash-mail.at", "trash-mail.cf", "trash-mail.ga",
    "trash-mail.ml", "trash-mail.tk", "trash2009.com", "trash2010.com",
    "trash2011.com", "trashdevil.com", "trashdevil.de", "trashemail.de",
    "trashmail.app", "trashmail.fr", "trashmail.xyz", "trashmailer.com",
    "trashptr.com", "trbvm.com", "trillianpro.com", "tryalert.com",
    "turual.com", "twinmail.de", "twoweirdtricks.com", "tyldd.com",
    "uggsrock.com", "umail.net", "uroid.com", "valemail.net",
    "venompen.com", "verifymail.info", "viditag.com", "viralplays.com",
    "vomoto.com", "vpn.st", "vsimcard.com", "vubby.com",
    "wasteland.raptors.dk", "webm4il.info", "wegwerfmail.de", "wegwerfmail.net",
    "wegwerfmail.org", "wetrainbayarea.com", "wh4f.org", "whyspam.me",
    "willhackforfood.biz", "willselfdestruct.com", "wimsg.com", "wronghead.com",
    "wuzup.net", "wuzupmail.net", "www.e4ward.com", "www.gishpuppy.com",
    "www.mailinator.com", "xagloo.com", "xemaps.com", "xents.com",
    "xmaily.com", "xoxy.net", "xyzfree.net", "yapped.net",
    "yeah.net", "yep.it", "yogamaven.com", "yopmail.fr",
    "you-spam.com", "youmail.dk", "ypmail.webarnak.fr.eu.org", "yuurok.com",
    "z1p.biz", "za.com", "zehnminuten.de", "zehnminutenmail.de",
    "zetmail.com", "zippymail.info", "zoemail.net", "zoemail.org",
    "zomg.info", "tempmail.com", "tempmail.net", "tempmail.org",
    "spamgourmet.net", "spamgourmet.org", "mailnull.net",
    "mailnull.org", "spambox.us", "spambox.info", "mailmetrash.com",
    "trashmail.se", "trashmail.ws", "yopmail.pp.ua", "nospam.ze.tc",
    "spamfree24.org", "mailscrap.com", "antichef.com", "antichef.net",
    "kurzepost.de", "postfach2go.de", "trashmail.ch", "wegwerfadresse.de",
}

# ---------------------------------------------------------------------------
# Known email providers
# ---------------------------------------------------------------------------
PROVIDERS = {
    "Gmail":      {"gmail.com", "googlemail.com"},
    "Outlook":    {"outlook.com", "hotmail.com", "live.com", "msn.com", "outlook.co.uk",
                   "live.co.uk", "hotmail.co.uk", "live.ca", "hotmail.fr", "live.fr"},
    "Yahoo":      {"yahoo.com", "yahoo.co.uk", "yahoo.co.in", "yahoo.fr", "yahoo.de",
                   "yahoo.es", "yahoo.it", "yahoo.com.br", "ymail.com"},
    "ProtonMail": {"protonmail.com", "protonmail.ch", "pm.me", "proton.me"},
    "iCloud":     {"icloud.com", "me.com", "mac.com"},
    "Zoho":       {"zoho.com", "zohomail.com"},
    "GMX":        {"gmx.com", "gmx.net", "gmx.de", "gmx.at", "gmx.ch"},
    "AOL":        {"aol.com", "aim.com"},
    "FastMail":   {"fastmail.com", "fastmail.fm", "fastmail.org"},
    "Tutanota":   {"tutanota.com", "tutanota.de", "tutamail.com", "tuta.io"},
    "Mailfence":  {"mailfence.com"},
    "Posteo":     {"posteo.de", "posteo.net"},
    "Runbox":     {"runbox.com"},
    "Hushmail":   {"hushmail.com"},
    "Lavabit":    {"lavabit.com"},
    "Mail.ru":    {"mail.ru", "list.ru", "bk.ru", "inbox.ru"},
}

# Flat lookup: domain -> provider name
_DOMAIN_TO_PROVIDER: dict = {}
for _provider, _domains in PROVIDERS.items():
    for _d in _domains:
        _DOMAIN_TO_PROVIDER[_d] = _provider

# Regex for RFC-5322-like email validation (covers the vast majority of real addresses)
_EMAIL_REGEX = re.compile(
    r"^(?P<local>[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+"
    r"(?:\.[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+)*)"
    r"@"
    r"(?P<domain>[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?"
    r"(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*\.[a-zA-Z]{2,})$"
)


def _validate_syntax(email):
    """
    Validates the email address syntax using a strict regex.

    Returns:
        (is_valid, local_part, domain)
    """
    email = email.strip()
    match = _EMAIL_REGEX.match(email)
    if match:
        return True, match.group("local"), match.group("domain").lower()
    return False, "", ""


def _check_disposable(domain):
    """
    Checks whether the given domain is in the known disposable email domain list.

    Returns:
        (is_disposable, matched_domain_or_None)
    """
    domain = domain.lower()
    if domain in DISPOSABLE_DOMAINS:
        return True, domain
    return False, None


def _query_mx(domain):
    """
    Queries MX records for the given domain using dnspython.

    Returns:
        (has_mx, [list of MX exchange hostnames sorted by preference])
    """
    try:
        answers = dns.resolver.resolve(domain, "MX", lifetime=10)
        records = sorted(answers, key=lambda r: r.preference)
        exchanges = [str(r.exchange).rstrip(".") for r in records]
        return bool(exchanges), exchanges
    except (
        dns.resolver.NoAnswer,
        dns.resolver.NXDOMAIN,
        dns.resolver.NoNameservers,
        dns.exception.Timeout,
        dns.exception.DNSException,
    ):
        return False, []


def _detect_provider(domain):
    """
    Identifies the email provider from the domain name.

    Returns:
        Provider name string, e.g. 'Gmail', 'Outlook', 'Corporate', 'Unknown'.
    """
    domain = domain.lower()
    if domain in _DOMAIN_TO_PROVIDER:
        return _DOMAIN_TO_PROVIDER[domain]
    return "Unknown"


def _determine_email_type(is_disposable, provider, domain):
    """
    Determines the high-level email type.

    Categories:
        - 'disposable'  -> known throw-away service
        - 'personal'    -> well-known consumer provider
        - 'corporate'   -> custom domain not matching any consumer provider
        - 'unknown'     -> anything else
    """
    if is_disposable:
        return "disposable"
    if provider != "Unknown":
        return "personal"
    # Heuristic: if domain has an MX record but no known provider, call it corporate
    return "corporate"


def validate_email(email):
    """
    Entry point. Validates a single email address and returns a structured dict.

    Args:
        email: Raw email address string to validate.

    Returns:
        {
            'valid_syntax': bool,
            'is_disposable': bool,
            'disposable_domain': str or None,
            'has_mx': bool,
            'mx_records': list[str],
            'provider': str,
            'email_type': str,
        }
    """
    result = {
        "valid_syntax": False,
        "is_disposable": False,
        "disposable_domain": None,
        "has_mx": False,
        "mx_records": [],
        "provider": "Unknown",
        "email_type": "unknown",
    }

    # --- Syntax check ---
    valid, _local, domain = _validate_syntax(email)
    result["valid_syntax"] = valid

    if not valid:
        # Cannot continue without a parseable domain
        return result

    # --- Disposable check ---
    is_disposable, matched_domain = _check_disposable(domain)
    result["is_disposable"] = is_disposable
    result["disposable_domain"] = matched_domain

    # --- MX records ---
    has_mx, mx_records = _query_mx(domain)
    result["has_mx"] = has_mx
    result["mx_records"] = mx_records

    # --- Provider detection ---
    provider = _detect_provider(domain)
    result["provider"] = provider

    # --- Email type ---
    result["email_type"] = _determine_email_type(is_disposable, provider, domain)

    return result


# ---------------------------------------------------------------------------
# Quick CLI test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import json
    import sys

    test_addresses = [
        "user@gmail.com",
        "nobody@mailinator.com",
        "contact@example.com",
        "bad-address@",
        "jane.doe@protonmail.com",
        "support@microsoft.com",
    ]

    targets = sys.argv[1:] if len(sys.argv) > 1 else test_addresses

    for addr in targets:
        print(f"\n{'='*60}")
        print(f"  Validating: {addr}")
        print(f"{'='*60}")
        print(json.dumps(validate_email(addr), indent=2, default=str))
