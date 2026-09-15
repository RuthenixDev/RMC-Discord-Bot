import discord
import time
from discord.ext import commands
from discord import app_commands
from utils.permissions import check_cog_access
from utils import settings_cache as settings
from discord.ui import View, Button
from typing import Optional
from constants import RMC_EMBED_COLOR
<<<<<<< Updated upstream
=======
from cogs.isolation import IsolatedUser

BOT_NAME_REGEXES = [
    re.compile(r"^[a-zA-Z._]+\d{3,8}\.?$", re.IGNORECASE),         # Покрывает: duelist_96035, nikitos511., echoexplorer05448
    re.compile(r"^[a-zA-Z_]+\.[a-zA-Z]{3,5}$", re.IGNORECASE),     # Покрывает: usagii.jjj
    re.compile(r"^[a-zA-Z]+\d+[._]+\d+$", re.IGNORECASE),          # Покрывает: asd2099._19909
    re.compile(r"^[a-zA-Z]+[._]+\d+[._]+\d+$", re.IGNORECASE),     # Покрывает: dimitrii.87_74940
    re.compile(r"^[\d._]+$"),                                      # Только цифры и знаки: 12345_67890
    re.compile(r"[bcdfghjklmnpqrstvwxz]{6,}", re.IGNORECASE),      # Набор из 6+ согласных подряд: dfghjkl
    re.compile(r"^(?:[a-zA-Z]+\d+){3,}[a-zA-Z]*$", re.IGNORECASE), # Чередование букв и цифр: a1b2c3d4
    re.compile(r"^[a-f0-9]{10,}$", re.IGNORECASE)                  # Сгенерированные хэши: a8b4f2c9e1
]


async def evaluate_suspicion(member: discord.Member) -> tuple[float, list]:
    score = 0.0
    reasons = []

    account_age_seconds = (discord.utils.utcnow() - member.created_at).total_seconds()

    if account_age_seconds < 86400:
        score += 3
        reasons.append("Аккаунту меньше 24 часов (+3)")
    elif account_age_seconds < 2592000: # 30 дней
        score += 2
        reasons.append("Аккаунту меньше месяца (+2)")
    elif account_age_seconds < 31536000: # 365 дней
        score += 1
        reasons.append("Аккаунту меньше года (+1)")

    if member.avatar is None:
        score += 1.5
        reasons.append("У аккаунта стандартный аватар (+1.5)")
    elif member.avatar.is_animated():
        score -= 1.5
        reasons.append("У аккаунта анимированный аватар (-1.5)")

    if member.global_name is None:
        score += 1
        reasons.append("У аккаунта не установлено отображаемое имя (+1)")

    if not member.public_flags.value:
        score += 0.5
        reasons.append("У аккаунта нет значков профиля (+0.5)")

    if any(pattern.match(member.name) for pattern in BOT_NAME_REGEXES):
        score += 3
        reasons.append("Ник попадает под паттерн спам-ботов (+3)")

    return score, reasons

class SuspicionActionView(discord.ui.View):
    def __init__(self, target_member: discord.Member, bot: commands.Bot, score: float):
        super().__init__(timeout=None)
        self.target_member = target_member
        self.bot = bot
        self.score = score

    @discord.ui.button(label="Изолировать", style=discord.ButtonStyle.danger)
    async def btn_isolate(self, interaction: discord.Interaction, button: discord.ui.Button):   
        user_roles = [
            role for role in self.target_member.roles 
            if not role.is_default() and not role.managed and role < interaction.guild.me.top_role
        ]
        user_role_ids = [role.id for role in user_roles]
        isolation_cog = self.bot.get_cog("Isolation")
        if not isolation_cog:
            return await interaction.response.send_message("❌ Ошибка: Модуль изоляции не найден.", ephemeral=True)

        isolated_user = IsolatedUser(
            roles=user_role_ids,
            isolated_at=time.time(),
            isolated_by=interaction.user.id,
            reason=f"[Omnivisor] Изолирован из-за высокого уровна подозрительности {self.score}"
        )

        async with isolation_cog._file_lock:
            isolated_data = await isolation_cog.load_isolated_data()
            isolated_data[str(self.target_member.id)] = isolated_user
            await isolation_cog.save_isolated_data(isolated_data)

        settings_data = settings.load_settings()
        isolation_role_id = settings_data.get('isolation_role_id')
        isolation_role = interaction.guild.get_role(isolation_role_id)

        if isolation_role:
            try:
                new_roles = [
                    r for r in self.target_member.roles 
                    if r not in user_roles and r != isolation_role and not r.is_default() and not r.managed
                ]
                new_roles.append(isolation_role)
                await self.target_member.edit(roles=new_roles, reason=f"Изолирован {interaction.user} через Omnivisor.")
            except discord.Forbidden:
                pass # Игнорируем недостаток прав, чтобы кнопка успела изменить состояние

        from utils import omnivisor_db as db
        await db.log_action(
            action_type="Изоляция",
            display_name=self.target_member.display_name,
            username=self.target_member.name,
            user_id=self.target_member.id,
            moderator_id=interaction.user.id,
            reason=isolated_user.reason,
            timestamp=int(isolated_user.isolated_at),
            joined_at=int(self.target_member.joined_at.timestamp()) if self.target_member.joined_at else 0
        )
        isolator_channel = interaction.guild.get_channel(settings_data.get('isolator_channel_id'))
        if isolator_channel:
            await isolator_channel.send(f"{self.target_member.mention} \nДоброго времени суток, это дополнительная проверка, чтобы убедиться, что вы не бот. Ответьте на это сообщение любым образом, чтобы мы могли идентифицировать в вас человека.\n\nHello, this is an additional verification step to ensure you are not a bot. Please reply to this message in any way so we can confirm that you are a human.")

        for child in self.children:
            child.disabled = True

        embed = interaction.message.embeds[0]
        embed.add_field(
            name = "🛡️ Решение",
            value = f"✅ Изолирован модератором {interaction.user.mention}"
        )
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Проигнорировать", style=discord.ButtonStyle.secondary)
    async def btn_ignore(self, interaction: discord.Interaction, button: discord.ui.Button):
        for child in self.children:
            child.disabled = True

        from utils import omnivisor_db as db
        await db.log_action(
            action_type="Игнорирование подозрения",
            display_name=self.target_member.display_name,
            username=self.target_member.name,
            user_id=self.target_member.id,    
            moderator_id=interaction.user.id,
            reason="Модератор счел аккаунт безопасным",
            timestamp=int(time.time()),
            joined_at=int(self.target_member.joined_at.timestamp()) if self.target_member.joined_at else 0
        )
        embed = interaction.message.embeds[0]
        embed.add_field(
            name = "🛡️ Решение",
            value = f"👀 Проигнорирован модератором {interaction.user.mention}"
        )
        await interaction.response.edit_message(embed=embed, view=self)
>>>>>>> Stashed changes

class Omnivisor(commands.Cog):
    """Cog для организации работы проекта Омнивизор через РМК-Бота"""
    required_access = "admin"

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_check(self, ctx: commands.Context):
        allowed = await check_cog_access(ctx, self.required_access)
        if not allowed:
            raise commands.CheckFailure()
        return True
    
    async def check_admin(self, interaction: discord.Interaction) -> bool:
        """Проверяет, есть ли у пользователя админская роль"""
        settings_data = settings.load_settings()
        admin_roles = settings_data.get('admin_roles', [])
        user_roles = [role.id for role in interaction.user.roles]
        return any(role_id in admin_roles for role_id in user_roles)
    
    async def find_first_message(self, member: discord.Member):
        """Пытается найти первое сообщение участника на сервере"""
        first_message = None
        oldest_date = member.joined_at   
        
        for channel in member.guild.text_channels:
            if not channel.permissions_for(member.guild.me).read_message_history:
                continue
                
            try:
                async for message in channel.history(limit=200, oldest_first=True):
                    if message.author == member:
                        if not first_message or message.created_at < first_message.created_at:
                            first_message = message
                            break  
            except discord.Forbidden:
                continue
        
        if first_message:
            timestamp = int(first_message.created_at.timestamp())
            return f"Первое сообщение: <t:{timestamp}:F>\n **Ссылка:** {first_message.jump_url}"
        return "❌ Не удалось найти первое сообщение (возможно, слишком далеко в истории)"
    
    async def find_last_message(self, member: discord.Member):
        """Пытается найти последнее сообщение участника на сервере"""
        last_message = None
        newest_date = 0  
        
        for channel in member.guild.text_channels:
            if not channel.permissions_for(member.guild.me).read_message_history:
                continue
                
            try:
                async for message in channel.history(limit=200):
                    if message.author == member:
                        if not last_message or message.created_at > last_message.created_at:
                            last_message = message
                        break  
                        
            except discord.Forbidden:
                continue
        
        if last_message:
            timestamp = int(last_message.created_at.timestamp())
            return f"Последнее сообщение: <t:{timestamp}:F>\n **Ссылка:** {last_message.jump_url}"
        return "❌ Не удалось найти последнее сообщение"
    
    async def count_messages_slow(self, member: discord.Member, requester: discord.Member) -> int:
        """Считает сообщения участника на сервере (с пагинацией по 5000)"""
        count = 0
        print(f"⚠️ ВНИМАНИЕ: {requester.name} ({requester.id}) запустил подсчёт сообщений для {member.name} ({member.id})")

        
        channels = list(member.guild.text_channels) #+ list(member.guild.threads) + list(member.guild.forums)

        for channel in channels:
            if not channel.permissions_for(member.guild.me).read_message_history:
                continue

            last_id = None  
            while True:
                try:
                   
                    kwargs = {'limit': 5000}
                    if last_id:
                        kwargs['before'] = discord.Object(id=last_id)

                    messages = []
                    async for message in channel.history(**kwargs):
                        messages.append(message)
                        if message.author == member:
                            count += 1

                    if not messages:
                        break  

                    last_id = messages[-1].id

                    if len(messages) < 5000:
                        break

                except discord.Forbidden:
                    break  
                except Exception as e:
                    print(f"Ошибка в канале {channel.name}: {e}")
                    break

        return count
    
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Автоматически собирает информацию о новом участнике, если включена автостатистика"""
        
        settings_data = settings.load_settings()
        auto_stat_enabled = settings_data.get('auto_stat_enabled', 0)

        if auto_stat_enabled != 1:
            return  
        
        channel_id = settings_data.get('log_channel')
        if not channel_id:
            return  
        
        log_channel = member.guild.get_channel(channel_id)
        if not log_channel:
            return
        
        role_id = settings_data.get('auto_stat_role_id')
        role_mention = f"<@&{role_id}>" if role_id else ""
        
        try:
            member_roles = [role for role in member.roles if not role.is_default() and not role.managed]
            role_mentions = [role.mention for role in member_roles]
            roles_text = ", ".join(role_mentions) if role_mentions else "❌ Нет ролей"
            
            user_info_embed = discord.Embed(
                title="📥 Новый участник на сервере",
                description=f"Информация о новом участнике {member.mention}",
                color=RMC_EMBED_COLOR,
                timestamp=discord.utils.utcnow()
            )
            
            user_info_embed.add_field(
                name="Участник",
                value=f"Отображаемое имя: `{member.display_name}` | Глобальное имя: `{member.global_name or 'Нет'}` | ID: `{member.id}`",
                inline=False
            )
            
            user_info_embed.add_field(
                name="Роли участника",
                value=roles_text,
                inline=False
            )
            
            timestamp_created_at = int(member.created_at.timestamp())
            timestamp_joined_at = int(member.joined_at.timestamp())
            
            user_info_embed.add_field(
                name="📅 Даты",
                value=f"Дата создания аккаунта: <t:{timestamp_created_at}:D> | Зашёл на сервер: <t:{timestamp_joined_at}:D>",
                inline=False
            )
            
            # first_message = await self.find_first_message(member)
            # user_info_embed.add_field(
            #     name="📝 Первое сообщение",
            #     value=first_message,
            #     inline=False
            # )
            
            user_info_embed.set_author(
                name=member.display_name,
                icon_url=member.avatar.url if member.avatar else None
            )
            
            user_info_embed.set_footer(
                text=f"Автостатистика"
            )
            
            content = role_mention if role_mention else None
            
            await log_channel.send(content=content, embed=user_info_embed)
            
        except Exception as e:
            # Логируем ошибку, но не прерываем основной процесс
            log_channel.send(f"{role_mention}! Ошибка в автостатистике для **{member.name}**: {e}")
    

    @app_commands.command(
        name="omnivisor_settings",
        description="Настройки информации"
    )
    @app_commands.guild_only()
    @app_commands.describe(
        role = "Роль для упоминания при автостатистике",
        auto_stat = "Статус автостатистики"
    )
    @app_commands.choices(auto_stat=[
        app_commands.Choice(name="Включить", value=1),
        app_commands.Choice(name="Выключить", value=0)
    ])
    async def omnivisor_settings(self, interaction: discord.Interaction, role: Optional[discord.Role], auto_stat: Optional[int]):
        if not await self.check_admin(interaction):
            await interaction.response.send_message("❌ Недостаточно прав", ephemeral=True)
            return

        settings_data = settings.load_settings()

        if role is None and auto_stat is None:
            saved_role_id = settings_data.get('auto_stat_role_id')
            role_object = interaction.guild.get_role(saved_role_id) if saved_role_id else None
            role_text = role_object.mention if role_object else "❌Не настроена"

            auto_stat_enabled = settings_data.get('auto_stat_enabled')
            auto_stat_text = "✅ Включена" if auto_stat_enabled == 1 else "❌ Выключена"

            embed = discord.Embed(
                title="⚙️Сохранённые настройки",
                description=f"В настройках сохранено следующее: \n - Роль упоминания: {role_text} \n - Статус автостатистики: {auto_stat_text}",
                color=RMC_EMBED_COLOR,
                timestamp=discord.utils.utcnow()
            )
            await interaction.response.send_message(embed=embed)
            return
            
        changes = []
        needs_save = False

        if role:
            # if role >= interaction.guild.me.top_role:
            #     embed = discord.Embed(
            #         title="❌Ошибка",
            #         description="Для изоляции нельзя назначить роль, которая выше роли бота!",
            #         color=RMC_EMBED_COLOR,
            #         timestamp=discord.utils.utcnow()
            #     )
            #     await interaction.response.send_message(embed=embed, ephemeral=True)
            #     return
            if role.is_default():
                embed = discord.Embed(
                    title="❌Ошибка",
                    description="Для изоляции нельзя назначить `@everyone`!",
                    color=RMC_EMBED_COLOR,
                    timestamp=discord.utils.utcnow()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            else: 
                settings_data['auto_stat_role_id'] = role.id
                changes.append(f"Роль {role.mention}")
                needs_save = True
                
        if auto_stat is not None:  
            settings_data['auto_stat_enabled'] = auto_stat
            needs_save = True
            if auto_stat == 1:
                changes.append("✅ Автостатистика включена")
            else:  # auto_stat == 0
                changes.append("❌ Автостатистика выключена")

        if needs_save:
            settings.save_settings(settings_data)

            if len(changes) == 1:
                desc = f"Установлен {changes[0]}"
            else:
                desc = f"Установлены: \n- {changes[0]} \n- {changes[1]}"

            embed = discord.Embed(
                title="✅Настройки изменены успешно",
                description = desc,
                color=RMC_EMBED_COLOR,
                timestamp=discord.utils.utcnow()
            )
            await interaction.response.send_message(embed=embed)

        else: 
            embed = discord.Embed(
                title="ℹ️ Нет изменений",
                description="Вы не указали параметры для изменения.",
                color=RMC_EMBED_COLOR,
                timestamp=discord.utils.utcnow()
            )
            await interaction.response.send_message(embed=embed)


    @app_commands.command(
        name="user_info",
        description="Получить информацию об участнике"
    )
    @app_commands.guild_only()
    @app_commands.describe(
        member = "Участник для получения информации",
        count_status = "Включить или выключить подсчёт сообщений. ПРЕДУПРЕЖДЕНИЕ: ОЧЕНЬ РЕСУРСОЗАТРАНАЯ ФУНКЦИЯ, ИСПОЛЬЗОВАТЬ С ОСТОРОЖНОСТЬЮ!!!"
    )
    @app_commands.choices(count_status=[
        app_commands.Choice(name="Включить (опасно!)", value=1),
        app_commands.Choice(name="Выключить", value=0)
    ])
    async def user_info(self, interaction: discord.Interaction, member: discord.Member, count_status: Optional[int] = False):
        if not await self.check_admin(interaction):
            await interaction.response.send_message("❌ Недостаточно прав", ephemeral=True)
            return
        

        try:
            settings_data = settings.load_settings()
            channel_id = settings_data.get('log_channel')
            log_channel = interaction.guild.get_channel(channel_id) if channel_id else None 

            member_roles = [role for role in member.roles if not role.is_default() and not role.managed]
            role_mentions = [role.mention for role in member_roles]
            roles_text = ", ".join(role_mentions) if role_mentions else "❌ Нет ролей"

            if not log_channel:
                embed = discord.Embed(
                    title="❌ Ошибка",
                    description="Канал для логов не настроен! Используйте `/set_log`",
                    color=RMC_EMBED_COLOR
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            await interaction.response.defer(ephemeral=True)

            text=f"{interaction.user.mention}"

            user_info_embed = discord.Embed(
                title="Информация об участнике сервера",
                description=f"Информация об участнике {member.mention}",
                color=RMC_EMBED_COLOR
            )
            user_info_embed.add_field(
                name="Участник",
                value=f"Отображаемое имя: `{member.display_name}` | Глобальное имя: `{member.global_name}` | ID: `{member.id}`",
                inline=False
            )
            user_info_embed.add_field(
                name="Роли участника",
                value=f"{roles_text}"
            )
            timestamp_created_at = int(member.created_at.timestamp())
            timestamp_joined_at = int(member.joined_at.timestamp())

            user_info_embed.add_field(
                name="📅 Даты",
                value=f"Дата создания аккаунта: <t:{timestamp_created_at}:D> | Дата захода на сервер: <t:{timestamp_joined_at}:D>",
                inline=False
            )
            first_message_info = await self.find_first_message(member)
            if not first_message_info:
                first_message_info = "❌ Не удалось найти первое сообщение"
            user_info_embed.add_field(
                name="📝 Первое сообщение",
                value=first_message_info,
                inline=False
            )
            last_message_info = await self.find_last_message(member)
            if not last_message_info:
                last_message_info = "❌ Не удалось найти последнее сообщение"
            user_info_embed.add_field(
                name="📝 Последнее сообщение",
                value=last_message_info,
                inline=False
            )
            count_status_bool = bool(count_status)
            if count_status_bool:
                message_count = await self.count_messages_slow(member, interaction.user)
                display_value = f"~{message_count}"
            else:
                message_count = "❌ Подсчёт сообщений выключен"
                display_value = message_count
            user_info_embed.add_field(
                name="📝 Количество сообщений",
                value=display_value,
                inline=False
            )
            user_info_embed.set_author(
                name=member.display_name,
                icon_url=member.avatar.url
            )
            user_info_embed.set_footer(
                text=f"Запросил: {interaction.user.display_name} ({interaction.user.id})",
                icon_url=interaction.user.avatar.url
            )

            response_embed = discord.Embed(
                title="✅ Информация успешно собрана",
                description=f"Собранная информация отправлена в {log_channel.mention}",
                color=RMC_EMBED_COLOR
            )


            await log_channel.send(embed=user_info_embed, content=text)
            await interaction.followup.send(embed=response_embed, ephemeral=True)
            

            

        except Exception as e:
            embed = discord.Embed(
                title="❌ Ошибка",
                description=f"Не удалось получить информацию об участнике {member.mention}: ```{e}```",
                color=RMC_EMBED_COLOR
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Omnivisor(bot))