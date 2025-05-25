# TODO: Set permanent weekly events for team practice that stay on redeploy

from discord.ui import View, Button
from discord.ext import commands
from datetime import datetime
import discord
import asyncio
import pytz
import json
import os

class Events(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.repeating_events = {}
        self.file_path = "repeating_events.json"
        self.load_repeating_events() # Load events on startup
        self.bot.loop.create_task(self.repeating_event_scheduler())

    def save_repeating_events(self):
        """Save repeating events to a file."""
        try:
            with open(self.file_path, "w") as f:
                json.dump(self.repeating_events, f, indent=4)
        except Exception as e:
            print(f"Error saving repeating events: {e}")

    def load_repeating_events(self):
        """Load repeating events from a file."""
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r") as f:
                    self.repeating_events = json.load(f)
                # Convert role IDs back to integers for Discord API compatibility
                for channel_id, events in self.repeating_events.items():
                    for event in events:
                        if event["role_to_mention"]:
                            event["role_to_mention"] = int(event["role_to_mention"])
            except Exception as e:
                print(f"Error loading repeating events: {e}")
                self.repeating_events = {}

    async def repeating_event_scheduler(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            current_time = int(datetime.now().timestamp())
            for channel_id, events in list(self.repeating_events.items()):
                for event in events[:]:  # Iterate over a copy of the list to allow modification
                    # Check if it's time to post the event 24 hours early
                    if (
                        current_time >= event["timestamp"] - 24 * 60 * 60  # 24 hours before the event
                        and not event.get("posted_early", False)  # Ensure it hasn't already been posted early
                    ):
                        channel = self.bot.get_channel(channel_id)
                        if channel:  # Ensure the channel is valid
                            embed = discord.Embed(
                                title=event["title"],
                                description=f"**Time:** <t:{event['timestamp']}:F> (relative: <t:{event['timestamp']}:R>)\n",
                                color=discord.Color.blue(),
                            )
                            embed.add_field(name="✅ Attending", value="[_______]", inline=True)
                            embed.add_field(name="❌ Not Attending", value="[_______]", inline=True)
                            embed.set_footer(text="Repeating Event")

                            # Mention the role if applicable
                            role_to_mention = channel.guild.get_role(event["role_to_mention"]) if event["role_to_mention"] else None
                            if role_to_mention:
                                await channel.send(f"{role_to_mention.mention}", embed=embed)
                            else:
                                await channel.send(embed=embed)

                            # Mark the event as posted early
                            event["posted_early"] = True

                            # Save updated events to file
                            self.save_repeating_events()

                    # Check if it's time to reschedule the event
                    if current_time >= event["timestamp"]:
                        # Reschedule the event for next week
                        event["timestamp"] += 7 * 24 * 60 * 60  # Add 7 days in seconds
                        event["posted_early"] = False  # Reset the early-post flag

                        # Save updated events to file
                        self.save_repeating_events()

            await asyncio.sleep(60)  # Check every minute

    @commands.command()
    @commands.has_role("Admins")
    async def event(self, ctx):
        try:
            await ctx.message.delete()
        except Exception as e:
            await ctx.send(f"Unexpected error when deleting command message: {e}", delete_after=10)
            return

        def check_dm(m):
            return m.author == ctx.author and isinstance(m.channel, discord.DMChannel)

        async def get_property(prompt):
            try:
                await ctx.author.send(prompt)
                msg = await self.bot.wait_for("message", check=check_dm, timeout=60.0)
                return msg.content
            except asyncio.TimeoutError:
                await ctx.author.send("You took too long to respond. Event creation canceled.")
                return None

        # Ask for the event title
        event_title = await get_property("Enter event title:")
        if not event_title:
            await ctx.author.send("Please provide a title. Event creation canceled.")
            return

        # Let the user choose from pytz timezones for MST, EST, PST, and Central
        try:
            await ctx.author.send("Please choose a timezone:\n1. MST\n2. EST\n3. PST\n4. CST")
            msg = await self.bot.wait_for("message", check=check_dm, timeout=60.0)
            timezone_choice = msg.content.strip().lower()

            if timezone_choice == "1":
                timezone = "America/Denver"
            elif timezone_choice == "2":
                timezone = "America/New_York"
            elif timezone_choice == "3":
                timezone = "America/Los_Angeles"
            elif timezone_choice == "4":
                timezone = "America/Chicago"
            else:
                await ctx.author.send("Invalid choice. Event creation canceled.")
                return
        except Exception as e:
            await ctx.author.send(f"Error retrieving timezones: {e}. Event creation canceled.")
            return

        # Get current year
        current_year = datetime.now(pytz.timezone(timezone)).year
        # Ask for the event date and time
        event_date = await get_property(f"Enter the event date (MM-DD)")
        if not event_date:
            await ctx.author.send("Please provide a date. Event creation canceled.")
            return

        # Validate the date format
        try:
            month, day = map(int, event_date.split("-"))
            if month < 1 or month > 12 or day < 1 or day > 31:
                raise ValueError("Invalid date")
            event_datetime = datetime(current_year, month, day)
            event_datetime = pytz.timezone(timezone).localize(event_datetime)
        except ValueError:
            await ctx.author.send("Invalid date format. Please use MM-DD. Event creation canceled.")
            return

        # Ask for the event time (not in 24-hour format)
        event_time = await get_property("Enter the event time (HH:MM AM/PM):")
        if not event_time:
            await ctx.author.send("Please provide a time. Event creation canceled.")
            return

        # Validate the time format
        try:
            event_time = datetime.strptime(event_time, "%I:%M %p").time()
            event_datetime = event_datetime.replace(hour=event_time.hour, minute=event_time.minute)
        except ValueError:
            await ctx.author.send("Invalid time format. Please use HH:MM AM/PM. Event creation canceled.")
            return

        # Get the timestamp for the event
        timestamp = int(event_datetime.timestamp())
        if timestamp < int(datetime.now(pytz.timezone(timezone)).timestamp()):
            await ctx.author.send("The event time must be in the future. Event creation canceled.")
            return

        # Ask for a role to mention
        role_name = await get_property("Which role should be mentioned for this event? (Provide the exact role name or type 'none' to skip)")
        if not role_name:
            await ctx.author.send("Please provide a role name. Event creation canceled.")
            return

        # Find the role in the guild
        role_to_mention = None
        if role_name.lower() != "none":
            role_to_mention = discord.utils.get(ctx.guild.roles, name=role_name)
            if not role_to_mention:
                await ctx.author.send(f"Role '{role_name}' not found. Event creation canceled.")
                return

        # Ask if the event should repeat weekly
        repeat_weekly = await get_property("Would you like this event to repeat weekly? (yes/no)")
        if not repeat_weekly or repeat_weekly.lower() not in ["yes", "no"]:
            await ctx.author.send("Invalid response. Event creation canceled.")
            return
        repeat_weekly = repeat_weekly.lower() == "yes"

        # Confirm and post the event
        await ctx.author.send("Thank you! Posting the event now...")
        embed = discord.Embed(
            title=event_title,
            description=f"**Time:** <t:{timestamp}:F> (relative: <t:{timestamp}:R>)\n",
            color=discord.Color.blue(),
        )
        embed.add_field(name="✅ Attending", value="[_______]", inline=True)
        embed.add_field(name="❌ Not Attending", value="[_______]", inline=True)
        embed.set_footer(text=f"Event created by {ctx.author.name}")

        # Create the buttons
        class EventView(View):
            def __init__(self):
                super().__init__(timeout=None)
                self.attending = []
                self.not_attending = []

            @discord.ui.button(label="✔", style=discord.ButtonStyle.green)
            async def attending_button(self, interaction: discord.Interaction, button: Button):
                if interaction.user.name not in self.attending:
                    self.attending.append(interaction.user.name)
                    if interaction.user.name in self.not_attending:
                        self.not_attending.remove(interaction.user.name)
                    await self.update_embed(interaction)

            @discord.ui.button(label="X", style=discord.ButtonStyle.red)
            async def not_attending_button(self, interaction: discord.Interaction, button: Button):
                if interaction.user.name not in self.not_attending:
                    self.not_attending.append(interaction.user.name)
                    if interaction.user.name in self.attending:
                        self.attending.remove(interaction.user.name)
                    await self.update_embed(interaction)

            async def update_embed(self, interaction: discord.Interaction):
                embed.set_field_at(0, name="✅ Attending", value="\n".join(self.attending) or "[_______]", inline=True)
                embed.set_field_at(1, name="❌ Not Attending", value="\n".join(self.not_attending) or "[_______]", inline=True)
                await interaction.response.edit_message(embed=embed, view=self)

        # Post the embed to the channel where the command was invoked
        view = EventView()
        if role_to_mention:
            await ctx.send(f"{role_to_mention.mention}", embed=embed, view=view)
        else:
            await ctx.send(embed=embed, view=view)

        # Schedule the event to repeat weekly if requested
        if repeat_weekly:
            if ctx.channel.id not in self.repeating_events:
                self.repeating_events[ctx.channel.id] = []
            self.repeating_events[ctx.channel.id].append({
                "title": event_title,
                "timestamp": timestamp,
                "role_to_mention": role_to_mention.id if role_to_mention else None,
            })
            self.save_repeating_events()  # Save after adding the event

async def setup(bot):
    await bot.add_cog(Events(bot))
