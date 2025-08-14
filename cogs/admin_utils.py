# cogs/admin_utils.py
import discord
from discord.ext import commands
from utils import settings_cache as settings




class AdminUtils(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(help="🔄 Перезагружает настройки из settings.json в кэш")
    @commands.has_permissions(administrator=True)
    async def updatesettings(self, ctx):
        settings.reload()
        await ctx.send("✅ Настройки перезагружены из файла и обновлены в кэше.")


async def setup(bot):
    await bot.add_cog(AdminUtils(bot))
