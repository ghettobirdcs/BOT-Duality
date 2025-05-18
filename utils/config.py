from discord.ext import commands
from dotenv import load_dotenv
import discord
import os

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
REACTION_MESSAGE_ID = int(os.getenv("REACTION_MESSAGE_ID", 0))
AI_ROLE_NAME = os.getenv("AI_ROLE_NAME", "AI Fanclub")
NSFW_CHANNEL = int(os.getenv("NSFW_CHANNEL", 0))
MODEL_PATH = os.getenv("MODEL_PATH") 
HF_TOKEN = os.getenv("HF_TOKEN")

def is_in_allowed_channel():
    def predicate(ctx):
        # Check if the command is in the allowed channel or a dm
        return isinstance(ctx.channel, discord.DMChannel) or ctx.channel.id == NSFW_CHANNEL
    return commands.check(predicate)
