# cogs/admin_utils.py
import discord
from discord.ext import commands
from utils import settings_cache as settings




class AdminUtils(commands.Cog):
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
        name="updatesettings",
        with_app_command=True,  # регистрирует как slash
        description="Принудительно перезагружает settings.json"
    )
    async def updatesettings(self, ctx):
        settings.reload_settings()
        await ctx.send("✅ Настройки перезагружены из файла и обновлены в кэше.")


async def setup(bot):
    await bot.add_cog(AdminUtils(bot))
