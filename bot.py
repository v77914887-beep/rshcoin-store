import asyncio
import json
import logging
import os
import sqlite3

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (KeyboardButton, LabeledPrice, Message,
                           PreCheckoutQuery, ReplyKeyboardMarkup, WebAppInfo)

TOKEN = os.environ["BOT_TOKEN"]          # токен от @BotFather
WEBAPP_URL = os.environ["WEBAPP_URL"]    # https-адрес, где лежит index.html

# Цены и выдачу определяет бот, а не мини-приложение: данным клиента верить нельзя.
CATALOG = {
    "coin_100":  {"title": "100 RSH COIN",  "stars": 50,   "coins": 100,  "desc": "Стартовый набор монет"},
    "coin_550":  {"title": "550 RSH COIN",  "stars": 250,  "coins": 550,  "desc": "Выгодный набор монет"},
    "coin_1200": {"title": "1200 RSH COIN", "stars": 500,  "coins": 1200, "desc": "Большой набор монет"},
    "coin_2600": {"title": "2600 RSH COIN", "stars": 1000, "coins": 2600, "desc": "Максимальный набор монет"},
    "nft_fox":    {"title": "NFT Neon Fox",     "stars": 300,  "desc": "Коллекционный NFT RSH COIN"},
    "nft_skull":  {"title": "NFT Gold Skull",   "stars": 500,  "desc": "Коллекционный NFT RSH COIN"},
    "nft_owl":    {"title": "NFT Cyber Owl",    "stars": 800,  "desc": "Коллекционный NFT RSH COIN"},
    "nft_dragon": {"title": "NFT Royal Dragon", "stars": 1500, "desc": "Коллекционный NFT RSH COIN"},
}

db = sqlite3.connect("rsh.db")
db.executescript("""
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, coins INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS payments(charge TEXT PRIMARY KEY, user_id INTEGER, item TEXT, stars INTEGER);
""")

dp = Dispatcher()


def coins(uid: int) -> int:
    row = db.execute("SELECT coins FROM users WHERE id=?", (uid,)).fetchone()
    return row[0] if row else 0


def shop_kb(uid: int) -> ReplyKeyboardMarkup:
    # sendData работает только у мини-приложений, открытых кнопкой клавиатуры
    btn = KeyboardButton(text="🛍 Открыть RSH COIN",
                         web_app=WebAppInfo(url=f"{WEBAPP_URL}?bal={coins(uid)}"))
    return ReplyKeyboardMarkup(keyboard=[[btn]], resize_keyboard=True)


@dp.message(CommandStart())
async def start(m: Message):
    await m.answer("Добро пожаловать в RSH COIN! Нажмите кнопку ниже, чтобы открыть магазин.",
                   reply_markup=shop_kb(m.from_user.id))


@dp.message(Command("nft"))
async def my_nft(m: Message):
    rows = db.execute("SELECT item FROM payments WHERE user_id=? AND item LIKE 'nft_%'",
                      (m.from_user.id,)).fetchall()
    await m.answer("Ваши NFT:\n" + "\n".join(CATALOG[r[0]]["title"] for r in rows)
                   if rows else "У вас пока нет NFT.")


@dp.message(F.web_app_data)
async def order(m: Message):
    try:
        item_id = json.loads(m.web_app_data.data)["id"]
        item = CATALOG[item_id]
    except (KeyError, ValueError, TypeError):
        return await m.answer("Не удалось разобрать заказ.")
    await m.answer_invoice(title=item["title"], description=item["desc"], payload=item_id,
                           currency="XTR",  # Telegram Stars, provider_token не нужен
                           prices=[LabeledPrice(label=item["title"], amount=item["stars"])])


@dp.pre_checkout_query()
async def pre_checkout(q: PreCheckoutQuery):
    ok = q.invoice_payload in CATALOG
    await q.answer(ok=ok, error_message=None if ok else "Товар недоступен")


@dp.message(F.successful_payment)
async def paid(m: Message):
    p, uid = m.successful_payment, m.from_user.id
    item = CATALOG[p.invoice_payload]
    try:  # charge_id уникален: повторное уведомление не выдаст товар дважды
        db.execute("INSERT INTO payments VALUES(?,?,?,?)",
                   (p.telegram_payment_charge_id, uid, p.invoice_payload, p.total_amount))
    except sqlite3.IntegrityError:
        return
    if "coins" in item:
        db.execute("INSERT INTO users(id, coins) VALUES(?, ?) "
                   "ON CONFLICT(id) DO UPDATE SET coins = coins + ?",
                   (uid, item["coins"], item["coins"]))
    db.commit()
    await m.answer(f"✅ Оплачено: {item['title']}\nБаланс: 🪙 {coins(uid)}",
                   reply_markup=shop_kb(uid))


async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(Bot(TOKEN))


if __name__ == "__main__":
    asyncio.run(main())

