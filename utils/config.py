from discord.ext import commands
from dotenv import load_dotenv
import os

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
MUSIC_PLAYER = os.getenv("MUSIC_PLAYER_CHANNEL")

def is_in_allowed_channel():
    def predicate(ctx):
        # Check if the command is in the allowed channel
        return ctx.channel.id == int(MUSIC_PLAYER)
    return commands.check(predicate)