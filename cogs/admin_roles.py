import discord
from discord.ext import commands
from utils.settings import load_settings, save_settings

class AdminSettings(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.settings = load_settings()
        self.admin_roles_ids = set(self.settings.get("admin_roles", []))

    def update_admin_roles(self):
        self.settings["admin_roles"] = list(self.admin_roles_ids)
        save_settings(self.settings)

    @commands.command(help="Добавляет роль в список административных")
    @commands.has_permissions(administrator=True)
    async def addadmin(self, ctx, role: discord.Role):
        if role.id in self.admin_roles_ids:
            await ctx.send(f"⚠️ Роль {role.name} уже есть в списке.")
            return
        self.admin_roles_ids.add(role.id)
        self.update_admin_roles()
        await ctx.send(f"✅ Роль {role.name} добавлена в список административных.")

    @commands.command(help="Удаляет роль из списка административных")
    @commands.has_permissions(administrator=True)
    async def removeadmin(self, ctx, role: discord.Role):
        if role.id not in self.admin_roles_ids:
            await ctx.send(f"⚠️ Роль {role.name} не найдена.")
            return
        self.admin_roles_ids.remove(role.id)
        self.update_admin_roles()
        await ctx.send(f"✅ Роль {role.name} удалена из списка административных.")

    @commands.command(help="Выводит все административные роли")
    async def listadmins(self, ctx):
        if not self.admin_roles_ids:
            await ctx.send("📭 Список административных ролей пуст.")
            return
        embed = discord.Embed(title="💎 Административные роли", color=0x00ccff)
        for rid in self.admin_roles_ids:
            role = ctx.guild.get_role(rid)
            embed.add_field(name=role.name if role else "❓ Неизвестная роль",
                            value=role.mention if role else f"ID: {rid}",
                            inline=False)
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(AdminSettings(bot))
