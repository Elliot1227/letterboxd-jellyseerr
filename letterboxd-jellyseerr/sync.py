#!/usr/bin/env python3
"""
Letterboxd → Jellyseerr sync script.
Reads your Letterboxd watchlist, checks streaming availability,
auto-denies anything on your services, and queues the rest in Jellyseerr.
"""

import json
import time
import logging
import requests
import feedparser
from bs4 import BeautifulSoup
from pathlib import Path
from config import (
    LETTERBOXD_USERNAME,
    JELLYSEERR_URL,
    JELLYSEERR_API_KEY,
    STREAMING_API_KEY,
    STREAMING_SERVICES,
    COUNTRY_CODE,
    CACHE_FILE,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; letterboxd-sync/1.0)"}


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def load_cache() -> dict:
    if Path(CACHE_FILE).exists():
        with open(CACHE_FILE) as f:
            return json.load(f)
    return {}


def save_cache(cache: dict):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)


# ---------------------------------------------------------------------------
# Letterboxd
# ---------------------------------------------------------------------------

def fetch_watchlist() -> list[dict]:
    """Return list of {title, year, letterboxd_url} from RSS feed."""
    url = f"https://letterboxd.com/{LETTERBOXD_USERNAME}/watchlist/rss/"
    log.info(f"Fetching watchlist from {url}")
    feed = feedparser.parse(url)
    films = []
    for entry in feed.entries:
        films.append({
            "title": entry.get("letterboxd_filmtitle", entry.title),
            "year": entry.get("letterboxd_filmyear", ""),
            "letterboxd_url": entry.link,
        })
    log.info(f"Found {len(films)} films in watchlist")
    return films


def get_tmdb_id_from_letterboxd(letterboxd_url: str) -> int | None:
    """Scrape TMDB ID embedded in a Letterboxd film page."""
    try:
        r = requests.get(letterboxd_url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        # Letterboxd embeds TMDB id in a data attribute on the body
        body = soup.find("body")
        if body and body.get("data-tmdb-id"):
            return int(body["data-tmdb-id"])
        # Fallback: look in the film details section
        link = soup.find("a", attrs={"data-track-action": "TMDb"})
        if link and link.get("href"):
            # href like https://www.themoviedb.org/movie/12345
            parts = link["href"].rstrip("/").split("/")
            return int(parts[-1])
    except Exception as e:
        log.warning(f"Could not get TMDB ID from {letterboxd_url}: {e}")
    return None


# ---------------------------------------------------------------------------
# Streaming availability
# ---------------------------------------------------------------------------

def check_streaming(tmdb_id: int) -> list[str]:
    """Return list of service names this movie is available on (filtered to your services)."""
    url = "https://streaming-availability.p.rapidapi.com/shows/movie"
    params = {
        "tmdb_id": f"movie/{tmdb_id}",
        "series_granularity": "show",
        "output_language": "en",
    }
    headers = {
        "X-RapidAPI-Key": STREAMING_API_KEY,
        "X-RapidAPI-Host": "streaming-availability.p.rapidapi.com",
    }
    try:
        r = requests.get(url, headers=headers, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        available = []
        streaming_options = data.get("streamingOptions", {}).get(COUNTRY_CODE.lower(), [])
        for option in streaming_options:
            service_id = option.get("service", {}).get("id", "").lower()
            service_name = option.get("service", {}).get("name", "")
            if service_id in STREAMING_SERVICES:
                if service_name not in available:
                    available.append(service_name)
        return available
    except Exception as e:
        log.warning(f"Streaming check failed for TMDB {tmdb_id}: {e}")
    return []


# ---------------------------------------------------------------------------
# Jellyseerr
# ---------------------------------------------------------------------------

def jellyseerr_headers() -> dict:
    return {"X-Api-Key": JELLYSEERR_API_KEY, "Content-Type": "application/json"}


def get_existing_requests() -> dict[int, dict]:
    """Return {tmdb_id: request_object} for all existing Jellyseerr requests."""
    existing = {}
    page = 1
    while True:
        r = requests.get(
            f"{JELLYSEERR_URL}/api/v1/request",
            headers=jellyseerr_headers(),
            params={"take": 100, "skip": (page - 1) * 100},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        results = data.get("results", [])
        if not results:
            break
        for req in results:
            media = req.get("media", {})
            tmdb_id = media.get("tmdbId")
            if tmdb_id:
                existing[tmdb_id] = req
        page += 1
        if len(results) < 100:
            break
    return existing


def create_request(tmdb_id: int) -> dict | None:
    """Create a Jellyseerr movie request. Returns the created request or None."""
    payload = {"mediaType": "movie", "mediaId": tmdb_id}
    try:
        r = requests.post(
            f"{JELLYSEERR_URL}/api/v1/request",
            headers=jellyseerr_headers(),
            json=payload,
            timeout=10,
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log.warning(f"Failed to create request for TMDB {tmdb_id}: {e}")
    return None


def deny_request(request_id: int, reason: str = "Available on streaming"):
    """Deny a Jellyseerr request."""
    try:
        r = requests.post(
            f"{JELLYSEERR_URL}/api/v1/request/{request_id}/decline",
            headers=jellyseerr_headers(),
            json={"reason": reason},
            timeout=10,
        )
        r.raise_for_status()
        log.info(f"Denied request {request_id}: {reason}")
    except Exception as e:
        log.warning(f"Failed to deny request {request_id}: {e}")


# ---------------------------------------------------------------------------
# Main sync
# ---------------------------------------------------------------------------

def sync():
    cache = load_cache()
    films = fetch_watchlist()

    # Build a fresh watchlist snapshot in the cache
    cache["watchlist"] = []

    existing_requests = get_existing_requests()
    log.info(f"Found {len(existing_requests)} existing Jellyseerr requests")

    for film in films:
        url = film["letterboxd_url"]
        slug = url.rstrip("/").split("/")[-1]

        # Resolve TMDB ID (use cache to avoid re-scraping)
        film_cache = cache.get("films", {}).get(slug, {})
        tmdb_id = film_cache.get("tmdb_id")

        if not tmdb_id:
            log.info(f"Resolving TMDB ID for {film['title']}...")
            tmdb_id = get_tmdb_id_from_letterboxd(url)
            time.sleep(0.5)  # be polite to Letterboxd

        if not tmdb_id:
            log.warning(f"Could not resolve TMDB ID for {film['title']}, skipping")
            continue

        # Check streaming (use cache)
        streaming = film_cache.get("streaming")
        if streaming is None:
            streaming = check_streaming(tmdb_id)
            time.sleep(0.3)

        # Fetch poster from TMDB if not cached
        poster_path = film_cache.get("poster_path", "")
        if not poster_path:
            try:
                tmdb_r = requests.get(
                    f"https://api.themoviedb.org/3/movie/{tmdb_id}",
                    params={"api_key": ""},  # public metadata endpoint doesn't need key for basic info
                    timeout=10,
                )
                # We'll get poster via Jellyseerr's media endpoint instead
                pass
            except Exception:
                pass

        # Update film cache entry
        if "films" not in cache:
            cache["films"] = {}
        cache["films"][slug] = {
            "tmdb_id": tmdb_id,
            "title": film["title"],
            "year": film["year"],
            "letterboxd_url": url,
            "streaming": streaming,
            "poster_path": poster_path,
        }

        # Add to watchlist snapshot
        cache["watchlist"].append(slug)

        on_your_services = [s for s in streaming if s]

        if tmdb_id in existing_requests:
            req = existing_requests[tmdb_id]
            req_id = req["id"]
            req_status = req.get("status")  # 1=pending, 2=approved, 3=declined, 4=available
            # If it exists and is pending but available on streaming, deny it
            if req_status == 1 and on_your_services:
                log.info(f"{film['title']} is pending but available on {on_your_services}, denying")
                deny_request(req_id, f"Available on: {', '.join(on_your_services)}")
        else:
            if on_your_services:
                log.info(f"{film['title']} available on {on_your_services}, skipping Jellyseerr")
            else:
                log.info(f"Creating Jellyseerr request for {film['title']} (TMDB {tmdb_id})")
                req = create_request(tmdb_id)
                if req:
                    log.info(f"Created request {req.get('id')} for {film['title']}")
                time.sleep(0.3)

    save_cache(cache)
    log.info("Sync complete")


if __name__ == "__main__":
    sync()
