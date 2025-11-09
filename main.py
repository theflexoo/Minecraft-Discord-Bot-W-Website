# main.py
import threading
import bot
import web

# Bot in eigenem Thread starten
t = threading.Thread(target=bot.start_bot)
t.start()

# Website starten
web.start_web()