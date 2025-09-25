import discord
from typing import Optional
from discord import app_commands
from discord.ext import commands
from constants import RMC_EMBED_COLOR

class Rules(commands.Cog):
    """Cog для просмотра правил сервера."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.rule_names = {
            "1": "Краши и фишинговые ссылки",
            "2": "Реклама", 
            "3": "NSFW шок-контент",
            "4": "Оскорбления",
            "5": "Критика",
            "6": "Обсуждение политики",
            "7": "Спам и флуд",
            "8": "Призывы к насилию",
            "9": "Акции от имени РМК",
            "10": "Выдача себя за другое лицо",
            "11": "Поиск неточностей в правилах",
            "12": "О других аккаунтах участника",
            "13": "О критике администрации",
            "14": "О личных сообщениях администрации",
            "15": "О действиях администрации",
            "basis": "Право администрации на самостоятельное принятие решений",
            "link": "Ссылка на полные правила"
        }

    @commands.hybrid_command(
        name="rule",
        with_app_command=True,
        description="Посмотреть пункт правил сервера."
    )
    @app_commands.describe(rule_id="Выберите пункт правил")
    @app_commands.choices(rule_id=[
        app_commands.Choice(name="Справка о команде", value="help"),
        app_commands.Choice(name="Краши и фишинговые ссылки", value="1"),
        app_commands.Choice(name="Реклама", value="2"),
        app_commands.Choice(name="NSFW шок-контент", value="3"),
        app_commands.Choice(name="Оскорбления", value="4"),
        app_commands.Choice(name="Критика", value="5"),
        app_commands.Choice(name="Обсуждение политики", value="6"),
        app_commands.Choice(name="Спам и флуд", value="7"),
        app_commands.Choice(name="Призывы к насилию", value="8"),
        app_commands.Choice(name="Акции от имени РМК", value="9"),
        app_commands.Choice(name="Выдача себя за другое лицо", value="10"),
        app_commands.Choice(name="Поиск неточностей в правилах", value="11"),
        app_commands.Choice(name="О других аккаунтах участника", value="12"),
        app_commands.Choice(name="О критике администрации", value="13"),
        app_commands.Choice(name="О личных сообщениях администрации", value="14"),
        app_commands.Choice(name="О действиях администрации", value="15"),
        app_commands.Choice(name="Право администрации на самостоятельное принятие решений", value="basis"),
        app_commands.Choice(name="Ссылка на полные правила", value="link")
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
            embed = discord.Embed(
                title="📖 Справка по команде rule",
                description="Доступные пункты правил:",
                color=RMC_EMBED_COLOR
            )
            
            for i in range(1, 16):
                rule_key = str(i)
                rule_name = self.rule_names.get(rule_key, f"Правило {i}")
                embed.add_field(
                    name=f"📜 {rule_name}",
                    value=f"Используйте `!rmc rule {i}` или `/rule {i}`",
                    inline=True  
                )
            
            embed.add_field(
                name="⚖️ " + self.rule_names.get("basis", "Основа основ"),
                value="`!rmc rule basis` или `/rule basis`",
                inline=True
            )
            
            embed.add_field(
                name="🔗 " + self.rule_names.get("link", "Ссылка на правила"),
                value="`!rmc rule link` или `/rule link`",
                inline=True
            )
            
            embed.set_footer(text="Выберите нужный пункт для просмотра подробного описания")
            await ctx.send(embed=embed)
            return

        answer = rules_map.get(rule_id)
        if answer:
            if rule_id.isdigit():
                rule_name = self.rule_names.get(rule_id, f"Правило {rule_id}")
                title = f"📜 {rule_name}"
                color = RMC_EMBED_COLOR
            elif rule_id == "basis":
                rule_name = self.rule_names.get("basis", "Основа основ")
                title = f"⚖️ {rule_name}"
                color = RMC_EMBED_COLOR
            else:  
                rule_name = self.rule_names.get("link", "Ссылка на правила")
                title = f"🔗 {rule_name}"
                color = RMC_EMBED_COLOR
            
            embed = discord.Embed(
                title=title,
                description=answer,
                color=color,
                timestamp=discord.utils.utcnow()
            )
            
            if rule_id.isdigit():
                embed.set_footer(text="Соблюдайте правила сервера!")
            elif rule_id == "basis":
                embed.set_footer(text="Администрация оставляет за собой право трактовать правила")
            else:
                embed.set_footer(text="Полная версия правил доступна по ссылке")
            
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="❌ Ошибка",
                description=f"Пункта `{rule_id}` нет в правилах!",
                color=RMC_EMBED_COLOR
            )
            
            available_rules = []
            for i in range(1, 16):
                rule_key = str(i)
                rule_name = self.rule_names.get(rule_key, f"Правило {i}")
                available_rules.append(f"• {rule_name} (`{i}`)")
            
            available_rules.append(f"• {self.rule_names.get('basis', 'Основа основ')} (`basis`)")
            available_rules.append(f"• {self.rule_names.get('link', 'Ссылка на правила')} (`link`)")
            
            embed.add_field(
                name="Доступные пункты",
                value="\n".join(available_rules),
                inline=False
            )
            embed.set_footer(text="Используйте !rmc rule help для справки")

            if ctx.interaction is not None:
                await ctx.send(embed=embed, ephemeral=True)
            else:
                await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(Rules(bot))
