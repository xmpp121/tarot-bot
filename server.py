# server.py
import os
import logging
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from telegram import Update
from bot import build_application

# ---------- ЛОГИ ----------
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("webhook")

# ---------- СЕКРЕТЫ (ДОЛЖНЫ СОВПАДАТЬ С setWebhook) ----------
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "super-secret-path")  # <- проверь
TELEGRAM_SECRET_TOKEN = os.getenv("TELEGRAM_SECRET_TOKEN", "super-secret-header")  # <- проверь

# ---------- PTB Application ----------
application = build_application()  # НЕ запускает polling
app = FastAPI()

@app.on_event("startup")
async def on_startup():
    log.info("Initializing PTB application...")
    log.info("WEBHOOK_SECRET expected path: /webhook/%s (and with trailing slash)", WEBHOOK_SECRET)
    await application.initialize()
    await application.start()
    log.info("PTB application started.")

@app.on_event("shutdown")
async def on_shutdown():
    log.info("Stopping PTB application...")
    await application.stop()
    await application.shutdown()
    log.info("PTB application stopped.")

@app.get("/health")
async def health():
    return {"ok": True, "webhook_path": f"/webhook/{WEBHOOK_SECRET}"}

# --- общая функция обработки (чтобы не дублировать код) ---
async def _process_update(request: Request):
    tg_header = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if tg_header != TELEGRAM_SECRET_TOKEN:
        log.warning("Unauthorized webhook call. Got header=%s", tg_header)
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        data = await request.json()
    except Exception as e:
        log.exception("Can't parse JSON body: %s", e)
        return JSONResponse({"ok": False, "error": "bad json"}, status_code=200)

    try:
        update = Update.de_json(data, application.bot)
    except Exception as e:
        log.exception("Can't de_json Update: %s", e)
        return JSONResponse({"ok": False, "error": "bad update"}, status_code=200)

    try:
        await application.process_update(update)
    except Exception as e:
        log.exception("Error while processing update: %s", e)
        return JSONResponse({"ok": False, "error": "handler error"}, status_code=200)

    return {"ok": True}

# --- РОУТЫ БЕЗ И С ЗАКЛЮЧИТЕЛЬНОГО СЛЭША ---
@app.post(f"/webhook/{WEBHOOK_SECRET}")
async def telegram_webhook_no_slash(request: Request):
    return await _process_update(request)

@app.post(f"/webhook/{WEBHOOK_SECRET}/")
async def telegram_webhook_with_slash(request: Request):
    return await _process_update(request)
