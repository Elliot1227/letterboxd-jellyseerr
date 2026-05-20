# ---------------------------------------------------------------------------
# config.py — edit these before running anything
# ---------------------------------------------------------------------------

# Your Letterboxd username (the part in your profile URL)
LETTERBOXD_USERNAME = "your_letterboxd_username"

# Your Jellyseerr instance URL (no trailing slash)
JELLYSEERR_URL = "https://jellyseerr.yourdomain.com"

# Jellyseerr API key — Settings → General → API Key
JELLYSEERR_API_KEY = "your_jellyseerr_api_key"

# Streaming Availability API key from https://www.movieofthenight.com/about/api
STREAMING_API_KEY = "your_rapidapi_key"

# Your country code (US, GB, CA, etc.)
COUNTRY_CODE = "us"

# Service IDs as used by the Streaming Availability API.
# Full list: https://docs.movieofthenight.com/resource/countries
# Common ones: netflix, hulu, hbo, apple, prime, disney, paramount, peacock
STREAMING_SERVICES = {"netflix", "hulu", "hbo", "apple"}

# Where to store the local cache (watchlist + resolved IDs + streaming info)
CACHE_FILE = "/home/claude/letterboxd-jellyseerr/cache.json"

# Port the Flask API runs on
API_PORT = 5000

# How long to cache streaming availability results (seconds). 24 hours default.
STREAMING_CACHE_TTL = 86400
