import discord
import time
import re
import io
import openpyxl
from datetime import datetime
from dataclasses import dataclass, asdict
from discord.ext import commands
from discord import app_commands
from utils.exceptions import NoLogChannelError
from utils.permissions import check_cog_access
from utils import settings_cache as settings
from discord.ui import View, Button
from typing import Optional, List
from constants import RMC_EMBED_COLOR
from isolation import IsolatedUser

BOT_NAME_REGEX = re.compile(r"^[a-zA-Z]+\d{4,5}$", re.IGNORECASE)


async def evaluate_suspicion(member: discord.Member) -> tuple[float, list]:
    score = 0.0
    reasons = []

    account_age_seconds = (discord.utils.utcnow() - member.created_at).total_seconds()

    if account_age_seconds < 86400:
        score += 2
        reasons.append("Аккаунту меньше 24 часов (+2)")
    elif 86400 <= account_age_seconds <= 259200:
        score += 1
        reasons.append("Аккаунту от 1 до 3 дней (+1)")

    if member.avatar is None:
        score += 1
        reasons.append("У аккаунта стандартный аватар (+1)")
    elif member.avatar.is_animated():
        score -= 1.5
        reasons.append("У аккаунта анимированный аватар (-1.5)")

    if not member.public_flags.value:
        score += 0.5
        reasons.append("У аккаунта нет значков профиля (+0.5)")

    if BOT_NAME_REGEX.match(member.name):
        score += 2
        reasons.append("Ник попадает под паттерн ботов (+2)")

    return score, reasons

class SuspicionActionView(discord.ui.View):
    def __init__(self, target_member: discord.Member, bot: commands.Bot, score: float):
        super().__init__(timeout=None)
        self.target_member = target_member
        self.bot = bot
        self.score = score

    @discord.ui.button(label="Изолировать", style=discord.ButtonStyle.danger)
    async def btn_isolate(self, interaction: discord.Interaction, button: discord.ui.Button):   
        user_roles = [
            role for role in self.target_member.roles 
            if not role.is_default() and not role.managed
        ]
        isolation_cog = self.bot.get_cog("Isolation")
        if not isolation_cog:
            return await interaction.response.send_message("❌ Ошибка: Модуль изоляции не найден.", ephemeral=True)

        isolated_user = IsolatedUser(
            roles=user_roles,
            isolated_at=time.time(),
            isolated_by=interaction.user.id,
            reason=f"[Omnivisor] Изолирован из-за высокого уровна подозрительности {self.score}"
        )

        async with isolation_cog._file_lock:
            isolated_data = await isolation_cog.load_isolated_data()
            isolated_data[str(self.target_member.id)] = asdict(isolated_user)
            await isolation_cog.save_isolated_data(isolated_data)

        settings_data = settings.load_settings()
        isolation_role_id = settings_data.get('isolation_role_id')
        isolation_role = interaction.guild.get_role(isolation_role_id)

        if isolation_role:
            if user_roles:
                await self.target_member.remove_roles(*user_roles, reason=f"Изолирован {interaction.user} через Omnivisor.")
            await self.target_member.add_roles(isolation_role, reason=f"Изолирован {interaction.user} через Omnivisor.")

        from utils import omnivisor_db as db
        await db.log_action(
            action_type="Изоляция",
            display_name=self.target_member.display_name,
            username=self.target_member.name,
            user_id=self.target_member.id,
            moderator_id=interaction.user.id,
            reason=isolated_user.reason,
            timestamp=int(isolated_user.isolated_at),
            joined_at=int(self.target_member.joined_at.timestamp()) if self.target_member.joined_at else 0
        )

        for child in self.children:
            child.disabled = True

        embed = interaction.message.embeds[0]
        embed.add_field(
            name = "🛡️ Решение",
            value = f"✅ Изолирован модератором {interaction.user.mention}"
        )
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Проигнорировать", style=discord.ButtonStyle.secondary)
    async def btn_ignore(self, interaction: discord.Interaction, button: discord.ui.button):
        for child in self.children:
            child.disabled = True

        from utils import omnivisor_db as db
        await db.log_action(
            action_type="Игнорирование подозрения",
            display_name=self.target_member.display_name,
            username=self.target_member.name,
            user_id=self.target_member.id,    
            moderator_id=interaction.user.id,
            reason="Модератор счел аккаунт безопасным",
            timestamp=int(time.time()),
            joined_at=int(self.target_member.joined_at.timestamp()) if self.target_member.joined_at else 0
        )
        embed = interaction.message.embeds[0]
        embed.add_field(
            name = "🛡️ Решение",
            value = f"👀 Проигнорирован модератором {interaction.user.mention}"
        )
        await interaction.response.edit_message(embed=embed, view=self)

class Omnivisor(commands.Cog):
    """Cog для организации работы проекта Омнивизор через РМК-Бота"""
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
    
    def _get_log_channel(self, guild: discord.Guild) -> discord.TextChannel | None:
        """Загружает канал для логов из настроек"""
        settings_data = settings.load_settings()
        channel_id = settings_data.get('log_channel')
        log_channel = guild.get_channel(channel_id) if channel_id else None
        
        return log_channel
    
    def _get_omnivisor_roles(self) -> str:
        """Загружает роли для пинга в логировании из настроек"""
        settings_data = settings.load_settings()

        if not settings_data.get('auto_stat_enabled', True):
            return ""
        
        omnivisor_roles_ids = settings_data.get('auto_stat_roles', [])
        omnivisor_roles = " ".join([f"<@&{r}>" for r in omnivisor_roles_ids])
        return omnivisor_roles

    
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        from utils import omnivisor_db as db

        score, reasons = await evaluate_suspicion(member)

        await db.log_action(
            action_type="Новый участник на сервере",
            display_name=member.display_name,
            username=member.name,
            user_id=member.id,
            moderator_id=None,
            timestamp=int(time.time()),
            joined_at=int(member.joined_at.timestamp()) if member.joined_at else 0
        )

        settings_data = settings.load_settings()
        log_channel = self._get_log_channel(member.guild)
        omnivisor_roles = self._get_omnivisor_roles()
        
        if not log_channel:
            pass
            # raise NoLogChannelError()
        
        log_embed = discord.Embed(
            title="📥 Новый участник на сервере",
            color=RMC_EMBED_COLOR,
            timestamp=discord.utils.utcnow()
        )
        log_embed.add_field(name="Участник", value=f"{member.mention}\n`{member.id}`\n@{member.name}", inline=True)
        log_embed.add_field(name="📅 Даты", value=f"Дата создания аккаунта: <t:{int(member.created_at.timestamp())}:d> | Зашёл на сервер: <t:{int(member.joined_at.timestamp())}:d>", inline=True)
        reasons_text = "\n".join(reasons) if reasons else "Подозрительных признаков не найдено"
        log_embed.add_field(name=f"📊 Индекс подозрения: {score}", value=f"```{reasons_text}```", inline=False)
        log_embed.set_thumbnail(url=member.display_avatar.url)

        if score >= 2:
            ping_roles = " ".join([f"<@&{r}>" for r in settings_data.get('admin_roles', [])])
            view = SuspicionActionView(member, self.bot, score)
            await log_channel.send(content=f"⚠️ {ping_roles} **Внимание, обнаружен вход подозрительного аккаунта!** Требуется внимание администрации", embed=log_embed, view=view)
        else:
            await log_channel.send(content=f"{omnivisor_roles}",embed=log_embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        import asyncio
        from utils import omnivisor_db as db
        await asyncio.sleep(2)

        action_type = "Выход с сервера"
        moderator_id = None
        reason = "Самостоятельный выход"

        try:
            async for entry in member.guild.audit_logs(limit=3, action=discord.AuditLogAction.kick):
                if entry.target.id == member.id:
                    action_type = "Кик"
                    moderator_id = entry.user.id
                    reason = entry.reason or "Причина не указана"
                    break
        except discord.Forbidden:
            pass

        await db.log_action(
            action_type=action_type,
            display_name=member.display_name,
            username=member.name,
            user_id=member.id,
            moderator_id=moderator_id,
            timestamp=int(time.time()),
            joined_at=0,
        )

        log_channel = self._get_log_channel(member.guild)
        omnivisor_roles = self._get_omnivisor_roles()

        if log_channel:
            log_embed = discord.Embed(
                title="📤 Участник покинул сервер",
                color=RMC_EMBED_COLOR,
                timestamp=discord.utils.utcnow()
            )
            log_embed.add_field(name="Участник", value=f"{member.mention} (`{member.id}`)\n@{member.name}", inline=True)
            log_embed.add_field(name="Действие", value=action_type, inline=True)
            if moderator_id:
                log_embed.add_field(name="Модератор", value=f"<@{moderator_id}>", inline=True)
                log_embed.add_field(name="Причина", value=f"```{reason}```", inline=False)

            await log_channel.send(content=omnivisor_roles, embed=log_embed)

    @commands.Cog.listener()
    async def on_member_ban(self, guild = discord.Guild, user = discord.User):
        import asyncio
        from utils import omnivisor_db as db
        
        await asyncio.sleep(2)
        action_type = "Бан"
        try:
            async for entry in guild.audit_logs(limit=3, action=discord.AuditLogAction.ban):
                if entry.target.id == user.id:
                    moderator_id = entry.user.id
                    reason = entry.reason or "Причина не указана"
                    break
        except discord.Forbidden:
            pass

        display_name = getattr(user, 'display_name', user.name)

        await db.log_action(
            action_type = action_type, 
            display_name = display_name, 
            username = user.name, 
            user_id = user.id, 
            timestamp = int(time.time()), 
            joined_at = 0, 
            moderator_id = moderator_id, 
            reason = reason
        )

        settings_data = settings.load_settings()
        log_channel = self._get_log_channel(guild)
        omnivisor_roles = self._get_omnivisor_roles()

        if log_channel:
            log_embed = discord.Embed(
                title="🔨 Участник был забанен",
                color=RMC_EMBED_COLOR,
                timestamp=discord.utils.utcnow()
            ) 
            log_embed.add_field(name="Участник", value=f"{user.mention} (`{user.id}`)\n@{user.name}", inline=True)
            if moderator_id:
                log_embed.add_field(name="Модератор", value=f"<@{moderator_id}>", inline=True)
                log_embed.add_field(name="Причина", value=f"```{reason}```", inline=False)
            await log_channel.send(content=omnivisor_roles, embed=log_embed)

    @app_commands.command(
        name="export_logs",
        description="Выгрузить отчёт Omnivisor в Excel"
    )
    @app_commands.describe(
        clear_db="Очистить базу данных после выгрузки отчёта?"
    )
    @app_commands.choices(fruits=[
        app_commands.Choice(name='Нет', value=0),
        app_commands.Choice(name='Да', value=1),
    ])
    async def export_logs(self, interaction: discord.Interaction, clear_db: int = 0):
        if not await self.check_admin(interaction):
            return await interaction.response.send_message("❌ Недостаточно прав", ephemeral=True)
        
        await interaction.response.defer(ephemeral=True)

        clear_db_bool = bool(clear_db)

        from utils import omnivisor_db as db
        logs = await db.get_logs_for_export()

        if not logs:
            return await interaction.followup.send("📭 База данных пуста. Действий для выгрузки нет.", ephemeral=True)
        
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Omnivisor Logs"

        headers = [
            "ID Лога", "Действие", "Никнейм", "Имя аккаунта", 
            "ID Пользователя", "Дата действия", "Дата захода", 
            "Модератор (ID)", "Причина"
        ]
        ws.append(headers)

        mode_names_cache = {}

        for row in logs:
            action_time = "Неизвестно"
            if row['timestamp']:
                action_time = datetime.fromtimestamp(row['timestamp']).strftime('%d.%m.%Y %H:%M:%S')

            join_time = "Неизвестно"
            if row['joined_at'] and row['joined_at'] > 0:
                join_time = datetime.fromtimestamp(row['joined_at']).strftime('%d.%m.%Y %H:%M:%S')

            mod_name = "Система/Бот"
            mod_id = row['moderator_id']

            if mod_id:
                if mod_id in mode_names_cache:
                    mod_name = mode_names_cache[mod_id]
                else:
                    mod = interaction.guild.get_member(mod_id) 
                    if not mod:
                        mod = self.bot.get_user(mod_id)
                    
                    if mod:
                        mod_name = f"{mod.display_name} (@{mod.name})"
                    else:
                        mod_name = f"Неизвестно (ID: {mod_id})"
                    
                    mode_names_cache[mod_id] = mod_name

            ws.append([
                row['log_id'],
                row['action_type'],
                row['display_name'],
                row['username'],
                str(row['user_id']), 
                action_time,
                join_time,
                mod_name,
                row['reason']
            ])

        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)

        file_name = f"omnivisor_logs_{datetime.now().strftime('%d_%m_&Y')}.xlsx"
        discord_file = discord.File(fp=buffer, filename=file_name)

        response_embed = discord.Embed(
            title="✅ Выгрузка журнала успешно завершена!",
            description="Файл прикреплен к сообщению.",
            color=RMC_EMBED_COLOR,
            timestamp=discord.utils.utcnow()
        )
        if clear_db_bool:
            response_embed.add_field(
                name="🗑️ Очистка",
                value="База данных логов была очищена согласно запросу."
            )

        await interaction.followup.send(embed=response_embed, file=discord_file)

        if clear_db_bool:
            await db.clear_action_logs()
   

    @app_commands.command(
       name="sync_db",
       description="Создать слепок участников сервера для дополнения Протокол-ξ."
    )
    @app_commands.guild_only()
    async def sync_db(self, interaction: discord.Interaction):
        if not await self.check_admin(interaction):
            return await interaction.response.send_message("❌ Недостаточно прав", ephemeral=True)
        
        await interaction.response.defer(ephemeral=True)

        members_to_sync = []

        for member in interaction.guild.members:
            if member.bot:
                continue

            roles_list = [role.name for role in member.roles if not role.is_default()]
            roles_str = ", ".join(roles_list) if roles_list else "Нет ролей"

            joined_at = int(member.joined_at.timestamp()) if member.joined_at else 0
            created_at = int(member.created_at.timestamp())

            members_to_sync.append((
                "Синхронизация",        # action_type
                member.display_name,    # display_name
                member.name,            # username
                member.id,              # user_id
                created_at,             # created_at
                joined_at,              # joined_at
                roles_str               # roles
            ))

        from utils import omnivisor_db as db
        await db.sync_members(members_to_sync)

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Server Snapshot"

        headers = [
            "Тип записи", "Никнейм", "Имя аккаунта", 
            "ID Пользователя", "Дата создания", "Дата захода", "Список ролей"
        ]
        ws.append(headers)

        for data in members_to_sync:
            c_time = datetime.fromtimestamp(data[4]).strftime('%d.%m.%Y %H:%M:%S')
            j_time = datetime.fromtimestamp(data[5]).strftime('%d.%m.%Y %H:%M:%S') if data[5] > 0 else "Неизвестно"
            
            ws.append([
                data[0], 
                data[1], 
                data[2], 
                str(data[3]), 
                c_time, 
                j_time, 
                data[6]  
            ])

        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)

        file_name = f"omnivisor_snapshot_{datetime.now().strftime('%d_%m_%Y_%H%M')}.xlsx"
        discord_file = discord.File(fp=buffer, filename=file_name)

        response_embed = discord.Embed(
            title="🔄 База данных синхронизирована",
            description=(
                f"Данные участников обновлены в БД.\n"
                f"Всего обработано: **{len(members_to_sync)}** чел.\n\n"
                f"💾 Актуальный слепок прикреплен к сообщению."
            ),
            color=RMC_EMBED_COLOR,
            timestamp=discord.utils.utcnow()
        )

        await interaction.followup.send(embed=response_embed, file=discord_file)

    @app_commands.command(
        name="omnivisor_settings",
        description="Настройки системы уведомлений и мониторинга Omnivisor"
    )
    @app_commands.describe(
        notifications="Включить или выключить упоминания ролей Омнивизора",
        add_role="Добавить роль в список для пингов",
        remove_role="Удалить роль из списка для пингов"
    )
    async def omnivisor_settings(self, interaction: discord.Interaction, notifications: Optional[bool] = None, add_role: Optional[discord.Role] = None, remove_role: Optional[discord.Role] = None):
        if not await self.check_admin(interaction):
            return await interaction.response.send_message("❌ Недостаточно прав", ephemeral=True)

        settings_data = settings.load_settings()
        changes = []

        if notifications is not None:
            settings_data['auto_stat_enabled'] = notifications
            status = "Включены" if notifications else "Выключены"
            changes.append(f"Уведомления: **{status}**")

        if add_role:
            roles = settings_data.get('auto_stat_roles', [])
            if add_role.id not in roles:
                roles.append(add_role.id)
                settings_data['auto_stat_roles'] = roles
                changes.append(f"Добавлена роль: {add_role.mention}")
            else:
                changes.append(f"⚠️ Роль {add_role.mention} уже есть в списке")

        if remove_role:
            roles = settings_data.get('auto_stat_roles', [])
            if remove_role.id in roles:
                roles.remove(remove_role.id)
                settings_data['auto_stat_roles'] = roles
                changes.append(f"Удалена роль: {remove_role.mention}")
            else:
                changes.append(f"⚠️ Роль {remove_role.mention} не найдена в списке")

        if changes:
            settings.save_settings(settings_data)
            embed = discord.Embed(
                title="✅ Настройки Omnivisor обновлены",
                description="\n".join(changes),
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow()
            )
            await interaction.response.send_message(embed=embed)
        else:
            is_enabled = settings_data.get('auto_stat_enabled', True)
            roles_ids = settings_data.get('auto_stat_roles', [])
            roles_mentions = " ".join([f"<@&{r}>" for r in roles_ids]) if roles_ids else "Не настроены"
            
            embed = discord.Embed(
                title="⚙️ Текущие настройки Omnivisor",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="Уведомления (пинги)", value="✅ Включены" if is_enabled else "❌ Выключены", inline=False)
            embed.add_field(name="Роли для уведомлений", value=roles_mentions, inline=False)
            embed.set_footer(text="Используйте параметры команды для изменения этих настроек")
            await interaction.response.send_message(embed=embed)
