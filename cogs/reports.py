import discord
import re
from discord.ext import commands
from discord import app_commands
from utils.permissions import check_cog_access
from utils import settings_cache as settings
from discord.ui import View, Button
import sys
import os
from constants import RMC_EMBED_COLOR

<<<<<<< Updated upstream
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

=======
#TODO: сделать логику сохранения кнопок ответа на репорт чтобы они не умирали при перезагрузке
# что-то сделать с архивацией ветки (получить ID через self.report_message.id)

class ConfirmView(discord.ui.View):
    def __init__(self, label: str):
        super().__init__(timeout=30)
        self.value = None

    @discord.ui.button(label="Да", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = True
        self.stop()

    @discord.ui.button(label="Нет", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        self.stop()

class ReportCommentModal(discord.ui.Modal, title="Комментарий к ответу"):
    def __init__(self, report_message: discord.Message, response_type: str):
        super().__init__()
        self.report_message = report_message
        self.response_type = response_type

        self.comment = discord.ui.TextInput(
            label=f"Комментарий ({response_type})",
            placeholder="Опишите решение или причину...",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=1000
        )
        self.add_item(self.comment)

    async def on_submit(self, interaction: discord.Interaction):
        comment = self.comment.value

        embed = self.report_message.embeds[0]
        
        for i, field in enumerate(embed.fields):
            if field.name == "📊 Статус":
                embed.set_field_at(i, name="📊 Статус", value=self.response_type, inline=True)
                break
        
        embed.color = discord.Color.green() if "✅" in self.response_type else discord.Color.orange()
        embed.add_field(name="👮 Ответственный", value=interaction.user.mention, inline=True)
        embed.add_field(name="💬 Комментарий", value=comment, inline=False)

        thread = interaction.guild.get_thread(self.report_message.id)
        if thread:
            try:
                await thread.edit(archived=True, locked=True, reason=f"Репорт закрыт: {self.response_type}")
            except discord.HTTPException:
                pass

        await self.report_message.edit(embed=embed, view=None)
        await interaction.response.send_message("✅ Ответ добавлен к репорту.", ephemeral=True)

class AnswerTypeView(discord.ui.View):
    def __init__(self, report_message: discord.Message):
        super().__init__(timeout=120)
        self.report_message = report_message

    @discord.ui.button(label="Выполнено", style=discord.ButtonStyle.success, emoji="✅")
    async def done_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ReportCommentModal(self.report_message, "✅ Выполнено"))

    @discord.ui.button(label="Проигнорировано", style=discord.ButtonStyle.secondary, emoji="⏭️")
    async def ignore_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ReportCommentModal(self.report_message, "⏭️ Проигнорировано"))

    @discord.ui.button(label="Отменить", style=discord.ButtonStyle.danger, emoji="❌")
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="❌ Действие отменено.", view=None)

class ReportAnswerView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @classmethod
    def build(cls, in_blacklist: bool, has_thread: bool):
        view = cls()
        if in_blacklist:
            view.remove_item(view.add_blacklist_btn)
        else:
            view.remove_item(view.remove_blacklist_btn)
            
        if not has_thread:
            view.remove_item(view.go_to_thread_btn)
            
        return view

    def _get_reporter_id(self, message: discord.Message):
        try:
            val = message.embeds[0].fields[0].value
            match = re.search(r'`(\d+)`', val)
            return int(match.group(1)) if match else None
        except Exception:
            return None

    def _check_admin(self, interaction: discord.Interaction):
        data = settings.load_settings()
        admin_roles_ids = set(data.get("admin_roles", []))
        return any(r.id in admin_roles_ids for r in interaction.user.roles)

    @discord.ui.button(label="🚫 Добавить в ЧС", style=discord.ButtonStyle.danger, emoji="🚫", custom_id="report_add_blacklist")
    async def add_blacklist_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check_admin(interaction):
            return await interaction.response.send_message("❌ У вас нет прав для выполнения этого действия.", ephemeral=True)

        reporter_id = self._get_reporter_id(interaction.message)
        if not reporter_id:
            return await interaction.response.send_message("❌ Ошибка: Не удалось определить ID отправителя.", ephemeral=True)

        confirm_view = ConfirmView("Добавить в ЧС репортов?")
        await interaction.response.send_message(
            f"Вы уверены, что хотите добавить <@{reporter_id}> в чёрный список репортов?",
            view=confirm_view,
            ephemeral=True
        )
        
        await confirm_view.wait()
        if confirm_view.value:
            data = settings.load_settings()
            blacklist = set(data.get("report_blacklist", []))

            if reporter_id in blacklist:
                return await interaction.edit_original_response(content="❌ Пользователь уже в ЧС.", view=None)

            blacklist.add(reporter_id)
            data["report_blacklist"] = list(blacklist)
            settings.save_settings(data)

            await interaction.edit_original_response(
                content=f"✅ <@{reporter_id}> добавлен в чёрный список репортов.",
                view=None
            )
            
            embed = interaction.message.embeds[0]
            embed.set_field_at(0, 
                name="👤 Отправитель жалобы", 
                value=f"<@{reporter_id}> (`{reporter_id}`) 🚫", 
                inline=True
            )
            has_thread = interaction.guild.get_thread(interaction.message.id) is not None
            new_view = ReportAnswerView.build(in_blacklist=True, has_thread=has_thread)
            await interaction.message.edit(embed=embed, view=new_view)

    @discord.ui.button(label="✅ Удалить из ЧС", style=discord.ButtonStyle.success, emoji="✅", custom_id="report_remove_blacklist")
    async def remove_blacklist_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check_admin(interaction):
            return await interaction.response.send_message("❌ У вас нет прав для выполнения этого действия.", ephemeral=True)

        reporter_id = self._get_reporter_id(interaction.message)
        if not reporter_id:
            return await interaction.response.send_message("❌ Ошибка: Не удалось определить ID отправителя.", ephemeral=True)

        confirm_view = ConfirmView("Удалить из ЧС репортов?")
        await interaction.response.send_message(
            f"Вы уверены, что хотите удалить <@{reporter_id}> из чёрного списка репортов?",
            view=confirm_view,
            ephemeral=True
        )
        
        await confirm_view.wait()
        if confirm_view.value:
            data = settings.load_settings()
            blacklist = set(data.get("report_blacklist", []))

            if reporter_id not in blacklist:
                return await interaction.edit_original_response(content="❌ Пользователь не в ЧС.", view=None)

            blacklist.remove(reporter_id)
            data["report_blacklist"] = list(blacklist)
            settings.save_settings(data)

            await interaction.edit_original_response(
                content=f"♻️ <@{reporter_id}> удалён из чёрного списка репортов.",
                view=None
            )
            
            embed = interaction.message.embeds[0]
            embed.set_field_at(0, 
                name="👤 Отправитель жалобы", 
                value=f"<@{reporter_id}> (`{reporter_id}`)", 
                inline=True
            )
            has_thread = interaction.guild.get_thread(interaction.message.id) is not None
            new_view = ReportAnswerView.build(in_blacklist=False, has_thread=has_thread)
            await interaction.message.edit(embed=embed, view=new_view)

    @discord.ui.button(label="💬 Добавить ответ на репорт", style=discord.ButtonStyle.primary, emoji="💬", custom_id="report_give_answer")
    async def give_answer_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check_admin(interaction):
            return await interaction.response.send_message("❌ У вас нет прав для ответа на репорты.", ephemeral=True)

        view = AnswerTypeView(interaction.message)
        await interaction.response.send_message(
            "📋 **Выберите тип ответа:**\n\n"
            "✅ **Выполнено** - жалоба рассмотрена и приняты меры\n"
            "⏭️ **Проигнорировано** - жалоба не требует действий\n"
            "❌ **Отменить** - вернуться назад",
            view=view,
            ephemeral=True
        )

    @discord.ui.button(label="💬 Обсуждение", style=discord.ButtonStyle.blurple, emoji="💬", custom_id="report_go_to_thread")
    async def go_to_thread_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        thread = interaction.guild.get_thread(interaction.message.id)
        if thread:
            await interaction.response.send_message(
                f"📎 Перейти к обсуждению: {thread.mention}",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "❌ Ветка обсуждения не найдена.",
                ephemeral=True
            )

# ====== Модальное окно для указания причины ======
class ReportReasonModal(discord.ui.Modal, title="Отправка жалобы"):
    def __init__(self, cog: commands.Cog, target_message: discord.Message):
        super().__init__()
        self.cog = cog
        self.target_message = target_message

        self.reason = discord.ui.TextInput(
            label="Причина жалобы",
            style=discord.TextStyle.paragraph,
            placeholder="Опишите причину жалобы...",
            required=False,
            max_length=500
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        success = await self.cog.send_report(
            interaction.guild, interaction.user, self.target_message, str(self.reason)
        )
        if success:
            await interaction.response.send_message("✅ Репорт отправлен администрации.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Репорт не отправлен, т.к. на сервере не настроен канал для репортов. Обратитесь к Администрации.", ephemeral=True)
>>>>>>> Stashed changes

class Reports(commands.Cog):
    required_access = "admin"

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        # Регистрируем View глобально, чтобы кнопки реагировали после рестарта бота
        self.bot.add_view(ReportAnswerView())

    async def cog_check(self, ctx: commands.Context):
        allowed = await check_cog_access(ctx, self.required_access)
        if not allowed:
            raise commands.CheckFailure()
        return True

    # ====== Работа с настройками ======
    def update_report_channels(self, new_ids):
        data = settings.load_settings()

        data["report_channels"] = list(new_ids)
        settings.save_settings(data)

    def update_report_blacklist(self, new_ids):
        data = settings.load_settings()

        data["report_blacklist"] = list(new_ids)
        settings.save_settings(data)

    # ====== Управление каналами для репортов ======
    @commands.hybrid_command(
        name="addreport",
        with_app_command=True,  # регистрирует как slash
        description="Добавляет канал в список каналов, куда отправляются репорты"
    )
    @commands.has_permissions(manage_channels=True)
    async def addreport(self, ctx, channel: discord.TextChannel = None):
        if channel is None:
            channel = ctx.channel
        data = settings.load_settings()

        report_channel_ids = set(data.get("report_channels", []))

        if channel.id in report_channel_ids:
            embed = discord.Embed(
                description=f"⚠️ Канал {channel.mention} уже в списке репортов.",
                color=discord.Color.dark_gray()
            )
            await ctx.reply(
                embed=embed
            )
            return

        report_channel_ids.add(channel.id)
        self.update_report_channels(report_channel_ids)
        embed = discord.Embed(
            description=f"✅ Канал {channel.mention} добавлен для репортов.",
            color=discord.Color.green()
        )
        await ctx.reply(
            embed=embed
        )

    @commands.hybrid_command(
        name="removereport",
        with_app_command=True,  # регистрирует как slash
        description="Удаляет канал из списка каналов, куда отправляются репорты"
    )
    @commands.has_permissions(manage_channels=True)
    async def removereport(self, ctx, channel: discord.TextChannel = None):
        if channel is None:
            channel = ctx.channel

        data = settings.load_settings()

        report_channel_ids = set(data.get("report_channels", []))

        if channel.id not in report_channel_ids:
            embed = discord.Embed(
                description=f"⚠️ Канал {channel.mention} не найден в списке репортов.",
                color=discord.Color.dark_gray()
            )
            await ctx.reply(
                embed=embed
            )
            return

        report_channel_ids.remove(channel.id)
        self.update_report_channels(report_channel_ids)
        embed = discord.Embed(
            description=f"❌ Канал {channel.mention} удалён из репортов.",
            color=discord.Color.dark_red()
        )
        await ctx.reply(
            embed=embed
        )
    @commands.hybrid_command(
        name="listreports",
        with_app_command=True,  # регистрирует как slash
        description="Список репорт-каналов"
    )
    async def listreports(self, ctx):
        data = settings.load_settings()

        report_channel_ids = set(data.get("report_channels", []))

        if not report_channel_ids:
            embed = discord.Embed(
                description="📭 Список репорт-каналов пуст.",
                color=discord.Color.dark_gray()
            )
            await ctx.reply(
                embed=embed
            )
            return

        embed = discord.Embed(title="🚨 Каналы для репортов", color=RMC_EMBED_COLOR)
        for cid in report_channel_ids:
            channel = self.bot.get_channel(cid)
            if channel:
                embed.add_field(name=channel.name, value=channel.mention, inline=False)
            else:
                embed.add_field(name="❓ Неизвестный канал", value=f"ID: {cid}", inline=False)
        await ctx.send(embed=embed)
    @commands.hybrid_command(
        name="report_addblacklist",
        with_app_command=True,
        description="Добавить участника в чёрный список репортов."
    )
    @commands.has_permissions(kick_members=True)
    async def report_addblacklist(self, ctx, member: discord.Member):
        data = settings.load_settings()

        blacklist = set(data.get("report_blacklist", []))

        if member.id in blacklist:
            embed = discord.Embed(
                description=f"⚠️ {member.mention} уже в чёрном списке.",
                color=discord.Color.red()
            )
            await ctx.reply(embed=embed)
            return
        else:
            blacklist.add(member.id)
            self.update_report_blacklist(blacklist)

            embed = discord.Embed(
                description=f"✅ {member.mention} добавлен в чёрный список репортов.",
                color=discord.Color.green()
            )
            await ctx.reply(embed=embed)

    @commands.hybrid_command(
            name="report_removeblacklist",
            with_app_command=True,
            description="Удалить участника из чёрного списка репортов"
    )
    @commands.has_permissions(kick_members=True)
    async def report_removeblacklist(self, ctx, member: discord.Member):
        data = settings.load_settings()
        blacklist = set(data.get("report_blacklist", []))

        if member.id not in blacklist:
            embed = discord.Embed(
                description=f"❌ {member.mention} не найден в чёрном списке.",
                color=discord.Color.red()
            )
            await ctx.reply(embed=embed)
            return

        blacklist.remove(member.id)
        self.update_report_blacklist(blacklist)

        embed = discord.Embed(
            description=f"✅ {member.mention} удалён из чёрного списка репортов.",
            color=discord.Color.green()
        )
        await ctx.reply(embed=embed)

    @commands.hybrid_command(
            name="report_showblacklist",
            with_app_command=True,
            description="Просмотреть чёрный список репортов."
    )
    @commands.has_permissions(kick_members=True)
    async def report_showblacklist(self, ctx):
        data = settings.load_settings()

        blacklist = set(data.get("report_blacklist", []))

        if not blacklist:
            embed = discord.Embed(
                description="📭 Чёрный список пуст.",
                color=RMC_EMBED_COLOR
            )
            await ctx.reply(embed=embed)
            return

        embed = discord.Embed(title="🚫 Чёрный список репортов", color=RMC_EMBED_COLOR)
        for uid in blacklist:
            user = ctx.guild.get_member(uid)
            if user:
                embed.add_field(name=user.display_name, value=user.mention, inline=False)
            else:
                embed.add_field(name="❓ Неизвестный пользователь", value=f"ID: {uid}", inline=False)

        await ctx.send(embed=embed)
    
#----------------------------------------------
    # ====== Внутренний метод для отправки репорта ======
    async def send_report(self, guild: discord.Guild, reporter: discord.Member, target_message: discord.Message, reason: str):
        """Отправка embed-а с жалобой в репорт-каналы, с кнопками ЧС и ответа"""
        data = settings.load_settings()

        report_channel_ids = set(data.get("report_channels", []))
        admin_roles_ids = set(data.get("admin_roles", []))
        blacklist = set(data.get("report_blacklist", []))

        if not report_channel_ids:
            print("Не могу отправить репорт — нет настроенных каналов!")
            return False

        if reporter.id in blacklist:
            admin_mentions = "⚠️ Пользователь в чёрном списке!"
        else:
            admin_mentions = " ".join(
                role.mention
                for rid in admin_roles_ids
                if (role := guild.get_role(rid))
            ) or "⚠️ (Нет настроенных админ-ролей)"

        # Создаем красивый embed
        embed = discord.Embed(
            title="🚨 Новый репорт",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="👤 Отправитель жалобы", value=f"{reporter.mention} (`{reporter.id}`)", inline=True)
        embed.add_field(name="📝 Автор сообщения", value=f"{target_message.author.mention} (`{target_message.author.id}`)", inline=True)
        embed.add_field(name="📋 Причина", value=reason or "—", inline=False)
        embed.add_field(name="💬 Сообщение", value=f"[Перейти к сообщению]({target_message.jump_url})\n```{target_message.content[:100]}{'...' if len(target_message.content) > 100 else ''}```", inline=False)
        embed.add_field(name="📊 Статус", value="⏳ Ожидает рассмотрения", inline=True)
        embed.add_field(name="📅 Дата сообщения", value=f"<t:{int(target_message.created_at.timestamp())}:R>", inline=True)
        embed.set_footer(text=f"ID репорта: {target_message.id}")

        thread = None
        report_message = None

        for cid in report_channel_ids:
            if channel := guild.get_channel(cid):
                report_message = await channel.send(admin_mentions, embed=embed)
                break

        if not report_message:
            print("Не могу отправить репорт — настроенные каналы не найдены на сервере!")
            return False

        if report_message:
            try:
                thread_name = f"Обсуждение репорта от {reporter.display_name}"
                
                thread = await report_message.create_thread(
                    name=thread_name[:100],  
                    reason=f"Обсуждение репорта от {reporter}"
                )
                
                welcome_embed = discord.Embed(
                    title="💬 Обсуждение репорта",
                    color=discord.Color.blue(),
                    description=(
                        f"**Репорт от:** {reporter.mention}\n"
                        f"**На сообщение:** {target_message.author.mention}\n"
                        f"**Причина:** {reason or '—'}\n"
                        f"**Ссылка на сообщение:** [Перейти]({target_message.jump_url})\n\n"
                        f"Используйте эту ветку для обсуждения репорта."
                    )
                )
                await thread.send(embed=welcome_embed)
                
                embed.add_field(
                    name="💬 Ветка обсуждения", 
                    value=f"[Перейти в ветку]({thread.jump_url})", 
                    inline=False
                )
                
                await report_message.edit(embed=embed)
                
            except discord.HTTPException as e:
                print(f"Ошибка при создании ветки: {e}")
                thread = None

<<<<<<< Updated upstream
        # --- View с кнопками ---
        class ReportView(discord.ui.View):
            def __init__(self, reporter: discord.Member, guild: discord.Guild, blacklist: set, admin_roles_ids: set, thread: discord.Thread = None):
                super().__init__(timeout=None)
                self.reporter = reporter
                self.guild = guild
                self.blacklist = blacklist
                self.admin_roles_ids = admin_roles_ids
                self.thread = thread

                if reporter.id in blacklist:
                    self.add_item(RemoveBlacklistButton())
                else:
                    self.add_item(AddBlacklistButton())

                self.add_item(GiveAnswerButton())

                self.add_item(QuickCloseButton())
                
                if thread:
                    self.add_item(GoToThreadButton())

        class AddBlacklistButton(discord.ui.Button):
            def __init__(self):
                super().__init__(label="🚫 Добавить в ЧС", style=discord.ButtonStyle.danger, emoji="🚫")

            async def callback(self, interaction: discord.Interaction):
                if not any(r.id in self.view.admin_roles_ids for r in interaction.user.roles):
                    await interaction.response.send_message("❌ У вас нет прав для выполнения этого действия.", ephemeral=True)
                    return

                confirm_view = ConfirmView("Добавить в ЧС репортов?")
                await interaction.response.send_message(
                    f"Вы уверены, что хотите добавить {self.view.reporter.mention} в чёрный список репортов?",
                    view=confirm_view,
                    ephemeral=True
                )
                
                await confirm_view.wait()
                if confirm_view.value:
                    data = settings.load_settings()
                    blacklist = set(data.get("report_blacklist", []))

                    if self.view.reporter.id in blacklist:
                        await interaction.edit_original_response(content="❌ Пользователь уже в ЧС.", view=None)
                        return

                    blacklist.add(self.view.reporter.id)
                    data["report_blacklist"] = list(blacklist)
                    settings.save_settings(data)

                    await interaction.edit_original_response(
                        content=f"✅ {self.view.reporter.mention} добавлен в чёрный список репортов.",
                        view=None
                    )
                    
                    embed = interaction.message.embeds[0]
                    embed.set_field_at(0, 
                        name="👤 Отправитель жалобы", 
                        value=f"{self.view.reporter.mention} (`{self.view.reporter.id}`) 🚫", 
                        inline=True
                    )
                    await interaction.message.edit(embed=embed, view=ReportView(self.view.reporter, self.view.guild, blacklist, self.view.admin_roles_ids, self.view.thread))

        class RemoveBlacklistButton(discord.ui.Button):
            def __init__(self):
                super().__init__(label="✅ Удалить из ЧС", style=discord.ButtonStyle.success, emoji="✅")

            async def callback(self, interaction: discord.Interaction):
                if not any(r.id in self.view.admin_roles_ids for r in interaction.user.roles):
                    await interaction.response.send_message("❌ У вас нет прав для выполнения этого действия.", ephemeral=True)
                    return

                confirm_view = ConfirmView("Удалить из ЧС репортов?")
                await interaction.response.send_message(
                    f"Вы уверены, что хотите удалить {self.view.reporter.mention} из чёрного списка репортов?",
                    view=confirm_view,
                    ephemeral=True
                )
                
                await confirm_view.wait()
                if confirm_view.value:
                    data = settings.load_settings()
                    blacklist = set(data.get("report_blacklist", []))

                    if self.view.reporter.id not in blacklist:
                        await interaction.edit_original_response(content="❌ Пользователь не в ЧС.", view=None)
                        return

                    blacklist.remove(self.view.reporter.id)
                    data["report_blacklist"] = list(blacklist)
                    settings.save_settings(data)

                    await interaction.edit_original_response(
                        content=f"♻️ {self.view.reporter.mention} удалён из чёрного списка репортов.",
                        view=None
                    )
                    
                    embed = interaction.message.embeds[0]
                    embed.set_field_at(0, 
                        name="👤 Отправитель жалобы", 
                        value=f"{self.view.reporter.mention} (`{self.view.reporter.id}`)", 
                        inline=True
                    )
                    await interaction.message.edit(embed=embed, view=ReportView(self.view.reporter, self.view.guild, blacklist, self.view.admin_roles_ids, self.view.thread))

        class GiveAnswerButton(discord.ui.Button):
            def __init__(self):
                super().__init__(label="💬 Ответить", style=discord.ButtonStyle.primary, emoji="💬")

            async def callback(self, interaction: discord.Interaction):
                if not any(r.id in self.view.admin_roles_ids for r in interaction.user.roles):
                    await interaction.response.send_message("❌ У вас нет прав для ответа на репорты.", ephemeral=True)
                    return

                view = AnswerTypeView(interaction.message)
                await interaction.response.send_message(
                    "📋 **Выберите тип ответа:**\n\n"
                    "✅ **Выполнено** - жалоба рассмотрена и приняты меры\n"
                    "⏭️ **Проигнорировано** - жалоба не требует действий\n"
                    "❌ **Отменить** - вернуться назад",
                    view=view,
                    ephemeral=True
                )

        class QuickCloseButton(discord.ui.Button):
            def __init__(self):
                super().__init__(label="🔒 Быстро закрыть", style=discord.ButtonStyle.secondary, emoji="🔒")

            async def callback(self, interaction: discord.Interaction):
                if not any(r.id in self.view.admin_roles_ids for r in interaction.user.roles):
                    await interaction.response.send_message("❌ У вас нет прав для закрытия репортов.", ephemeral=True)
                    return

                embed = interaction.message.embeds[0]
                embed.set_field_at(4, name="📊 Статус", value="🔒 Закрыто", inline=True)
                embed.color = discord.Color.green()
                embed.add_field(name="👮 Ответственный", value=interaction.user.mention, inline=True)
                embed.add_field(name="💬 Комментарий", value="Решено (быстрое закрытие)", inline=False)

                if self.view.thread:
                    try:
                        await self.view.thread.edit(archived=True, locked=True, reason="Репорт закрыт")
                    except discord.HTTPException:
                        pass

                await interaction.message.edit(embed=embed, view=None)
                await interaction.response.send_message("✅ Репорт закрыт.", ephemeral=True)

        class GoToThreadButton(discord.ui.Button):
            def __init__(self):
                super().__init__(label="💬 Обсуждение", style=discord.ButtonStyle.blurple, emoji="💬")

            async def callback(self, interaction: discord.Interaction):
                if self.view.thread:
                    await interaction.response.send_message(
                        f"📎 Перейти к обсуждению: {self.view.thread.mention}",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        "❌ Ветка обсуждения не найдена.",
                        ephemeral=True
                    )

        class ConfirmView(discord.ui.View):
            def __init__(self, label: str):
                super().__init__(timeout=30)
                self.value = None

            @discord.ui.button(label="Да", style=discord.ButtonStyle.danger)
            async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
                self.value = True
                self.stop()

            @discord.ui.button(label="Нет", style=discord.ButtonStyle.secondary)
            async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
                self.value = False
                self.stop()

        class AnswerTypeView(discord.ui.View):
            def __init__(self, report_message: discord.Message):
                super().__init__(timeout=120)
                self.report_message = report_message

            @discord.ui.button(label="Выполнено", style=discord.ButtonStyle.success, emoji="✅")
            async def done_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                await interaction.response.send_modal(ReportCommentModal(self.report_message, "✅ Выполнено"))

            @discord.ui.button(label="Проигнорировано", style=discord.ButtonStyle.secondary, emoji="⏭️")
            async def ignore_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                await interaction.response.send_modal(ReportCommentModal(self.report_message, "⏭️ Проигнорировано"))

            @discord.ui.button(label="Отменить", style=discord.ButtonStyle.danger, emoji="❌")
            async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                await interaction.response.edit_message(content="❌ Действие отменено.", view=None)

        # --- Модальное окно для комментария ---
        class ReportCommentModal(discord.ui.Modal, title="Комментарий к ответу"):
            def __init__(self, report_message: discord.Message, response_type: str):
                super().__init__()
                self.report_message = report_message
                self.response_type = response_type

                self.comment = discord.ui.TextInput(
                    label=f"Комментарий ({response_type})",
                    placeholder="Опишите решение или причину...",
                    style=discord.TextStyle.paragraph,
                    required=True,
                    max_length=1000
                )
                self.add_item(self.comment)

            async def on_submit(self, interaction: discord.Interaction):
                comment = self.comment.value

                embed = self.report_message.embeds[0]
                
                for i, field in enumerate(embed.fields):
                    if field.name == "📊 Статус":
                        embed.set_field_at(i, name="📊 Статус", value=self.response_type, inline=True)
                        break
                
                embed.color = discord.Color.green() if "✅" in self.response_type else discord.Color.orange()
                embed.add_field(name="👮 Ответственный", value=interaction.user.mention, inline=True)
                embed.add_field(name="💬 Комментарий", value=comment, inline=False)

                if hasattr(self.report_message, '_view') and self.report_message._view:
                    view = self.report_message._view
                    if hasattr(view, 'thread') and view.thread:
                        try:
                            await view.thread.edit(archived=True, locked=True, reason=f"Репорт закрыт: {self.response_type}")
                        except discord.HTTPException:
                            pass

                await self.report_message.edit(embed=embed, view=None)
                await interaction.response.send_message("✅ Ответ добавлен к репорту.", ephemeral=True)

        # --- View для выбора типа ответа ---
        class AnswerTypeView(discord.ui.View):
            def __init__(self, report_message: discord.Message):
                super().__init__(timeout=120)
                self.report_message = report_message

            @discord.ui.button(label="Выполнено", style=discord.ButtonStyle.success, emoji="✅")
            async def done_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                modal = ReportCommentModal(self.report_message, "✅ Выполнено")
                await interaction.response.send_modal(modal)

            @discord.ui.button(label="Проигнорировано", style=discord.ButtonStyle.secondary, emoji="⏭️")
            async def ignore_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                modal = ReportCommentModal(self.report_message, "⏭️ Проигнорировано")
                await interaction.response.send_modal(modal)

            @discord.ui.button(label="Отменить", style=discord.ButtonStyle.danger, emoji="❌")
            async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                await interaction.response.edit_message(content="❌ Действие отменено.", view=None)

=======
>>>>>>> Stashed changes
        if report_message:
            view = ReportAnswerView.build(
                in_blacklist=(reporter.id in blacklist), 
                has_thread=(thread is not None)
            )
            await report_message.edit(view=view)

        return True


# ====== Context-menu (Message) ======
@app_commands.context_menu(name="Пожаловаться")
async def context_report(interaction: discord.Interaction, message: discord.Message):
    cog: Reports | None = interaction.client.get_cog("Reports")
    if cog is None:
        await interaction.response.send_message("Ошибка: Reports cog не загружен.", ephemeral=True)
        return

    await interaction.response.send_modal(ReportReasonModal(cog, message))


async def setup(bot: commands.Bot):
    reports_cog = Reports(bot)
    await bot.add_cog(reports_cog)

    try:
        bot.tree.add_command(context_report)
    except Exception:
        pass
