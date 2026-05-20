#!/usr/bin/env python3
"""
Flask API for the Scriptable widget.
Endpoints:
  GET  /random           — random film from watchlist with streaming + Jellyseerr status
  POST /approve/<req_id> — approve a pending Jellyseerr request
  GET  /health           — sanity check
"""

import json
import random
import logging
import requests
from flask import Flask, jsonify, abort
from pathlib import Path
from config import (
    JELLYSEERR_URL,
    JELLYSEERR_API_KEY,
    CACHE_FILE,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

app = Flask(__name__)

TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_cache() -> dict:
    if Path(CACHE_FILE).exists():
        with open(CACHE_FILE) as f:
            return json.load(f)
    return {}


def jellyseerr_headers() -> dict:
    return {"X-Api-Key": JELLYSEERR_API_KEY, "Content-Type": "application/json"}


def get_jellyseerr_request_for_tmdb(tmdb_id: int) -> dict | None:
    """Find a Jellyseerr request by TMDB ID."""
    try:
        # Check media status directly
        r = requests.get(
            f"{JELLYSEERR_URL}/api/v1/movie/{tmdb_id}",
            headers=jellyseerr_headers(),
            timeout=8,
        )
        if r.status_code == 200:
            data = r.json()
            media_info = data.get("mediaInfo")
            if media_info:
                requests_list = media_info.get("requests", [])
                for req in requests_list:
                    if req.get("status") == 1:  # pending
                        return req
    except Exception as e:
        log.warning(f"Jellyseerr lookup failed for TMDB {tmdb_id}: {e}")
    return None


def get_poster_url(tmdb_id: int, cached_poster: str) -> str:
    """Return a full poster URL, fetching from TMDB if not cached."""
    if cached_poster:
        return f"{TMDB_IMAGE_BASE}{cached_poster}"
    try:
        r = requests.get(
            f"{JELLYSEERR_URL}/api/v1/movie/{tmdb_id}",
            headers=jellyseerr_headers(),
            timeout=8,
        )
        if r.status_code == 200:
            data = r.json()
            poster = data.get("posterPath")
            if poster:
                return f"{TMDB_IMAGE_BASE}{poster}"
    except Exception:
        pass
    return ""


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/random")
def random_film():
    cache = load_cache()
    watchlist = cache.get("watchlist", [])
    films = cache.get("films", {})

    if not watchlist:
        return jsonify({"error": "Watchlist is empty. Run sync.py first."}), 404

    # Pick a random slug from the watchlist
    slug = random.choice(watchlist)
    film = films.get(slug)

    if not film:
        return jsonify({"error": "Film not found in cache."}), 404

    tmdb_id = film["tmdb_id"]
    poster_url = get_poster_url(tmdb_id, film.get("poster_path", ""))

    # Check for pending Jellyseerr request
    jellyseerr_request = get_jellyseerr_request_for_tmdb(tmdb_id)
    request_id = jellyseerr_request["id"] if jellyseerr_request else None

    return jsonify({
        "title": film["title"],
        "year": film["year"],
        "tmdb_id": tmdb_id,
        "letterboxd_url": film["letterboxd_url"],
        "poster_url": poster_url,
        "streaming": film.get("streaming", []),
        "jellyseerr_request_id": request_id,
        "in_jellyseerr": request_id is not None,
    })


@app.route("/approve/<int:request_id>", methods=["POST"])
def approve_request(request_id: int):
    try:
        r = requests.post(
            f"{JELLYSEERR_URL}/api/v1/request/{request_id}/approve",
            headers=jellyseerr_headers(),
            timeout=10,
        )
        r.raise_for_status()
        return jsonify({"success": True, "request_id": request_id})
    except requests.HTTPError as e:
        log.error(f"Failed to approve request {request_id}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
    except Exception as e:
        log.error(f"Unexpected error approving {request_id}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from config import API_PORT
    app.run(host="0.0.0.0", port=API_PORT)
