import discord
import time
from discord.ext import commands
from discord import app_commands
from utils.permissions import check_cog_access
from utils import settings_cache as settings
from discord.ui import View, Button
from typing import Optional
from constants import RMC_EMBED_COLOR

class ResponseButton(discord.ui.View):
    def __init__(self, target_user: discord.User, original_author: discord.User, original_message: str):
        super().__init__(timeout=86400)
        self.target_user = target_user
        self.original_author = original_author
        self.original_message = original_message
        self.clicked = False
        self.message_id = None
        self.channel_id = None
    
    @discord.ui.button(label="✏️ Ответить", style=discord.ButtonStyle.primary)
    async def response_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.target_user:
            await interaction.response.send_message("❌ Эта кнопка не для вас!", ephemeral=True)
            return
        if self.clicked:
            await interaction.response.send_message("⏳ Вы уже отправили ответ!", ephemeral=True)
            return
        self.clicked = True
        modal = ResponseModal(self, self.original_author, self.original_message)
        await interaction.response.send_modal(modal)

    async def disable_button(self, interaction):
        channel = interaction.client.get_channel(self.channel_id)
        if channel:
            try:
                message = await channel.fetch_message(self.message_id)
                for child in message.components[0].children:
                    child.disabled = True
                await message.edit(view=self)
            except:
                pass

class ResponseModal(discord.ui.Modal, title="Ответ на сообщение"):
    response = discord.ui.TextInput(
        label="Ваш ответ",
        style=discord.TextStyle.long,
        placeholder="Введите ваш ответ...",
        max_length=1000,
        required=True
    )

    def __init__(self, view: ResponseButton,original_author, original_message):
        super().__init__()
        self.view = view
        self.original_author = original_author
        self.original_message = original_message

    
    async def on_submit(self, interaction: discord.Interaction):
        # Отправляем ответ модератору (или куда нужно)
        await interaction.response.send_message(
            f"✅ Ваш ответ отправлен!",
            ephemeral=True
        )

        settings_data = settings.load_settings()
        channel_id = settings_data.get('log_channel')

        if channel_id:
            log_channel = interaction.client.get_channel(channel_id)  
            text = f"{self.original_author.mention}"
            log_embed = discord.Embed(
                title="📬 Получен ответ",
                color=RMC_EMBED_COLOR,
                timestamp=discord.utils.utcnow()
            )
            
            # Кто ответил
            log_embed.add_field(
                name="✍️ Ответил",
                value=f"{interaction.user.mention}\n`{interaction.user.id}`",
                inline=True
            )
            
            # Кому ответил (оригинальный автор)
            log_embed.add_field(
                name="👤 Оригинальный отправитель",
                value=f"{self.original_author.mention}\n`{self.original_author.id}`",
                inline=True
            )
            
            # Текст ответа
            log_embed.add_field(
                name="📝 Текст ответа",
                value=f"```{self.response.value}```",
                inline=False
            )
            
            # Оригинальное сообщение (опционально)
            log_embed.add_field(
                name="📨 Оригинальное сообщение",
                value=f"```{self.original_message}```",
                inline=False
            )
                    
            if log_channel:
                await log_channel.send(text, embed=log_embed)

        await self.view.disable_button(interaction)

class Messaging(commands.Cog):
    """Cog для отправки сообщений в ЛС участникам сервера от имени бота."""
    required_access = "admin"

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_check(self, ctx: commands.Context):
        allowed = await check_cog_access(ctx, self.required_access)
        if not allowed:
            raise commands.CheckFailure()
        return True
    
    async def check_admin(self, interaction: discord.Interaction) -> bool:
        """Проверяет, есть ли у пользователя админская роль"""
        settings_data = settings.load_settings()
        admin_roles = settings_data.get('admin_roles', [])
        user_roles = [role.id for role in interaction.user.roles]
        return any(role_id in admin_roles for role_id in user_roles)
    
    @app_commands.command(
        name="dm_embed_user",
        description="Отправить личное embed-сообщение участнику"
    )
    @app_commands.guild_only()
    @app_commands.choices(anonymous=[
        app_commands.Choice(name="Да", value=1),
        app_commands.Choice(name="Нет", value=0),
    ])
    @app_commands.describe(
        member = "Адресат сообщения",
        message = "Текст embed-сообщения",
        anonymous = "Анонимность сообщения",
        #log_channel = "Канал для отправки лога"
    )
    @app_commands.choices(allow_response=[
        app_commands.Choice(name="Да", value=1),
        app_commands.Choice(name="Нет", value=0),
    ])
    async def dm_embed_user(self, interaction: discord.Interaction, member: discord.Member, message: str, anonymous: int, allow_response: int = 0):
        
        if not await self.check_admin(interaction):
            await interaction.response.send_message("❌ Недостаточно прав", ephemeral=True)
            return

        is_anonymous = bool(anonymous)
        is_allow_response = bool(allow_response)
        
        is_allow_response_formatted = "✅ Да" if is_allow_response else "❌ Нет"

        if is_anonymous:
            author = "🕵️ Анонимное сообщение"
            icon = None
            anonymous_formatted = "✅ Да"
        else: 
            author = interaction.user
            icon = interaction.user.avatar.url if interaction.user.avatar else None
            anonymous_formatted = "❌ Нет"
        try:

            settings_data = settings.load_settings()
            channel_id = settings_data.get('log_channel')
            log_channel = interaction.guild.get_channel(channel_id) if channel_id else None 

            if not log_channel:
                embed = discord.Embed(
                    title="❌ Ошибка",
                    description=f"У бота не настроен канал для логов! Воспользуйтесь `/set_log`",
                    color=RMC_EMBED_COLOR
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            dm_message = discord.Embed(
                title="📨 Вам сообщение!",
                description=f"{message}",
                color=RMC_EMBED_COLOR,
                timestamp=discord.utils.utcnow()
            )
            dm_message.set_footer(
                text=f"{author}",
                icon_url=icon
            )
            if is_allow_response:
                view = ResponseButton(
                    target_user=member,
                    original_author=interaction.user,
                    original_message=message
                )  
                sent_message = await member.send(embed=dm_message, view=view)
                view.message_id = sent_message.id
                view.channel_id = sent_message.channel.id
                #await member.send(embed=dm_message, view=view)
            else:
                await member.send(embed=dm_message)
            embed = discord.Embed(
                title=f"✅ Сообщение успешно отправлено!",
                description=f"Участник {member.mention} получил сообщение.",
                color=RMC_EMBED_COLOR
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

            if log_channel:
                timestamp = time.time()
                discord_time = f"<t:{int(timestamp)}:d>"

                try:
                    fresh_member = await interaction.guild.fetch_member(member.id)
                    member_mention = fresh_member.mention
                except discord.NotFound:
                    member_mention = f"@{member.name} (покинул сервер)"
                except:
                    member_mention = f"<@{member.id}>"  # fallback

                log_message = discord.Embed(
                    title=f"Участнику отправлено embed-сообщение",
                    color=RMC_EMBED_COLOR
                )
                log_message.add_field(
                    name="👤 Получатель",
                    value=f"{member_mention}\n`{member.id}`",
                    inline=True
                )
                log_message.add_field(
                    name="✍️ Автор сообщения",
                    value=f"{interaction.user.mention} `{interaction.user.id}`",
                    inline=False
                )
                log_message.add_field(
                    name="📝 Текст сообщения",
                    value=f"```{message}```",
                    inline=False
                )
                log_message.add_field(
                    name="🕵️ Анонимность",
                    value=f"{anonymous_formatted}",
                    inline=True
                )
                log_message.add_field(
                    name="📅 Дата",
                    value=f"{discord_time}",
                    inline=True
                )
                log_message.add_field(
                    name="📨 Разрешён ответ",
                    value=f"{is_allow_response_formatted}",
                    inline=True
                )
                await log_channel.send(embed=log_message)
            else:
                embed = discord.Embed(
                    title="❌ Ошибка",
                    description=f"У бота не настроен канал для логов!",
                    color=RMC_EMBED_COLOR
                )
                embed.set_footer(
                    text="Для настройки используйте `/set_log`"
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
        except discord.Forbidden:
            embed = discord.Embed(
                title="❌ Ошибка",
                description=f"Не могу отправить сообщение {member.mention}. Закрыты ЛС.",
                color=RMC_EMBED_COLOR
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            embed = discord.Embed(
                title="❌ Ошибка",
                description=f"Не удалось отправить сообщение: {e}",
                color=RMC_EMBED_COLOR
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="send_msg",
        description="Отправить сообщение в текстовый канал от имени бота"
    )
    @app_commands.guild_only()
    @app_commands.describe(
        channel = "Канал для отправки сообщения",
        content = "Содержимое сообщения",
        reply_on = "Ссылка на сообщение для ответа (опционально)"
    )
    async def send_msg(self, interaction: discord.Interaction, channel: discord.TextChannel, content: str, reply_on: Optional[str] = None):
        
        if not await self.check_admin(interaction):
            await interaction.response.send_message("❌ Недостаточно прав", ephemeral=True)
            return

        if not channel.permissions_for(interaction.guild.me).send_messages:
            embed = discord.Embed(
                title="❌ Ошибка",
                description=f"У бота нет прав писать в канал {channel.mention}",
                color=RMC_EMBED_COLOR
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        settings_data = settings.load_settings()
        channel_id = settings_data.get('log_channel')
        log_channel = interaction.guild.get_channel(channel_id) if channel_id else None 

        timestamp = time.time()
        discord_time = f"<t:{int(timestamp)}:d>"

        if not log_channel:
            embed = discord.Embed(
                title="❌ Ошибка",
                description="У бота не настроен канал для логов!",
                color=RMC_EMBED_COLOR
            )
            embed.set_footer(text="Для настройки используйте `/set_log`")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        try:
            log_embed = discord.Embed(
                title=f"Модератор отправил сообщение через бота",
                color=RMC_EMBED_COLOR
            )
            log_embed.add_field(
                name="✍️ Автор сообщения",
                value=f"{interaction.user.mention} ({interaction.user.id})",
                inline=False
            )
            log_embed.add_field(
                name="Канал",
                value=f"{channel.mention}",
                inline=True
            )
            log_embed.add_field(
                name="📝 Текст сообщения",
                value=f"```{content}```",
                inline=False
            )
            log_embed.add_field(
                name="📅 Дата",
                value=f"{discord_time}",
                inline=True
            )

            if reply_on:
                parts = reply_on.split('/')
                msg_channel_id = int(parts[-2]) 
                msg_id = int(parts[-1])
                msg_channel = interaction.guild.get_channel(msg_channel_id)
                if not msg_channel:
                    embed = discord.Embed(
                        title="❌ Ошибка",
                        description=f"Не удалось найти канал для ответа. Проверьте ссылку.",
                        color=RMC_EMBED_COLOR
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return
                reply_message = await msg_channel.fetch_message(msg_id)
                await channel.send(content, reference=reply_message)
                
                log_embed.add_field(
                    name="💬 Ответ на",
                    value=f"[сообщение]({reply_on})",
                    inline=True
                )
                
                embed = discord.Embed(
                    title="✅ Сообщение отправлено",
                    description=f"Сообщение отправлено в {channel.mention} с содержимым: ```{content}```",
                    color=RMC_EMBED_COLOR,
                    timestamp=discord.utils.utcnow()
                )
            else:
                await channel.send(content)
                
                embed = discord.Embed(
                    title="✅ Сообщение отправлено",
                    description=f"Сообщение отправлено в {channel.mention} с содержимым: ```{content}```",
                    color=RMC_EMBED_COLOR,
                    timestamp=discord.utils.utcnow()
                )

            await interaction.response.send_message(embed=embed, ephemeral=True)
            await log_channel.send(embed=log_embed)

        except discord.HTTPException as e: 

            if e.code == 50035 and "Cannot reply to a message in a different channel" in str(e):
                embed = discord.Embed(
                    title="❌ Ошибка",
                    description=f"Нельзя ответить на сообщение из другого канала.\n"
                            f"Сообщение находится в {msg_channel.mention}, "
                            f"а вы отправляете в {channel.mention}.\n\n"
                            f"**Решение:** отправьте сообщение в канал {msg_channel.mention} "
                            f"или используйте ссылку на сообщение из этого канала.",
                    color=RMC_EMBED_COLOR
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                # Другая HTTP ошибка
                embed = discord.Embed(
                    title="❌ Ошибка",
                    description=f"Ошибка API Discord: ```{e}```",
                    color=RMC_EMBED_COLOR
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        except discord.Forbidden:
            embed = discord.Embed(
                title="❌ Ошибка",
                description=f"У бота нет прав писать в канал {channel.mention}",
                color=RMC_EMBED_COLOR
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return  
        except Exception as e:
            embed = discord.Embed(
                title="❌ Ошибка",
                description=f"У бота не получилось отправить сообщение из-за ошибки: ```{e}```",
                color=RMC_EMBED_COLOR
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return 

    async def color_autocomplete(self, interaction: discord.Interaction, current: str):
        preset_colors = {
            "🔴 Красный": discord.Color.red(),
            "🔵 Синий": discord.Color.blue(),
            "🟢 Зелёный": discord.Color.green(),
            "🟣 Фиолетовый": discord.Color.purple(),
            "💗 Розовый": discord.Color.magenta(),  
            "🟤 Коричневый": discord.Color.from_rgb(150, 75, 0),  
            "⬛ Чёрный": discord.Color.from_rgb(0, 0, 0),  
            "⬜ Белый": discord.Color.from_rgb(255, 255, 255),  
            "🔘 Серый": discord.Color.lighter_grey(),
            "⚫ Тёмно-серый": discord.Color.darker_grey(),
            "🟡 Золотой": discord.Color.gold(),
            "🩵 Стандартный RMC_EMBED_COLOR": RMC_EMBED_COLOR
        }

        choices = []

        for name, value in preset_colors.items():
            if current.lower() in name.lower():
                choices.append(app_commands.Choice(name=name, value=str(value)))

        if current.startswith('#') or current.startswith('0x'):
            choices.append(app_commands.Choice(
                name=f"✏️ Свой цвет: {current}",
                value=current
            ))

        return choices
    
    @app_commands.command(
        name="send_embed",
        description="Отправить embed-сообщение в текстовый канал от имени бота"
    )
    @app_commands.guild_only()
    @app_commands.describe(
        channel = "Канал для отправки сообщения",
        color = "Цвет embed-сообщения",
        title = "Заголовок embed",
        content = "Содержимое embed",
        image_link = "Ссылка на картинку (опционально)",
        footer_content = "Содержимое футера с указанием автора",
        embed_author = "Указать себя как автора"
    )
    @app_commands.autocomplete(color=color_autocomplete)
    #@app_commands.choices(color=[
    #    app_commands.Choice(name="🔴 Красный", value="red"),
    #    app_commands.Choice(name="🔵 Синий", value="blue"),
    #    app_commands.Choice(name="🟢 Зелёный", value="green"),
    #    app_commands.Choice(name="🟣 Фиолетовый", value="purple"),
    #    app_commands.Choice(name="🟡 Золотой", value="gold"),
    #    app_commands.Choice(name="🩵 Стандартный RMC_EMBED_COLOR", value="default"),
    #])
    @app_commands.choices(embed_author=[
        app_commands.Choice(name="Да", value=1),
        app_commands.Choice(name="Нет", value=0)
    ])
    async def send_embed(self, interaction: discord.Interaction, channel: discord.TextChannel, color: str, title: Optional[str], content: str, footer_content: Optional[str], embed_author: int, image_link: Optional[str] = None, ):
        
        if not await self.check_admin(interaction):
            await interaction.response.send_message("❌ Недостаточно прав", ephemeral=True)
            return
        
        settings_data = settings.load_settings()
        channel_id = settings_data.get('log_channel')
        log_channel = interaction.guild.get_channel(channel_id) if channel_id else None 

        timestamp = time.time()
        discord_time = f"<t:{int(timestamp)}:d>"

        embed_author_bool = bool(embed_author)

        #color_map = {
        #    "red": discord.Color.red(),
        #    "blue": discord.Color.blue(),
        #    "green": discord.Color.green(),
        #    "purple": discord.Color.purple(),
        #    "gold": discord.Color.gold(),
        #    "default": RMC_EMBED_COLOR
        #}

        try:
            if color.startswith('#'):
                color_int = int(color[1:], 16)
            elif color.startswith('0x'):
                color_int = int(color, 16)
            elif color.startswith('rgb(') and color.endswith(')'):
                rgb_values = color[4:-1].split(',')
                r, g, b = [int(x.strip()) for x in rgb_values]
                if not all(0 <= x <= 255 for x in (r, g, b)):
                    raise ValueError("RGB значения должны быть от 0 до 255")
                color_int = (r << 16) + (g << 8) + b
            elif ',' in color:
                rgb_values = color.split(',')
                r, g, b = [int(x.strip()) for x in rgb_values]
                if not all(0 <= x <= 255 for x in (r, g, b)):
                    raise ValueError("RGB значения должны быть от 0 до 255")
                color_int = (r << 16) + (g << 8) + b
            else:
                color_int = int(color)
        except ValueError as e:
            embed = discord.Embed(
                title="❌ Ошибка",
                description=f"Некорректный формат цвета. Используйте:\n"
                            f"• HEX: #FF0000\n"
                            f"• RGB: rgb(255,0,0) или 255,0,0\n"
                            f"• Или выберите из списка",
                color=RMC_EMBED_COLOR
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        embed_color = color_int

        if '\\n' in content:
            content = content.replace('\\n', '\n')

        try:
            if log_channel:
                embed = discord.Embed(
                    title="✅ Сообщение отправлено",
                    description=f"Сообщение отправлено в {channel.mention}.",
                    color=RMC_EMBED_COLOR,
                    timestamp=discord.utils.utcnow()
                )

                log_embed = discord.Embed(
                    title=f"Модератор отправил embed-сообщение через бота",
                    color=RMC_EMBED_COLOR
                )
                log_embed.add_field(
                    name="✍️ Автор embed-сообщения",
                    value=f"{interaction.user.mention} ({interaction.user.id})",
                    inline=False
                )
                log_embed.add_field(
                    name="📢 Канал",
                    value=f"{channel.mention}",
                    inline=True
                )
                if title:
                    log_embed.add_field(
                        name="🔍 Заголовок embed-сообщения",
                        value=f"```{title}```",
                        inline=False
                    )
                else:
                    log_embed.add_field(
                        name="🔍 Заголовок embed-сообщения",
                        value=f"Не указан",
                        inline=False
                    )
                log_embed.add_field(
                    name="📝 Текст embed-сообщения",
                    value=f"```{content}```",
                    inline=False
                )
                log_embed.add_field(
                    name="📅 Дата",
                    value=f"{discord_time}",
                    inline=True
                )
                if footer_content:
                    log_embed.add_field(
                        name="🔍 Содержимое футера",
                        value=f"```{footer_content}```",
                        inline=False
                    )
                else:
                    log_embed.add_field(
                        name="🔍 Содержимое футера",
                        value=f"Не указан",
                        inline=False
                    )
                log_embed.add_field(
                    name="👨‍💼 Указание авторства",
                    value="✅ Да" if embed_author_bool else "❌ Нет"
                )

                send_embed = discord.Embed(
                    title=title if title else "",
                    description=f"{content}",
                    color=embed_color,
                    timestamp=discord.utils.utcnow()
                )
                if footer_content:
                    send_embed.set_footer(
                        text=footer_content,
                        #icon_url=interaction.user.avatar.url
                    )
                if image_link:
                    send_embed.set_image(url=image_link) 
                    log_embed.add_field(
                        name="📷 С картинкой",
                        value="(приложена ниже)"
                    )
                    log_embed.set_image(url=image_link)
                else:
                    log_embed.add_field(
                        name="📷 Картинка отсутсвует",
                        value="К embed-сообщению не было приложено фотографии"
                    )
                if embed_author_bool:
                    send_embed.set_author(
                        name=interaction.user.display_name,
                        icon_url=interaction.user.avatar.url if interaction.user.avatar.url else None
                    )

                await channel.send(embed=send_embed)

                await interaction.response.send_message(embed=embed, ephemeral=True)
                await log_channel.send(embed=log_embed)
            else:
                embed = discord.Embed(
                    title="❌ Ошибка",
                    description=f"У бота не настроен канал для логов!",
                    color=RMC_EMBED_COLOR
                )
                embed.set_footer(
                    text="Для настройки используйте `/set_log`"
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
        except discord.Forbidden:
            embed = discord.Embed(
                title="❌ Ошибка",
                description=f"У бота нет прав писать в канал {channel.mention}",
                color=RMC_EMBED_COLOR
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return  
        except Exception as e:
            embed = discord.Embed(
                title="❌ Ошибка",
                description=f"У бота не получилось отправить сообщение из-за ошибки: ```{e}```",
                color=RMC_EMBED_COLOR
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return 

    @app_commands.command(
        name="react_on_msg",
        description="Прореагировать на сообщение от имени бота"
    )
    @app_commands.guild_only()
    @app_commands.describe(
        message_link = "Ссылка на целевое сообщение",
        emoji = "Эмоджи для реакции"
    )
    async def react_on_msg(self, interaction: discord.Interaction, message_link: str, emoji: str):
        if not await self.check_admin(interaction):
            await interaction.response.send_message("❌ Недостаточно прав", ephemeral=True)
            return
        
        settings_data = settings.load_settings()
        channel_id = settings_data.get('log_channel')
        log_channel = interaction.guild.get_channel(channel_id) if channel_id else None 

        if log_channel:
            try:
                parts = message_link.split('/')
                channel_id = int(parts[-2])
                message_id = int(parts[-1])

                timestamp = time.time()
                discord_time = f"<t:{int(timestamp)}:d>"

                channel = interaction.guild.get_channel(channel_id)

                if not channel:
                    embed = discord.Embed(
                        title="❌ Ошибка",
                        description=f"У бота не получилось найти канал для отправки реакции",
                        color=RMC_EMBED_COLOR
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return 
            
                message = await channel.fetch_message(message_id)
                await message.add_reaction(emoji)

                embed = discord.Embed(
                    title="✅ Реакция поставлена",
                    description=f'Бот поставил реакцию "{emoji}" на сообщение {message_link}',
                    color=RMC_EMBED_COLOR,
                    timestamp=discord.utils.utcnow()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)

                log_embed = discord.Embed(
                    title=f"Модератор поставил реакцию на сообщение через бота",
                    color=RMC_EMBED_COLOR
                )
                log_embed.add_field(
                    name="✍️ Автор реакции",
                    value=f"{interaction.user.mention} ({interaction.user.id})",
                    inline=False
                )
                log_embed.add_field(
                    name="📢 Канал",
                    value=f"{channel.mention}",
                    inline=True
                )
                log_embed.add_field(
                    name="💭 Реакция",
                    value=f"{emoji}",
                    inline=True
                )
                log_embed.add_field(
                    name="💬 Целевое сообщение",
                    value=f"{message_link}",
                    inline=False
                )
                log_embed.add_field(
                    name="📅 Дата",
                    value=f"{discord_time}",
                    inline=True
                )
                await log_channel.send(embed=log_embed)


            except discord.Forbidden as e:
                embed = discord.Embed(
                    title="❌ Ошибка",
                    description=f"У бота не получилось отправить реакцию из-за прав канала: ```{e}```",
                    color=RMC_EMBED_COLOR
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return 
            except Exception as e:
                embed = discord.Embed(
                    title="❌ Ошибка",
                    description=f"У бота не получилось отправить реакцию из-за ошибки: ```{e}```",
                    color=RMC_EMBED_COLOR
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return 
        else:    
            embed = discord.Embed(
                title="❌ Ошибка",
                description=f"У бота не настроен канал для логов!",
                color=RMC_EMBED_COLOR
            )
            embed.set_footer(
                text="Для настройки используйте `/set_log`"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="dm_user",
        description="Отправить сообщение в личные сообщения участника"
    )
    @app_commands.guild_only()
    @app_commands.describe(
        member = "Участник для отправки сообщения",
        content = "Содержимое сообщения"
    )
    async def dm_user(self, interaction: discord.Interaction, member: discord.Member, content: str):
        if not await self.check_admin(interaction):
            await interaction.response.send_message("❌ Недостаточно прав", ephemeral=True)
            return


        settings_data = settings.load_settings()
        channel_id = settings_data.get('log_channel')
        log_channel = interaction.guild.get_channel(channel_id) if channel_id else None 

        timestamp = time.time()
        discord_time = f"<t:{int(timestamp)}:d>"

        try:
            if log_channel:
                embed = discord.Embed(
                    title="✅ Сообщение отправлено",
                    description=f"Сообщение участинку {member.mention} отправлено!",
                    color=RMC_EMBED_COLOR,
                    timestamp=discord.utils.utcnow()
                )
                log_embed = discord.Embed(
                    title=f"Модератор отправил сообщение участнику через бота",
                    color=RMC_EMBED_COLOR
                )
                log_embed.add_field(
                    name="✍️ Автор сообщения",
                    value=f"{interaction.user.mention} ({interaction.user.id})",
                    inline=False
                )
                log_embed.add_field(
                    name="Целевой участник",
                    value=f"{member.mention}",
                    inline=True
                )
                log_embed.add_field(
                    name="📝 Текст сообщения",
                    value=f"```{content}```",
                    inline=False
                )
                log_embed.add_field(
                    name="📅 Дата",
                    value=f"{discord_time}",
                    inline=True
                )
                await member.send(content)
                await interaction.response.send_message(embed=embed, ephemeral=True)
                await log_channel.send(embed=log_embed)
            else:
                embed = discord.Embed(
                    title="❌ Ошибка",
                    description=f"У бота не настроен канал для логов!",
                    color=RMC_EMBED_COLOR
                )
                embed.set_footer(
                    text="Для настройки используйте `/set_log`"
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
        except discord.Forbidden:
            embed = discord.Embed(
                title="❌ Ошибка",
                description=f"Бот не смог отправить сообщение {member.mention}. Закрыты ЛС.",
                color=RMC_EMBED_COLOR
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return  
        except Exception as e:
            embed = discord.Embed(
                title="❌ Ошибка",
                description=f"У бота не получилось отправить сообщение из-за ошибки: ```{e}```",
                color=RMC_EMBED_COLOR
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return 
        
        

async def setup(bot: commands.Bot):
    await bot.add_cog(Messaging(bot))