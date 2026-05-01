import discord
from discord.ext import commands
import datetime
import os
import sqlite3
import asyncio
from flask import Flask
from threading import Thread

# ================= CONFIG =================
TOKEN = os.getenv("TOKEN")

LOG_CHANNEL_ID = 1496478745538855146
WELCOME_CHANNEL_ID = 1496478743873589448
VERIFY_ROLE_ID = 1496479066075697234
TICKET_CATEGORY_ID = 1496840441654677614

# ================= WEB (Render 유지용) =================
app = Flask(__name__)

@app.route("/")
def home():
    return "OK - BOT RUNNING"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

def keep_alive():
    Thread(target=run_web, daemon=True).start()

# ================= DB =================
conn = sqlite3.connect("bot.db", check_same_thread=False)
cursor = conn.cursor()

def init_db():
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS warnings (
        user_id INTEGER PRIMARY KEY,
        count INTEGER
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS warn_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        mod_id INTEGER,
        reason TEXT,
        time TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS levels (
        user_id INTEGER PRIMARY KEY,
        xp INTEGER,
        level INTEGER
    )
    """)
    conn.commit()

# ================= BOT =================
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ================= UTIL =================
def embed(title, desc="", color=0x5865F2):
    e = discord.Embed(title=title, description=desc, color=color)
    e.timestamp = datetime.datetime.utcnow()
    return e

# ================= PERMISSION (멀티 서버 대응) =================
def is_staff(member: discord.Member):
    STAFF_NAMES = ["운영진", "Admin", "Staff", "관리자"]

    return any(
        r.name in STAFF_NAMES
        for r in member.roles
    )

# ================= WARNING SYSTEM =================
def get_warn(uid):
    cursor.execute("SELECT count FROM warnings WHERE user_id=?", (uid,))
    r = cursor.fetchone()
    return r[0] if r else 0

def add_warn(uid, mod_id, reason):
    c = get_warn(uid) + 1

    cursor.execute("REPLACE INTO warnings VALUES(?,?)", (uid, c))

    cursor.execute("""
        INSERT INTO warn_logs (user_id, mod_id, reason, time)
        VALUES (?,?,?,?)
    """, (uid, mod_id, reason, datetime.datetime.utcnow().isoformat()))

    conn.commit()
    return c

def remove_warn(uid):
    c = max(get_warn(uid) - 1, 0)
    cursor.execute("REPLACE INTO warnings VALUES(?,?)", (uid, c))
    conn.commit()
    return c

# ================= LEVEL =================
def add_xp(uid):
    cursor.execute("SELECT xp,level FROM levels WHERE user_id=?", (uid,))
    r = cursor.fetchone()
    xp, lv = r if r else (0, 1)

    xp += 10

    if xp >= lv * 100:
        lv += 1
        xp = 0

    cursor.execute("REPLACE INTO levels VALUES(?,?,?)", (uid, xp, lv))
    conn.commit()
    return lv, xp

# ================= TICKET =================
class CloseView(discord.ui.View):
    @discord.ui.button(label="닫기", style=discord.ButtonStyle.danger)
    async def close(self, i, b):
        await i.response.send_message("삭제됨")
        await asyncio.sleep(2)
        await i.channel.delete()

class TicketView(discord.ui.View):
    @discord.ui.button(label="티켓 생성", style=discord.ButtonStyle.primary)
    async def create(self, i, b):
        cat = i.guild.get_channel(TICKET_CATEGORY_ID)
        ch = await i.guild.create_text_channel(name=f"ticket-{i.user.id}", category=cat)
        await ch.send(i.user.mention, view=CloseView())
        await i.response.send_message("생성 완료", ephemeral=True)

# ================= VERIFY =================
class VerifyView(discord.ui.View):
    @discord.ui.button(label="인증", style=discord.ButtonStyle.success)
    async def verify(self, i, b):
        role = i.guild.get_role(VERIFY_ROLE_ID)
        await i.user.add_roles(role)
        await i.response.send_message("인증 완료", ephemeral=True)

# ================= EVENTS =================
@bot.event
async def on_ready():
    init_db()
    await bot.tree.sync()
    print("🔥 FULL OPERATING BOT READY")

@bot.event
async def on_member_join(m):
    ch = bot.get_channel(WELCOME_CHANNEL_ID)
    if ch:
        await ch.send(embed=embed("환영", m.mention))

@bot.event
async def on_message(m):
    if m.author.bot:
        return

    lv, xp = add_xp(m.author.id)
    if xp == 0:
        await m.channel.send(f"{m.author.mention} 레벨업 {lv}")

    await bot.process_commands(m)

# ================= PREFIX COMMANDS (호환용) =================
@bot.command()
async def 경고(ctx, user: discord.Member, *, reason="없음"):
    if not is_staff(ctx.author):
        return await ctx.reply("❌ 권한 없음")

    c = add_warn(user.id, ctx.author.id, reason)
    await ctx.send(embed=embed("경고", f"{user.mention} | {c}회 | {reason}"))

@bot.command()
async def 경고확인(ctx, user: discord.Member):
    c = get_warn(user.id)
    await ctx.send(embed=embed("경고 확인", f"{user.mention} | {c}회"))

@bot.command()
async def 경고감소(ctx, user: discord.Member):
    if not is_staff(ctx.author):
        return await ctx.reply("❌ 권한 없음")

    c = remove_warn(user.id)
    await ctx.send(embed=embed("경고 감소", f"{user.mention} | {c}회"))

@bot.command()
async def 인증패널(ctx):
    if not is_staff(ctx.author):
        return await ctx.reply("❌ 권한 없음")

    await ctx.send(embed=embed("인증"), view=VerifyView())

@bot.command()
async def 티켓패널(ctx):
    await ctx.send(embed=embed("티켓"), view=TicketView())

# ================= SLASH COMMANDS =================
@bot.tree.command(name="경고")
async def slash_warn(interaction: discord.Interaction, user: discord.Member, reason: str = "없음"):
    if not is_staff(interaction.user):
        return await interaction.response.send_message("❌ 권한 없음", ephemeral=True)

    c = add_warn(user.id, interaction.user.id, reason)

    await interaction.response.send_message(
        embed=embed("경고", f"{user.mention} | {c}회 | {reason}")
    )

@bot.tree.command(name="경고확인")
async def slash_check(interaction: discord.Interaction, user: discord.Member):
    c = get_warn(user.id)

    await interaction.response.send_message(
        embed=embed("경고 확인", f"{user.mention} | {c}회")
    )

@bot.tree.command(name="경고감소")
async def slash_minus(interaction: discord.Interaction, user: discord.Member):
    if not is_staff(interaction.user):
        return await interaction.response.send_message("❌ 권한 없음", ephemeral=True)

    c = remove_warn(user.id)

    await interaction.response.send_message(
        embed=embed("경고 감소", f"{user.mention} | {c}회")
    )

@bot.tree.command(name="인증패널")
async def slash_verify(interaction: discord.Interaction):
    if not is_staff(interaction.user):
        return await interaction.response.send_message("❌ 권한 없음", ephemeral=True)

    await interaction.response.send_message("인증", view=VerifyView())

@bot.tree.command(name="티켓패널")
async def slash_ticket(interaction: discord.Interaction):
    await interaction.response.send_message("티켓", view=TicketView())

# ================= RUN =================
async def main():
    keep_alive()
    await bot.start(TOKEN)

asyncio.run(main())
