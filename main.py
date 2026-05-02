import discord
from discord.ext import commands
import os
import sqlite3
import datetime
import asyncio
import random
from flask import Flask
from threading import Thread

# ================= CONFIG =================
TOKEN = os.getenv("TOKEN")
VERIFY_ROLE_ID = 1499675598178750560

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ================= KEEP ALIVE =================
app = Flask(__name__)

@app.route("/")
def home():
    return "BOT ONLINE"

def run():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

def keep_alive():
    Thread(target=run, daemon=True).start()

# ================= DB =================
DB = sqlite3.connect("bot.db", check_same_thread=False)
CUR = DB.cursor()

def init_db():
    CUR.execute("CREATE TABLE IF NOT EXISTS money (uid INTEGER PRIMARY KEY, bal INTEGER)")
    CUR.execute("CREATE TABLE IF NOT EXISTS warn (gid INTEGER, uid INTEGER, cnt INTEGER)")
    CUR.execute("CREATE TABLE IF NOT EXISTS sticky (cid INTEGER PRIMARY KEY, msg TEXT)")
    CUR.execute("""
    CREATE TABLE IF NOT EXISTS config (
        gid INTEGER PRIMARY KEY,
        welcome INTEGER,
        log INTEGER,
        ticket INTEGER
    )
    """)
    DB.commit()

# ================= EMBED =================
def embed(t, d="", c=0x5865F2):
    return discord.Embed(
        title=f"✨ {t}",
        description=d,
        color=c,
        timestamp=datetime.datetime.utcnow()
    )

# ================= ECONOMY =================
def money(uid):
    CUR.execute("SELECT bal FROM money WHERE uid=?", (uid,))
    r = CUR.fetchone()
    return r[0] if r else 0

def set_money(uid, v):
    CUR.execute("REPLACE INTO money VALUES (?,?)", (uid, max(v, 0)))
    DB.commit()

def add_money(uid, v):
    set_money(uid, money(uid) + v)

def remove_money(uid, v):
    set_money(uid, money(uid) - v)

# ================= WARN SYSTEM =================
def warn_count(gid, uid):
    CUR.execute("SELECT cnt FROM warn WHERE gid=? AND uid=?", (gid, uid))
    r = CUR.fetchone()
    return r[0] if r else 0

def add_warn(gid, uid):
    c = warn_count(gid, uid) + 1
    CUR.execute("REPLACE INTO warn VALUES (?,?,?)", (gid, uid, c))
    DB.commit()
    return c

def clear_warn(gid, uid):
    CUR.execute("DELETE FROM warn WHERE gid=? AND uid=?", (gid, uid))
    DB.commit()

async def punish(member, c):
    try:
        if c == 1:
            await member.timeout(datetime.timedelta(minutes=10))
        elif c == 2:
            await member.timeout(datetime.timedelta(hours=1))
        elif c == 3:
            await member.timeout(datetime.timedelta(days=1))
        elif c == 4:
            await member.kick()
        elif c >= 5:
            await member.ban()
    except:
        pass

# ================= CHANNEL CONFIG =================
def set_channel(gid, key, val):
    CUR.execute("INSERT OR IGNORE INTO config (gid) VALUES (?)", (gid,))
    CUR.execute(f"UPDATE config SET {key}=? WHERE gid=?", (val, gid))
    DB.commit()

def get_channel(gid, key):
    CUR.execute(f"SELECT {key} FROM config WHERE gid=?", (gid,))
    r = CUR.fetchone()
    return r[0] if r else None

# ================= STICKY =================
@bot.event
async def on_message(m):
    if m.author.bot:
        return

    CUR.execute("SELECT msg FROM sticky WHERE cid=?", (m.channel.id,))
    r = CUR.fetchone()

    if r:
        await m.channel.send(embed=embed("📌 스티키", r[0]))

    await bot.process_commands(m)

@bot.tree.command(name="스티키")
async def sticky(i, msg: str):
    CUR.execute("REPLACE INTO sticky VALUES (?,?)", (i.channel.id, msg))
    DB.commit()
    await i.response.send_message(embed=embed("스티키 설정 완료", msg))

# ================= VERIFY =================
class VerifyView(discord.ui.View):
    @discord.ui.button(label="인증", style=discord.ButtonStyle.success)
    async def v(self, i, b):
        role = i.guild.get_role(VERIFY_ROLE_ID)
        if not role:
            role = await i.guild.create_role(name="인증")

        await i.user.add_roles(role)
        await i.response.send_message(embed=embed("인증 완료"), ephemeral=True)

# ================= TICKET =================
class TicketView(discord.ui.View):
    @discord.ui.button(label="티켓 생성", style=discord.ButtonStyle.primary)
    async def create(self, i, b):

        cat_id = get_channel(i.guild.id, "ticket")
        cat = i.guild.get_channel(cat_id) if cat_id else None

        ch = await i.guild.create_text_channel(
            name=f"ticket-{i.user.id}",
            category=cat
        )

        await ch.send(i.user.mention, view=CloseTicket())
        await i.response.send_message(embed=embed("티켓 생성 완료"), ephemeral=True)

class CloseTicket(discord.ui.View):
    @discord.ui.button(label="닫기", style=discord.ButtonStyle.danger)
    async def close(self, i, b):
        await i.channel.delete()

# ================= ADMIN PANEL =================
class AdminPanel(discord.ui.View):
    @discord.ui.button(label="서버 상태")
    async def s(self, i, b):
        await i.response.send_message(embed=embed("상태", "ONLINE"))

    @discord.ui.button(label="경고 확인")
    async def w(self, i, b):
        c = warn_count(i.guild.id, i.user.id)
        await i.response.send_message(embed=embed("경고", f"{c}회"))

# ================= CHANNEL SET =================
@bot.tree.command(name="채널설정")
async def set_ch(i, 종류: str, 채널: discord.TextChannel):

    mp = {
        "입장": "welcome",
        "로그": "log",
        "티켓": "ticket"
    }

    set_channel(i.guild.id, mp[종류], 채널.id)
    await i.response.send_message(embed=embed("채널 설정 완료"))

# ================= WARN COMMAND =================
@bot.tree.command(name="경고")
async def warn(i, u: discord.Member, reason: str = "없음"):

    if not i.user.guild_permissions.administrator:
        return await i.response.send_message("권한 없음", ephemeral=True)

    c = add_warn(i.guild.id, u.id)
    await punish(u, c)

    await i.response.send_message(embed=embed("경고", f"{u.mention} → {c}회\n{reason}"))

@bot.tree.command(name="경고확인")
async def warn_check(i, u: discord.Member):
    await i.response.send_message(embed=embed("경고 확인", f"{u.mention} → {warn_count(i.guild.id, u.id)}회"))

@bot.tree.command(name="경고삭제")
async def warn_clear(i, u: discord.Member):
    clear_warn(i.guild.id, u.id)
    await i.response.send_message(embed=embed("경고 삭제 완료"))

# ================= ECONOMY =================
@bot.tree.command(name="잔액")
async def bal(i, u: discord.Member=None):
    u = u or i.user
    await i.response.send_message(embed=embed("잔액", f"{money(u.id)}원"))

@bot.tree.command(name="송금")
async def pay(i, u: discord.Member, amt: int):
    if money(i.user.id) < amt:
        return await i.response.send_message("잔액 부족", ephemeral=True)

    remove_money(i.user.id, amt)
    add_money(u.id, amt)

    await i.response.send_message(embed=embed("송금 완료"))

# ================= PANELS =================
@bot.tree.command(name="관리자패널")
async def panel(i):
    await i.response.send_message(embed=embed("관리자 패널"), view=AdminPanel())

@bot.tree.command(name="티켓패널")
async def ticket(i):
    await i.response.send_message(embed=embed("티켓 시스템"), view=TicketView())

@bot.tree.command(name="인증패널")
async def verify(i):
    await i.response.send_message(embed=embed("인증 시스템"), view=VerifyView())

# ================= READY =================
@bot.event
async def on_ready():
    init_db()
    await bot.tree.sync()
    print("🔥 FULL V4 SYSTEM READY")

def start():
    keep_alive()
    bot.run(TOKEN)

if __name__ == "__main__":
    start()
