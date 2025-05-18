from discord.ext import commands
from utils.file_utils import add_to_conversation
from utils.ai_utils import get_ai
from utils.config import is_in_allowed_channel
from utils.ai_utils import call_ai_api, split_message
import asyncio

class ChatBot(commands.Cog):
    def __init__(self, bot, chat_lock):
        self.bot = bot
        self.chat_lock = chat_lock
        self.conversation_history = {}
        self.user_personalities = {}

    @commands.command()
    @is_in_allowed_channel()
    async def set_ai(self, ctx, *, personality: str):
        user_id = ctx.author.id
        # Set new personality
        self.user_personalities[user_id] = personality

        # Clear the user's conversation history
        if user_id in self.conversation_history:
            del self.conversation_history[user_id]

        await ctx.send(f"Your personality has been set to: {personality}. Your conversation history has been cleared.")

    @commands.command()
    @commands.is_owner()
    @is_in_allowed_channel()
    async def clear_ai(self, ctx):
        self.user_personalities.clear()
        await ctx.send("ALL Personalities wiped for every user.")

    @commands.command()
    @is_in_allowed_channel()
    async def clear(self, ctx):
        user_id = ctx.author.id
        if user_id in self.conversation_history:
            del self.conversation_history[user_id]
        await ctx.send("Conversation history cleared.")

    @commands.command()
    @is_in_allowed_channel()
    @commands.is_owner() # Command for the bot owner to clear ALL history for every user
    async def clearall(self, ctx):
        self.conversation_history.clear()
        await ctx.send("ALL Conversation history cleared for every user.")

    async def process_ai_response(self, ctx):
        user_id = ctx.author.id
        # Prepare the payload for the AI API
        payload = {
            "model": "huihui_ai/llama3.2-abliterate",
            "messages": self.conversation_history[user_id],
            "stream": False
        }

        # Send the initial "Working..." message
        status_message = await ctx.send("working...")

        try:
            # Call the AI API
            api_url = "http://127.0.0.1:11434/api/chat"
            response_data = call_ai_api(api_url, payload)

            if not response_data:
                await ctx.send("Failed to get a response from the AI.")
                return

            # Extract the assistant's reply from the response
            ai_reply = response_data["message"]["content"]
            print(f"\n\n|------------------\n| AI reply: {ai_reply}\n|------------------")

            # Add the AI's reply to the conversation history
            assistant_message = {"role": "assistant", "content": ai_reply}
            add_to_conversation(self.conversation_history, user_id, assistant_message)

            # Split the AI's reply into chunks of less than 2000 characters
            chunks = split_message(ai_reply)

            # Send each chunk as a separate message
            if chunks:
                # Edit the initial "working..." message with the first chunk
                await status_message.edit(content=chunks[0])

            # Send subsequent chunks as new messages
            for chunk in chunks[1:]:
                await ctx.send(chunk)
        except Exception as e:
            print(f"[ERROR] Unknown exception:\n{e}")

    @commands.command()
    @is_in_allowed_channel()
    async def chat(self, ctx, *, user_message: str):
        user_id = ctx.author.id
        # Add the system message to the conversation history if it's the user's first message
        if user_id not in self.conversation_history:
            system_message = {
                "role": "system",
                "content": get_ai(self.user_personalities, user_id)
            }
            add_to_conversation(self.conversation_history, user_id, system_message)

        # Add the user's message to the conversation history
        user_message_entry = {"role": "user", "content": user_message}
        print(f"\n\n|------------------\n| message: {user_message}\n|------------------")

        # print(f"\n\n[DEBUG] Conversation history:\n{conversation_history}\n\n")
        add_to_conversation(self.conversation_history, user_id, user_message_entry)

        # Process the AI response
        async with self.chat_lock:  # Prevent overlapping commands
            await self.process_ai_response(ctx)

async def setup(bot):
    chat_lock = asyncio.Lock()
    await bot.add_cog(ChatBot(bot, chat_lock))  # pyright: ignore
