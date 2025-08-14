import discord
from discord.ext import commands
from discord import app_commands
from utils.settings import load_settings, save_settings


class Reports(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.settings = load_settings()
        self.report_channel_ids = set(self.settings.get("report_channels", []))
        self.admin_roles_ids = set(self.settings.get("admin_roles", []))

    # ====== Работа с settings.json ======
    def update_report_channels(self):
        self.settings["report_channels"] = list(self.report_channel_ids)
        save_settings(self.settings)

    # ====== Управление каналами для репортов ======
    @commands.command(help="Добавляет канал для репортов")
    @commands.has_permissions(manage_channels=True)
    async def addreport(self, ctx, channel: discord.TextChannel):
        if channel.id in self.report_channel_ids:
            await ctx.send(f"⚠️ Канал {channel.mention} уже в списке репортов.")
            return
        self.report_channel_ids.add(channel.id)
        self.update_report_channels()
        await ctx.send(f"✅ Канал {channel.mention} добавлен для репортов.")

    @commands.command(help="Удаляет канал из репортов")
    @commands.has_permissions(manage_channels=True)
    async def removereport(self, ctx, channel: discord.TextChannel):
        if channel.id not in self.report_channel_ids:
            await ctx.send(f"⚠️ Канал {channel.mention} не найден в репортах.")
            return
        self.report_channel_ids.remove(channel.id)
        self.update_report_channels()
        await ctx.send(f"❌ Канал {channel.mention} удалён из репортов.")

    @commands.command(help="Список каналов для репортов")
    async def listreports(self, ctx):
        if not self.report_channel_ids:
            await ctx.send("📭 Список каналов для репортов пуст.")
            return
        embed = discord.Embed(title="🚨 Каналы для репортов", color=discord.Color.red())
        for cid in self.report_channel_ids:
            channel = self.bot.get_channel(cid)
            if channel:
                embed.add_field(name=channel.name, value=channel.mention, inline=False)
            else:
                embed.add_field(name="❓ Неизвестный канал", value=f"ID: {cid}", inline=False)
        await ctx.send(embed=embed)

    # ====== Внутренний метод для отправки репорта ======
    async def send_report(self, guild: discord.Guild, reporter: discord.Member,
                          target_message: discord.Message, reason: str):
        """Отправка embed-а с жалобой в репорт-каналы"""
        if not self.report_channel_ids:
            return

        # Пингуем админские роли
        admin_mentions = " ".join(
            role.mention
            for rid in self.admin_roles_ids
            if (role := guild.get_role(rid))
        ) or "⚠️ (Нет настроенных админ-ролей)"

        embed = discord.Embed(
            title="🚨 Новый репорт",
            color=discord.Color.red()
        )
        embed.add_field(name="Отправитель жалобы", value=reporter.mention, inline=False)
        embed.add_field(name="Причина", value=reason or "—", inline=False)
        embed.add_field(name="Сообщение", value=f"[Перейти к сообщению]({target_message.jump_url})", inline=False)
        embed.set_footer(text=f"Автор сообщения: {target_message.author} ({target_message.author.id})")

        # Отправляем в каждый канал
        for cid in self.report_channel_ids:
            if channel := guild.get_channel(cid):
                await channel.send(admin_mentions, embed=embed)

    # ====== Slash-команда ======
    @app_commands.command(name="report", description="Пожаловаться на сообщение (используйте в ответ на сообщение)")
    @app_commands.describe(reason="Причина жалобы")
    async def report(self, interaction: discord.Interaction, reason: str):
        # Проверяем, что команда вызвана в гильдии
        if not interaction.guild or not interaction.channel:
            await interaction.response.send_message("❌ Эта команда доступна только на сервере.", ephemeral=True)
            return

        # Проверяем, что сообщение — ответ
        ref = getattr(interaction, "message", None)
        target_message = None

        # В slash-команде interaction.message чаще всего None, поэтому ищем reply вручную
        try:
            async for msg in interaction.channel.history(limit=10):
                if msg.reference and msg.reference.message_id:
                    if msg.author.id == interaction.user.id:
                        target_message = await interaction.channel.fetch_message(msg.reference.message_id)
                        break
        except:
            pass

        if not target_message:
            await interaction.response.send_message(
                "⚠️ Используйте команду в **ответ на сообщение**, на которое хотите пожаловаться.",
                ephemeral=True
            )
            return

        # Отправляем репорт
        await self.send_report(interaction.guild, interaction.user, target_message, reason)
        await interaction.response.send_message("✅ Репорт отправлен администрации.", ephemeral=True)

    # ====== Контекстное меню ======
    @app_commands.context_menu(name="Пожаловаться")
    async def context_report(self, interaction: discord.Interaction, message: discord.Message):
        await interaction.response.send_modal(ReportReasonModal(self, message))


# ====== Модальное окно для указания причины ======
class ReportReasonModal(discord.ui.Modal, title="Отправка жалобы"):
    def __init__(self, cog: Reports, target_message: discord.Message):
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
        await self.cog.send_report(
            interaction.guild, interaction.user, self.target_message, str(self.reason)
        )
        await interaction.response.send_message("✅ Репорт отправлен администрации.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Reports(bot))
