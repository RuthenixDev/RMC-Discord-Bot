import discord
from discord.ext import commands
from utils import settings_cache as settings


class Starboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.star_emoji = "⭐"

    async def cog_check(self, ctx: commands.Context):
        """Проверка на доступ: админ или роль из admin_roles"""
        data = settings.load_settings()
        admin_roles = data.get("admin_roles", [])

        if ctx.author.guild_permissions.administrator:
            return True
        if any(str(role.id) in admin_roles for role in ctx.author.roles):
            return True

        raise commands.CheckFailure("")

    def update_star_threshold(self, new_target: int):
        """Обновить количество реакций для попадания в starboard"""
        data = settings.load_settings()
        data["starboards_target"] = int(new_target)
        settings.save_settings(data)

    def update_star_channel(self, channel_id: int):
        """Обновить id starboard канала"""
        data = settings.load_settings()
        data["starboard_channel_id"] = int(channel_id)
        settings.save_settings(data)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """Отслеживаем добавление реакции"""
        if str(payload.emoji) != self.star_emoji:
            return

        channel = self.bot.get_channel(payload.channel_id)
        if channel is None:
            return

        try:
            message = await channel.fetch_message(payload.message_id)
        except discord.NotFound:
            return

        # Загружаем настройки
        data = settings.load_settings()
        starboards_target = int(data.get("starboards_target", 3))
        starboard_channel_id = data.get("starboard_channel_id")

        if not starboard_channel_id:
            return

        # Считаем количество звёзд
        star_count = 0
        for reaction in message.reactions:
            if str(reaction.emoji) == self.star_emoji:
                star_count = reaction.count
                break

        if star_count < starboards_target:
            return

        starboard_channel = self.bot.get_channel(int(starboard_channel_id))
        if starboard_channel is None:
            return

        # Проверка на дубликат
        async for msg in starboard_channel.history(limit=200):
            if msg.embeds and msg.embeds[0].footer.text == f"ID: {message.id}":
                return

        # Формируем embed
        embed = discord.Embed(
            description=message.content or "*[без текста]*",
            color=discord.Color.gold()
        )
        embed.set_author(
            name=message.author.display_name,
            icon_url=message.author.display_avatar.url
        )
        embed.add_field(
            name="Ссылка",
            value=f"[Перейти к сообщению]({message.jump_url})",
            inline=False
        )
        if message.attachments:
            embed.set_image(url=message.attachments[0].url)

        embed.set_footer(text=f"ID: {message.id}")

        await starboard_channel.send(
            embed=embed
        )

    # ========================
    # Hybrid команды
    # ========================

    @commands.hybrid_command(name="setthreshold", description="Задать количество звёзд для попадания в starboard")
    async def set_star_threshold(self, ctx: commands.Context, number: int):
        self.update_star_threshold(number)
        embed = discord.Embed(
            description=f"✅ Порог для звёзд обновлён: теперь нужно **{number}** {self.star_emoji}",
            color=discord.Color.green()
        )
        await ctx.reply(
            embed=embed
        )

    @commands.hybrid_command(name="setstarboard", description="Задать канал для starboard")
    async def set_star_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        self.update_star_channel(channel.id)
        embed = discord.Embed(
            description=f"✅ Starboard будет использовать канал {channel.mention}",
            color=discord.Color.green()
        )
        await ctx.reply(
            embed=embed
        )


async def setup(bot):
    await bot.add_cog(Starboard(bot))
