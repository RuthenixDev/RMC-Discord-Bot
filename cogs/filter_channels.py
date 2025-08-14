import discord
from discord.ext import commands
from utils.settings import load_settings, save_settings

class FilterChannels(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.settings = load_settings()
        self.filter_channel_ids = set(self.settings.get("filter_channels", []))

    def update_filter_channels(self):
        self.settings["filter_channels"] = list(self.filter_channel_ids)
        save_settings(self.settings)

    @commands.command(help="Добавляет канал в список фильтруемых (только медиа)")
    @commands.has_permissions(manage_channels=True)
    async def addfilter(self, ctx, channel: discord.TextChannel):
        if channel.id in self.filter_channel_ids:
            await ctx.send(f"⚠️ Канал {channel.mention} уже в списке.")
            return
        self.filter_channel_ids.add(channel.id)
        self.update_filter_channels()
        await ctx.send(f"✅ Канал {channel.mention} добавлен в список фильтруемых.")

    @commands.command(help="Удаляет канал из списка фильтруемых")
    @commands.has_permissions(manage_channels=True)
    async def removefilter(self, ctx, channel: discord.TextChannel):
        if channel.id not in self.filter_channel_ids:
            await ctx.send(f"⚠️ Канал {channel.mention} не найден.")
            return
        self.filter_channel_ids.remove(channel.id)
        self.update_filter_channels()
        await ctx.send(f"✅ Канал {channel.mention} удалён из списка фильтруемых.")

    @commands.command(help="Показывает список фильтруемых каналов")
    async def listfilters(self, ctx):
        if not self.filter_channel_ids:
            await ctx.send("📭 Список фильтруемых каналов пуст.")
            return

        embed = discord.Embed(title="📵 Фильтруемые каналы", color=0x00ccff)
        for cid in self.filter_channel_ids:
            channel = self.bot.get_channel(cid)
            if channel:
                embed.add_field(name=channel.name, value=channel.mention, inline=False)
            else:
                embed.add_field(name="❓ Неизвестный канал", value=f"ID: {cid}", inline=False)

        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(FilterChannels(bot))
