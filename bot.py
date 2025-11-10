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
player_sessions = {}
last_players = set()
last_status = None
message_id = None
last_reset_day = None  # Für Auto-Reset um Mitternacht

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
    global online_since, last_status, last_players, player_sessions, message_id, last_reset_day, server_status

    channel = client.get_channel(CHANNEL_ID)
    server = get_server_status()
    if not server:
        return

    # --- Auto-Reset um Mitternacht ---
    now_berlin = datetime.now(ZoneInfo("Europe/Berlin"))
    if last_reset_day is None:
        last_reset_day = now_berlin.date()

    # Reset nur einmal täglich
    if now_berlin.date() > last_reset_day:
        now_berlin_time = datetime.now(ZoneInfo("Europe/Berlin"))
        for p, times in player_sessions.items():
            if times["end"] is None:
                times["end"] = now_berlin_time
                times["total"] += now_berlin_time - times["start"]
        last_reset_day = now_berlin.date()

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
            online_since = datetime.now(ZoneInfo("Europe/Berlin"))
        uptime = datetime.now(ZoneInfo("Europe/Berlin")) - online_since
        uptime_str = f"{uptime.seconds//3600}h {(uptime.seconds//60)%60}m"
    else:
        online_since = None
        uptime_str = "–"

    # --- Spieler Joins / Leaves tracken ---
    now_berlin_time = datetime.now(ZoneInfo("Europe/Berlin"))
    if status_code == 1:
        joined = player_list - last_players
        left = last_players - player_list
        for p in joined:
            player_sessions[p] = {"start": now_berlin_time, "end": None, "total": timedelta()}
        for p in left:
            if p in player_sessions and player_sessions[p]["end"] is None:
                player_sessions[p]["end"] = now_berlin_time
                player_sessions[p]["total"] += now_berlin_time - player_sessions[p]["start"]
        last_players = player_list

    # --- Session-Text für Discord Embed ---
    session_lines = []
    for player, times in player_sessions.items():
        start_time = times["start"].astimezone(ZoneInfo("Europe/Berlin")).strftime("%H:%M")
        end_time = times["end"].astimezone(ZoneInfo("Europe/Berlin")).strftime("%H:%M") if times["end"] else "…"
        total_time = times["total"] + (now_berlin_time - times["start"] if times["end"] is None else timedelta())
        total_str = f"{total_time.seconds//3600}h {(total_time.seconds//60)%60}m"
        session_lines.append(f"• {player} → {start_time}–{end_time} ({total_str})")

    session_text = "\n".join(session_lines) if session_lines else "Noch keine Aktivität heute"

    # --- Serverstatus für Web.py aktualisieren ---
    server_status["status_text"] = status_text
    server_status["color"] = color
    server_status["players"] = list(player_list)
    server_status["sessions"] = {p: {"start": times["start"].isoformat(),
                                     "end": times["end"].isoformat() if times["end"] else None,
                                     "total_seconds": times["total"].total_seconds() +
                                                      (now_berlin_time - times["start"]).total_seconds() if times["end"] is None else times["total"].total_seconds()}
                                 for p, times in player_sessions.items()}
    server_status["uptime"] = uptime_str
    server_status["last_update"] = now_berlin.strftime("%H:%M:%S CET")

    # --- Embed vorbereiten ---
    embed = discord.Embed(
        title=f"{status_text} • {name}",
        description="💠 **Statusübersicht**",
        color=color,
        timestamp=datetime.now(ZoneInfo("Europe/Berlin"))
    )
    embed.add_field(name="⏱️ Uptime", value=uptime_str, inline=True)
    embed.add_field(name="👥 Spieler online", value=", ".join(player_list) if player_list else "Niemand online", inline=True)
    embed.add_field(name="📊 Heute online gewesen", value=session_text, inline=False)
    embed.set_footer(text=f"🕒 Letztes Update: {server_status['last_update']} • Automatisches Live-Update alle 10 Sekunden")

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