from flask import Flask
from threading import Thread
import time

app = Flask('')
port = process.env.PORT || 10000 # For running as a web app on render.com

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    app.run(host='0.0.0.0', port=port)

def keep_terminal_active():
    while True:
        print("Keeping terminal active...")
        time.sleep(300)  # Print every 5 minutes

def keep_alive():
    Thread(target=keep_terminal_active, daemon=True).start()
    t = Thread(target=run)
    t.start()
