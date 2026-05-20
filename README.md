# letterboxd-jellyseerr

Syncs your Letterboxd watchlist to Jellyseerr, auto-denies anything available on your streaming services, and gives you an iOS home screen widget to browse your watchlist and approve downloads.

## How it works

- A sync script runs on a schedule, reads your Letterboxd watchlist RSS feed, resolves each film to a TMDB ID, checks streaming availability, and creates Jellyseerr requests for anything not on your services
- Anything already on Netflix/Hulu/HBO Max/Apple TV gets auto-denied in Jellyseerr
- A small Flask API serves your watchlist data to the widget
- A Scriptable iOS widget shows a random film poster from your full watchlist — tap it to see streaming info and approve the download

## Prerequisites

- Python 3.10+
- A self-hosted Jellyseerr instance with an external URL
- A [Streaming Availability API](https://www.movieofthenight.com/about/api) key (free tier is fine)
- [Scriptable](https://apps.apple.com/app/scriptable/id1405459188) on iOS (free)

## Setup

### 1. Clone and install

```bash
git clone https://github.com/yourusername/letterboxd-jellyseerr.git
cd letterboxd-jellyseerr
python3 -m venv venv
venv/bin/pip install -r requirements.txt
```

### 2. Configure

Copy the example config and fill it in:

```bash
cp config.py config.local.py  # optional — or just edit config.py directly
```

Edit `config.py`:

```python
LETTERBOXD_USERNAME = "yourname"
JELLYSEERR_URL      = "https://jellyseerr.yourdomain.com"
JELLYSEERR_API_KEY  = "..."   # Jellyseerr → Settings → General → API Key
STREAMING_API_KEY   = "..."   # from movieofthenight.com/about/api
COUNTRY_CODE        = "us"
STREAMING_SERVICES  = {"netflix", "hulu", "hbo", "apple"}
```

Service ID reference:

| Service | ID |
|---|---|
| Netflix | `netflix` |
| Hulu | `hulu` |
| HBO Max | `hbo` |
| Apple TV+ | `apple` |
| Disney+ | `disney` |
| Prime Video | `prime` |
| Peacock | `peacock` |
| Paramount+ | `paramount` |

### 3. Run the first sync

```bash
venv/bin/python sync.py
```

This scrapes each Letterboxd film page once to resolve TMDB IDs. Takes a few minutes depending on watchlist size. Results are cached in `cache.json` so subsequent runs are fast.

### 4. Start the API

```bash
venv/bin/python api.py
```

Test it:

```bash
curl http://localhost:5000/random
curl http://localhost:5000/health
```

### 5. Run as a systemd service

```bash
# Edit the service file — update User and all paths to match your system
nano letterboxd-api.service

sudo cp letterboxd-api.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable letterboxd-api
sudo systemctl start letterboxd-api
sudo systemctl status letterboxd-api
```

### 6. Schedule the sync

```bash
crontab -e
```

Add (runs daily at 6am):

```
0 6 * * * /home/youruser/letterboxd-jellyseerr/venv/bin/python /home/youruser/letterboxd-jellyseerr/sync.py >> /var/log/letterboxd-sync.log 2>&1
```

### 7. Expose the API

Add a location block to your existing nginx config (same server as Jellyseerr):

```nginx
location /watchlist/ {
    proxy_pass http://127.0.0.1:5000/;
    proxy_set_header Host $host;
}
```

Or use a subdomain — whatever you prefer. The widget just needs an HTTPS URL it can reach from your phone.

### 8. Set up the Scriptable widget

1. Open Scriptable → tap **+** → paste the contents of `widget.js`
2. At the top of the script, set `API_BASE` to your external API URL:
   ```js
   const API_BASE = "https://yourdomain.com/watchlist"
   ```
3. Long-press your home screen → **+** → Scriptable → select this script
4. Choose **Medium** or **Large** size for the best poster display

Tapping the widget opens a detail view with streaming availability and an Approve button. The widget picks a new random film each time iOS refreshes it (every 15–30 min).

## File overview

```
letterboxd-jellyseerr/
├── config.py                 ← all settings, edit this first
├── sync.py                   ← watchlist sync, run on cron
├── api.py                    ← Flask API for the widget
├── widget.js                 ← paste into Scriptable on iOS
├── letterboxd-api.service    ← systemd service for api.py
├── requirements.txt
└── README.md
```

`cache.json` is created automatically on first sync. Don't commit it — it contains your watchlist state and will be regenerated.

## .gitignore

```
cache.json
venv/
__pycache__/
*.pyc
```
