from discord.ext import commands

class MessageHandler(commands.Cog):
    def __init__(self, bot, banned_words):
        self.bot = bot
        self.banned_words = banned_words

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.bot.user:
            return

        # Check for banned words
        if any(word in message.content.lower() for word in self.banned_words):
            await message.delete()
            await message.channel.send(f"{message.author.mention} Use of banned words detected - watch your mouth!")
        elif "shut up" in message.content.lower():
            await message.channel.send(f"Shut up {message.author.mention}")

        # Process other commands
        await self.bot.process_commands(message)

async def setup(bot):
    banned_words = ["diddy", ]
    await bot.add_cog(MessageHandler(bot, banned_words))
