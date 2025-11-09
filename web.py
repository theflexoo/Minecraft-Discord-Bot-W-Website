from flask import Flask, jsonify, render_template_string
import os
import requests
from datetime import datetime, timedelta
import pytz

app = Flask(__name__)

EXAROTON_API_KEY = os.getenv("EXAROTON_API_KEY")
SERVER_ID = os.getenv("SERVER_ID")

# Cache für Spieler und Status
online_cache = {
    "status_code": 0,
    "status_text": "Offline",
    "color": "#e74c3c",
    "players": [],
    "sessions": {},
    "uptime": "–",
    "last_update": None
}

# Status Mapping
STATUS_MAP = {
    0: ("Offline", "#e74c3c", "🟥"),
    1: ("Online", "#2ecc71", "🟩"),
    2: ("Startet", "#f1c40f", "🟨"),
    3: ("Stoppt", "#e67e22", "🟧"),
    4: ("Neustartet", "#3498db", "🔁")
}

def fetch_server_status():
    global online_cache
    url = f"https://api.exaroton.com/v1/servers/{SERVER_ID}"
    headers = {"Authorization": f"Bearer {EXAROTON_API_KEY}"}
    try:
        r = requests.get(url, headers=headers, timeout=5)
        data = r.json()["data"]
        code = data["status"]
        status_text, color, icon = STATUS_MAP.get(code, ("Unbekannt", "#95a5a6", "❓"))
        online_cache["status_code"] = code
        online_cache["status_text"] = f"{icon} {status_text}"
        online_cache["color"] = color

        # Spieler
        player_list = data.get("players", {}).get("list", [])
        online_cache["players"] = player_list

        # Session Tracking
        now = datetime.now(pytz.timezone("Europe/Berlin"))
        # Spieler Sessions aufbauen oder aktualisieren
        sessions = online_cache.get("sessions", {})
        last_players = set(sessions.keys())
        current_players = set(player_list)

        joined = current_players - last_players
        left = last_players - current_players

        for p in joined:
            sessions[p] = {"start": now, "end": None, "total": timedelta()}

        for p in left:
            if sessions[p]["end"] is None:
                sessions[p]["end"] = now
                sessions[p]["total"] += now - sessions[p]["start"]

        # Update ongoing Spieler
        for p in current_players:
            if sessions[p]["end"] is None:
                sessions[p]["total"] += timedelta(seconds=0)  # Keine Änderung, nur Referenz

        online_cache["sessions"] = sessions

        # Uptime
        online_cache["uptime"] = data.get("uptime", "–")
        online_cache["last_update"] = now.strftime("%H:%M:%S")

    except Exception as e:
        print("Fehler bei Server-Abfrage:", e)

@app.route("/api/online")
def api_online():
    fetch_server_status()
    return jsonify(online_cache)

HTML_TEMPLATE = """
<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Minecraft Server Status</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
<style>
body { background-color: #f8f9fa; }
.status-badge { font-size: 1.2rem; font-weight: bold; padding: 0.5em 1em; border-radius: 0.5em; }
.player-online { color: #2ecc71; font-weight: bold; }
.player-offline { color: #e74c3c; font-weight: bold; }
.session { font-size: 0.9rem; }
.live-dot { display:inline-block; width:10px; height:10px; border-radius:50%; background:#2ecc71; animation: pulse 1s infinite; margin-right:5px; }
@keyframes pulse { 0% { transform:scale(0.8); opacity:0.6 } 50% { transform:scale(1.2); opacity:1 } 100% { transform:scale(0.8); opacity:0.6 } }
</style>
</head>
<body class="p-3">
<div class="container">
<h1 class="mb-3">Minecraft Server Dashboard</h1>
<div class="mb-3">
<span>Status:</span> <span id="status" class="status-badge" style="background-color: #e74c3c;">lade…</span> <span class="live-dot"></span>
</div>
<div class="mb-3">
<span>Uptime:</span> <span id="uptime">–</span>
</div>
<div class="mb-3">
<span>Letztes Update:</span> <span id="last_update">–</span>
</div>
<h3>Spieler online:</h3>
<ul id="players" class="list-group mb-3"></ul>
<h3>Heute online gewesen:</h3>
<ul id="sessions" class="list-group mb-3"></ul>
<footer class="text-muted small">Automatisch aktualisiert alle 10 Sekunden</footer>
</div>

<script>
async function refresh() {
    const res = await fetch('/api/online');
    if (!res.ok) return;
    const data = await res.json();
    document.getElementById('status').textContent = data.status_text;
    document.getElementById('status').style.backgroundColor = data.color;
    document.getElementById('uptime').textContent = data.uptime;
    document.getElementById('last_update').textContent = data.last_update;

    const list = document.getElementById('players');
    list.innerHTML = '';
    if (data.players.length === 0) {
        list.innerHTML = '<li class="list-group-item">Niemand online</li>';
    } else {
        data.players.forEach(p => {
            const li = document.createElement('li');
            li.className = 'list-group-item player-online';
            li.textContent = p;
            list.appendChild(li);
        });
    }

    const sessList = document.getElementById('sessions');
    sessList.innerHTML = '';
    const sessions = data.sessions || {};
    for (const [player, times] of Object.entries(sessions)) {
        let start = new Date(times.start).toLocaleTimeString('de-DE', {hour:'2-digit',minute:'2-digit'});
        let end = times.end ? new Date(times.end).toLocaleTimeString('de-DE',{hour:'2-digit',minute:'2-digit'}) : "…";
        let totalSec = times.total ? times.total.seconds || 0 : 0;
        const totalStr = `${Math.floor(totalSec/3600)}h ${Math.floor((totalSec%3600)/60)}m`;
        const li = document.createElement('li');
        li.className = 'list-group-item session';
        li.textContent = `• ${player} → ${start}–${end} (${totalStr})`;
        sessList.appendChild(li);
    }
}

refresh();
setInterval(refresh, 10000);
</script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))