# TODO: Understand this
# TODO: Add cookies command if possible

import discord
import asyncio
from discord.ext import commands
from spotipy import Spotify
from spotipy.oauth2 import SpotifyClientCredentials
import yt_dlp
from utils.config import is_in_allowed_channel, SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET

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
        self.current_song = {}  # {guild_id: dict} - Stores the currently playing song
        self.status_message = {}  # {guild_id: message}
        self.progress_message = {}  # {guild_id: message} - Progress bar message
        self.progress_task = {}  # {guild_id: asyncio.Task} - Tracks progress bar updates

    def get_queue(self, guild_id):
        """Get the queue for the given guild, or create one if it doesn't exist."""
        if guild_id not in self.song_queues:
            self.song_queues[guild_id] = asyncio.Queue()
        return self.song_queues[guild_id]

    def generate_progress_bar(self, elapsed, total):
        """Generates a progress bar for the elapsed and total time."""
        bar_length = 30  # Total length of the progress bar
        progress = min(int((elapsed / total) * bar_length), bar_length)
        bar = "▬" * progress + "🔘" + "▬" * (bar_length - progress)
        return f"{bar} {self.format_time(elapsed)} / {self.format_time(total)}"

    def format_time(self, seconds):
        """Formats time in seconds to MM:SS."""
        minutes, seconds = divmod(int(seconds), 60)
        return f"{minutes:02}:{seconds:02}"

    async def update_status_message(self, ctx, status=None, remove_status_after=None):
        """Updates the embed message with the current song, queue, and optional status."""
        guild_id = ctx.guild.id
        queue = self.get_queue(guild_id)
        current_song = self.current_song.get(guild_id, {"title": "No song playing", "duration": 0})
        title = current_song.get("title", "No song playing")
        duration = current_song.get("duration", 0)
        remaining_songs = list(queue._queue)
        next_song = remaining_songs[0]['title'] if remaining_songs else "None"
        queue_length = len(remaining_songs)

        # Log the data that will be displayed in the embed
        # print(f"Updating embed for guild {guild_id}")
        # print(f"Current song: {current_song}")
        # print(f"Next song: {next_song}")
        # print(f"Queue length: {queue_length}")

        embed = discord.Embed(
            title="🎵 Music Player Status",
            color=discord.Color.blue()
        )
        embed.add_field(name="Now Playing", value=f"`{title}`", inline=False)
        embed.add_field(name="Next Song", value=f"`{next_song}`", inline=False)
        embed.add_field(name="Songs in Queue", value=f"`{queue_length}`", inline=False)

        # Optional status field (e.g., "Searching for a song...")
        if status:
            embed.add_field(name="Status", value=status, inline=False)

        # Edit the existing status message if it exists
        if guild_id in self.status_message:
            try:
                await self.status_message[guild_id].edit(embed=embed)
            except discord.NotFound:
                # If the message was deleted, create a new one
                self.status_message[guild_id] = await ctx.send(embed=embed)
        else:
            # Create a new status message if it doesn't exist
            self.status_message[guild_id] = await ctx.send(embed=embed)

        # If remove_status_after is set, wait and then remove the status field
        if remove_status_after:
            await asyncio.sleep(remove_status_after)
            await self.update_status_message(ctx)  # Re-render without the status field

    async def update_progress_message(self, ctx, duration):
        """Updates the progress bar message at regular intervals."""
        guild_id = ctx.guild.id
        elapsed = 0

        try:
            # Create or update the progress bar periodically
            while elapsed < duration:
                progress_bar = self.generate_progress_bar(elapsed, duration)
                
                # If progress message doesn't exist, create it
                if guild_id not in self.progress_message:
                    self.progress_message[guild_id] = await ctx.send(progress_bar)
                else:
                    # Update existing progress message
                    await self.progress_message[guild_id].edit(content=progress_bar)
                
                await asyncio.sleep(10)  # Update every 10 seconds
                elapsed += 10

        except discord.NotFound:
            # If the message is deleted, stop updating
            print(f"[DEBUG] Progress bar message for guild {guild_id} was deleted.")
        except Exception as e:
            # Log any unexpected errors
            print(f"[ERROR] Error in progress task for guild {guild_id}: {e}")
        finally:
            # Cleanup: delete progress message when the song ends
            if guild_id in self.progress_message:
                try:
                    await self.progress_message[guild_id].delete()
                    del self.progress_message[guild_id]
                except discord.NotFound:
                    pass

    async def play_next_in_queue(self, ctx):
        """Plays the next song in the queue, if it exists."""
        guild_id = ctx.guild.id
        queue = self.get_queue(guild_id)

        if not queue.empty():
            # Get the next song from the queue
            next_song = await queue.get()
            self.current_song[guild_id] = next_song  # Update the currently playing song
            audio_url = next_song['audio_url']
            duration = next_song.get("duration", 0)
            vc = ctx.voice_client

            # Cancel any existing progress task
            if guild_id in self.progress_task:
                self.progress_task[guild_id].cancel()
                del self.progress_task[guild_id]

            try:
                # Wait until the current audio playback stops (if necessary)
                while vc.is_playing():
                    await asyncio.sleep(0.5)

                # Play the next song
                ffmpeg_options = {
                    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
                    'options': '-af "volume=0.1"',
                }
                vc.play(
                    discord.FFmpegPCMAudio(audio_url, **ffmpeg_options),
                    after=lambda e: self.bot.loop.create_task(self.play_next_in_queue(ctx))
                )

                # Log the song and queue state
                # print(f"Playing next song: {self.current_song[guild_id]}")
                # print(f"Remaining queue: {list(queue._queue)}")

                # Update the embed immediately after the song starts playing
                await self.update_status_message(ctx)

                # Start tracking progress
                self.progress_task[guild_id] = self.bot.loop.create_task(
                    self.update_progress_message(ctx, duration)
                )
            except Exception as e:
                # Inform the user if the next song fails to play
                print(f"[ERROR] Failed to play the next song in guild {guild_id}: {e}")
                await ctx.send(f"Failed to play the next song: {e}")
                if vc.is_connected():
                    await vc.disconnect()
        else:
            # Queue is empty but only reset the song after playback stops
            await asyncio.sleep(1)
            vc = ctx.voice_client
            if vc and vc.is_playing():
                print("Playback is ongoing; waiting for it to finish before resetting.")
                while vc.is_playing():
                    await asyncio.sleep(1)
            self.current_song[guild_id] = {"title": "No song playing"}  # Reset current song
            print("Queue is empty. No song is currently playing.")
            await self.update_status_message(ctx)
            
            # Cleanup progress message when queue becomes empty
            if guild_id in self.progress_message:
                try:
                    await self.progress_message[guild_id].delete()
                    del self.progress_message[guild_id]
                except discord.NotFound:
                    pass
            
            await asyncio.sleep(600)  # Disconnect after 10 minutes of inactivity
            if ctx.voice_client and not ctx.voice_client.is_playing():
                await ctx.voice_client.disconnect()

    @commands.command()
    @is_in_allowed_channel()
    async def skip(self, ctx):
        # Attempt to delete the user's command message
        try:
            await ctx.message.delete()
        except Exception as e:
            print(f"Failed to delete skip command message: {e}")

        """Skips the currently playing song."""
        guild_id = ctx.guild.id

        # Cancel the current progress task if it exists
        if guild_id in self.progress_task:
            self.progress_task[guild_id].cancel()
            del self.progress_task[guild_id]

        # Stop the current song and wait for it to stop before playing the next one
        if ctx.voice_client:  # Check if the bot is connected to a voice channel
            if ctx.voice_client.is_playing():  # Check if music is currently playing
                # print(f"Skipping song: {self.current_song[guild_id]}")
                ctx.voice_client.stop()  # Stop the current song
                await self.play_next_in_queue(ctx)  # Play the next song in the queue
            else:
                await ctx.send("No song is currently playing.")
        else:
            await ctx.send("I am not connected to any voice channel.")

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
            except Exception as e:
                await ctx.send("Failed to retrieve track information from Spotify.", delete_after=10)
                await ctx.message.delete()  # Delete the user's command message
                return
        else:
            search_query = query

        # Update the embed to show "Searching..." status
        await self.update_status_message(ctx, status=f"Searching for `{search_query}` on YouTube...")

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
            for i in range(3):  # Retry up to 3 times
                try:
                    info = ydl.extract_info(f"ytsearch:{search_query}", download=False)['entries'][0]
                    audio_url = info['url']
                    video_title = info['title']
                    duration = info['duration']  # Duration in seconds
                    break
                except Exception as e:
                    await self.update_status_message(ctx, status=f"Failed to find `{search_query}`. [{i}] Trying again...")
                    await ctx.message.delete()  # Delete the user's command message
                    await asyncio.sleep(2)  # Wait before retrying
                    continue

        # Add the song to the queue
        queue = self.get_queue(ctx.guild.id)
        await queue.put({'audio_url': audio_url, 'title': video_title, 'duration': duration})

        # Update the embed to show the song was queued, then remove the status after 2 seconds
        await self.update_status_message(ctx, status=f"Queued: `{video_title}`", remove_status_after=2)

        # Join the user's voice channel and start playing if not already playing
        if not ctx.voice_client:  # If the bot is not connected to a voice channel
            if ctx.author.voice:  # Check if the user is in a voice channel
                try:
                    channel = ctx.author.voice.channel
                    vc = await channel.connect()  # Connect to the channel
                    await self.play_next_in_queue(ctx)  # Start playing the first song
                except Exception as e:
                    await self.update_status_message(ctx, status=f"Failed to join the voice channel: {e}")
                    await ctx.message.delete()  # Delete the user's command message
                    return
            else:
                await self.update_status_message(ctx, status="You need to be in a voice channel to play music!")
                await ctx.message.delete()  # Delete the user's command message
                return
        elif not ctx.voice_client.is_playing():  # If the bot is connected but not playing
            await self.play_next_in_queue(ctx)

        # Delete the user's command message
        await ctx.message.delete()

    @commands.command()
    @commands.is_owner()
    @is_in_allowed_channel()
    async def stop(self, ctx):
        """Stops the current music and disconnects the bot from the voice channel."""
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
            self.current_song[ctx.guild.id] = {"title": "No song playing"}  # Reset current song
        else:
            await ctx.send("I am not connected to any voice channel.")
        await self.update_status_message(ctx)

async def setup(bot):
    await bot.add_cog(Music(bot))
