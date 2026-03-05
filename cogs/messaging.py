import discord
import time
from discord.ext import commands
from discord import app_commands
from utils.permissions import check_cog_access
from utils import settings_cache as settings
from discord.ui import View, Button
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

class DirectMessage(commands.Cog):
    "Cog для отправки сообщений в ЛС участникам сервера от имени бота."
    required_access = "admin"

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_check(self, ctx: commands.Context):
        allowed = await check_cog_access(ctx, self.required_access)
        if not allowed:
            raise commands.CheckFailure()
        return True
    
    @app_commands.command(
        name="dm_user",
        description="Отправить личное сообщение участнику"
    )
    @app_commands.guild_only()
    @app_commands.choices(anonymous=[
        app_commands.Choice(name="Да", value=1),
        app_commands.Choice(name="Нет", value=0),
    ])
    @app_commands.describe(
        member = "Адресат сообщения",
        message = "Сообщение",
        anonymous = "Анонимность сообщения",
        #log_channel = "Канал для отправки лога"
    )
    @app_commands.choices(allow_response=[
        app_commands.Choice(name="Да", value=1),
        app_commands.Choice(name="Нет", value=0),
    ])
    async def dm_user(self, interaction: discord.Interaction, member: discord.Member, message: str, anonymous: int, allow_response: int = 0):
        
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
                    title=f"Участнику отправлено сообщение",
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

async def setup(bot: commands.Bot):
    await bot.add_cog(DirectMessage(bot))