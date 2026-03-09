import discord
import os
import time
import xml.etree.ElementTree as ET
from typing import Optional
from discord import app_commands
from discord.ext import commands
from wand.image import Image
from utils import settings_cache as settings
from constants import RMC_EMBED_COLOR

SVG_FILE = "map.svg" 
PNG_FILE = "map.png"

_country_cache = {"timestamp": 0, "data": []}

def get_country_names():
    """Возвращает список всех стран."""

    if not os.path.exists(SVG_FILE):
        return []
    
    tree = ET.parse(SVG_FILE)
    root = tree.getroot()
    countries = []


    for path in root.findall(".//{http://www.w3.org/2000/svg}path"):
        country_class = path.attrib.get("id")
        if country_class:
            countries.append(country_class.strip())
    return countries

def get_country_names_cached():
    if time.time() - _country_cache["timestamp"] > 10:
        _country_cache["data"] = list({c.strip() for c in get_country_names()})
        _country_cache["timestamp"] = time.time()
        return _country_cache["data"]  # ✅ возвращаем только список стран

#COUNTRIES = list({c.strip() for c in get_country_names()})

def update_svg(country_name: str, color: str):
    if not country_name:
        return False  # сразу выходим, если None

    tree = ET.parse(SVG_FILE)
    root = tree.getroot()
    found = False

    for path in root.findall(".//{http://www.w3.org/2000/svg}path"):
        country_class = path.attrib.get("id")
        if country_class and country_class.strip() == country_name:
            path.attrib["fill"] = color
            found = True

    if found:
        tree.write(SVG_FILE, encoding="utf-8", xml_declaration=True)
        return True
    return False




def svg_to_png(svg_path: str, png_path: str):
    """Конвертация SVG в PNG с использованием Wand."""
    try:
        from wand.image import Image
        with Image(filename=svg_path) as img:
            img.format = 'png'
            img.save(filename=png_path)
        return True
    except Exception as e:
        print(f"Ошибка конвертации SVG: {e}")
        return False

async def country_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    countries = get_country_names_cached()
    """Возвращает варианты стран на основе инпута пользователя."""
    return [
        app_commands.Choice(name=country, value=country)
        for country in countries
        if current.lower() in country.lower()
    ][:25]

class Map(commands.Cog):
    """Cog для просмотра карты."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        if not os.path.exists(SVG_FILE):
            root = ET.Element("{http://www.w3.org/2000/svg}svg")
            tree = ET.ElementTree(root)
            tree.write(SVG_FILE, encoding="utf-8", xml_declaration=True)
            print(f"Создан новый файл {SVG_FILE}")
            
    @app_commands.command(
        name="map",
        description="Посмотреть карту сервера."
    )
    @app_commands.describe(
        map_type="Выберите действие с картой.",
        country_name="Название страны (только для add/remove)"
    )
    @app_commands.choices(map_type=[
        app_commands.Choice(name="Посмотреть текущую карту", value="show"),
        app_commands.Choice(name="Добавить страну", value="add"),
        app_commands.Choice(name="Убрать страну", value="remove")
    ])
    @app_commands.autocomplete(country_name=country_autocomplete)
    async def map(
        self, 
        interaction: discord.Interaction, 
        map_type: str = None, 
        country_name: Optional[str] = None
    ):
        """Посмотреть карту сервера"""
        data = settings.load_settings()
        admin_roles = data.get("admin_roles", [])
        user_roles = [role.id for role in interaction.user.roles]
        is_admin = any(role_id in user_roles for role_id in admin_roles)
        if map_type == "show":
            try:
                if svg_to_png(SVG_FILE, PNG_FILE):
                    file = discord.File(PNG_FILE, filename="map.png")
                    embed = discord.Embed(
                        title="🗺 Текущая карта",
                        color=RMC_EMBED_COLOR,
                        timestamp=discord.utils.utcnow()
                    )
                    embed.set_image(url="attachment://map.png")
                    embed.set_footer(text="Карта стран участников РМК.")
                    await interaction.response.send_message(embed=embed, file=file)
            except Exception as e:
                error_embed = discord.Embed(
                    name="❌ Ошибка при загрузке карты", 
                    description=f"При загрузке карты возникла ошибка: ```{e}```."
                )
                await interaction.response.send_message(embed=error_embed, ephemeral=True)
        elif is_admin:
            if map_type == "add" and country_name and is_admin:
                if update_svg(country_name, "#FF0000"): 
                    svg_to_png(SVG_FILE, PNG_FILE)
                    file = discord.File(PNG_FILE, filename="map.png")
                    embed = discord.Embed(
                        title="🗺 Обновлённая версия карты",
                        color=RMC_EMBED_COLOR,
                        timestamp=discord.utils.utcnow()
                    )
                    embed.set_image(url="attachment://map.png")
                    embed.set_footer(text="Ознакомиться с текущей версией карты можно по команде !rmc map show")
                    await interaction.response.send_message(
                        content=f"✅ `{country_name}` добавлена на карту.",
                        embed=embed,
                        file=file   # вот это добавь
                    )
                    print(f"На карту добавлена страна {country_name} пользователем {interaction.user.name}.")
                else: 
                    error_embed = discord.Embed(
                        name="❌ Ошибка при изменении карты", 
                        description=f"Страна `{country_name}` не найдена в SVG-файле."
                    )
                    await interaction.response.send_message(embed=error_embed, ephemeral=True)
            elif map_type == "remove" and country_name:
                if update_svg(country_name, "#d1dbdd"):
                    svg_to_png(SVG_FILE, PNG_FILE)
                    file = discord.File(PNG_FILE, filename="map.png")
                    embed = discord.Embed(
                        title="🗺 Обновлённая версия карты",
                        color=RMC_EMBED_COLOR,
                        timestamp=discord.utils.utcnow()
                    )
                    embed.set_footer(text="Ознакомиться с текущей версией карты можно по команде !rmc map show")
                    embed.set_image(url="attachment://map.png")
                    await interaction.response.send_message(
                        content=f"✅ `{country_name}` убрана с карты.",
                        embed=embed,
                        file=file   # вот это добавь
                    )
                    print(f"С карты удалена страна {country_name} пользователем {interaction.user.name}.")
                else:
                    error_embed = discord.Embed(
                        name="❌ Ошибка при изменении карты", 
                        description=f"Страна `{country_name}` не найдена в SVG-файле."
                    )
                    await interaction.response.send_message(embed=error_embed, ephemeral=True)
            else:
                error_embed = discord.Embed(
                    name="❌ Ошибка при использовании команды", 
                    description=f"Проверьте правильность аргументов и попробуйте снова."
                )
                await interaction.response.send_message(embed=error_embed, ephemeral=True)
                #await interaction.response.send_message("⚠ Неверное использование команды. Проверь аргументы.")
        else:
            error_embed = discord.Embed(
                name="❌ Ошибка при использовании команды", 
                description=f"У вас нет прав для изменения карты."
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Map(bot))