import discord
import re
import time
from typing import Optional
from discord.ext import commands
from discord import app_commands
from constants import RMC_EMBED_COLOR
from utils import settings_cache as settings
from utils import interpol_db
from utils.permissions import check_admin_interaction


class InterpolApplyModal(discord.ui.Modal, title="Внесение нарушителя в Интерпол"):
    offender = discord.ui.TextInput(
        label="ID или Упоминание нарушителя",
        placeholder="Введите Discord ID (123456789...) или @user",
        min_length=3,
        max_length=50,
        required=True
    )
    reason = discord.ui.TextInput(
        label="Причина внесения",
        style=discord.TextStyle.paragraph,
        placeholder="Опишите причину внесения...",
        min_length=5,
        max_length=1000,
        required=True
    )
    evidence = discord.ui.TextInput(
        label="Ссылка на доказательства / Комментарий",
        style=discord.TextStyle.paragraph,
        placeholder="Укажите ссылки на доказательства или комментарий...",
        min_length=3,
        max_length=1000,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        # Парсим ID из текста или упоминания
        digits = re.findall(r'\d+', self.offender.value)
        if not digits:
            return await interaction.response.send_message(
                "❌ Некорректный ID или упоминание нарушителя. Укажите числовой ID или упоминание.",
                ephemeral=True
            )

        offender_id = int(digits[0])
        if len(str(offender_id)) < 15:
            return await interaction.response.send_message(
                "❌ Указан слишком короткий ID пользователя. ID должен содержать 15-20 цифр.",
                ephemeral=True
            )

        # Проверяем существование пользователя через API Discord
        offender_user = interaction.guild.get_member(offender_id)
        if not offender_user:
            try:
                offender_user = await interaction.client.fetch_user(offender_id)
            except discord.NotFound:
                return await interaction.response.send_message(
                    "❌ Пользователь с таким ID не найден в Discord.",
                    ephemeral=True
                )
            except discord.HTTPException:
                pass

        settings_data = settings.load_settings()
        mod_channel_id = settings_data.get('interpol_moderation_channel_id')
        if not mod_channel_id:
            return await interaction.response.send_message(
                "❌ Канал модерации Интерпола не настроен. Обратитесь к Администрации.",
                ephemeral=True
            )

        mod_channel = interaction.guild.get_channel(mod_channel_id)
        if not mod_channel:
            return await interaction.response.send_message(
                "❌ Канал модерации не найден на сервере. Обратитесь к Администрации.",
                ephemeral=True
            )

        # Формируем Embed для канала модерации
        offender_tag = f"{offender_user.mention}" if offender_user else f"<@{offender_id}>"
        mod_embed = discord.Embed(
            title="📥 Новая заявка в Интерпол",
            color=RMC_EMBED_COLOR,
            timestamp=discord.utils.utcnow()
        )
        mod_embed.add_field(name="Нарушитель", value=f"{offender_tag}\nID: `{offender_id}`", inline=True)
        mod_embed.add_field(name="Заявитель", value=f"{interaction.user.mention}\nID: `{interaction.user.id}`", inline=True)
        mod_embed.add_field(name="Причина", value=self.reason.value, inline=False)
        mod_embed.add_field(name="Доказательства / Комментарий", value=self.evidence.value, inline=False)

        await mod_channel.send(embed=mod_embed, view=InterpolModerationView())
        await interaction.response.send_message("✅ Заявка отправлена на рассмотрение.", ephemeral=True)


class InterpolApplyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Внести нарушителя в Интерпол",
        style=discord.ButtonStyle.danger,
        custom_id="interpol_apply_btn",
        emoji="🚨"
    )
    async def apply_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(InterpolApplyModal())


class InterpolModerationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Принять",
        style=discord.ButtonStyle.green,
        custom_id="interpol_mod_accept",
        emoji="✅"
    )
    async def accept_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await check_admin_interaction(interaction)
        except Exception:
            return await interaction.response.send_message(
                "❌ Недостаточно прав для принятия решения по заявкам.",
                ephemeral=True
            )

        await interaction.response.defer()

        embed = interaction.message.embeds[0]

        # Извлекаем данные из Embed
        offender_field = embed.fields[0].value
        reporter_field = embed.fields[1].value
        reason = embed.fields[2].value
        evidence = embed.fields[3].value

        offender_ids = re.findall(r'\d{15,20}', offender_field)
        reporter_ids = re.findall(r'\d{15,20}', reporter_field)

        offender_id = int(offender_ids[0]) if offender_ids else 0
        reporter_id = int(reporter_ids[0]) if reporter_ids else interaction.user.id

        # Отключаем кнопки
        for item in self.children:
            item.disabled = True

        embed.color = discord.Color.green()
        embed.add_field(name="📊 Статус", value="✅ **Принято**", inline=True)
        embed.add_field(name="👮 Обработал", value=interaction.user.mention, inline=True)

        await interaction.message.edit(embed=embed, view=self)

        # Публикация карточки нарушителя в публичный канал Интерпола
        settings_data = settings.load_settings()
        public_channel_id = settings_data.get('interpol_public_channel_id')
        public_channel = interaction.guild.get_channel(public_channel_id) if public_channel_id else None

        # Создаем запись в БД
        record_id = await interpol_db.add_record(
            user_id=offender_id,
            reason=reason,
            evidence=evidence,
            reporter_id=reporter_id,
            moderator_id=interaction.user.id
        )

        public_msg_id = None
        if public_channel:
            card_embed = discord.Embed(
                title="🚨 КАРТОЧКА НАРУШИТЕЛЯ ИНТЕРПОЛА",
                color=discord.Color.red(),
                timestamp=discord.utils.utcnow()
            )
            card_embed.add_field(name="№ Записи", value=f"`#{record_id}`", inline=True)
            card_embed.add_field(name="Нарушитель", value=f"<@{offender_id}>\nID: `{offender_id}`", inline=True)
            card_embed.add_field(name="Причина", value=reason, inline=False)
            card_embed.add_field(name="Доказательства / Комментарий", value=evidence, inline=False)
            card_embed.add_field(name="Модератор", value=interaction.user.mention, inline=True)
            card_embed.set_footer(text=f"Запись #{record_id} • Интерпол")

            try:
                public_msg = await public_channel.send(embed=card_embed)
                public_msg_id = public_msg.id
                await interpol_db.update_public_message(record_id, public_channel.id, public_msg_id)
            except discord.HTTPException:
                pass

        await interaction.followup.send(
            f"✅ Заявка принята. Нарушитель <@{offender_id}> внесен в БД Интерпола (Запись `#{record_id}`).",
            ephemeral=True
        )

    @discord.ui.button(
        label="Отклонить",
        style=discord.ButtonStyle.red,
        custom_id="interpol_mod_reject",
        emoji="✖"
    )
    async def reject_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await check_admin_interaction(interaction)
        except Exception:
            return await interaction.response.send_message(
                "❌ Недостаточно прав для принятия решения по заявкам.",
                ephemeral=True
            )

        await interaction.response.defer()

        embed = interaction.message.embeds[0]

        # Отключаем кнопки
        for item in self.children:
            item.disabled = True

        embed.color = discord.Color.dark_grey()
        embed.add_field(name="📊 Статус", value="❌ **Отклонено**", inline=True)
        embed.add_field(name="👮 Обработал", value=interaction.user.mention, inline=True)

        await interaction.message.edit(embed=embed, view=self)
        await interaction.followup.send("❌ Заявка отклонена. Запись в базу данных не внесена.", ephemeral=True)


class InterpolPaginationView(discord.ui.View):
    def __init__(self, records: list, author_id: int, per_page: int = 20):
        super().__init__(timeout=180)
        self.records = records
        self.author_id = author_id
        self.per_page = per_page
        self.current_page = 0
        self.total_pages = (len(records) - 1) // per_page + 1
        self.update_buttons()

    def update_buttons(self):
        self.prev_button.disabled = (self.current_page == 0)
        self.next_button.disabled = (self.current_page >= self.total_pages - 1)

    def create_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=f"📋 База данных Интерпола (Всего записей: {len(self.records)})",
            color=RMC_EMBED_COLOR,
            timestamp=discord.utils.utcnow()
        )
        start_idx = self.current_page * self.per_page
        end_idx = start_idx + self.per_page
        page_records = self.records[start_idx:end_idx]

        lines = []
        for r in page_records:
            user_mention = f"<@{r['user_id']}>"
            reason_short = r['reason'][:50] + ("..." if len(r['reason']) > 50 else "")
            lines.append(f"**#{r['id']}** | {user_mention} (`{r['user_id']}`) — {reason_short}")

        embed.description = "\n".join(lines) if lines else "Нет записей."
        embed.set_footer(text=f"Страница {self.current_page + 1} из {self.total_pages}")
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ Управлять пагинацией может только автор команды.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="◀", style=discord.ButtonStyle.primary, custom_id="interpol_page_prev")
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.create_embed(), view=self)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.primary, custom_id="interpol_page_next")
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.create_embed(), view=self)


class Interpol(commands.Cog):
    """Система Интерпол"""
    required_access = "admin"

    interpol = app_commands.Group(name="interpol", description="Команды управления системой Интерпол")

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        await interpol_db.init_db()
        self.bot.add_view(InterpolApplyView())
        self.bot.add_view(InterpolModerationView())

    # --- Команды настройки каналов (Администрация) ---

    @interpol.command(
        name="set_apply_channel",
        description="Установить канал подачи заявок в Интерпол"
    )
    @app_commands.guild_only()
    @app_commands.describe(
        channel="Канал для кнопки подачи заявок",
        rules_text="Текст правил / инструкция (необязательно)"
    )
    async def set_apply_channel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        rules_text: Optional[str] = None
    ):
        await check_admin_interaction(interaction)
        await interaction.response.defer(ephemeral=True)

        settings_data = settings.load_settings()

        # Отключаем старый пост, если он существовал
        old_channel_id = settings_data.get('interpol_apply_channel_id')
        old_message_id = settings_data.get('interpol_apply_message_id')
        if old_channel_id and old_message_id:
            try:
                old_channel = interaction.guild.get_channel(old_channel_id)
                if old_channel:
                    old_msg = await old_channel.fetch_message(int(old_message_id))
                    disabled_view = discord.ui.View.from_message(old_msg)
                    for child in disabled_view.children:
                        child.disabled = True
                    await old_msg.edit(view=disabled_view)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass

        description = rules_text if rules_text else (
            "Нажмите кнопку ниже, чтобы заполнить отчёт о нарушителе для внесения в базу данных Интерпола.\n\n"
            "После отправки ваша заявка будет передана на рассмотрение Администрации."
        )

        apply_embed = discord.Embed(
            title="🚨 Внесение нарушителя в Интерпол",
            description=description,
            color=RMC_EMBED_COLOR
        )
        new_msg = await channel.send(embed=apply_embed, view=InterpolApplyView())

        settings_data['interpol_apply_channel_id'] = channel.id
        settings_data['interpol_apply_message_id'] = new_msg.id
        if rules_text:
            settings_data['interpol_rules_text'] = rules_text
        settings.save_settings(settings_data)

        await interaction.followup.send(
            f"✅ Канал подачи заявок успешно установлен: {channel.mention}",
            ephemeral=True
        )

    @interpol.command(
        name="set_moderation_channel",
        description="Установить канал модерации для рассмотрения заявок Интерпола"
    )
    @app_commands.guild_only()
    @app_commands.describe(channel="Канал для поступающих заявок")
    async def set_moderation_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await check_admin_interaction(interaction)
        await interaction.response.defer(ephemeral=True)

        settings_data = settings.load_settings()
        settings_data['interpol_moderation_channel_id'] = channel.id
        settings.save_settings(settings_data)

        await interaction.followup.send(
            f"✅ Канал модерации заявок успешно установлен: {channel.mention}",
            ephemeral=True
        )

    @interpol.command(
        name="set_public_channel",
        description="Установить публичный канал для карточек Интерпола"
    )
    @app_commands.guild_only()
    @app_commands.describe(channel="Канал для публикации утвержденных карточек")
    async def set_public_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await check_admin_interaction(interaction)
        await interaction.response.defer(ephemeral=True)

        settings_data = settings.load_settings()
        settings_data['interpol_public_channel_id'] = channel.id
        settings.save_settings(settings_data)

        await interaction.followup.send(
            f"✅ Публичный канал Интерпола успешно установлен: {channel.mention}",
            ephemeral=True
        )

    # --- Команды управления и просмотра ---

    @interpol.command(
        name="remove",
        description="Удалить запись о нарушителе из БД Интерпола"
    )
    @app_commands.guild_only()
    @app_commands.describe(target="ID записи (#) или Discord ID нарушителя")
    async def remove_record(self, interaction: discord.Interaction, target: str):
        await check_admin_interaction(interaction)
        await interaction.response.defer(ephemeral=True)

        digits = re.findall(r'\d+', target)
        if not digits:
            return await interaction.followup.send("❌ Укажите числовой ID записи или Discord ID нарушителя.", ephemeral=True)

        identifier = int(digits[0])
        removed_records = await interpol_db.remove_record(identifier)

        if not removed_records:
            return await interaction.followup.send("❌ Запись с таким ID не найдена в базе данных Интерпола.", ephemeral=True)

        # Удаляем / обновляем публичные карточки нарушителей
        for record in removed_records:
            pub_chan_id = record.get('public_channel_id')
            pub_msg_id = record.get('public_message_id')
            if pub_chan_id and pub_msg_id:
                pub_channel = interaction.guild.get_channel(pub_chan_id)
                if pub_channel:
                    try:
                        msg = await pub_channel.fetch_message(pub_msg_id)
                        await msg.delete()
                    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                        pass

        await interaction.followup.send(
            f"✅ Успешно удалено записей из базы данных Интерпола: `{len(removed_records)}`.",
            ephemeral=True
        )

    @interpol.command(
        name="list",
        description="Показать список всех нарушителей в базе Интерпола"
    )
    @app_commands.guild_only()
    async def list_records(self, interaction: discord.Interaction):
        await interaction.response.defer()

        records = await interpol_db.get_all_records()
        if not records:
            return await interaction.followup.send("ℹ️ База данных Интерпола пока пуста.")

        pagination_view = InterpolPaginationView(records, author_id=interaction.user.id)
        embed = pagination_view.create_embed()
        await interaction.followup.send(embed=embed, view=pagination_view)

    @interpol.command(
        name="show",
        description="Показать полную карточку конкретного нарушителя из БД"
    )
    @app_commands.guild_only()
    @app_commands.describe(target="ID записи (#) или Discord ID нарушителя")
    async def show_record(self, interaction: discord.Interaction, target: str):
        await interaction.response.defer()

        digits = re.findall(r'\d+', target)
        if not digits:
            return await interaction.followup.send("❌ Укажите числовой ID записи или Discord ID нарушителя.")

        identifier = int(digits[0])
        records = await interpol_db.get_records_by_target(identifier)

        if not records:
            return await interaction.followup.send("❌ Нарушитель или запись с таким ID не найдена в БД Интерпола.")

        for r in records:
            card_embed = discord.Embed(
                title="🚨 КАРТОЧКА НАРУШИТЕЛЯ ИНТЕРПОЛА",
                color=discord.Color.red(),
                timestamp=discord.utils.utcnow()
            )
            card_embed.add_field(name="№ Записи", value=f"`#{r['id']}`", inline=True)
            card_embed.add_field(name="Нарушитель", value=f"<@{r['user_id']}>\nID: `{r['user_id']}`", inline=True)
            card_embed.add_field(name="Причина", value=r['reason'], inline=False)
            card_embed.add_field(name="Доказательства / Комментарий", value=r['evidence'], inline=False)
            card_embed.add_field(name="Заявитель", value=f"<@{r['reporter_id']}>", inline=True)
            card_embed.add_field(name="Модератор", value=f"<@{r['moderator_id']}>", inline=True)
            card_embed.add_field(name="Дата внесения", value=f"<t:{r['created_at']}:F>", inline=False)
            card_embed.set_footer(text=f"Запись #{r['id']} • Интерпол")

            await interaction.followup.send(embed=card_embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Interpol(bot))
