"""Weather information retrieval using free Open-Meteo API."""

from __future__ import annotations

from typing import Any

import httpx

from orin.config.settings import OrinConfig, get_config

# WMO Weather interpretation codes (WW)
WMO_CODE_MAP: dict[int, str] = {
    0: "clear sky",
    1: "mainly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "foggy",
    48: "depositing rime fog",
    51: "light drizzle",
    53: "moderate drizzle",
    55: "dense drizzle",
    61: "slight rain",
    63: "moderate rain",
    65: "heavy rain",
    71: "slight snow fall",
    73: "moderate snow fall",
    75: "heavy snow fall",
    77: "snow grains",
    80: "slight rain showers",
    81: "moderate rain showers",
    82: "violent rain showers",
    85: "slight snow showers",
    86: "heavy snow showers",
    95: "thunderstorm",
    96: "thunderstorm with slight hail",
    99: "thunderstorm with heavy hail",
}


def get_weather(location: str | None = None, config: OrinConfig | None = None) -> dict[str, Any]:
    """Fetches current weather for the specified location or default configured location.

    Returns structured weather data and a formatted spoken summary.
    """
    cfg = config or get_config()
    target_loc = (location or cfg.network.weather_location or "").strip()

    if not target_loc:
        target_loc = "London"  # Default fallback location if none configured

    try:
        # Step 1: Geocode location to lat/lon using Open-Meteo Geocoding API
        with httpx.Client(timeout=5.0) as client:
            geo_resp = client.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={"name": target_loc, "count": 1, "language": "en", "format": "json"},
            )
            if geo_resp.status_code != 200:
                return {
                    "success": False,
                    "location": target_loc,
                    "spoken": f"Could not find coordinates for {target_loc}.",
                }

            geo_data = geo_resp.json()
            results = geo_data.get("results")
            if not results:
                return {
                    "success": False,
                    "location": target_loc,
                    "spoken": f"Sorry, I couldn't find the location {target_loc}.",
                }

            first = results[0]
            lat = first["latitude"]
            lon = first["longitude"]
            city_name = first.get("name", target_loc)
            country = first.get("country", "")

            # Step 2: Fetch current weather forecast
            weather_resp = client.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
                    "temperature_unit": "celsius",
                },
            )
            if weather_resp.status_code != 200:
                return {
                    "success": False,
                    "location": city_name,
                    "spoken": f"Weather service is currently unavailable for {city_name}.",
                }

            w_data = weather_resp.json().get("current", {})
            temp = w_data.get("temperature_2m", 0.0)
            humidity = w_data.get("relative_humidity_2m", 0)
            code = w_data.get("weather_code", 0)
            wind = w_data.get("wind_speed_10m", 0.0)

            condition = WMO_CODE_MAP.get(code, "fair")
            loc_label = f"{city_name}, {country}" if country else city_name
            spoken = (
                f"In {city_name}, it's currently {round(temp)} degrees Celsius and {condition}, "
                f"with {humidity}% humidity and winds at {round(wind)} kilometers per hour."
            )

            return {
                "success": True,
                "location": loc_label,
                "temperature_c": temp,
                "condition": condition,
                "humidity": humidity,
                "wind_speed_kmh": wind,
                "spoken": spoken,
            }

    except httpx.RequestError:
        return {
            "success": False,
            "location": target_loc,
            "spoken": f"I couldn't fetch the weather for {target_loc} because the internet is unreachable.",
        }
    except Exception as e:
        return {
            "success": False,
            "location": target_loc,
            "spoken": f"Failed to retrieve weather: {e}",
        }
