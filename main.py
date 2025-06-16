import discord
from discord.ext import commands
from dotenv import load_dotenv
import os
import json

load_dotenv()
TOKEN = os.getenv("TOKEN")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!rmc ", intents=intents)

SETTINGS_FILE = "settings.json"

RMC_EMBED_COLOR = 0x00ccff

# ===================== Работа с settings.json =====================
def load_settings():
    if not os.path.exists(SETTINGS_FILE):
        return {"star_channels": []}
    with open(SETTINGS_FILE, "r") as f:
        return json.load(f)

def save_settings(data):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(data, f, indent=4)

settings = load_settings()
star_channel_ids = set(settings.get("star_channels", []))

def update_star_channels():
    settings["star_channels"] = list(star_channel_ids)
    save_settings(settings)

# ===================== Событие запуска =====================
@bot.event
async def on_ready():
    print(f"Бот {bot.user} запущен!")

# ===================== Автоматическая реакция =====================
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # Добавление реакции в star-канале
    if message.channel.id in star_channel_ids:
        try:
            await message.add_reaction("⭐")
        except discord.Forbidden:
            print("Нет прав для добавления реакции")
        except discord.HTTPException as e:
            print(f"Ошибка при добавлении реакции: {e}")

        # Создание ветки
        first_line = message.content.split('\n')[0]
        thread_name = first_line[:100] if first_line else f"Обсуждение {message.author.display_name}"    

        try:
            thread = await message.create_thread(
                name=thread_name,
                auto_archive_duration=1440  # 1 день
            )
            await thread.send(
                f"**Обсуждение работы пользователя {message.author.display_name}**\n\n"
                "Если вам понравилась работа, не забудьте поставить реакцию ⭐ чтобы поддержать автора!"
            )
        except discord.Forbidden:
            print(f"Нет прав для создания ветки в канале {message.channel.name}")
        except discord.HTTPException as e:
            print(f"Ошибка при создании ветки: {e}")

    # Обработка команд (если используешь @bot.command)
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
