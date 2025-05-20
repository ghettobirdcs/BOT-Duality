import discord
from discord.ext import commands

class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member):
        guild = member.guild
        role = discord.utils.get(guild.roles, name="Prospects")
        general = self.bot.get_channel(1197071765927637084)

        if role:
            await member.add_roles(role)
            await general.send(f"Welcome to Duality, {member.name}! You have been assigned the {role.name} role.")
        else:
            await general.send("Welcome to Duality! However, the 'Prospects' role could not be assigned because it doesn't exist.")

async def setup(bot):
    await bot.add_cog(Welcome(bot))