import asyncio
import json
import sys
import uuid
import urllib.request
import urllib.error
from urllib.parse import unquote

from io import BytesIO

from pyrogram import Client
from pyrogram.raw import functions, types as raw_types
from pyrogram.raw.core import TLObject
from pyrogram.raw.core.primitives import Int, Long, String
from pyrogram.raw.all import objects as raw_objects


class WebViewResultUrl(TLObject):
    """Manual implementation of types.webViewResultUrl#4d22ff98
    (respons dari RequestMainWebView, juga belum ada di schema bawaan)."""

    ID = 0x4D22FF98
    QUALNAME = "types.WebViewResultUrl"

    __slots__ = ["url", "query_id", "fullsize", "fullscreen"]

    def __init__(self, *, url: str, query_id: int = None, fullsize: bool = None, fullscreen: bool = None):
        self.url = url
        self.query_id = query_id
        self.fullsize = fullsize
        self.fullscreen = fullscreen

    @staticmethod
    def read(b: BytesIO, *args):
        flags = Int.read(b)
        fullsize = bool(flags & (1 << 1))
        fullscreen = bool(flags & (1 << 2))
        query_id = Long.read(b) if flags & (1 << 0) else None
        url = String.read(b)
        return WebViewResultUrl(url=url, query_id=query_id, fullsize=fullsize, fullscreen=fullscreen)

    def write(self, *args) -> bytes:
        raise NotImplementedError("WebViewResultUrl cuma dipakai buat baca respons")


class RequestMainWebView(TLObject):
    """Manual implementation of messages.requestMainWebView#c9e01e7b
    (belum ada di schema bawaan pyrogram official)."""

    ID = 0xC9E01E7B
    QUALNAME = "functions.messages.RequestMainWebView"

    __slots__ = ["peer", "bot", "platform", "compact", "fullscreen", "start_param", "theme_params"]

    def __init__(self, *, peer, bot, platform: str, compact: bool = None,
                 fullscreen: bool = None, start_param: str = None, theme_params=None):
        self.peer = peer
        self.bot = bot
        self.platform = platform
        self.compact = compact
        self.fullscreen = fullscreen
        self.start_param = start_param
        self.theme_params = theme_params

    @staticmethod
    def read(b: BytesIO, *args):
        flags = Int.read(b)
        compact = bool(flags & (1 << 7))
        fullscreen = bool(flags & (1 << 8))
        peer = TLObject.read(b)
        bot = TLObject.read(b)
        start_param = String.read(b) if flags & (1 << 1) else None
        theme_params = TLObject.read(b) if flags & (1 << 0) else None
        platform = String.read(b)
        return RequestMainWebView(
            peer=peer, bot=bot, platform=platform, compact=compact,
            fullscreen=fullscreen, start_param=start_param, theme_params=theme_params,
        )

    def write(self, *args) -> bytes:
        b = BytesIO()
        b.write(Int(self.ID, False))

        flags = 0
        flags |= (1 << 7) if self.compact else 0
        flags |= (1 << 8) if self.fullscreen else 0
        flags |= (1 << 1) if self.start_param is not None else 0
        flags |= (1 << 0) if self.theme_params is not None else 0
        b.write(Int(flags))

        b.write(self.peer.write())
        b.write(self.bot.write())

        if self.start_param is not None:
            b.write(String(self.start_param))
        if self.theme_params is not None:
            b.write(self.theme_params.write())

        b.write(String(self.platform))
        return b.getvalue()


raw_objects[RequestMainWebView.ID] = RequestMainWebView
raw_objects[WebViewResultUrl.ID] = WebViewResultUrl


BOT_USERNAME = "wisplings_bot"
START_PARAM = "gGFvMANX--M"
BASE_URL = "https://rymkmhxxiyfdmblzqrnt.supabase.co/functions/v1"
ORIGIN = "https://wisplings.vercel.app"

# WAJIB diisi sama api_id/api_hash yang dipakai pas generate sessions.txt
API_ID = 0  # ganti dengan api_id lu
API_HASH = ""  # ganti dengan api_hash lu

SESSIONS_FILE = "sessions.txt"
TOKENS_FILE = "tokens.txt"


def load_sessions(path):
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def select_sessions(sessions):
    print(f"Total akun di {SESSIONS_FILE}: {len(sessions)}")
    print("1. Satu akun (pilih index)")
    print("2. Semua akun")
    print("3. Dari index X sampai akhir")
    choice = input("Pilih mode [1/2/3]: ").strip()

    if choice == "1":
        idx = int(input(f"Index akun (1-{len(sessions)}): ").strip())
        return [sessions[idx - 1]]
    elif choice == "2":
        return sessions
    elif choice == "3":
        start = int(input(f"Mulai dari index (1-{len(sessions)}): ").strip())
        return sessions[start - 1:]
    else:
        print("Pilihan tidak valid, keluar.")
        sys.exit(1)


def http_post(url, headers, body_dict):
    data = json.dumps(body_dict).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    for k, v in headers.items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        try:
            return e.code, json.loads(body)
        except json.JSONDecodeError:
            return e.code, {"raw": body}


def base_headers(idem_key, token=None):
    h = {
        "Content-Type": "application/json",
        "Origin": ORIGIN,
        "Referer": ORIGIN + "/",
        "Idempotency-Key": idem_key,
    }
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


async def get_init_data(session_string):
    """Pakai akun Telegram (Pyrogram session string) buat 'buka' mini app Wisplings dan ambil initData mentah."""
    app = Client(
        name="acc",
        api_id=API_ID,
        api_hash=API_HASH,
        session_string=session_string,
        in_memory=True,
    )
    async with app:
        peer = await app.resolve_peer(BOT_USERNAME)
        bot_input_user = raw_types.InputUser(
            user_id=peer.user_id, access_hash=peer.access_hash
        )
        result = await app.invoke(
            RequestMainWebView(
                peer=peer,
                bot=bot_input_user,
                platform="android",
                start_param=START_PARAM,
            )
        )
        url = result.url
        if "tgWebAppData=" not in url:
            raise RuntimeError(f"tgWebAppData tidak ditemukan di URL: {url}")
        frag = url.split("tgWebAppData=", 1)[1]
        init_data = frag.split("&", 1)[0]
        return unquote(init_data)


async def auth_telegram(init_data):
    url = f"{BASE_URL}/auth-telegram"
    headers = base_headers(f"login:{uuid.uuid4()}")
    return await asyncio.to_thread(http_post, url, headers, {"initData": init_data})


async def onboarding_action(token, action):
    url = f"{BASE_URL}/onboarding-action"
    headers = base_headers(f"tutorial-{action.lower()}:{uuid.uuid4()}", token)
    return await asyncio.to_thread(http_post, url, headers, {"action": action})


async def process_account(index, session_string):
    print(f"\n[{index}] Membuka mini app Wisplings...")
    try:
        init_data = await get_init_data(session_string)
    except Exception as e:
        print(f"[{index}] Gagal ambil initData: {e}")
        return

    status, auth_resp = await auth_telegram(init_data)
    if status != 200 or not auth_resp.get("ok"):
        print(f"[{index}] auth-telegram gagal ({status}): {auth_resp}")
        return

    data = auth_resp["data"]
    token = data["token"]
    user = data["user"]
    print(f"[{index}] Login sukses: @{user.get('username')} (id {user.get('telegramId')}), newUser={data.get('isNewUser')}")

    with open(TOKENS_FILE, "a", encoding="utf-8") as f:
        f.write(f"{user.get('telegramId')}|{user.get('username')}|{token}\n")

    status, begin_resp = await onboarding_action(token, "BEGIN")
    if status == 200 and begin_resp.get("ok"):
        stage = begin_resp["data"].get("stage")
        print(f"[{index}] onboarding BEGIN sukses, stage sekarang: {stage}")
    else:
        print(f"[{index}] onboarding BEGIN gagal ({status}): {begin_resp}")


async def main():
    sessions = load_sessions(SESSIONS_FILE)
    if not sessions:
        print(f"{SESSIONS_FILE} kosong.")
        return

    selected = select_sessions(sessions)
    print(f"\nMemproses {len(selected)} akun...\n")

    for i, s in enumerate(selected, start=1):
        await process_account(i, s)
        await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(main())
