import discord
import datetime
from discord.ext import commands
from discord import app_commands
import aiohttp
from discord import Webhook
from main import RMC_EMBED_COLOR
from main import BOT_TOKEN
from utils import settings_cache as settings


class Resolution(commands.Cog):
    """Cog для написания резолюций"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="resolution",
        description="Создать резолюцию"
    )
    @app_commands.guild_only()
    async def resolution(self, interaction: discord.Interaction):
        """Создать резолюцию"""
        # Проверка на админа
        data = settings.load_settings()
        admin_roles = data.get("admin_roles", [])
        user_roles = [role.id for role in interaction.user.roles]
        is_admin = interaction.user.guild_permissions.administrator or any(role_id in user_roles for role_id in admin_roles)

        if is_admin:
            modal = ResolutionModal(
                channel=interaction.channel,
                guild=interaction.guild,
                author=interaction.user,
                bot=self.bot
            )
            await interaction.response.send_modal(modal)
        else:
            await interaction.response.send_message(
                "❌ У вас недостаточно прав для публикации резолюций",
                ephemeral=True
            )


class ResolutionModal(discord.ui.Modal, title="Создание резолюции"):
    number = discord.ui.TextInput(
        label="Номер резолюции",
        placeholder="Например: 23",
        max_length=10
    )
    title_input = discord.ui.TextInput(
        label="Название резолюции",
        placeholder="Например: О бане Кирилла",
        max_length=100
    )
    description = discord.ui.TextInput(
        label="Описание резолюции",
        placeholder="Опиши суть",
        style=discord.TextStyle.paragraph,
        max_length=2000
    )
    duration = discord.ui.TextInput(
        label="Время для голосования (максимум неделя)",
        placeholder="Например: 7",
        max_length=2
    )

    def __init__(self, channel: discord.TextChannel, guild: discord.Guild, author: discord.Member, bot: commands.Bot):
        super().__init__()
        self.channel = channel
        self.guild = guild
        self.author = author
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        print(f"[ResolutionModal] submitted by {interaction.user} in {self.channel} (guild {self.guild})")
        
        # Проверяем число
        try:
            duration_days = int(self.duration.value)
            if duration_days < 1 or duration_days > 7:
                await interaction.response.send_message(
                    "❌ Длительность голосования должна быть от 1 до 7 дней!",
                    ephemeral=True
                )
                return
        except ValueError:
            await interaction.response.send_message(
                "❌ Неверный формат времени! Укажите число.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"Резолюция #{self.number.value}: {self.title_input.value}",
            description=self.description.value,
            color=RMC_EMBED_COLOR,
            timestamp=discord.utils.utcnow()
        )
        embed.set_footer(text=f"Автор: {self.author.display_name}")

        # Сначала отвечаем на взаимодействие
        await interaction.response.send_message("✅ Резолюция публикуется...", ephemeral=True)
        
        # Отправляем резолюцию в канал
        resolution_message = await self.channel.send(content="@everyone", embed=embed)
        
        # Создаем опрос через HTTP запрос
        await self.create_poll(interaction, duration_days)

    async def create_poll(self, interaction: discord.Interaction, duration_days: int):
        """Создает опрос через прямой HTTP запрос к Discord API"""
        try:
            headers = {
                "Authorization": f"Bot {BOT_TOKEN}",
                "Content-Type": "application/json"
            }
            
            poll_data = {
                "poll": {
                    "question": {
                        "text": f"Резолюция #{self.number.value}: {self.title_input.value}"
                    },
                    "answers": [
                        {"poll_media": {"text": "За", "emoji": {"id": 1422601900737560656, "name": "approved"}}}, #<:approved:1422601900737560656>
                        {"poll_media": {"text": "Против", "emoji": {"id": 1422601837370146969, "name": "declined"}}}, #<:declined:1422601837370146969>
                        {"poll_media": {"text": "Воздерживаюсь", "emoji": {"id": 1422601751336321096,"name": "abstained"}}} #<:abstained:1422601751336321096>
                    ],
                    "duration": duration_days * 24,  # Конвертируем дни в часы
                    "allow_multiselect": False
                }
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"https://discord.com/api/v10/channels/{self.channel.id}/messages",
                    headers=headers,
                    json=poll_data
                ) as response:
                    
                    if response.status == 200:
                        print(f"[ResolutionModal] Poll created successfully in channel {self.channel.id}")
                    else:
                        error_text = await response.text()
                        print(f"[ResolutionModal] Failed to create poll: {response.status} - {error_text}")
                        
                        # Отправляем сообщение об ошибке
                        error_embed = discord.Embed(
                            title="❌ Ошибка при создании опроса",
                            description="Не удалось создать опрос для голосования. Проверьте права бота.",
                            color=0xff0000
                        )
                        await self.channel.send(embed=error_embed)
                        
        except Exception as e:
            print(f"[ResolutionModal] Error creating poll: {e}")
            
            # Отправляем сообщение об ошибке
            error_embed = discord.Embed(
                title="❌ Ошибка при создании опроса",
                description=f"Произошла ошибка: {str(e)}",
                color=0xff0000
            )
            await self.channel.send(embed=error_embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Resolution(bot))