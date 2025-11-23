import discord
from discord.ext import commands
from utils.permissions import check_cog_access
from constants import RMC_EMBED_COLOR


class HelpCmd(commands.Cog):
    required_access = None

    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx: commands.Context):
        allowed = await check_cog_access(ctx, self.required_access)
        if not allowed:
            raise commands.CheckFailure()
        return True

    @commands.hybrid_command(
        name="help",
        with_app_command=True,
        description="Показывает список команд"
    )
    async def help(self, ctx: commands.Context):
        embed = discord.Embed(
            title="🛠️ Список доступных команд",
            color=RMC_EMBED_COLOR
        )

        for command in self.bot.commands:
            if command.hidden:
                continue

            embed.add_field(
                name=f"!rmc {command.name}",
                value=command.description or "",
                inline=False
            )

        await ctx.send(ctx, embed)


async def setup(bot):
    await bot.add_cog(HelpCmd(bot))
