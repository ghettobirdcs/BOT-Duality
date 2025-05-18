from flask import Flask
from threading import Thread
import time

app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_terminal_active():
    while True:
        print("Keeping terminal active...")
        time.sleep(300)  # Print every 5 minutes

def keep_alive():
    Thread(target=keep_terminal_active, daemon=True).start()
    t = Thread(target=run)
    t.start()