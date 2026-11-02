"""Privacy-friendly web search and instant answer retrieval using public APIs."""

from __future__ import annotations

from typing import Any

import httpx


def search_web(query: str) -> dict[str, Any]:
    """Queries DuckDuckGo Instant Answer API and Wikipedia for quick factual answers.

    Returns concise text formatted for conversational voice output.
    """
    clean_query = query.strip()
    if not clean_query:
        return {
            "success": False,
            "query": "",
            "spoken": "Please specify what you would like me to search for.",
        }

    try:
        with httpx.Client(timeout=5.0) as client:
            # 1. Try DuckDuckGo Instant Answer API
            ddg_resp = client.get(
                "https://api.duckduckgo.com/",
                params={
                    "q": clean_query,
                    "format": "json",
                    "no_html": "1",
                    "skip_disambig": "1",
                },
                headers={"User-Agent": "Orin-Voice-Assistant/0.1.0"},
            )
            if ddg_resp.status_code == 200:
                ddg_data = ddg_resp.json()
                abstract = (ddg_data.get("AbstractText") or "").strip()
                if abstract:
                    heading = ddg_data.get("Heading", clean_query)
                    return {
                        "success": True,
                        "query": clean_query,
                        "source": "DuckDuckGo",
                        "title": heading,
                        "snippet": abstract,
                        "spoken": f"According to DuckDuckGo: {abstract}",
                    }

                # Check answer field (e.g. calculation or quick fact)
                answer = (ddg_data.get("Answer") or "").strip()
                if answer:
                    return {
                        "success": True,
                        "query": clean_query,
                        "source": "DuckDuckGo",
                        "title": clean_query,
                        "snippet": answer,
                        "spoken": f"{answer}",
                    }

            # 2. Fallback to Wikipedia summary API
            # Replace spaces with underscores and URL-encode
            wiki_topic = clean_query.replace(" ", "_")
            wiki_resp = client.get(
                f"https://en.wikipedia.org/api/rest_v1/page/summary/{wiki_topic}",
                headers={"User-Agent": "Orin-Voice-Assistant/0.1.0"},
            )
            if wiki_resp.status_code == 200:
                wiki_data = wiki_resp.json()
                extract = (wiki_data.get("extract") or "").strip()
                title = wiki_data.get("title", clean_query)
                if extract:
                    # Keep first two sentences for concise speech
                    sentences = [s.strip() for s in extract.split(". ") if s.strip()]
                    short_extract = ". ".join(sentences[:2])
                    if not short_extract.endswith("."):
                        short_extract += "."
                    return {
                        "success": True,
                        "query": clean_query,
                        "source": "Wikipedia",
                        "title": title,
                        "snippet": extract,
                        "spoken": f"According to Wikipedia: {short_extract}",
                    }

        return {
            "success": False,
            "query": clean_query,
            "spoken": f"I searched online for '{clean_query}', but didn't find a direct summary.",
        }

    except httpx.RequestError:
        return {
            "success": False,
            "query": clean_query,
            "spoken": f"I couldn't search online for '{clean_query}' because internet access is unavailable.",
        }
    except Exception as e:
        return {
            "success": False,
            "query": clean_query,
            "spoken": f"Web search encountered an error: {e}",
        }
