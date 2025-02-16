import discord
from discord.ext import commands
from discord import ButtonStyle, SelectOption
import json
import datetime
import asyncio
import io
import html
import os
from dotenv import load_dotenv 
load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

# تعريف أنواع التذاكر
TICKET_TYPES = {
    "Website": "شراء موقع",
    "bots": "شراء بوتات",
    "design": "شراء تصميم",
    "short": "شراء اختصار",
    "inquiry": "استفسار"
}

# رابط البنر
BANNER_URL = "https://cdn.discordapp.com/attachments/1340375716268736546/1340620635100942387/e72d33da6858a6a8.png?ex=67b305c2&is=67b1b442&hm=8024da58f140ca1778b8f067373acd4b983c6bc4c244c8c18cb5343de6c3af62&"

class TicketTypeSelect(discord.ui.Select):
    def __init__(self):
        options = [
            SelectOption(
                label=label,
                value=key,
                emoji="🛒" if "شراء" in label else "❓"
            ) for key, label in TICKET_TYPES.items()
        ]
        super().__init__(
            placeholder="اختر نوع التذكرة",
            options=options,
            custom_id="ticket_type"
        )

    async def callback(self, interaction: discord.Interaction):
        # التحقق من عدم وجود تذكرة مفتوحة
        for channel in interaction.guild.channels:
            if channel.name == f"ticket-{interaction.user.name}":
                await interaction.response.send_message("لديك تذكرة مفتوحة بالفعل!", ephemeral=True)
                return

        # إنشاء التذكرة
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        channel = await interaction.guild.create_text_channel(
            f"ticket-{interaction.user.name}",
            overwrites=overwrites,
            category=interaction.channel.category
        )

        # إنشاء Embed للترحيب
        embed = discord.Embed(
            title=f"تذكرة جديدة - {TICKET_TYPES[self.values[0]]}",
            description=f"مرحباً {interaction.user.mention}!\nسيقوم فريق الدعم بالرد عليك قريباً.",
            color=discord.Color.green(),
            timestamp=datetime.datetime.utcnow()
        )
        
        # إضافة البنر
        embed.set_image(url=BANNER_URL)
        embed.set_author(name=interaction.guild.name, icon_url=interaction.guild.icon.url if interaction.guild.icon else None)
        embed.set_footer(text=f"نوع التذكرة: {TICKET_TYPES[self.values[0]]}")
        
        # إضافة الأزرار
        ticket_view = discord.ui.View(timeout=None)
        ticket_view.add_item(ClaimButton())
        ticket_view.add_item(ControlSelect())
        
        await channel.send(embed=embed, view=ticket_view)
        await interaction.response.send_message(f"تم إنشاء تذكرتك في {channel.mention}", ephemeral=True)

class ControlSelect(discord.ui.Select):
    def __init__(self):
        options = [
            SelectOption(label="نسخ التذكرة", value="copy", description="احصل على نسخة HTML من التذكرة", emoji="📋"),
            SelectOption(label="إغلاق التذكرة", value="close", description="إغلاق التذكرة نهائياً", emoji="🔒"),
            SelectOption(label="إرسال تنبيه", value="notify", description="إرسال تنبيه لصاحب التذكرة", emoji="🔔"),
        ]
        super().__init__(
            placeholder="تحكم في التذكرة",
            options=options,
            custom_id="ticket_controls"
        )

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "copy":
            await self.copy_ticket(interaction)
        elif self.values[0] == "close":
            await self.close_ticket(interaction)
        elif self.values[0] == "notify":
            await self.notify_user(interaction)

    async def copy_ticket(self, interaction: discord.Interaction):
        messages = []
        async for message in interaction.channel.history(limit=100, oldest_first=True):
            messages.append({
                'author': message.author.name,
                'content': message.content,
                'timestamp': message.created_at.strftime("%Y-%m-%d %H:%M:%S")
            })

        html_content = f"""
        <!DOCTYPE html>
        <html dir="rtl">
        <head>
            <meta charset="UTF-8">
            <title>نسخة التذكرة - {interaction.channel.name}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f0f0f0; }}
                .ticket-container {{ max-width: 800px; margin: 0 auto; background-color: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(1,0,0,0); }}
                .message {{ border-bottom: 1px solid #eee; padding: 10px 0; }}
                .author {{ font-weight: bold; color: #730000; }}
                .timestamp {{ color: #999; font-size: 0.8em; }}
                .server-info {{ text-align: center; margin-bottom: 20px; }}
                .server-name {{ font-size: 1.5em; font-weight: bold; color: #730000; }}
            </style>
        </head>
        <body>
            <div class="ticket-container">
                <div class="server-info">
                    <div class="server-name">{interaction.guild.name}</div>
                    <div>تذكرة: {interaction.channel.name}</div>
                </div>
                {''.join([f'''
                <div class="message">
                    <div class="author">{msg['author']}</div>
                    <div class="content">{html.escape(msg['content'])}</div>
                    <div class="timestamp">{msg['timestamp']}</div>
                </div>
                ''' for msg in messages])}
            </div>
        </body>
        </html>
        """

        file = discord.File(io.StringIO(html_content), filename=f"ticket-{interaction.channel.name}.html")
        try:
            await interaction.user.send("هذه نسخة من التذكرة:", file=file)
            await interaction.response.send_message("تم إرسال نسخة من التذكرة إلى الخاص!", ephemeral=True)
        except:
            await interaction.response.send_message("لم نتمكن من إرسال النسخة. الرجاء التأكد من فتح الرسائل الخاصة.", ephemeral=True)

    async def close_ticket(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_channels and interaction.channel.name != f"ticket-{interaction.user.name}":
            await interaction.response.send_message("ليس لديك صلاحية لإغلاق التذكرة!", ephemeral=True)
            return

        confirm_view = ConfirmClose()
        await interaction.response.send_message("هل أنت متأكد من إغلاق التذكرة؟", view=confirm_view, ephemeral=True)

    async def notify_user(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("ليس لديك صلاحية لإرسال تنبيهات!", ephemeral=True)
            return
            
        ticket_owner = interaction.channel.name.replace("ticket-", "")
        member = interaction.guild.get_member_named(ticket_owner)
        
        if member:
            try:
                await member.send(f"هناك رد جديد في تذكرتك في سيرفر {interaction.guild.name}!")
                await interaction.response.send_message("تم إرسال التنبيه بنجاح!", ephemeral=True)
            except:
                await interaction.response.send_message("لم يتم إرسال التنبيه. الرجاء التأكد من أن المستخدم يسمح بالرسائل الخاصة.", ephemeral=True)
        else:
            await interaction.response.send_message("لم يتم العثور على صاحب التذكرة!", ephemeral=True)

class ClaimButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            style=ButtonStyle.blurple,
            label="استلام التذكرة",
            custom_id="claim_ticket"
        )

    async def callback(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("ليس لديك صلاحية لاستلام التذاكر!", ephemeral=True)
            return
            
        embed = discord.Embed(
            title="تم استلام التذكرة",
            description=f"تم استلام التذكرة بواسطة {interaction.user.mention}",
            color=discord.Color.blue()
        )
        embed.set_thumbnail(url="https://canary.discord.com/assets/49f0ac367fcb93fa.svg")
        
        await interaction.response.send_message(embed=embed)
        self.disabled = True
        await interaction.message.edit(view=self.view)

class ConfirmClose(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(label="تأكيد", style=ButtonStyle.red)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("سيتم إغلاق التذكرة خلال 5 ثواني...")
        await asyncio.sleep(5)
        await interaction.channel.delete()

    @discord.ui.button(label="إلغاء", style=ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("تم إلغاء إغلاق التذكرة.", ephemeral=True)

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketTypeSelect())
BANNER_URL = "https://cdn.discordapp.com/attachments/1340375716268736546/1340621879504797716/dc2cb1b3d49ba588.png?ex=67b306eb&is=67b1b56b&hm=01a121a2d90dc9f62aef39864014b2642b565c8e7be90eacf355a5e741ecf722&"

@bot.event
async def on_ready():
    print(f'Bot is ready as {bot.user}')
    print(f'Banner URL: {BANNER_URL}')  # للتأكد من الرابط
    try:
        bot.add_view(TicketView())
    except Exception as e:
        print(f"Error adding views: {e}")

@bot.command()
@commands.has_permissions(administrator=True)
async def setup(ctx):
    embed = discord.Embed(
        title="نظام التذاكر",
        description="اختر نوع التذكرة من القائمة أدناه",
        color=discord.Color.blue()
    )
    
    # إضافة البنر للرسالة الرئيسية
    embed.set_image(url=BANNER_URL)
    embed.set_author(name=ctx.guild.name, icon_url=ctx.guild.icon.url if ctx.guild.icon else None)
    
    await ctx.send(embed=embed, view=TicketView())

# تشغيل البوت
bot.run(os.getenv('DISCORD_TOKEN'))