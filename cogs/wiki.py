import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Select, View
from constants import RMC_EMBED_COLOR
from utils.permissions import check_cog_access

class WikiMainSelect(Select):
    """Выпадающее меню для выбора статьи с поддержкой пагинации."""
    def __init__(self, wiki_map: dict, current_page: int, total_pages: int):
        self.wiki_map = wiki_map
        self.current_page = current_page
        self.total_pages = total_pages

        keys = list(wiki_map.keys())
        start_idx = current_page * 24
        end_idx = start_idx + 24
        page_keys = keys[start_idx:end_idx]

        options = []
        for key in page_keys:
            art = wiki_map[key]
            label_text = f"{art['title']} ({key.lower()})"
            options.append(discord.SelectOption(
                label=label_text[:100],
                description=art["desc"][:100],
                emoji=art.get("emoji", "📖"),
                value=key
            ))

        if total_pages > 1:
            next_page = (current_page + 1) % total_pages
            options.append(discord.SelectOption(
                label=f"▶️ Переключить страницу ({next_page + 1}/{total_pages})",
                description="Показать следующие статьи",
                emoji="🔄",
                value="__page_next__"
            ))

        super().__init__(
            placeholder=f"Выберите статью (Стр. {current_page + 1}/{total_pages})...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        val = self.values[0]
        if val == "__page_next__":
            self.view.current_page = (self.view.current_page + 1) % self.total_pages
            await self.view.update_message(interaction)
        else:
            self.view.selected_article = val
            self.view.selected_subsection = None
            await self.view.update_message(interaction)

class WikiSubSelect(Select):
    """Выпадающее меню подпунктов статьи с кнопкой возврата в главное меню."""
    def __init__(self, subsections: list):
        options = []
        for idx, sub in enumerate(subsections):
            options.append(discord.SelectOption(
                label=sub["title"][:100],
                description=sub.get("desc", "")[:100],
                emoji="📄",
                value=f"sub_{idx}"
            ))

        # Последний пункт для возврата в общее меню
        options.append(discord.SelectOption(
            label="🏠 Вернуться в главное меню",
            description="Вернуться к общему списку статей",
            emoji="🏠",
            value="__return_main__"
        ))

        super().__init__(
            placeholder="Выберите подпункт статьи...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        val = self.values[0]
        if val == "__return_main__":
            self.view.selected_article = None
            self.view.selected_subsection = None
            await self.view.update_message(interaction)
        else:
            sub_idx = int(val.split("_")[1])
            self.view.selected_subsection = sub_idx
            await self.view.update_message(interaction)

class WikiView(View):
    """View управляющий состоянием интерактивной википедией."""
    def __init__(self, wiki_map: dict, author: discord.User | discord.Member):
        super().__init__(timeout=600)
        self.wiki_map = wiki_map
        self.author = author
        self.current_page = 0
        self.selected_article = None
        self.selected_subsection = None
        self.message = None
        self.update_components()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Вы не можете использовать это меню.", ephemeral=True)
            return False
        return True

    def get_total_pages(self) -> int:
        return (len(self.wiki_map) - 1) // 24 + 1

    def build_main_embed(self) -> discord.Embed:
        total_articles = len(self.wiki_map)
        total_pages = self.get_total_pages()
        embed = discord.Embed(
            title="📚 Википедия по моддингу Hearts of Iron IV",
            description=(
                "Добро пожаловать в справочный центр по моддингу HOI4!\n\n"
                "Используйте **выпадающее меню ниже**, чтобы выбрать интересующую вас статью и ознакомиться с её содержанием и подпунктами.\n\n"
                f"**Всего доступно статей:** `{total_articles}` | **Страница:** `{self.current_page + 1}/{total_pages}`"
            ),
            color=RMC_EMBED_COLOR,
            timestamp=discord.utils.utcnow()
        )
        embed.set_footer(text="Для выбора статьи или смены страницы используйте меню ниже ⬇️")
        return embed

    def build_article_embed(self) -> discord.Embed:
        if not self.selected_article or self.selected_article not in self.wiki_map:
            return self.build_main_embed()

        art = self.wiki_map[self.selected_article]
        subsections = art.get("subsections", [])

        desc_parts = [art["desc"]]

        if subsections:
            desc_parts.append("\n**📌 Доступные подпункты и разделы статьи:**")
            for idx, sub in enumerate(subsections):
                is_selected = (self.selected_subsection == idx)
                prefix = "👉 " if is_selected else "• "
                desc_parts.append(f"{prefix}[**{sub['title']}**]({sub['url']}) — {sub['desc']}")

        desc_parts.append(f"\n🔗 **[Перейти к полной статье на Wiki]({art['url']})**")

        embed = discord.Embed(
            title=f"{art.get('emoji', '📖')} {art['title']} ({self.selected_article.lower()})",
            description="\n".join(desc_parts),
            color=RMC_EMBED_COLOR,
            timestamp=discord.utils.utcnow()
        )

        if self.selected_subsection is not None and 0 <= self.selected_subsection < len(subsections):
            sub = subsections[self.selected_subsection]
            embed.add_field(
                name=f"📄 Выбранный подпункт: {sub['title']}",
                value=f"{sub['desc']}\n🔗 **[Открыть подпункт]({sub['url']})**",
                inline=False
            )

        embed.set_footer(text="Для перехода к другим подпунктам или возврата выберите пункт из меню ниже ⬇️")
        return embed

    def update_components(self):
        self.clear_items()
        if self.selected_article is None:
            self.add_item(WikiMainSelect(self.wiki_map, self.current_page, self.get_total_pages()))
        else:
            art_data = self.wiki_map[self.selected_article]
            self.add_item(WikiSubSelect(art_data.get("subsections", [])))

    async def update_message(self, interaction: discord.Interaction):
        self.update_components()
        if self.selected_article is None:
            embed = self.build_main_embed()
        else:
            embed = self.build_article_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

class Wiki(commands.Cog):
    required_access = None
    """Cog для просмотра страниц Вики"""

    async def cog_check(self, ctx: commands.Context):
        allowed = await check_cog_access(ctx, self.required_access)
        if not allowed:
            raise commands.CheckFailure()
        return True

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.wiki_map = {
            "map": {
                "title": "Создание и редактирование карты",
                "emoji": "🗺️",
                "url": "https://hoi4.paradoxwikis.com/Map_modding",
                "desc": "Основное руководство по созданию и редактированию карты, штатов и провинций.",
                "subsections": [
                    {"title": "State modding", "url": "https://hoi4.paradoxwikis.com/State_modding", "desc": "Моддинг штатов, регионов и населения."},
                    {"title": "Supply areas", "url": "https://hoi4.paradoxwikis.com/Supply_areas_modding", "desc": "Моддинг зон снабжения и инфраструктуры."}
                ]
            },
            "country": {
                "title": "Создание стран",
                "emoji": "🚩",
                "url": "https://hoi4.paradoxwikis.com/Country_creation",
                "desc": "Создание новых государств, тегов, правителей и истории.",
                "subsections": [
                    {"title": "Cosmetic tags", "url": "https://hoi4.paradoxwikis.com/Cosmetic_tag_modding", "desc": "Динамические косметические теги стран."},
                    {"title": "History & OOB", "url": "https://hoi4.paradoxwikis.com/Country_creation#History", "desc": "История страны и расстановка стартовых войск."}
                ]
            },
            "data_structures": {
                "title": "Структуры данных",
                "emoji": "📊",
                "url": "https://hoi4.paradoxwikis.com/Data_structures",
                "desc": "Массивы, переменные, глобальные флаги и структуры данных в Paradox Script.",
                "subsections": []
            },
            "effect": {
                "title": "Эффекты (Effects)",
                "emoji": "⚡",
                "url": "https://hoi4.paradoxwikis.com/Effect",
                "desc": "Справочник эффектов, изменяющих состояние игры, стран и юнитов.",
                "subsections": []
            },
            "defines": {
                "title": "Игровые константы (Defines)",
                "emoji": "⚙️",
                "url": "https://hoi4.paradoxwikis.com/Defines",
                "desc": "Параметры и числовые константы игрового движка в NDefines.",
                "subsections": []
            },
            "scopes": {
                "title": "Области видимости (Scopes)",
                "emoji": "🎯",
                "url": "https://hoi4.paradoxwikis.com/Scopes",
                "desc": "Контексты исполнения скриптов (ROOT, FROM, PREV, THIS, EVERY_COUNTRY и др.).",
                "subsections": []
            },
            "on_actions": {
                "title": "Триггеры действий (On Actions)",
                "emoji": "🔔",
                "url": "https://hoi4.paradoxwikis.com/On_actions",
                "desc": "События и скрипты, вызываемые игрой при выполнении конкретных действий.",
                "subsections": []
            },
            "achievement": {
                "title": "Моддинг достижений",
                "emoji": "🏆",
                "url": "https://hoi4.paradoxwikis.com/Achievement_modding",
                "desc": "Создание пользовательских достижений и условий их получения.",
                "subsections": []
            },
            "autonomy": {
                "title": "Уровни автономии",
                "emoji": "📜",
                "url": "https://hoi4.paradoxwikis.com/Autonomy_state_modding",
                "desc": "Настройка уровней зависимых государств и видов марионеток.",
                "subsections": []
            },
            "building": {
                "title": "Постройки и здания",
                "emoji": "🏗️",
                "url": "https://hoi4.paradoxwikis.com/Building_modding",
                "desc": "Создание новых видов зданий, фабрик, укреплений и инфраструктуры.",
                "subsections": []
            },
            "cosmetic_tag": {
                "title": "Косметические теги",
                "emoji": "🏷️",
                "url": "https://hoi4.paradoxwikis.com/Cosmetic_tag_modding",
                "desc": "Настройка альтернативных названий, флагов и цветов для государств.",
                "subsections": []
            },
            "division": {
                "title": "Моддинг дивизий",
                "emoji": "🎖️",
                "url": "https://hoi4.paradoxwikis.com/Division_modding",
                "desc": "Настройка шаблонов дивизий, состава и стартовых сухопутных сил.",
                "subsections": []
            },
            "equipment": {
                "title": "Снаряжение и техника",
                "emoji": "⚔️",
                "url": "https://hoi4.paradoxwikis.com/Equipment_modding",
                "desc": "Создание типов вооружения, танков, самолетов и кораблей.",
                "subsections": []
            },
            "event": {
                "title": "События (Ивенты)",
                "emoji": "📰",
                "url": "https://hoi4.paradoxwikis.com/Event_modding",
                "desc": "Создание событий для стран, новостных ивентов и диалоговых окон.",
                "subsections": [
                    {"title": "Country events", "url": "https://hoi4.paradoxwikis.com/Event_modding#Country_event", "desc": "Обычные события для конкретной страны."},
                    {"title": "News events", "url": "https://hoi4.paradoxwikis.com/Event_modding#News_event", "desc": "Глобальные новостные сообщения."}
                ]
            },
            "ideology": {
                "title": "Моддинг идеологий",
                "emoji": "⚖️",
                "url": "https://hoi4.paradoxwikis.com/Ideology_modding",
                "desc": "Создание политических идеологий, суб-идеологий и правил фракций.",
                "subsections": []
            },
            "mio": {
                "title": "Военно-промышленные организации (МИО)",
                "emoji": "🏭",
                "url": "https://hoi4.paradoxwikis.com/Military_industrial_organization_modding",
                "desc": "Настройка концернов, производительского оборудования и древа МИО.",
                "subsections": []
            },
            "decision": {
                "title": "Решения и категории",
                "emoji": "☑️",
                "url": "https://hoi4.paradoxwikis.com/Decision_modding",
                "desc": "Создание вкладки решений, категорий, таймеров и миссий.",
                "subsections": []
            },
            "resources": {
                "title": "Стратегические ресурсы",
                "emoji": "💎",
                "url": "https://hoi4.paradoxwikis.com/Resources_modding",
                "desc": "Добавление и настройка мировых ресурсов (нефть, сталь и др.).",
                "subsections": []
            },
            "unit": {
                "title": "Моддинг юнитов",
                "emoji": "🪖",
                "url": "https://hoi4.paradoxwikis.com/Unit_modding",
                "desc": "Добавление батальонов, типов войск и их характеристик.",
                "subsections": []
            },
            "entity": {
                "title": "3D Модели и Entity",
                "emoji": "🎮",
                "url": "https://hoi4.paradoxwikis.com/Entity_modding",
                "desc": "Привязка 3D-моделей солдат, техники и анимаций на карте.",
                "subsections": []
            },
            "font": {
                "title": "Шрифты интерфейса",
                "emoji": "🔤",
                "url": "https://hoi4.paradoxwikis.com/Font_modding",
                "desc": "Добавление и конвертация новых шрифтов для GUI.",
                "subsections": []
            },
            "music": {
                "title": "Музыка и радиостанция",
                "emoji": "🎵",
                "url": "https://hoi4.paradoxwikis.com/Music_modding",
                "desc": "Добавление музыкальных треков и кастомных радиостанций.",
                "subsections": []
            },
            "sound": {
                "title": "Звуковые эффекты",
                "emoji": "🔊",
                "url": "https://hoi4.paradoxwikis.com/Sound_modding",
                "desc": "Подключение звуков интерфейса, стрельбы и окружения.",
                "subsections": []
            },
            "portrait": {
                "title": "Портреты персонажей",
                "emoji": "🖼️",
                "url": "https://hoi4.paradoxwikis.com/Portrait_modding",
                "desc": "Настройка и привязка портретов лидеров и военачальников.",
                "subsections": []
            },
            "namelist": {
                "title": "Списки имён",
                "emoji": "📜",
                "url": "https://hoi4.paradoxwikis.com/Namelist_modding",
                "desc": "Генерация имён дивизий, кораблей, самолетов и персонажей.",
                "subsections": []
            },
            "mod_structure": {
                "title": "Структура мода",
                "emoji": "📁",
                "url": "https://hoi4.paradoxwikis.com/Mod_structure",
                "desc": "Иерархия папок мода, файл .mod и дескриптор.",
                "subsections": []
            },
            "console": {
                "title": "Консольные команды",
                "emoji": "💻",
                "url": "https://hoi4.paradoxwikis.com/Console_commands",
                "desc": "Список чит-кодов и консольных команд для тестов.",
                "subsections": []
            },
            "troubleshooting": {
                "title": "Отладка и ошибки",
                "emoji": "🛠️",
                "url": "https://hoi4.paradoxwikis.com/Troubleshooting",
                "desc": "Поиск багов, анализ error.log и отладка вылетов.",
                "subsections": []
            },
            "scripted_gui": {
                "title": "Скриптовый GUI",
                "emoji": "🖥️",
                "url": "https://hoi4.paradoxwikis.com/Scripted_GUI_modding",
                "desc": "Интерактивные интерфейсы, кнопки и окна на скриптах.",
                "subsections": []
            },
            "interface": {
                "title": "Моддинг интерфейса",
                "emoji": "🎨",
                "url": "https://hoi4.paradoxwikis.com/Interface_modding",
                "desc": "Редактирование .gui файлов, окон, макетов и кнопок.",
                "subsections": []
            },
            "modifiers": {
                "title": "Модификаторы",
                "emoji": "📈",
                "url": "https://hoi4.paradoxwikis.com/Modifiers",
                "desc": "Полный список баффов и дебаффов для страны и юнитов.",
                "subsections": [
                    {"title": "List of modifiers", "url": "https://hoi4.paradoxwikis.com/List_of_modifiers", "desc": "Полный перечень всех модификаторов игры."}
                ]
            },
            "idea": {
                "title": "Национальные духи и советники",
                "emoji": "💡",
                "url": "https://hoi4.paradoxwikis.com/Idea_modding",
                "desc": "Создание идей, законов, министров и советников.",
                "subsections": []
            },
            "technology": {
                "title": "Технологии и исследования",
                "emoji": "🔬",
                "url": "https://hoi4.paradoxwikis.com/Technology_modding",
                "desc": "Моддинг технологического древа, исследований и бонусов.",
                "subsections": []
            },
            "bop": {
                "title": "Баланс сил (Balance of Power)",
                "emoji": "⚖️",
                "url": "https://hoi4.paradoxwikis.com/Balance_of_power_modding",
                "desc": "Механика противоборствующих сторон и шкалы силы.",
                "subsections": []
            },
            "bookmark": {
                "title": "Стартовые закладки",
                "emoji": "📅",
                "url": "https://hoi4.paradoxwikis.com/Bookmark_modding",
                "desc": "Создание дат начала игры (1936, 1939 и т.д.).",
                "subsections": []
            },
            "gfx": {
                "title": "Графические ассеты (GFX)",
                "emoji": "🖼️",
                "url": "https://hoi4.paradoxwikis.com/Graphical_asset_modding",
                "desc": "Настройка текстур, .dds файлов, иконок и ассетов.",
                "subsections": [
                    {"title": "Posteffect modding", "url": "https://hoi4.paradoxwikis.com/Posteffect_modding", "desc": "Моддинг пост-эффектов шейдеров."},
                    {"title": "Particle modding", "url": "https://hoi4.paradoxwikis.com/Particle_modding", "desc": "Моддинг частиц и спецэффектов."}
                ]
            },
            "ai": {
                "title": "Моддинг ИИ (AI)",
                "emoji": "🤖",
                "url": "https://hoi4.paradoxwikis.com/AI_modding",
                "desc": "Настройка поведения бота, шаблонов строительства и фокусов.",
                "subsections": [
                    {"title": "AI focuses", "url": "https://hoi4.paradoxwikis.com/AI_focuses", "desc": "Настройка приоритетов фокусов для ИИ."}
                ]
            },
            "character": {
                "title": "Персонажи (Characters)",
                "emoji": "👤",
                "url": "https://hoi4.paradoxwikis.com/Character_modding",
                "desc": "Единая система генералов, лидеров стран и советников.",
                "subsections": []
            },
            "localisation": {
                "title": "Локализация",
                "emoji": "🌐",
                "url": "https://hoi4.paradoxwikis.com/Localisation",
                "desc": "Языковые файлы YAML, раскраска текста и переменные.",
                "subsections": [
                    {"title": "Colouring characters", "url": "https://hoi4.paradoxwikis.com/Localisation#Colouring_characters", "desc": "Задание цвета тексту в файлах локализации."},
                    {"title": "Formatting variables", "url": "https://hoi4.paradoxwikis.com/Localisation#Formatting_variables", "desc": "Вывод переменных и значений в текст."},
                    {"title": "Scripted localisation", "url": "https://hoi4.paradoxwikis.com/Localisation#Scripted_localisation", "desc": "Динамический текст по скриптовым условиям."}
                ]
            },
            "national_focuses": {
                "title": "Национальные фокусы",
                "emoji": "🎯",
                "url": "https://hoi4.paradoxwikis.com/National_focus_modding",
                "desc": "Создание древа фокусов, веток, связей и иконок.",
                "subsections": []
            },
            "triggers": {
                "title": "Триггеры и условия",
                "emoji": "🔍",
                "url": "https://hoi4.paradoxwikis.com/Triggers",
                "desc": "Справочник логических условий и проверок в скриптах.",
                "subsections": []
            }
        }

    @commands.hybrid_command(
        name="wiki",
        with_app_command=True,
        description="Посмотреть интерактивную справку и статьи по моддингу HOI4."
    )
    async def wiki(self, ctx: commands.Context):
        """Показать справочник статей вики по моддингу HOI4."""
        view = WikiView(self.wiki_map, ctx.author)
        embed = view.build_main_embed()
        msg = await ctx.send(embed=embed, view=view)
        view.message = msg

async def setup(bot: commands.Bot):
    await bot.add_cog(Wiki(bot))