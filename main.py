import threading
import bot
import web
import os

# --- Discord-Bot im Hintergrund starten ---
bot_thread = threading.Thread(target=bot.start_bot, daemon=True)
bot_thread.start()

# --- Website im Hauptthread starten ---
# Stelle sicher, dass PORT gesetzt ist (Render setzt automatisch)
port = int(os.getenv("PORT", 10000))
web.app.run(host="0.0.0.0", port=port, debug=False)