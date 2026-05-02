# ================= 기본 =================
import discord
from discord.ext import commands
import os, sqlite3, datetime, asyncio, random
from flask import Flask
from threading import Thread

TOKEN = os.getenv("TOKEN")

# ================= 설정 =================
WELCOME_CHANNEL_ID = 0
LOG_CHANNEL_ID = 0
TICKET_CATEGORY_ID = 0
VERIFY_ROLE_ID = 0

DB_PATH = "bot.db"

SALARY = 100000
ATTENDANCE = 500000
MAX_BET = 1000000
DICE_COST = 50000
DICE_WIN = DICE_COST * 3

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
    cursor.execute("CREATE TABLE IF NOT EXISTS attendance (id INTEGER PRIMARY KEY, date TEXT)")
    conn.commit()

# ================= 유틸 =================
def embed(t, d="", c=0x5865F2):
    e = discord.Embed(title=t, description=d, color=c)
    e.timestamp = datetime.datetime.utcnow()
    return e

def money(uid):
    cursor.execute("SELECT bal FROM money WHERE id=?", (uid,))
    r = cursor.fetchone()
    return r[0] if r else 0

def set_money(uid, v):
    cursor.execute("REPLACE INTO money VALUES (?,?)", (uid, max(v,0)))
    conn.commit()

def add_money(uid, v): set_money(uid, money(uid)+v)
def rm_money(uid, v): set_money(uid, money(uid)-v)

def warn(uid):
    cursor.execute("SELECT cnt FROM warn WHERE id=?", (uid,))
    r = cursor.fetchone()
    return r[0] if r else 0

def add_warn(uid):
    c = warn(uid)+1
    cursor.execute("REPLACE INTO warn VALUES (?,?)", (uid,c))
    conn.commit()
    return c

def clear_warn(uid):
    cursor.execute("REPLACE INTO warn VALUES (?,0)", (uid,))
    conn.commit()

def today(): return (datetime.datetime.utcnow()+datetime.timedelta(hours=9)).strftime("%Y-%m-%d")

# ================= 봇 =================
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ================= 이벤트 =================
@bot.event
async def on_ready():
    init_db()
    await bot.tree.sync()
    print("READY")

@bot.event
async def on_member_join(m):
    ch = bot.get_channel(WELCOME_CHANNEL_ID)
    if ch:
        await ch.send(embed=embed("환영", m.mention))

# ================= 경제 =================
@bot.tree.command(name="잔액")
async def bal(i:discord.Interaction, user:discord.Member):
    await i.response.send_message(embed=embed("잔액", f"{user.mention}: {money(user.id):,}원"))

@bot.tree.command(name="월급")
async def salary(i:discord.Interaction):
    add_money(i.user.id, SALARY)
    await i.response.send_message(embed=embed("월급", f"+{SALARY:,}원"))

@bot.tree.command(name="출석")
async def att(i:discord.Interaction):
    if today()==cursor.execute("SELECT date FROM attendance WHERE id=?", (i.user.id,)).fetchone():
        return await i.response.send_message("이미 출석")
    cursor.execute("REPLACE INTO attendance VALUES (?,?)",(i.user.id,today()))
    conn.commit()
    add_money(i.user.id, ATTENDANCE)
    await i.response.send_message(embed=embed("출석", f"+{ATTENDANCE:,}원"))

@bot.tree.command(name="송금")
async def send(i:discord.Interaction, user:discord.Member, 금액:int):
    if money(i.user.id)<금액: return await i.response.send_message("잔액 부족")
    rm_money(i.user.id, 금액)
    add_money(user.id, 금액)
    await i.response.send_message(embed=embed("송금", f"{i.user.mention}→{user.mention} {금액:,}원"))

# ================= 게임 =================
@bot.tree.command(name="홀짝")
async def odd_even(i:discord.Interaction, 금액:int):
    n=random.randint(1,100)
    res="홀수" if n%2 else "짝수"
    add_money(i.user.id, 금액)
    await i.response.send_message(embed=embed("결과", f"{n} → {res}"))

@bot.tree.command(name="주사위")
async def dice(i:discord.Interaction):
    if money(i.user.id)<DICE_COST: return await i.response.send_message("돈 부족")
    n=random.randint(1,6)
    if n==6:
        add_money(i.user.id, DICE_WIN)
        msg="당첨"
    else:
        rm_money(i.user.id, DICE_COST)
        msg="실패"
    await i.response.send_message(embed=embed("주사위", f"{n} → {msg}"))

# ================= 경고 =================
@bot.tree.command(name="경고")
async def warn_cmd(i:discord.Interaction, user:discord.Member):
    c=add_warn(user.id)
    await i.response.send_message(embed=embed("경고", f"{user.mention}: {c}회"))

@bot.tree.command(name="경고삭제")
async def warn_clear_cmd(i:discord.Interaction, user:discord.Member):
    clear_warn(user.id)
    await i.response.send_message("초기화 완료")

@bot.tree.command(name="경고확인")
async def warn_check(i:discord.Interaction, user:discord.Member):
    await i.response.send_message(embed=embed("경고", f"{user.mention}: {warn(user.id)}회"))

# ================= 티켓 =================
class TicketView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)

    @discord.ui.button(label="티켓 생성")
    async def create(self,i,b):
        cat=i.guild.get_channel(TICKET_CATEGORY_ID)
        ch=await i.guild.create_text_channel(f"ticket-{i.user.id}",category=cat)
        await ch.send(i.user.mention)
        await i.response.send_message("생성",ephemeral=True)

@bot.tree.command(name="티켓패널")
async def ticket_panel(i:discord.Interaction):
    await i.response.send_message("티켓", view=TicketView())

# ================= 인증 =================
class VerifyView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)

    @discord.ui.button(label="인증")
    async def verify(self,i,b):
        role=i.guild.get_role(VERIFY_ROLE_ID)
        await i.user.add_roles(role)
        await i.response.send_message("인증 완료",ephemeral=True)

@bot.tree.command(name="인증패널")
async def verify_panel(i:discord.Interaction):
    await i.response.send_message("인증", view=VerifyView())

# ================= 실행 =================
async def main():
    keep_alive()
    await bot.start(TOKEN)

asyncio.run(main())
