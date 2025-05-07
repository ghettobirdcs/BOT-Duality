from discord.ext import commands
import discord

class Reactions(commands.Cog):
    def __init__(self, bot, reaction_message_id, role_name):
        self.bot = bot
        self.reaction_message_id = reaction_message_id
        self.role_name = role_name

    @commands.Cog.listener()
    async def on_reaction(self, payload):
        if payload.message_id == self.reaction_message_id:
            guild = await self.bot.fetch_guild(payload.guild_id)
            member = await guild.fetch_member(payload.user_id)
            role = discord.utils.get(guild.roles, name=self.role_name)

        return role, member  # pyright: ignore

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        """Assign a role when a user reacts to a specific message."""
        role, member = await self.on_reaction(payload)

        if role and member:
            await member.add_roles(role)
            await member.send(f"Assigned you to role: [{self.role_name}]")

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        """Remove the role when a user removes their reaction."""
        role, member = await self.on_reaction(payload)

        if role and member:
            await member.remove_roles(role)
            await member.send(f"Removed you from role: [{self.role_name}]")

async def setup(bot):
    from utils.config import REACTION_MESSAGE_ID, AI_ROLE_NAME
    await bot.add_cog(Reactions(bot, REACTION_MESSAGE_ID, AI_ROLE_NAME))
