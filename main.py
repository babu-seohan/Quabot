# ================= 기본 =================
import discord
from discord.ext import commands
import os, sqlite3, datetime, random, asyncio
from flask import Flask
from threading import Thread

TOKEN = os.getenv("TOKEN")

DB_PATH = "bot.db"

# ================= 서버 유지 =================
app = Flask(__name__)
@app.route("/")
def home(): return "BOT ONLINE"

def run(): app.run(host="0.0.0.0", port=10000)
def keep_alive(): Thread(target=run).start()

# ================= DB =================
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()

def init_db():
    cursor.execute("CREATE TABLE IF NOT EXISTS money (id INTEGER PRIMARY KEY, bal INTEGER)")
    cursor.execute("CREATE TABLE IF NOT EXISTS warn (id INTEGER PRIMARY KEY, cnt INTEGER)")
    cursor.execute("CREATE TABLE IF NOT EXISTS config (guild_id INTEGER PRIMARY KEY, log INTEGER, welcome INTEGER)")
    conn.commit()

# ================= 유틸 =================
def embed(t,d="",c=0x5865F2):
    e=discord.Embed(title=t,description=d,color=c)
    e.timestamp=datetime.datetime.utcnow()
    return e

def get_config(guild_id):
    cursor.execute("SELECT log, welcome FROM config WHERE guild_id=?", (guild_id,))
    r = cursor.fetchone()
    return r if r else (None, None)

def set_config(guild_id, log=None, welcome=None):
    cur_log, cur_wel = get_config(guild_id)

    log = log if log is not None else cur_log
    welcome = welcome if welcome is not None else cur_wel

    cursor.execute("REPLACE INTO config VALUES (?,?,?)", (guild_id, log, welcome))
    conn.commit()

def log(bot, guild_id, text):
    log_id, _ = get_config(guild_id)
    if log_id:
        ch = bot.get_channel(log_id)
        if ch:
            asyncio.create_task(ch.send(text))

# ================= 봇 =================
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

def is_admin(member):
    return member.guild_permissions.administrator

# ================= 이벤트 =================
@bot.event
async def on_ready():
    init_db()
    await bot.tree.sync()
    print("READY")

@bot.event
async def on_member_join(m):
    _, welcome_id = get_config(m.guild.id)
    if welcome_id:
        ch = bot.get_channel(welcome_id)
        if ch:
            await ch.send(embed=embed("🎉 환영", m.mention))

    log(bot, m.guild.id, f"👋 입장: {m}")

# ================= 채널 설정 (추가됨) =================

@bot.tree.command(name="채널로그", description="로그 채널 설정")
async def set_log_channel(i: discord.Interaction, 채널: discord.TextChannel):
    if not is_admin(i.user):
        return await i.response.send_message("❌ 권한 없음", ephemeral=True)

    set_config(i.guild.id, log=채널.id)

    await i.response.send_message(
        embed=embed("✅ 설정 완료", f"로그 채널 → {채널.mention}")
    )

@bot.tree.command(name="채널입장", description="입장 채널 설정")
async def set_welcome_channel(i: discord.Interaction, 채널: discord.TextChannel):
    if not is_admin(i.user):
        return await i.response.send_message("❌ 권한 없음", ephemeral=True)

    set_config(i.guild.id, welcome=채널.id)

    await i.response.send_message(
        embed=embed("✅ 설정 완료", f"입장 채널 → {채널.mention}")
    )

@bot.tree.command(name="채널전체설정", description="로그 + 입장 채널 한번에 설정")
async def set_all(i: discord.Interaction, 로그채널: discord.TextChannel, 입장채널: discord.TextChannel):
    if not is_admin(i.user):
        return await i.response.send_message("❌ 권한 없음", ephemeral=True)

    set_config(i.guild.id, log=로그채널.id, welcome=입장채널.id)

    await i.response.send_message(
        embed=embed("🔥 전체 설정 완료",
                    f"로그: {로그채널.mention}\n입장: {입장채널.mention}")
    )

# ================= 테스트용 기본 명령 =================

@bot.tree.command(name="핑")
async def ping(i:discord.Interaction):
    await i.response.send_message("🏓 Pong!")

# ================= 실행 =================
async def main():
    keep_alive()
    await bot.start(TOKEN)

asyncio.run(main())
