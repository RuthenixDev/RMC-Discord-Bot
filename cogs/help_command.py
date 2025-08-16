import discord
from discord.ext import commands
from utils import settings_cache as settings


class HelpCmd(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx: commands.Context):
        data = settings.load_settings()
        admin_roles = data.get("admin_roles", [])

        if ctx.author.guild_permissions.administrator:
            return True
        if any(str(role.id) in admin_roles for role in ctx.author.roles):
            return True

        raise commands.CheckFailure("❌ У вас нет прав для этого раздела команд. Если вы считаете это ошибкой, свяжитесь с администратором.")

    @commands.hybrid_command(
        name="help",
        with_app_command=True,  # регистрирует как slash
        description="Показывает список команд"
    )
    async def help(self, ctx):
        embed = discord.Embed(title="🛠️ Список доступных команд", color=0x00ccff)
        for command in self.bot.commands:
            if command.hidden:
                continue
            embed.add_field(name=f"!rmc {command.name}", value=command.help or "", inline=False)
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(HelpCmd(bot))
