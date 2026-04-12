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
    async def isolate(self, interaction: discord.Interaction, isolation_member: discord.Member, isolation_reason: Optional[str]):
        if not await self.check_admin(interaction):
            await interaction.response.send_message("❌ Недостаточно прав", ephemeral=True)
            return

        if isolation_member == interaction.user:
            embed = self._create_embed("❌Ошибка при изоляции", "Вы не можете изолировать себя!")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        try:
            
            
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
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            try:
                isolation_member_roles = []
                for role in isolation_member.roles:
                    if not role.is_default() and not role.managed and role != isolation_role:
                        isolation_member_roles.append(role)

                role_ids = [role.id for role in isolation_member_roles]
                member = isolation_member 
                user_id = str(isolation_member.id)
                admin_roles = settings_data.get('admin_roles', [])

                if any(role_id in admin_roles for role_id in role_ids):
                    embed = self._create_embed(
                        "❌Ошибка при изоляции", 
                        "У выбранного участника есть роль, которая отмечена как административная."
                    )
                    embed.set_footer(text="Для просмотра списка — /listadmins.")
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return

                isolated_data = await self._load_isolated_data()

                if user_id in isolated_data:
                    embed = self._create_embed("❌Ошибка при изоляции", "Выбранный участник уже изолирован!")
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return
                else:
                    isolated_data[user_id] = IsolatedUser(
                        roles=role_ids,
                        isolated_at=time.time(),
                        isolated_by=interaction.user.id,
                        reason=isolation_reason if isolation_reason else "Не указана"
                    )
                    await self._save_isolated_data(isolated_data)

                await interaction.response.defer(ephemeral=True)
                if isolation_member_roles:
                    await isolation_member.remove_roles(*isolation_member_roles)
    
                await isolation_member.add_roles(isolation_role, reason=f"Изолирован {interaction.user} по причине «{isolation_reason}».")
                
                response_embed = self._create_embed("✅Успешная изоляция", f"Участник {isolation_member.mention} изолирован!")
                
                if isolation_reason:
                    response_embed.add_field(name="Причина", value=f"{isolation_reason}")
                else:
                    response_embed.add_field(name="Причина", value="❌Причина не указана")
                
                await interaction.followup.send(embed=response_embed, ephemeral=True)

                if log_channel:
                    user_data = isolated_data[user_id]
                    
                    log_embed = self._create_embed("Участник был изолирован")
                    log_embed.add_field(
                        name="Изолирован",
                        value=f"{member.mention} \n `{member}` \n `{member.id}`",
                        inline=False
                    )
                    log_embed.add_field(
                        name="Изолировал",
                        value=f"{interaction.user.mention} \n `{interaction.user}` \n `{interaction.user.id}`",
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

            except discord.Forbidden:
                embed = self._create_embed("❌Ошибка при изоляции", "У бота недостаточно прав для изоляции")
                if not interaction.response.is_done():
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                else:
                    await interaction.followup.send(embed=embed, ephemeral=True)
                return
        except NoLogChannelError:
            raise
        except Exception as e:
            print(f"ОШИБКА в isolate: {e}")
            import traceback
            traceback.print_exc()
            
            if not interaction.response.is_done():
                await interaction.response.send_message(f"❌ Ошибка: {e}", ephemeral=True)
            else:
                await interaction.followup.send(f"❌ Ошибка: {e}", ephemeral=True)
        
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Возвращает участника в изолятор при попытке обхода через перезаход на сервер."""
        
        user_id = str(member.id)
        
        isolated_data = await self._load_isolated_data() 
        
        if user_id in isolated_data:
            user_data = isolated_data[user_id]
            reason = user_data.reason
            time_text = user_data.formatted_time
            isolated_by = user_data.isolated_by  

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
                        await member.add_roles(isolation_role, reason="Автоматический возврат изоляции после перезахода.")

                        channel_id = settings_data.get('log_channel')
                        if channel_id:
                            log_channel = member.guild.get_channel(channel_id)
                            if log_channel:
                                
                                warning_embed = self._create_embed(
                                    title="⚠️ Попытка обхода изоляции",
                                    description=f"Пользователь {member.mention} попытался снять изоляцию через перезаход на сервер, но роль была возвращена.",
                                )
                                warning_embed.add_field(
                                    name="Пользователь",
                                    value=f"{member.mention}\n`{member}`\n`{member.id}`",
                                    inline=False
                                )
                                warning_embed.add_field(
                                    name="Модератор",
                                    value=moderator_text
                                )
                                warning_embed.add_field(
                                    name="Причина изоляции",
                                    value=f"`{reason}`"
                                )
                                warning_embed.add_field(
                                    name="Дата изоляции",
                                    value=f"{time_text}"
                                )

                                await log_channel.send(embed=warning_embed)
                                
                    except discord.Forbidden:
                        print(f"Ошибка: У бота нет прав выдать роль участнику {member.id}.")

    @app_commands.command(
        name="unisolate",
        description="Вернуть участника из изолятора"
    )
    @app_commands.guild_only()
    @app_commands.describe(
        unisolation_member="Участник для помилования",
    )
    async def unisolate(self, interaction: discord.Interaction, unisolation_member: discord.Member, unisolation_reason: Optional[str] = None):
        if not await self.check_admin(interaction):
            await interaction.response.send_message("❌ Недостаточно прав", ephemeral=True)
            return

        try:
            member = unisolation_member 
            user_id = str(member.id)

            settings_data = settings.load_settings()

            isolate_role = settings_data.get('isolation_role_id')
            role_object = interaction.guild.get_role(isolate_role) if isolate_role else None

            channel_id = settings_data.get('log_channel')
            log_channel = interaction.guild.get_channel(channel_id) if channel_id else None 

            if not log_channel:
                raise NoLogChannelError()

            if not role_object:
                embed = self._create_embed("❌Ошибка", "Не назначена роль изоляции!")
                embed.set_footer(text="Для настройки используйте /isolate_settings.")
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            await interaction.response.defer(ephemeral=True)
            
            isolated_data = await self._load_isolated_data()

            if user_id in isolated_data:
                user_data = isolated_data[user_id]
                
                roles_to_restore = []
                for role_id in user_data.roles:
                    role = interaction.guild.get_role(role_id)
                    if role:
                        roles_to_restore.append(role)

                await member.remove_roles(role_object, reason=f"Модератор {interaction.user} снял изоляцию по причине {unisolation_reason}")

                if roles_to_restore:
                    await member.add_roles(*roles_to_restore, reason=f"Модератор {interaction.user} снял изоляцию по причине {unisolation_reason}")

                del isolated_data[user_id]
                await self._save_isolated_data(isolated_data)

                response_embed = self._create_embed(
                    "✅Успешное возвращение",
                    f"Участник {member.mention} был возвращён из изолятора!"
                )
                
                if unisolation_reason:
                    response_embed.add_field(name="Причина", value=f"{unisolation_reason}")
                else:
                    response_embed.add_field(name="Причина", value="❌Причина не указана")
                
                await interaction.followup.send(embed=response_embed, ephemeral=True)

                log_embed = self._create_embed("Участник был возвращён")
                log_embed.add_field(
                    name="Возвратился",
                    value=f"{member.mention} \n `{member}` \n `{member.id}`",
                    inline=False
                )
                log_embed.add_field(
                    name="Возвратил",
                    value=f"{interaction.user.mention} \n `{interaction.user}` \n `{interaction.user.id}`",
                    inline=False
                )
                log_embed.add_field(
                    name="Причина возвращения",
                    value=f"```{unisolation_reason}```"
                )
                log_embed.add_field(
                    name="Причина изоляции",
                    value=f"`{user_data.reason}`"
                )
                log_embed.add_field(
                    name="Дата изоляции",
                    value=f"{user_data.formatted_time}"
                )
                
                await log_channel.send(embed=log_embed)

            else:
                embed = self._create_embed("❌Ошибка при возвращении из изоляции", "Выбранный участник ещё не изолирован!")
                
                if not interaction.response.is_done():
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                else:
                    await interaction.followup.send(embed=embed, ephemeral=True)
                return
        except NoLogChannelError:
            raise         
        except Exception as e:
            print(f"ОШИБКА в unisolate: {e}")
            import traceback
            traceback.print_exc()
            
            if not interaction.response.is_done():
                await interaction.response.send_message(f"❌ Ошибка: {e}", ephemeral=True)
            else:
                await interaction.followup.send(f"❌ Ошибка: {e}", ephemeral=True)
    #@unisolate.autocomplete("unisolation_member") Я ТОПТАЛ ЭТО ГОВНО ЭТОТ КОД ДОЛЖЕН ВЫВОДИТЬ ТОЛЬКО ИЗОЛИРОВАННЫХ УЧАСТНИКОВ НО ОН ЧМО ТУПОРЫЛОЕ Я ПИСАЛ ЭТО ЧАСИК 
    #async def isolated_autocomplete(self, interaction: discord.Interaction, current: str,) -> List[app_commands.Choice[str]]:
#
    #    if os.path.exists(isolated_users):
    #        try:
    #            with open(isolated_users, 'r', encoding='utf-8') as f:
    #                isolated_data = json.load(f)
    #        except json.JSONDecodeError:
    #            return []
    #        
    #        choices = []
#
    #        for user_id in isolated_data.keys():
#
    #            try:
    #                all_members = await interaction.guild.fetch_members(limit=None).flatten()
    #                for member in all_members:
    #                    if str(member.id) not in isolated_data:
    #                        continue
    #                    if current.lower() in member.display_name.lower():
    #                        choices.append(app_commands.Choice(name=member.display_name, value=str(member.id)))
    #            except discord.NotFound:
    #                continue
    #            except discord.Forbidden:
    #                continue
#
    #            if member is None:
    #                continue
    #            if current.lower() in member.display_name.lower():
    #                choices.append(
    #                    app_commands.Choice(
    #                        name=member.display_name,
    #                        value=str(member.id),
    #                    )
    #                )
    #        return choices[:25]
#
    #    else:
    #        return []
    #
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