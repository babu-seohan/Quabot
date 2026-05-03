import asyncio
import datetime
import os
import random
import sqlite3
from threading import Thread

import discord
from discord.ext import commands
from flask import Flask

TOKEN = os.getenv("TOKEN")

SALARY_AMOUNT = 100000
SALARY_COOLDOWN = 10
ATTENDANCE_AMOUNT = 500000

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)
bot_ready_synced = False
salary_cd = {}

app = Flask(__name__)


@app.route("/")
def home():
    return "BOT ONLINE", 200


@app.route("/health")
def health():
    return "OK", 200


def keep_alive():
    port = int(os.environ.get("PORT", 10000))
    Thread(
        target=lambda: app.run(host="0.0.0.0", port=port, use_reloader=False),
        daemon=True,
    ).start()


conn = sqlite3.connect("bot.db", check_same_thread=False)
cur = conn.cursor()


def init_db():
    cur.execute("CREATE TABLE IF NOT EXISTS money (uid INTEGER PRIMARY KEY, bal INTEGER DEFAULT 0)")
    cur.execute("CREATE TABLE IF NOT EXISTS attendance (uid INTEGER PRIMARY KEY, date TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS warn (uid INTEGER PRIMARY KEY, cnt INTEGER DEFAULT 0)")
    cur.execute(
        """CREATE TABLE IF NOT EXISTS party (
        guild_id INTEGER,
        owner_id INTEGER,
        voice_id INTEGER,
        PRIMARY KEY (guild_id, owner_id)
    )"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS guild_config (
        guild_id INTEGER PRIMARY KEY,
        verify_role INTEGER,
        admin_role INTEGER,
        welcome_ch INTEGER,
        log_ch INTEGER,
        levelup_ch INTEGER,
        party_cat INTEGER
    )"""
    )
    for col in ["levelup_ch INTEGER", "party_cat INTEGER"]:
        try:
            cur.execute(f"ALTER TABLE guild_config ADD COLUMN {col}")
        except Exception:
            pass
    cur.execute(
        """CREATE TABLE IF NOT EXISTS sticky (
        channel_id INTEGER PRIMARY KEY,
        guild_id INTEGER,
        content TEXT,
        message_id INTEGER
    )"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS levels (
        guild_id INTEGER,
        uid INTEGER,
        xp INTEGER DEFAULT 0,
        lv INTEGER DEFAULT 0,
        last_msg INTEGER DEFAULT 0,
        PRIMARY KEY (guild_id, uid)
    )"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS voice_track (
        guild_id INTEGER,
        uid INTEGER,
        joined_at INTEGER,
        PRIMARY KEY (guild_id, uid)
    )"""
    )
    conn.commit()


def base_embed(title, desc="", color=0x5865F2, footer=None, icon=None):
    e = discord.Embed(title=title, description=desc, color=color)
    e.timestamp = datetime.datetime.utcnow()
    if footer:
        e.set_footer(text=footer, icon_url=icon)
    return e


def success_embed(title, desc=""):
    return base_embed(f"��  {title}", desc, 0x57F287, "�깃났")


def error_embed(title, desc=""):
    return base_embed(f"��  {title}", desc, 0xED4245, "�ㅻ쪟")


def info_embed(title, desc=""):
    return base_embed(f"�뱄툘  {title}", desc, 0x5865F2)


def warn_embed(title, desc=""):
    return base_embed(f"�좑툘  {title}", desc, 0xFEE75C, "寃쎄퀬")


def command_list_embed(guild: discord.Guild):
    e = discord.Embed(
        title="�뱰 紐낅졊�� 紐⑸줉",
        description="�щ옒��(`/`) 紐낅졊�댁� �띿뒪��(`!`) 紐낅졊�대� 紐⑤몢 吏��먰빀�덈떎.",
        color=0x5865F2,
        timestamp=datetime.datetime.utcnow(),
    )
    e.add_field(
        name="�숋툘 �ㅼ젙/�⑤꼸",
        value=(
            "`/��븷` `!��븷 @�몄쬆��븷 @愿�由ъ옄��븷`\n"
            "`/梨꾨꼸�ㅼ젙` `!梨꾨꼸�ㅼ젙 #�낆옣 #濡쒓렇 #�덈꺼�� 移댄뀒怨좊━`\n"
            "`/�몄쬆�⑤꼸` `!�몄쬆�⑤꼸`\n"
            "`/�곗폆�⑤꼸` `!�곗폆�⑤꼸`\n"
            "`/愿�由ъ옄�⑤꼸` `!愿�由ъ옄�⑤꼸`"
        ),
        inline=False,
    )
    e.add_field(
        name="�㏏ 愿�由�",
        value=(
            "`/泥�냼 媛쒖닔` `!泥�냼 媛쒖닔`\n"
            "`/寃쎄퀬 @�좎�` `!寃쎄퀬 @�좎�`\n"
            "`/寃쎄퀬��젣 @�좎�` `!寃쎄퀬��젣 @�좎�`\n"
            "`/寃쎄퀬�뺤씤 [�좎�]` `!寃쎄퀬�뺤씤 [�좎�]`"
        ),
        inline=False,
    )
    e.add_field(
        name="�뮥 寃쎌젣/寃뚯엫",
        value=(
            "`/�붿븸 [�좎�]` `!�붿븸 [�좎�]`\n"
            "`/�↔툑 @�좎� 湲덉븸` `!�↔툑 @�좎� 湲덉븸`\n"
            "`/�붽툒` `!�붽툒`\n"
            "`/異쒖꽍` `!異쒖꽍`\n"
            "`/��吏� �좏깮 湲덉븸` `!��吏� �� 10000`"
        ),
        inline=False,
    )
    e.add_field(
        name="狩� �덈꺼",
        value="`/�덈꺼 [�좎�]` `!�덈꺼 [�좎�]`\n`/�쒖쐞` `!�쒖쐞`",
        inline=False,
    )
    e.add_field(
        name="�렜 �뚰떚/�ㅽ떚��",
        value=(
            "`/�뚰떚�앹꽦` `!�뚰떚�앹꽦`\n"
            "`/�뚰떚��젣` `!�뚰떚��젣`\n"
            "`/�ㅽ떚�� �댁슜` `!�ㅽ떚�� �댁슜`\n"
            "`/�ㅽ떚�ㅽ빐��` `!�ㅽ떚�ㅽ빐��`"
        ),
        inline=False,
    )
    e.add_field(name="�뱴 �꾩�", value="`/紐낅졊�대ぉ濡�` `!紐낅졊�대ぉ濡�` `!�꾩�留�`", inline=False)
    if guild:
        e.set_footer(text=guild.name, icon_url=guild.icon.url if guild.icon else None)
    return e


def get_cfg(guild_id: int) -> dict:
    cur.execute(
        """SELECT verify_role, admin_role, welcome_ch, log_ch, levelup_ch, party_cat
        FROM guild_config WHERE guild_id=?""",
        (guild_id,),
    )
    row = cur.fetchone()
    keys = ["verify_role", "admin_role", "welcome_ch", "log_ch", "levelup_ch", "party_cat"]
    return dict(zip(keys, row)) if row else {key: None for key in keys}


def set_cfg(guild_id: int, **kwargs):
    cfg = get_cfg(guild_id)
    cfg.update({key: value for key, value in kwargs.items() if key in cfg})
    cur.execute(
        """INSERT INTO guild_config
        (guild_id, verify_role, admin_role, welcome_ch, log_ch, levelup_ch, party_cat)
        VALUES (?,?,?,?,?,?,?)
        ON CONFLICT(guild_id) DO UPDATE SET
        verify_role=excluded.verify_role,
        admin_role=excluded.admin_role,
        welcome_ch=excluded.welcome_ch,
        log_ch=excluded.log_ch,
        levelup_ch=excluded.levelup_ch,
        party_cat=excluded.party_cat""",
        (
            guild_id,
            cfg["verify_role"],
            cfg["admin_role"],
            cfg["welcome_ch"],
            cfg["log_ch"],
            cfg["levelup_ch"],
            cfg["party_cat"],
        ),
    )
    conn.commit()


def check_perm(guild: discord.Guild, user: discord.Member) -> bool:
    if user.id == guild.owner_id:
        return True
    if user.guild_permissions.administrator:
        return True
    cfg = get_cfg(guild.id)
    if cfg["admin_role"]:
        role = guild.get_role(cfg["admin_role"])
        return bool(role and role in user.roles)
    return False


def is_admin(interaction: discord.Interaction) -> bool:
    return interaction.guild and check_perm(interaction.guild, interaction.user)


def is_admin_ctx(ctx: commands.Context) -> bool:
    return ctx.guild and check_perm(ctx.guild, ctx.author)


async def deny(interaction: discord.Interaction):
    await interaction.response.send_message(
        embed=error_embed("沅뚰븳 �놁쓬", "�쒕쾭 �뚯쑀�� �먮뒗 遊� 愿�由ъ옄 ��븷�� �꾩슂�⑸땲��."),
        ephemeral=True,
    )


async def send_log(guild: discord.Guild, embeds: list):
    cfg = get_cfg(guild.id)
    if not cfg["log_ch"]:
        return
    channel = guild.get_channel(cfg["log_ch"])
    if channel:
        try:
            await channel.send(embeds=embeds)
        except Exception:
            pass


def money(uid):
    cur.execute("SELECT bal FROM money WHERE uid=?", (uid,))
    row = cur.fetchone()
    return row[0] if row else 0


def set_money(uid, value):
    cur.execute("REPLACE INTO money VALUES (?,?)", (uid, max(value, 0)))
    conn.commit()


def add_money(uid, value):
    set_money(uid, money(uid) + value)


def remove_money(uid, value):
    set_money(uid, money(uid) - value)


def today_kst():
    return (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).strftime("%Y-%m-%d")


def normalize_odd_even(choice: str):
    text = choice.strip()
    if text in ["��", "����", "odd", "Odd", "ODD"]:
        return "��"
    if text in ["吏�", "吏앹닔", "even", "Even", "EVEN"]:
        return "吏�"
    return None


def get_warn(uid):
    cur.execute("SELECT cnt FROM warn WHERE uid=?", (uid,))
    row = cur.fetchone()
    return row[0] if row else 0


def add_warn(uid):
    count = get_warn(uid) + 1
    cur.execute("REPLACE INTO warn VALUES (?,?)", (uid, count))
    conn.commit()
    return count


def clear_warn(uid):
    cur.execute("REPLACE INTO warn VALUES (?,0)", (uid,))
    conn.commit()


def warn_punishment_text(count: int) -> str:
    if count == 1:
        return "���꾩븘�� 10遺�"
    if count == 2:
        return "���꾩븘�� 1�쒓컙"
    if count == 3:
        return "���꾩븘�� 1��"
    if count == 4:
        return "異붾갑"
    if count >= 5:
        return "李⑤떒"
    return "�놁쓬"


async def apply_warn_punishment(member: discord.Member, count: int):
    try:
        if count == 1:
            await member.timeout(discord.utils.utcnow() + datetime.timedelta(minutes=10), reason="寃쎄퀬 1�� - 10遺� ���꾩븘��")
        elif count == 2:
            await member.timeout(discord.utils.utcnow() + datetime.timedelta(hours=1), reason="寃쎄퀬 2�� - 1�쒓컙 ���꾩븘��")
        elif count == 3:
            await member.timeout(discord.utils.utcnow() + datetime.timedelta(days=1), reason="寃쎄퀬 3�� - 1�� ���꾩븘��")
        elif count == 4:
            await member.kick(reason="寃쎄퀬 4�� - 異붾갑")
        elif count >= 5:
            await member.ban(reason="寃쎄퀬 5�� - 李⑤떒")
    except Exception as e:
        print(f"寃쎄퀬 泥섎쾶 �ㅻ쪟: {e}")


async def remove_warn_punishment(guild: discord.Guild, user: discord.User):
    member = guild.get_member(user.id)
    if member:
        try:
            await member.timeout(None, reason="寃쎄퀬 ��젣 - 泥섎쾶 �댁젣")
        except Exception as e:
            print(f"���꾩븘�� �댁젣 �ㅻ쪟: {e}")
    try:
        await guild.fetch_ban(user)
        await guild.unban(user, reason="寃쎄퀬 ��젣 - 李⑤떒 �댁젣")
    except discord.NotFound:
        pass
    except Exception as e:
        print(f"李⑤떒 �댁젣 �ㅻ쪟: {e}")


def warn_check_embed(user: discord.User):
    count = get_warn(user.id)
    e = discord.Embed(title="�좑툘 寃쎄퀬 �뺤씤", color=0xFEE75C, timestamp=datetime.datetime.utcnow())
    e.add_field(name="�좎�", value=user.mention, inline=True)
    e.add_field(name="�꾩쟻 寃쎄퀬", value=f"**{count}��**", inline=True)
    e.add_field(name="�꾩옱 泥섎쾶", value=f"**{warn_punishment_text(count)}**", inline=False)
    e.set_thumbnail(url=user.display_avatar.url)
    return e


def xp_needed(level: int) -> int:
    return 5 * (level ** 2) + 50 * level + 100


def get_lv(guild_id, uid):
    cur.execute("SELECT xp, lv, last_msg FROM levels WHERE guild_id=? AND uid=?", (guild_id, uid))
    row = cur.fetchone()
    return (row[0], row[1], row[2]) if row else (0, 0, 0)


def save_lv(guild_id, uid, xp, level, last_msg):
    cur.execute(
        """INSERT INTO levels (guild_id,uid,xp,lv,last_msg) VALUES(?,?,?,?,?)
        ON CONFLICT(guild_id,uid) DO UPDATE SET
        xp=excluded.xp,
        lv=excluded.lv,
        last_msg=excluded.last_msg""",
        (guild_id, uid, xp, level, last_msg),
    )
    conn.commit()


def get_rank(guild_id, uid):
    cur.execute("SELECT uid FROM levels WHERE guild_id=? ORDER BY lv DESC, xp DESC", (guild_id,))
    for index, (row_uid,) in enumerate(cur.fetchall(), 1):
        if row_uid == uid:
            return index
    return 0


def get_top(guild_id, limit=10):
    cur.execute("SELECT uid,xp,lv FROM levels WHERE guild_id=? ORDER BY lv DESC, xp DESC LIMIT ?", (guild_id, limit))
    return cur.fetchall()


async def grant_xp(guild: discord.Guild, member: discord.Member, amount: int):
    if member.bot:
        return
    xp, level, last_msg = get_lv(guild.id, member.id)
    xp += amount
    leveled_up = False
    new_level = level
    while xp >= xp_needed(new_level):
        xp -= xp_needed(new_level)
        new_level += 1
        leveled_up = True
    save_lv(guild.id, member.id, xp, new_level, last_msg)
    if leveled_up:
        cfg = get_cfg(guild.id)
        channel = guild.get_channel(cfg["levelup_ch"]) if cfg["levelup_ch"] else None
        e = discord.Embed(
            title="�럦 �덈꺼 ��!",
            description=f"{member.mention} �섏씠 �덈꺼�� �덉뒿�덈떎!\n\n> �덈꺼 **{level}** �� **{new_level}**\n> �ㅼ쓬 �덈꺼源뚯� **{xp_needed(new_level):,} XP**",
            color=0xF1C40F,
            timestamp=datetime.datetime.utcnow(),
        )
        e.set_thumbnail(url=member.display_avatar.url)
        e.set_footer(text=f"{guild.name} �덈꺼 �쒖뒪��")
        if channel:
            await channel.send(content=member.mention, embed=e)


async def process_chat_xp(message: discord.Message):
    if not message.guild or message.author.bot:
        return
    xp, level, last_msg = get_lv(message.guild.id, message.author.id)
    now = int(datetime.datetime.utcnow().timestamp())
    if now - last_msg < 60:
        return
    save_lv(message.guild.id, message.author.id, xp, level, now)
    await grant_xp(message.guild, message.author, random.randint(15, 25))


@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    guild = member.guild
    now = int(datetime.datetime.utcnow().timestamp())

    cur.execute("SELECT voice_id FROM party WHERE guild_id=? AND owner_id=?", (guild.id, member.id))
    row = cur.fetchone()
    if row and after.channel:
        voice_channel = guild.get_channel(row[0])
        if voice_channel and after.channel.id != voice_channel.id:
            try:
                await member.move_to(voice_channel)
            except Exception:
                pass

    if after.channel and not before.channel:
        cur.execute("INSERT OR REPLACE INTO voice_track VALUES (?,?,?)", (guild.id, member.id, now))
        conn.commit()
    elif before.channel and not after.channel:
        cur.execute("SELECT joined_at FROM voice_track WHERE guild_id=? AND uid=?", (guild.id, member.id))
        row = cur.fetchone()
        if row:
            minutes = (now - row[0]) // 60
            if minutes > 0:
                await grant_xp(guild, member, min(minutes * 10, 200))
            cur.execute("DELETE FROM voice_track WHERE guild_id=? AND uid=?", (guild.id, member.id))
            conn.commit()


def get_sticky(channel_id):
    cur.execute("SELECT content, message_id FROM sticky WHERE channel_id=?", (channel_id,))
    row = cur.fetchone()
    return row if row else None


def set_sticky(channel_id, guild_id, content, message_id):
    cur.execute(
        """INSERT INTO sticky VALUES (?,?,?,?)
        ON CONFLICT(channel_id) DO UPDATE SET
        content=excluded.content,
        message_id=excluded.message_id""",
        (channel_id, guild_id, content, message_id),
    )
    conn.commit()


def del_sticky(channel_id):
    cur.execute("DELETE FROM sticky WHERE channel_id=?", (channel_id,))
    conn.commit()


async def send_sticky(channel: discord.TextChannel, guild: discord.Guild, content: str):
    e = discord.Embed(title="�뱦 怨좎젙 硫붿떆吏�", description=content, color=0xF1C40F, timestamp=datetime.datetime.utcnow())
    e.set_footer(text="�뱦 �� 硫붿떆吏��� 梨꾨꼸 �섎떒�� 怨좎젙�⑸땲��.")
    message = await channel.send(embed=e)
    set_sticky(channel.id, guild.id, content, message.id)
    return message


class VerifyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="�몄쬆�섍린", emoji="��", style=discord.ButtonStyle.success, custom_id="v_verify")
    async def verify(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        cfg = get_cfg(interaction.guild.id)
        role = interaction.guild.get_role(cfg["verify_role"]) if cfg["verify_role"] else None
        if not role:
            role = discord.utils.get(interaction.guild.roles, name="�몄쬆") or await interaction.guild.create_role(name="�몄쬆", color=discord.Color.green())
        if role in interaction.user.roles:
            return await interaction.followup.send(embed=warn_embed("�대� �몄쬆��", "�대� �몄쬆�� �곹깭�낅땲��."), ephemeral=True)
        await interaction.user.add_roles(role)
        try:
            e = discord.Embed(
                title="�� �몄쬆 �꾨즺",
                description=f"**{interaction.guild.name}** �몄쬆 �꾨즺!\n> ��븷 `{role.name}` ��(媛�) 遺��щ릺�덉뒿�덈떎.",
                color=0x57F287,
                timestamp=datetime.datetime.utcnow(),
            )
            await interaction.user.send(embed=e)
        except discord.Forbidden:
            pass
        await interaction.followup.send(embed=success_embed("�몄쬆 �꾨즺", f"`{role.name}` ��븷 遺��щ맖"), ephemeral=True)
        log = discord.Embed(title="�뱥 �몄쬆 濡쒓렇", color=0x57F287, timestamp=datetime.datetime.utcnow())
        log.add_field(name="�좎�", value=f"{interaction.user.mention} (`{interaction.user}`)")
        log.add_field(name="��븷", value=role.mention)
        log.set_thumbnail(url=interaction.user.display_avatar.url)
        await send_log(interaction.guild, [log])


class TicketCloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="�곗폆 �リ린", emoji="�뵏", style=discord.ButtonStyle.danger, custom_id="v_ticket_close")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_admin(interaction):
            return await interaction.response.send_message(embed=error_embed("沅뚰븳 �놁쓬", "遊� 愿�由ъ옄 ��븷�� �꾩슂�⑸땲��."), ephemeral=True)
        await interaction.response.send_message(embed=warn_embed("�곗폆 �ル뒗 以�...", "3珥� �� 梨꾨꼸�� ��젣�⑸땲��."))
        await asyncio.sleep(3)
        await interaction.channel.delete()


class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="�곗폆 �앹꽦", emoji="�렅截�", style=discord.ButtonStyle.primary, custom_id="v_ticket")
    async def create(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        existing = discord.utils.get(interaction.guild.text_channels, name=f"ticket-{interaction.user.name.lower()}")
        if existing:
            return await interaction.followup.send(embed=warn_embed("�대� �곗폆 議댁옱", f"�대┛ �곗폆: {existing.mention}"), ephemeral=True)
        cfg = get_cfg(interaction.guild.id)
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
        }
        if cfg["admin_role"]:
            admin_role = interaction.guild.get_role(cfg["admin_role"])
            if admin_role:
                overwrites[admin_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
        channel = await interaction.guild.create_text_channel(
            name=f"ticket-{interaction.user.name}",
            overwrites=overwrites,
            topic=f"{interaction.user} �� �곗폆",
        )
        e = discord.Embed(
            title="�렅截� �곗폆 �앹꽦��",
            description=f"�덈뀞�섏꽭�� {interaction.user.mention}��!\n愿�由ъ옄媛� 怨� �듬��쒕┰�덈떎.\n臾몄쓽 �댁슜�� �묒꽦�� 二쇱꽭��.",
            color=0x5865F2,
            timestamp=datetime.datetime.utcnow(),
        )
        e.set_footer(text="�곗폆�� �レ쑝�ㅻ㈃ �꾨옒 踰꾪듉�� �뚮윭二쇱꽭��.")
        e.set_thumbnail(url=interaction.user.display_avatar.url)
        await channel.send(embed=e, view=TicketCloseView())
        await interaction.followup.send(embed=success_embed("�곗폆 �앹꽦 �꾨즺", f"梨꾨꼸: {channel.mention}"), ephemeral=True)


class PartyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="�뚰떚 李멸�", emoji="�렜", style=discord.ButtonStyle.success, custom_id="v_party_join")
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        cur.execute("SELECT voice_id FROM party WHERE guild_id=? AND owner_id=?", (interaction.guild.id, interaction.user.id))
        row = cur.fetchone()
        if not row:
            return await interaction.followup.send(embed=error_embed("�뚰떚 �놁쓬"), ephemeral=True)
        channel = interaction.guild.get_channel(row[0])
        if channel:
            await interaction.user.move_to(channel)
            await interaction.followup.send(embed=success_embed("李멸� �꾨즺", f"{channel.mention}�쇰줈 �대룞"), ephemeral=True)
        else:
            await interaction.followup.send(embed=error_embed("梨꾨꼸 �놁쓬"), ephemeral=True)


class AdminPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="�뚰떚 紐⑸줉", emoji="�렜", style=discord.ButtonStyle.primary, custom_id="v_ap_party")
    async def party(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        cur.execute("SELECT owner_id, voice_id FROM party WHERE guild_id=?", (interaction.guild.id,))
        rows = cur.fetchall()
        if not rows:
            return await interaction.followup.send(embed=info_embed("�뚰떚 �놁쓬"), ephemeral=True)
        await interaction.followup.send(embed=info_embed("�뚰떚 紐⑸줉", "\n".join(f"<@{owner}> �� <#{voice}>" for owner, voice in rows)), ephemeral=True)

    @discord.ui.button(label="寃쎄퀬 紐⑸줉", emoji="�좑툘", style=discord.ButtonStyle.danger, custom_id="v_ap_warn")
    async def warns(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        cur.execute("SELECT uid, cnt FROM warn WHERE cnt > 0")
        rows = cur.fetchall()
        if not rows:
            return await interaction.followup.send(embed=info_embed("寃쎄퀬 �놁쓬"), ephemeral=True)
        text = "\n".join(f"<@{uid}> �� **{count}��** ({warn_punishment_text(count)})" for uid, count in rows)
        await interaction.followup.send(embed=warn_embed("寃쎄퀬 紐⑸줉", text), ephemeral=True)

    @discord.ui.button(label="�곗폆 紐⑸줉", emoji="�렅截�", style=discord.ButtonStyle.success, custom_id="v_ap_ticket")
    async def tickets(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        tickets = [channel for channel in interaction.guild.text_channels if channel.name.startswith("ticket-")]
        if not tickets:
            return await interaction.followup.send(embed=info_embed("�곗폆 �놁쓬"), ephemeral=True)
        await interaction.followup.send(embed=info_embed(f"�곗폆 紐⑸줉 ({len(tickets)}媛�)", "\n".join(channel.mention for channel in tickets)), ephemeral=True)


async def send_verify_panel(destination, guild: discord.Guild):
    e = discord.Embed(
        title="�� �쒕쾭 �몄쬆",
        description="�꾨옒 踰꾪듉�� �뚮윭 �몄쬆�� �꾨즺�섏꽭��.\n> �몄쬆 �꾨즺 �� ��븷�� �먮룞 遺��щ맗�덈떎.",
        color=0x57F287,
        timestamp=datetime.datetime.utcnow(),
    )
    e.set_footer(text=guild.name, icon_url=guild.icon.url if guild.icon else None)
    await destination.send(embed=e, view=VerifyView())


async def send_ticket_panel(destination, guild: discord.Guild):
    e = discord.Embed(
        title="�렅截� �곗폆 �쒖뒪��",
        description="臾몄쓽�ы빆�� �덉쑝硫� �꾨옒 踰꾪듉�� �뚮윭 �곗폆�� �앹꽦�섏꽭��.\n> 1�몃떦 1媛쒕쭔 �앹꽦 媛��ν빀�덈떎.",
        color=0x5865F2,
        timestamp=datetime.datetime.utcnow(),
    )
    e.set_footer(text=guild.name, icon_url=guild.icon.url if guild.icon else None)
    await destination.send(embed=e, view=TicketView())


async def send_admin_panel(destination, user: discord.Member):
    e = discord.Embed(
        title="�숋툘 愿�由ъ옄 �⑤꼸",
        description="�쒕쾭 愿�由� �꾧뎄�낅땲��. 踰꾪듉�쇰줈 媛� 湲곕뒫�� �뺤씤�섏꽭��.",
        color=0xEB459E,
        timestamp=datetime.datetime.utcnow(),
    )
    e.set_footer(text=f"愿�由ъ옄: {user}", icon_url=user.display_avatar.url)
    await destination.send(embed=e, view=AdminPanel())


async def run_salary(user: discord.User):
    now = datetime.datetime.utcnow().timestamp()
    last = salary_cd.get(user.id, 0)
    if now - last < SALARY_COOLDOWN:
        remain = int(SALARY_COOLDOWN - (now - last))
        return None, remain
    salary_cd[user.id] = now
    add_money(user.id, SALARY_AMOUNT)
    return money(user.id), 0


async def run_attendance(user: discord.User):
    cur.execute("SELECT date FROM attendance WHERE uid=?", (user.id,))
    row = cur.fetchone()
    today = today_kst()
    if row and row[0] == today:
        return None
    cur.execute("REPLACE INTO attendance VALUES (?,?)", (user.id, today))
    conn.commit()
    add_money(user.id, ATTENDANCE_AMOUNT)
    return money(user.id)


async def run_odd_even(user: discord.User, choice: str, bet: int):
    normalized = normalize_odd_even(choice)
    if not normalized:
        return "bad_choice", None
    if bet <= 0:
        return "bad_bet", None
    if money(user.id) < bet:
        return "no_money", None
    number = random.randint(1, 100)
    result = "��" if number % 2 else "吏�"
    if normalized == result:
        reward = bet * 2
        add_money(user.id, reward)
        return "win", (number, result, reward, money(user.id))
    remove_money(user.id, bet)
    return "lose", (number, result, bet, money(user.id))


@bot.tree.command(name="紐낅졊�대ぉ濡�", description="遊뉗쓽 紐⑤뱺 紐낅졊�대� �뺤씤�⑸땲��.")
async def cmd_command_list(interaction: discord.Interaction):
    await interaction.response.send_message(embed=command_list_embed(interaction.guild))


@bot.tree.command(name="��븷", description="[愿�由ъ옄] �몄쬆 ��븷 諛� 遊� 愿�由ъ옄 ��븷�� �ㅼ젙�⑸땲��.")
async def cmd_roles(interaction: discord.Interaction, �몄쬆��븷: discord.Role, 愿�由ъ옄��븷: discord.Role):
    if interaction.user.id != interaction.guild.owner_id and not interaction.user.guild_permissions.administrator:
        return await deny(interaction)
    set_cfg(interaction.guild.id, verify_role=�몄쬆��븷.id, admin_role=愿�由ъ옄��븷.id)
    e = discord.Embed(title="�숋툘 ��븷 �ㅼ젙 �꾨즺", color=0x57F287, timestamp=datetime.datetime.utcnow())
    e.add_field(name="�� �몄쬆 ��븷", value=�몄쬆��븷.mention, inline=True)
    e.add_field(name="�썳截� 愿�由ъ옄 ��븷", value=愿�由ъ옄��븷.mention, inline=True)
    await interaction.response.send_message(embed=e)


@bot.tree.command(name="梨꾨꼸�ㅼ젙", description="[愿�由ъ옄] �낆옣쨌濡쒓렇쨌�덈꺼�� 梨꾨꼸 諛� �뚰떚 移댄뀒怨좊━瑜� �ㅼ젙�⑸땲��.")
async def cmd_channels(interaction: discord.Interaction, �낆옣梨꾨꼸: discord.TextChannel, 濡쒓렇梨꾨꼸: discord.TextChannel, �덈꺼�낆콈��: discord.TextChannel, �뚰떚移댄뀒怨좊━: discord.CategoryChannel):
    if not is_admin(interaction):
        return await deny(interaction)
    set_cfg(interaction.guild.id, welcome_ch=�낆옣梨꾨꼸.id, log_ch=濡쒓렇梨꾨꼸.id, levelup_ch=�덈꺼�낆콈��.id, party_cat=�뚰떚移댄뀒怨좊━.id)
    await interaction.response.send_message(embed=success_embed("梨꾨꼸 �ㅼ젙 �꾨즺", "�낆옣, 濡쒓렇, �덈꺼��, �뚰떚 移댄뀒怨좊━媛� ���λ릺�덉뒿�덈떎."))


@bot.tree.command(name="�몄쬆�⑤꼸", description="[愿�由ъ옄] �몄쬆 �⑤꼸�� �꾩넚�⑸땲��.")
async def cmd_verify_panel(interaction: discord.Interaction):
    if not is_admin(interaction):
        return await deny(interaction)
    await send_verify_panel(interaction.channel, interaction.guild)
    await interaction.response.send_message(embed=success_embed("�몄쬆 �⑤꼸 �꾩넚 �꾨즺"), ephemeral=True)


@bot.tree.command(name="�곗폆�⑤꼸", description="[愿�由ъ옄] �곗폆 �⑤꼸�� �꾩넚�⑸땲��.")
async def cmd_ticket_panel(interaction: discord.Interaction):
    if not is_admin(interaction):
        return await deny(interaction)
    await send_ticket_panel(interaction.channel, interaction.guild)
    await interaction.response.send_message(embed=success_embed("�곗폆 �⑤꼸 �꾩넚 �꾨즺"), ephemeral=True)


@bot.tree.command(name="愿�由ъ옄�⑤꼸", description="[愿�由ъ옄] 愿�由ъ옄 �⑤꼸�� �꾩넚�⑸땲��.")
async def cmd_admin_panel(interaction: discord.Interaction):
    if not is_admin(interaction):
        return await deny(interaction)
    await send_admin_panel(interaction.channel, interaction.user)
    await interaction.response.send_message(embed=success_embed("愿�由ъ옄 �⑤꼸 �꾩넚 �꾨즺"), ephemeral=True)


@bot.tree.command(name="泥�냼", description="[愿�由ъ옄] 硫붿떆吏�瑜� �쇨큵 ��젣�⑸땲��. 理쒕� 100媛�")
async def cmd_purge(interaction: discord.Interaction, 媛쒖닔: int):
    if not is_admin(interaction):
        return await deny(interaction)
    if not 1 <= 媛쒖닔 <= 100:
        return await interaction.response.send_message(embed=error_embed("�섎せ�� �낅젰", "1~100 �ъ씠 �レ옄瑜� �낅젰�섏꽭��."), ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=媛쒖닔)
    await interaction.followup.send(embed=success_embed("泥�냼 �꾨즺", f"**{len(deleted)}媛�** ��젣 �꾨즺"), ephemeral=True)


@bot.tree.command(name="寃쎄퀬", description="[愿�由ъ옄] �좎��먭쾶 寃쎄퀬瑜� 遺��ы빀�덈떎.")
async def cmd_warn(interaction: discord.Interaction, �좎�: discord.Member):
    if not is_admin(interaction):
        return await deny(interaction)
    count = add_warn(�좎�.id)
    e = discord.Embed(title="�좑툘 寃쎄퀬 遺���", color=0xFEE75C, timestamp=datetime.datetime.utcnow())
    e.add_field(name="����", value=�좎�.mention, inline=True)
    e.add_field(name="�꾩쟻 寃쎄퀬", value=f"**{count}��**", inline=True)
    e.add_field(name="泥섎쾶", value=f"**{warn_punishment_text(count)}**", inline=False)
    e.set_thumbnail(url=�좎�.display_avatar.url)
    await interaction.response.send_message(embed=e)
    await send_log(interaction.guild, [e])
    await apply_warn_punishment(�좎�, count)


@bot.tree.command(name="寃쎄퀬��젣", description="[愿�由ъ옄] �좎��� 寃쎄퀬瑜� 珥덇린�뷀븯怨� 泥섎쾶�� �댁젣�⑸땲��.")
async def cmd_warn_clear(interaction: discord.Interaction, �좎�: discord.User):
    if not is_admin(interaction):
        return await deny(interaction)
    clear_warn(�좎�.id)
    await remove_warn_punishment(interaction.guild, �좎�)
    await interaction.response.send_message(embed=success_embed("寃쎄퀬 珥덇린��", f"{�좎�.mention} 寃쎄퀬 珥덇린�� 諛� 泥섎쾶 �댁젣 �꾨즺"))


@bot.tree.command(name="寃쎄퀬�뺤씤", description="�좎��� 寃쎄퀬 �잛닔瑜� �뺤씤�⑸땲��.")
async def cmd_warn_check(interaction: discord.Interaction, �좎�: discord.User = None):
    await interaction.response.send_message(embed=warn_check_embed(�좎� or interaction.user))


@bot.tree.command(name="�붿븸", description="�붿븸�� �뺤씤�⑸땲��.")
async def cmd_balance(interaction: discord.Interaction, �좎�: discord.Member = None):
    user = �좎� or interaction.user
    e = discord.Embed(title="�뮥 �붿븸 �뺤씤", description=f"{user.mention}\n�붿븸: `{money(user.id):,}��`", color=0x2ECC71)
    await interaction.response.send_message(embed=e)


@bot.tree.command(name="�↔툑", description="�ㅻⅨ �좎��먭쾶 �↔툑�⑸땲��.")
async def cmd_transfer(interaction: discord.Interaction, �좎�: discord.Member, 湲덉븸: int):
    if �좎�.bot or �좎�.id == interaction.user.id:
        return await interaction.response.send_message("�� ���� �ㅻ쪟", ephemeral=True)
    if 湲덉븸 <= 0:
        return await interaction.response.send_message("�� 湲덉븸 �ㅻ쪟", ephemeral=True)
    if money(interaction.user.id) < 湲덉븸:
        return await interaction.response.send_message("�� �붿븸 遺�議�", ephemeral=True)
    remove_money(interaction.user.id, 湲덉븸)
    add_money(�좎�.id, 湲덉븸)
    e = discord.Embed(title="�뮯 �↔툑 �꾨즺", description=f"{interaction.user.mention} �� {�좎�.mention}\n湲덉븸: `{湲덉븸:,}��`", color=0x3498DB)
    await interaction.response.send_message(embed=e)


@bot.tree.command(name="異쒖꽍", description="�섎（�� �� 踰� 異쒖꽍 蹂댁긽�� 諛쏆뒿�덈떎.")
async def cmd_attendance(interaction: discord.Interaction):
    balance = await run_attendance(interaction.user)
    if balance is None:
        return await interaction.response.send_message("�� �ㅻ뒛 �대� 異쒖꽍�덉뒿�덈떎", ephemeral=True)
    e = discord.Embed(title="�뱟 異쒖꽍 �꾨즺", description=f"蹂댁긽: `{ATTENDANCE_AMOUNT:,}��`\n�꾩옱 �붿븸: `{balance:,}��`", color=0x57F287)
    await interaction.response.send_message(embed=e)


@bot.tree.command(name="�붽툒", description="�붽툒�� 諛쏆뒿�덈떎.")
async def cmd_salary(interaction: discord.Interaction):
    balance, remain = await run_salary(interaction.user)
    if balance is None:
        return await interaction.response.send_message(f"�� 荑⑦��� 以묒엯�덈떎. `{remain}珥�` �� �ㅼ떆 �쒕룄�섏꽭��.", ephemeral=True)
    e = discord.Embed(title="�뮳 �붽툒 吏�湲�", description=f"+{SALARY_AMOUNT:,}�� 吏�湲�\n�꾩옱 �붿븸: `{balance:,}��`", color=0x9B59B6)
    await interaction.response.send_message(embed=e)


@bot.tree.command(name="��吏�", description="��吏� 寃뚯엫�� �⑸땲��. �좏깮�� ��/吏�, 湲덉븸�� �낅젰�섏꽭��.")
async def cmd_odd_even(interaction: discord.Interaction, �좏깮: str, 湲덉븸: int):
    status, data = await run_odd_even(interaction.user, �좏깮, 湲덉븸)
    if status == "bad_choice":
        return await interaction.response.send_message("�� �좏깮�� `��` �먮뒗 `吏�`留� 媛��ν빀�덈떎.", ephemeral=True)
    if status == "bad_bet":
        return await interaction.response.send_message("�� 湲덉븸 �ㅻ쪟", ephemeral=True)
    if status == "no_money":
        return await interaction.response.send_message("�� �붿븸 遺�議�", ephemeral=True)
    number, result, amount, balance = data
    if status == "win":
        text = f"�럦 �밸━!\n�レ옄: `{number}` ({result})\n+`{amount:,}��`\n�꾩옱 �붿븸: `{balance:,}��`"
    else:
        text = f"�뮙 �⑤같!\n�レ옄: `{number}` ({result})\n-`{amount:,}��`\n�꾩옱 �붿븸: `{balance:,}��`"
    await interaction.response.send_message(embed=discord.Embed(title="�렡 ��吏� 寃뚯엫", description=text, color=0xF1C40F))


@bot.tree.command(name="�덈꺼", description="�덈꺼�� �뺤씤�⑸땲��.")
async def cmd_level(interaction: discord.Interaction, �좎�: discord.Member = None):
    user = �좎� or interaction.user
    xp, level, _ = get_lv(interaction.guild.id, user.id)
    needed = xp_needed(level)
    rank = get_rank(interaction.guild.id, user.id)
    filled = int((xp / needed) * 20)
    bar = "��" * filled + "��" * (20 - filled)
    e = discord.Embed(title="狩� �덈꺼 �뺣낫", color=0xF1C40F, timestamp=datetime.datetime.utcnow())
    e.set_thumbnail(url=user.display_avatar.url)
    e.add_field(name="�좎�", value=user.mention, inline=True)
    e.add_field(name="�덈꺼", value=f"**{level}**", inline=True)
    e.add_field(name="�쒕쾭 �쒖쐞", value=f"**#{rank}**", inline=True)
    e.add_field(name="寃쏀뿕移�", value=f"`{xp:,}` / `{needed:,}`", inline=True)
    e.add_field(name="吏꾪뻾��", value=f"`{bar}` {int(xp / needed * 100)}%", inline=False)
    await interaction.response.send_message(embed=e)


@bot.tree.command(name="�쒖쐞", description="�쒕쾭 �덈꺼 �쒖쐞瑜� �뺤씤�⑸땲��.")
async def cmd_rank(interaction: discord.Interaction):
    rows = get_top(interaction.guild.id)
    if not rows:
        return await interaction.response.send_message(embed=info_embed("�쒖쐞 �놁쓬", "�꾩쭅 �덈꺼 �곗씠�곌� �놁뒿�덈떎."), ephemeral=True)
    medals = {1: "�쪍", 2: "�쪎", 3: "�쪏"}
    desc = "\n".join(f"{medals.get(i, f'`{i}.`')} <@{uid}> �� **�덈꺼 {level}** (`{xp:,}` XP)" for i, (uid, xp, level) in enumerate(rows, 1))
    await interaction.response.send_message(embed=discord.Embed(title="�룇 �덈꺼 �쒖쐞", description=desc, color=0xF1C40F))


@bot.tree.command(name="�뚰떚�앹꽦", description="�뚰떚 �뚯꽦 梨꾨꼸�� �앹꽦�⑸땲��.")
async def cmd_party_create(interaction: discord.Interaction):
    await interaction.response.defer()
    cur.execute("SELECT voice_id FROM party WHERE guild_id=? AND owner_id=?", (interaction.guild.id, interaction.user.id))
    if cur.fetchone():
        return await interaction.followup.send(embed=warn_embed("�대� �뚰떚 議댁옱", "湲곗〈 �뚰떚瑜� 癒쇱� ��젣�섏꽭��."), ephemeral=True)
    cfg = get_cfg(interaction.guild.id)
    category = interaction.guild.get_channel(cfg["party_cat"]) if cfg["party_cat"] else None
    channel = await interaction.guild.create_voice_channel(name=f"�렜 {interaction.user.display_name}�� �뚰떚", category=category)
    cur.execute("INSERT OR REPLACE INTO party VALUES (?,?,?)", (interaction.guild.id, interaction.user.id, channel.id))
    conn.commit()
    await interaction.followup.send(embed=success_embed("�뚰떚 �앹꽦 �꾨즺", f"梨꾨꼸 {channel.mention} �앹꽦��"), view=PartyView())


@bot.tree.command(name="�뚰떚��젣", description="�먯떊�� �뚰떚 梨꾨꼸�� ��젣�⑸땲��.")
async def cmd_party_delete(interaction: discord.Interaction):
    await interaction.response.defer()
    cur.execute("SELECT voice_id FROM party WHERE guild_id=? AND owner_id=?", (interaction.guild.id, interaction.user.id))
    row = cur.fetchone()
    if not row:
        return await interaction.followup.send(embed=error_embed("�뚰떚 �놁쓬"), ephemeral=True)
    channel = interaction.guild.get_channel(row[0])
    if channel:
        await channel.delete()
    cur.execute("DELETE FROM party WHERE guild_id=? AND owner_id=?", (interaction.guild.id, interaction.user.id))
    conn.commit()
    await interaction.followup.send(embed=success_embed("�뚰떚 ��젣 �꾨즺"))


@bot.tree.command(name="�ㅽ떚��", description="梨꾨꼸�� 怨좎젙 硫붿떆吏�瑜� �ㅼ젙�⑸땲��.")
async def cmd_sticky_set(interaction: discord.Interaction, �댁슜: str):
    if not is_admin(interaction):
        return await deny(interaction)
    await interaction.response.defer(ephemeral=True)
    existing = get_sticky(interaction.channel.id)
    if existing:
        try:
            old = await interaction.channel.fetch_message(existing[1])
            await old.delete()
        except Exception:
            pass
    await send_sticky(interaction.channel, interaction.guild, �댁슜)
    await interaction.followup.send(embed=success_embed("�ㅽ떚�� �ㅼ젙 �꾨즺"), ephemeral=True)


@bot.tree.command(name="�ㅽ떚�ㅽ빐��", description="梨꾨꼸�� 怨좎젙 硫붿떆吏�瑜� �댁젣�⑸땲��.")
async def cmd_sticky_remove(interaction: discord.Interaction):
    if not is_admin(interaction):
        return await deny(interaction)
    existing = get_sticky(interaction.channel.id)
    if not existing:
        return await interaction.response.send_message(embed=warn_embed("�ㅽ떚�� �놁쓬"), ephemeral=True)
    try:
        old = await interaction.channel.fetch_message(existing[1])
        await old.delete()
    except Exception:
        pass
    del_sticky(interaction.channel.id)
    await interaction.response.send_message(embed=success_embed("�ㅽ떚�� �댁젣 �꾨즺"), ephemeral=True)


@bot.command(name="紐낅졊�대ぉ濡�", aliases=["�꾩�留�", "h", "紐낅졊��", "help"])
async def pfx_command_list(ctx: commands.Context):
    await ctx.send(embed=command_list_embed(ctx.guild))


@bot.command(name="��븷")
async def pfx_roles(ctx: commands.Context, �몄쬆��븷: discord.Role, 愿�由ъ옄��븷: discord.Role):
    if ctx.author.id != ctx.guild.owner_id and not ctx.author.guild_permissions.administrator:
        return await ctx.send(embed=error_embed("沅뚰븳 �놁쓬", "�쒕쾭 �뚯쑀�� �먮뒗 愿�由ъ옄 沅뚰븳�� �꾩슂�⑸땲��."))
    set_cfg(ctx.guild.id, verify_role=�몄쬆��븷.id, admin_role=愿�由ъ옄��븷.id)
    await ctx.send(embed=success_embed("��븷 �ㅼ젙 �꾨즺", f"�몄쬆 ��븷: {�몄쬆��븷.mention}\n愿�由ъ옄 ��븷: {愿�由ъ옄��븷.mention}"))


@bot.command(name="梨꾨꼸�ㅼ젙")
async def pfx_channels(ctx: commands.Context, �낆옣梨꾨꼸: discord.TextChannel, 濡쒓렇梨꾨꼸: discord.TextChannel, �덈꺼�낆콈��: discord.TextChannel, �뚰떚移댄뀒怨좊━: discord.CategoryChannel):
    if not is_admin_ctx(ctx):
        return await ctx.send(embed=error_embed("沅뚰븳 �놁쓬"))
    set_cfg(ctx.guild.id, welcome_ch=�낆옣梨꾨꼸.id, log_ch=濡쒓렇梨꾨꼸.id, levelup_ch=�덈꺼�낆콈��.id, party_cat=�뚰떚移댄뀒怨좊━.id)
    await ctx.send(embed=success_embed("梨꾨꼸 �ㅼ젙 �꾨즺", "�낆옣, 濡쒓렇, �덈꺼��, �뚰떚 移댄뀒怨좊━媛� ���λ릺�덉뒿�덈떎."))


@bot.command(name="�몄쬆�⑤꼸")
async def pfx_verify_panel(ctx: commands.Context):
    if not is_admin_ctx(ctx):
        return await ctx.send(embed=error_embed("沅뚰븳 �놁쓬"))
    await send_verify_panel(ctx.channel, ctx.guild)


@bot.command(name="�곗폆�⑤꼸")
async def pfx_ticket_panel(ctx: commands.Context):
    if not is_admin_ctx(ctx):
        return await ctx.send(embed=error_embed("沅뚰븳 �놁쓬"))
    await send_ticket_panel(ctx.channel, ctx.guild)


@bot.command(name="愿�由ъ옄�⑤꼸")
async def pfx_admin_panel(ctx: commands.Context):
    if not is_admin_ctx(ctx):
        return await ctx.send(embed=error_embed("沅뚰븳 �놁쓬"))
    await send_admin_panel(ctx.channel, ctx.author)


@bot.command(name="�붿븸", aliases=["bal", "money"])
async def pfx_balance(ctx: commands.Context, �좎�: discord.Member = None):
    user = �좎� or ctx.author
    await ctx.send(embed=discord.Embed(title="�뮥 �붿븸 �뺤씤", description=f"{user.mention}\n�붿븸: `{money(user.id):,}��`", color=0x2ECC71))


@bot.command(name="�↔툑", aliases=["pay"])
async def pfx_transfer(ctx: commands.Context, �좎�: discord.Member, 湲덉븸: int):
    if �좎�.bot or �좎�.id == ctx.author.id:
        return await ctx.send("�� ���� �ㅻ쪟")
    if 湲덉븸 <= 0:
        return await ctx.send("�� 湲덉븸 �ㅻ쪟")
    if money(ctx.author.id) < 湲덉븸:
        return await ctx.send("�� �붿븸 遺�議�")
    remove_money(ctx.author.id, 湲덉븸)
    add_money(�좎�.id, 湲덉븸)
    await ctx.send(embed=discord.Embed(title="�뮯 �↔툑 �꾨즺", description=f"{ctx.author.mention} �� {�좎�.mention}\n湲덉븸: `{湲덉븸:,}��`", color=0x3498DB))


@bot.command(name="異쒖꽍")
async def pfx_attendance(ctx: commands.Context):
    balance = await run_attendance(ctx.author)
    if balance is None:
        return await ctx.send("�� �ㅻ뒛 �대� 異쒖꽍�덉뒿�덈떎")
    await ctx.send(embed=discord.Embed(title="�뱟 異쒖꽍 �꾨즺", description=f"蹂댁긽: `{ATTENDANCE_AMOUNT:,}��`\n�꾩옱 �붿븸: `{balance:,}��`", color=0x57F287))


@bot.command(name="�붽툒")
async def pfx_salary(ctx: commands.Context):
    balance, remain = await run_salary(ctx.author)
    if balance is None:
        return await ctx.send(f"�� 荑⑦��� 以묒엯�덈떎. `{remain}珥�` �� �ㅼ떆 �쒕룄�섏꽭��.")
    await ctx.send(embed=discord.Embed(title="�뮳 �붽툒 吏�湲�", description=f"+{SALARY_AMOUNT:,}�� 吏�湲�\n�꾩옱 �붿븸: `{balance:,}��`", color=0x9B59B6))


@bot.command(name="��吏�")
async def pfx_odd_even(ctx: commands.Context, �좏깮: str, 湲덉븸: int):
    status, data = await run_odd_even(ctx.author, �좏깮, 湲덉븸)
    if status == "bad_choice":
        return await ctx.send("�� �좏깮�� `��` �먮뒗 `吏�`留� 媛��ν빀�덈떎.")
    if status == "bad_bet":
        return await ctx.send("�� 湲덉븸 �ㅻ쪟")
    if status == "no_money":
        return await ctx.send("�� �붿븸 遺�議�")
    number, result, amount, balance = data
    if status == "win":
        text = f"�럦 �밸━!\n�レ옄: `{number}` ({result})\n+`{amount:,}��`\n�꾩옱 �붿븸: `{balance:,}��`"
    else:
        text = f"�뮙 �⑤같!\n�レ옄: `{number}` ({result})\n-`{amount:,}��`\n�꾩옱 �붿븸: `{balance:,}��`"
    await ctx.send(embed=discord.Embed(title="�렡 ��吏� 寃뚯엫", description=text, color=0xF1C40F))


@bot.command(name="寃쎄퀬", aliases=["warn"])
async def pfx_warn(ctx: commands.Context, �좎�: discord.Member):
    if not is_admin_ctx(ctx):
        return await ctx.send(embed=error_embed("沅뚰븳 �놁쓬", "遊� 愿�由ъ옄 ��븷�� �꾩슂�⑸땲��."))
    count = add_warn(�좎�.id)
    e = discord.Embed(title="�좑툘 寃쎄퀬 遺���", color=0xFEE75C, timestamp=datetime.datetime.utcnow())
    e.add_field(name="����", value=�좎�.mention, inline=True)
    e.add_field(name="�꾩쟻 寃쎄퀬", value=f"**{count}��**", inline=True)
    e.add_field(name="泥섎쾶", value=f"**{warn_punishment_text(count)}**", inline=False)
    await ctx.send(embed=e)
    await send_log(ctx.guild, [e])
    await apply_warn_punishment(�좎�, count)


@bot.command(name="寃쎄퀬��젣", aliases=["clearwarn"])
async def pfx_warn_clear(ctx: commands.Context, �좎�: discord.User):
    if not is_admin_ctx(ctx):
        return await ctx.send(embed=error_embed("沅뚰븳 �놁쓬"))
    clear_warn(�좎�.id)
    await remove_warn_punishment(ctx.guild, �좎�)
    await ctx.send(embed=success_embed("寃쎄퀬 珥덇린��", f"{�좎�.mention} 寃쎄퀬 珥덇린�� 諛� 泥섎쾶 �댁젣 �꾨즺"))


@bot.command(name="寃쎄퀬�뺤씤", aliases=["warncheck", "warnings"])
async def pfx_warn_check(ctx: commands.Context, �좎�: discord.User = None):
    await ctx.send(embed=warn_check_embed(�좎� or ctx.author))


@bot.command(name="泥�냼", aliases=["purge", "clear"])
async def pfx_purge(ctx: commands.Context, 媛쒖닔: int):
    if not is_admin_ctx(ctx):
        return await ctx.send(embed=error_embed("沅뚰븳 �놁쓬"))
    if not 1 <= 媛쒖닔 <= 100:
        return await ctx.send(embed=error_embed("�섎せ�� �낅젰", "1~100 �ъ씠 �レ옄瑜� �낅젰�섏꽭��."))
    deleted = await ctx.channel.purge(limit=媛쒖닔 + 1)
    notice = await ctx.send(embed=success_embed("泥�냼 �꾨즺", f"**{len(deleted)-1}媛�** ��젣 �꾨즺"))
    await asyncio.sleep(5)
    try:
        await notice.delete()
    except Exception:
        pass


@bot.command(name="�덈꺼", aliases=["lv", "level"])
async def pfx_level(ctx: commands.Context, �좎�: discord.Member = None):
    user = �좎� or ctx.author
    xp, level, _ = get_lv(ctx.guild.id, user.id)
    needed = xp_needed(level)
    rank = get_rank(ctx.guild.id, user.id)
    filled = int((xp / needed) * 20)
    bar = "��" * filled + "��" * (20 - filled)
    e = discord.Embed(title="狩� �덈꺼 �뺣낫", color=0xF1C40F)
    e.set_thumbnail(url=user.display_avatar.url)
    e.add_field(name="�좎�", value=user.mention)
    e.add_field(name="�덈꺼", value=f"**{level}**")
    e.add_field(name="�쒕쾭 �쒖쐞", value=f"**#{rank}**")
    e.add_field(name="寃쏀뿕移�", value=f"`{xp:,}` / `{needed:,}`")
    e.add_field(name="吏꾪뻾��", value=f"`{bar}` {int(xp / needed * 100)}%", inline=False)
    await ctx.send(embed=e)


@bot.command(name="�쒖쐞", aliases=["rank", "top"])
async def pfx_rank(ctx: commands.Context):
    rows = get_top(ctx.guild.id)
    if not rows:
        return await ctx.send(embed=info_embed("�쒖쐞 �놁쓬", "�꾩쭅 �곗씠�곌� �놁뒿�덈떎."))
    medals = {1: "�쪍", 2: "�쪎", 3: "�쪏"}
    desc = "\n".join(f"{medals.get(i, f'`{i}.`')} <@{uid}> �� **�덈꺼 {level}** (`{xp:,}` XP)" for i, (uid, xp, level) in enumerate(rows, 1))
    await ctx.send(embed=discord.Embed(title="�룇 �덈꺼 �쒖쐞", description=desc, color=0xF1C40F))


@bot.command(name="�뚰떚�앹꽦")
async def pfx_party_create(ctx: commands.Context):
    cur.execute("SELECT voice_id FROM party WHERE guild_id=? AND owner_id=?", (ctx.guild.id, ctx.author.id))
    if cur.fetchone():
        return await ctx.send(embed=warn_embed("�대� �뚰떚 議댁옱", "湲곗〈 �뚰떚瑜� 癒쇱� ��젣�섏꽭��."))
    cfg = get_cfg(ctx.guild.id)
    category = ctx.guild.get_channel(cfg["party_cat"]) if cfg["party_cat"] else None
    channel = await ctx.guild.create_voice_channel(name=f"�렜 {ctx.author.display_name}�� �뚰떚", category=category)
    cur.execute("INSERT OR REPLACE INTO party VALUES (?,?,?)", (ctx.guild.id, ctx.author.id, channel.id))
    conn.commit()
    await ctx.send(embed=success_embed("�뚰떚 �앹꽦 �꾨즺", f"梨꾨꼸 {channel.mention} �앹꽦��"), view=PartyView())


@bot.command(name="�뚰떚��젣")
async def pfx_party_delete(ctx: commands.Context):
    cur.execute("SELECT voice_id FROM party WHERE guild_id=? AND owner_id=?", (ctx.guild.id, ctx.author.id))
    row = cur.fetchone()
    if not row:
        return await ctx.send(embed=error_embed("�뚰떚 �놁쓬"))
    channel = ctx.guild.get_channel(row[0])
    if channel:
        await channel.delete()
    cur.execute("DELETE FROM party WHERE guild_id=? AND owner_id=?", (ctx.guild.id, ctx.author.id))
    conn.commit()
    await ctx.send(embed=success_embed("�뚰떚 ��젣 �꾨즺"))


@bot.command(name="�ㅽ떚��")
async def pfx_sticky_set(ctx: commands.Context, *, �댁슜: str):
    if not is_admin_ctx(ctx):
        return await ctx.send(embed=error_embed("沅뚰븳 �놁쓬"))
    existing = get_sticky(ctx.channel.id)
    if existing:
        try:
            old = await ctx.channel.fetch_message(existing[1])
            await old.delete()
        except Exception:
            pass
    await send_sticky(ctx.channel, ctx.guild, �댁슜)
    await ctx.send(embed=success_embed("�ㅽ떚�� �ㅼ젙 �꾨즺"))


@bot.command(name="�ㅽ떚�ㅽ빐��")
async def pfx_sticky_remove(ctx: commands.Context):
    if not is_admin_ctx(ctx):
        return await ctx.send(embed=error_embed("沅뚰븳 �놁쓬"))
    existing = get_sticky(ctx.channel.id)
    if not existing:
        return await ctx.send(embed=warn_embed("�ㅽ떚�� �놁쓬"))
    try:
        old = await ctx.channel.fetch_message(existing[1])
        await old.delete()
    except Exception:
        pass
    del_sticky(ctx.channel.id)
    await ctx.send(embed=success_embed("�ㅽ떚�� �댁젣 �꾨즺"))


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    await bot.process_commands(message)
    if not message.guild:
        return
    await process_chat_xp(message)
    sticky = get_sticky(message.channel.id)
    if not sticky:
        return
    content, old_id = sticky
    try:
        old_msg = await message.channel.fetch_message(old_id)
        await old_msg.delete()
    except Exception:
        pass
    await send_sticky(message.channel, message.guild, content)


@bot.event
async def on_member_join(member: discord.Member):
    cfg = get_cfg(member.guild.id)
    if not cfg["welcome_ch"]:
        return
    channel = member.guild.get_channel(cfg["welcome_ch"])
    if not channel:
        return
    e = discord.Embed(
        title="�몝 �덈줈�� 硫ㅻ쾭 �낆옣!",
        description=f"{member.mention} ��, **{member.guild.name}** �� �ㅼ떊 寃껋쓣 �섏쁺�⑸땲��!\n\n> �쒕쾭 洹쒖튃�� 瑗� �쎌뼱蹂댁꽭��.\n> �몄쬆�� �꾨즺�섎㈃ �� 留롮� 梨꾨꼸�� �댁슜�� �� �덉뒿�덈떎.",
        color=0x57F287,
        timestamp=datetime.datetime.utcnow(),
    )
    e.set_thumbnail(url=member.display_avatar.url)
    e.set_footer(text=f"�꾩옱 硫ㅻ쾭 ��: {member.guild.member_count}紐�")
    await channel.send(embed=e)


@bot.event
async def on_member_remove(member: discord.Member):
    cfg = get_cfg(member.guild.id)
    if not cfg["log_ch"]:
        return
    channel = member.guild.get_channel(cfg["log_ch"])
    if not channel:
        return
    e = discord.Embed(
        title="�몝 硫ㅻ쾭 �댁옣",
        description=f"**{member}** �섏씠 �쒕쾭瑜� �좊궗�듬땲��.",
        color=0xED4245,
        timestamp=datetime.datetime.utcnow(),
    )
    e.set_thumbnail(url=member.display_avatar.url)
    e.set_footer(text=f"�꾩옱 硫ㅻ쾭 ��: {member.guild.member_count}紐�")
    await channel.send(embed=e)


@bot.event
async def on_ready():
    global bot_ready_synced
    if bot_ready_synced:
        return
    init_db()
    for view in [VerifyView(), TicketView(), TicketCloseView(), PartyView(), AdminPanel()]:
        bot.add_view(view)
    synced = await bot.tree.sync()
    bot_ready_synced = True
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="�쒕쾭 愿�由� 以� ��"))
    print(f"�뵦 QUABOT READY | {bot.user} ({bot.user.id})")
    print(f"�� Slash commands synced: {len(synced)}")


async def start_bot():
    if not TOKEN:
        raise RuntimeError("TOKEN environment variable is not set.")
    while True:
        try:
            print("Starting QUABOT...")
            await bot.start(TOKEN)
        except discord.LoginFailure:
            print("Invalid Discord bot token. Check your TOKEN environment variable.")
            break
        except KeyboardInterrupt:
            print("Bot stopped by user.")
            break
        except Exception as e:
            print(f"Bot crashed: {e}")
            print("Restarting in 10 seconds...")
            try:
                await bot.close()
            except Exception:
                pass
            await asyncio.sleep(10)


asyncio.run(start_bot())