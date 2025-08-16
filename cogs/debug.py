from discord.ext import commands
import discord
import time
from utils import settings_cache as settings

class Debug(commands.Cog):
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

    @commands.hybrid_command(name="ping", with_app_command=True, description="Проверка бота и вывод ошибок")
    async def ping(self, ctx: commands.Context):
        latency_ms = round(self.bot.latency * 1000)

        embed = discord.Embed(title="📡 Ping", color=discord.Color.green())
        embed.add_field(name="Задержка", value=f"{latency_ms} ms", inline=False)

        # Ошибки загрузки когов
        if getattr(self.bot, "load_errors", []):
            errors_text = "\n".join(self.bot.load_errors)
            embed.add_field(name="⚠ Ошибки при загрузке когов", value=f"```{errors_text}```", inline=False)

        # Последняя критическая ошибка
        if getattr(self.bot, "last_critical_error", None):
            embed.add_field(name="💥 Последняя критическая ошибка", 
                            value=f"```{self.bot.last_critical_error[-1000:]}```",  # обрезка до 1000 символов
                            inline=False)

        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Debug(bot))
