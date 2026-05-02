# ================== IMPORT ==================
import discord
from discord.ext import commands
import os
import sqlite3
import datetime
import asyncio
import random
from flask import Flask
from threading import Thread

# ================== CONFIG ==================
TOKEN = os.getenv("TOKEN")

SALARY_AMOUNT = 100000
SALARY_COOLDOWN = 5
ATTENDANCE_AMOUNT = 500000
MAX_BET = 1000000

DICE_COST = 50000
DICE_WIN = DICE_COST * 3

DB = sqlite3.connect("bot.db", check_same_thread=False)
CUR = DB.cursor()

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ================== KEEP ALIVE ==================
app = Flask(__name__)

@app.route("/")
def home():
    return "BOT ONLINE"

def run():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

def keep_alive():
    Thread(target=run, daemon=True).start()

# ================== DB INIT ==================
def init_db():
    CUR.execute("CREATE TABLE IF NOT EXISTS money (uid INTEGER PRIMARY KEY, bal INTEGER)")
    CUR.execute("CREATE TABLE IF NOT EXISTS warn (uid INTEGER PRIMARY KEY, cnt INTEGER)")
    CUR.execute("CREATE TABLE IF NOT EXISTS attendance (uid INTEGER PRIMARY KEY, date TEXT)")
    CUR.execute("""
    CREATE TABLE IF NOT EXISTS config (
        gid INTEGER PRIMARY KEY,
        welcome INTEGER,
        log INTEGER,
        level INTEGER
    )
    """)
    DB.commit()

# ================== UTIL ==================
def embed(t, d="", c=0x5865F2):
    e = discord.Embed(title=t, description=d, color=c)
    e.timestamp = datetime.datetime.utcnow()
    return e

def money(uid):
    CUR.execute("SELECT bal FROM money WHERE uid=?", (uid,))
    r = CUR.fetchone()
    return r[0] if r else 0

def set_money(uid, v):
    CUR.execute("REPLACE INTO money VALUES (?,?)", (uid, max(v,0)))
    DB.commit()

def add_money(uid, v): set_money(uid, money(uid)+v)
def sub_money(uid, v): set_money(uid, money(uid)-v)

def warn(uid):
    CUR.execute("SELECT cnt FROM warn WHERE uid=?", (uid,))
    r = CUR.fetchone()
    return r[0] if r else 0

def add_warn(uid):
    c = warn(uid)+1
    CUR.execute("REPLACE INTO warn VALUES (?,?)", (uid,c))
    DB.commit()
    return c

def clear_warn(uid):
    CUR.execute("REPLACE INTO warn VALUES (?,0)", (uid,))
    DB.commit()

def set_ch(gid, key, val):
    CUR.execute("INSERT OR IGNORE INTO config (gid) VALUES (?)", (gid,))
    CUR.execute(f"UPDATE config SET {key}=? WHERE gid=?", (val,gid))
    DB.commit()

def get_ch(gid, key):
    CUR.execute(f"SELECT {key} FROM config WHERE gid=?", (gid,))
    r=CUR.fetchone()
    return r[0] if r else None

def today():
    return (datetime.datetime.utcnow()+datetime.timedelta(hours=9)).strftime("%Y-%m-%d")

# ================== EVENTS ==================
@bot.event
async def on_ready():
    init_db()
    await bot.tree.sync()
    print("🔥 READY")

@bot.event
async def on_member_join(m):
    ch_id = get_ch(m.guild.id,"welcome")
    if ch_id:
        ch = bot.get_channel(ch_id)
        if ch:
            await ch.send(embed=embed("환영", m.mention))

# ================== ECONOMY ==================
salary_cd = {}

@bot.tree.command(name="월급")
async def salary(i: discord.Interaction):
    now = datetime.datetime.now().timestamp()
    last = salary_cd.get(i.user.id,0)

    if now-last < SALARY_COOLDOWN:
        return await i.response.send_message("쿨타임", ephemeral=True)

    salary_cd[i.user.id]=now
    add_money(i.user.id, SALARY_AMOUNT)

    await i.response.send_message(embed=embed("월급", f"{SALARY_AMOUNT}원 지급"))

@bot.tree.command(name="출석")
async def attendance(i: discord.Interaction):
    CUR.execute("SELECT date FROM attendance WHERE uid=?", (i.user.id,))
    r=CUR.fetchone()

    if r and r[0]==today():
        return await i.response.send_message("이미 출석", ephemeral=True)

    CUR.execute("REPLACE INTO attendance VALUES (?,?)",(i.user.id,today()))
    DB.commit()

    add_money(i.user.id, ATTENDANCE_AMOUNT)

    await i.response.send_message(embed=embed("출석", f"{ATTENDANCE_AMOUNT}원"))

@bot.tree.command(name="잔액")
async def balance(i: discord.Interaction, user: discord.Member=None):
    user=user or i.user
    await i.response.send_message(embed=embed("잔액", f"{user.mention}: {money(user.id)}원"))

@bot.tree.command(name="송금")
async def transfer(i: discord.Interaction, user: discord.Member, amt:int):
    if money(i.user.id)<amt:
        return await i.response.send_message("잔액 부족",ephemeral=True)

    sub_money(i.user.id, amt)
    add_money(user.id, amt)

    await i.response.send_message(embed=embed("송금", f"{user.mention}에게 {amt}원"))

# ================== WARN ==================
@bot.tree.command(name="경고")
async def warn_cmd(i:discord.Interaction, user:discord.Member):
    c=add_warn(user.id)
    await i.response.send_message(embed=embed("경고", f"{user.mention} {c}회"))

@bot.tree.command(name="경고확인")
async def warn_check(i:discord.Interaction, user:discord.Member):
    await i.response.send_message(embed=embed("경고", f"{user.mention} {warn(user.id)}회"))

@bot.tree.command(name="경고삭제")
async def warn_clear_cmd(i:discord.Interaction, user:discord.Member):
    clear_warn(user.id)
    await i.response.send_message("초기화")

# ================== CHANNEL ==================
@bot.tree.command(name="채널")
async def ch(i:discord.Interaction, 종류:str, 채널:discord.TextChannel):
    mp={"입장":"welcome","로그":"log","레벨":"level"}
    set_ch(i.guild.id, mp[종류], 채널.id)
    await i.response.send_message("설정 완료")

# ================== GAME ==================
@bot.tree.command(name="홀짝")
async def odd_even(i:discord.Interaction, amt:int):
    n=random.randint(1,100)
    res="홀수" if n%2 else "짝수"

    await i.response.send_message(f"{n} → {res}")

@bot.tree.command(name="주사위")
async def dice(i:discord.Interaction):
    if money(i.user.id)<DICE_COST:
        return await i.response.send_message("돈 부족",ephemeral=True)

    n=random.randint(1,6)

    if n==6:
        add_money(i.user.id,DICE_WIN)
        await i.response.send_message(f"🎉 {n} → {DICE_WIN}원")
    else:
        sub_money(i.user.id,DICE_COST)
        await i.response.send_message(f"💥 {n} → -{DICE_COST}")

# ================== RUN ==================
async def main():
    keep_alive()
    await bot.start(TOKEN)

asyncio.run(main())
