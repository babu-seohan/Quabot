import discord
from discord.ext import commands
import os, sqlite3, datetime, asyncio, random
from flask import Flask
from threading import Thread

# ================== 기본 설정 ==================
TOKEN = os.getenv("TOKEN")
DB_PATH = "bot.db"

app = Flask(__name__)

@app.route("/")
def home():
    return "BOT ONLINE"

def keep_alive():
    Thread(target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000))), daemon=True).start()

# ================== DB ==================
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()

def init_db():
    cursor.execute("CREATE TABLE IF NOT EXISTS money (user_id INTEGER PRIMARY KEY, balance INTEGER)")
    cursor.execute("CREATE TABLE IF NOT EXISTS warnings (user_id INTEGER PRIMARY KEY, count INTEGER)")
    cursor.execute("CREATE TABLE IF NOT EXISTS attendance (user_id INTEGER PRIMARY KEY, last TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS config (guild_id INTEGER PRIMARY KEY, log_channel INTEGER, welcome_channel INTEGER)")
    conn.commit()

# ================== 봇 ==================
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

def embed(t, d="", c=0x5865F2):
    e = discord.Embed(title=t, description=d, color=c)
    e.timestamp = datetime.datetime.utcnow()
    return e

# ================== 돈 ==================
def get_money(uid):
    cursor.execute("SELECT balance FROM money WHERE user_id=?", (uid,))
    r = cursor.fetchone()
    return r[0] if r else 0

def add_money(uid, amt):
    b = get_money(uid) + amt
    cursor.execute("REPLACE INTO money VALUES(?,?)", (uid, b))
    conn.commit()
    return b

def remove_money(uid, amt):
    b = max(get_money(uid) - amt, 0)
    cursor.execute("REPLACE INTO money VALUES(?,?)", (uid, b))
    conn.commit()
    return b

# ================== 로그 ==================
async def send_log(guild, msg):
    cursor.execute("SELECT log_channel FROM config WHERE guild_id=?", (guild.id,))
    r = cursor.fetchone()
    if r and r[0]:
        ch = guild.get_channel(r[0])
        if ch:
            await ch.send(msg)

# ================== 경고 ==================
def get_warn(uid):
    cursor.execute("SELECT count FROM warnings WHERE user_id=?", (uid,))
    r = cursor.fetchone()
    return r[0] if r else 0

def add_warn(uid):
    c = get_warn(uid) + 1
    cursor.execute("REPLACE INTO warnings VALUES(?,?)", (uid, c))
    conn.commit()
    return c

def clear_warn(uid):
    cursor.execute("REPLACE INTO warnings VALUES(?,?)", (uid, 0))
    conn.commit()

# ================== 이벤트 ==================
@bot.event
async def on_ready():
    init_db()
    print(f"🔥 READY {bot.user}")

@bot.event
async def on_member_join(member):
    cursor.execute("SELECT welcome_channel FROM config WHERE guild_id=?", (member.guild.id,))
    r = cursor.fetchone()
    if r and r[0]:
        ch = member.guild.get_channel(r[0])
        if ch:
            await ch.send(embed=embed("환영", f"{member.mention} 어서와!"))

# ================== 채널 설정 ==================
@bot.tree.command(name="채널설정")
async def channel_set(i: discord.Interaction, 로그채널: discord.TextChannel=None, 환영채널: discord.TextChannel=None):
    cursor.execute("REPLACE INTO config VALUES(?,?,?)",
                   (i.guild.id,
                    로그채널.id if 로그채널 else None,
                    환영채널.id if 환영채널 else None))
    conn.commit()
    await i.response.send_message(embed=embed("채널 설정 완료"))

# ================== 경제 ==================
@bot.tree.command(name="잔액")
async def balance(i: discord.Interaction, 유저: discord.Member=None):
    user = 유저 or i.user
    await i.response.send_message(embed=embed("잔액", f"{user.mention}: {get_money(user.id):,}원"))

@bot.tree.command(name="송금")
async def transfer(i: discord.Interaction, 유저: discord.Member, 금액: int):
    if 금액 <= 0:
        return await i.response.send_message("❌ 금액 오류", ephemeral=True)

    if get_money(i.user.id) < 금액:
        return await i.response.send_message("❌ 돈 부족", ephemeral=True)

    remove_money(i.user.id, 금액)
    add_money(유저.id, 금액)

    await i.response.send_message(embed=embed("송금 완료", f"{유저.mention}에게 {금액:,}원"))
    await send_log(i.guild, f"💸 {i.user} → {유저} : {금액}")

@bot.tree.command(name="출석")
async def attendance(i: discord.Interaction):
    today = str(datetime.date.today())
    cursor.execute("SELECT last FROM attendance WHERE user_id=?", (i.user.id,))
    r = cursor.fetchone()

    if r and r[0] == today:
        return await i.response.send_message("이미 출석함", ephemeral=True)

    cursor.execute("REPLACE INTO attendance VALUES(?,?)", (i.user.id, today))
    conn.commit()

    add_money(i.user.id, 500000)
    await i.response.send_message(embed=embed("출석", "500,000원 지급"))

# ================== 게임 ==================
@bot.tree.command(name="홀짝")
async def odd_even(i: discord.Interaction, 금액:int):
    num = random.randint(1,100)
    result = "홀수" if num%2 else "짝수"

    win = random.choice(["홀수","짝수"])

    if win == result:
        add_money(i.user.id, 금액*2)
        msg = "승리"
    else:
        msg = "실패(손해없음)"

    await i.response.send_message(embed=embed("홀짝", f"{num} → {result}\n{msg}"))

# ================== 주사위 ==================
@bot.tree.command(name="주사위")
async def dice(i: discord.Interaction):
    n = random.randint(1,6)
    if n == 6:
        add_money(i.user.id, 150000)
        msg="당첨"
    else:
        remove_money(i.user.id, 50000)
        msg="실패"

    await i.response.send_message(embed=embed("주사위", f"{n} → {msg}"))

# ================== 경고 ==================
@bot.tree.command(name="경고")
async def warn(i: discord.Interaction, 유저: discord.Member):
    c = add_warn(유저.id)
    await i.response.send_message(embed=embed("경고", f"{유저.mention} {c}회"))
    await send_log(i.guild, f"⚠️ {유저} 경고 {c}")

@bot.tree.command(name="경고확인")
async def warn_check(i: discord.Interaction, 유저: discord.Member):
    await i.response.send_message(embed=embed("경고", f"{유저.mention}: {get_warn(유저.id)}회"))

@bot.tree.command(name="경고삭제")
async def warn_clear_cmd(i: discord.Interaction, 유저: discord.Member):
    clear_warn(유저.id)
    await i.response.send_message("초기화 완료")

# ================== 티켓 ==================
class TicketView(discord.ui.View):
    @discord.ui.button(label="티켓 생성", style=discord.ButtonStyle.primary)
    async def create(self, i: discord.Interaction, b):
        ch = await i.guild.create_text_channel(f"ticket-{i.user.name}")
        await ch.send(i.user.mention)
        await i.response.send_message("생성됨", ephemeral=True)

@bot.tree.command(name="티켓패널")
async def ticket_panel(i: discord.Interaction):
    await i.response.send_message("티켓", view=TicketView())

# ================== 인증 ==================
class VerifyView(discord.ui.View):
    @discord.ui.button(label="인증", style=discord.ButtonStyle.success)
    async def verify(self, i: discord.Interaction, b):
        role = discord.utils.get(i.guild.roles, name="인증")
        if not role:
            role = await i.guild.create_role(name="인증")
        await i.user.add_roles(role)
        await i.response.send_message("완료", ephemeral=True)

@bot.tree.command(name="인증패널")
async def verify_panel(i: discord.Interaction):
    await i.response.send_message("인증", view=VerifyView())

# ================== 실행 ==================
async def main():
    keep_alive()
    await bot.start(TOKEN)

asyncio.run(main())
