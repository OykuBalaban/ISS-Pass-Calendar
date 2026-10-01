from datetime import timedelta

import pytest

from conftest import MUNICH, T0
from isspass import tle
from isspass.models import Location
from isspass.predictor import PassPredictor
from isspass.service import PassService

P = PassPredictor()


def test_search_is_not_a_favorite_until_asked(repo):
    a = repo.use_location(Location("Edirne", 41.68, 26.56, "Europe/Istanbul"))
    assert repo.default_location().id == a
    assert repo.favorites() == []
    repo.set_favorite(a, True)
    assert [f.name for f in repo.favorites()] == ["Edirne"]


def test_same_place_is_stored_once(repo):
    a = repo.use_location(Location("Munich", 48.14, 11.58, "Europe/Berlin"))
    b = repo.use_location(Location("Near Munich", 48.15, 11.60, "Europe/Berlin"))
    assert a == b and len(repo.locations()) == 1


def test_recent_keeps_last_five_and_keeps_favorites(repo):
    import time
    fav = repo.use_location(Location("Fav", 0.0, 0.0, "UTC"))
    repo.set_favorite(fav, True)
    for i in range(1, 8):
        time.sleep(0.002)
        repo.use_location(Location(f"P{i}", float(i), float(i), "UTC"))
    names = [l.name for l in repo.recent()]
    assert names == ["P7", "P6", "P5", "P4", "P3"]
    assert "Fav" in [l.name for l in repo.locations()]
    assert len(repo.locations()) == 6


def test_data_states(repo, sample):
    svc = PassService(repo, P, auto_update=False)
    assert svc.data_status(T0)["state"] == "none"
    repo.save_tle(sample, T0)
    assert svc.data_status(T0)["state"] == "fresh"
    assert svc.data_status(T0 + timedelta(days=10))["state"] == "old"
    assert svc.data_status(T0 + timedelta(days=20))["state"] == "expired"


def test_expired_data_shows_no_passes(repo, sample):
    repo.save_tle(sample, T0)
    svc = PassService(repo, P, auto_update=False)
    status, passes = svc.upcoming(MUNICH, T0 + timedelta(days=20))
    assert status["state"] == "expired" and passes == []


def test_auto_update_downloads_when_data_is_missing(repo, sample):
    svc = PassService(repo, P, downloader=lambda: sample)
    result = svc.ensure_data(T0)
    assert result["ok"] and repo.latest_tle() is not None
    assert svc.ensure_data(T0) is None


def test_auto_update_offline_keeps_old_data_and_waits(repo, sample):
    repo.save_tle(sample, T0)
    calls = []

    def offline():
        calls.append(1)
        raise tle.TleError("No internet connection.")
    svc = PassService(repo, P, downloader=offline)
    later = T0 + timedelta(days=3)
    assert svc.ensure_data(later)["ok"] is False
    assert svc.ensure_data(later) is None
    assert len(calls) == 1
    assert svc.data_status(later)["state"] == "fresh"


def test_newest_epoch_wins(repo, sample):
    repo.save_tle(sample, T0)
    older = type(sample)(sample.name, sample.line1, sample.line2, sample.epoch - timedelta(days=3), "manual")
    repo.save_tle(older, T0)
    assert repo.latest_tle().epoch == sample.epoch


def test_pass_in_progress_is_still_listed(repo, sample):
    repo.save_tle(sample, T0)
    svc = PassService(repo, P, auto_update=False)
    _, passes = svc.upcoming(MUNICH, T0)
    p = passes[0]
    halfway = p.shown_start + (p.shown_end - p.shown_start) / 2
    _, during = PassService(repo, P, auto_update=False).upcoming(MUNICH, halfway)
    assert abs((during[0].shown_start - p.shown_start).total_seconds()) < 2


def test_data_is_refreshed_after_12_hours(repo, sample):
    repo.save_tle(sample, T0)
    calls = []

    def fake():
        calls.append(1)
        return sample
    svc = PassService(repo, P, downloader=fake)
    assert svc.ensure_data(sample.epoch + timedelta(hours=6)) is None
    assert svc.ensure_data(sample.epoch + timedelta(hours=13))["ok"]
    assert len(calls) == 1


def test_background_updater_downloads_without_a_page_visit(repo, sample):
    import time
    svc = PassService(repo, P, downloader=lambda: sample)
    svc.start_background_updates(lambda: T0)
    for _ in range(50):
        if repo.latest_tle():
            break
        time.sleep(0.05)
    assert repo.latest_tle() is not None
    assert repo.latest_tle().saved_at is not None
