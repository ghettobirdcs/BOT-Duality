import discord
import asyncio
from discord.ext import commands
from spotipy import Spotify
from spotipy.oauth2 import SpotifyClientCredentials
import yt_dlp
from utils.config import is_in_allowed_channel, SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET

# TODO: Make skip, pause, rewind commands
# TODO: Make embeds for the queue (song length, songs in queue, time until queued song starts)

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Initialize Spotify API client
        self.spotify_client = Spotify(auth_manager=SpotifyClientCredentials(
            client_id=SPOTIFY_CLIENT_ID,
            client_secret=SPOTIFY_CLIENT_SECRET,
        ))
        # Initialize a queue for each guild
        self.song_queues = {}  # {guild_id: asyncio.Queue}

    def get_queue(self, guild_id):
        """Get the queue for the given guild, or create one if it doesn't exist."""
        if guild_id not in self.song_queues:
            self.song_queues[guild_id] = asyncio.Queue()
        return self.song_queues[guild_id]

    async def play_next_in_queue(self, ctx):
        """Plays the next song in the queue, if it exists."""
        queue = self.get_queue(ctx.guild.id)
        if not queue.empty():
            # Get the next song from the queue
            next_song = await queue.get()
            audio_url = next_song['audio_url']
            video_title = next_song['title']
            vc = ctx.voice_client

            try:
                vc.play(discord.FFmpegPCMAudio(audio_url), after=lambda e: self.bot.loop.create_task(self.play_next_in_queue(ctx)))
                await ctx.send(f"Now playing: `{video_title}`")
            except Exception as e:
                await ctx.send(f"Failed to play the next song: {e}")
                if vc.is_connected():
                    await vc.disconnect()
        else:
            await asyncio.sleep(600)  # Disconnect after 10 minutes of inactivity
            if ctx.voice_client and not ctx.voice_client.is_playing():
                await ctx.voice_client.disconnect()
                await ctx.send("Disconnected due to inactivity.")

    @commands.command()
    @is_in_allowed_channel()
    async def play(self, ctx, *, query: str):
        """Plays a song from YouTube using a query or Spotify link."""
        # If the query is a Spotify link, extract metadata
        if "spotify.com" in query:
            try:
                track_info = self.spotify_client.track(query)
                track_name = track_info['name']
                artist_name = track_info['artists'][0]['name']
                search_query = f"{track_name} {artist_name}"
                status_message = await ctx.send(f"Searching YouTube for: `{track_name}` by `{artist_name}`")
            except Exception as e:
                status_message = await ctx.send("Failed to retrieve track information from Spotify.")
                return
        else:
            search_query = query
            status_message = await ctx.send(f"Searching YouTube for: `{search_query}`")

        # Search for the track on YouTube and retrieve the audio URL
        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'cookiefile': "./cookies.txt"
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(f"ytsearch:{search_query}", download=False)['entries'][0]
                audio_url = info['url']
                video_title = info['title']
                await status_message.edit(content=f"Queued: `{video_title}`")
            except Exception as e:
                await status_message.edit(content=f"Failed to find `{video_title}` on YouTube.")
                return

                # Add the song to the queue
        queue = self.get_queue(ctx.guild.id)
        await queue.put({'audio_url': audio_url, 'title': video_title})

        # Join the user's voice channel and start playing if not already playing
        if not ctx.voice_client:  # If the bot is not connected to a voice channel
            if ctx.author.voice:  # Check if the user is in a voice channel
                try:
                    channel = ctx.author.voice.channel
                    vc = await channel.connect()  # Connect to the channel
                    await self.play_next_in_queue(ctx)  # Start playing the first song
                except Exception as e:
                    await ctx.send(f"Failed to join the voice channel `{vc}`: {e}")
                    return
            else:
                await ctx.send("You need to be in a voice channel to play music!")
                return
        elif not ctx.voice_client.is_playing():  # If the bot is connected but not playing
            await self.play_next_in_queue(ctx)

    @commands.command()
    @is_in_allowed_channel()
    async def skip(self, ctx):
        """Skips the currently playing song."""
        if ctx.voice_client:  # Check if the bot is connected to a voice channel
            if ctx.voice_client.is_playing():  # Check if music is currently playing
                await ctx.send("Skipping the current song...")
                ctx.voice_client.stop()  # Stop the current song
                await self.play_next_in_queue(ctx)  # Play the next song in the queue
            else:
                await ctx.send("No song is currently playing.")
        else:
            await ctx.send("I am not connected to any voice channel.")

    @commands.command()
    @commands.is_owner()
    @is_in_allowed_channel()
    async def stop(self, ctx):
        """Stops the current music and disconnects the bot from the voice channel."""
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
            await ctx.send("Music stopped and disconnected from the voice channel.")
        else:
            await ctx.send("I am not connected to any voice channel.")

async def setup(bot):
    await bot.add_cog(Music(bot))