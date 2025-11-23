import utils.settings_cache as settings

def load_admin_roles():
    data = settings.load_settings()
    return {int(r) for r in data.get("admin_roles", [])}


async def check_admin(ctx):
    """Проверка, является ли пользователь администратором или имеет роль из admin_roles."""
    admin_roles = load_admin_roles()

    if ctx.author.id == ctx.bot.owner_id:
        return True
    elif ctx.author.guild_permissions.administrator:
        return True
    elif any(role.id in admin_roles for role in ctx.author.roles):
        return True

    return False


async def check_cog_access(ctx, required_access=None):
    """
    Универсальная проверка прав доступа для когов.
    """

    if required_access == "admin":
        return await check_admin(ctx)

    # пример добавления новых уровней 
    #if required_access == "analytics":
    #    return ctx.author.id in analytics_admins

    return True
