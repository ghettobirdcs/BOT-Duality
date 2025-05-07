import discord
from discord.ext import commands
from discord.ui import View, Button
from datetime import datetime, timedelta
import asyncio
import pytz

class Events(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # TODO: Fix repeating_events
        self.repeating_events = {}

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
        event_title = await get_property("What would you like to title this event?")
        if not event_title:
            return

        # Generate a list of times from noon to midnight
        mst = pytz.timezone("US/Mountain")  # Define the MST timezone
        now_mst = datetime.now(mst)
        # Round the current time down to the nearest hour
        now_mst = now_mst.replace(minute=0, second=0, microsecond=0)

        time_options = [now_mst + timedelta(hours=i) for i in range(49)]  # Generate times for the next 48 hours

        # Convert times to Discord relative timestamps (in UTC)
        time_strings = [
            f"{i + 1}: <t:{int(option.astimezone(pytz.utc).timestamp())}:F> (relative: <t:{int(option.astimezone(pytz.utc).timestamp())}:R>)"
            for i, option in enumerate(time_options)
        ]

        # Split the time options into chunks to avoid exceeding the 2000-character limit
        chunk_size = 10  # Number of options per message
        chunks = [time_strings[i:i + chunk_size] for i in range(0, len(time_strings), chunk_size)]
        
        # Send each chunk as a separate message
        await ctx.author.send("When should this event take place? Choose one of the following options by typing the number:")
        for chunk in chunks:
            await ctx.author.send("\n".join(chunk))
        
        # Wait for the user's response
        selected_index = await get_property("Please type the number corresponding to your choice:")

        if not selected_index or not selected_index.isdigit() or int(selected_index) - 1 not in range(len(time_options)):
            await ctx.author.send("Invalid selection. Event creation canceled.")
            return
        event_time = time_options[int(selected_index) - 1]

        # Ask for a role to mention
        role_name = await get_property("Which role should be mentioned for this event? (Provide the exact role name or type 'none' to skip)")
        if not role_name:
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
        # timestamp = int(time.mktime(event_time.astimezone(pytz.utc).timetuple()))  # Convert to Unix timestamp
        timestamp = int(event_time.astimezone(pytz.utc).timestamp())  # Convert to Unix timestamp
        embed = discord.Embed(
            title=event_title,
            description=f"**Time:** <t:{timestamp}:F> (relative: <t:{timestamp}:R>)\n",
            color=discord.Color.red(),
        )
        embed.add_field(name="✅ Attending", value="No one yet!", inline=True)
        embed.add_field(name="❌ Not Attending", value="No one yet!", inline=True)
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
                embed.set_field_at(0, name="✅ Attending", value="\n".join(self.attending) or "No one yet!", inline=True)
                embed.set_field_at(1, name="❌ Not Attending", value="\n".join(self.not_attending) or "No one yet!", inline=True)
                await interaction.response.edit_message(embed=embed, view=self)

        # Post the embed to the channel where the command was invoked
        view = EventView()
        if role_to_mention:
            await ctx.send(f"{role_to_mention.mention}", embed=embed, view=view)
        else:
            await ctx.send(embed=embed, view=view)

        # Schedule the event to repeat weekly if requested
        if repeat_weekly:
            self.repeating_events[ctx.channel.id] = {
                "ctx": ctx,
                "embed": embed,
                "view": view,
                "role_to_mention": role_to_mention,
            }

async def setup(bot):
    await bot.add_cog(Events(bot))
