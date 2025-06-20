from utils.config import DISCORD_TOKEN
from utils.keep_alive import keep_alive
from discord.ext import commands
import asyncio
import discord
# import logging

# Configure logging
# logging.basicConfig(
#     level=logging.DEBUG,  # Set the logging level
#     format="%(asctime)s %(levelname)s: %(message)s",  # Log format
#     handlers=[
#         logging.FileHandler(filename="discord.log", encoding="utf-8", mode="w"),  # Log to a file
#     ]
# )

# handler = logging.FileHandler(filename="discord.log", encoding="utf-8", mode="w")
intents = discord.Intents.default()
intents.messages = True
intents.voice_states = True
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix=".", intents=intents)

@bot.event
async def on_message(message):
    # Pass the message to the MessageHandler cog
    await bot.get_cog("message_handler").on_message(message)  # pyright: ignore

@bot.event
async def on_ready():
    print(f"{bot.user.name} is online!")  # pyright: ignore

@bot.event
async def on_disconnect():
    print("[DISCONNECTED]")

@bot.command()
@commands.is_owner()
async def shutdown(ctx):
    await ctx.send("Shutting down...")
    await bot.close()  # Gracefully close the bot

async def load_cogs():
    """Load all cogs."""
    await bot.load_extension("cogs.message_handler")
    await bot.load_extension("cogs.error_handler")
    await bot.load_extension("cogs.welcome")
    await bot.load_extension("cogs.events")
    await bot.load_extension("cogs.music")

async def main():
    print("Starting bot...")
    async with bot:
        await load_cogs()
        await bot.start(DISCORD_TOKEN)  # pyright: ignore

if __name__ == "__main__":
    keep_alive()
    asyncio.run(main())
