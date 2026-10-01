from datetime import timedelta

from pyorbital.astronomy import sun_zenith_angle
from pyorbital.orbital import Orbital

from conftest import MUNICH, T0
from isspass.predictor import PassPredictor, compass

P = PassPredictor()


def test_all_passes_match_independent_reference(sample):
    ours = P.passes(sample, MUNICH, T0, days=2, only_visible=False)
    orb = Orbital("ISS", line1=sample.line1, line2=sample.line2)
    ref = orb.get_next_passes(T0.replace(tzinfo=None), 48, MUNICH.longitude, MUNICH.latitude, 0.5, horizon=10)
    assert len(ours) == len(ref)
    for p, (rise, fall, _) in zip(ours, ref):
        assert abs((p.rise.replace(tzinfo=None) - rise).total_seconds()) < 10
        assert abs((p.set.replace(tzinfo=None) - fall).total_seconds()) < 10


def test_visible_passes_happen_in_a_dark_sky(sample):
    visible = P.passes(sample, MUNICH, T0, days=5, only_visible=True)
    assert visible, "expected some visible passes in five days"
    for p in visible:
        assert sun_zenith_angle(p.shown_start.replace(tzinfo=None), MUNICH.longitude, MUNICH.latitude) > 96
        assert p.duration_minutes() >= 0.5


def test_daylight_passes_are_filtered_out(sample):
    every = P.passes(sample, MUNICH, T0, days=5, only_visible=False)
    visible = P.passes(sample, MUNICH, T0, days=5, only_visible=True)
    daylight = [p for p in every
                if sun_zenith_angle((p.rise + (p.set - p.rise) / 2).replace(tzinfo=None),
                                    MUNICH.longitude, MUNICH.latitude) < 90]
    assert daylight, "expected daytime passes in five days"
    assert all(not p.visible for p in daylight)
    assert len(visible) < len(every)


def test_path_is_on_the_sky(sample):
    p = P.passes(sample, MUNICH, T0, days=5)[0]
    assert 2 <= len(p.path) <= 32
    assert all(0 <= az < 360 and 9.5 <= el <= 90 for az, el, _ in p.path)
    seconds = [t for _, _, t in p.path]
    assert seconds[0] == 0 and seconds == sorted(seconds)
    assert abs(seconds[-1] - p.duration_minutes() * 60) < 1


def test_compass():
    assert [compass(a) for a in (0, 45, 91, 180, 270, 349)] == ["N", "NE", "E", "S", "W", "N"]


def test_hidden_passes_say_why(sample):
    every = P.passes(sample, MUNICH, T0, days=5, only_visible=False)
    hidden = [p for p in every if not p.visible]
    assert all(p.reason in ("daylight", "Earth's shadow", "too short", "too low") for p in hidden)
    assert all(p.reason is None for p in every if p.visible)
    for p in hidden:
        sun = sun_zenith_angle((p.rise + (p.set - p.rise) / 2).replace(tzinfo=None), MUNICH.longitude, MUNICH.latitude)
        if sun < 85:
            assert p.reason == "daylight"
        if sun > 110:
            assert p.reason == "Earth's shadow"
    assert {"daylight", "Earth's shadow"} <= {p.reason for p in hidden}
