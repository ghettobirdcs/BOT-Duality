import discord
from discord.ext import commands
from spotipy import Spotify
from spotipy.oauth2 import SpotifyClientCredentials
import yt_dlp
import asyncio

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Initialize Spotify API client
        self.spotify_client = Spotify(auth_manager=SpotifyClientCredentials(
            client_id="YOUR_SPOTIFY_CLIENT_ID",
            client_secret="YOUR_SPOTIFY_CLIENT_SECRET"
        ))

    @commands.command(name="play")
    async def play(self, ctx, *, query: str):
        """Plays a song from YouTube using a query or Spotify link."""
        # If the query is a Spotify link, extract metadata
        if "spotify.com" in query:
            try:
                track_info = self.spotify_client.track(query)
                track_name = track_info['name']  # pyright: ignore
                artist_name = track_info['artists'][0]['name']  # pyright: ignore
                search_query = f"{track_name} {artist_name}"
                await ctx.send(f"Searching YouTube for: {track_name} by {artist_name}")
            except Exception as e:
                await ctx.send(f"Failed to retrieve track information from Spotify.\nError: {e}")
                return
        else:
            search_query = query
            await ctx.send(f"Searching YouTube for: {search_query}")

        # Search for the track on YouTube and retrieve the audio URL
        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(f"ytsearch:{search_query}", download=False)['entries'][0]
                audio_url = info['url']
                video_title = info['title']
                await ctx.send(f"Now playing: {video_title}")
            except Exception as e:
                await ctx.send("Failed to find the track on YouTube.")
                return

        # Join the user's voice channel and play the audio
        if ctx.author.voice:
            channel = ctx.author.voice.channel
            vc = await channel.connect()
            vc.play(discord.FFmpegPCMAudio(audio_url))
            while vc.is_playing():
                await asyncio.sleep(1)
            await vc.disconnect()
        else:
            await ctx.send("You need to be in a voice channel to play music!")

    @commands.command(name="stop")
    async def stop(self, ctx):
        """Stops the current music and disconnects the bot from the voice channel."""
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
            await ctx.send("Music stopped and disconnected from the voice channel.")
        else:
            await ctx.send("I am not connected to any voice channel.")

async def setup(bot):
    await bot.add_cog(Music(bot))
