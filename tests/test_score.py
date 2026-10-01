from isspass import score


def test_not_visible_is_zero():
    assert score.chance(False, 80, 6, -15, 0, 0) == 0


def test_great_pass_in_clear_sky_is_ten():
    assert score.chance(True, 80, 6, -18, 0, 0) == 10


def test_low_short_pass_is_lower():
    assert score.chance(True, 12, 1, -7, 0, 0) < score.chance(True, 60, 5, -15, 0, 0)


def test_clouds_lower_the_chance():
    clear = score.chance(True, 60, 5, -15, 0, 0)
    some = score.chance(True, 60, 5, -15, 50, 2)
    cloudy = score.chance(True, 60, 5, -15, 100, 3)
    assert clear > some > cloudy
    assert cloudy <= 1


def test_rain_and_fog_hurt_more_than_clouds_alone():
    dry = score.chance(True, 60, 5, -15, 40, 2)
    rain = score.chance(True, 60, 5, -15, 40, 63)
    fog = score.chance(True, 60, 5, -15, 40, 45)
    assert rain < dry and fog < dry


def test_without_forecast_only_the_pass_counts():
    assert score.chance(True, 60, 5, -15, None, None) == score.chance(True, 60, 5, -15, 0, 0)


def test_always_between_zero_and_ten():
    for el in (10, 30, 90):
        for minutes in (0, 3, 10):
            for clouds in (0, 50, 100):
                assert 0 <= score.chance(True, el, minutes, -10, clouds, 61) <= 10
