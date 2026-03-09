import discord
import time
import random
import asyncio
from discord.ext import commands, tasks
from discord import app_commands
from utils.permissions import check_cog_access
from utils import settings_cache as settings
from constants import RMC_EMBED_COLOR

class Reactions(commands.Cog):
    """Cog для отправки реакций на случайные сообщения в выбранных каналах"""

    required_access = "admin"

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.emoji_task.start()

    @app_commands.command(
        name="add_reaction_channel",
        description="Добавить канал для реакций"
    )
    @app_commands.guild_only()
    async def add_reaction_channel(self, interaction:discord.Interaction, reaction_channel: discord.TextChannel):

        settings_data = settings.load_settings()

        if 'reaction_channels' not in settings_data:
            settings_data['reaction_channels'] = []
        if reaction_channel.id not in settings_data['reaction_channels']:

            settings_data['reaction_channels'].append(reaction_channel.id)
            settings.save_settings(settings_data)

            embed = discord.Embed(
                title="✅ Канал успешно установлен",
                description = f"Канал {reaction_channel.mention} успешно установлен для реакций",
                color=RMC_EMBED_COLOR,
                timestamp=discord.utils.utcnow()
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            embed = discord.Embed(
                title="❌ Канал уже установлен",
                description = f"Канал {reaction_channel.mention} уже установлен для реакций",
                color=RMC_EMBED_COLOR,
                timestamp=discord.utils.utcnow()
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="remove_reaction_channel",
        description="Удалить канал для реакций"
    )
    @app_commands.guild_only()
    async def remove_reaction_channel(self, interaction:discord.Interaction, reaction_channel: discord.TextChannel):

        settings_data = settings.load_settings()

        if 'reaction_channels' not in settings_data:
            settings_data['reaction_channels'] = []
        
        if reaction_channel.id in settings_data['reaction_channels']:

            settings_data['reaction_channels'].remove(reaction_channel.id)
            settings.save_settings(settings_data)
            
            embed = discord.Embed(
                title="✅ Канал удалён",
                description=f"Канал {reaction_channel.mention} удалён из списка каналов для реакций",
                color=RMC_EMBED_COLOR,
                timestamp=discord.utils.utcnow()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            embed = discord.Embed(
                title="❌ Канал не найден",
                description=f"Канал {reaction_channel.mention} не был в списке каналов для реакций",
                color=RMC_EMBED_COLOR,
                timestamp=discord.utils.utcnow()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(
        name="show_reaction_channels",
        description="Показать список каналов для реакций"  
    )
    @app_commands.guild_only()
    async def show_reaction_channels(self, interaction:discord.Interaction):

        settings_data = settings.load_settings()

        channel_ids = settings_data.get('reaction_channels', [])
        
        if channel_ids:
            
            channels_list = []

            for channel_id in settings_data['reaction_channels']:  
                channel = interaction.guild.get_channel(channel_id)
                if channel:
                    channels_list.append(f"• {channel.mention} (`{channel_id}`)")
                else:
                    channels_list.append(f"• ~~Канал удалён~~ (`{channel_id}`)")

            channels_text = "\n".join(channels_list)
            
            embed = discord.Embed(
                title="📋 Список каналов для реакций",
                description=channels_text,
                color=RMC_EMBED_COLOR,
                timestamp=discord.utils.utcnow()
            )
            embed.set_footer(text=f"Всего каналов: {len(channels_list)}")
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            embed = discord.Embed(
                title="❌ Каналы не найдены",
                description=f"Ни один канал не установлен для реакций",
                color=RMC_EMBED_COLOR,
                timestamp=discord.utils.utcnow()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="set_reaction_frequency",
        description="Установить частоту проверки количества сообщений (в секундах)"
    )
    @app_commands.guild_only()
    @app_commands.describe(
        seconds = "Время в секундах"
    )
    async def set_reaction_frequency(self, interaction: discord.Interaction, seconds: int):
        if seconds < 10:
            embed = discord.Embed(
                title="❌ Ошибка",
                description=f"Частота не может быть меньше 10 секунд",
                color=RMC_EMBED_COLOR,
                timestamp=discord.utils.utcnow()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        settings_data = settings.load_settings()
        settings_data['reaction_frequency'] = seconds
        settings.save_settings(settings_data)

        self.emoji_task.change_interval(seconds=seconds)

        embed = discord.Embed(
            title="✅ Частота установлена успешно",
            description=f"Новая частота: `{seconds}`",
            color=RMC_EMBED_COLOR,
            timestamp=discord.utils.utcnow()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return



    @tasks.loop(seconds=60)  # значение по умолчанию
    async def emoji_task(self):
        settings_data = settings.load_settings()
        
        # Получаем настройки
        channels = settings_data.get('reaction_channels', [])
        emojis = settings_data.get('reaction_emojis')  # дефолтные реакции
        chance = settings_data.get('reaction_chance', 10)  # шанс 10%
        
        if not channels or not emojis:
            return  # нет каналов или реакций — выходим
        
        # Проходим по всем каналам
        for channel_id in channels:
            channel = self.bot.get_channel(channel_id)
            if not channel:
                continue
            
            try:
                # Получаем последние сообщения в канале
                async for message in channel.history(limit=10):
                    # Проверяем, что сообщение не от бота
                    if message.author.bot:
                        continue
                    
                    # Проверяем, не ставили ли мы уже реакции
                    if message.reactions:   
                        continue
                    
                    # Случайный шанс
                    if random.randint(1, 100) <= chance:
                        # Выбираем случайную реакцию
                        emoji = random.choice(emojis)
                        
                        try:
                            await message.add_reaction(emoji)
                        except discord.Forbidden:
                            continue  # нет прав — пропускаем
                        except discord.HTTPException:
                            continue  # ошибка API — пропускаем
                        
                        # Ставим только на одно сообщение за проход
                        break
                        
            except discord.Forbidden:
                continue  # нет доступа к каналу
            except Exception as e:
                print(f"Ошибка в канале {channel_id}: {e}")
                continue

async def setup(bot: commands.Bot):
    await bot.add_cog(Reactions(bot))