#!/usr/bin/env python3
"""
Letterboxd → Jellyseerr sync script.
Scrapes your Letterboxd watchlist, checks streaming availability,
auto-denies anything on your services, and queues the rest in Jellyseerr.
"""

import os
import json
import time
import logging
import requests
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
    """Scrape watchlist pages directly from Letterboxd."""
    films = []
    page = 1

    while True:
        url = f"https://letterboxd.com/{LETTERBOXD_USERNAME}/watchlist/page/{page}/"
        log.info(f"Fetching watchlist page {page}...")
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        items = soup.select("li.griditem")
        if not items:
            break

        for item in items:
            div = item.find("div", attrs={"data-item-slug": True})
            if not div:
                continue
            slug = div["data-item-slug"]
            full_name = div.get("data-item-full-display-name", "")
            # full_name is like "Portrait of a Lady on Fire (2019)"
            year = ""
            title = full_name
            if full_name.endswith(")") and "(" in full_name:
                title, _, year_part = full_name.rpartition("(")
                title = title.strip()
                year = year_part.rstrip(")")
            link = div.get("data-item-link", f"/film/{slug}/")
            films.append({
                "title": title,
                "year": year,
                "letterboxd_url": f"https://letterboxd.com{link}",
            })

        page += 1
        time.sleep(0.5)

    log.info(f"Found {len(films)} films in watchlist")
    return films


def get_tmdb_id_from_letterboxd(letterboxd_url: str) -> int | None:
    """Scrape TMDB ID embedded in a Letterboxd film page."""
    try:
        r = requests.get(letterboxd_url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        body = soup.find("body")
        if body and body.get("data-tmdb-id"):
            return int(body["data-tmdb-id"])
        link = soup.find("a", attrs={"data-track-action": "TMDb"})
        if link and link.get("href"):
            parts = link["href"].rstrip("/").split("/")
            return int(parts[-1])
    except Exception as e:
        log.warning(f"Could not get TMDB ID from {letterboxd_url}: {e}")
    return None


# ---------------------------------------------------------------------------
# Streaming availability
# ---------------------------------------------------------------------------

def check_streaming(tmdb_id: int) -> list[str]:
    url = f"https://streaming-availability.p.rapidapi.com/shows/movie/{tmdb_id}"
    headers = {
        "X-RapidAPI-Key": STREAMING_API_KEY,
        "X-RapidAPI-Host": "streaming-availability.p.rapidapi.com",
    }
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
        available = []
        for option in data.get("streamingOptions", {}).get(COUNTRY_CODE.lower(), []):
            service_id = option.get("service", {}).get("id", "").lower()
            service_name = option.get("service", {}).get("name", "")
            if service_id in STREAMING_SERVICES and service_name not in available:
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
            tmdb_id = req.get("media", {}).get("tmdbId")
            if tmdb_id:
                existing[tmdb_id] = req
        page += 1
        if len(results) < 100:
            break
    return existing


def create_request(tmdb_id: int) -> dict | None:
    try:
        r = requests.post(
            f"{JELLYSEERR_URL}/api/v1/request",
            headers=jellyseerr_headers(),
            json={"mediaType": "movie", "mediaId": tmdb_id},
            timeout=10,
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log.warning(f"Failed to create request for TMDB {tmdb_id}: {e}")
    return None


def deny_request(request_id: int, reason: str = "Available on streaming"):
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
    if "films" not in cache:
        cache["films"] = {}

    films = fetch_watchlist()
    cache["watchlist"] = []

    existing_requests = get_existing_requests()
    log.info(f"Found {len(existing_requests)} existing Jellyseerr requests")

    for film in films:
        url = film["letterboxd_url"]
        slug = url.rstrip("/").split("/")[-1]

        film_cache = cache["films"].get(slug, {})
        tmdb_id = film_cache.get("tmdb_id")

        if not tmdb_id:
            log.info(f"Resolving TMDB ID for {film['title']}...")
            tmdb_id = get_tmdb_id_from_letterboxd(url)
            time.sleep(0.5)

        if not tmdb_id:
            log.warning(f"Could not resolve TMDB ID for {film['title']}, skipping")
            continue

        streaming = film_cache.get("streaming")
        if streaming is None:
            streaming = check_streaming(tmdb_id)
            time.sleep(0.3)

        cache["films"][slug] = {
            "tmdb_id": tmdb_id,
            "title": film["title"],
            "year": film["year"],
            "letterboxd_url": url,
            "streaming": streaming,
            "poster_path": film_cache.get("poster_path", ""),
        }
        cache["watchlist"].append(slug)

        on_your_services = [s for s in streaming if s]

        if tmdb_id in existing_requests:
            req = existing_requests[tmdb_id]
            if req.get("status") == 1 and on_your_services:
                log.info(f"{film['title']} is pending but on streaming, denying")
                deny_request(req["id"], f"Available on: {', '.join(on_your_services)}")
        else:
            if on_your_services:
                log.info(f"{film['title']} available on {on_your_services}, skipping")
            else:
                log.info(f"Creating request for {film['title']} (TMDB {tmdb_id})")
                req = create_request(tmdb_id)
                if req:
                    log.info(f"Created request {req.get('id')}")
                time.sleep(0.3)

    save_cache(cache)
    log.info("Sync complete")


if __name__ == "__main__":
    sync()
