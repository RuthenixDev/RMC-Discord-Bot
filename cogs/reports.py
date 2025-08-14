import discord
from discord.ext import commands
from discord import app_commands
from utils import settings_cache as settings
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class Reports(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ====== Работа с настройками ======
    def update_report_channels(self, new_ids):
        data = settings.load_settings()

        data["report_channels"] = list(new_ids)
        settings.save_settings(data)

    # ====== Управление каналами для репортов ======
    @commands.command(help="Добавляет канал для репортов")
    @commands.has_permissions(manage_channels=True)
    async def addreport(self, ctx, channel: discord.TextChannel):
        data = settings.load_settings()

        report_channel_ids = set(data.get("report_channels", []))

        if channel.id in report_channel_ids:
            await ctx.send(f"⚠️ Канал {channel.mention} уже в списке репортов.")
            return

        report_channel_ids.add(channel.id)
        self.update_report_channels(report_channel_ids)
        await ctx.send(f"✅ Канал {channel.mention} добавлен для репортов.")

    @commands.command(help="Удаляет канал из репортов")
    @commands.has_permissions(manage_channels=True)
    async def removereport(self, ctx, channel: discord.TextChannel):
        data = settings.load_settings()

        report_channel_ids = set(data.get("report_channels", []))

        if channel.id not in report_channel_ids:
            await ctx.send(f"⚠️ Канал {channel.mention} не найден в репортах.")
            return

        report_channel_ids.remove(channel.id)
        self.update_report_channels(report_channel_ids)
        await ctx.send(f"❌ Канал {channel.mention} удалён из репортов.")

    @commands.command(help="Список каналов для репортов")
    async def listreports(self, ctx):
        data = settings.load_settings()

        report_channel_ids = set(data.get("report_channels", []))

        if not report_channel_ids:
            await ctx.send("📭 Список каналов для репортов пуст.")
            return

        embed = discord.Embed(title="🚨 Каналы для репортов", color=discord.Color.red())
        for cid in report_channel_ids:
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
        data = settings.load_settings()

        report_channel_ids = set(data.get("report_channels", []))
        admin_roles_ids = set(data.get("admin_roles", []))

        if not report_channel_ids:
            print("Не могу отправить репорт — нет настроенных каналов!")
            return

        admin_mentions = " ".join(
            role.mention
            for rid in admin_roles_ids
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

        for cid in report_channel_ids:
            if channel := guild.get_channel(cid):
                await channel.send(admin_mentions, embed=embed)


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
