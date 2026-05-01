import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button, Modal, TextInput
import datetime, os, sqlite3, asyncio
from flask import Flask
from threading import Thread

# ================= KEEP ALIVE =================
app = Flask(__name__)
@app.route("/")
def home():
    return "alive", 200

def keep_alive():
    Thread(target=lambda: app.run(host="0.0.0.0", port=10000), daemon=True).start()

# ================= DB =================
conn = sqlite3.connect("bot.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("CREATE TABLE IF NOT EXISTS warnings (user_id INTEGER PRIMARY KEY, count INTEGER)")
cursor.execute("CREATE TABLE IF NOT EXISTS levels (user_id INTEGER PRIMARY KEY, xp INTEGER, level INTEGER)")
cursor.execute("CREATE TABLE IF NOT EXISTS tickets (channel_id INTEGER, user_id INTEGER)")
conn.commit()

# ================= 설정 =================
TOKEN = os.getenv("TOKEN")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")

WELCOME_CHANNEL_ID = 0
LOG_CHANNEL_ID = 0
TICKET_CATEGORY_ID = 0
VERIFY_ROLE_ID = 0

# ================= 봇 =================
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ================= 유틸 =================
def embed(t, d="", c=0x5865F2):
    e = discord.Embed(title=t, description=d, color=c)
    e.timestamp = datetime.datetime.utcnow()
    return e

async def log(msg):
    ch = bot.get_channel(LOG_CHANNEL_ID)
    if ch:
        await ch.send(embed=embed("📜 로그", msg))

# ================= 경고 =================
def get_warn(uid):
    cursor.execute("SELECT count FROM warnings WHERE user_id=?", (uid,))
    r = cursor.fetchone()
    return r[0] if r else 0

def set_warn(uid, count):
    cursor.execute("REPLACE INTO warnings VALUES(?,?)", (uid, count))
    conn.commit()

def add_warn(uid):
    c = get_warn(uid)+1
    set_warn(uid,c)
    return c

async def auto_punish(m,c):
    try:
        if c==1: await m.timeout(datetime.timedelta(minutes=10)); return "10분"
        if c==2: await m.timeout(datetime.timedelta(hours=1)); return "1시간"
        if c==3: await m.timeout(datetime.timedelta(days=1)); return "1일"
        if c==4: await m.kick(); return "킥"
        if c==5: await m.ban(); return "밴"
    except Exception as e:
        return str(e)

# ================= 레벨 =================
def get_level(uid):
    cursor.execute("SELECT xp,level FROM levels WHERE user_id=?", (uid,))
    r = cursor.fetchone()
    if not r:
        cursor.execute("INSERT INTO levels VALUES(?,?,?)",(uid,0,1))
        conn.commit()
        return 0,1
    return r

def add_xp(uid,amount):
    xp,lv = get_level(uid)
    xp += amount
    if xp >= lv*100:
        xp = 0
        lv += 1
        leveled = True
    else:
        leveled = False
    cursor.execute("REPLACE INTO levels VALUES(?,?,?)",(uid,xp,lv))
    conn.commit()
    return xp,lv,leveled

# ================= 티켓 =================
class CloseTicket(View):
    @discord.ui.button(label="🔒 닫기", style=discord.ButtonStyle.danger)
    async def close(self,i,b):
        await i.response.send_message("삭제중...")
        await asyncio.sleep(5)
        await i.channel.delete()

class TicketModal(Modal,title="티켓"):
    title_input = TextInput(label="제목")
    async def on_submit(self,i):
        g=i.guild
        c=g.get_channel(TICKET_CATEGORY_ID)
        ch=await g.create_text_channel(name=f"ticket-{i.user.id}",category=c)
        await ch.send(i.user.mention,view=CloseTicket())
        await i.response.send_message(ch.mention,ephemeral=True)

class TicketView(View):
    @discord.ui.button(label="티켓",style=discord.ButtonStyle.blurple)
    async def t(self,i,b):
        await i.response.send_modal(TicketModal())

# ================= 인증 =================
class Verify(View):
    @discord.ui.button(label="인증",style=discord.ButtonStyle.green)
    async def v(self,i,b):
        role=i.guild.get_role(VERIFY_ROLE_ID)
        await i.user.add_roles(role)
        await i.response.send_message("완료",ephemeral=True)

# ================= 명령어 =================
@bot.tree.command(name="경고")
async def warn(i,user:discord.Member,이유:str):
    c=add_warn(user.id)
    r=await auto_punish(user,c)
    msg=f"{user.mention} {c}회\n{이유}"
    if r: msg+=f"\n처벌:{r}"
    await i.response.send_message(embed=embed("경고",msg))

@bot.tree.command(name="경고취소")
async def unwarn(i,user:discord.Member):
    c=get_warn(user.id)
    if c==0:
        return await i.response.send_message("없음",ephemeral=True)
    set_warn(user.id,c-1)
    await i.response.send_message(embed=embed("취소",f"{c-1}회"))

@bot.tree.command(name="경고확인")
async def check_warn(i,user:discord.Member):
    c=get_warn(user.id)
    await i.response.send_message(embed=embed("경고 확인",f"{user.mention}: {c}회"))

@bot.command()
async def 레벨(ctx):
    xp,lv=get_level(ctx.author.id)
    await ctx.send(embed=embed("레벨",f"Lv.{lv} | XP:{xp}/{lv*100}"))

@bot.tree.command(name="티켓패널")
async def tp(i):
    await i.response.send_message(view=TicketView())

@bot.command()
async def 인증패널(ctx):
    await ctx.send(view=Verify())

# ================= 이벤트 =================
@bot.event
async def on_member_join(m):
    ch=bot.get_channel(WELCOME_CHANNEL_ID)
    if ch:
        await ch.send(embed=embed("환영",m.mention))

@bot.event
async def on_message(m):
    if m.author.bot: return

    # 레벨
    xp,lv,up = add_xp(m.author.id,10)
    if up:
        await m.channel.send(f"🎉 {m.author.mention} 레벨업! Lv.{lv}")

    await bot.process_commands(m)

# ================= 실행 =================
@bot.event
async def on_ready():
    await bot.tree.sync()
    print("완료")

keep_alive()
bot.run(TOKEN)
