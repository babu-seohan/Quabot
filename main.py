import discord
from discord.ext import commands, tasks
from discord import app_commands
import datetime
import os
import sqlite3
import asyncio
from flask import Flask
from threading import Thread

# ================= KEEP ALIVE =================
app = Flask(__name__)

@app.route("/")
def home():
    return "봇 살아있음", 200

def keep_alive():
    Thread(target=lambda: app.run(host="0.0.0.0", port=10000), daemon=True).start()

# ================= DB =================
conn = sqlite3.connect("bot.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("CREATE TABLE IF NOT EXISTS warnings (user_id INTEGER PRIMARY KEY, count INTEGER)")
cursor.execute("CREATE TABLE IF NOT EXISTS levels (user_id INTEGER PRIMARY KEY, xp INTEGER, level INTEGER)")
conn.commit()

# ================= 환경 =================
TOKEN = os.getenv("TOKEN")
LOG_CHANNEL_ID = 1496478745538855146
WELCOME_CHANNEL_ID = 1496478743873589448
VERIFY_ROLE_ID = 1496479066075697234
TICKET_CATEGORY_ID = 1496840441654677614

# ================= 봇 =================
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ================= 유틸 =================
def embed(title, desc="", color=0x5865F2):
    e = discord.Embed(title=title, description=desc, color=color)
    e.timestamp = datetime.datetime.utcnow()
    return e

async def safe_send(channel, **kwargs):
    try:
        await channel.send(**kwargs)
    except:
        pass

async def log(msg):
    try:
        ch = bot.get_channel(LOG_CHANNEL_ID)
        if ch:
            await ch.send(embed=embed("📜 로그", msg))
    except:
        pass

# ================= 경고 =================
def get_warn(uid):
    cursor.execute("SELECT count FROM warnings WHERE user_id=?", (uid,))
    r = cursor.fetchone()
    return r[0] if r else 0

def add_warn(uid):
    count = get_warn(uid) + 1
    cursor.execute("REPLACE INTO warnings VALUES(?,?)", (uid, count))
    conn.commit()
    return count

def remove_warn(uid):
    count = max(get_warn(uid) - 1, 0)
    cursor.execute("REPLACE INTO warnings VALUES(?,?)", (uid, count))
    conn.commit()
    return count

async def auto_punish(member, count):
    try:
        if count == 1:
            await member.timeout(datetime.timedelta(minutes=10))
            return "타임아웃 10분"
        elif count == 2:
            await member.timeout(datetime.timedelta(hours=1))
            return "타임아웃 1시간"
        elif count == 3:
            await member.timeout(datetime.timedelta(days=1))
            return "타임아웃 1일"
        elif count == 4:
            await member.kick()
            return "킥"
        elif count == 5:
            await member.ban()
            return "밴"
    except Exception as e:
        return f"처벌 실패: {e}"

# ================= 레벨 =================
def add_xp(uid):
    cursor.execute("SELECT xp, level FROM levels WHERE user_id=?", (uid,))
    r = cursor.fetchone()

    if not r:
        xp, level = 0, 1
    else:
        xp, level = r

    xp += 10
    if xp >= level * 100:
        level += 1
        xp = 0

    cursor.execute("REPLACE INTO levels VALUES(?,?,?)", (uid, xp, level))
    conn.commit()
    return level, xp

# ================= 티켓 =================
class CloseView(discord.ui.View):
    @discord.ui.button(label="🔒 닫기", style=discord.ButtonStyle.danger)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("5초 후 삭제됨")
        await log(f"티켓 종료: {interaction.channel.name}")
        await asyncio.sleep(5)
        try:
            await interaction.channel.delete()
        except:
            pass

class TicketView(discord.ui.View):
    @discord.ui.button(label="🎫 티켓", style=discord.ButtonStyle.primary)
    async def ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        category = guild.get_channel(TICKET_CATEGORY_ID)

        ch = await guild.create_text_channel(
            name=f"ticket-{interaction.user.id}",
            category=category
        )

        await ch.send(f"{interaction.user.mention} 티켓 생성", view=CloseView())
        await interaction.response.send_message(f"생성됨: {ch.mention}", ephemeral=True)

# ================= 인증 =================
class VerifyView(discord.ui.View):
    @discord.ui.button(label="인증", style=discord.ButtonStyle.success)
    async def verify(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = interaction.guild.get_role(VERIFY_ROLE_ID)
        try:
            await interaction.user.add_roles(role)
            await interaction.response.send_message("인증 완료", ephemeral=True)
        except:
            await interaction.response.send_message("실패", ephemeral=True)

# ================= 명령어 =================
@bot.tree.command(name="경고")
async def warn(interaction: discord.Interaction, user: discord.Member, 이유: str):
    count = add_warn(user.id)
    result = await auto_punish(user, count)

    msg = f"{user.mention} 경고 {count}회\n이유: {이유}"
    if result:
        msg += f"\n처벌: {result}"

    await interaction.response.send_message(embed=embed("⚠️ 경고", msg))
    await log(msg)

@bot.tree.command(name="경고취소")
async def unwarn(interaction: discord.Interaction, user: discord.Member):
    count = remove_warn(user.id)
    await interaction.response.send_message(embed=embed("✅ 경고 감소", f"{user.mention} → {count}회"))

@bot.tree.command(name="경고확인")
async def checkwarn(interaction: discord.Interaction, user: discord.Member):
    count = get_warn(user.id)
    await interaction.response.send_message(embed=embed("📊 경고", f"{user.mention} → {count}회"))

@bot.tree.command(name="티켓패널")
async def ticket_panel(interaction: discord.Interaction):
    await interaction.response.send_message(embed=embed("🎫 티켓"), view=TicketView())

@bot.command()
async def 인증패널(ctx):
    await ctx.send(embed=embed("인증"), view=VerifyView())

# ================= 이벤트 =================
@bot.event
async def on_member_join(member):
    ch = bot.get_channel(WELCOME_CHANNEL_ID)
    if ch:
        await safe_send(ch, embed=embed("환영", f"{member.mention} 환영"))

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    level, xp = add_xp(message.author.id)

    if xp == 0:
        await safe_send(message.channel, content=f"{message.author.mention} 레벨업! {level}")

    await bot.process_commands(message)

# ================= 자동 재연결 =================
@tasks.loop(seconds=30)
async def auto_reconnect():
    if not bot.is_closed():
        return

    try:
        await bot.start(TOKEN)
    except:
        pass

# ================= 실행 =================
@bot.event
async def on_ready():
    await bot.tree.sync()
    print("🔥 안정화 봇 실행 완료")
    auto_reconnect.start()

def run_bot():
    while True:
        try:
            bot.run(TOKEN)
        except Exception as e:
            print("💥 봇 죽음 → 재시작", e)
            asyncio.sleep(5)

keep_alive()
run_bot()
