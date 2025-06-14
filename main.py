import discord
from discord.ext import commands
from dotenv import load_dotenv
import os

load_dotenv(os.getenv("TOKEN"))
TOKEN = ""

bot = commands.Bot(command_prefix="!rmc", intents=discord.Intents.all())

@bot.event
async def on_ready():
    print(f"Бот {bot.user} запущен!")

@bot.command()
async def ping(ctx):
    await ctx.send("Привет!")

bot.run(TOKEN)
