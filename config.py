# ---------------------------------------------------------------------------
# config.py — edit these before running anything
# ---------------------------------------------------------------------------

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Your Letterboxd username
LETTERBOXD_USERNAME = "your_letterboxd_username"

# Your Jellyseerr instance URL (no trailing slash)
JELLYSEERR_URL = "https://jellyseerr.yourdomain.com"

# Jellyseerr API key — Settings → General → API Key
JELLYSEERR_API_KEY = "your_jellyseerr_api_key"

# Streaming Availability API key from https://www.movieofthenight.com/about/api
STREAMING_API_KEY = "your_rapidapi_key"

# Your country code
COUNTRY_CODE = "us"

# Service IDs from the Streaming Availability API.
# Common ones: netflix, hulu, hbo, apple, prime, disney, paramount, peacock
STREAMING_SERVICES = {"netflix", "hulu", "hbo", "apple"}

# Path to the venv Python binary — update if your venv is elsewhere
VENV_PYTHON = os.path.join(BASE_DIR, "venv", "bin", "python")

# Internal file paths — no need to change these
CACHE_FILE = os.path.join(BASE_DIR, "cache.json")
FEED_FILE  = os.path.join(BASE_DIR, "feed.xml")

# Port the Flask API listens on
API_PORT = 5000
