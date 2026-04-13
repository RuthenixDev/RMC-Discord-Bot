import discord
import os
import json
import aiofiles
import time
from datetime import datetime
from typing import Optional
from discord import app_commands
from discord.ui import View, Button
from discord.ext import commands
from constants import RMC_EMBED_COLOR
from utils.permissions import check_cog_access
from utils import settings_cache as settings
from utils.exceptions import NoLogChannelError

class RulesAdminView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="Добавить", style=discord.ButtonStyle.success, emoji="➕")
    async def add_rule_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = AddRuleModal(self.cog)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Изменить", style=discord.ButtonStyle.primary, emoji="✏️")
    async def edit_rule_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = EditRuleModal(self.cog)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Удалить", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def delete_rule_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = DeleteRuleModal(self.cog)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Системные", style=discord.ButtonStyle.secondary, emoji="⚙️")
    async def system_items_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = discord.ui.View()
        select = discord.ui.Select(placeholder="Выберите системный раздел для правки...")
        
        select.add_option(label="Основа", value="basis", emoji="📜")
        select.add_option(label="Система наказаний", value="punishment_system", emoji="⚖️")
        select.add_option(label="Ссылка на правила", value="link", emoji="🔗")

        async def select_callback(select_interaction: discord.Interaction):
            modal = EditSystemItemModal(self.cog, select.values[0])
            await select_interaction.response.send_modal(modal)

        select.callback = select_callback
        view.add_item(select)
        
        await interaction.response.send_message("Какой раздел вы хотите отредактировать?", view=view, ephemeral=True)
    
class EditSystemItemModal(discord.ui.Modal):
    def __init__(self, cog, sys_id: str):
        titles = {
            "basis": "Редактирование: Основа",
            "punishment_system": "Редактирование: Наказания",
            "link": "Редактирование: Ссылка"
        }
        super().__init__(title=titles.get(sys_id, "Системный раздел"))
        self.cog = cog
        self.sys_id = sys_id
        self.title_input = discord.ui.TextInput(
            label="Заголовок раздела",
            placeholder="Например: Основа / Правила сервера",
            max_length=100,
            required=False 
        )
        self.text_input = discord.ui.TextInput(
            label="Содержание",
            style=discord.TextStyle.paragraph,
            placeholder="Введите текст раздела...",
            max_length=2000,
            required=False
        )
        
        self.add_item(self.title_input)
        self.add_item(self.text_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            data = await self.cog._load_rules_data()
            if "system_items" not in data:
                data["system_items"] = {}
            
            current = data["system_items"].get(self.sys_id, {"title": "", "text": ""})

            new_title = self.title_input.value.strip() or current['title']
            new_text = self.text_input.value.strip() or current['text']

            data["system_items"][self.sys_id] = {
                "title": new_title,
                "text": new_text
            }

            await self.cog._log_rule_change(
                interaction, 
                f"Системный раздел ({self.sys_id})", 
                0, 
                new_title, 
                new_text
            )

            await self.cog._save_rules_data(data)

            await interaction.response.send_message(f"✅ Раздел «{new_title}» успешно обновлен!", ephemeral=True)

        except NoLogChannelError:
            await interaction.response.send_message("❌ Ошибка: Не настроены логи.", ephemeral=True)

class AddRuleModal(discord.ui.Modal, title="➕Добавление правила"):
    number = discord.ui.TextInput(
        label="Номер правила",
        placeholder="Например: 17 (действует автосдвиг)",
        min_length=1,
        max_length=2
    )
    rule_title = discord.ui.TextInput(
        label="Заголовок правила",
        placeholder="Введите краткое название...",
        max_length=100
    )
    rule_text = discord.ui.TextInput(
        label="Текст правила",
        placeholder="Введите полный текст правила...",
        style=discord.TextStyle.paragraph,
        max_length=2000
    )

    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        try:
            if not self.number.value.isdigit():
                await interaction.response.send_message("❌Номер правила должен быть числом!", ephemeral=True)
                return
            
            target_pos = int(self.number.value)
            data = await self.cog._load_rules_data()
            rules = data.get("rules", [])

            new_rule = {
                "title": self.rule_title.value,
                "text": self.rule_text.value
            }

            idx = max(0, min(target_pos - 1, len(rules)))
            rules.insert(idx, new_rule)

            data["rules"] = rules

            await self.cog._log_rule_change(
                interaction,
                "Добавление",
                target_pos,
                self.rule_title.value,
                self.rule_text.value
            )

            await self.cog._save_rules_data(data)

            response_embed = discord.Embed(
                title=f"✅ Правило №{target_pos} добавлено успешно!",
                description=f"**{self.rule_title.value}**\n\n{self.rule_text.value}",
                color=RMC_EMBED_COLOR
            )

            await interaction.response.send_message(embed=response_embed, ephemeral=True)

        except NoLogChannelError:
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Ошибка: Не настроен канал логов. Изменения не сохранены.", ephemeral=True)
            else:
                await interaction.followup.send("❌ Ошибка: Не настроен канал логов. Изменения не сохранены.", ephemeral=True)
        except Exception as e:
            print(f"Ошибка в AddRuleModal: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message(f"❌ Произошла ошибка: {e}", ephemeral=True)

class EditRuleModal(discord.ui.Modal, title="✏️Изменение правила"):
    number = discord.ui.TextInput(
        label="Номер правила",
        placeholder="Например: 17 (действует автосдвиг)",
        min_length=1,
        max_length=2
    )
    rule_title = discord.ui.TextInput(
        label="Новый заголовок",
        placeholder="Введите новое краткое название...",
        max_length=100,
        required=False
    )
    rule_text = discord.ui.TextInput(
        label="Новый текст правила",
        placeholder="Введите новый полный текст правила...",
        style=discord.TextStyle.paragraph,
        max_length=2000,
        required=False
    )

    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        try:
            val = self.number.value.strip()
            if not val.isdigit():
                await interaction.response.send_message("❌Номер правила должен быть числом!", ephemeral=True)
                return
            
            target_pos = int(val)
            idx = target_pos - 1

            data = await self.cog._load_rules_data()
            rules = data.get("rules", [])

            if idx < 0 or idx >= len(rules):
                await interaction.response.send_message(f"❌ Правила под номером {target_pos} не существует!", ephemeral=True)
                return
            
            current_rule = rules[idx]
            new_title = self.rule_title.value.strip() or current_rule['title']
            new_text = self.rule_text.value.strip() or current_rule['text']
            
            await self.cog._log_rule_change(
                interaction,
                "Редактирование",
                target_pos,
                self.rule_title.value,
                self.rule_text.value
            )

            rules[idx] = {
                "title": new_title,
                "text": new_text
            }

            data["rules"] = rules

            await self.cog._save_rules_data(data)

            response_embed = discord.Embed(
                title=f"✅ Правило №{target_pos} успешно изменено!",
                description=f"**{new_title}**\n\n{new_text}",
                color=discord.Color.blue()
            )

            await interaction.response.send_message(embed=response_embed, ephemeral=True)
            
        except NoLogChannelError:
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Ошибка: Не настроен канал логов. Изменения не сохранены.", ephemeral=True)
            else:
                await interaction.followup.send("❌ Ошибка: Не настроен канал логов. Изменения не сохранены.", ephemeral=True)
        except Exception as e:
            print(f"Ошибка в EditRuleModal: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message(f"❌ Произошла ошибка: {e}", ephemeral=True)

class DeleteRuleModal(discord.ui.Modal, title="🗑️Удаление правила"):
    number = discord.ui.TextInput(
        label="Номер правила",
        placeholder="Введите номер правила для удаления...",
        min_length=1,
        max_length=2
    )

    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction:discord.Interaction):
        try:
            val = self.number.value.strip()
            if not val.isdigit():
                await interaction.response.send_message("❌ Введите число!", ephemeral=True)
                return
            
            target_pos = int(val)
            idx = target_pos - 1
            
            data = await self.cog._load_rules_data()
            rules = data.get("rules", [])

            if idx < 0 or idx >= len(rules):
                await interaction.response.send_message(f"❌ Правило №{target_pos} не найдено!", ephemeral=True)
                return

            deleted_rule = rules[idx]

            await self.cog._log_rule_change(
                interaction, 
                "Удаление", 
                target_pos, 
                deleted_rule['title']
            )

            rules.pop(idx)
            data["rules"] = rules

            await self.cog._save_rules_data(data)
            await interaction.response.send_message(f"🗑️ Правило №{target_pos} успешно удалено!", ephemeral=True)

        except NoLogChannelError:
            await interaction.response.send_message("❌ Ошибка: Логи не настроены.", ephemeral=True)


class Rules(commands.Cog):
    required_access = None

    async def cog_check(self, ctx: commands.Context):
        allowed = await check_cog_access(ctx, self.required_access)
        if not allowed:
            raise commands.CheckFailure()
        return True

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def check_admin(self, interaction: discord.Interaction) -> bool:
        settings_data = settings.load_settings()
        admin_roles = settings_data.get('admin_roles', [])
        user_roles = [role.id for role in interaction.user.roles]
        return any(role_id in admin_roles for role_id in user_roles)

    async def _load_rules_data(self):
        if not os.path.exists("rules.json"):
            return {"edit_date": None, "rules": [], "system_items": {}}
        try:
            async with aiofiles.open("rules.json", mode='r', encoding='utf-8') as f: 
                content = await f.read()
                if content:
                    data = json.loads(content)
                    if "system_items" not in data:
                        data["system_items"] = {}
                    if "rules" not in data:
                        data["rules"] = []
                    return data
                return {"edit_date": None, "rules": [], "system_items": {}}
        except (json.JSONDecodeError, Exception) as e:
            print(f"Ошибка при загрузке правил: {e}")
            return {"edit_date": None, "rules": [], "system_items": {}}
        
    async def _save_rules_data(self, data: dict):
        data["edit_date"] = time.time()
        async with aiofiles.open("rules.json", mode='w', encoding='utf-8') as f:
            await f.write(json.dumps(data, indent=4, ensure_ascii=False))

    async def _log_rule_change(self, interaction: discord.Interaction, action: str, rule_id: int, title: str, text: Optional[str] = None): 
        settings_data = settings.load_settings()
        log_channel_id = settings_data.get("log_channel")
        if not log_channel_id:
            raise NoLogChannelError()
        log_channel = interaction.guild.get_channel(log_channel_id) if log_channel_id else None 
        if not log_channel:
            raise NoLogChannelError()
        log_rule_embed = discord.Embed(
            title=f"📝 Изменение правил: {action}",
            color=RMC_EMBED_COLOR,
            timestamp=discord.utils.utcnow()
        )
        log_rule_embed.add_field(name="Модератор", value=f"{interaction.user.mention}  `{interaction.user.id}`", inline=True)
        log_rule_embed.add_field(name="ID правила", value=f"#{rule_id}", inline=True)
        log_rule_embed.add_field(name="Заголовок", value=title, inline=False)

        if text:
            display_text = text if len(text) <= 1024 else text[:1021] + "..."
            log_rule_embed.add_field(name="Текст правила", value=display_text, inline=False)

        await log_channel.send(embed=log_rule_embed)

    @app_commands.command(
        name="rule_edit",
        description="Управление правилами сервера."
    )
    @app_commands.guild_only()
    async def rule_edit(self, interaction: discord.Interaction):
        if not await self.check_admin(interaction):
            await interaction.response.send_message("❌ Недостаточно прав", ephemeral=True)
            return
        
        data = await self._load_rules_data()
        rules = data.get("rules", [])
        edit_date = data.get("edit_date")

        time_str = f"<t:{int(edit_date)}:R>" if edit_date else "Никогда"

        description = ""
        for i, rule in enumerate(rules, 1):
            description += f"**{i}.** {rule['title']}\n"

        if not description: 
            description = "Правила ещё не созданы"

        embed = discord.Embed(
            title="🛠️ Настройка правил сервера",
            description=description,
            timestamp=discord.utils.utcnow(),
            color=RMC_EMBED_COLOR
        )
        embed.set_footer(text=f"Последнее изменение: {time_str}")

        await interaction.response.send_message(
            embed=embed,
            view=RulesAdminView(self),
            ephemeral=True
        )

    @app_commands.command(name="rule", description="Показать пункт правил")
    @app_commands.describe(item="Выберите пункт правил")
    #@app_commands.autocomplete(item=rule_autocomplete)
    async def rule(self, interaction: discord.Interaction, item: str):
        data = await self._load_rules_data()
        
        if item.startswith("sys_"):
            sys_id = item.replace("sys_", "")
            content = data.get("system_items", {}).get(sys_id)
            
            if sys_id == "basis":
                title = f"📜 {content['title']}"
                footer = "Администрация оставляет за собой право трактовать правила"
            elif sys_id == "punishment_system":
                title = f"⚖️ {content['title']}"
                footer = "Администрация оставляет за собой право не следовать установленной системе"
            else:
                title = f"🔗 {content['title']}"
                footer = "Полная версия правил доступна по ссылке"
        else:
            rules = data.get("rules", [])
            idx = int(item) - 1
            content = rules[idx] if 0 <= idx < len(rules) else None
            title = f"📍 Правило №{item}: {content['title']}"
            footer = "Соблюдайте правила сервера!"

        if not content:
            await interaction.response.send_message("❌ Пункт не найден", ephemeral=True)
            return

        embed = discord.Embed(
            title=title,
            description=content['text'],
            color=RMC_EMBED_COLOR,
            timestamp=discord.utils.utcnow()
        )
        embed.set_footer(text=footer)
        await interaction.response.send_message(embed=embed)

    @rule.autocomplete("item")
    async def rule_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        data = await self._load_rules_data()
        choices = []
        
        sys_items = data.get("system_items", {})
        for sys_id, item in sys_items.items():
            label = f"⚙️ {item['title']}"
            if current.lower() in label.lower():
                choices.append(app_commands.Choice(name=label, value=f"sys_{sys_id}"))

        rules = data.get("rules", [])
        for i, rule in enumerate(rules, 1):
            label = f"{i}. {rule['title']}"
            if current.lower() in label.lower():
                choices.append(app_commands.Choice(name=label, value=str(i)))
                
        return choices[:25]

async def setup(bot: commands.Bot):
    await bot.add_cog(Rules(bot))