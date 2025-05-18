from discord.ext import commands
from dotenv import load_dotenv
import discord
import os

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")