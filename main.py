# ================== IMPORT ==================
import discord
from discord.ext import commands
import os
import sqlite3
import datetime
import asyncio
from flask import Flask
from threading import Thread

# ================== CONFIG ==================
TOKEN = os.getenv("TOKEN")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ================== KEEP ALIVE ==================
app = Flask(__name__)

@app.route("/")
def home():
    return "BOT ONLINE"

def keep_alive():
    Thread(target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000))), daemon=True).start()

# ================== DB ==================
conn = sqlite3.connect("bot.db", check_same_thread=False)
cur = conn.cursor()

def init_db():
    cur.execute("CREATE TABLE IF NOT EXISTS money (uid INTEGER PRIMARY KEY, bal INTEGER)")
    cur.execute("CREATE TABLE IF NOT EXISTS warn (uid INTEGER PRIMARY KEY, cnt INTEGER)")
    cur.execute("CREATE TABLE IF NOT EXISTS channel_config (guild_id INTEGER PRIMARY KEY, welcome INTEGER, log INTEGER)")
    cur.execute("CREATE TABLE IF NOT EXISTS party (guild_id INTEGER, owner_id INTEGER, voice_id INTEGER)")
    cur.execute("CREATE TABLE IF NOT EXISTS party_config (guild_id INTEGER PRIMARY KEY, category_id INTEGER, voice_id INTEGER)")
    conn.commit()

# ================== UTIL ==================
def embed(t, d="", c=0x5865F2):
    e = discord.Embed(title=t, description=d, color=c)
    e.timestamp = datetime.datetime.utcnow()
    return e

# ================== ECONOMY ==================
def money(uid):
    cur.execute("SELECT bal FROM money WHERE uid=?", (uid,))
    r = cur.fetchone()
    return r[0] if r else 0

def add_money(uid, v):
    cur.execute("REPLACE INTO money VALUES (?,?)", (uid, money(uid)+v))
    conn.commit()

def sub_money(uid, v):
    cur.execute("REPLACE INTO money VALUES (?,?)", (uid, money(uid)-v))
    conn.commit()

# ================== WARN ==================
def warn(uid):
    cur.execute("SELECT cnt FROM warn WHERE uid=?", (uid,))
    r = cur.fetchone()
    return r[0] if r else 0

def add_warn(uid):
    c = warn(uid)+1
    cur.execute("REPLACE INTO warn VALUES (?,?)", (uid,c))
    conn.commit()
    return c

def clear_warn(uid):
    cur.execute("REPLACE INTO warn VALUES (?,0)", (uid,))
    conn.commit()

# ================== VERIFY ==================
class VerifyView(discord.ui.View):
    @discord.ui.button(label="✅ 인증하기", style=discord.ButtonStyle.success)
    async def verify(self, i, b):

        role = discord.utils.get(i.guild.roles, name="인증")
        if not role:
            role = await i.guild.create_role(name="인증")

        await i.user.add_roles(role)

        try:
            await i.user.send(embed=embed("인증 완료", "서버 인증 완료"))
        except:
            pass

        await i.response.send_message("인증 완료", ephemeral=True)

# ================== TICKET ==================
class TicketView(discord.ui.View):
    @discord.ui.button(label="🎟 티켓 생성", style=discord.ButtonStyle.primary)
    async def create(self, i, b):

        overwrites = {
            i.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            i.user: discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }

        ch = await i.guild.create_text_channel(
            name=f"ticket-{i.user.name}",
            overwrites=overwrites
        )

        await ch.send(embed=embed("티켓", "관리자에게 문의하세요"))

        await i.response.send_message("티켓 생성 완료", ephemeral=True)

# ================== PARTY ==================
class PartyView(discord.ui.View):
    @discord.ui.button(label="🎮 참가", style=discord.ButtonStyle.success)
    async def join(self, i, b):

        cur.execute("SELECT voice_id FROM party WHERE guild_id=? AND owner_id=?", (i.guild.id, i.user.id))
        r = cur.fetchone()

        if not r:
            return await i.response.send_message("파티 없음", ephemeral=True)

        vc = i.guild.get_channel(r[0])
        if vc:
            await i.user.move_to(vc)
            await i.response.send_message("참가 완료", ephemeral=True)

# ================== ADMIN PANEL ==================
class AdminPanel(discord.ui.View):

    @discord.ui.button(label="🎮 파티", style=discord.ButtonStyle.primary)
    async def p(self, i, b):
        await i.response.send_message("파티 관리 UI")

    @discord.ui.button(label="⚠ 경고", style=discord.ButtonStyle.danger)
    async def w(self, i, b):
        await i.response.send_message("경고 관리 UI")

    @discord.ui.button(label="🎟 티켓", style=discord.ButtonStyle.success)
    async def t(self, i, b):
        await i.response.send_message("티켓 관리 UI")

# ================== PARTY CREATE ==================
@bot.tree.command(name="파티생성")
async def party_create(i):

    vc = await i.guild.create_voice_channel(f"🎮 파티-{i.user.name}")

    cur.execute("INSERT INTO party VALUES (?,?,?)", (i.guild.id, i.user.id, vc.id))
    conn.commit()

    await i.response.send_message(f"파티 생성 {vc.mention}")

# ================== PARTY DELETE ==================
@bot.tree.command(name="파티삭제")
async def party_delete(i):

    cur.execute("SELECT voice_id FROM party WHERE guild_id=? AND owner_id=?", (i.guild.id, i.user.id))
    r = cur.fetchone()

    if not r:
        return await i.response.send_message("없음", ephemeral=True)

    vc = i.guild.get_channel(r[0])
    if vc:
        await vc.delete()

    cur.execute("DELETE FROM party WHERE guild_id=? AND owner_id=?", (i.guild.id, i.user.id))
    conn.commit()

    await i.response.send_message("삭제 완료")

# ================== PANEL COMMANDS ==================
@bot.tree.command(name="인증패널")
async def verify_panel(i):
    await i.response.send_message(embed=embed("인증 시스템"), view=VerifyView())

@bot.tree.command(name="티켓패널")
async def ticket_panel(i):
    await i.response.send_message(embed=embed("티켓 시스템"), view=TicketView())

@bot.tree.command(name="관리자패널")
async def admin_panel(i):
    if not i.user.guild_permissions.administrator:
        return await i.response.send_message("권한 없음", ephemeral=True)

    await i.response.send_message(embed=embed("관리자 패널"), view=AdminPanel())

# ================== ECONOMY ==================
@bot.tree.command(name="잔액")
async def bal(i, user: discord.Member=None):
    user=user or i.user
    await i.response.send_message(embed=embed("잔액", f"{user.mention}: {money(user.id)}원"))

@bot.tree.command(name="송금")
async def pay(i, user: discord.Member, amt:int):
    if money(i.user.id)<amt:
        return await i.response.send_message("부족",ephemeral=True)

    sub_money(i.user.id, amt)
    add_money(user.id, amt)

    await i.response.send_message("송금 완료")

# ================== WARN ==================
@bot.tree.command(name="경고")
async def warn_cmd(i, user: discord.Member):
    c = add_warn(user.id)
    await i.response.send_message(f"{user.mention} {c}회")

@bot.tree.command(name="경고삭제")
async def warn_clear(i, user: discord.Member):
    clear_warn(user.id)
    await i.response.send_message("삭제")

# ================== AUTO VOICE MOVE ==================
@bot.event
async def on_voice_state_update(member, before, after):

    cur.execute("SELECT voice_id FROM party WHERE guild_id=? AND owner_id=?", (member.guild.id, member.id))
    r = cur.fetchone()

    if r and after.channel:
        vc = member.guild.get_channel(r[0])
        if vc:
            await member.move_to(vc)

# ================== EVENTS ==================
@bot.event
async def on_ready():
    init_db()
    await bot.tree.sync()
    print("🔥 FULL ULTIMATE BOT READY")

# ================== RUN ==================
def start():
    keep_alive()
    bot.run(TOKEN)

start()
