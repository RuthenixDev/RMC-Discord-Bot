import discord
from discord.ext import commands
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TOKEN")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!rmc ", intents=intents, help_command=None)


@bot.event
async def on_ready():
    print(f"Бот {bot.user} запущен!")
    await bot.tree.sync()
    print("Slash-команды синхронизированы.")


async def main():
    async with bot:

        import logging
        logging.basicConfig(level=logging.DEBUG)


        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                try:
                    await bot.load_extension(f'cogs.{filename[:-3]}')
                    print(f"✅ Ког {filename} загружен")
                except Exception as e:
                    print(f"❌ Ошибка при загрузке {filename}: {e}")
        await bot.start(TOKEN)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
