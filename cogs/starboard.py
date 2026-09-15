import discord
from discord.ext import commands
from discord import app_commands
from utils import settings_cache as settings
from utils.permissions import check_cog_access
from constants import RMC_EMBED_COLOR


class Starboard(commands.Cog):
    required_access = "admin"

    def __init__(self, bot):
        self.bot = bot
        self.star_emoji = "⭐"
        self.block_emoji = discord.PartialEmoji(name="declined", id=1419728189059502080)

    async def cog_check(self, ctx: commands.Context):
        allowed = await check_cog_access(ctx, self.required_access)
        if not allowed:
            raise commands.CheckFailure()
        return True

    def get_starboards(self, data: dict):
        """Получает список starboards и мигрирует старые настройки при необходимости"""
        if "starboards" not in data:
            starboards = []
            old_id = data.get("starboard_channel_id")
            old_target = data.get("starboards_target", 3)
            if old_id:
                starboards.append({"channel_id": int(old_id), "target": int(old_target)})
            data["starboards"] = starboards
            settings.save_settings(data)
            return starboards
        return data["starboards"]

    def update_starboards(self, starboards: list):
        """Обновить список starboard каналов"""
        data = settings.load_settings()
        data["starboards"] = starboards
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
        excluded_messages = data.get("starboard_excluded_messages", [])
        if payload.message_id in excluded_messages:
            return

        starboards = self.get_starboards(data)
        if not starboards:
            return

        # Считаем количество звёзд и проверяем блокирующие реакции
        star_count = 0
        for reaction in message.reactions:
            if reaction.me and str(reaction.emoji) != self.star_emoji:
                return  # Любая реакция бота (кроме звезды) считается блокирующей
            
            if str(reaction.emoji) == self.star_emoji:
                star_count = reaction.count

        if star_count == 0:
            return

        # Формируем embed только один раз, если он вообще куда-то будет отправлен
        embed = None

        for sb in starboards:
            target = sb.get("target", 3)
            channel_id = sb.get("channel_id")

            if star_count < target:
                continue

            starboard_channel = self.bot.get_channel(int(channel_id))
            if starboard_channel is None:
                continue

            # Проверка на дубликат для этого конкретного канала
            duplicate = False
            async for msg in starboard_channel.history(limit=200):
                if msg.embeds and msg.embeds[0].footer.text == f"ID: {message.id}":
                    duplicate = True
                    break
            
            if duplicate:
                continue

            if embed is None:
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

            await starboard_channel.send(embed=embed)

    # ========================
    # Hybrid команды
    # ========================

    @commands.hybrid_command(name="addstarboard", description="Добавить/обновить starboard канал и его порог звёзд")
    @app_commands.describe(channel="Канал для starboard", target="Необходимое количество звёзд")
    async def addstarboard(self, ctx: commands.Context, channel: discord.TextChannel, target: int):
        data = settings.load_settings()
        starboards = self.get_starboards(data)
        
        # Обновляем, если уже есть, или добавляем
        updated = False
        for sb in starboards:
            if sb["channel_id"] == channel.id:
                sb["target"] = target
                updated = True
                break
        
        if not updated:
            starboards.append({"channel_id": channel.id, "target": target})
            
        self.update_starboards(starboards)
        
        action = "Обновлён" if updated else "Добавлен"
        embed = discord.Embed(
            description=f"✅ {action} starboard канал {channel.mention} с порогом **{target}** {self.star_emoji}",
            color=discord.Color.green()
        )
        await ctx.reply(embed=embed)

    @commands.hybrid_command(name="removestarboard", description="Удалить starboard канал")
    @app_commands.describe(channel="Канал для удаления из starboard")
    async def removestarboard(self, ctx: commands.Context, channel: discord.TextChannel):
        data = settings.load_settings()
        starboards = self.get_starboards(data)
        
        new_starboards = [sb for sb in starboards if sb["channel_id"] != channel.id]
        
        if len(new_starboards) == len(starboards):
            embed = discord.Embed(
                description=f"⚠️ Канал {channel.mention} не найден в списке starboard.",
                color=discord.Color.dark_gray()
            )
            return await ctx.reply(embed=embed)
            
        self.update_starboards(new_starboards)
        
        embed = discord.Embed(
            description=f"❌ Канал {channel.mention} удалён из списка starboard.",
            color=discord.Color.dark_red()
        )
        await ctx.reply(embed=embed)

    @commands.hybrid_command(name="liststarboards", description="Показать список starboard каналов и их порогов")
    async def liststarboards(self, ctx: commands.Context):
        data = settings.load_settings()
        starboards = self.get_starboards(data)
        
        if not starboards:
            embed = discord.Embed(
                description="📭 Список starboard каналов пуст.",
                color=discord.Color.dark_gray()
            )
            return await ctx.reply(embed=embed)
            
        embed = discord.Embed(title="🌟 Starboard каналы", color=RMC_EMBED_COLOR)
        for sb in starboards:
            channel = self.bot.get_channel(sb["channel_id"])
            channel_name = channel.mention if channel else f"❓ Неизвестный канал (ID: {sb['channel_id']})"
            embed.add_field(
                name=f"Порог: {sb['target']} ⭐",
                value=channel_name,
                inline=False
            )
            
        await ctx.reply(embed=embed)

    @commands.hybrid_command(name="starboard_block", description="Заблокировать сообщение для Starboard")
    @app_commands.describe(message_link="Ссылка на сообщение", custom_emoji="Кастомный эмодзи для блокировки (опционально)")
    async def starboard_block(self, ctx: commands.Context, message_link: str, custom_emoji: str = None):
        settings_data = settings.load_settings()
        log_channel_id = settings_data.get('log_channel')
        log_channel = ctx.guild.get_channel(log_channel_id) if log_channel_id else None

        if not log_channel:
            embed = discord.Embed(
                title="❌ Возникла ошибка при блокировке сообщения для Starboard",
                description="Канал для логов не найден. Настройте через /set_log",
                color=RMC_EMBED_COLOR
            )
            return await ctx.reply(embed=embed, ephemeral=True)

        try:
            parts = message_link.strip('/').split("/")
            channel_id = int(parts[-2])
            message_id = int(parts[-1])
        except (ValueError, IndexError):
            embed = discord.Embed(
                title="❌ Возникла ошибка при блокировке сообщения для Starboard",
                description="Неверный формат ссылки на сообщение.",
                color=RMC_EMBED_COLOR
            )
            return await ctx.reply(embed=embed, ephemeral=True)

        channel = ctx.guild.get_channel(channel_id) or ctx.guild.get_thread(channel_id)
        if not channel:
            embed = discord.Embed(
                title="❌ Возникла ошибка при блокировке сообщения для Starboard",
                description="Канал не найден.",
                color=RMC_EMBED_COLOR
            )
            return await ctx.reply(embed=embed, ephemeral=True)

        try:
            message = await channel.fetch_message(message_id)
            emoji_to_use = custom_emoji if custom_emoji else self.block_emoji
            await message.add_reaction(emoji_to_use)
            embed = discord.Embed(
                title = "✅ Успешно заблокировано сообщение для Starboard",
                description=f"Бот поставил реакцию {emoji_to_use}.\nТеперь это сообщение не попадёт в Starboard.\n[Перейти к сообщению]({message_link})",
                color=RMC_EMBED_COLOR
            )
            await ctx.reply(embed=embed, ephemeral=True)
            log_embed = discord.Embed(
                title="Модератор заблокировал сообщение для Starboard",
                description=f"Модератор {ctx.author.mention} заблокировал сообщение для Starboard.",
                color = RMC_EMBED_COLOR,
                timestamp=discord.utils.utcnow()
            )
            log_embed.add_field(name="Модератор", value=f"{ctx.author.mention} `{ctx.author.id}`", inline=False)
            log_embed.add_field(name="Автор сообщения", value=f"{message.author.mention} `{message.author.id}`", inline=False)
            log_embed.add_field(name="Сообщение", value=f"[Перейти к сообщению]({message_link})", inline=False)

            if log_channel:
                await log_channel.send(embed=log_embed)
            
        except discord.NotFound:
            embed = discord.Embed(
                title="❌ Возникла ошибка при блокировке сообщения для Starboard",
                description="Сообщение не найдено.",
                color=RMC_EMBED_COLOR
            )
            await ctx.reply(embed=embed, ephemeral=True)
        except discord.Forbidden:
            embed = discord.Embed(
                title="❌ Возникла ошибка при блокировке сообщения для Starboard",
                description="У бота нет прав на добавление реакции.",
                color=RMC_EMBED_COLOR
            )
            await ctx.reply(embed=embed, ephemeral=True)
        except discord.HTTPException:
            embed = discord.Embed(
                title="❌ Ошибка",
                description="Не удалось поставить реакцию. Убедитесь, что эмодзи указан верно и бот имеет к нему доступ.",
                color=RMC_EMBED_COLOR
            )
            await ctx.reply(embed=embed, ephemeral=True)

    @commands.hybrid_command(name="starboard_unblock", description="Снять блокировку Starboard (убрать реакцию бота)")
    @app_commands.describe(message_link="Ссылка на сообщение")
    async def starboard_unblock(self, ctx: commands.Context, message_link: str):
        settings_data = settings.load_settings()
        log_channel_id = settings_data.get('log_channel')
        log_channel = ctx.guild.get_channel(log_channel_id) if log_channel_id else None

        if not log_channel:
            embed = discord.Embed(
                title="❌ Возникла ошибка при разблокировке сообщения для Starboard",
                description="Канал для логов не найден. Настройте через /set_log",
                color=RMC_EMBED_COLOR
            )
            return await ctx.reply(embed=embed, ephemeral=True)
        
        try:
            parts = message_link.strip('/').split("/")
            channel_id = int(parts[-2])
            message_id = int(parts[-1])
        except (ValueError, IndexError):
            embed = discord.Embed(description="❌ Неверный формат ссылки на сообщение.", color=discord.Color.red())
            return await ctx.reply(embed=embed, ephemeral=True)

        channel = ctx.guild.get_channel(channel_id) or ctx.guild.get_thread(channel_id)
        if not channel:
            embed = discord.Embed(
                title="❌ Возникла ошибка при разблокировке сообщения для Starboard",
                description="Канал не найден.",
                color=RMC_EMBED_COLOR
            )
            return await ctx.reply(embed=embed, ephemeral=True)

        try:
            message = await channel.fetch_message(message_id)
            
            removed_emojis = []
            for reaction in message.reactions:
                if reaction.me and str(reaction.emoji) != self.star_emoji:
                    await message.remove_reaction(reaction.emoji, self.bot.user)
                    removed_emojis.append(str(reaction.emoji))

            if removed_emojis:
                emojis_str = ", ".join(removed_emojis)
                embed = discord.Embed(
                    title = "✅ Успешно разблокировано сообщение для Starboard",
                    description=f"Бот убрал реакцию(и) {emojis_str}.\nТеперь это сообщение снова может попасть в Starboard.\n[Перейти к сообщению]({message_link})",
                    color=RMC_EMBED_COLOR
                )
                await ctx.reply(embed=embed, ephemeral=True)
            else:
                embed = discord.Embed(
                    title="⚠️ Сообщение не было заблокировано",
                    description="Бот не ставил блокирующих реакций на это сообщение.",
                    color=discord.Color.orange()
                )
                return await ctx.reply(embed=embed, ephemeral=True)

            log_embed = discord.Embed(
                title="Модератор разблокировал сообщение для Starboard",
                description=f"Модератор {ctx.author.mention} разблокировал сообщение для Starboard (убраны: {emojis_str}).",
                color = RMC_EMBED_COLOR,
                timestamp=discord.utils.utcnow()
            )
            log_embed.add_field(name="Модератор", value=f"{ctx.author.mention} `{ctx.author.id}`", inline=False)
            log_embed.add_field(name="Автор сообщения", value=f"{message.author.mention} `{message.author.id}`", inline=False)
            log_embed.add_field(name="Сообщение", value=f"[Перейти к сообщению]({message_link})", inline=False)
            
            if log_channel:
                await log_channel.send(embed=log_embed)

        except discord.NotFound:
            embed = discord.Embed(
                title="❌ Возникла ошибка при разблокировке сообщения для Starboard",
                description="Сообщение не найдено.",
                color=RMC_EMBED_COLOR
            )
            await ctx.reply(embed=embed, ephemeral=True)
        except discord.Forbidden:
            embed = discord.Embed(
                title="❌ Возникла ошибка при разблокировке сообщения для Starboard",
                description="У бота нет прав на удаление реакции.",
                color=RMC_EMBED_COLOR
            )
            await ctx.reply(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Starboard(bot))
