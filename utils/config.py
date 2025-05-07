from discord.ext import commands
import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
REACTION_MESSAGE_ID = int(os.getenv("REACTION_MESSAGE_ID", 0))
AI_ROLE_NAME = os.getenv("AI_ROLE_NAME", "AI Fanclub")
NSFW_CHANNEL = int(os.getenv("NSFW_CHANNEL", 0))
MODEL_PATH = os.getenv("MODEL_PATH", "UnfilteredAI/NSFW-GEN-ANIME")

def is_in_allowed_channel():
    def predicate(ctx):
        return ctx.channel.id == int(os.getenv('NSFW_CHANNEL', 0))
    return commands.check(predicate)
