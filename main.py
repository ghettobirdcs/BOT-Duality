from huggingface_hub import InferenceClient
from datetime import datetime, timedelta
from requests import HTTPError
from discord.ui import Button, View
from discord.ext import commands
from dotenv import load_dotenv
from discord.ext import tasks
import asyncio
import discord
import logging
import json
import pytz
import os

load_dotenv()
token = os.getenv("DISCORD_TOKEN")

# AI Chatbot vars
client = InferenceClient(
    provider="novita",
    api_key=os.getenv("API_KEY")
)
conversation_history = {}

handler = logging.FileHandler(filename="discord.log", encoding="utf-8", mode="w")
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=".", intents=intents)
banned_words = ["diddy",]

repeating_events = {}

def save_repeating_events():
    # Prepare a simplified version of repeating_events for saving
    simplified_events = {}

    for channel_id, event_data in repeating_events.items():
        embed = event_data["embed"]
        role_to_mention = event_data["role_to_mention"]

        # Serialize the embed object
        embed_data = {
            "title": embed.title,
            "description": embed.description,
            "fields": [{"name": field.name, "value": field.value, "inline": field.inline} for field in embed.fields],
            "footer": embed.footer.text if embed.footer else None,
            "color": embed.color.value if embed.color else None,
        }

        # Add the serialized data to the simplified_events dictionary
        simplified_events[channel_id] = {
            "embed": embed_data,
            "role_to_mention": role_to_mention.id if role_to_mention else None,
        }

    # Save to a JSON file
    with open("repeating_events.json", "w") as f:
        json.dump(simplified_events, f, indent=4)

async def load_repeating_events():
    global repeating_events
    try:
        with open("repeating_events.json", "r") as f:
            simplified_events = json.load(f)

        # Reconstruct repeating_events
        for channel_id, event_data in simplified_events.items():
            channel = bot.get_channel(int(channel_id))
            if not channel:
                continue

            embed_data = event_data["embed"]
            embed = discord.Embed(
                title=embed_data["title"],
                description=embed_data["description"],
                color=discord.Color(embed_data["color"]) if embed_data["color"] else None,
            )
            for field in embed_data["fields"]:
                embed.add_field(name=field["name"], value=field["value"], inline=field["inline"])
            if embed_data["footer"]:
                embed.set_footer(text=embed_data["footer"])

            role_to_mention = None
            if event_data["role_to_mention"]:
                guild = channel.guild  # pyright: ignore
                role_to_mention = guild.get_role(event_data["role_to_mention"])

            repeating_events[channel_id] = {
                "ctx": None,  # ctx cannot be reconstructed
                "embed": embed,
                "view": None,  # view cannot be reconstructed
                "role_to_mention": role_to_mention,
            }

        print("Repeating events loaded successfully.")
    except FileNotFoundError:
        print("No repeating events file found. Starting fresh.")
    except Exception as e:
        print(f"Error loading repeating events: {e}")

@bot.event
async def on_ready():
    print(f"{bot.user.name} is online!")  # pyright: ignore

    # Load events when the bot starts
    await load_repeating_events()  

    # Start the loop if it's not already running
    if not repeat_event.is_running():
        repeat_event.start()

@bot.event
async def on_disconnect():
    save_repeating_events()  # Save events when the bot shuts down
    print("Repeating events saved.")

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
    elif "shut up" in message.content.lower():
        await message.channel.send(f"Shut up {message.author.mention}")

    # Lets us continue handling other messages
    await bot.process_commands(message)

@tasks.loop(seconds=604800)  # Weekly interval
async def repeat_event():
    for channel_id, event_data in repeating_events.items():
        channel = bot.get_channel(int(channel_id))
        if not channel:
            continue

        embed = event_data["embed"]
        role_to_mention = event_data["role_to_mention"]

        if role_to_mention:
            await channel.send(f"{role_to_mention.mention}", embed=embed)  # pyright: ignore
        else:
            await channel.send(embed=embed)  # pyright: ignore

@bot.command()
@commands.is_owner()  # Restrict this command to the bot owner for security
async def shutdown(ctx):
    """Gracefully shuts down the bot."""
    await ctx.send("Shutting down... Saving data.")
    save_repeating_events()  # Save repeating events to a file
    await ctx.send("Data saved. Goodbye!")
    await bot.close()  # Gracefully close the bot

# Pick personality based on user_id
def pick_personality(user_id):
    content = "You are a helpful assistant"

    if user_id in {int(os.getenv("JELLO_UID")), int(os.getenv("BRAN_UID"))}:  # pyright: ignore
        content = "You will role-play as a valley girl"
    elif user_id in {int(os.getenv("CRONCHY_UID")), int(os.getenv("BAM_UID"))}:  # pyright: ignore
        content = "You will role-play as my long-distance counter-strike girlfriend. Be very supportive and flirtatious."
    elif user_id == int(os.getenv("UPSTART_UID")):  # pyright: ignore
        content = "You will role-play as a cringe white-knight redditor trying to get me to hangout."
    elif user_id == int(os.getenv("ZIM_UID")):  # pyright: ignore
        content = "You will role-play as my horny anime girlfriend. You speak both English and Japanese."
    elif user_id == int(os.getenv("GHETTOBIRD_UID")):  # pyright: ignore
        content = "You will role-play as an ancient hermit who only speaks in tongues cursed with infinite knowledge."
    elif user_id == int(os.getenv("CLICK_UID")):  # pyright: ignore
        content = "You will role-play as a 14-year old zoomer that doom-scrools tiktok every hour of every day. The kind of snotty-nosed kid that asks what games you have on your phone."

    return content

async def process_ai_response(user_id, conversation_history, status_message, ctx):
    """Handles the AI call and processes the response."""
    # Send the conversation history to the AI model
    completion = await asyncio.to_thread(
        client.chat.completions.create,
        model="deepseek-ai/DeepSeek-V3-0324",
        messages=conversation_history[user_id],
    )

    # Get the AI's reply
    ai_reply = completion["choices"][0]["message"]["content"]

    # Add the AI's reply to the conversation history
    conversation_history[user_id].append({"role": "assistant", "content": ai_reply})

    # Split the AI's reply into chunks of less than 2000 characters
    chunks = [ai_reply[i:i + 2000] for i in range(0, len(ai_reply), 2000)]

    # Send each chunk as a separate message
    for i, chunk in enumerate(chunks):
        if i == 0:
            # Edit the initial "working..." message with the first chunk
            await status_message.edit(content=chunk)
        else:
            # Send subsequent chunks as new messages
            await ctx.send(chunk)

@bot.command()
async def chat(ctx, *, user_message: str):
    """Chat with the AI chatbot."""
    user_id = ctx.author.id  # Unique ID for the user

    # Initialize conversation history for the user if not already present
    if user_id not in conversation_history:
        conversation_history[user_id] = [
            {
                "role": "system",
                "content": pick_personality(user_id)
            }
        ]

    # Add the user's message to the conversation history
    conversation_history[user_id].append({"role": "user", "content": user_message})

    # Send the initial "Working..." message
    status_message = await ctx.send("working...")
    ai_done = False

    # Define the animation task
    async def animate_working():
        nonlocal ai_done # Ensure the flag is properly updated in the nested function
        working_states = ["working...", "working", "working.", "working.."]
        i = 0
        while not ai_done:  # Keep animating until the AI processing is done
            new_state = working_states[i % len(working_states)]
            await status_message.edit(content=new_state)
            i += 1
            await asyncio.sleep(0.5)

    animation_task = asyncio.create_task(animate_working())

    try:
        # Attempt to process the AI response
        await process_ai_response(user_id, conversation_history, status_message, ctx)

    except HTTPError as e:
        ai_done = True
        await animation_task

        if e.response.status_code == 402:
            # Notify the user about the delay
            for remaining in range(60, 0, -1):  # Countdown from 60 to 1
                await status_message.edit(content=f"Slow down!\nInference limit reached; retrying in {remaining} seconds...")
                await asyncio.sleep(1)  # Wait for 1 second

            try:
                # Retry the AI call
                await process_ai_response(user_id, conversation_history, status_message, ctx)
            except Exception as retry_error:
                # Handle errors during the retry
                await status_message.edit(content=f"Retry failed: {retry_error}", delete_after=10)
        else:
            # Handle other HTTP errors
            await status_message.edit(content=f"Unknown HTTP Error: {e}", delete_after=10)

    except Exception as e:
        # Stop the animation in case of an error
        ai_done = True
        await animation_task

        # Handle errors (e.g., API issues)
        await status_message.edit(content=f"Exception when contacting AI: {e}", delete_after=5)


@bot.command()
async def clear(ctx):
    user_id = ctx.author.id
    if user_id in conversation_history:
        del conversation_history[user_id]
    await ctx.send("Conversation history cleared.")

@bot.command()
@commands.is_owner() # Command for the bot owner to clear ALL history for every user
async def clearall(ctx):
    conversation_history.clear()
    await ctx.send("ALL Conversation history cleared for every user.")

@bot.command()
@commands.has_role("Admins")
async def event(ctx):
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
            msg = await bot.wait_for("message", check=check_dm, timeout=60.0)
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
        repeating_events[ctx.channel.id] = {
            "ctx": ctx,
            "embed": embed,
            "view": view,
            "role_to_mention": role_to_mention,
        }

bot.run(token, log_handler=handler, log_level=logging.DEBUG)  # pyright: ignore
