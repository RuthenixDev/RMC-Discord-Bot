import discord
from discord.ext import commands
from utils import settings_cache as settings


class FilterChannels(commands.Cog):
    """Cog для управления каналами с фильтрацией сообщений."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def update_filter_channels(self, new_ids):
        data = settings.get()
        data["filter_channels"] = list(new_ids)
        settings.save()

    @commands.command(help="Добавляет канал в список фильтрации")
    @commands.has_permissions(manage_channels=True)
    async def addfilter(self, ctx, channel: discord.TextChannel):
        data = settings.get()
        filter_channel_ids = set(data.get("filter_channels", []))

        if channel.id in filter_channel_ids:
            await ctx.send(f"⚠️ Канал {channel.mention} уже в списке фильтрации.")
            return

        filter_channel_ids.add(channel.id)
        self.update_filter_channels(filter_channel_ids)
        await ctx.send(f"✅ Канал {channel.mention} добавлен в список фильтрации.")

    @commands.command(help="Удаляет канал из списка фильтрации")
    @commands.has_permissions(manage_channels=True)
    async def removefilter(self, ctx, channel: discord.TextChannel):
        data = settings.get()
        filter_channel_ids = set(data.get("filter_channels", []))

        if channel.id not in filter_channel_ids:
            await ctx.send(f"⚠️ Канал {channel.mention} не найден в списке фильтрации.")
            return

        filter_channel_ids.remove(channel.id)
        self.update_filter_channels(filter_channel_ids)
        await ctx.send(f"❌ Канал {channel.mention} удалён из списка фильтрации.")

    @commands.command(help="Показывает все каналы в списке фильтрации")
    async def listfilters(self, ctx):
        data = settings.get()
        filter_channel_ids = set(data.get("filter_channels", []))

        if not filter_channel_ids:
            await ctx.send("📭 Список каналов для фильтрации пуст.")
            return

        embed = discord.Embed(title="🛡️ Каналы с фильтрацией", color=discord.Color.purple())
        for cid in filter_channel_ids:
            channel = self.bot.get_channel(cid)
            if channel:
                embed.add_field(name=channel.name, value=channel.mention, inline=False)
            else:
                embed.add_field(name="❓ Неизвестный канал", value=f"ID: {cid}", inline=False)

        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Пример фильтрации сообщений."""
        if message.author.bot:
            return

        data = settings.get()
        filter_channel_ids = set(data.get("filter_channels", []))

        if message.channel.id not in filter_channel_ids:
            return

        # Здесь можно вставить свою логику фильтрации
        if "запрещенное слово" in message.content.lower():
            try:
                await message.delete()
                await message.channel.send(
                    f"⚠️ {message.author.mention}, ваше сообщение было удалено из-за запрещённого содержания.",
                    delete_after=5
                )
            except discord.Forbidden:
                print(f"Нет прав удалять сообщения в {message.channel.name}")
            except discord.HTTPException as e:
                print(f"Ошибка при удалении сообщения: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(FilterChannels(bot))
