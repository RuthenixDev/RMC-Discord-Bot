import discord
from discord.ext import commands
from utils import settings_cache as settings
from constants import RMC_EMBED_COLOR


class StarChannels(commands.Cog):
    """Cog для управления ⭐-каналами и автоматической реакции."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_check(self, ctx: commands.Context):
        data = settings.load_settings()
        admin_roles = data.get("admin_roles", [])

        if ctx.author.guild_permissions.administrator:
            return True
        elif any(str(role.id) in admin_roles for role in ctx.author.roles):
            return True

        raise commands.CheckFailure()
        

    def update_star_channels(self, new_ids):
        """Обновляет список ⭐-каналов в settings.json."""
        data = settings.load_settings()
        data["star_channels"] = list(new_ids)
        settings.save_settings(data)

    @commands.hybrid_command(
        name="addstar",
        with_app_command=True,
        description="Добавляет канал в ⭐-список"
    )
    async def addstar(self, ctx, channel: discord.TextChannel = None):
        if channel is None:
            channel = ctx.channel

        data = settings.load_settings()
        star_channel_ids = set(data.get("star_channels", []))

        if channel.id in star_channel_ids:
            embed = discord.Embed(
                description=f"⚠️ Канал {channel.mention} уже в ⭐-списке.",
                color=discord.Color.dark_gray()
            )
            await ctx.reply(
                embed=embed
            )
            return

        star_channel_ids.add(channel.id)
        self.update_star_channels(star_channel_ids)
        embed = discord.Embed(
            description=f"✅ Канал {channel.mention} добавлен в ⭐-список.",
            color=discord.Color.green()
        )
        await ctx.reply(
            embed=embed
        )

    @commands.hybrid_command(
        name="removestar",
        with_app_command=True,
        description="Удаляет канал из ⭐-списка"
    )
    async def removestar(self, ctx, channel: discord.TextChannel = None):
        if channel is None:
            channel = ctx.channel

        data = settings.load_settings()
        star_channel_ids = set(data.get("star_channels", []))

        if channel.id not in star_channel_ids:
            embed = discord.Embed(
                description=f"⚠️ Канал {channel.mention} не найден в ⭐-списке.",
                color=discord.Color.dark_gray()
            )
            await ctx.reply(
                embed=embed
            )
            return

        star_channel_ids.remove(channel.id)
        self.update_star_channels(star_channel_ids)
        embed = discord.Embed(
            description=f"❌ Канал {channel.mention} удалён из ⭐-списка.",
            color=discord.Color.dark_red()
        )
        await ctx.reply(
            embed=embed
        )

    @commands.hybrid_command(
        name="liststars",
        with_app_command=True,
        description="Показывает все каналы в ⭐-списке"
    )
    async def liststars(self, ctx):
        data = settings.load_settings()
        star_channel_ids = set(data.get("star_channels", []))

        if not star_channel_ids:
            embed = discord.Embed(
                description="📭 Список ⭐-каналов пуст.",
                color=discord.Color.dark_gray()
            )
            await ctx.reply(
                embed=embed
            )
            return

        embed = discord.Embed(title="⭐ Каналы со звёздной реакцией", color=RMC_EMBED_COLOR)
        for cid in star_channel_ids:
            channel = self.bot.get_channel(cid)
            if channel:
                embed.add_field(name=channel.name, value=channel.mention, inline=False)
            else:
                embed.add_field(name="❓ Неизвестный канал", value=f"ID: {cid}", inline=False)

        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Автоматически добавляет ⭐ и создаёт ветку в ⭐-каналах."""
        if message.author.bot:
            return

        data = settings.load_settings()
        star_channel_ids = set(data.get("star_channels", []))

        if message.channel.id not in star_channel_ids:
            return

        # Реакция ⭐
        try:
            await message.add_reaction("⭐")
        except (discord.Forbidden, discord.HTTPException):
            pass

        # Создание ветки
        first_line = message.content.split('\n')[0]
        thread_name =  f"Обсуждение {message.author.display_name}"

        try:
            thread = await message.create_thread(
                name=thread_name,
                auto_archive_duration=4320  # 1 день = 1440, считается в минутах
            )
            await thread.send(
                f"**Обсуждение работы пользователя {message.author.display_name}**\n\n"
                "Если вам понравилась работа, поставьте реакцию ⭐, чтобы поддержать автора!"
            )
        except discord.Forbidden:
            print(f"Нет прав для создания ветки в канале {message.channel.name}")
        except discord.HTTPException as e:
            print(f"Ошибка при создании ветки: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(StarChannels(bot))
