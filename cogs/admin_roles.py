import discord
from discord.ext import commands
from utils import settings as settings



class AdminSettings(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def update_admin_roles(self, new_roles):
        data = settings.get()
        data["admin_roles"] = list(new_roles)
        settings.save()

    @commands.command(help="Добавляет роль в список административных")
    @commands.has_permissions(administrator=True)
    async def addadmin(self, ctx, role: discord.Role):
        data = settings.get()
        admin_roles_ids = set(data.get("admin_roles", []))
        if role.id in admin_roles_ids:
            await ctx.send(f"⚠️ Роль {role.name} уже есть в списке.")
            return
        admin_roles_ids.add(role.id)
        self.update_admin_roles(admin_roles_ids)
        await ctx.send(f"✅ Роль {role.name} добавлена в список административных.")

    @commands.command(help="Удаляет роль из списка административных")
    @commands.has_permissions(administrator=True)
    async def removeadmin(self, ctx, role: discord.Role):
        data = settings.get()
        admin_roles_ids = set(data.get("admin_roles", []))
        if role.id not in admin_roles_ids:
            await ctx.send(f"⚠️ Роль {role.name} не найдена.")
            return
        admin_roles_ids.remove(role.id)
        self.update_admin_roles(admin_roles_ids)
        await ctx.send(f"✅ Роль {role.name} удалена из списка административных.")

    @commands.command(help="Выводит все административные роли")
    async def listadmins(self, ctx):
        data = settings.get()
        admin_roles_ids = set(data.get("admin_roles", []))
        if not admin_roles_ids:
            await ctx.send("📭 Список административных ролей пуст.")
            return
        embed = discord.Embed(title="💎 Административные роли", color=0x00ccff)
        for rid in admin_roles_ids:
            role = ctx.guild.get_role(rid)
            embed.add_field(name=role.name if role else "❓ Неизвестная роль",
                            value=role.mention if role else f"ID: {rid}",
                            inline=False)
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(AdminSettings(bot))
