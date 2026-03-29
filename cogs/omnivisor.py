import discord
import time
import io
import openpyxl
from discord.ext import commands
from discord import app_commands
from utils.permissions import check_cog_access
from utils import settings_cache as settings
from utils import omnivisor_db
from discord.ui import View, Button
from typing import Optional
from constants import RMC_EMBED_COLOR
from datetime import datetime

class NotesPaginationView(discord.ui.View):
    def __init__(self, user: discord.User | discord.Member, notes: list):
        super().__init__(timeout=60)
        self.user = user
        self.notes = notes
        self.current_page = 0
        self.notes_per_page = 5  # Оптимально для мобилок и ПК
        self.total_pages = (len(notes) - 1) // self.notes_per_page + 1

    def create_embed(self):
        start = self.current_page * self.notes_per_page
        end = start + self.notes_per_page
        page_notes = self.notes[start:end]

        embed = discord.Embed(
            title=f"📝 Записи в деле: {self.user.display_name}",
            description=f"Всего заметок: **{len(self.notes)}**",
            color=RMC_EMBED_COLOR
        )

        for note in page_notes:
            keys = note.keys() if hasattr(note, 'keys') else {}
            time_val = note['timestamp'] if 'timestamp' in keys else note.get('created_at', 0)
            note_id_val = note['note_id'] if 'note_id' in keys else note.get('id', '???')
            
            time_str = f"<t:{time_val}:f>"
            mod_mention = f"<@{note['moderator_id']}>"
            
            # Обрезаем текст, чтобы точно влезть в лимит поля
            raw_text = note['note_text']
            max_len = 1021 - len(f"**Модератор:** {mod_mention}\n**Текст:** ")
            content = f"**Модератор:** {mod_mention}\n**Текст:** {raw_text[:max_len]}..." if len(raw_text) > max_len else f"**Модератор:** {mod_mention}\n**Текст:** {raw_text}"

            embed.add_field(name=f"ID: {note_id_val} | От {time_str}", value=content, inline=False)

        embed.set_footer(text=f"Страница {self.current_page + 1} из {self.total_pages}")
        return embed

    @discord.ui.button(label="⬅️", style=discord.ButtonStyle.gray)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            await interaction.response.edit_message(embed=self.create_embed(), view=self)
        else:
            await interaction.response.send_message("Это первая страница!", ephemeral=True)

    @discord.ui.button(label="➕ Добавить", style=discord.ButtonStyle.success)
    async def add_note(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(DossierEditModal(self.user))

    @discord.ui.button(label="🗑️ Удалить", style=discord.ButtonStyle.danger)
    async def del_note(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(DeleteNoteModal(self.user))

    @discord.ui.button(label="➡️", style=discord.ButtonStyle.gray)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            await interaction.response.edit_message(embed=self.create_embed(), view=self)
        else:
            await interaction.response.send_message("Это последняя страница!", ephemeral=True)

class DossierEditModal(discord.ui.Modal, title='Добавить комментарий'):
    comment = discord.ui.TextInput(
        label='Текст комментария',
        style=discord.TextStyle.paragraph,
        placeholder='Опишите важные детали...',
        required=True,
        max_length=1000
    )

    def __init__(self, user: discord.User | discord.Member):
        super().__init__()
        self.user = user

    async def on_submit(self, interaction: discord.Interaction):
        import time
        from utils import omnivisor_db
        timestamp = int(time.time())
        await omnivisor_db.add_note(self.user.id, interaction.user.id, self.comment.value, timestamp)
        await interaction.response.send_message(f"✅ Комментарий к делу {self.user.mention} успешно добавлен!", ephemeral=True)

class DeleteNoteModal(discord.ui.Modal, title='Удалить комментарий'):
    note_id_input = discord.ui.TextInput(
        label='Введите ID комментария (число)',
        style=discord.TextStyle.short,
        required=True,
        max_length=10
    )

    def __init__(self, user: discord.User | discord.Member):
        super().__init__()
        self.user = user

    async def on_submit(self, interaction: discord.Interaction):
        from utils import omnivisor_db
        try:
            note_id = int(self.note_id_input.value)
            await omnivisor_db.delete_note(note_id)
            await interaction.response.send_message(f"🗑️ Комментарий **#{note_id}** успешно удалён.", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ Ошибка: ID должен быть числом!", ephemeral=True)

class CommunityRoleModal(discord.ui.Modal, title='Изменить роль в сообществе'):
    role_input = discord.ui.TextInput(
        label='Новая роль',
        style=discord.TextStyle.short,
        placeholder='Художник, Стример, Подозреваемый...',
        required=True,
        max_length=100
    )

    def __init__(self, user: discord.User | discord.Member):
        super().__init__()
        self.user = user

    async def on_submit(self, interaction: discord.Interaction):
        from utils import omnivisor_db
        await omnivisor_db.update_field(self.user.id, "community_role", self.role_input.value)
        await interaction.response.send_message(f"✅ Роль в сообществе для {self.user.mention} изменена на **{self.role_input.value}**.\n*Вызовите досье заново для обновления информации.*", ephemeral=True)


class NotesControlView(discord.ui.View):
    def __init__(self, user: discord.User | discord.Member):
        super().__init__(timeout=None)
        self.user = user

    @discord.ui.button(label="Добавить", style=discord.ButtonStyle.success, emoji="➕")
    async def add_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(DossierEditModal(self.user))

    @discord.ui.button(label="Удалить по ID", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def del_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(DeleteNoteModal(self.user))


class DossierControlView(discord.ui.View):
    def __init__(self, user: discord.User | discord.Member, bot):
        super().__init__(timeout=None)
        self.user = user
        self.bot = bot

    @discord.ui.button(label="Изменить статус", style=discord.ButtonStyle.secondary, emoji="⚠️")
    async def change_status(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = StatusSelectionView(self.user)
        await interaction.response.send_message("Выберите новый статус:", view=view, ephemeral=True)

    @discord.ui.button(label="Роль в сообществе", style=discord.ButtonStyle.secondary, emoji="🎭")
    async def change_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Вызываем модальное окно для ввода роли
        await interaction.response.send_modal(CommunityRoleModal(self.user))

    @discord.ui.button(label="Просмотреть комментарии", style=discord.ButtonStyle.primary, emoji="📝")
    async def view_comments(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            from utils import omnivisor_db
            notes = await omnivisor_db.get_notes(self.user.id)
            
            if not notes:
                embed = discord.Embed(
                    title=f"📝 Записи в деле: {self.user.display_name}",
                    description="📂 В досье пока нет ни одной записи.",
                    color=RMC_EMBED_COLOR
                )
                # Если заметок нет, даем только кнопку добавления
                view = NotesControlView(self.user) 
                await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
                return

            # Если заметки есть, запускаем пагинацию
            pagination_view = NotesPaginationView(self.user, notes)
            await interaction.response.send_message(
                embed=pagination_view.create_embed(), 
                view=pagination_view, 
                ephemeral=True
            )
            
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            await interaction.response.send_message(f"❌ **Ошибка:**\n```python\n{e}\n```", ephemeral=True)


class StatusSelectionView(discord.ui.View):
    def __init__(self, user: discord.User | discord.Member):
        super().__init__(timeout=60)
        self.user = user
        statuses = [
            ("🟢Нет подозрений", discord.ButtonStyle.success),
            ("🟡Слабое подозрение", discord.ButtonStyle.secondary),
            ("🟠Подозрительный", discord.ButtonStyle.primary),
            ("🔴Почти наверняка", discord.ButtonStyle.danger),
            ("🟣Подтверждённый", discord.ButtonStyle.danger)
        ]
        for label, style in statuses:
            btn = discord.ui.Button(label=label, style=style)
            btn.callback = self.make_callback(label)
            self.add_item(btn)

    def make_callback(self, label):
        async def callback(interaction: discord.Interaction):
            from utils import omnivisor_db
            await omnivisor_db.update_suspicion(self.user.id, label)
            await interaction.response.edit_message(content=f"✅ Статус {self.user.mention} изменен на: **{label}**", view=None)
        return callback

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
    
    async def cog_load(self):
        """"Вызывается при загрузке кога. Инициализирует базу данных."""
        await omnivisor_db.init_db()
        print("✅ База данных Omnivisor инициализирована успешно")

    async def check_admin(self, interaction: discord.Interaction) -> bool:
        """Проверяет, есть ли у пользователя админская роль"""
        settings_data = settings.load_settings()
        admin_roles = settings_data.get('admin_roles', [])
        user_roles = [role.id for role in interaction.user.roles]
        return any(role_id in admin_roles for role_id in user_roles)
    
    async def create_base_embed(self, title: str, user: discord.User | discord.Member, db_data: dict, custom_desc: str = None) -> discord.Embed:
        """Создаёт базовый embed. Принимает User, чтобы работать с вышедшими по ID."""
        
<<<<<<< Updated upstream
        for channel in member.guild.text_channels:
            if not channel.permissions_for(member.guild.me).read_message_history:
                continue
                
            try:
                async for message in channel.history(limit=200, oldest_first=True):
                    if message.author == member:
                        if not first_message or message.created_at < first_message.created_at:
                            first_message = message
                            break  
            except discord.Forbidden:
                continue
        
        if first_message:
            timestamp = int(first_message.created_at.timestamp())
            return f"Первое сообщение: <t:{timestamp}:F>\n **Ссылка:** {first_message.jump_url}"
        return "❌ Не удалось найти первое сообщение (возможно, слишком далеко в истории)"
    
    async def find_last_message(self, member: discord.Member):
        """Пытается найти последнее сообщение участника на сервере"""
        last_message = None
        newest_date = 0  
        
        for channel in member.guild.text_channels:
            if not channel.permissions_for(member.guild.me).read_message_history:
                continue
                
            try:
                async for message in channel.history(limit=200):
                    if message.author == member:
                        if not last_message or message.created_at > last_message.created_at:
                            last_message = message
                        break  
                        
            except discord.Forbidden:
                continue
        
        if last_message:
            timestamp = int(last_message.created_at.timestamp())
            return f"Последнее сообщение: <t:{timestamp}:F>\n **Ссылка:** {last_message.jump_url}"
        return "❌ Не удалось найти последнее сообщение"
    
    async def count_messages_slow(self, member: discord.Member, requester: discord.Member) -> int:
        """Считает сообщения участника на сервере (с пагинацией по 5000)"""
        count = 0
        print(f"⚠️ ВНИМАНИЕ: {requester.name} ({requester.id}) запустил подсчёт сообщений для {member.name} ({member.id})")

        
        channels = list(member.guild.text_channels) #+ list(member.guild.threads) + list(member.guild.forums)

        for channel in channels:
            if not channel.permissions_for(member.guild.me).read_message_history:
                continue

            last_id = None  
            while True:
                try:
                   
                    kwargs = {'limit': 5000}
                    if last_id:
                        kwargs['before'] = discord.Object(id=last_id)

                    messages = []
                    async for message in channel.history(**kwargs):
                        messages.append(message)
                        if message.author == member:
                            count += 1

                    if not messages:
                        break  

                    last_id = messages[-1].id

                    if len(messages) < 5000:
                        break

                except discord.Forbidden:
                    break  
                except Exception as e:
                    print(f"Ошибка в канале {channel.name}: {e}")
                    break

        return count
    
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Автоматически собирает информацию о новом участнике, если включена автостатистика"""
        
        settings_data = settings.load_settings()
        auto_stat_enabled = settings_data.get('auto_stat_enabled', 0)

        if auto_stat_enabled != 1:
            return  
        
        channel_id = settings_data.get('log_channel')
        if not channel_id:
            return  
        
        log_channel = member.guild.get_channel(channel_id)
        if not log_channel:
            return
        
        role_id = settings_data.get('auto_stat_role_id')
        role_mention = f"<@&{role_id}>" if role_id else ""
        
        try:
            member_roles = [role for role in member.roles if not role.is_default() and not role.managed]
            role_mentions = [role.mention for role in member_roles]
            roles_text = ", ".join(role_mentions) if role_mentions else "❌ Нет ролей"
            
            user_info_embed = discord.Embed(
                title="📥 Новый участник на сервере",
                description=f"Информация о новом участнике {member.mention}",
                color=RMC_EMBED_COLOR,
                timestamp=discord.utils.utcnow()
            )
            
            user_info_embed.add_field(
                name="Участник",
                value=f"Отображаемое имя: `{member.display_name}` | Глобальное имя: `{member.global_name or 'Нет'}` | ID: `{member.id}`",
                inline=False
            )
            
            user_info_embed.add_field(
                name="Роли участника",
                value=roles_text,
                inline=False
            )
            
            timestamp_created_at = int(member.created_at.timestamp())
            timestamp_joined_at = int(member.joined_at.timestamp())
            
            user_info_embed.add_field(
                name="📅 Даты",
                value=f"Дата создания аккаунта: <t:{timestamp_created_at}:D> | Зашёл на сервер: <t:{timestamp_joined_at}:D>",
                inline=False
            )
            
            # first_message = await self.find_first_message(member)
            # user_info_embed.add_field(
            #     name="📝 Первое сообщение",
            #     value=first_message,
            #     inline=False
            # )
            
            user_info_embed.set_author(
                name=member.display_name,
                icon_url=member.avatar.url if member.avatar else None
            )
            
            user_info_embed.set_footer(
                text=f"Автостатистика"
            )
            
            content = role_mention if role_mention else None
            
            await log_channel.send(content=content, embed=user_info_embed)
            
        except Exception as e:
            # Логируем ошибку, но не прерываем основной процесс
            log_channel.send(f"{role_mention}! Ошибка в автостатистике для **{member.name}**: {e}")
    
=======
        description = custom_desc if custom_desc else f"Информация об участнике {user.mention}"
        
        embed = discord.Embed(
            title=title,
            description=description,
            color=RMC_EMBED_COLOR,
            timestamp=discord.utils.utcnow()
        )

        created_at = db_data.get("created_at", 0)
        joined_at = db_data.get("joined_at", 0)
        status = db_data.get("status", "Нет")
        source = db_data.get("source", "Вопроса не было")
        community_role = db_data.get("community_role", "Нет данных")
        suspicion = db_data.get("suspicion_level", "Норма")

        created_value = f"<t:{created_at}:d>" if created_at else "❌ Неизвестно"
        joined_value = f"<t:{joined_at}:d>" if joined_at else "❌ Неизвестно"

        username = f"@{user.name}"
        # Если это User (вне сервера), у него нет атрибута nick
        server_nick = getattr(user, 'nick', "Вне сервера") if getattr(user, 'nick', None) else "Отсутствует/Вне сервера"
        # Внутри create_base_embed
        names_info = f"**Имя на сервере:** `{server_nick}`\n**Уникальный handle:** `{username}`"

        # Если вдруг ники очень длинные (теоретически), лимитируем:
        if len(names_info) > 1024:
            names_info = names_info[:1021] + "..."

        # embed.add_field(name="Информация об именах", value=names_info, inline=False)

        embed.add_field(name="Информация об именах", value=names_info, inline=False)
        embed.add_field(name="ID", value=f"`{user.id}`", inline=True)
        embed.add_field(name="📅 Аккаунт создан", value=created_value, inline=True)
        embed.add_field(name="📅 Зашёл на сервер", value=joined_value, inline=True)
        
        embed.add_field(name="🚪 Вышел/Бан?", value=status, inline=True)
        embed.add_field(name="🔍 Как попал сюда", value=source, inline=True)
        embed.add_field(name="🎭 Роль в сообществе", value=community_role, inline=True)
        embed.add_field(name="⚠️ Подозрительность", value=suspicion, inline=False)

        embed.set_thumbnail(url=user.display_avatar.url)
        embed.set_footer(text="Протокол-ξ • Omnivisor")
        embed.set_author(name=user.display_name, icon_url=user.avatar.url if user.avatar else None)
        return embed

    @app_commands.command(name="dossier", description="Получить дело на участника (через пинг или по ID)")
    @app_commands.guild_only()
    @app_commands.describe(user="Участник или его ID для получения информации")
    async def dossier(self, interaction: discord.Interaction, user: discord.User):
        # Использование discord.User позволяет Discord принимать ID людей, которых нет на сервере!
        if not await self.check_admin(interaction):
            await interaction.response.send_message("❌ Недостаточно прав", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)

        from utils import omnivisor_db
        db_data = await omnivisor_db.get_dossier(user.id)

        if not db_data: 
            error_embed = discord.Embed(
                title="❌ Досье не найдено",
                description=f"Досье для {user.mention} (ID: `{user.id}`) нет в базе. Возможно, он новый или произошла ошибка.",
                color=RMC_EMBED_COLOR,
                timestamp=discord.utils.utcnow()
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)
            return

        embed = await self.create_base_embed(title="📂 Протокол-ξ: Досье", user=user, db_data=db_data)
        view = DossierControlView(user, self.bot)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)



    @app_commands.command(name="sync_db", description="Синхронизировать БД с текущими участниками и бан-листом")
    @app_commands.guild_only()
    async def sync_db(self, interaction: discord.Interaction):
        if not await self.check_admin(interaction):
            await interaction.response.send_message("❌ Недостаточно прав", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)

        # 1. Синхронизация участников сервера
        members_data = []
        for member in interaction.guild.members:
            if member.bot:
                continue
            username = f"@{member.name}"
            nickname = member.nick or "Отсутствует"
            created_at = int(member.created_at.timestamp()) if member.created_at else 0
            joined_at = int(member.joined_at.timestamp()) if member.joined_at else 0
            members_data.append((member.id, username, nickname, created_at, joined_at))

        # 2. Синхронизация бан-листа
        bans_data = []
        try:
            async for ban_entry in interaction.guild.bans():
                u = ban_entry.user
                c_at = int(u.created_at.timestamp()) if u.created_at else 0
                bans_data.append((u.id, f"@{u.name}", c_at))
        except discord.Forbidden:
            pass # Если у бота нет прав на просмотр банов, пропускаем этот шаг

        try:
            from utils import omnivisor_db
            await omnivisor_db.sync_members(members_data)
            if bans_data:
                await omnivisor_db.sync_banned_users(bans_data)

            embed = discord.Embed(
                title="✅ Синхронизация завершена",
                description=f"**Обработано участников:** {len(members_data)}\n**Обработано банов:** {len(bans_data)}\n\nБаза данных успешно обновлена.",
                color=RMC_EMBED_COLOR,
                timestamp=discord.utils.utcnow()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Ошибка при синхронизации базы данных: ```{e}```", ephemeral=True)

    @app_commands.command(name="export_dossier", description="Выгрузить Протокол-ξ в формате Excel (.xlsx)")
    @app_commands.guild_only()
    async def export_dossier(self, interaction: discord.Interaction):
        if not await self.check_admin(interaction):
            await interaction.response.send_message("❌ Доступ запрещен", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        from utils import omnivisor_db
        dossiers, notes = await omnivisor_db.get_all_data_for_export()

        # Создаем Excel книгу
        wb = openpyxl.Workbook()
        ws_main = wb.active
        ws_main.title = "Досье (Протокол-ξ)"
        ws_notes = wb.create_sheet(title="Журнал комментариев")

        # --- ЗАГОЛОВКИ ---
        main_headers = ["ID", "Handle", "Никнейм", "Создан", "Зашел", "Статус", "Источник", "Роль", "Подозрительность", "Комментарии (Ссылка)"]
        ws_main.append(main_headers)
        
        notes_headers = ["ID Юзера", "Модератор", "Дата", "Текст комментария", "Ссылка на досье"]
        ws_notes.append(notes_headers)

        # Сделаем заголовки жирными
        for cell in ws_main[1] + ws_notes[1]:
            cell.font = openpyxl.styles.Font(bold=True)

        # --- ГРУППИРОВКА КОММЕНТАРИЕВ ---
        # Группируем комментарии по user_id, чтобы легче было их склеивать
        user_notes = {}
        for note in notes:
            user_id = note['user_id']
            if user_id not in user_notes:
                user_notes[user_id] = []
            user_notes[user_id].append(note)

        # Текущая строка для записи на листе комментариев (начинаем со 2-й, т.к. 1-я это заголовки)
        current_note_row = 2

        # --- ЗАПОЛНЕНИЕ ЛИСТОВ ---
        for main_row_idx, user in enumerate(dossiers, start=2):
            user_id = user['user_id']
            
            # Форматируем даты из Unix timestamp в читаемый вид
            created_dt = datetime.fromtimestamp(user['created_at']).strftime('%d.%m.%Y') if user['created_at'] else "Нет"
            joined_dt = datetime.fromtimestamp(user['joined_at']).strftime('%d.%m.%Y') if user['joined_at'] else "Нет"

            # Подготавливаем текст всех комментариев
            u_notes = user_notes.get(user_id, [])
            if u_notes:
                # Склеиваем тексты комментариев в один блок
                combined_text = "\n---\n".join([n['note_text'] for n in u_notes])
                first_note_link = f"#'Журнал комментариев'!A{current_note_row}"
                display_text = f"Перейти к комментариям ({len(u_notes)})\n{combined_text}"
            else:
                first_note_link = None
                display_text = "Нет комментариев"

            # Записываем строку в главное досье
            row_data = [
                str(user_id), user['username'], user['nickname'], 
                created_dt, joined_dt, user['status'], user['source'], 
                user['community_role'], user['suspicion_level'], display_text
            ]
            ws_main.append(row_data)

            # Настраиваем ячейку с комментариями
            comments_cell = ws_main.cell(row=main_row_idx, column=10)
            comments_cell.alignment = openpyxl.styles.Alignment(wrap_text=True) # Перенос строк
            
            # Если есть комментарии, делаем ячейку гиперссылкой на лист Журнала
            if first_note_link:
                comments_cell.hyperlink = first_note_link
                comments_cell.font = openpyxl.styles.Font(color="0563C1", underline="single")

            # Записываем комментарии этого пользователя на второй лист
            for note in u_notes:
                note_dt = datetime.fromtimestamp(note['timestamp']).strftime('%d.%m.%Y %H:%M')
                
                ws_notes.append([
                    str(user_id), str(note['moderator_id']), note_dt, note['note_text'], "⬅️ Вернуться в досье"
                ])
                
                # Добавляем гиперссылку для возврата на первый лист
                return_cell = ws_notes.cell(row=current_note_row, column=5)
                return_cell.hyperlink = f"#'Досье (Протокол-ξ)'!A{main_row_idx}"
                return_cell.font = openpyxl.styles.Font(color="0563C1", underline="single")
                
                current_note_row += 1

        # Расширяем колонки для красоты
        ws_main.column_dimensions['J'].width = 50 # Колонка "Комментарии"
        ws_notes.column_dimensions['D'].width = 80 # Текст комментария на втором листе

        # --- ОТПРАВКА В DISCORD ---
        # Сохраняем файл в буфер памяти
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0) # Возвращаем курсор в начало файла

        file = discord.File(fp=buffer, filename=f"Protocol_Xi_{datetime.now().strftime('%Y%m%d')}.xlsx")
        
        embed = discord.Embed(
            title="📥 Протокол-ξ успешно выгружен",
            description="Файл в формате Excel прикреплен к этому сообщению.\n"
                        "В нём настроены перекрестные гиперссылки между досье и комментариями.",
            color=RMC_EMBED_COLOR
        )
        await interaction.followup.send(embed=embed, file=file, ephemeral=True)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        settings_data = settings.load_settings()
        if settings_data.get('auto_stat_enabled', 0) != 1:
            return  
            
        from utils import omnivisor_db
        
        username = f"@{member.name}"
        nickname = member.nick or "Отсутствует"
        created_at = int(member.created_at.timestamp()) if member.created_at else 0
        joined_at = int(member.joined_at.timestamp()) if member.joined_at else 0
        
        # Получаем статус добавления ('new' или 'returning')
        join_status = await omnivisor_db.add_new_member(member.id, username, nickname, created_at, joined_at)

        channel_id = settings_data.get('log_channel')
        log_channel = member.guild.get_channel(channel_id) if channel_id else None
        if not log_channel:
            raise NoLogChannelError() 

        db_data = await omnivisor_db.get_dossier(member.id)
        
        # Настраиваем текст в зависимости от того, новичок это или вернувшийся
        if join_status == 'new':
            title = "📥 Новый участник"
            desc_text = f"Участник {member.mention} добавлен в бд"
        else:
            title = "📥 Возвращение участника"
            desc_text = f"Статус участия {member.mention} обновлён в бд"

        user_info_embed = await self.create_base_embed(
            title=title, 
            user=member, 
            db_data=db_data or {},
            custom_desc=desc_text
        )
        
        roles_list = settings_data.get('auto_stat_roles', [])
        role_mentions = " ".join([f"<@&{r_id}>" for r_id in roles_list]) if roles_list else None
        
        await log_channel.send(content=role_mentions, embed=user_info_embed)


    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        # Проверяем настройки в первую очередь
        settings_data = settings.load_settings()
        if settings_data.get('auto_stat_enabled', 0) != 1:
            return  
            
        from utils import omnivisor_db
        
        # --- 1. ОБНОВЛЕНИЕ СТАТУСА В БД ---
        await omnivisor_db.update_status(member.id, "Да")

        # --- 2. ПРОВЕРКА КАНАЛА ЛОГОВ ---
        channel_id = settings_data.get('log_channel')
        log_channel = member.guild.get_channel(channel_id) if channel_id else None
        if not log_channel:
            raise NoLogChannelError() 
        
        # --- 3. ФОРМИРОВАНИЕ И ОТПРАВКА ---
        db_data = await omnivisor_db.get_dossier(member.id)

        user_info_embed = await self.create_base_embed(
            title="📤 Участник покинул сервер", 
            member=member, 
            db_data=db_data or {}
        )
        
        # Собираем список упоминаний ролей
        roles_list = settings_data.get('auto_stat_roles', [])
        role_mentions = " ".join([f"<@&{r_id}>" for r_id in roles_list]) if roles_list else None
        
        await log_channel.send(content=role_mentions, embed=user_info_embed)

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User | discord.Member):
        settings_data = settings.load_settings()
        if settings_data.get('auto_stat_enabled', 0) != 1:
            return  
            
        from utils import omnivisor_db
        import time
        
        await omnivisor_db.update_status(user.id, "Бан")

        timestamp = int(time.time())
        note_text = "🔨 Авто-лог: Выдана блокировка (Бан) на сервере."
        
        await omnivisor_db.add_note(
            user_id=user.id, 
            moderator_id=self.bot.user.id, 
            note_text=note_text, 
            timestamp=timestamp
        )

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        settings_data = settings.load_settings()
        if settings_data.get('auto_stat_enabled', 0) != 1:
            return  
            
        if before.nick != after.nick:
            old_nick = before.nick or "Отсутствует"
            new_nick = after.nick or "Отсутствует"

            from utils import omnivisor_db
            import time
            
            await omnivisor_db.update_nickname(after.id, new_nick)

            timestamp = int(time.time())
            note_text = f"🔄 Авто-лог: Смена никнейма с «{old_nick}» на «{new_nick}»"
            
            await omnivisor_db.add_note(
                user_id=after.id, 
                moderator_id=self.bot.user.id, 
                note_text=note_text, 
                timestamp=timestamp
            )
>>>>>>> Stashed changes

    @app_commands.command(
        name="omnivisor_settings",
        description="Настройки Протокола-ξ и автостатистики"
    )
    @app_commands.guild_only()
    @app_commands.describe(
<<<<<<< Updated upstream
        role = "Роль для упоминания при автостатистике",
        auto_stat = "Статус автостатистики"
=======
        add_role="Добавить роль для пинга в логах",
        remove_role="Удалить роль из писков пинга",
        clear_roles="Полностью очистить список ролей",
        auto_stat="Статус автостатистики (и записи в БД)"
>>>>>>> Stashed changes
    )
    @app_commands.choices(auto_stat=[
        app_commands.Choice(name="Включить", value=1),
        app_commands.Choice(name="Выключить", value=0)
    ])
<<<<<<< Updated upstream
    async def omnivisor_settings(self, interaction: discord.Interaction, role: Optional[discord.Role], auto_stat: Optional[int]):
=======
    async def omnivisor_settings(self, interaction: discord.Interaction, add_role: Optional[discord.Role] = None, remove_role: Optional[discord.Role] = None, clear_roles: Optional[bool] = False, auto_stat: Optional[int] = None):
        
>>>>>>> Stashed changes
        if not await self.check_admin(interaction):
            await interaction.response.send_message("❌ Недостаточно прав", ephemeral=True)
            return

        settings_data = settings.load_settings()
        current_roles = settings_data.get('auto_stat_roles', [])

<<<<<<< Updated upstream
        if role is None and auto_stat is None:
            saved_role_id = settings_data.get('auto_stat_role_id')
            role_object = interaction.guild.get_role(saved_role_id) if saved_role_id else None
            role_text = role_object.mention if role_object else "❌Не настроена"

=======
        # Если не передано никаких параметров — показываем текущие настройки
        if add_role is None and remove_role is None and clear_roles is False and auto_stat is None:
            roles_text = " ".join([f"<@&{r_id}>" for r_id in current_roles]) if current_roles else "❌ Не настроены"
            
>>>>>>> Stashed changes
            auto_stat_enabled = settings_data.get('auto_stat_enabled')
            auto_stat_text = "✅ Включена" if auto_stat_enabled == 1 else "❌ Выключена"

            embed = discord.Embed(
<<<<<<< Updated upstream
                title="⚙️Сохранённые настройки",
                description=f"В настройках сохранено следующее: \n - Роль упоминания: {role_text} \n - Статус автостатистики: {auto_stat_text}",
=======
                title="⚙️ Сохранённые настройки",
                description=(
                    f"**Роли для уведомлений:** {roles_text}\n"
                    f"**Автостатистика и авто-БД:** {auto_stat_text}"
                ),
>>>>>>> Stashed changes
                color=RMC_EMBED_COLOR,
                timestamp=discord.utils.utcnow()
            )
            await interaction.response.send_message(embed=embed)
            return
            
        changes = []
        needs_save = False

        # 1. Очистка списка ролей
        if clear_roles:
            current_roles = []
            changes.append("🧹 Список ролей полностью очищен")
            needs_save = True

        # 2. Удаление конкретной роли
        if remove_role:
            if remove_role.id in current_roles:
                current_roles.remove(remove_role.id)
                changes.append(f"➖ Удалена роль {remove_role.mention}")
                needs_save = True

        # 3. Добавление новой роли
        if add_role:
            if add_role.is_default():
                await interaction.response.send_message("❌ Ошибка: Нельзя назначить `@everyone`!", ephemeral=True)
                return
            elif add_role.id not in current_roles:
                current_roles.append(add_role.id)
                changes.append(f"➕ Добавлена роль {add_role.mention}")
                needs_save = True

        # Сохраняем обновленный список ролей в словарь
        if needs_save:
            settings_data['auto_stat_roles'] = current_roles

        # 4. Обновление статуса автостатистики
        if auto_stat is not None:  
            settings_data['auto_stat_enabled'] = auto_stat
            needs_save = True
            if auto_stat == 1:
<<<<<<< Updated upstream
                changes.append("✅ Автостатистика включена")
            else:  # auto_stat == 0
                changes.append("❌ Автостатистика выключена")
=======
                changes.append("✅ Автостатистика и БД включены")
            else:
                changes.append("❌ Автостатистика и БД выключены")
>>>>>>> Stashed changes

        # Если были изменения — сохраняем и выводим отчет
        if needs_save:
            settings.save_settings(settings_data)
            
            desc = "**Установлены следующие изменения:**\n" + "\n".join([f"- {c}" for c in changes])
            
            embed = discord.Embed(
                title="✅ Настройки изменены успешно",
                description=desc,
                color=RMC_EMBED_COLOR,
                timestamp=discord.utils.utcnow()
            )
            await interaction.response.send_message(embed=embed)
        else: 
            embed = discord.Embed(
                title="ℹ️ Нет изменений",
                description="Переданные параметры не требуют изменений.",
                color=RMC_EMBED_COLOR,
                timestamp=discord.utils.utcnow()
            )
            await interaction.response.send_message(embed=embed)


<<<<<<< Updated upstream
    @app_commands.command(
        name="user_info",
        description="Получить информацию об участнике"
    )
    @app_commands.guild_only()
    @app_commands.describe(
        member = "Участник для получения информации",
        count_status = "Включить или выключить подсчёт сообщений. ПРЕДУПРЕЖДЕНИЕ: ОЧЕНЬ РЕСУРСОЗАТРАНАЯ ФУНКЦИЯ, ИСПОЛЬЗОВАТЬ С ОСТОРОЖНОСТЬЮ!!!"
    )
    @app_commands.choices(count_status=[
        app_commands.Choice(name="Включить (опасно!)", value=1),
        app_commands.Choice(name="Выключить", value=0)
    ])
    async def user_info(self, interaction: discord.Interaction, member: discord.Member, count_status: Optional[int] = False):
        if not await self.check_admin(interaction):
            await interaction.response.send_message("❌ Недостаточно прав", ephemeral=True)
            return
        

        try:
            settings_data = settings.load_settings()
            channel_id = settings_data.get('log_channel')
            log_channel = interaction.guild.get_channel(channel_id) if channel_id else None 

            member_roles = [role for role in member.roles if not role.is_default() and not role.managed]
            role_mentions = [role.mention for role in member_roles]
            roles_text = ", ".join(role_mentions) if role_mentions else "❌ Нет ролей"

            if not log_channel:
                embed = discord.Embed(
                    title="❌ Ошибка",
                    description="Канал для логов не настроен! Используйте `/set_log`",
                    color=RMC_EMBED_COLOR
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            await interaction.response.defer(ephemeral=True)

            text=f"{interaction.user.mention}"

            user_info_embed = discord.Embed(
                title="Информация об участнике сервера",
                description=f"Информация об участнике {member.mention}",
                color=RMC_EMBED_COLOR
            )
            user_info_embed.add_field(
                name="Участник",
                value=f"Отображаемое имя: `{member.display_name}` | Глобальное имя: `{member.global_name}` | ID: `{member.id}`",
                inline=False
            )
            user_info_embed.add_field(
                name="Роли участника",
                value=f"{roles_text}"
            )
            timestamp_created_at = int(member.created_at.timestamp())
            timestamp_joined_at = int(member.joined_at.timestamp())

            user_info_embed.add_field(
                name="📅 Даты",
                value=f"Дата создания аккаунта: <t:{timestamp_created_at}:D> | Дата захода на сервер: <t:{timestamp_joined_at}:D>",
                inline=False
            )
            first_message_info = await self.find_first_message(member)
            if not first_message_info:
                first_message_info = "❌ Не удалось найти первое сообщение"
            user_info_embed.add_field(
                name="📝 Первое сообщение",
                value=first_message_info,
                inline=False
            )
            last_message_info = await self.find_last_message(member)
            if not last_message_info:
                last_message_info = "❌ Не удалось найти последнее сообщение"
            user_info_embed.add_field(
                name="📝 Последнее сообщение",
                value=last_message_info,
                inline=False
            )
            count_status_bool = bool(count_status)
            if count_status_bool:
                message_count = await self.count_messages_slow(member, interaction.user)
                display_value = f"~{message_count}"
            else:
                message_count = "❌ Подсчёт сообщений выключен"
                display_value = message_count
            user_info_embed.add_field(
                name="📝 Количество сообщений",
                value=display_value,
                inline=False
            )
            user_info_embed.set_author(
                name=member.display_name,
                icon_url=member.avatar.url
            )
            user_info_embed.set_footer(
                text=f"Запросил: {interaction.user.display_name} ({interaction.user.id})",
                icon_url=interaction.user.avatar.url
            )

            response_embed = discord.Embed(
                title="✅ Информация успешно собрана",
                description=f"Собранная информация отправлена в {log_channel.mention}",
                color=RMC_EMBED_COLOR
            )


            await log_channel.send(embed=user_info_embed, content=text)
            await interaction.followup.send(embed=response_embed, ephemeral=True)
            

            

        except Exception as e:
            embed = discord.Embed(
                title="❌ Ошибка",
                description=f"Не удалось получить информацию об участнике {member.mention}: ```{e}```",
                color=RMC_EMBED_COLOR
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

=======
>>>>>>> Stashed changes
async def setup(bot: commands.Bot):
    await bot.add_cog(Omnivisor(bot))