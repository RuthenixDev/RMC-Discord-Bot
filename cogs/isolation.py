import discord
import os
import json
import time
import aiofiles
from datetime import datetime
from discord.ext import commands
from discord import app_commands
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict
from utils.exceptions import NoLogChannelError
from utils.permissions import check_cog_access
from utils import settings_cache as settings
from constants import RMC_EMBED_COLOR

isolated_users = "isolated_users.json"

@dataclass
class IsolatedUser:
    roles: List[int]
    isolated_at: Optional[float] = None
    isolated_by: Optional[int] = None
    reason: str = "Не указана" # Дефолтное значение уже вшито!

    # Бонус: вшиваем генерацию красивого времени Discord прямо в класс
    @property
    def formatted_time(self) -> str:
        return f"<t:{int(self.isolated_at)}:d>" if self.isolated_at else "Неизвестно"

class Isolation(commands.Cog):
    """Cog изоляции участников"""
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
    
    async def _load_isolated_data(self) -> dict:
        """Async-загрузка данных об изолированных участниках из JSON-файла"""
        if not os.path.exists(isolated_users):
            return {}
        try:
            async with aiofiles.open(isolated_users, mode='r', encoding='utf-8') as f:
                content = await f.read()
                if not content:
                    return {}
                
                raw_data = json.loads(content)
                
                return {
                    user_id: IsolatedUser(
                        roles=data.get("roles", []),
                        isolated_at=data.get("isolated_at"),
                        isolated_by=data.get("isolated_by"),
                        reason=data.get("reason", "Не указана")
                    )
                    for user_id, data in raw_data.items()
                }
        except json.JSONDecodeError:
            return {}
        
    async def _save_isolated_data(self, data: dict):
        """Async-сохранение данных об изолированных участниках в JSON-файл"""
        raw_data = {user_id: asdict(user_obj) for user_id, user_obj in data.items()}

        async with aiofiles.open(isolated_users, mode='w', encoding='utf-8') as f:
            await f.write(json.dumps(raw_data, indent=4, ensure_ascii=False))

    def _create_embed(self, title: str, description: str = "") -> discord.Embed:
        embed = discord.Embed(
            title=title,
            description=description,
            color=RMC_EMBED_COLOR,
            timestamp=discord.utils.utcnow()
        )
        return embed
    # Использование:
# await interaction.response.send_message(embed=self._create_embed("❌ Ошибка", "Недостаточно прав", True))
    
    
    @app_commands.command(
        name="isolate_settings",
        description="Настройки изоляции"
    )
    @app_commands.guild_only()
    @app_commands.describe(
        isolation_role = "Роль изоляции",
        #log_channel = "Канал для логов"
    )
    async def isolate_settings(self, interaction: discord.Interaction, isolation_role: Optional[discord.Role]):
        if not await self.check_admin(interaction):
            await interaction.response.send_message("❌ Недостаточно прав", ephemeral=True)
            return

        settings_data = settings.load_settings()

        if isolation_role is None:
            saved_role_id = settings_data.get('isolation_role_id')
            role_object = interaction.guild.get_role(saved_role_id) if saved_role_id else None

            saved_channel_id = settings_data.get('log_channel')
            channel_object = interaction.guild.get_channel(saved_channel_id) if saved_channel_id else None

            role_text = role_object.mention if role_object else "❌Не настроена"
            channel_text = channel_object.mention if channel_object else "❌Не настроен"
            #print("Не было указаны роли, публикую сохранённые настройки")
            embed = discord.Embed(
                title="⚙️Сохранённые настройки",
                description=f"В настройках сохранено следующее: \n - Роль изоляции: {role_text} \n - Канал для логов (установить в /set_log): {channel_text}",
                color=RMC_EMBED_COLOR,
                timestamp=discord.utils.utcnow()
            )
            await interaction.response.send_message(embed=embed)
            return

        changes = []
        needs_save = False
        if isolation_role:
            if isolation_role >= interaction.guild.me.top_role:
                embed = self._create_embed("❌Ошибка", "Для изоляции нельзя назначить роль, которая выше роли бота!!")
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            if isolation_role.is_default():
                embed = self._create_embed("❌Ошибка", "Для изоляции нельзя назначить `@everyone`!")
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            else: 
                settings_data['isolation_role_id'] = isolation_role.id
                changes.append(f"Роль {isolation_role.mention}")
                needs_save = True

        if needs_save:
            settings.save_settings(settings_data)

            if len(changes) == 1:
                desc = f"Установлен {changes[0]}"
            else:
                desc = f"Установлены: \n- {changes[0]} \n- {changes[1]}"

            embed = discord.Embed(
                title="✅Настройки изменены успешно",
                description = desc,
                color=RMC_EMBED_COLOR,
                timestamp=discord.utils.utcnow()
            )
            await interaction.response.send_message(embed=embed)

        else: 
            embed = discord.Embed(
                title="❌Ошибка",
                description="К сожалению, что-то пошло не так, и бот вызвал это сообщение об ошибке. Пожалуйста, обратитесь к команде проекта.",
                color=RMC_EMBED_COLOR,
                timestamp=discord.utils.utcnow()
            )
            await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="isolate",
        description="Отправить участника в изолятор"
    )
    @app_commands.guild_only()
    @app_commands.describe(
        isolation_member="Участник для изоляции",
    )
    async def isolate(self, interaction: discord.Interaction, isolation_member: discord.User, isolation_reason: Optional[str]):
        if not await self.check_admin(interaction):
            await interaction.response.send_message("❌ Недостаточно прав", ephemeral=True)
            return

        if isolation_member.id == interaction.user.id:
            embed = self._create_embed("❌Ошибка при изоляции", "Вы не можете изолировать себя!")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        try:
            await interaction.response.defer(ephemeral=True)
            
            user_id = str(isolation_member.id)
            user_fetched = await self.bot.fetch_user(isolation_member.id)
            user_name = user_fetched.global_name or user_fetched.name
            member = interaction.guild.get_member(isolation_member.id)

            isolated_data = await self._load_isolated_data()

            if user_id in isolated_data:
                embed = self._create_embed("❌Ошибка", "Пользователь уже изолирован!")
                embed.set_footer(text="Проверьте список изолированных пользователей через /isolate_list.")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            settings_data = settings.load_settings()
            role_id = settings_data.get('isolation_role_id')
            channel_id = settings_data.get('log_channel')

            isolation_role = interaction.guild.get_role(role_id) if role_id else None
            log_channel = interaction.guild.get_channel(channel_id) if channel_id else None 

            if not log_channel:
                raise NoLogChannelError()

            if not isolation_role:
                embed = self._create_embed("❌Ошибка", "Не назначена роль изоляции!")
                embed.set_footer(text="Для настройки используйте /isolate_settings.")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            role_ids = []
            
            if member:
                admin_roles = settings_data.get('admin_roles', [])
                isolation_member_roles = []
                
                for role in member.roles:
                    if not role.is_default() and not role.managed and role != isolation_role:
                        if role.id in admin_roles:
                            embed = self._create_embed(
                                "❌Ошибка при изоляции", 
                                "У выбранного участника есть роль, которая отмечена как административная."
                            )
                            await interaction.followup.send(embed=embed, ephemeral=True)
                            return
                        isolation_member_roles.append(role)

                role_ids = [role.id for role in isolation_member_roles]

                if isolation_member_roles:
                    await member.remove_roles(*isolation_member_roles)
                await member.add_roles(isolation_role, reason=f"Изолирован {interaction.user}: {isolation_reason}")

            isolated_data[user_id] = IsolatedUser(
                roles=role_ids,
                isolated_at=time.time(),
                isolated_by=interaction.user.id,
                reason=isolation_reason if isolation_reason else "Не указана"
            )
            await self._save_isolated_data(isolated_data)
            
            status_text = "изолирован" if member else "изолирован заочно"
            response_embed = self._create_embed("✅Успешная изоляция", f"Пользователь {isolation_member.mention} {status_text}!")
            response_embed.add_field(name="Причина", value=isolation_reason if isolation_reason else "❌Причина не указана")
            await interaction.followup.send(embed=response_embed, ephemeral=True)

            if log_channel:
                user_data = isolated_data[user_id]
                log_embed = self._create_embed("Пользователь был изолирован")
                log_embed.add_field(
                    name="Изолирован",
                    value=f"<@{user_id}> **{user_name}**\nID: `{user_id}`\n",
                    inline=False
                )
                log_embed.add_field(
                    name="Изолировал",
                    value=f"{interaction.user.mention}\n`{interaction.user.id}`",
                    inline=False
                )
                log_embed.add_field(
                    name="Причина",
                    value=f"```{user_data.reason}```"
                )
                log_embed.add_field(
                    name="Дата изоляции",
                    value=f"{user_data.formatted_time}",
                    inline=True
                )
                await log_channel.send(embed=log_embed)

        except NoLogChannelError:
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Не настроен канал логов!", ephemeral=True)
            else:
                await interaction.followup.send("❌ Не настроен канал логов!", ephemeral=True)
        except Exception as e:
            import traceback
            traceback.print_exc()
            if not interaction.response.is_done():
                await interaction.response.send_message(f"❌ Ошибка: {e}", ephemeral=True)
            else:
                await interaction.followup.send(f"❌ Ошибка: {e}", ephemeral=True)
        
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Возвращает участника в изолятор (авто-возврат или заочная изоляция)."""
        
        user_id = str(member.id)
        isolated_data = await self._load_isolated_data() 
        
        if user_id in isolated_data:
            user_data = isolated_data[user_id]
            reason = user_data.reason
            time_text = user_data.formatted_time
            isolated_by = user_data.isolated_by  

            is_preemptive = len(user_data.roles) == 0

            title_text = "🔒 Применение заочной изоляции" if is_preemptive else "⚠️ Попытка обхода изоляции"
            description_text = (
                f"Пользователь {member.mention} зашёл на сервер и получил ранее назначенную роль изоляции."
                if is_preemptive else
                f"Пользователь {member.mention} попытался снять изоляцию через перезаход, роль была возвращена."
            )

            # Ищем модератора
            moderator_text = "Неизвестно"
            if isolated_by:
                moderator = member.guild.get_member(int(isolated_by))
                if not moderator:
                    try:
                        moderator = await member.guild.fetch_member(int(isolated_by))
                    except discord.NotFound:
                        moderator = None
                
                moderator_text = moderator.mention if moderator else f"<@{isolated_by}>"

            settings_data = settings.load_settings()
            role_id = settings_data.get('isolation_role_id')

            if role_id:
                isolation_role = member.guild.get_role(role_id)
                if isolation_role:
                    try:
                        # Выдаем роль
                        await member.add_roles(isolation_role, reason="Автоматическая изоляция при входе.")

                        # Логируем
                        channel_id = settings_data.get('log_channel')
                        if channel_id:
                            log_channel = member.guild.get_channel(channel_id)
                            if log_channel:
                                # Создаем эмбед ОДИН раз с правильными данными
                                warning_embed = self._create_embed(
                                    title=title_text,
                                    description=description_text,
                                )
                                warning_embed.add_field(
                                    name="Пользователь",
                                    value=f"{member.mention}\n`{member}`\n`{member.id}`",
                                    inline=False
                                )
                                warning_embed.add_field(
                                    name="Изолировал",
                                    value=moderator_text,
                                    inline=True
                                )
                                warning_embed.add_field(
                                    name="Дата изоляции",
                                    value=time_text,
                                    inline=True
                                )
                                warning_embed.add_field(
                                    name="Причина",
                                    value=f"```{reason}```",
                                    inline=False
                                )

                                await log_channel.send(embed=warning_embed)
                                
                    except discord.Forbidden:
                        print(f"Ошибка: У бота нет прав выдать роль участнику {member.id}.")

    @app_commands.command(
        name="unisolate",
        description="Вернуть участника из изолятора (поддерживает ID)"
    )
    @app_commands.guild_only()
    @app_commands.describe(
        unisolation_user="Выберите пользователя из списка или введите его ID",
        unisolation_reason="Причина снятия изоляции"
    )
    async def unisolate(self, interaction: discord.Interaction, unisolation_user: str, unisolation_reason: Optional[str] = None):
        if not await self.check_admin(interaction):
            await interaction.response.send_message("❌ Недостаточно прав", ephemeral=True)
            return

        try:
            # 1. Пытаемся получить ID из введенной строки
            try:
                user_id_int = int(unisolation_user.strip())
                user_id_str = str(user_id_int)
            except ValueError:
                await interaction.response.send_message("❌ Неверный формат ID. Введите число.", ephemeral=True)
                return

            settings_data = settings.load_settings()
            isolate_role_id = settings_data.get('isolation_role_id')
            role_object = interaction.guild.get_role(isolate_role_id) if isolate_role_id else None
            
            channel_id = settings_data.get('log_channel')
            log_channel = interaction.guild.get_channel(channel_id) if channel_id else None 

            if not log_channel:
                raise NoLogChannelError()

            if not role_object:
                embed = self._create_embed("❌ Ошибка", "Не назначена роль изоляции в настройках!")
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            await interaction.response.defer(ephemeral=True)
            
            isolated_data = await self._load_isolated_data()

            # Проверяем, есть ли пользователь в базе данных
            if user_id_str not in isolated_data:
                embed = self._create_embed("❌ Ошибка", "Этот пользователь не числится в списке изолированных.")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            user_data = isolated_data[user_id_str]
            
            # Пытаемся найти участника на сервере (member может быть None, если он вышел)
            member = interaction.guild.get_member(user_id_int)
            # Если get_member не нашел, пробуем fetch_member (запрос к API)
            if not member:
                try:
                    member = await interaction.guild.fetch_member(user_id_int)
                except:
                    member = None

            # 2. Логика восстановления ролей, если пользователь на сервере
            if member:
                roles_to_restore = []
                # Предполагаем, что user_data — это объект или словарь с атрибутом roles
                # Если это словарь, используйте user_data['roles']
                stored_roles = getattr(user_data, 'roles', []) 
                
                for r_id in stored_roles:
                    role = interaction.guild.get_role(r_id)
                    if role and role.id != role_object.id:
                        roles_to_restore.append(role)

                try:
                    await member.remove_roles(role_object, reason=f"Снятие изоляции: {unisolation_reason}")
                    if roles_to_restore:
                        await member.add_roles(*roles_to_restore, reason=f"Восстановление ролей: {unisolation_reason}")
                except discord.Forbidden:
                    # Если у бота нет прав управлять ролями этого юзера
                    pass

            # 3. Удаляем из базы данных в любом случае
            del isolated_data[user_id_str]
            await self._save_isolated_data(isolated_data)

            # Формируем ответ
            mention_str = member.mention if member else f"Пользователь с ID `{user_id_str}`"
            
            response_embed = self._create_embed(
                "✅ Успешное возращение",
                f"Пользователь {mention_str} был возвращён из изоляции."
            )
            response_embed.add_field(name="Причина возвращения", value=unisolation_reason or "Не указана")
            await interaction.followup.send(embed=response_embed, ephemeral=True)

            # Логгирование
            log_embed = self._create_embed("Участник был возвращён")
            log_embed.add_field(
                name="Пользователь",
                value=f"{mention_str}\nID: `{user_id_str}`",
                inline=False
            )
            log_embed.add_field(name="Кем возвращён", value=interaction.user.mention, inline=True)
            
            # Безопасное получение времени
            iso_time = getattr(user_data, 'formatted_time', 'Неизвестно')
            log_embed.add_field(name="Дата изоляции", value=iso_time, inline=True)
            log_embed.add_field(name="Причина возвращения", value=f"```{unisolation_reason or 'Не указана'}```", inline=False)
            
            await log_channel.send(embed=log_embed)

        except NoLogChannelError:
            if interaction.response.is_done():
                await interaction.followup.send("❌ Ошибка: не настроен канал логов.", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Ошибка: не настроен канал логов.", ephemeral=True)
        except Exception as e:
            import traceback
            traceback.print_exc()
            msg = f"❌ Критическая ошибка: {e}"
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)

    @unisolate.autocomplete("unisolation_user")
    async def isolated_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        choices = []
        if not os.path.exists(isolated_users):
            return []

        try:
            async with aiofiles.open(isolated_users, mode='r', encoding='utf-8') as f:
                content = await f.read()
                isolated_data = json.loads(content) if content else {}
        except:
            return []

        for user_id_str in isolated_data.keys():
            user_id = int(user_id_str)
            member = interaction.guild.get_member(user_id)
            
            if member:
                label = f"{member.display_name} (@{member.name})"
            else:
                label = f"Вне сервера (ID: {user_id_str})"

            if current.lower() in label.lower() or current in user_id_str:
                choices.append(app_commands.Choice(name=label, value=user_id_str))

        return choices[:25]

    @app_commands.command(
        name="isolate_list",
        description="Посмотреть список изолированных участников"
    )
    @app_commands.guild_only()
    async def isolate_list(self, interaction: discord.Interaction):
        if not await self.check_admin(interaction):
            await interaction.response.send_message("❌ Недостаточно прав", ephemeral=True)
            return

        isolated_data = await self._load_isolated_data()
        
        embed = self._create_embed("📋 Список изолированных участников")

        await interaction.response.defer()

        if isolated_data:
            for user_id_str, user_data in isolated_data.items():
                user_id = int(user_id_str)
                
                reason = user_data.reason
                discord_time = user_data.formatted_time
                isolated_by = user_data.isolated_by
                
                member = interaction.guild.get_member(user_id)
                if not member:
                    try:
                        member = await interaction.guild.fetch_member(user_id)
                    except discord.NotFound:
                        member = None
                
                moderator_text = "Неизвестно"
                if isolated_by:
                    mod_member = interaction.guild.get_member(int(isolated_by))
                    if not mod_member:
                        try:
                            mod_member = await interaction.guild.fetch_member(int(isolated_by))
                        except discord.NotFound:
                            mod_member = None
                            
                    moderator_text = mod_member.mention if mod_member else f"<@{isolated_by}>"
                
                if member:
                    embed.add_field(
                        name=f"{member.display_name}",
                        value=f"Участник: {member.mention} `{user_id}`\nДата: {discord_time} \nМодератор: {moderator_text} \nПричина:`{reason}`",
                        inline=False
                    )
                else:
                    embed.add_field(
                        name="❌ Участник покинул сервер",
                        value=f"ID: `{user_id}`\nПричина: `{reason}`\nВремя: {discord_time}",
                        inline=False
                    )
            
            await interaction.followup.send(embed=embed)
        else:
            embed.description = "✅ Изолированные участники отсутствуют"
            await interaction.followup.send(embed=embed)

           



async def setup(bot: commands.Bot):
    await bot.add_cog(Isolation(bot))