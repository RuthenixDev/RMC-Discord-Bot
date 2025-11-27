import discord
from discord.ext import commands
from utils import settings_cache as settings
from utils.permissions import check_cog_access




class AdminUtils(commands.Cog):
    required_access = "admin"
    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx: commands.Context):
        allowed = await check_cog_access(ctx, self.required_access)
        if not allowed:
            raise commands.CheckFailure()
        return True

    @commands.hybrid_command(
        name="updatesettings",
        with_app_command=True,  # регистрирует как slash
        description="Принудительно перезагружает settings.json"
    )
    async def updatesettings(self, ctx: commands.Context):
        settings.reload_settings()

        embed = discord.Embed(
            description="✅ Настройки перезагружены из файла и обновлены в кэше.",
            color=discord.Color.green()
        )

        if ctx.interaction:
            await ctx.interaction.response.send_message(embed=embed)
        else:
            await ctx.reply(embed=embed)


async def setup(bot):
    await bot.add_cog(AdminUtils(bot))
