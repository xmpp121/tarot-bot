# bot.py
import logging
import os
from dataclasses import dataclass
from typing import Dict, Optional

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, Poll
from telegram.ext import (
    Application, CommandHandler, MessageHandler, PollAnswerHandler,
    ContextTypes, filters
)

# ==== НАСТРОЙКИ (ЗАПОЛНИТЕ) ====
BOT_TOKEN = "8050194596:AAGoCprj1aDw4UwzhBQ2Ma8Uc-O4TBFhQaU"
CHANNEL_CHAT_ID = -1001234567890
CSV_PATH = "contacts.csv"


# ==== ЛОГИ ====
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("tarobot")

# ==== ВОПРОСЫ (все ответы принимаются) ====
QUESTIONS = [
    {
        "q": "Что в отношениях для вас сейчас важнее всего?",
        "options": [
            "Понимание и диалог 🗣️",
            "Стабильность и надёжность 🛡️",
            "Страсть и близость ❤️",
            "Перспектива будущего вместе 🏡",
        ],
    },
    {
        "q": "Какого ответа вы ждёте от расклада по любви?",
        "options": [
            "Вернётся ли гармония в текущие отношения",
            "Стоит ли продолжать или отпустить",
            "Есть ли шанс на новую встречу",
            "Как снять внутренние блоки в любви",
        ],
    },
    {
        "q": "Верите ли вы, что Таро помогает понять динамику отношений?",
        "options": [
            "Да, это полезный ориентир 🌙",
            "Скорее да, хочу проверить",
            "Не уверен(а), но интересно",
            "Нет, но готов(а) попробовать",
        ],
    },
]

# ==== КЛАВИАТУРЫ ====
def contact_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton(text="📱 Поделиться номером", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder="Нажмите, чтобы поделиться номером",
    )

def start_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton(text="✨ Получить бесплатный расклад")]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )

# ==== СОСТОЯНИЕ ====
@dataclass
class UserState:
    chat_id: int
    current_idx: int = 0
    last_poll_id: Optional[str] = None

USERS: Dict[int, UserState] = {}  # user_id -> state

# ==== ХЕНДЛЕРЫ ====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id
    USERS[user.id] = UserState(chat_id=chat_id)
    log.info("/start from user_id=%s chat_id=%s username=@%s",
             user.id, chat_id, user.username)

    await update.message.reply_text(
        "Привет! 👋\n"
        "Готов(а) к бесплатному мини-раскладу на отношения? 💞\n"
        "Нажмите кнопку ниже, чтобы начать:",
        reply_markup=start_keyboard()
    )

async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id
    state = USERS.get(user.id) or UserState(chat_id=chat_id)
    state.current_idx = 0
    state.last_poll_id = None
    USERS[user.id] = state
    log.info("Start quiz for user_id=%s chat_id=%s", user.id, chat_id)
    await send_next_question(user.id, context)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    if text == "✨ Получить бесплатный расклад":
        await quiz(update, context)
    else:
        await update.message.reply_text(
            "Нажмите «✨ Получить бесплатный расклад», чтобы начать 🙂",
            reply_markup=start_keyboard()
        )

async def send_next_question(user_id: int, context: ContextTypes.DEFAULT_TYPE):
    state = USERS.get(user_id)
    if not state:
        log.error("send_next_question: no state for user_id=%s", user_id)
        return

    # Все вопросы пройдены — просим номер
    if state.current_idx >= len(QUESTIONS):
        log.info("Quiz finished for user_id=%s", user_id)
        await context.bot.send_message(
            chat_id=state.chat_id,
            text=(
                "Спасибо за ответы! 🙏 Это поможет точнее подобрать бесплатный персональный расклад.\n"
                "Чтобы я отправил его лично вам, поделитесь номером телефона:"
            ),
            reply_markup=contact_keyboard(),
        )
        return

    q = QUESTIONS[state.current_idx]
    log.info("Send poll #%s to user_id=%s: %s", state.current_idx + 1, user_id, q["q"])

    # Обычный опрос (REGULAR): без правильных ответов — любой вариант подходит
    msg = await context.bot.send_poll(
        chat_id=state.chat_id,
        question=q["q"],
        options=q["options"],
        type=Poll.REGULAR,
        is_anonymous=False,           # чтобы получить PollAnswer с user.id
        allows_multiple_answers=False
    )

    state.last_poll_id = msg.poll.id
    USERS[user_id] = state

async def on_poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pa = update.poll_answer
    user_id = pa.user.id
    state = USERS.get(user_id)
    log.info("PollAnswer from user_id=%s poll_id=%s option_ids=%s",
             user_id, pa.poll_id, pa.option_ids)

    if not state:
        log.warning("No state for user_id=%s (PollAnswer). Ignoring.", user_id)
        return
    if not state.last_poll_id or state.last_poll_id != pa.poll_id:
        log.warning("Mismatched poll for user_id=%s (expected %s, got %s)",
                    user_id, state.last_poll_id, pa.poll_id)
        return

    # Просто двигаемся дальше
    state.current_idx += 1
    state.last_poll_id = None
    USERS[user_id] = state

    await context.bot.send_message(chat_id=state.chat_id, text="Принято 💫")
    await send_next_question(user_id, context)

def save_contact_to_csv(phone_number: str, first_name: str, last_name: str, user_id: int):
    need_header = not os.path.isfile(CSV_PATH)
    try:
        import csv
        with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if need_header:
                w.writerow(["phone_number", "first_name", "last_name", "user_id"])
            w.writerow([phone_number, first_name or "", last_name or "", str(user_id)])
        log.info("Contact saved to %s", CSV_PATH)
    except Exception as e:
        log.exception("Failed to save contact to CSV: %s", e)

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    contact = msg.contact
    phone = contact.phone_number
    first_name = contact.first_name or ""
    last_name = contact.last_name or ""
    user_id = contact.user_id

    log.info("Received contact from user_id=%s phone=%s name=%s %s",
             user_id, phone, first_name, last_name)

    # 1) Сначала тихо отправим контакт в канал (бот должен быть админом канала!)
    text = (
        "📥 Новый контакт (квиз Таро)\n"
        f"Имя: {first_name} {last_name}\n"
        f"Телефон: {phone}\n"
        f"User ID: {user_id}"
    )
    try:
        await context.bot.send_message(chat_id=CHANNEL_CHAT_ID, text=text)
        log.info("Contact forwarded to channel %s", CHANNEL_CHAT_ID)
    except Exception as e:
        log.exception("Failed to forward contact to channel: %s", e)

    # 2) (опционально) локально сохраняем
    try:
        save_contact_to_csv(phone, first_name, last_name, user_id)
    except Exception as e:
        log.exception("CSV save failed: %s", e)

    # 3) Пытаемся удалить контакт-сообщение пользователя
    try:
        await msg.delete()
        log.info("User contact message deleted")
    except Exception as e:
        # В приватных чатах обычно можно; в группах нужно право на удаление
        log.warning("Не удалось удалить контакт-сообщение: %s", e)

    # 4) Отправляем подтверждение
    try:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Спасибо! Номер получен ✅ Я вышлю ваш бесплатный расклад в ближайшее время."
        )
    except Exception as e:
        log.warning("Failed to send confirmation to user: %s", e)

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("pong ✅")

def build_application() -> Application:
    """Создаёт PTB Application (не запускает polling). Используется сервером вебхуков."""
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("quiz", quiz))  # запасной вариант
    app.add_handler(PollAnswerHandler(on_poll_answer))
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    return app
