import pytest

from conftest import SAMPLE_TEXT, T0
from isspass import tle


def test_parse_with_and_without_name():
    a = tle.parse(SAMPLE_TEXT)
    b = tle.parse("\n".join(SAMPLE_TEXT.strip().splitlines()[1:]))
    assert a.name == "ISS (ZARYA)" and a.line1 == b.line1
    assert a.epoch.strftime("%Y-%m-%d %H:%M") == "2014-01-20 22:23"
    assert 0.5 < a.age_days(T0) < 0.6


def broken(i, line):
    lines = SAMPLE_TEXT.strip().splitlines()
    lines[i] = line
    return "\n".join(lines)


@pytest.mark.parametrize("text, message", [
    ("hello", "exactly two TLE lines"),
    (broken(1, SAMPLE_TEXT.splitlines()[1][:60]), "69 characters"),
    (broken(1, SAMPLE_TEXT.splitlines()[1][:68] + "9"), "checksum"),
    (broken(2, "3" + SAMPLE_TEXT.splitlines()[2][1:]), "must start with '2 '"),
])
def test_bad_input_is_rejected(text, message):
    with pytest.raises(tle.TleError, match=message):
        tle.parse(text)


def test_other_satellite_is_rejected():
    hubble = ("1 20580U 90037B   14020.00000000  .00000000  00000-0  00000-0 0  9990\n"
              "2 20580  28.4700 100.0000 0003000  80.0000 280.0000 15.08000000000000")
    fixed = []
    for line in hubble.splitlines():
        fixed.append(line[:68] + str(tle.checksum(line)))
    with pytest.raises(tle.TleError, match="not the ISS"):
        tle.parse("\n".join(fixed))


def test_download_without_internet(monkeypatch):
    import urllib.error

    def offline(*a, **k):
        raise urllib.error.URLError("no network")
    monkeypatch.setattr(tle.urllib.request, "urlopen", offline)
    with pytest.raises(tle.TleError, match="No internet"):
        tle.download()


def test_backup_source_is_used_when_celestrak_fails(monkeypatch):
    import json
    import urllib.error
    lines = SAMPLE_TEXT.strip().splitlines()

    def fake_get(url, timeout):
        if "celestrak" in url:
            raise urllib.error.HTTPError(url, 403, "Forbidden", {}, None)
        return json.dumps({"name": lines[0], "line1": lines[1], "line2": lines[2]})
    monkeypatch.setattr(tle, "_get", fake_get)
    t = tle.download()
    assert t.source == "TLE API" and t.line1 == lines[1]


def test_certificate_problem_is_reported(monkeypatch):
    import ssl
    import urllib.error

    def bad_cert(url, timeout):
        raise urllib.error.URLError(ssl.SSLCertVerificationError("CERTIFICATE_VERIFY_FAILED"))
    monkeypatch.setattr(tle, "_get", bad_cert)
    with pytest.raises(tle.TleError, match="certificate"):
        tle.download()
