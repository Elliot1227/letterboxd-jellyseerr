// Letterboxd Widget — Scriptable (iOS)
// Drop this in Scriptable, add a medium or large widget, set the script.
// Tap the widget to open the detail view.
//
// CONFIG — edit these:
const API_BASE = "https://your-server.com:5000"  // your Flask API URL, no trailing slash
const WIDGET_BG_COLOR = new Color("#0f0f0f")
const TEXT_COLOR = new Color("#ffffff")
const ACCENT_COLOR = new Color("#f5c518")  // IMDb yellow, feels right for movies
const STREAMING_COLOR = new Color("#1db954")
const APPROVE_COLOR = new Color("#e50914")

// ---------------------------------------------------------------------------
// Fetch data
// ---------------------------------------------------------------------------

async function fetchFilm() {
  const req = new Request(`${API_BASE}/random`)
  req.timeoutInterval = 10
  try {
    return await req.loadJSON()
  } catch (e) {
    return null
  }
}

async function approveRequest(requestId) {
  const req = new Request(`${API_BASE}/approve/${requestId}`)
  req.method = "POST"
  req.timeoutInterval = 10
  try {
    return await req.loadJSON()
  } catch (e) {
    return { success: false, error: e.message }
  }
}

async function loadImage(url) {
  if (!url) return null
  try {
    const req = new Request(url)
    return await req.loadImage()
  } catch (e) {
    return null
  }
}

// ---------------------------------------------------------------------------
// Widget (home screen poster view)
// ---------------------------------------------------------------------------

async function buildWidget(film) {
  const w = new ListWidget()
  w.backgroundColor = WIDGET_BG_COLOR
  w.setPadding(0, 0, 0, 0)

  if (!film) {
    const err = w.addText("Could not load watchlist.\nCheck your API server.")
    err.textColor = TEXT_COLOR
    err.font = Font.systemFont(12)
    return w
  }

  // Background poster
  const poster = await loadImage(film.poster_url)
  if (poster) {
    w.backgroundImage = poster
  }

  // Gradient overlay so text is readable over the poster
  const gradient = new LinearGradient()
  gradient.locations = [0, 0.5, 1]
  gradient.colors = [
    new Color("#00000000"),
    new Color("#00000044"),
    new Color("#000000cc"),
  ]
  gradient.startPoint = new Point(0, 0)
  gradient.endPoint = new Point(0, 1)
  w.backgroundGradient = gradient

  w.addSpacer()

  // Streaming badges (bottom left)
  if (film.streaming && film.streaming.length > 0) {
    const row = w.addStack()
    row.layoutHorizontally()
    for (const service of film.streaming.slice(0, 3)) {
      const badge = row.addText(service.toUpperCase())
      badge.textColor = STREAMING_COLOR
      badge.font = Font.boldSystemFont(9)
      row.addSpacer(6)
    }
  }

  // Title
  const title = w.addText(film.title)
  title.textColor = TEXT_COLOR
  title.font = Font.boldSystemFont(16)
  title.lineLimit = 2

  // Year
  if (film.year) {
    const year = w.addText(String(film.year))
    year.textColor = new Color("#aaaaaa")
    year.font = Font.systemFont(12)
  }

  w.addSpacer(8)

  return w
}

// ---------------------------------------------------------------------------
// Detail view (shown on tap via Safari / in-app URL)
// We use a WebView presented via Safari Services since Scriptable
// doesn't have a native detail push. We build an HTML page and present it.
// ---------------------------------------------------------------------------

function buildDetailHTML(film) {
  const streamingHTML = film.streaming && film.streaming.length > 0
    ? film.streaming.map(s =>
        `<span class="badge">${s}</span>`
      ).join("")
    : `<span class="no-stream">Not on your services</span>`

  const approveButton = film.in_jellyseerr
    ? `<button class="approve" onclick="approve(${film.jellyseerr_request_id})">
         ↓ Approve Download
       </button>`
    : film.streaming && film.streaming.length === 0
      ? `<p class="no-request">Not in Jellyseerr yet — run a sync.</p>`
      : ``

  return `<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    background: #0a0a0a;
    color: #fff;
    font-family: -apple-system, BlinkMacSystemFont, sans-serif;
    min-height: 100vh;
  }
  .poster-wrap {
    position: relative;
    width: 100%;
    max-height: 60vh;
    overflow: hidden;
  }
  .poster-wrap img {
    width: 100%;
    display: block;
    object-fit: cover;
  }
  .poster-wrap::after {
    content: '';
    position: absolute;
    bottom: 0; left: 0; right: 0;
    height: 50%;
    background: linear-gradient(transparent, #0a0a0a);
  }
  .content {
    padding: 0 20px 40px;
    margin-top: -40px;
    position: relative;
    z-index: 1;
  }
  h1 {
    font-size: 26px;
    font-weight: 700;
    line-height: 1.2;
    margin-bottom: 4px;
  }
  .year {
    color: #888;
    font-size: 15px;
    margin-bottom: 20px;
  }
  .section-label {
    text-transform: uppercase;
    letter-spacing: 0.1em;
    font-size: 11px;
    color: #666;
    margin-bottom: 8px;
  }
  .streaming-row {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 28px;
  }
  .badge {
    background: #1a1a1a;
    border: 1px solid #1db954;
    color: #1db954;
    padding: 5px 12px;
    border-radius: 20px;
    font-size: 13px;
    font-weight: 600;
  }
  .no-stream {
    color: #555;
    font-size: 14px;
  }
  .approve {
    width: 100%;
    padding: 16px;
    background: #e50914;
    color: #fff;
    border: none;
    border-radius: 12px;
    font-size: 17px;
    font-weight: 700;
    letter-spacing: 0.02em;
    cursor: pointer;
    margin-top: 8px;
    -webkit-tap-highlight-color: transparent;
  }
  .approve:active { opacity: 0.8; }
  .approve:disabled { background: #444; color: #888; }
  .no-request { color: #555; font-size: 14px; margin-top: 8px; }
  .letterboxd-link {
    display: block;
    text-align: center;
    color: #555;
    font-size: 13px;
    text-decoration: none;
    margin-top: 24px;
    padding-top: 24px;
    border-top: 1px solid #1a1a1a;
  }
  .toast {
    position: fixed;
    bottom: 40px;
    left: 50%;
    transform: translateX(-50%);
    background: #1a1a1a;
    border: 1px solid #333;
    color: #fff;
    padding: 12px 24px;
    border-radius: 24px;
    font-size: 14px;
    opacity: 0;
    transition: opacity 0.3s;
    white-space: nowrap;
  }
  .toast.show { opacity: 1; }
</style>
</head>
<body>
  <div class="poster-wrap">
    ${film.poster_url ? `<img src="${film.poster_url}" alt="${film.title}">` : ''}
  </div>
  <div class="content">
    <h1>${film.title}</h1>
    <div class="year">${film.year || ''}</div>

    <div class="section-label">Streaming</div>
    <div class="streaming-row">${streamingHTML}</div>

    ${approveButton}

    <a class="letterboxd-link" href="${film.letterboxd_url}" target="_blank">
      View on Letterboxd →
    </a>
  </div>
  <div class="toast" id="toast"></div>

<script>
  const API_BASE = "${API_BASE}"

  async function approve(requestId) {
    const btn = document.querySelector('.approve')
    btn.disabled = true
    btn.textContent = 'Approving...'

    try {
      const res = await fetch(\`\${API_BASE}/approve/\${requestId}\`, { method: 'POST' })
      const data = await res.json()
      if (data.success) {
        btn.textContent = '✓ Approved'
        showToast('Download queued in Jellyseerr')
      } else {
        btn.disabled = false
        btn.textContent = '↓ Approve Download'
        showToast('Failed: ' + (data.error || 'unknown error'))
      }
    } catch (e) {
      btn.disabled = false
      btn.textContent = '↓ Approve Download'
      showToast('Network error')
    }
  }

  function showToast(msg) {
    const t = document.getElementById('toast')
    t.textContent = msg
    t.classList.add('show')
    setTimeout(() => t.classList.remove('show'), 3000)
  }
</script>
</body>
</html>`
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

async function run() {
  const film = await fetchFilm()

  // When tapped, Scriptable re-runs the script. We detect this via a param.
  if (config.runsInApp) {
    // Present the detail WebView
    if (film) {
      const html = buildDetailHTML(film)
      const wv = new WebView()
      await wv.loadHTML(html)
      await wv.present(false)
    } else {
      const alert = new Alert()
      alert.title = "Error"
      alert.message = "Could not fetch film data. Check API server."
      alert.addAction("OK")
      await alert.present()
    }
    return
  }

  // Running as widget
  const widget = await buildWidget(film)

  if (config.runsInWidget) {
    Script.setWidget(widget)
  } else {
    widget.presentMedium()
  }

  Script.complete()
}

run()
