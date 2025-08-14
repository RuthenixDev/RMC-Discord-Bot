import discord
from discord.ext import commands


class HelpCmd(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(help="Показывает список команд")
    async def help(self, ctx):
        embed = discord.Embed(title="🛠️ Список доступных команд", color=0x00ccff)
        for command in self.bot.commands:
            if command.hidden:
                continue
            embed.add_field(name=f"!rmc {command.name}", value=command.help or "", inline=False)
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(HelpCmd(bot))
