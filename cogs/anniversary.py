import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, date, timezone, timedelta
from constants import RMC_EMBED_COLOR

class Anniversary(commands.Cog):
    """Cog для просмотра даты годовщины сервера"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(
        name="anniversary",
        with_app_command=True,
        description="Посмотреть дату годовщины сервера."
    )
    async def anniversary(self, ctx: commands.Context):
        """Показать дату годовщины сервера."""
        time_now = datetime.now(timezone.utc).date()
        server_created = ctx.guild.created_at.date()
        server_date_ftd = server_created.strftime("%d.%m.%Y")
        anniversary_this_year = date(time_now.year, server_created.month, server_created.day)
        
        if anniversary_this_year >= time_now:
            anniversary_next = anniversary_this_year
        else:
            anniversary_next = date(time_now.year + 1, server_created.month, server_created.day)
        
        days_left = (anniversary_next - time_now).days
        anniversary_next_ftd = anniversary_next.strftime("%d.%m.%Y")
        embed = discord.Embed(
            title="🎉 Годовщина сервера",
            color=RMC_EMBED_COLOR,
            timestamp=discord.utils.utcnow()
        )
        
        embed.add_field(
            name="📅 Дата создания сервера",
            value=f"`{server_date_ftd}`",
            inline=True
        )
        
        embed.add_field(
            name="🎂 Следующая годовщина",
            value=f"`{anniversary_next_ftd}`",
            inline=True
        )
        
        embed.add_field(
            name="⏳ Дней до годовщины",
            value=f"`{days_left}` дней",
            inline=False
        )
        if days_left == 0:
            message = "🎊 **Сегодня годовщина сервера! Поздравляем!** 🎊"
        elif days_left == 1:
            message = "Завтра годовщина сервера! Приготовьтесь к празднику! 🎂"
        elif days_left < 7:
            message = "Скоро годовщина! Осталось совсем немного! ⏰"
        else:
            message = "Ждем с нетерпением следующей годовщины! 📅"
        
        embed.add_field(
            name="💬",
            value=message,
            inline=False
        )
        
        embed.set_footer(text=f"Серверу исполнится {time_now.year - server_created.year + (1 if anniversary_this_year < time_now else 0)} лет")
        
        await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(Anniversary(bot))