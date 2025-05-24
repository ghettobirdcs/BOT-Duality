# WARN: I just deleted the progress bar code, so it may not work but still should be functional without a progress bar being sent to the channel as well.

import discord
import asyncio
from discord.ext import commands
from spotipy import Spotify
from spotipy.oauth2 import SpotifyClientCredentials
import yt_dlp
import aiohttp
from utils.config import is_in_allowed_channel, SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET

ARCHIVE_SEARCH_API = "https://archive.org/advancedsearch.php"

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.spotify_client = Spotify(auth_manager=SpotifyClientCredentials(
            client_id=SPOTIFY_CLIENT_ID,
            client_secret=SPOTIFY_CLIENT_SECRET,
        ))
        self.song_queues = {}  # {guild_id: asyncio.Queue}
        self.current_song = {}  # {guild_id: dict}
        self.status_message = {}  # {guild_id: message}

    def get_queue(self, guild_id):
        if guild_id not in self.song_queues:
            self.song_queues[guild_id] = asyncio.Queue()
        return self.song_queues[guild_id]

    def format_time(self, seconds):
        minutes, seconds = divmod(int(seconds), 60)
        return f"{minutes:02}:{seconds:02}"

    async def update_status_message(self, ctx, status=None, remove_status_after=None):
        guild_id = ctx.guild.id
        queue = self.get_queue(guild_id)
        current_song = self.current_song.get(guild_id, {"title": "No song playing", "duration": 0})
        title = current_song.get("title", "No song playing")
        duration = current_song.get("duration", 0)
        remaining_songs = list(queue._queue)
        next_song = remaining_songs[0]['title'] if remaining_songs else "None"
        queue_length = len(remaining_songs)

        embed = discord.Embed(
            title="🎵 Music Player Status",
            color=discord.Color.blue()
        )
        embed.add_field(name="Now Playing", value=f"`{title}`", inline=False)
        embed.add_field(name="Next Song", value=f"`{next_song}`", inline=False)
        embed.add_field(name="Songs in Queue", value=f"`{queue_length}`", inline=False)

        if status:
            embed.add_field(name="Status", value=status, inline=False)

        if guild_id in self.status_message:
            try:
                await self.status_message[guild_id].edit(embed=embed)
            except discord.NotFound:
                self.status_message[guild_id] = await ctx.send(embed=embed)
        else:
            self.status_message[guild_id] = await ctx.send(embed=embed)

        if remove_status_after:
            await asyncio.sleep(remove_status_after)
            await self.update_status_message(ctx)

    async def play_next_in_queue(self, ctx):
        guild_id = ctx.guild.id
        queue = self.get_queue(guild_id)

        if not queue.empty():
            next_song = await queue.get()
            self.current_song[guild_id] = next_song
            audio_url = next_song['audio_url']
            vc = ctx.voice_client

            try:
                while vc.is_playing():
                    await asyncio.sleep(0.5)

                vc.play(
                    discord.FFmpegPCMAudio(audio_url),
                    after=lambda e: self.bot.loop.create_task(self.play_next_in_queue(ctx))
                )

                await self.update_status_message(ctx)
            except Exception as e:
                print(f"[ERROR] Failed to play the next song in guild {guild_id}: {e}")
                await ctx.send(f"Failed to play the next song: {e}")
                if vc.is_connected():
                    await vc.disconnect()
        else:
            vc = ctx.voice_client
            if vc and vc.is_playing():
                print("Playback is ongoing; waiting for it to finish before resetting.")
                while vc.is_playing():
                    await asyncio.sleep(1)
            self.current_song[guild_id] = {"title": "No song playing"}
            print("Queue is empty. No song is currently playing.")
            await self.update_status_message(ctx)
            await asyncio.sleep(600)
            if ctx.voice_client and not ctx.voice_client.is_playing():
                await ctx.voice_client.disconnect()

    @commands.command()
    @is_in_allowed_channel()
    async def skip(self, ctx):
        try:
            await ctx.message.delete()
        except Exception as e:
            print(f"Failed to delete skip command message: {e}")

        if ctx.voice_client:
            if ctx.voice_client.is_playing():
                ctx.voice_client.stop()
                await self.play_next_in_queue(ctx)
            else:
                await ctx.send("No song is currently playing.")
        else:
            await ctx.send("I am not connected to any voice channel.")

    async def archive_search(self, query, max_results=5):
        """
        Search archive.org for audio items matching the query.
        Returns a list of dicts with 'identifier', 'title', and 'url' fields.
        """
        params = {
            "q": f"{query} AND mediatype:(audio)",
            "fl[]": "identifier,title",
            "rows": max_results,
            "sort[]": "downloads desc",
            "output": "json"
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(ARCHIVE_SEARCH_API, params=params) as resp:
                data = await resp.json()
                results = []
                for doc in data.get("response", {}).get("docs", []):
                    identifier = doc["identifier"]
                    title = doc.get("title", identifier)
                    url = f"https://archive.org/details/{identifier}"
                    results.append({"identifier": identifier, "title": title, "url": url})
                return results

    @commands.command()
    @is_in_allowed_channel()
    async def search(self, ctx, *, query: str):
        """
        Search for audio/music in archive.org and show top results.
        Usage: !search <keywords>
        """
        await ctx.send(f"Searching archive.org for `{query}`...")
        results = await self.archive_search(query)
        if not results:
            await ctx.send("No results found for your query on archive.org.")
            return

        embed = discord.Embed(
            title=f"Archive.org Search Results for '{query}'",
            color=discord.Color.green()
        )
        for i, res in enumerate(results, start=1):
            embed.add_field(name=f"{i}. {res['title']}", value=f"[Play this]({res['url']})", inline=False)
        embed.set_footer(text="To play a result, use !play <number> or provide a direct archive.org URL.")

        # Save results for play by number
        if not hasattr(self, "last_search"):
            self.last_search = {}
        self.last_search[ctx.guild.id] = results

        await ctx.send(embed=embed)

    @commands.command()
    @is_in_allowed_channel()
    async def play(self, ctx, *, arg: str):
        """
        Play a song from archive.org by URL or by search result number.
        Usage: !play <archive.org url> or !play <number>
        """
        # If arg is a digit, interpret as search result number
        if arg.isdigit():
            idx = int(arg) - 1
            results = getattr(self, "last_search", {}).get(ctx.guild.id)
            if not results or idx < 0 or idx >= len(results):
                await ctx.send("Invalid search result number. Use !search first and pick a valid number.")
                await ctx.message.delete()
                return
            url = results[idx]['url']
        else:
            url = arg.strip()

        if not ("archive.org" in url):
            await ctx.send("Please provide a valid archive.org URL or use !search to find music.", delete_after=10)
            await ctx.message.delete()
            return

        await self.update_status_message(ctx, status=f"Fetching audio from archive.org...")

        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
        }

        # Try to extract audio info from archive.org
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if info is None:
                    raise Exception("yt-dlp could not extract info from the provided URL.")
                if isinstance(info, dict) and 'entries' in info:
                    entries = info['entries']
                    if isinstance(entries, list) and entries:
                        info = entries[0]
                audio_url = info['url']
                title = info.get('title', 'Unknown Audio')
                duration = info.get('duration', 0)
        except Exception as e:
            await self.update_status_message(ctx, status=f"Failed to get audio from archive.org: {e}", remove_status_after=5)
            await ctx.message.delete()
            return

        queue = self.get_queue(ctx.guild.id)
        await queue.put({'audio_url': audio_url, 'title': title, 'duration': duration})

        await self.update_status_message(ctx, status=f"Queued: `{title}`", remove_status_after=2)

        if not ctx.voice_client:
            if ctx.author.voice:
                try:
                    channel = ctx.author.voice.channel
                    vc = await channel.connect()
                    await self.play_next_in_queue(ctx)
                except Exception as e:
                    await self.update_status_message(ctx, status=f"Failed to join the voice channel: {e}")
                    await ctx.message.delete()
                    return
            else:
                await self.update_status_message(ctx, status="You need to be in a voice channel to play music!")
                await ctx.message.delete()
                return
        elif not ctx.voice_client.is_playing():
            await self.play_next_in_queue(ctx)

        await ctx.message.delete()

    @commands.command()
    @commands.is_owner()
    @is_in_allowed_channel()
    async def stop(self, ctx):
        """Stops the current music and disconnects the bot from the voice channel."""
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
            self.current_song[ctx.guild.id] = {"title": "No song playing"}
        else:
            await ctx.send("I am not connected to any voice channel.")
        await self.update_status_message(ctx)

async def setup(bot):
    await bot.add_cog(Music(bot))
