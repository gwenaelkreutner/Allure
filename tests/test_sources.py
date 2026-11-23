import pytest

from allure_cycling import RouteSourceError, load_url


def test_strava_route_explains_how_to_export():
    with pytest.raises(RouteSourceError, match="Export GPX"):
        load_url("https://www.strava.com/routes/123")


def test_komoot_link_without_tour_id_is_rejected():
    with pytest.raises(RouteSourceError, match="tour"):
        load_url("https://www.komoot.com/discover")
