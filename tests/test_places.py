from isspass.places import PlaceIndex, normalize

P = PlaceIndex()


def test_normalize_turkish_and_german():
    assert normalize("İstanbul") == "istanbul"
    assert normalize("Keşan") == "kesan"
    assert normalize("München") == "munchen"


def test_search_finds_small_towns_without_special_letters():
    names = [p["name"] for p in P.search("kesan")]
    assert "Keşan" in names


def test_search_uses_english_names_and_ranks_big_cities_first():
    assert P.search("munich")[0]["name"] == "Munich"
    assert P.search("ist")[0]["name"] == "Istanbul"


def test_nearest():
    place, km = P.nearest(40.86, 26.64)
    assert place["name"] == "Keşan" and km < 3


def test_suggestions_start_from_short_input():
    assert P.search("is")[0]["name"] == "Istanbul"
    assert len(P.search("i")) == 8
