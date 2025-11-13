import discord
from discord.ext import tasks
import requests
from dotenv import load_dotenv
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# === .env laden ===
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
EXAROTON_API_KEY = os.getenv("EXAROTON_API_KEY")
SERVER_ID = os.getenv("SERVER_ID")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))

# === Discord Setup ===
intents = discord.Intents.default()
client = discord.Client(intents=intents)

# === Variablen ===
online_since = None
last_players = set()
last_status = None
message_id = None
last_reset_day = None

# Spieler-Sessions: { "Name": [ {start, end}, ... ] }
player_sessions = {}

# === Globale Statusdaten für Web.py ===
server_status = {
    "status_text": "",
    "color": 0xe74c3c,
    "players": [],
    "sessions": {},
    "uptime": "–",
    "last_update": None
}


# === API Abfrage ===
def get_server_status():
    url = f"https://api.exaroton.com/v1/servers/{SERVER_ID}"
    headers = {"Authorization": f"Bearer {EXAROTON_API_KEY}"}
    try:
        r = requests.get(url, headers=headers, timeout=5)
        data = r.json()
        return data["data"]
    except Exception as e:
        print("Fehler bei API:", e)
        return None


# === Discord Events ===
@client.event
async def on_ready():
    print(f"✅ Eingeloggt als {client.user}")
    status_loop.start()


# === Status Loop (alle 10 Sekunden) ===
@tasks.loop(seconds=10)
async def status_loop():
    global online_since, last_status, last_players, message_id, last_reset_day, player_sessions, server_status

    channel = client.get_channel(CHANNEL_ID)
    server = get_server_status()
    if not server:
        return

    now_berlin = datetime.now(ZoneInfo("Europe/Berlin"))
    current_date = now_berlin.date()

    # --- Auto-Reset genau um Mitternacht ---
    if last_reset_day is None:
        last_reset_day = current_date
    elif current_date > last_reset_day:
        print("🌙 Mitternachts-Reset ausgeführt.")
        player_sessions = {}
        last_reset_day = current_date

    status_code = server["status"]
    name = server["name"]
    player_info = server.get("players", {})
    player_list = set(player_info.get("list", [])) if "list" in player_info else set()

    # --- Status Mapping ---
    status_map = {
        0: ("🟥 Offline", 0xe74c3c),
        1: ("🟩 Online", 0x2ecc71),
        2: ("🟨 Startet", 0xf1c40f),
        3: ("🟧 Stoppt", 0xe67e22),
        4: ("🔁 Neustartet", 0x3498db)
    }
    status_text, color = status_map.get(status_code, ("❓ Unbekannt", 0x95a5a6))

    # --- Online-Zeit ---
    if status_code == 1:
        if online_since is None:
            online_since = now_berlin
        uptime = now_berlin - online_since
        uptime_str = f"{uptime.seconds//3600}h {(uptime.seconds//60)%60}m"
    else:
        online_since = None
        uptime_str = "–"

    # --- Spieler Joins / Leaves tracken ---
    joined = player_list - last_players
    left = last_players - player_list

    for p in joined:
        player_sessions.setdefault(p, []).append({"start": now_berlin, "end": None})
    for p in left:
        if p in player_sessions and player_sessions[p]:
            for s in reversed(player_sessions[p]):
                if s["end"] is None:
                    s["end"] = now_berlin
                    break

    last_players = player_list

    # --- Session-Text für Discord Embed ---
    session_lines = []
    for player, sessions in player_sessions.items():
        total_time = timedelta()
        parts = []
        for s in sessions:
            start_time = s["start"].strftime("%H:%M")
            end_time = s["end"].strftime("%H:%M") if s["end"] else "…"
            parts.append(f"{start_time}–{end_time}")
            end_point = s["end"] if s["end"] else now_berlin
            total_time += end_point - s["start"]
        total_str = f"{total_time.seconds//3600}h {(total_time.seconds//60)%60}m"
        session_lines.append(f"• {player} → {', '.join(parts)} ({total_str})")

    session_text = "\n".join(session_lines) if session_lines else "Noch keine Aktivität heute"

    # --- Serverstatus für Web.py aktualisieren ---
    sessions_for_web = {}
    for player, sessions in player_sessions.items():
        total_seconds = sum(
            ((s["end"] or now_berlin) - s["start"]).total_seconds() for s in sessions
        )
        sessions_for_web[player] = {
            "sessions": [
                {"start": s["start"].isoformat(), "end": s["end"].isoformat() if s["end"] else None}
                for s in sessions
            ],
            "total_seconds": total_seconds,
        }

    server_status["status_text"] = status_text
    server_status["color"] = color
    server_status["players"] = list(player_list)
    server_status["sessions"] = sessions_for_web
    server_status["uptime"] = uptime_str
    server_status["last_update"] = now_berlin.strftime("%H:%M:%S CET")

    # --- Embed vorbereiten ---
    embed = discord.Embed(
        title=f"{status_text} • {name}",
        description="💠 **Statusübersicht**",
        color=color,
        timestamp=now_berlin
    )
    embed.add_field(name="⏱️ Uptime", value=uptime_str, inline=True)
    embed.add_field(
        name="👥 Spieler online",
        value=", ".join(player_list) if player_list else "Niemand online",
        inline=True
    )
    embed.add_field(name="📊 Heute online gewesen", value=session_text, inline=False)
    embed.set_footer(
        text=f"🕒 Letztes Update: {server_status['last_update']} • Automatisches Live-Update alle 10 Sekunden"
    )

    # --- Nachricht verwalten ---
    if (last_status != 1 and status_code == 1) or message_id is None:
        async for msg in channel.history(limit=20):
            if msg.author == client.user:
                await msg.delete()
        msg = await channel.send(embed=embed)
        message_id = msg.id
    else:
        try:
            msg = await channel.fetch_message(message_id)
            await msg.edit(embed=embed)
        except:
            msg = await channel.send(embed=embed)
            message_id = msg.id

    last_status = status_code


def start_bot():
    client.run(TOKEN)