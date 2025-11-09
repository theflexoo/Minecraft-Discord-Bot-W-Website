from flask import Flask, jsonify, render_template_string
import os
from bot import server_status

app = Flask(__name__)

# --- API Route ---
@app.route("/api/online")
def api_online():
    return jsonify(server_status)

# --- HTML Template ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Minecraft Server Dashboard</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
<style>
body {
    background-color: #1b1b1b;
    display: flex;
    justify-content: center;
    align-items: center;
    height: 100vh;
    margin: 0;
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    color: #fff;
}

.card-container {
    background: #2c2c2c;
    padding: 2rem;
    border-radius: 1rem;
    max-width: 600px;
    width: 90%;
    box-shadow: 0 0 20px rgba(0,0,0,0.5);
}

.status-badge {
    font-size: 1.3rem;
    font-weight: bold;
    padding: 0.5em 1em;
    border-radius: 0.5em;
}

.player-online { color: #2ecc71; font-weight: bold; }
.player-offline { color: #e74c3c; font-weight: bold; }
.session { font-size: 0.9rem; }

.live-dot {
    display:inline-block;
    width:12px;
    height:12px;
    border-radius:50%;
    background:#2ecc71;
    animation: pulse 1s infinite;
    margin-left:5px;
}

@keyframes pulse {
    0% { transform:scale(0.8); opacity:0.6 }
    50% { transform:scale(1.2); opacity:1 }
    100% { transform:scale(0.8); opacity:0.6 }
}

ul { padding-left: 1rem; }
li { margin-bottom: 0.3rem; }
footer { text-align: center; margin-top: 1rem; font-size: 0.8rem; color: #aaa; }
</style>
</head>
<body>
<div class="card-container">
    <h1 class="mb-3 text-center">Minecraft Server Dashboard</h1>
    <div class="mb-3">
        <span>Status:</span>
        <span id="status" class="status-badge">lade…</span>
        <span class="live-dot"></span>
    </div>
    <div class="mb-3"><span>Uptime:</span> <span id="uptime">–</span></div>
    <div class="mb-3"><span>Letztes Update:</span> <span id="last_update">–</span></div>
    <h3>Spieler online:</h3>
    <ul id="players" class="list-group mb-3"></ul>
    <h3>Heute online gewesen:</h3>
    <ul id="sessions" class="list-group mb-3"></ul>
    <footer>Automatisch aktualisiert alle 10 Sekunden</footer>
</div>

<script>
async function refresh() {
    try {
        const res = await fetch('/api/online');
        if (!res.ok) return;
        const data = await res.json();

        document.getElementById('status').textContent = data.status_text;
        document.getElementById('status').style.backgroundColor = data.color;
        document.getElementById('uptime').textContent = data.uptime;
        document.getElementById('last_update').textContent = data.last_update;

        const list = document.getElementById('players');
        list.innerHTML = '';
        if (!data.players || data.players.length === 0) {
            list.innerHTML = '<li class="list-group-item player-offline">Niemand online</li>';
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
            let total = times.total_seconds || 0;
            const totalStr = `${Math.floor(total/3600)}h ${Math.floor((total%3600)/60)}m`;
            const li = document.createElement('li');
            li.className = 'list-group-item session';
            li.textContent = `• ${player} → ${start}–${end} (${totalStr})`;
            sessList.appendChild(li);
        }
    } catch (err) {
        console.error("Fehler beim Laden:", err);
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

def start_web():
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)