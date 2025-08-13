import discord
from discord.ext import commands
from utils import settings_cache as settings


class StarChannels(commands.Cog):
    """Cog для управления ⭐-каналами и автоматической реакции."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def update_star_channels(self, new_ids):
        data = settings.get()
        data["star_channels"] = list(new_ids)
        settings.save()

    @commands.command(help="Добавляет канал в ⭐-список")
    @commands.has_permissions(manage_channels=True)
    async def addstar(self, ctx, channel: discord.TextChannel):
        data = settings.get()
        star_channel_ids = set(data.get("star_channels", []))

        if channel.id in star_channel_ids:
            await ctx.send(f"⚠️ Канал {channel.mention} уже в ⭐-списке.")
            return

        star_channel_ids.add(channel.id)
        self.update_star_channels(star_channel_ids)
        await ctx.send(f"✅ Канал {channel.mention} добавлен в ⭐-список.")

    @commands.command(help="Удаляет канал из ⭐-списка")
    @commands.has_permissions(manage_channels=True)
    async def removestar(self, ctx, channel: discord.TextChannel):
        data = settings.get()
        star_channel_ids = set(data.get("star_channels", []))

        if channel.id not in star_channel_ids:
            await ctx.send(f"⚠️ Канал {channel.mention} не найден в ⭐-списке.")
            return

        star_channel_ids.remove(channel.id)
        self.update_star_channels(star_channel_ids)
        await ctx.send(f"❌ Канал {channel.mention} удалён из ⭐-списка.")

    @commands.command(help="Показывает все каналы в ⭐-списке")
    async def liststars(self, ctx):
        data = settings.get()
        star_channel_ids = set(data.get("star_channels", []))

        if not star_channel_ids:
            await ctx.send("📭 Список ⭐-каналов пуст.")
            return

        embed = discord.Embed(title="⭐ Каналы со звёздной реакцией", color=discord.Color.gold())
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

        data = settings.get()
        star_channel_ids = set(data.get("star_channels", []))

        if message.channel.id not in star_channel_ids:
            return

        # Реакция ⭐
        try:
            await message.add_reaction("⭐")
        except discord.Forbidden:
            pass
        except discord.HTTPException:
            pass

        # Создание ветки
        first_line = message.content.split('\n')[0]
        thread_name = first_line[:100] if first_line else f"Обсуждение {message.author.display_name}"

        try:
            thread = await message.create_thread(
                name=thread_name,
                auto_archive_duration=1440  # 1 день
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
