# ================== IMPORT ==================
import discord
from discord.ext import commands
import os
import sqlite3
import datetime
import asyncio

# ================== BOT ==================
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ================== DB ==================
conn = sqlite3.connect("bot.db", check_same_thread=False)
cur = conn.cursor()

# ================== CONFIG TABLE ==================
cur.execute("""
CREATE TABLE IF NOT EXISTS guild_config (
    guild_id INTEGER PRIMARY KEY,
    admin_role_id INTEGER,
    welcome_channel INTEGER,
    log_channel INTEGER
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS party (
    guild_id INTEGER,
    owner_id INTEGER,
    voice_id INTEGER
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS warn (
    uid INTEGER PRIMARY KEY,
    cnt INTEGER
)
""")

conn.commit()

# ================== UTIL ==================
def embed(title, desc="", color=0x5865F2):
    e = discord.Embed(title=title, description=desc, color=color)
    e.timestamp = datetime.datetime.utcnow()
    return e

# ================== ADMIN SYSTEM ==================
def get_admin_role(gid):
    cur.execute("SELECT admin_role_id FROM guild_config WHERE guild_id=?", (gid,))
    r = cur.fetchone()
    return r[0] if r else None


def is_admin(i: discord.Interaction):
    if i.user.guild_permissions.administrator:
        return True
    role = get_admin_role(i.guild.id)
    return role and any(r.id == role for r in i.user.roles)

# ================== CHANNEL SYSTEM ==================
def set_channel(gid, key, val):
    cur.execute("INSERT OR IGNORE INTO guild_config (guild_id) VALUES (?)", (gid,))
    cur.execute(f"UPDATE guild_config SET {key}=? WHERE guild_id=?", (val, gid))
    conn.commit()

def get_channel(gid, key):
    cur.execute(f"SELECT {key} FROM guild_config WHERE guild_id=?", (gid,))
    r = cur.fetchone()
    return r[0] if r else None

# ================== ROLE SET ==================
@bot.tree.command(name="역할")
async def role_set(i: discord.Interaction, role: discord.Role):

    if not i.user.guild_permissions.administrator:
        return await i.response.send_message("❌ 관리자만 가능", ephemeral=True)

    cur.execute("REPLACE INTO guild_config (guild_id, admin_role_id) VALUES (?,?)",
                (i.guild.id, role.id))
    conn.commit()

    await i.response.send_message(embed=embed("관리자 역할 설정", f"{role.mention}"))

# ================== WELCOME ==================
@bot.event
async def on_member_join(member):

    ch_id = get_channel(member.guild.id, "welcome_channel")
    if ch_id:
        ch = bot.get_channel(ch_id)
        if ch:
            await ch.send(embed=embed("환영", member.mention))

# ================== LOG ==================
async def send_log(guild, msg):
    ch_id = get_channel(guild.id, "log_channel")
    if ch_id:
        ch = bot.get_channel(ch_id)
        if ch:
            await ch.send(embed=embed("LOG", msg))

# ================== CHANNEL COMMANDS ==================
@bot.tree.command(name="입장채널")
async def set_welcome(i, channel: discord.TextChannel):
    if not is_admin(i):
        return await i.response.send_message("❌ 권한 없음", ephemeral=True)

    set_channel(i.guild.id, "welcome_channel", channel.id)
    await i.response.send_message("입장 채널 설정 완료")

@bot.tree.command(name="로그채널")
async def set_log(i, channel: discord.TextChannel):
    if not is_admin(i):
        return await i.response.send_message("❌ 권한 없음", ephemeral=True)

    set_channel(i.guild.id, "log_channel", channel.id)
    await i.response.send_message("로그 채널 설정 완료")

# ================== WARNING ==================
def add_warn(uid):
    cur.execute("SELECT cnt FROM warn WHERE uid=?", (uid,))
    r = cur.fetchone()
    c = r[0] + 1 if r else 1
    cur.execute("REPLACE INTO warn VALUES (?,?)", (uid, c))
    conn.commit()
    return c

def get_warn(uid):
    cur.execute("SELECT cnt FROM warn WHERE uid=?", (uid,))
    r = cur.fetchone()
    return r[0] if r else 0

def clear_warn(uid):
    cur.execute("REPLACE INTO warn VALUES (?,0)", (uid,))
    conn.commit()

@bot.tree.command(name="경고")
async def warn(i, user: discord.Member):
    if not is_admin(i):
        return await i.response.send_message("❌ 권한 없음", ephemeral=True)

    c = add_warn(user.id)
    await i.response.send_message(embed=embed("경고", f"{user.mention} {c}회"))

@bot.tree.command(name="경고확인")
async def warn_check(i, user: discord.Member):
    await i.response.send_message(embed=embed("경고", f"{user.mention} {get_warn(user.id)}회"))

@bot.tree.command(name="경고삭제")
async def warn_clear(i, user: discord.Member):
    if not is_admin(i):
        return await i.response.send_message("❌ 권한 없음", ephemeral=True)

    clear_warn(user.id)
    await i.response.send_message("초기화 완료")

# ================== VERIFY ==================
class Verify(discord.ui.View):
    @discord.ui.button(label="인증", style=discord.ButtonStyle.green)
    async def v(self, i, b):
        role = discord.utils.get(i.guild.roles, name="인증")
        if not role:
            role = await i.guild.create_role(name="인증")

        await i.user.add_roles(role)

        try:
            await i.user.send("인증 완료")
        except:
            pass

        await i.response.send_message("완료", ephemeral=True)

@bot.tree.command(name="인증패널")
async def verify_panel(i):
    await i.response.send_message(embed=embed("인증"), view=Verify())

# ================== TICKET ==================
class Ticket(discord.ui.View):
    @discord.ui.button(label="티켓 생성", style=discord.ButtonStyle.primary)
    async def t(self, i, b):
        ch = await i.guild.create_text_channel(f"ticket-{i.user.name}")
        await ch.send(i.user.mention)
        await i.response.send_message("생성됨", ephemeral=True)

@bot.tree.command(name="티켓패널")
async def ticket_panel(i):
    if not is_admin(i):
        return await i.response.send_message("❌ 권한 없음", ephemeral=True)

    await i.response.send_message(embed=embed("티켓"), view=Ticket())

# ================== PARTY ==================
@bot.tree.command(name="파티생성")
async def party_create(i):

    vc = await i.guild.create_voice_channel(f"🎮 파티-{i.user.name}")

    cur.execute("INSERT INTO party VALUES (?,?,?)",
                (i.guild.id, i.user.id, vc.id))
    conn.commit()

    await i.response.send_message(f"파티 생성: {vc.mention}")

@bot.tree.command(name="파티삭제")
async def party_delete(i):

    cur.execute("SELECT voice_id FROM party WHERE guild_id=? AND owner_id=?",
                (i.guild.id, i.user.id))
    r = cur.fetchone()

    if not r:
        return await i.response.send_message("없음", ephemeral=True)

    ch = i.guild.get_channel(r[0])
    if ch:
        await ch.delete()

    cur.execute("DELETE FROM party WHERE guild_id=? AND owner_id=?",
                (i.guild.id, i.user.id))
    conn.commit()

    await i.response.send_message("삭제 완료")

class PartyView(discord.ui.View):
    @discord.ui.button(label="참가", style=discord.ButtonStyle.success)
    async def join(self, i, b):

        cur.execute("SELECT voice_id FROM party WHERE guild_id=? AND owner_id=?",
                    (i.guild.id, i.user.id))
        r = cur.fetchone()

        if not r:
            return await i.response.send_message("파티 없음", ephemeral=True)

        vc = i.guild.get_channel(r[0])
        if vc:
            await i.user.move_to(vc)

        await i.response.send_message("참가 완료", ephemeral=True)

# ================== READY ==================
@bot.event
async def on_ready():
    await bot.tree.sync()
    print("🔥 QUABOT FINAL FULL VERSION READY")

# ================== RUN ==================
bot.run(os.getenv("TOKEN"))
