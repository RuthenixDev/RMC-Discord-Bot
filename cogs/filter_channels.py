import discord
from discord.ext import commands
from utils import settings_cache as settings
import time
from constants import RMC_EMBED_COLOR

COOLDOWN = 600

class FilterChannels(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_check(self, ctx: commands.Context):
        data = settings.load_settings()
        admin_roles = data.get("admin_roles", [])

        if ctx.author.guild_permissions.administrator:
            return True
        elif any(str(role.id) in admin_roles for role in ctx.author.roles):
            return True

        raise commands.CheckFailure("❌ У вас нет прав для этого раздела команд. Если вы считаете это ошибкой, свяжитесь с администратором.")

    def update_filter_channels(self, new_ids):
        data = settings.load_settings()

        data["filter_channels"] = list(new_ids)
        settings.save_settings(data)

    def update_filter_timeouts(self, filter_timeouts):
            data = settings.load_settings()

            data["filter_timeout"] = filter_timeouts
            settings.save_settings(data)


    @commands.hybrid_command(
        name="addfilter",
        with_app_command=True,
        description="Добавляет канал в список онли-медиа каналов"
    )
    async def addfilter(self, ctx, channel: discord.TextChannel = None):
        if channel is None:
            channel = ctx.channel

        data = settings.load_settings()
        filter_channel_ids: set[int] = set(data.get("filter_channels", []))

        if channel.id in filter_channel_ids:
            embed = discord.Embed(
                description=f"⚠️ Канал {channel.mention} уже в списке фильтруемых.",
                color=discord.Color.dark_gray()
            )
            await ctx.reply(
                embed=embed
            )
            return
        
        filter_channel_ids.add(channel.id)
        self.update_filter_channels(filter_channel_ids)
        embed = discord.Embed(
            description=f"✅ Канал {channel.mention} добавлен в список фильтруемых.",
            color=discord.Color.green()
        )
        await ctx.reply(
            embed=embed
        )

    @commands.hybrid_command(
        name="removefilter",
        with_app_command=True,
        description="Удаляет канал из списка онли-медиа каналов"
    )
    async def removefilter(self, ctx, channel: discord.TextChannel = None):
        if channel is None:
            channel = ctx.channel
            
        data = settings.load_settings()
        filter_channel_ids: set[int] = set(data.get("filter_channels", []))

        if channel.id not in filter_channel_ids:
            embed = discord.Embed(
                description=f"⚠️ Канал {channel.mention} не найден в списке фильтруемых.",
                color=discord.Color.dark_gray()
            )
            await ctx.reply(
                embed=embed
            )
            return
        filter_channel_ids.remove(channel.id)
        self.update_filter_channels(filter_channel_ids)
        embed = discord.Embed(
            description=f"❌ Канал {channel.mention} удалён из списка фильтруемых.",
            color=discord.Color.dark_red()
        )
        await ctx.reply(
            embed=embed
        )

    @commands.hybrid_command(
        name="listfilters",
        with_app_command=True,
        description="Показывает список онли-медиа каналов"
    )
    async def listfilters(self, ctx):
        data = settings.load_settings()
        filter_channel_ids: set[int] = set(data.get("filter_channels", []))

        if not filter_channel_ids:
            embed = discord.Embed(
                description="📭 Список фильтруемых каналов пуст.",
                color=discord.Color.dark_gray()
            )
            await ctx.reply(
                embed=embed
            )
            return

        embed = discord.Embed(title="📵 Фильтруемые каналы", color=RMC_EMBED_COLOR)
        for cid in filter_channel_ids:
            channel = self.bot.get_channel(cid)
            if channel:
                embed.add_field(name=channel.name, value=channel.mention, inline=False)
            else:
                embed.add_field(name="❓ Неизвестный канал", value=f"ID: {cid}", inline=False)

        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        data = settings.load_settings()
        filter_channel_ids: set[int] = set(data.get("filter_channels", []))

        user_id_str = str(message.author.id)
        now = int(time.time())
        filter_timeouts = data.get("filter_timeouts", {})

        last_violation = filter_timeouts.get(user_id_str, 0)

        has_attachments = bool(message.attachments)
        has_links = ("http://" in message.content) or ("https://" in message.content)
        is_forwarded = message.flags.forwarded

        if message.channel.id not in filter_channel_ids:
            return

        if not has_attachments and not has_links and not is_forwarded:
            try:
                await message.delete()
                print(f"Удалено сообщение от {message.author} в {message.channel.name} без вложений и ссылок")

                if now - last_violation >= COOLDOWN:
                    filter_timeouts[user_id_str] = now
                    self.update_filter_timeouts(filter_timeouts)

                    embed = discord.Embed(
                        title="📵 Только медиа-сообщения!",
                        description="Этот канал предназначен **только для изображений, видео или ссылок**.\n\n"
                                    "Пожалуйста, не отправляй обычные текстовые сообщения без вложений.",
                        color=RMC_EMBED_COLOR
                    )
                    try:
                        await message.author.send(embed=embed)
                    except discord.Forbidden:
                        print(f"Не удалось отправить ЛС пользователю {message.author}")
            except discord.Forbidden:
                print(f"Нет прав удалять сообщения в {message.channel.name}")
            except discord.HTTPException as e:
                print(f"Ошибка при удалении сообщения: {e}")


async def setup(bot):
    await bot.add_cog(FilterChannels(bot))