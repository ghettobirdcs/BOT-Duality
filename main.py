from datetime import datetime, timedelta
from discord.ui import Button, View
from discord.ext import commands
from dotenv import load_dotenv
from discord.ext import tasks
import asyncio
import discord
import logging
import pytz
import time
import os

load_dotenv()
token = os.getenv("DISCORD_TOKEN")

handler = logging.FileHandler(filename="discord.log", encoding="utf-8", mode="w")
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=".", intents=intents)
banned_words = ["diddy",]

repeating_events = {}

@bot.event
async def on_ready():
    # print(f"{bot.user.name} online")
    pass

@bot.event
async def on_member_join(member, ctx):
    await member.send(f"Welcome to Duality, {member.name}!")
    role = discord.utils.get(ctx.guild.roles, name="Prospects")
    if role:
        await ctx.author.add_roles(role)
        await ctx.send(f"{member.name} is now assigned to {role}")
    else:
        await ctx.send("Couldn't assign member - role doesn't exist")
    
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # Check if any banned word is in the message content
    if any(word in message.content.lower() for word in banned_words):
        await message.delete()
        await message.channel.send(f"{message.author.mention} Use of banned words detected - watch your mouth!")

    # Lets us continue handling other messages
    await bot.process_commands(message)

@tasks.loop(seconds=604800)
async def repeat_event():
    for event_data in repeating_events.values():
        ctx = event_data["ctx"]
        embed = event_data["embed"]
        view = event_data["view"]
        role_to_mention = event_data["role_to_mention"]
        
        if role_to_mention:
            await ctx.send(f"{role_to_mention.mention}", embed=embed, view=view)
        else:
            await ctx.send(embed=embed, view=view)

@bot.command()
@commands.has_role("Admins")
async def event(ctx):
    try:
        await ctx.message.delete()
    except discord.HTTPException:
        await ctx.send("Failed to delete command message...", delete_after=5)
        return

    def check_dm(m):
        return m.author == ctx.author and isinstance(m.channel, discord.DMChannel)

    async def get_property(prompt):
        try:
            await ctx.author.send(prompt)
            msg = await bot.wait_for("message", check=check_dm, timeout=60.0)
            return msg.content
        except asyncio.TimeoutError:
            await ctx.author.send("You took too long to respond. Event creation canceled.")
            return None

    # Ask for the event title
    event_title = await get_property("What would you like to title this event?")

    # Generate a list of times from noon to midnight
    mst = pytz.timezone("US/Mountain")  # Define the MST timezone
    now_mst = datetime.now(mst)
    time_options = [now_mst + timedelta(hours=i) for i in range(49)]  # Generate times for the next 48 hours

    # Convert times to Discord relative timestamps
    time_strings = [
        f"{i + 1}: <t:{int(time.mktime(option.astimezone(pytz.utc).timetuple()))}:F> (relative: <t:{int(time.mktime(option.astimezone(pytz.utc).timetuple()))}:R>)"
        for i, option in enumerate(time_options)
    ]
    time_prompt = (
        "When should this event take place? Choose one of the following options by typing the number:\n" +
        "\n".join(time_strings)
    )
    selected_index = await get_property(time_prompt)
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
    timestamp = int(time.mktime(event_time.astimezone(pytz.utc).timetuple()))  # Convert to Unix timestamp
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

        @discord.ui.button(label="O", style=discord.ButtonStyle.green)
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
        repeating_events[ctx.channel.id] = {
            "ctx": ctx,
            "embed": embed,
            "view": view,
            "role_to_mention": role_to_mention,
        }
        if not repeat_event.is_running():
            repeat_event.start()

bot.run(token, log_handler=handler, log_level=logging.DEBUG)  # pyright: ignore
