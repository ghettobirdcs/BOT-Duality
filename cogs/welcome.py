import discord
from discord.ext import commands

class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member):
        # TODO: See if we can get 'general' channel without hardcoded id
        general = self.bot.get_channel(1197071765927637084)
        await general.send(f"Welcome to Duality, {member.mention}!")

async def setup(bot):
    await bot.add_cog(Welcome(bot))
