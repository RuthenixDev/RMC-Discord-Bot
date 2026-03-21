import discord
from discord.ext import commands
from discord.ui import Button, View
from discord import app_commands
from utils.permissions import check_cog_access
from utils import settings_cache as settings
from constants import RMC_EMBED_COLOR

class CommandWrapper:
    def __init__(self, name, description, cog, is_admin, is_slash=False):
        self.name = name
        self.description = description
        self.cog = cog
        self.hidden = False
        self.is_admin = is_admin
        self.is_slash = is_slash
        
class PaginatedHelpView(View):
    def __init__(self, command_chunks, author, admin_command_names=None, description=None):
        super().__init__(timeout=60)
        self.command_chunks = command_chunks
        self.current_page = 0
        self.author = author
        self.admin_command_names = admin_command_names or []
        self.description = description
        #self.message = None
    
    @discord.ui.button(label="◀️ Назад", style=discord.ButtonStyle.secondary, custom_id="help_prev")
    async def previous_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user != self.author:
            return await interaction.response.send_message("❌ Эта кнопка не для тебя!", ephemeral=True)
        
        self.current_page = (self.current_page - 1) % len(self.command_chunks)
        embed = self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="▶️ Вперед", style=discord.ButtonStyle.secondary, custom_id="help_next")
    async def next_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user != self.author:
            return await interaction.response.send_message("❌ Эта кнопка не для тебя!", ephemeral=True)
        
        self.current_page = (self.current_page + 1) % len(self.command_chunks)
        embed = self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    def create_embed(self):
        embed = discord.Embed(
            title=f"🛠️ Список команд (страница {self.current_page + 1}/{len(self.command_chunks)})",
            color=RMC_EMBED_COLOR,
            description=self.description
        )
        
        commands_list = self.command_chunks[self.current_page]
        for command in commands_list:

            if hasattr(command, 'is_slash') and command.is_slash:
                prefix = "/"
            else:
                prefix = "!rmc "

            name = f"{prefix}{command.name}"
            if command.name in self.admin_command_names:  # проверка по имени
                name = "👑 " + name
            embed.add_field(
                name=name,
                value=command.description or "Без описания",
                inline=False
            )
        
        return embed
    #async def on_timeout(self):
    #    """Когда кнопки истекли на сцене появлется данный герой"""
    #    for child in self.children:
    #        child.disabled = True
#
    #    if self.message:
    #        try:
    #            embed = self.create_embed()
    #            embed.set_footer(text="⏰ Время ожидания истекло. Используйте /help заново.")
    #            await self.message.edit(embed=embed, view=self)
    #        except:
    #            pass



class HelpCmd(commands.Cog):
    required_access = None

    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx: commands.Context):
        allowed = await check_cog_access(ctx, self.required_access)
        if not allowed:
            raise commands.CheckFailure()
        return True

    @commands.hybrid_command(
        name="help",
        with_app_command=True,
        description="Показывает список команд"
    )
    async def help(self, ctx: commands.Context):
        # Собираем обычные команды
        regular_commands = []
        admin_commands = []

        for command in self.bot.commands:
            if command.hidden or command.name == "help":
                continue
            
            is_admin_cmd = hasattr(command.cog, 'required_access') and command.cog.required_access == "admin"
            
            wrapper = CommandWrapper(
                name=command.name,
                description=command.description or "Без описания",
                cog=command.cog,
                is_admin=is_admin_cmd,
                is_slash=False  # обычные команды
            )
            
            if is_admin_cmd:
                admin_commands.append(wrapper)
            else:
                regular_commands.append(wrapper)

        # Собираем чистые слэш-команды
        for cmd in self.bot.tree.walk_commands():
            # Пропускаем, если это гибридная команда (уже есть в bot.commands)
            if any(c.name == cmd.name for c in self.bot.commands):
                continue
            
            # Определяем, админская ли команда
            is_admin_cmd = False
            if hasattr(cmd, 'binding') and hasattr(cmd.binding, 'required_access'):
                if cmd.binding.required_access == "admin":  # ✅ исправлено
                    is_admin_cmd = True
            
            # Создаём обёртку
            
            wrapper = CommandWrapper(
                name=cmd.name,
                description=cmd.description or "Без описания",
                cog=cmd.binding if hasattr(cmd, 'binding') else None,
                is_admin=is_admin_cmd,
                is_slash=True
            )
            
            if is_admin_cmd:
                admin_commands.append(wrapper)
            else:
                regular_commands.append(wrapper)

        user_roles = ctx.author.roles

        settings_data = settings.load_settings()
        admin_roles = settings_data.get('admin_roles', [])
        is_admin = any(role.id in admin_roles for role in user_roles)
        
        if is_admin:
            display_commands = regular_commands + admin_commands
        else:
            display_commands = regular_commands
        # Разбиваем на группы по 20 команд (оставляем запас)

        desc="Команды для админов помечены 👑" if is_admin else None
        #print(f"is_admin={is_admin}, desc={desc}") 

        chunk_size = 20
        command_chunks = [display_commands[i:i + chunk_size] 
                         for i in range(0, len(display_commands), chunk_size)]
        
        if not command_chunks:
            await ctx.reply("❌ Команды не найдены!")
            return
        
        

        # Если всего 1 страница - отправляем просто embed
        if len(command_chunks) == 1:
            
            embed = discord.Embed(
                title="🛠️ Список доступных команд",
                color=RMC_EMBED_COLOR,
                description=desc
            )
            
            for command in display_commands:
                is_admin_command = hasattr(command.cog, 'required_access') and command.cog.required_access == 'admin'
                name = f"!rmc {command.name}"
                if is_admin_command:
                    name = "👑 " + name
                embed.add_field(
                    name=name,
                    value=command.description or "Без описания",
                    inline=False
                )
            
            await ctx.reply(embed=embed)
        else:
            # Если много страниц - используем пагинацию
            admin_names = [cmd.name for cmd in admin_commands]  # список имён админских команд
            view = PaginatedHelpView(command_chunks, ctx.author, admin_names, description=desc)
            embed = view.create_embed()
            await ctx.reply(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(HelpCmd(bot))