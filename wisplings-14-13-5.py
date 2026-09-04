# ====== KONFIGURASI (isi dulu sebelum run) ======
API_ID = 0        # ganti dengan api_id lu
API_HASH = ""      # ganti dengan api_hash lu

BOT_USERNAME = "wisplings_bot"
START_PARAM = "gGFvMANX--M"
BASE_URL = "https://rymkmhxxiyfdmblzqrnt.supabase.co/functions/v1"
ORIGIN = "https://wisplings.vercel.app"

SESSIONS_FILE = "sessions.txt"
TOKENS_FILE = "tokens.txt"

# Katalog item shop-buy / care-use.
# slug espresso, snack, wipe udah konfirmed dari capture network asli.
# Sisanya (double-shot, energy-drink, full-charge, meal, feast, banquet,
# sponge, bath, royal-spa) masih tebakan dari nama tampilan -> slug
# (lowercase, spasi jadi strip "-", bukan underscore -- item energy selain
# espresso kemarin gagal pas dites pakai underscore).
# Kalau ternyata ada yang masih salah pas dicoba, tinggal betulin slug di
# sini aja, gak usah ubah logic lain.
ITEM_CATALOG = {
    "energy": [
        {"slug": "espresso", "name": "Espresso", "price": 20},
        {"slug": "double-shot", "name": "Double Shot", "price": 60},
        {"slug": "energy-drink", "name": "Energy Drink", "price": 180},
        {"slug": "full-charge", "name": "Full Charge", "price": 900},
    ],
    "food": [
        {"slug": "snack", "name": "Snack", "price": 20},
        {"slug": "meal", "name": "Meal", "price": 60},
        {"slug": "feast", "name": "Feast", "price": 180},
        {"slug": "banquet", "name": "Banquet", "price": 900},
    ],
    "wash": [
        {"slug": "wipe", "name": "Wipe", "price": 20},
        {"slug": "sponge", "name": "Sponge", "price": 60},
        {"slug": "bath", "name": "Bath", "price": 180},
        {"slug": "royal-spa", "name": "Royal Spa", "price": 900},
    ],
}
# Mapping kategori item -> field needs di spirit
CATEGORY_TO_NEED = {
    "energy": "energy",
    "food": "food",
    "wash": "clean",
}

# Restore bps per item (dari capture network). Dipakai buat estimasi cap quantity
# sebelum kirim request. Kalau slug gak ada di sini, fallback ke kirim 1x dulu.
ITEM_RESTORE_BPS = {
    "espresso": 624,
    "double-shot": 1872,
    "energy-drink": 5616,
    "full-charge": 10000,
    "snack": 624,
    "meal": 1872,
    "feast": 5616,
    "banquet": 10000,
    "wipe": 624,
    "sponge": 1872,
    "bath": 5616,
    "royal-spa": 10000,
}

CAP_BPS = 10000  # 100% — stop pake item kalau nambah 1x udah bakal overflow


def calc_capped_quantity(current_bps: int, restore_bps: int, requested_qty: int) -> int:
    """Hitung berapa quantity yang perlu dipake supaya gak overflow 100%.
    Return 0 kalau udah penuh atau nambah 1x aja udah bakal lewat 100%."""
    if current_bps + restore_bps > CAP_BPS:
        return 0
    needed = CAP_BPS - current_bps
    max_qty = needed // restore_bps
    return min(requested_qty, max_qty)



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


def load_sessions(path):
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def load_tokens(path):
    """Baca TOKENS_FILE. Format per baris: telegramId|username|token|spiritId
    (spiritId opsional, buat baris lama yang cuma 3 kolom bakal None)."""
    tokens = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split("|")
            if len(parts) < 3:
                continue
            tokens.append({
                "telegramId": parts[0],
                "username": parts[1],
                "token": parts[2],
                "spiritId": parts[3] if len(parts) > 3 and parts[3] else None,
            })
    return tokens


def select_indexed(items, label, describe=None):
    print(f"Total akun di {label}: {len(items)}")
    if describe:
        for i, it in enumerate(items, start=1):
            print(f"  {i}. {describe(it)}")
    print("1. Satu akun (pilih index)")
    print("2. Semua akun")
    print("3. Dari index X sampai akhir")
    print("4. Beberapa akun (pisah koma, misal: 1,6,8,5,10)")
    choice = input("Pilih mode [1/2/3/4]: ").strip()

    if choice == "1":
        idx = int(input(f"Index akun (1-{len(items)}): ").strip())
        return [items[idx - 1]]
    elif choice == "2":
        return items
    elif choice == "3":
        start = int(input(f"Mulai dari index (1-{len(items)}): ").strip())
        return items[start - 1:]
    elif choice == "4":
        raw = input(f"Index akun, pisah koma (1-{len(items)}), misal 1,6,8,5,10: ").strip()
        result = []
        for part in raw.split(","):
            part = part.strip()
            if not part:
                continue
            idx = int(part)
            if 1 <= idx <= len(items):
                result.append(items[idx - 1])
        if not result:
            print("Gak ada index valid, keluar.")
            sys.exit(1)
        return result
    else:
        print("Pilihan tidak valid, keluar.")
        sys.exit(1)


def select_sessions(sessions):
    return select_indexed(sessions, SESSIONS_FILE)


def select_tokens(tokens):
    return select_indexed(
        tokens, TOKENS_FILE,
        describe=lambda t: f"@{t['username']} (id {t['telegramId']})"
    )


def save_tokens(path, tokens):
    with open(path, "w", encoding="utf-8") as f:
        for t in tokens:
            f.write(f"{t['telegramId']}|{t['username']}|{t['token']}|{t.get('spiritId') or ''}\n")


def pick_categories():
    cats = list(ITEM_CATALOG.keys())
    print("Pilih kategori (bisa gabung, pisahkan koma):")
    for i, c in enumerate(cats, start=1):
        print(f"{i}. {c}")
    print("Contoh: '1' = 1 kategori, '1,2' = 2 kategori, '1,2,3' = semua")
    raw = input("Pilihan: ").strip()
    selected = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        idx = int(part)
        if 1 <= idx <= len(cats) and cats[idx - 1] not in selected:
            selected.append(cats[idx - 1])
    if not selected:
        print("Pilihan tidak valid, keluar.")
        sys.exit(1)
    return selected


def pick_item(category):
    items = ITEM_CATALOG[category]
    print(f"Pilih item ({category}):")
    for i, it in enumerate(items, start=1):
        print(f"{i}. {it['name']} - {it['price']} wisp (slug: {it['slug']})")
    idx = int(input("Pilihan: ").strip())
    return items[idx - 1]


def ask_quantity():
    raw = input("Jumlah (default 1): ").strip()
    return int(raw) if raw else 1


def pick_chest(chests):
    print("Pilih chest (cuma yang bisa dibeli pake WISP):")
    for i, c in enumerate(chests, start=1):
        price = c.get("nextPriceWisp") or c.get("priceWisp")
        print(f"{i}. {c['name']} - harga sekarang: {price} wisp "
              f"(naik tiap beli, cap {c.get('priceCapWisp')}, udah dimiliki: {c.get('ownedCount')})")
    idx = int(input("Pilihan: ").strip())
    return chests[idx - 1]


def pick_spirit_target():
    print("Target spirit buat item ini:")
    print("1. Cuma spirit aktif")
    print("2. Semua spirit yang dimiliki akun")
    choice = input("Pilihan [1/2]: ").strip()
    return choice


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


def http_get(url, headers):
    req = urllib.request.Request(url, method="GET")
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

        # kirim /start dengan parameter reff dulu, banyak sistem referral bot
        # baru ke-track lewat command ini, bukan cuma dari startapp mini app
        try:
            await app.invoke(
                functions.messages.StartBot(
                    bot=bot_input_user,
                    peer=peer,
                    random_id=uuid.uuid4().int & ((1 << 63) - 1),
                    start_param=START_PARAM,
                )
            )
            await asyncio.sleep(2)
        except Exception as e:
            pass

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


async def care_use(token, spirit_id, item_slug, quantity=1):
    url = f"{BASE_URL}/care-use"
    headers = base_headers(f"care-batch:{uuid.uuid4()}", token)
    body = {"actions": [{"spiritId": spirit_id, "itemSlug": item_slug, "quantity": quantity}]}
    return await asyncio.to_thread(http_post, url, headers, body)


async def shop_buy(token, item_slug, quantity=1):
    url = f"{BASE_URL}/shop-buy"
    headers = base_headers(f"buy:{uuid.uuid4()}", token)
    body = {"itemSlug": item_slug, "quantity": quantity}
    return await asyncio.to_thread(http_post, url, headers, body)


async def game_bootstrap(token):
    """GET game-bootstrap -> ambil data.home.activeSpirit.id (spiritId akun ini)."""
    url = f"{BASE_URL}/game-bootstrap"
    headers = base_headers(f"bootstrap:{uuid.uuid4()}", token)
    return await asyncio.to_thread(http_get, url, headers)


async def collection_overview(token):
    url = f"{BASE_URL}/collection-overview"
    headers = base_headers(f"collection-overview:{uuid.uuid4()}", token)
    return await asyncio.to_thread(http_get, url, headers)


async def fetch_spirits(token):
    """Ambil semua spirit yang dimiliki akun ini lewat collection-overview."""
    status, resp = await collection_overview(token)
    if status in (200, 201) and resp.get("ok"):
        return resp["data"].get("spirits", [])
    return []


async def chests_catalog(token):
    url = f"{BASE_URL}/chests-catalog"
    headers = base_headers(f"chests-catalog:{uuid.uuid4()}", token)
    return await asyncio.to_thread(http_get, url, headers)


async def fetch_wisp_chests(token):
    """Cuma ambil chest yang purchaseCurrency-nya WISP (yang lain pakai Stars/TON,
    di luar scope skrip ini)."""
    status, resp = await chests_catalog(token)
    if status in (200, 201) and resp.get("ok"):
        defs = resp["data"].get("definitions", [])
        return [d for d in defs if d.get("purchaseCurrency") == "WISP"]
    return []


async def chest_buy(token, chest_slug):
    url = f"{BASE_URL}/chest-buy"
    headers = base_headers(f"chest-buy:{uuid.uuid4()}", token)
    body = {"chestSlug": chest_slug}
    return await asyncio.to_thread(http_post, url, headers, body)


async def chest_open(token, chest_instance_id):
    url = f"{BASE_URL}/chest-open"
    headers = base_headers(f"chest-open:{uuid.uuid4()}", token)
    body = {"chestInstanceId": chest_instance_id}
    return await asyncio.to_thread(http_post, url, headers, body)


async def slot_buy(token):
    url = f"{BASE_URL}/slot-buy"
    headers = base_headers(f"slot:{uuid.uuid4()}", token)
    return await asyncio.to_thread(http_post, url, headers, {})


async def fetch_spirit_id(token):
    status, resp = await game_bootstrap(token)
    if status in (200, 201) and resp.get("ok"):
        try:
            return resp["data"]["home"]["activeSpirit"]["id"]
        except (KeyError, TypeError):
            return None
    return None


async def fetch_balance(token):
    """Ambil balanceCoins (wisp) dari game-bootstrap. Return None kalau gagal."""
    status, resp = await game_bootstrap(token)
    if status in (200, 201) and resp.get("ok"):
        try:
            return resp["data"]["home"]["balanceCoins"]
        except (KeyError, TypeError):
            return None
    return None


async def mining_collect(token):
    url = f"{BASE_URL}/mining-collect"
    headers = base_headers(f"collect:{uuid.uuid4()}", token)
    return await asyncio.to_thread(http_post, url, headers, {})


async def daily_claim(token):
    url = f"{BASE_URL}/daily-claim"
    headers = base_headers(f"daily-claim:{uuid.uuid4()}", token)
    return await asyncio.to_thread(http_post, url, headers, {})


async def run_onboarding_step(index, token, action, retries=3):
    for attempt in range(1, retries + 1):
        status, resp = await onboarding_action(token, action)
        if status in (200, 201) and resp.get("ok"):
            stage = resp["data"].get("stage")
            print(f"[{index}] onboarding {action} sukses, stage: {stage}")
            return resp["data"]
        if status == 500 and attempt < retries:
            wait = 2 * attempt
            print(f"[{index}] onboarding {action} gagal 500, retry {attempt}/{retries} dalam {wait}s...")
            await asyncio.sleep(wait)
            continue
        print(f"[{index}] onboarding {action} gagal ({status}): {resp}")
        return None


async def run_care_step(index, token, spirit_id, item_slug, retries=3):
    for attempt in range(1, retries + 1):
        status, resp = await care_use(token, spirit_id, item_slug)
        if status in (200, 201) and resp.get("ok"):
            stage = resp["data"].get("onboardingStage")
            print(f"[{index}] care-use {item_slug} sukses, onboardingStage: {stage}")
            return resp["data"]
        if status == 500 and attempt < retries:
            wait = 2 * attempt
            print(f"[{index}] care-use {item_slug} gagal 500, retry {attempt}/{retries} dalam {wait}s...")
            await asyncio.sleep(wait)
            continue
        print(f"[{index}] care-use {item_slug} gagal ({status}): {resp}")
        return None


async def run_buy_step(index, token, item_slug, quantity, retries=3):
    for attempt in range(1, retries + 1):
        status, resp = await shop_buy(token, item_slug, quantity)
        if status in (200, 201) and resp.get("ok"):
            d = resp["data"]
            print(f"[{index}] buy {item_slug} x{quantity} sukses. "
                  f"spentCoins: {d.get('spentCoins')}, balanceCoins: {d.get('balanceCoins')}, "
                  f"quantityOwned: {d.get('quantityOwned')}")
            return d
        if status == 500 and attempt < retries:
            wait = 2 * attempt
            print(f"[{index}] buy {item_slug} gagal 500, retry {attempt}/{retries} dalam {wait}s...")
            await asyncio.sleep(wait)
            continue
        print(f"[{index}] buy {item_slug} gagal ({status}): {resp}")
        return None


async def run_use_step(index, token, spirit_id, item_slug, quantity, retries=3):
    for attempt in range(1, retries + 1):
        status, resp = await care_use(token, spirit_id, item_slug, quantity)
        if status in (200, 201) and resp.get("ok"):
            d = resp["data"]
            result = (d.get("results") or [{}])[0]
            print(f"[{index}] use {item_slug} x{quantity} sukses. "
                  f"xpGained: {result.get('xpGained')}, levelAfter: {result.get('levelAfter')}, "
                  f"quantityOwned: {result.get('quantityOwned')}")
            return d
        if status == 500 and attempt < retries:
            wait = 2 * attempt
            print(f"[{index}] use {item_slug} gagal 500, retry {attempt}/{retries} dalam {wait}s...")
            await asyncio.sleep(wait)
            continue
        print(f"[{index}] use {item_slug} gagal ({status}): {resp}")
        return None


async def run_mining_step(index, token, retries=3):
    for attempt in range(1, retries + 1):
        status, resp = await mining_collect(token)
        if status in (200, 201) and resp.get("ok"):
            d = resp["data"]
            print(f"[{index}] claim mining sukses. collectedCoins: {d.get('collectedCoins')}, "
                  f"balanceCoins: {d.get('balanceCoins')}, "
                  f"nextCollectInSeconds: {d.get('nextCollectInSeconds')}, "
                  f"effectiveMiningPerHour: {d.get('effectiveMiningPerHour')}")
            return d
        if status == 500 and attempt < retries:
            wait = 2 * attempt
            print(f"[{index}] claim mining gagal 500, retry {attempt}/{retries} dalam {wait}s...")
            await asyncio.sleep(wait)
            continue
        print(f"[{index}] claim mining gagal ({status}): {resp}")
        return None


async def run_daily_claim_step(index, token, retries=3):
    for attempt in range(1, retries + 1):
        status, resp = await daily_claim(token)
        if status in (200, 201) and resp.get("ok"):
            d = resp["data"]
            print(f"[{index}] claim daily sukses. rewardCoins: {d.get('rewardCoins')}, "
                  f"rewardXp: {d.get('rewardXp')}, bonusCoins: {(d.get('bonus') or {}).get('coins')}, "
                  f"balanceCoins: {d.get('balanceCoins')}, streakDay: {d.get('streakDay')}, "
                  f"consecutiveDays: {d.get('consecutiveDays')}")
            return d
        if status == 500 and attempt < retries:
            wait = 2 * attempt
            print(f"[{index}] claim daily gagal 500, retry {attempt}/{retries} dalam {wait}s...")
            await asyncio.sleep(wait)
            continue
        print(f"[{index}] claim daily gagal ({status}): {resp}")
        return None


async def run_chest_buy_step(index, token, chest_slug, retries=3):
    for attempt in range(1, retries + 1):
        status, resp = await chest_buy(token, chest_slug)
        if status in (200, 201) and resp.get("ok"):
            d = resp["data"]
            print(f"[{index}] beli {d.get('chestSlug', chest_slug)} sukses. "
                  f"spentWisp: {d.get('spentWisp')}, balanceWisp: {d.get('balanceWisp')}, "
                  f"nextPriceWisp: {d.get('nextPriceWisp')}")
            return d
        if status == 500 and attempt < retries:
            wait = 2 * attempt
            print(f"[{index}] beli chest gagal 500, retry {attempt}/{retries} dalam {wait}s...")
            await asyncio.sleep(wait)
            continue
        print(f"[{index}] beli chest gagal ({status}): {resp}")
        return None


async def run_chest_open_step(index, token, chest_instance_id, retries=3):
    for attempt in range(1, retries + 1):
        status, resp = await chest_open(token, chest_instance_id)
        if status in (200, 201) and resp.get("ok"):
            d = resp["data"]
            spirit = d.get("resultSpirit") or {}
            print(f"[{index}] buka chest sukses. dapet {spirit.get('name')} "
                  f"({d.get('resultRarity')}), spiritId: {spirit.get('id')}")
            return d
        if status == 500 and attempt < retries:
            wait = 2 * attempt
            print(f"[{index}] buka chest gagal 500, retry {attempt}/{retries} dalam {wait}s...")
            await asyncio.sleep(wait)
            continue
        print(f"[{index}] buka chest gagal ({status}): {resp}")
        return None


async def run_slot_buy_step(index, token, retries=3):
    for attempt in range(1, retries + 1):
        status, resp = await slot_buy(token)
        if status in (200, 201) and resp.get("ok"):
            d = resp["data"]
            print(f"[{index}] beli slot sukses. slotNumber: {d.get('slotNumber')}, "
                  f"maxSlots: {d.get('maxSlots')}, spentCoins: {d.get('spentCoins')}, "
                  f"balanceCoins: {d.get('balanceCoins')}, nextPriceCoins: {d.get('nextPriceCoins')}")
            return d
        if status == 500 and attempt < retries:
            wait = 2 * attempt
            print(f"[{index}] beli slot gagal 500, retry {attempt}/{retries} dalam {wait}s...")
            await asyncio.sleep(wait)
            continue
        print(f"[{index}] beli slot gagal ({status}): {resp}")
        return None


async def login_account(index, session_string):
    """2 step paling awal doang: buka initData + auth-telegram.
    Return dict {telegramId, username, token} kalau sukses, None kalau gagal."""
    print(f"\n[{index}] Membuka mini app Wisplings...")

    init_data = None
    for attempt in range(1, 3):
        try:
            init_data = await get_init_data(session_string)
            break
        except Exception as e:
            print(f"[{index}] Gagal ambil initData (percobaan {attempt}/2): {e}")
            if attempt < 2:
                await asyncio.sleep(3)
    if not init_data:
        print(f"[{index}] GAGAL TOTAL ambil initData, akun ini di-skip.")
        return None

    status, auth_resp = None, None
    for attempt in range(1, 3):
        status, auth_resp = await auth_telegram(init_data)
        if status in (200, 201) and auth_resp.get("ok"):
            break
        print(f"[{index}] auth-telegram gagal (percobaan {attempt}/2) ({status}): {auth_resp}")
        if attempt < 2:
            await asyncio.sleep(3)
    if status not in (200, 201) or not auth_resp.get("ok"):
        print(f"[{index}] GAGAL TOTAL auth-telegram, akun ini di-skip.")
        return None

    data = auth_resp["data"]
    user = data["user"]
    print(f"[{index}] Login sukses: @{user.get('username')} (id {user.get('telegramId')}), newUser={data.get('isNewUser')}")
    return {"telegramId": user.get("telegramId"), "username": user.get("username"), "token": data["token"]}


async def process_account(index, session_string):
    logged_in = await login_account(index, session_string)
    if not logged_in:
        return False

    token = logged_in["token"]
    user = {"telegramId": logged_in["telegramId"], "username": logged_in["username"]}

    spirit_id = None

    onb = await run_onboarding_step(index, token, "BEGIN")
    if not onb:
        print(f"[{index}] BEGIN gagal, skip lanjut ke step berikutnya...")
    await asyncio.sleep(1)

    onb = await run_onboarding_step(index, token, "OPEN_STARTER")
    if onb:
        spirit_id = onb.get("starterSpirit", {}).get("id")
    else:
        print(f"[{index}] OPEN_STARTER gagal, skip lanjut ke step berikutnya...")
    await asyncio.sleep(1)

    onb = await run_onboarding_step(index, token, "ACCEPT_SPIRIT")
    if not onb:
        print(f"[{index}] ACCEPT_SPIRIT gagal, skip lanjut ke step berikutnya...")
    await asyncio.sleep(1)

    onb = await run_onboarding_step(index, token, "CLAIM_STARTER_KIT")
    if not onb:
        print(f"[{index}] CLAIM_STARTER_KIT gagal, skip lanjut ke step berikutnya...")
    await asyncio.sleep(3)

    if spirit_id:
        # urutan ngikutin nama stage: CARE_FOOD->snack, CARE_ENERGY->espresso, CARE_CLEAN->wipe
        for slug in ("snack", "espresso", "wipe"):
            care = await run_care_step(index, token, spirit_id, slug)
            if not care:
                print(f"[{index}] care-use {slug} gagal, skip lanjut...")
            await asyncio.sleep(1)
    else:
        print(f"[{index}] spiritId gak ketemu (OPEN_STARTER gagal), skip semua care-use.")

    onb = await run_onboarding_step(index, token, "CLAIM_REWARD")
    if onb:
        print(f"[{index}] Onboarding selesai. rewardWisp: {onb.get('rewardWisp')}, balanceWisp: {onb.get('balanceWisp')}")
    else:
        print(f"[{index}] CLAIM_REWARD gagal.")

    # tulis token (+ spiritId kalau ketemu) di akhir, biar mode buy/use/claim
    # mining bisa langsung pakai dari TOKENS_FILE tanpa login ulang.
    with open(TOKENS_FILE, "a", encoding="utf-8") as f:
        f.write(f"{user.get('telegramId')}|{user.get('username')}|{token}|{spirit_id or ''}\n")
    return True


async def run_register_quick_mode():
    """Mode Register cepat: cuma buka initData + auth-telegram (2 step awal),
    tanpa onboarding (BEGIN/OPEN_STARTER/dst). SpiritId bakal kosong dan
    otomatis di-fetch lewat game-bootstrap pas mode Use jalan nanti."""
    sessions = load_sessions(SESSIONS_FILE)
    if not sessions:
        print(f"{SESSIONS_FILE} kosong.")
        return

    selected = select_sessions(sessions)

    open(TOKENS_FILE, "w", encoding="utf-8").close()

    print(f"\nLogin cepat {len(selected)} akun (tanpa onboarding)...\n")

    sukses = 0
    gagal = []
    for i, s in enumerate(selected, start=1):
        logged_in = await login_account(i, s)
        if logged_in:
            with open(TOKENS_FILE, "a", encoding="utf-8") as f:
                f.write(f"{logged_in['telegramId']}|{logged_in['username']}|{logged_in['token']}|\n")
            sukses += 1
        else:
            gagal.append(i)
        await asyncio.sleep(2)

    print(f"\n=== Ringkasan Register Cepat ===")
    print(f"Sukses: {sukses}/{len(selected)}")
    if gagal:
        print(f"Gagal di index: {gagal} (cek log di atas buat alasannya)")
    print(f"spiritId belum ada buat akun baru -> bakal auto-fetch pas mode Use jalan.")


async def run_register_mode():
    sessions = load_sessions(SESSIONS_FILE)
    if not sessions:
        print(f"{SESSIONS_FILE} kosong.")
        return

    selected = select_sessions(sessions)

    # tokens.txt selalu ditulis ulang dari nol tiap kali mode Register jalan,
    # biar gak perlu hapus manual dulu dan gak numpuk data lama/duplikat.
    open(TOKENS_FILE, "w", encoding="utf-8").close()

    print(f"\nMemproses {len(selected)} akun...\n")

    sukses = 0
    gagal = []
    for i, s in enumerate(selected, start=1):
        ok = await process_account(i, s)
        if ok:
            sukses += 1
        else:
            gagal.append(i)
        await asyncio.sleep(2)

    print(f"\n=== Ringkasan Register ===")
    print(f"Sukses: {sukses}/{len(selected)}")
    if gagal:
        print(f"Gagal di index: {gagal} (gak masuk {TOKENS_FILE}, cek log di atas buat alasannya)")


async def run_buy_mode():
    tokens = load_tokens(TOKENS_FILE)
    if not tokens:
        print(f"{TOKENS_FILE} kosong. Jalankan mode Register dulu.")
        return

    categories = pick_categories()
    tasks = []  # list of (item, quantity)
    for cat in categories:
        item = pick_item(cat)
        quantity = ask_quantity()
        tasks.append((item, quantity))

    selected = select_tokens(tokens)
    ringkasan = ", ".join(f"{it['name']} x{q}" for it, q in tasks)
    print(f"\nBeli [{ringkasan}] buat {len(selected)} akun...\n")

    for i, acc in enumerate(selected, start=1):
        print(f"[{i}] @{acc['username']} (id {acc['telegramId']})")
        for item, quantity in tasks:
            await run_buy_step(i, acc["token"], item["slug"], quantity)
            await asyncio.sleep(1)
        await asyncio.sleep(1)


async def run_use_mode():
    tokens = load_tokens(TOKENS_FILE)
    if not tokens:
        print(f"{TOKENS_FILE} kosong. Jalankan mode Register dulu.")
        return

    categories = pick_categories()
    tasks = []  # list of (item, quantity)
    for cat in categories:
        item = pick_item(cat)
        quantity = ask_quantity()
        tasks.append((item, quantity))

    target = pick_spirit_target()
    selected = select_tokens(tokens)
    ringkasan = ", ".join(f"{it['name']} x{q}" for it, q in tasks)
    print(f"\nPakai [{ringkasan}] buat {len(selected)} akun...\n")

    skipped_log = []  # [(akun_idx, username, spirit_name, item_name, alasan)]

    for i, acc in enumerate(selected, start=1):
        print(f"[{i}] @{acc['username']} (id {acc['telegramId']})")
        spirits = await fetch_spirits(acc["token"])
        if not spirits:
            print(f"[{i}] gak ketemu spirit sama sekali (collection-overview kosong/gagal), skip akun ini.")
            continue

        if target == "2":
            spirit_targets = spirits
        else:
            actives = [s for s in spirits if s.get("isActive")]
            spirit_targets = actives if actives else spirits[:1]

        for j, sp in enumerate(spirit_targets):
            print(f"[{i}] -> spirit {sp.get('name')} (id {sp.get('id')})")
            sp_needs = sp.get("needs", {})
            for item, quantity in tasks:
                cat = next((c for c, its in ITEM_CATALOG.items() for it in its if it["slug"] == item["slug"]), None)
                need_field = CATEGORY_TO_NEED.get(cat)
                restore_bps = ITEM_RESTORE_BPS.get(item["slug"])

                if need_field and restore_bps:
                    current_bps = sp_needs.get(need_field, 0)
                    actual_qty = calc_capped_quantity(current_bps, restore_bps, quantity)
                    pct = current_bps / 100
                    if actual_qty == 0:
                        print(f"[{i}] skip {item['name']} — {need_field} udah {pct:.1f}%, nambah 1x bakal overflow 100%.")
                        continue
                    if actual_qty < quantity:
                        print(f"[{i}] {item['name']}: {need_field} {pct:.1f}%, pake {actual_qty}x (dari {quantity}x) biar pas 100%.")
                    result = await run_use_step(i, acc["token"], sp["id"], item["slug"], actual_qty)
                    if result is None:
                        # gagal — kemungkinan stok habis
                        skipped_log.append((i, acc["username"], sp.get("name"), item["name"], "stok habis / request gagal"))
                    else:
                        # update needs lokal dari spiritUpdates
                        for su in result.get("spiritUpdates", []):
                            if su["id"] == sp["id"]:
                                sp_needs = su.get("needs", sp_needs)
                                break
                else:
                    result = await run_use_step(i, acc["token"], sp["id"], item["slug"], quantity)
                    if result is None:
                        skipped_log.append((i, acc["username"], sp.get("name"), item["name"], "stok habis / request gagal"))
                await asyncio.sleep(1)
            if j < len(spirit_targets) - 1:
                print(f"[{i}] jeda 30 detik sebelum spirit berikutnya...")
                await asyncio.sleep(30)
        await asyncio.sleep(1)

    if skipped_log:
        print("\n" + "=" * 60)
        print("RINGKASAN — spirit yang belum ke-top up (stok habis / gagal):")
        for akun_i, uname, spirit_name, item_name, alasan in skipped_log:
            print(f"  Akun [{akun_i}] @{uname} | Spirit: {spirit_name} | Item: {item_name} | Alasan: {alasan}")
        print("=" * 60)
    else:
        print("\nSemua spirit berhasil di-use tanpa masalah.")


async def run_claim_mining_mode():
    tokens = load_tokens(TOKENS_FILE)
    if not tokens:
        print(f"{TOKENS_FILE} kosong. Jalankan mode Register dulu.")
        return

    selected = select_tokens(tokens)
    print(f"\nClaim mining buat {len(selected)} akun...\n")

    for i, acc in enumerate(selected, start=1):
        print(f"[{i}] @{acc['username']} (id {acc['telegramId']})")
        await run_mining_step(i, acc["token"])
        await asyncio.sleep(1)


async def run_claim_daily_mode():
    tokens = load_tokens(TOKENS_FILE)
    if not tokens:
        print(f"{TOKENS_FILE} kosong. Jalankan mode Register dulu.")
        return

    selected = select_tokens(tokens)
    print(f"\nClaim daily reward buat {len(selected)} akun...\n")

    for i, acc in enumerate(selected, start=1):
        print(f"[{i}] @{acc['username']} (id {acc['telegramId']})")
        await run_daily_claim_step(i, acc["token"])
        await asyncio.sleep(1)


async def run_check_balance_mode():
    tokens = load_tokens(TOKENS_FILE)
    if not tokens:
        print(f"{TOKENS_FILE} kosong. Jalankan mode Register dulu.")
        return

    selected = select_tokens(tokens)
    print(f"\nCek balance wisp buat {len(selected)} akun...\n")

    total = 0
    for i, acc in enumerate(selected, start=1):
        balance = await fetch_balance(acc["token"])
        if balance is not None:
            print(f"[{i}] @{acc['username']} (id {acc['telegramId']}): {balance} wisp")
            total += balance
        else:
            print(f"[{i}] @{acc['username']} (id {acc['telegramId']}): gagal ambil balance")
        await asyncio.sleep(1)

    print(f"\nTotal balance ({len(selected)} akun): {total} wisp")


async def run_chest_mode():
    tokens = load_tokens(TOKENS_FILE)
    if not tokens:
        print(f"{TOKENS_FILE} kosong. Jalankan mode Register dulu.")
        return

    selected = select_tokens(tokens)

    print("Ambil daftar chest yang bisa dibeli pake WISP...")
    chests = await fetch_wisp_chests(selected[0]["token"])
    if not chests:
        print("Gak ketemu chest yang bisa dibeli pake WISP (mungkin sekarang semuanya pake Stars/TON).")
        return

    chest = pick_chest(chests)
    qty = ask_quantity()
    print(f"\nBeli & buka {chest['name']} (slug: {chest['slug']}) x{qty} buat {len(selected)} akun...\n")
    print("Catatan: harga naik otomatis tiap beli, skrip gak perlu hitung manual, tinggal panggil berkali-kali.\n")

    for i, acc in enumerate(selected, start=1):
        print(f"[{i}] @{acc['username']} (id {acc['telegramId']})")
        for n in range(qty):
            buy_d = await run_chest_buy_step(i, acc["token"], chest["slug"])
            if buy_d and buy_d.get("chestInstanceId"):
                await asyncio.sleep(1)
                await run_chest_open_step(i, acc["token"], buy_d["chestInstanceId"])
            await asyncio.sleep(1)
        await asyncio.sleep(1)


async def run_check_spirits_mode():
    tokens = load_tokens(TOKENS_FILE)
    if not tokens:
        print(f"{TOKENS_FILE} kosong. Jalankan mode Register dulu.")
        return

    selected = select_tokens(tokens)
    print(f"\nCek jumlah spirit buat {len(selected)} akun...\n")

    total = 0
    for i, acc in enumerate(selected, start=1):
        spirits = await fetch_spirits(acc["token"])
        print(f"[{i}] @{acc['username']} (id {acc['telegramId']}): {len(spirits)} spirit")
        for sp in spirits:
            aktif = " (aktif)" if sp.get("isActive") else ""
            print(f"      - {sp.get('name')} | level {sp.get('level')} | {sp.get('rarity')}{aktif} | id: {sp.get('id')}")
        total += len(spirits)
        await asyncio.sleep(1)

    print(f"\nTotal spirit ({len(selected)} akun): {total}")


async def run_slot_buy_mode():
    tokens = load_tokens(TOKENS_FILE)
    if not tokens:
        print(f"{TOKENS_FILE} kosong. Jalankan mode Register dulu.")
        return

    selected = select_tokens(tokens)
    qty = ask_quantity()
    print(f"\nBeli slot x{qty} buat {len(selected)} akun...\n")
    print("Catatan: harga naik tiap beli (nextPriceCoins), server yang atur, tinggal panggil berkali-kali.\n")

    for i, acc in enumerate(selected, start=1):
        print(f"[{i}] @{acc['username']} (id {acc['telegramId']})")
        for n in range(qty):
            await run_slot_buy_step(i, acc["token"])
            await asyncio.sleep(1)
        await asyncio.sleep(1)


async def run_debug_mode():
    """Mode 11: simpan raw JSON dari collection-overview (semua spirit)
    + 1x care-use ke spirit pertama pake espresso ke debug_response.json."""
    tokens = load_tokens(TOKENS_FILE)
    if not tokens:
        print(f"{TOKENS_FILE} kosong. Jalankan mode Register dulu.")
        return

    selected = select_tokens(tokens)
    acc = selected[0]
    print(f"\n[DEBUG] Pakai akun @{acc['username']} (id {acc['telegramId']})\n")

    debug_out = {}

    # 1. Raw collection-overview
    print("[DEBUG] Fetching collection-overview...")
    status, resp = await collection_overview(acc["token"])
    debug_out["collection_overview"] = {"status": status, "response": resp}

    spirits = resp.get("data", {}).get("spirits", [])
    if not spirits:
        print("[DEBUG] Gak ada spirit, stop.")
        with open("debug_response.json", "w", encoding="utf-8") as f:
            json.dump(debug_out, f, indent=2)
        print("[DEBUG] Disimpan ke debug_response.json")
        return

    sp = spirits[0]
    spirit_id = sp["id"]
    print(f"[DEBUG] Spirit pertama: {sp.get('name')} (id {spirit_id})")

    # 2. Raw care-use 1x espresso
    await asyncio.sleep(2)
    print("[DEBUG] Fetching care-use 1x espresso...")
    status2, resp2 = await care_use(acc["token"], spirit_id, "espresso", 1)
    debug_out["care_use_espresso"] = {"status": status2, "response": resp2}

    with open("debug_response.json", "w", encoding="utf-8") as f:
        json.dump(debug_out, f, indent=2)
    print("[DEBUG] Selesai. Hasil disimpan ke debug_response.json")


async def run_check_slots_mode():
    """Mode 12: tampilkan info slot spirit semua akun — used/max/limit + harga slot berikutnya."""
    tokens = load_tokens(TOKENS_FILE)
    if not tokens:
        print(f"{TOKENS_FILE} kosong. Jalankan mode Register dulu.")
        return

    selected = select_tokens(tokens)
    for i, acc in enumerate(selected, start=1):
        print(f"\n[{i}] @{acc['username']} (id {acc['telegramId']})")
        status, resp = await collection_overview(acc["token"])
        if status != 200 or not resp.get("ok"):
            print(f"[{i}] Gagal fetch collection-overview (status {status})")
            continue

        data = resp.get("data", {})
        slots = data.get("slots", {})
        used  = slots.get("used", "?")
        max_  = slots.get("max", "?")
        limit = slots.get("limit", "?")
        next_slot  = slots.get("nextSlot", "?")
        next_price = slots.get("nextPriceCoins", "?")
        balance    = data.get("balanceCoins", "?")

        print(f"[{i}] Slot terpakai : {used} / {max_} (maks bisa beli: {limit})")
        print(f"[{i}] Slot berikutnya: #{next_slot} — harga {next_price:,} coins")
        print(f"[{i}] Balance coins  : {balance:,}")

        spirits = data.get("spirits", [])
        if spirits:
            print(f"[{i}] Spirit ({len(spirits)}):")
            for sp in spirits:
                needs = sp.get("needs", {})
                food   = needs.get("food", 0) / 100
                clean  = needs.get("clean", 0) / 100
                energy = needs.get("energy", 0) / 100
                status_sp = sp.get("status", "?")
                mining = sp.get("miningPerHour", 0)
                print(f"       - {sp['name']} (Lv{sp['level']} {sp['rarity']}) | {status_sp} | "
                      f"food {food:.0f}% clean {clean:.0f}% energy {energy:.0f}% | ⛏ {mining}/hr")
        await asyncio.sleep(1)


async def main():
    print("=== Wisplings Multi-Tool ===")
    print("1. Register (onboarding penuh, pakai sessions.txt)")
    print("2. Buy item (shop-buy, pakai tokens.txt)")
    print("3. Use item (care-use, pakai tokens.txt)")
    print("4. Claim mining (mining-collect, pakai tokens.txt)")
    print("5. Claim daily (daily-claim, pakai tokens.txt)")
    print("6. Register cepat (cuma login, tanpa onboarding, pakai sessions.txt)")
    print("7. Cek balance wisp (game-bootstrap, pakai tokens.txt)")
    print("8. Buy & Open Chest (chest-buy + chest-open, pakai tokens.txt)")
    print("9. Cek jumlah spirit (collection-overview, pakai tokens.txt)")
    print("10. Buy slot (slot-buy, pakai tokens.txt)")
    print("11. [DEBUG] Raw response collection-overview + care-use")
    print("12. Cek slot spirit (used/max + harga next slot + kondisi spirit)")
    mode = input("Pilih mode [1-12]: ").strip()

    if mode == "1":
        await run_register_mode()
    elif mode == "2":
        await run_buy_mode()
    elif mode == "3":
        await run_use_mode()
    elif mode == "4":
        await run_claim_mining_mode()
    elif mode == "5":
        await run_claim_daily_mode()
    elif mode == "6":
        await run_register_quick_mode()
    elif mode == "7":
        await run_check_balance_mode()
    elif mode == "8":
        await run_chest_mode()
    elif mode == "9":
        await run_check_spirits_mode()
    elif mode == "10":
        await run_slot_buy_mode()
    elif mode == "11":
        await run_debug_mode()
    elif mode == "12":
        await run_check_slots_mode()
    else:
        print("Pilihan tidak valid, keluar.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
