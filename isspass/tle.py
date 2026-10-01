import json
import ssl
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

from isspass.models import TleSet

ISS_CATALOG = 25544
CELESTRAK_URL = "https://celestrak.org/NORAD/elements/gp.php?CATNR={}&FORMAT=TLE"
BACKUP_URL = "https://tle.ivanstanojevic.me/api/tle/{}"
USER_AGENT = "ISS-Pass-Calendar/1.0 (student project)"


class TleError(ValueError):
    pass


def checksum(line):
    total = sum(int(c) if c.isdigit() else (1 if c == "-" else 0) for c in line[:68])
    return total % 10


def epoch_of(line1):
    yy = int(line1[18:20])
    day = float(line1[20:32])
    year = 2000 + yy if yy < 57 else 1900 + yy
    return datetime(year, 1, 1, tzinfo=timezone.utc) + timedelta(days=day - 1)


def parse(text, source="manual"):
    lines = [l.rstrip() for l in text.strip().splitlines() if l.strip()]
    if len(lines) == 2:
        name, line1, line2 = "ISS (ZARYA)", lines[0], lines[1]
    elif len(lines) == 3:
        name, line1, line2 = lines[0].strip(), lines[1], lines[2]
    else:
        raise TleError("Paste exactly two TLE lines, with or without a name line above them.")

    for n, line in ((1, line1), (2, line2)):
        if len(line) != 69:
            raise TleError(f"Line {n} must be 69 characters long, it has {len(line)}.")
        if not line.startswith(f"{n} "):
            raise TleError(f"Line {n} must start with '{n} '.")
        if not line[68].isdigit() or checksum(line) != int(line[68]):
            raise TleError(f"Line {n} has a wrong checksum. The data may be damaged.")
    if line1[2:7] != line2[2:7]:
        raise TleError("The two lines belong to different satellites.")
    if int(line1[2:7]) != ISS_CATALOG:
        raise TleError(f"This is satellite {int(line1[2:7])}, not the ISS ({ISS_CATALOG}).")
    try:
        epoch = epoch_of(line1)
    except ValueError:
        raise TleError("The date in line 1 cannot be read.")
    return TleSet(name, line1, line2, epoch, source)


def _ssl_context():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def _get(url, timeout):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as r:
        return r.read().decode("utf-8")


def _reason(exc):
    if isinstance(exc, urllib.error.HTTPError):
        return f"server answered {exc.code}"
    inner = getattr(exc, "reason", exc)
    if isinstance(inner, ssl.SSLCertVerificationError) or "CERTIFICATE" in str(inner).upper():
        return "certificate error on this computer"
    if isinstance(inner, TimeoutError) or "timed out" in str(inner):
        return "timeout"
    return "no connection"


def download(timeout=12):
    reasons = []
    try:
        return parse(_get(CELESTRAK_URL.format(ISS_CATALOG), timeout), source="CelesTrak")
    except (urllib.error.URLError, OSError) as exc:
        reasons.append(f"CelesTrak: {_reason(exc)}")
    except TleError:
        reasons.append("CelesTrak: unexpected answer")
    try:
        body = json.loads(_get(BACKUP_URL.format(ISS_CATALOG), timeout))
        return parse(f"{body['name']}\n{body['line1']}\n{body['line2']}", source="TLE API")
    except (urllib.error.URLError, OSError) as exc:
        reasons.append(f"backup: {_reason(exc)}")
    except (TleError, ValueError, KeyError):
        reasons.append("backup: unexpected answer")

    if all("no connection" in r or "timeout" in r for r in reasons):
        raise TleError("No internet connection. Saved data still works offline.")
    raise TleError("Download failed (" + "; ".join(reasons) + ").")
