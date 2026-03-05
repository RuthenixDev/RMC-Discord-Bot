import discord
import os
import json
import time
from datetime import datetime
from typing import Optional, List
from discord.ext import commands
from discord import app_commands
from utils.permissions import check_cog_access
from utils import settings_cache as settings
from constants import RMC_EMBED_COLOR

isolated_users = "isolated_users.json"

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
    
    
    @app_commands.command(
        name="isolate_settings",
        description="Настройки изоляции"
    )
    @app_commands.guild_only()
    @app_commands.describe(
        isolation_role = "Роль изоляции",
        log_channel = "Канал для логов"
    )
    async def isolate_settings(self, interaction: discord.Interaction, isolation_role: Optional[discord.Role], log_channel: Optional[discord.TextChannel]):

        settings_data = settings.load_settings()

        if isolation_role is None and log_channel is None:
            saved_role_id = settings_data.get('isolation_role_id')
            role_object = interaction.guild.get_role(saved_role_id) if saved_role_id else None

            saved_channel_id = settings_data.get('isolation_log_channel_id')
            channel_object = interaction.guild.get_channel(saved_channel_id) if saved_channel_id else None

            role_text = role_object.mention if role_object else "❌Не настроена"
            channel_text = channel_object.mention if channel_object else "❌Не настроен"
            #print("Не было указаны роли, публикую сохранённые настройки")
            embed = discord.Embed(
                title="⚙️Сохранённые настройки",
                description=f"В настройках сохранено следующее: \n - Роль изоляции: {role_text} \n - Канал для логов: {channel_text}",
                color=RMC_EMBED_COLOR,
                timestamp=discord.utils.utcnow()
            )
            await interaction.response.send_message(embed=embed)
            return

        changes = []
        needs_save = False
        if isolation_role:
            if isolation_role >= interaction.guild.me.top_role:
                embed = discord.Embed(
                    title="❌Ошибка",
                    description="Для изоляции нельзя назначить роль, которая выше роли бота!",
                    color=RMC_EMBED_COLOR,
                    timestamp=discord.utils.utcnow()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            if isolation_role.is_default():
                embed = discord.Embed(
                    title="❌Ошибка",
                    description="Для изоляции нельзя назначить `@everyone`!",
                    color=RMC_EMBED_COLOR,
                    timestamp=discord.utils.utcnow()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            else: 
                settings_data['isolation_role_id'] = isolation_role.id
                changes.append(f"Роль {isolation_role.mention}")
                needs_save = True

        if log_channel:
            if not log_channel.permissions_for(interaction.guild.me).send_messages:
                embed = discord.Embed(
                    title="❌Ошибка",
                    description="У бота нет прав писать в выбранный канал!",
                    color=RMC_EMBED_COLOR,
                    timestamp=discord.utils.utcnow()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            else:
                settings_data['isolation_log_channel_id'] = log_channel.id
                changes.append(f"Канал {log_channel.mention}")
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
        isolation_member = "Участник для изоляции",
    )
    async def isolate(self, interaction: discord.Interaction, isolation_member: discord.Member, isolation_reason: Optional[str]):

        try:
            settings_data = settings.load_settings()

            role_id = settings_data.get('isolation_role_id')
            channel_id = settings_data.get('isolation_log_channel_id')

            isolation_role = interaction.guild.get_role(role_id) if role_id else None
            log_channel = interaction.guild.get_channel(channel_id) if channel_id else None 

            if not isolation_role:
                embed = discord.Embed(
                    title="❌Ошибка",
                    description="Не назначена роль изоляции!",
                    color=RMC_EMBED_COLOR,
                    timestamp=discord.utils.utcnow()
                )
                embed.set_footer(text="Для настройки используйте /isolate_settings.")
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            if not log_channel:
                embed = discord.Embed(
                    title="❌Ошибка",
                    description="Не назначен канал для логов",
                    color=RMC_EMBED_COLOR,
                    timestamp=discord.utils.utcnow()
                )
                embed.set_footer(text="Для настройки используйте /isolate_settings.")
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            try:
                #получаем его роли
                isolation_member_roles = []
                for role in isolation_member.roles:
                    if not role.is_default() and not role.managed and role != isolation_role:
                        isolation_member_roles.append(role)

                role_ids = [role.id for role in isolation_member_roles]
                user_id = str(isolation_member.id)

                admin_roles = settings_data.get('admin_roles', [])

                #если у него есть админ роль делаем откат рп
                if any(role_id in admin_roles for role_id in role_ids):
                    embed = discord.Embed(
                        title="❌Ошибка при изоляции",
                        description="У выбранного участника есть роль, которая отмечена как административная.",
                        color=RMC_EMBED_COLOR,
                        timestamp=discord.utils.utcnow()
                    )
                    embed.set_footer(
                        text="Для просмотра списка — /listadmins."
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return

                #а если он не админ то сохраняем роли и газуем
                if os.path.exists(isolated_users):
                    with open(isolated_users, 'r', encoding='utf-8') as f:
                        isolated_data = json.load(f)
                else:
                    isolated_data = {}

                if user_id in isolated_data:
                    embed = discord.Embed(
                        title="❌Ошибка при изоляции",
                        description="Выбранный участник уже изолирован!",
                        color=RMC_EMBED_COLOR,
                        timestamp=discord.utils.utcnow()
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return
                else:
                    isolated_data[user_id] = {
                        "roles": role_ids,
                        "isolated_at": time.time(),
                        "isolated_by": interaction.user.id,
                        "reason": isolation_reason or None
                    }
                    with open(isolated_users, 'w', encoding='utf-8') as f:
                        json.dump(isolated_data, f, indent=4, ensure_ascii=False)

                #лишаем ролей
                await interaction.response.defer(ephemeral=True)
                if isolation_member_roles:
                    await isolation_member.remove_roles(*isolation_member_roles)
    
                #изолируем
                await isolation_member.add_roles(isolation_role, reason=f"Изолирован {interaction.user} по причине «{isolation_reason}».")
                response_embed = discord.Embed(
                    title=f"✅Успешная изоляция",
                    description=f"Участник {isolation_member.mention} изолирован!",
                    color=RMC_EMBED_COLOR,
                    timestamp=discord.utils.utcnow()
                )
                if isolation_reason:
                    response_embed.add_field(
                        name="Причина",
                        value=f"{isolation_reason}"
                    )
                if not isolation_reason:
                    response_embed.add_field(
                        name="Причина",
                        value=f"❌Причина не указана"
                    )
                #response_embed.set_footer(text="С")
                await interaction.followup.send(embed=response_embed, ephemeral=True)


                user_data = isolated_data[user_id]  # получаем словарь с данными
                #saved_roles_ids = user_data["roles"]
                #isolated_by = user_data.get("isolated_by")  
                #reason = user_data.get("reason", "Не указана")
                isolation_date = user_data.get("isolated_at")
                timestamp = user_data.get("isolated_at")

                if timestamp:
                    discord_time = f"<t:{int(timestamp)}:d>"
                else:
                    discord_time = "Неизвестно"

                log_embed = discord.Embed(
                    title="Участник был изолирован",
                    color=RMC_EMBED_COLOR,
                    timestamp=discord.utils.utcnow()
                )
                log_embed.add_field(
                    name="Изолирован",
                    value=f"{isolation_member.mention} | {isolation_member} | {isolation_member.id}",
                    inline=False
                )
                log_embed.add_field(
                    name="Изолировал",
                    value=f"{interaction.user.mention} | {interaction.user} | {interaction.user.id}",
                    inline=False
                )
                log_embed.add_field(
                    name="Причина",
                    value=f"```{isolation_reason}```"
                )
                log_embed.add_field(
                    name="Дата изоляции",
                    value=f"{discord_time}",
                    inline=True
                )
                await log_channel.send(embed=log_embed)
            except discord.Forbidden:
                embed = discord.Embed(
                    title="❌Ошибка при изоляции",
                    description="У бота недостаточно прав для изоляции",
                    color=RMC_EMBED_COLOR,
                    timestamp=discord.utils.utcnow()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
        except Exception as e:
            print(f"ОШИБКА в unisolate: {e}")
            import traceback
            traceback.print_exc()
            
            if not interaction.response.is_done():
                await interaction.response.send_message(f"❌ Ошибка: {e}", ephemeral=True)
            else:
                await interaction.followup.send(f"❌ Ошибка: {e}", ephemeral=True)
        

    @app_commands.command(
        name="unisolate",
        description="Вернуть участника из изолятора"
    )
    @app_commands.guild_only()
    #@app_commands.autocomplete(unisolation_member=isolated_autocomplete)
    @app_commands.describe(
        unisolation_member = "Участник для помилования",
    )
    async def unisolate(self, interaction: discord.Interaction, unisolation_member: discord.Member, unisolation_reason: Optional[str] = None):

        try:
            #member = interaction.guild.get_member(int(unisolation_member))
            member = unisolation_member #это выглядит очень странно, но я ток что вырезал час свеой жизни, поэтому просто вставлю так
            user_id = str(member.id)

            settings_data = settings.load_settings()

            isolate_role = settings_data.get('isolation_role_id')
            role_object = interaction.guild.get_role(isolate_role) if isolate_role else None

            channel_id = settings_data.get('isolation_log_channel_id')
            log_channel = interaction.guild.get_channel(channel_id) if channel_id else None 


            if not role_object:
                embed = discord.Embed(
                    title="❌Ошибка",
                    description="Не назначена роль изоляции!",
                    color=RMC_EMBED_COLOR,
                    timestamp=discord.utils.utcnow()
                )
                embed.set_footer(text="Для настройки используйте /isolate_settings.")
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            if not log_channel:
                embed = discord.Embed(
                    title="❌Ошибка",
                    description="Не назначен канал для логов",
                    color=RMC_EMBED_COLOR,
                    timestamp=discord.utils.utcnow()
                )
                embed.set_footer(text="Для настройки используйте /isolate_settings.")
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            await interaction.response.defer(ephemeral=True)
            
            if os.path.exists(isolated_users):
                    with open(isolated_users, 'r', encoding='utf-8') as f:
                        isolated_data = json.load(f)
            else:
                isolated_data = {}

            if user_id in isolated_data:

                user_data = isolated_data[user_id]
                saved_roles_ids = user_data["roles"]
                timestamp = user_data.get("isolated_at")
                isolated_by = user_data.get("isolated_by")
                reason = user_data.get("reason", "Не указана")
                if timestamp:
                    discord_time = f"<t:{int(timestamp)}:d>"
                else:
                    discord_time = "Неизвестно"

                roles_to_restore = []
                for role_id in saved_roles_ids:
                    role = interaction.guild.get_role(role_id)
                    if role:
                        roles_to_restore.append(role)


                await member.remove_roles(role_object, reason=f"Модератор {interaction.user} снял изоляцию по причине {unisolation_reason}")

                if roles_to_restore:
                    await member.add_roles(*roles_to_restore, reason=f"Модератор {interaction.user} снял изоляцию по причине {unisolation_reason}")

                del isolated_data[user_id]
                with open(isolated_users, 'w', encoding='utf-8') as f:
                    json.dump(isolated_data, f, indent=4, ensure_ascii=False)

                response_embed = discord.Embed(
                    title=f"✅Успешное возвращение",
                    description=f"Участник {member.mention} был возвращён из изолятора!",
                    color=RMC_EMBED_COLOR,
                    timestamp=discord.utils.utcnow()
                )
                if unisolation_reason:
                    response_embed.add_field(
                        name="Причина",
                        value=f"{unisolation_reason}"
                    )
                if not unisolation_reason:
                    response_embed.add_field(
                        name="Причина",
                        value=f"❌Причина не указана"
                    )
                #response_embed.set_footer(text="С")
                await interaction.followup.send(embed=response_embed, ephemeral=True)

                log_embed = discord.Embed(
                    title="Участник бьл возвращён",
                    color=RMC_EMBED_COLOR,
                    timestamp=discord.utils.utcnow()
                )
                log_embed.add_field(
                    name="Возвратился",
                    value=f"{member.mention} | {member} | {member.id}",
                    inline=False
                )
                log_embed.add_field(
                    name="Возвратил",
                    value=f"{interaction.user.mention} | {interaction.user} | ({interaction.user.id})",
                    inline=False
                )
                log_embed.add_field(
                    name="Причина возвращения",
                    value=f"```{unisolation_reason}```"
                )
                log_embed.add_field(
                    name="Причина изоляции",
                    value=f"`{reason}`"
                )

                log_embed.add_field(
                    name="Дата изоляции",
                    value=f"{discord_time}"
                )
                await log_channel.send(embed=log_embed)

            else:
                embed = discord.Embed(
                    title="❌Ошибка при возвращении из изоляции",
                    description="Выбранный участник ещё не изолирован!",
                    color=RMC_EMBED_COLOR,
                    timestamp=discord.utils.utcnow()
                )
                if not interaction.response.is_done():
                    await interaction.response.send_message(embed=response_embed, ephemeral=True)
                else:
                    await interaction.followup.send(embed=embed, ephemeral=True)
                return
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

        if os.path.exists(isolated_users):
            with open(isolated_users, 'r', encoding='utf-8') as f:
                isolated_data = json.load(f)
        else:
            isolated_data = {}

        embed = discord.Embed(
            title="📋 Список изолированных участников",
            color=RMC_EMBED_COLOR,
            timestamp=discord.utils.utcnow()
        )

        await interaction.response.defer()

        if isolated_data:
            for user_id_str, user_data in isolated_data.items():  # Проходим по всем
                user_id = int(user_id_str)
                
                # Получаем данные для КАЖДОГО пользователя
                isolated_by = user_data.get("isolated_by")
                reason = user_data.get("reason", "Не указана")
                timestamp = user_data.get("isolated_at")
                
                # Форматируем время
                if timestamp:
                    discord_time = f"<t:{int(timestamp)}:d>"
                else:
                    discord_time = "Неизвестно"
                
                try:
                    member = await interaction.guild.fetch_member(user_id)
                    
                    # Получаем модератора, если есть
                    moderator_text = "Неизвестно"
                    if isolated_by:
                        try:
                            moderator = await interaction.guild.fetch_member(int(isolated_by))
                            moderator_text = moderator.mention
                        except:
                            moderator_text = f"<@{isolated_by}>"
                    
                    embed.add_field(
                        name=f"{member.display_name}",
                        value=f"Участник: {member.mention} `{user_id}`\nДата: {discord_time} \nМодератор: {moderator_text} \nПричина:`{reason}`",
                        inline=False
                    )
                except discord.NotFound:
                    embed.add_field(
                        name="❌ Неизвестный участник",
                        value=f"ID: `{user_id}`\nПричина: `{reason}`\nВремя: {discord_time}",
                        inline=False
                    )
            
            await interaction.followup.send(embed=embed)
        else:
            embed.description = "✅ Изолированные участники отсутствуют"
            await interaction.followup.send(embed=embed)

           



async def setup(bot: commands.Bot):
    await bot.add_cog(Isolation(bot))