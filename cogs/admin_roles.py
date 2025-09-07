import discord
from discord.ext import commands
from utils import settings_cache as settings
from constants import RMC_EMBED_COLOR




class AdminSettings(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx: commands.Context):
        data = settings.load_settings()
        admin_roles = data.get("admin_roles", [])

        if ctx.author.guild_permissions.administrator:
            return True 
        if any(str(role.id) in admin_roles for role in ctx.author.roles):
            return True

        raise commands.CheckFailure("❌ У вас нет прав для этого раздела команд. Если вы считаете это ошибкой, свяжитесь с администратором.")


    def update_admin_roles(self, new_roles):
        data = settings.load_settings()

        data["admin_roles"] = list(new_roles)
        settings.save_settings(data)

    @commands.hybrid_command(
        name="addadmin",
        with_app_command=True,
        description="Добавляет роль в список административных"
    )
    async def addadmin(self, ctx, role: discord.Role):
        data = settings.load_settings()

        admin_roles_ids = set(data.get("admin_roles", []))
        if role.id in admin_roles_ids:
            embed = discord.Embed(
                description=f"⚠️ Роль {role.name} уже администратор.",
                color=discord.Color.dark_gray()
            )
            await ctx.reply(
                embed=embed
            )
            return
        admin_roles_ids.add(role.id)
        self.update_admin_roles(admin_roles_ids)
        embed = discord.Embed(
            description=f"✅ Роль {role.name} добавлена в администраторов.",
            color=discord.Color.green()
        )
        await ctx.reply(
            embed=embed
        )

    @commands.hybrid_command(
        name="removeadmin",
        with_app_command=True,
        description="Удаляет роль из списка административных"
    )
    async def removeadmin(self, ctx, role: discord.Role):
        data = settings.load_settings()

        admin_roles_ids = set(data.get("admin_roles", []))
        if role.id not in admin_roles_ids:
            embed = discord.Embed(
                description=f"⚠️ Роль {role.name} не является администратором.",
                color=discord.Color.dark_gray()
            )
            await ctx.reply(
                embed=embed
            )
            return
        admin_roles_ids.remove(role.id)
        self.update_admin_roles(admin_roles_ids)
        embed = discord.Embed(
            description=f"✅ Роль {role.name} удалена из администраторов.",
            color=discord.Color.dark_red()
        )
        await ctx.reply(
            embed=embed
        )

    @commands.hybrid_command(
        name="listadmins",
        with_app_command=True,
        description="Показывает все административные роли"
    )
    async def listadmins(self, ctx):
        data = settings.load_settings()

        admin_roles_ids = set(data.get("admin_roles", []))
        if not admin_roles_ids:
            embed = discord.Embed(
                description="📭 Список административных ролей пуст.",
                color=discord.Color.dark_gray()
            )
            await ctx.reply(
                embed=embed
            )
            return
        embed = discord.Embed(title="💎 Административные роли", color=RMC_EMBED_COLOR)
        for rid in admin_roles_ids:
            role = ctx.guild.get_role(rid)
            embed.add_field(name=role.name if role else "❓ Неизвестная роль",
                            value=role.mention if role else f"ID: {rid}",
                            inline=False)
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(AdminSettings(bot))
