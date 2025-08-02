import discord
from discord.ext import commands
from utils.settings import load_settings, save_settings

class StarChannels(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.settings = load_settings()
        self.star_channel_ids = set(self.settings.get("star_channels", []))

    def update_star_channels(self):
        self.settings["star_channels"] = list(self.star_channel_ids)
        save_settings(self.settings)

    @commands.command(help="Добавляет канал в ⭐-список")
    @commands.has_permissions(manage_channels=True)
    async def addstar(self, ctx, channel: discord.TextChannel):
        self.star_channel_ids.add(channel.id)
        self.update_star_channels()
        await ctx.send(f"✅ Добавлен канал: {channel.mention} для ⭐-списка")

    @commands.command(help="Удаляет канал из ⭐-списка")
    @commands.has_permissions(manage_channels=True)
    async def removestar(self, ctx, channel: discord.TextChannel):
        if channel.id in self.star_channel_ids:
            self.star_channel_ids.remove(channel.id)
            self.update_star_channels()
            await ctx.send(f"❌ Удалён канал: {channel.mention} из ⭐-списка")
        else:
            await ctx.send(f"⚠️ Канал {channel.mention} не в ⭐-списке")

    @commands.command(help="Выводит все каналы в ⭐-списке")
    async def liststars(self, ctx):
        if not self.star_channel_ids:
            await ctx.send("📭 Список каналов пуст.")
            return

        embed = discord.Embed(title="⭐ Каналы со звёздной реакцией", color=discord.Color.gold())
        for cid in self.star_channel_ids:
            channel = self.bot.get_channel(cid)
            if channel:
                embed.add_field(name=channel.name, value=channel.mention, inline=False)
            else:
                embed.add_field(name="❓ Неизвестный канал", value=f"ID: {cid}", inline=False)

        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(StarChannels(bot))
