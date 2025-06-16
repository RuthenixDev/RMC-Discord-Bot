import discord
from discord.ext import commands
from dotenv import load_dotenv
import os
import json
import time

load_dotenv()
TOKEN = os.getenv("TOKEN")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!rmc ", intents=intents)

SETTINGS_FILE = "settings.json"
RMC_EMBED_COLOR = 0x00ccff
COOLDOWN = 600

# ===================== Работа с settings.json =====================
def load_settings():
    if not os.path.exists(SETTINGS_FILE):
        return {"star_channels": []}
    with open(SETTINGS_FILE, "r") as f:
        return json.load(f)

def save_settings(data):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(data, f, indent=4)

##############################
settings = load_settings()
star_channel_ids = set(settings.get("star_channels", []))
admin_roles_ids = set(settings.get("admin_roles", []))
filter_channel_ids = set(settings.get("filter_channels", []))
filter_timeouts = settings.get("filter_timeout", {})
##############################

def update_star_channels():
    settings["star_channels"] = list(star_channel_ids)
    save_settings(settings)

def update_admin_roles():
    settings["admin_roles"] = list(admin_roles_ids)
    save_settings(settings)

def update_filter_channels():
    settings["filter_channels"] = list(filter_channel_ids)
    save_settings(settings)

def update_filter_timeouts():
    settings["filter_timeout"] = filter_timeouts
    save_settings(settings)

# ===================== Событие запуска =====================
@bot.event
async def on_ready():
    print(f"Бот {bot.user} запущен!")

# ===================== Ивенты =====================
async def handle_filter_violation(message):
    user_id_str = str(message.author.id)
    now = int(time.time())
    filter_timeouts = settings.setdefault("filter_timeout", {})
    last_violation = filter_timeouts.get(user_id_str, 0)

    has_attachments = bool(message.attachments)
    has_links = ("http://" in message.content) or ("https://" in message.content)

    if not has_attachments and not has_links:
        try:
            await message.delete()
            print(f"Удалено сообщение от {message.author} в {message.channel.name} без вложений и ссылок")

            if now - last_violation >= COOLDOWN:
                filter_timeouts[user_id_str] = now
                update_filter_timeouts()

                embed = discord.Embed(
                    title="📵 Только медиа-сообщения!",
                    description="Этот канал предназначен **только для изображений, видео или ссылок**.\n\n"
                                "Пожалуйста, не отправляй обычные текстовые сообщения без вложений.",
                    color=RMC_EMBED_COLOR
                )
                try:
                    await message.author.send(embed=embed)
                except discord.Forbidden:
                    print(f"Не удалось отправить ЛС пользователю {message.author}")
        except discord.Forbidden:
            print(f"Нет прав удалять сообщения в {message.channel.name}")
        except discord.HTTPException as e:
            print(f"Ошибка при удалении сообщения: {e}")



@bot.event
async def on_message(message):
    if message.author.bot:
        return

    ### Добавление реакции в star-канале ###
    if message.channel.id in star_channel_ids:
        try:
            await message.add_reaction("⭐")
        except discord.Forbidden:
            print("Нет прав для добавления реакции")
        except discord.HTTPException as e:
            print(f"Ошибка при добавлении реакции: {e}")

    ### Создание ветки ###
        first_line = message.content.split('\n')[0]
        thread_name = first_line[:100] if first_line else f"Обсуждение {message.author.display_name}"    

        try:
            thread = await message.create_thread(
                name=thread_name,
                auto_archive_duration=1440
            )
            await thread.send(
                f"**Обсуждение работы пользователя {message.author.display_name}**\n\n"
                "Если вам понравилась работа, не забудьте поставить реакцию ⭐ чтобы поддержать автора!"
            )
        except discord.Forbidden:
            print(f"Нет прав для создания ветки в канале {message.channel.name}")
        except discord.HTTPException as e:
            print(f"Ошибка при создании ветки: {e}")


    if message.channel.id in filter_channel_ids:
        if any(role.id in admin_roles_ids for role in message.author.roles):
            await bot.process_commands(message)
            return

        has_attachments = bool(message.attachments)
        has_links = ("http://" in message.content) or ("https://" in message.content)

        if not has_attachments and not has_links:
            await handle_filter_violation(message)
            return

    await bot.process_commands(message)




# ===================== Команды управления =====================

@bot.command(help="Добавляет канал в ⭐-список")
@commands.has_permissions(manage_channels=True)
async def addstar(ctx, channel: discord.TextChannel): # Добавляем канал в список звёздочек
    star_channel_ids.add(channel.id)
    update_star_channels()
    await ctx.send(f"✅ Добавлен канал: {channel.mention} для ⭐-списка")

@bot.command(help="Удаляет канал из ⭐-списка")
@commands.has_permissions(manage_channels=True)
async def removestar(ctx, channel: discord.TextChannel): # Удаляем канал из списка звёздочек
    if channel.id in star_channel_ids:
        star_channel_ids.remove(channel.id)
        update_star_channels()
        await ctx.send(f"❌ Удалён канал: {channel.mention} из ⭐-списка")
    else:
        await ctx.send(f"⚠️ Канал {channel.mention} не в ⭐-списке")

@bot.command(help="Выводит все каналы в ⭐-списке")
async def liststars(ctx): # Выводим каналы со звёдочками
    if not star_channel_ids:
        await ctx.send("📭 Список каналов пуст.")
        return

    embed = discord.Embed(title="⭐ Каналы со звёздной реакцией", color=discord.Color.gold())
    for cid in star_channel_ids:
        channel = bot.get_channel(cid)
        if channel:
            embed.add_field(name=channel.name, value=channel.mention, inline=False)
        else:
            embed.add_field(name="❓ Неизвестный канал", value=f"ID: {cid}", inline=False)

    await ctx.send(embed=embed)


@bot.command(help="Добавляет роль в список административных")
@commands.has_permissions(administrator=True)
async def addadmin(ctx, role: discord.Role):
    admin_roles = settings.get("admin_roles", [])
    if role.id in admin_roles:
        await ctx.send(f"⚠️ Роль {role.name} уже находится в списке.")
        return

    admin_roles.append(role.id)
    settings["admin_roles"] = admin_roles
    save_settings(settings)

    admin_roles_ids.add(role.id)

    await ctx.send(f"✅ Роль {role.name} добавлена в список административных.")

@bot.command(help="Выводит все административные роли")
async def listadmins(ctx):
    if not admin_roles_ids:
        await ctx.send("📭 Список административных ролей пуст.")
        return

    embed = discord.Embed(title="💎 Административные роли", color=RMC_EMBED_COLOR)
    for rid in admin_roles_ids:
        role = ctx.guild.get_role(rid)
        if role:
            embed.add_field(name=role.name, value=role.mention, inline=False)
        else:
            embed.add_field(name="❓Неизвестная роль", value=f"ID: {rid}", inline=False)

    await ctx.send(embed=embed)

@bot.command(help="Удаляет роль из списка административных")
@commands.has_permissions(administrator=True)
async def removeadmin(ctx, role: discord.Role):
    admin_roles = settings.get("admin_roles", [])
    if role.id not in admin_roles:
        await ctx.send(f"⚠️ Роль {role.name} не найдена в списке административных.")
        return

    admin_roles.remove(role.id)
    settings["admin_roles"] = admin_roles
    save_settings(settings)

    admin_roles_ids.discard(role.id)

    await ctx.send(f"✅ Роль {role.name} удалена из списка административных.")


@bot.command(help="Добавляет канал в список фильтруемых (только медиа)")
@commands.has_permissions(manage_channels=True)
async def addfilter(ctx, channel: discord.TextChannel):
    if channel.id in filter_channel_ids:
        await ctx.send(f"⚠️ Канал {channel.mention} уже находится в списке.")
        return

    filter_channel_ids.add(channel.id)
    update_filter_channels()
    await ctx.send(f"✅ Канал {channel.mention} добавлен в список фильтруемых.")

@bot.command(help="Удаляет канал из списка фильтруемых")
@commands.has_permissions(manage_channels=True)
async def removefilter(ctx, channel: discord.TextChannel):
    if channel.id not in filter_channel_ids:
        await ctx.send(f"⚠️ Канал {channel.mention} не найден в списке.")
        return

    filter_channel_ids.remove(channel.id)
    update_filter_channels()
    await ctx.send(f"✅ Канал {channel.mention} удалён из списка фильтруемых.")

@bot.command(help="Показывает список фильтруемых каналов")
async def listfilters(ctx):
    if not filter_channel_ids:
        await ctx.send("📭 Список фильтруемых каналов пуст.")
        return

    embed = discord.Embed(title="📵 Фильтруемые каналы (только медиа)", color=RMC_EMBED_COLOR)
    for cid in filter_channel_ids:
        channel = bot.get_channel(cid)
        if channel:
            embed.add_field(name=channel.name, value=channel.mention, inline=False)
        else:
            embed.add_field(name="❓ Неизвестный канал", value=f"ID: {cid}", inline=False)

    await ctx.send(embed=embed)




bot.remove_command("help")
@bot.command(help="Выводит все доступные команды")
async def help(ctx):
    embed = discord.Embed(
        title="🛠️ Список доступных команд",
        color=RMC_EMBED_COLOR
    )

    for command in bot.commands:
        if command.hidden:
            continue

        embed.add_field(
            name= f"!rmc {command.name}",
            value=command.help or "",
            inline=False
        )

    await ctx.send(embed=embed)

bot.run(TOKEN)
