"""Tests for Orin online tools, weather retrieval, and privacy-preserving web search."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from orin.cli.main import app
from orin.core.router import get_intent_classifier, get_intent_dispatcher
from orin.core.router.intents import IntentType
from orin.net.search import search_web
from orin.net.weather import get_weather

runner = CliRunner()


def test_weather_success_mocked() -> None:
    """Test get_weather returns structured data and spoken summary on successful API response."""
    geo_mock = MagicMock()
    geo_mock.status_code = 200
    geo_mock.json.return_value = {
        "results": [
            {"name": "Paris", "latitude": 48.85, "longitude": 2.35, "country": "France"}
        ]
    }

    forecast_mock = MagicMock()
    forecast_mock.status_code = 200
    forecast_mock.json.return_value = {
        "current": {
            "temperature_2m": 18.2,
            "relative_humidity_2m": 62,
            "weather_code": 2,
            "wind_speed_10m": 11.5,
        }
    }

    def client_get(url, *args, **kwargs):
        if "geocoding-api" in url:
            return geo_mock
        return forecast_mock

    with patch("httpx.Client") as mock_client:
        mock_instance = MagicMock()
        mock_instance.get.side_effect = client_get
        mock_client.return_value.__enter__.return_value = mock_instance

        res = get_weather(location="Paris")
        assert res["success"] is True
        assert "Paris" in res["location"]
        assert res["temperature_c"] == 18.2
        assert res["condition"] == "partly cloudy"
        assert "18 degrees Celsius" in res["spoken"]


def test_weather_network_error() -> None:
    """Test get_weather handles network unavailability gracefully."""
    import httpx

    with patch("httpx.Client") as mock_client:
        mock_instance = MagicMock()
        mock_instance.get.side_effect = httpx.RequestError("No internet connection")
        mock_client.return_value.__enter__.return_value = mock_instance

        res = get_weather(location="Tokyo")
        assert res["success"] is False
        assert "unreachable" in res["spoken"].lower() or "error" in res["spoken"].lower()


def test_search_web_duckduckgo_mocked() -> None:
    """Test search_web retrieves abstract from DuckDuckGo."""
    ddg_mock = MagicMock()
    ddg_mock.status_code = 200
    ddg_mock.json.return_value = {
        "Heading": "Python",
        "AbstractText": "Python is a high-level programming language.",
    }

    with patch("httpx.Client") as mock_client:
        mock_instance = MagicMock()
        mock_instance.get.return_value = ddg_mock
        mock_client.return_value.__enter__.return_value = mock_instance

        res = search_web(query="Python language")
        assert res["success"] is True
        assert res["source"] == "DuckDuckGo"
        assert "programming language" in res["spoken"]


def test_search_web_wikipedia_fallback_mocked() -> None:
    """Test search_web falls back to Wikipedia when DuckDuckGo returns no abstract."""
    ddg_mock = MagicMock()
    ddg_mock.status_code = 200
    ddg_mock.json.return_value = {"AbstractText": "", "Answer": ""}

    wiki_mock = MagicMock()
    wiki_mock.status_code = 200
    wiki_mock.json.return_value = {
        "title": "Ada Lovelace",
        "extract": "Augusta Ada King, Countess of Lovelace was an English mathematician. She wrote the first algorithm.",
    }

    def client_get(url, *args, **kwargs):
        if "duckduckgo" in url:
            return ddg_mock
        return wiki_mock

    with patch("httpx.Client") as mock_client:
        mock_instance = MagicMock()
        mock_instance.get.side_effect = client_get
        mock_client.return_value.__enter__.return_value = mock_instance

        res = search_web(query="Ada Lovelace")
        assert res["success"] is True
        assert res["source"] == "Wikipedia"
        assert "mathematician" in res["spoken"]


def test_router_weather_classification() -> None:
    """Test IntentClassifier correctly routes weather queries."""
    classifier = get_intent_classifier()

    p1 = classifier.classify("what is the weather in London")
    assert p1.intent_type == IntentType.WEATHER
    assert p1.parameters.get("location") == "london"

    p2 = classifier.classify("what's the weather")
    assert p2.intent_type == IntentType.WEATHER

    p3 = classifier.classify("check weather forecast in Berlin")
    assert p3.intent_type == IntentType.WEATHER
    assert p3.parameters.get("location") == "berlin"


def test_router_web_search_classification() -> None:
    """Test IntentClassifier correctly routes web search queries."""
    classifier = get_intent_classifier()

    p1 = classifier.classify("search the web for quantum physics")
    assert p1.intent_type == IntentType.WEB_SEARCH
    assert p1.parameters.get("query") == "quantum physics"

    p2 = classifier.classify("look up artificial intelligence online")
    assert p2.intent_type == IntentType.WEB_SEARCH
    assert p2.parameters.get("query") == "artificial intelligence online"


def test_dispatcher_weather_and_search() -> None:
    """Test IntentDispatcher executes weather and search intents."""
    dispatcher = get_intent_dispatcher()

    with patch("orin.core.router.dispatcher.get_weather") as mock_weather:
        mock_weather.return_value = {
            "success": True,
            "spoken": "In Berlin, it is 15 degrees and sunny.",
        }
        classifier = get_intent_classifier()
        intent = classifier.classify("weather in Berlin")
        result = dispatcher.dispatch(intent)
        assert result.handled is True
        assert "15 degrees" in result.spoken_response

    with patch("orin.core.router.dispatcher.search_web") as mock_search:
        mock_search.return_value = {
            "success": True,
            "spoken": "According to DuckDuckGo: Antigravity is a concept.",
            "snippet": "Antigravity is a concept.",
        }
        intent = classifier.classify("search the web for antigravity")
        result = dispatcher.dispatch(intent)
        assert result.handled is True
        assert "Antigravity" in result.spoken_response


def test_cli_weather_and_search_commands() -> None:
    """Test CLI commands for weather and search."""
    with patch("orin.net.weather.get_weather") as mock_weather:
        mock_weather.return_value = {
            "success": True,
            "location": "Rome, Italy",
            "condition": "Clear sky",
            "temperature_c": 22.0,
            "humidity": 45,
            "wind_speed_kmh": 8.0,
            "spoken": "In Rome, it is 22 degrees and sunny.",
        }
        res = runner.invoke(app, ["weather", "Rome"])
        assert res.exit_code == 0
        assert "Rome" in res.stdout

    with patch("orin.net.search.search_web") as mock_search:
        mock_search.return_value = {
            "success": True,
            "source": "DuckDuckGo",
            "title": "Quantum Computing",
            "snippet": "Quantum computing is a rapidly-emerging technology.",
            "spoken": "Quantum computing is a rapidly-emerging technology.",
        }
        res = runner.invoke(app, ["search", "Quantum Computing"])
        assert res.exit_code == 0
        assert "Quantum Computing" in res.stdout
