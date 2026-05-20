# letterboxd-jellyseerr

Syncs your Letterboxd watchlist to Jellyseerr, auto-denies anything available on your streaming services, and gives you an iOS home screen widget to browse your watchlist and approve downloads.

## How it works

- A sync script runs on a schedule, scrapes your Letterboxd watchlist via [letterboxd-rss](https://codeberg.org/janw/letterboxd-rss), resolves each film to a TMDB ID, checks streaming availability, and creates Jellyseerr requests for anything not on your services
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
git clone https://github.com/Elliot1227/letterboxd-jellyseerr.git
cd letterboxd-jellyseerr
python3 -m venv venv
venv/bin/pip install -r requirements.txt
```

### 2. Configure

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

This will take a few minutes the first time — letterboxd-rss scrapes your watchlist pages, then the sync script hits each film's Letterboxd page to resolve the TMDB ID. All results are cached in `cache.json` so subsequent runs only process new additions.

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

Edit `letterboxd-api.service` — replace `your_user` with your actual username and verify the paths match where you cloned the repo.

```bash
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

Add a location block to your existing nginx config:

```nginx
location /watchlist/ {
    proxy_pass http://127.0.0.1:5000/;
    proxy_set_header Host $host;
}
```

Or expose it on a subdomain — whatever you already use for Jellyseerr, do the same here.

### 8. Set up the Scriptable widget (iOS)

1. Install [Scriptable](https://apps.apple.com/app/scriptable/id1405459188) (free)
2. Open Scriptable → tap **+** → paste the contents of `widget.js`
3. At the top of the script, set `API_BASE` to your external API URL:
   ```js
   const API_BASE = "https://yourdomain.com/watchlist"
   ```
4. Long-press your home screen → **+** → Scriptable → select this script
5. Choose **Medium** or **Large** size for the best poster display

Tapping the widget opens a detail view with streaming info and an Approve button. iOS refreshes the widget every 15–30 minutes, picking a new random film each time.

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

`cache.json` and `feed.xml` are created automatically. Don't commit them.

## .gitignore

```
cache.json
feed.xml
venv/
__pycache__/
*.pyc
```
