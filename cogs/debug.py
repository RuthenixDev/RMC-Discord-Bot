from discord.ext import commands
import discord,json,io
from utils.permissions import check_cog_access
from utils import settings_cache as settings
from constants import MAX_MESSAGE,RMC_EMBED_COLOR



class Debug(commands.Cog):
    required_access = "admin"
    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx: commands.Context):
        allowed = await check_cog_access(ctx, self.required_access)
        if not allowed:
            raise commands.CheckFailure()
        return True

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

        await ctx.reply(embed=embed)

    @commands.hybrid_command(name="showjson", with_app_command=True, description="Вывести содержимое settings.json")
    async def showjson(self, ctx: commands.Context):
        # Загрузка настроек из кэша или файла
        data = settings.load_settings()

        if not data:
            await ctx.reply("❌ Файл `settings.json` пуст или отсутствует.")
            return

        # Форматируем красиво
        pretty_json = json.dumps(data, indent=4, ensure_ascii=False)

        if len(pretty_json) <= MAX_MESSAGE:
            embed=discord.Embed( description="```json\n" + pretty_json + "\n```", color=RMC_EMBED_COLOR )
            await ctx.reply(embed=embed)
            return

        file_bytes = io.BytesIO(pretty_json.encode("utf-8"))
        embed=discord.Embed( description="⚠️ Содержимое файла слишком большое для отправки в сообщении, отправляю как файл.", color=RMC_EMBED_COLOR )
        await ctx.reply(
            embed=embed,
            file=discord.File(file_bytes, filename="settings.json")
        )

async def setup(bot):
    await bot.add_cog(Debug(bot))
