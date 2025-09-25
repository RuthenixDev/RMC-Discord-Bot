import discord
from typing import Optional
from discord import app_commands
from discord.ext import commands
from main import RMC_EMBED_COLOR

class Rules(commands.Cog):
    """Cog для просмотра правил сервера."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(
        name="rule",
        with_app_command=True,
        description="Посмотреть пункт правил сервера."
    )
    @app_commands.describe(rule_id="Выберите пункт правил")
    @app_commands.choices(rule_id=[
        app_commands.Choice(name="help", value="help"),
        app_commands.Choice(name="1", value="1"),
        app_commands.Choice(name="2", value="2"),
        app_commands.Choice(name="3", value="3"),
        app_commands.Choice(name="4", value="4"),
        app_commands.Choice(name="5", value="5"),
        app_commands.Choice(name="6", value="6"),
        app_commands.Choice(name="7", value="7"),
        app_commands.Choice(name="8", value="8"),
        app_commands.Choice(name="9", value="9"),
        app_commands.Choice(name="10", value="10"),
        app_commands.Choice(name="11", value="11"),
        app_commands.Choice(name="12", value="12"),
        app_commands.Choice(name="13", value="13"),
        app_commands.Choice(name="14", value="14"),
        app_commands.Choice(name="15", value="15"),
        app_commands.Choice(name="basis", value="basis"),
        app_commands.Choice(name="link", value="link")
    ])
    async def rule(self, ctx: commands.Context, rule_id: Optional[str] = None):
        """Показать пункт правил по номеру или help."""

        rules_map = {
            "help": "Доступно для ввода: `help`, пункты правил 1-15, `basis`, `link`.",
            "1": "1. Любые попытки взлома, краша, рейда сервера, размещения фишинговых ссылок, вредоносного ПО и прочих сомнительных материалов караются перманентным баном.",
            "2": "2. Запрещена любая реклама без разрешения администрации сервера.",
            "3": "3. Запрещены шок-контент, NSFW-контент, насилие и прочий контент, нарушающий моральные нормы. За подобные действия обычно следует бан.",
            "4": "4. Запрещены систематические оскорбления, угрозы в адрес участников, модеров и проектов.",
            "5": "5. Конструктивная критика приветствуется, необоснованные агрессивные высказывания будут модерироваться.",
            "6": "6. Политические, религиозные дискуссии запрещены повсеместно, кроме канала `полит-чат` с ролью `Диванный политик`. Если разговор сложился таким образом или на подобную тему, то следует перейти в данный канал. Все остальные правила в данном канале сохраняют свою силу.",
            "7": "7. Запрещено спамить, флудить, попрошайничать, капсить без меры. Запрещён и является более тяжким проступком необоснованный массовый пинг.",
            "8": "8. Запрещены провокации и призывы к насилию, расизму, терроризму и т.д.",
            "9": "9. Запрещены любые акции от имени РМК без ведома и согласия администрации РМК.",
            "10": "10. Запрещено выдавать себя за другого человека без его ведома и согласия. Запрещено распространение личной информации других людей, а также личных сведений, порочащих их.",
            "11": "11. Не приветствуется намеренный поиск и использование лазеек в правилах. Любые махинации с толкованием текста правил не будут рассматриваться как аргумент.",
            "12": "12. Наказание распространяется на все аккаунты участника.",
            "13": "13. Каждый член администрации не обязан терпеть критику и оскорбления в адрес сервера или администрации.",
            "14": "14. Администрация не обязана отвечать на личные сообщения.",
            "15": "15. Действия администрации обсуждению не подлежат.",
            "basis": "Администрация имеет право самой выбирать меру наказания в зависимости от тяжести нарушения. Администрация сохраняет за собой право выносить наказание без объяснения причины и отсылки на определённые правила, а также не применять наказания в тех случаях, когда посчитает это нужным.",
            "link": "https://discord.com/channels/1283116690678485125/1283118892880887868/1331716635257606184"
        }

        if rule_id is None or rule_id == "help":
            # Embed для справки
            embed = discord.Embed(
                title="📖 Справка по команде rule",
                description="Доступные пункты правил:",
                color=RMC_EMBED_COLOR
            )
            
            # Добавляем все доступные пункты
            for i in range(1, 16):
                embed.add_field(
                    name=f"Правило {i}",
                    value=f"Используйте `!rmc rule {i}` или `/rule {i}`",
                    inline=True
                )
            
            embed.add_field(
                name="Основа основ",
                value="`!rmc rule basis` или `/rule basis`",
                inline=False
            )
            
            embed.add_field(
                name="Ссылка на правила",
                value="`!rmc rule link` или `/rule link`",
                inline=False
            )
            
            embed.set_footer(text="Выберите нужный пункт для просмотра")
            await ctx.send(embed=embed)
            return

        answer = rules_map.get(rule_id)
        if answer:
            # Embed для конкретного правила
            if rule_id.isdigit():
                title = f"📜 Правило {rule_id}"
                color = RMC_EMBED_COLOR  # Красный для правил
            elif rule_id == "basis":
                title = "⚖️ Основа основ"
                color = RMC_EMBED_COLOR  # Оранжевый
            else:  # link
                title = "🔗 Ссылка на правила"
                color = RMC_EMBED_COLOR  # Фиолетовый
            
            embed = discord.Embed(
                title=title,
                description=answer,
                color=color,
                timestamp=discord.utils.utcnow()
            )
            
            # Добавляем разные футеры в зависимости от типа
            if rule_id.isdigit():
                embed.set_footer(text="Соблюдайте правила сервера!")
            elif rule_id == "basis":
                embed.set_footer(text="Администрация оставляет за собой право трактовать правила")
            else:
                embed.set_footer(text="Полная версия правил доступна по ссылке")
            
            await ctx.send(embed=embed)
        else:
            # Embed для ошибки
            embed = discord.Embed(
                title="❌ Ошибка",
                description=f"Пункта `{rule_id}` нет в правилах!",
                color=RMC_EMBED_COLOR
            )
            embed.add_field(
                name="Доступные пункты",
                value="1-15, basis, link",
                inline=False
            )
            embed.set_footer(text="Используйте !rmc rule help для справки")
            await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(Rules(bot))
