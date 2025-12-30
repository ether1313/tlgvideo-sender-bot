import os
import datetime
import asyncio
import logging
from zoneinfo import ZoneInfo
from telegram import Bot
from telegram.error import TimedOut, NetworkError, RetryAfter, Forbidden
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ================================================================
# LOGGING
# ================================================================
logger = logging.getLogger("tlg_scheduled_bot")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
logger.addHandler(handler)

# ================================================================
# ENV
# ================================================================
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID", "-1003478383694"))
MY_TZ = ZoneInfo("Asia/Kuala_Lumpur")

if not BOT_TOKEN:
    raise ValueError("🔴 Missing BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
scheduler = AsyncIOScheduler(timezone=MY_TZ)

# ================================================================
# VIDEO LIST
# ================================================================
VIDEO_MAP = {
    "ipay9": 25, "bybid9": 31, "bp77": 27, "crown9": 39, "kangaroobet88": 40,
    "rolex9": 30, "micky13": 34, "winnie13": 35, "cosmojack": 44,
    "kingbet9": 26, "me99": 28, "gucci9": 43, "pokemon13": 33, "mrbean9": 32,
    "novabet13": 41, "xpay33": 38, "queen13": 37, "spongbob13": 36
}

GROUP_A = ["ipay9", "bybid9", "bp77", "crown9", "kangaroobet88", "rolex9", "micky13", "winnie13", "cosmojack"]
GROUP_B = ["kingbet9", "me99", "gucci9", "pokemon13", "mrbean9", "novabet13", "xpay33", "queen13", "spongbob13"]

TARGET_CHANNELS = ["@tpaaustralia"]

# ================================================================
# SAFE TELEGRAM WRAPPER
# ================================================================
async def safe_telegram_call(func, *args, **kwargs):
    retry = 0
    backoff = 2

    while True:
        try:
            return await func(*args, **kwargs)

        except RetryAfter as e:
            wait_time = int(e.retry_after) + 1
            logger.warning(f"🔴 Rate limit — waiting {wait_time}s")
            await asyncio.sleep(wait_time)

        except TimedOut:
            logger.warning("🔴 Telegram timeout — retrying…")
            await asyncio.sleep(backoff)

        except NetworkError:
            logger.warning("🔴 Network error — retrying…")
            await asyncio.sleep(backoff)

        except ConnectionResetError:
            logger.warning("🔴 Connection reset — retrying…")
            await asyncio.sleep(backoff)

        except Forbidden:
            logger.error("🔴 Forbidden — no permission to send message.")
            return None

        except Exception as e:
            logger.error(f"🔴 Unknown Telegram error: {e}")
            await asyncio.sleep(backoff)

        retry += 1
        backoff = min(backoff * 1.5, 30)
        logger.info(f"🟡 Retrying... attempt {retry}")

# ================================================================
# FORWARD ONE MESSAGE
# ================================================================
async def forward_once(message_id):
    logger.info(f"🟢 Forwarding message_id={message_id}")

    for channel in TARGET_CHANNELS:
        try:
            await safe_telegram_call(
                bot.forward_message,
                chat_id=channel,
                from_chat_id=GROUP_ID,
                message_id=message_id
            )
            logger.info(f"🟢 Done forwarded to {channel}")

        except Exception as e:
            logger.error(f"🔴 Permanent failure forwarding to {channel}: {e}")

    show_next_run()

# ================================================================
# SHOW NEXT RUN
# ================================================================
def show_next_run():
    jobs = scheduler.get_jobs()
    now = datetime.datetime.now(MY_TZ)

    upcoming = [
        (job.id, job.trigger.get_next_fire_time(None, now))
        for job in jobs if job.trigger.get_next_fire_time(None, now)
    ]

    if upcoming:
        jid, t = min(upcoming, key=lambda x: x[1])
        logger.info(f"🟢 NEXT RUN: {jid} at {t}")
    else:
        logger.info("🟡 No upcoming tasks scheduled.")

# ================================================================
# BUILD DAILY SCHEDULE
# ================================================================
def build_daily_schedule():
    logger.info("🟢 Rebuilding today's schedule…")

    # Remove all jobs except Daily Reload & Health Check jobs
    for job in scheduler.get_jobs():
        if job.id not in ("daily_reload", "health_check"):
            scheduler.remove_job(job.id)

    now = datetime.datetime.now(MY_TZ)
    weekday = now.weekday()  # Monday=0 ... Sunday=6

    if weekday == 0:
        selected = GROUP_A
        logger.info(f"🔵 Monday → Group A: {selected}")
    elif weekday == 4:
        selected = GROUP_B
        logger.info(f"🔵 Friday → Group B: {selected}")
    else:
        logger.info(f"🔴 No video schedule today (weekday={weekday}).")
        show_next_run()
        return

    start_hour = 8

    for i, name in enumerate(selected):
        msg_id = VIDEO_MAP[name]
        hour = start_hour + i * 2

        if hour < 24:
            run_time = now.replace(hour=hour, minute=0, second=0, microsecond=0)
        else:
            next_day = now + datetime.timedelta(days=1)
            run_time = next_day.replace(hour=hour - 24, minute=0, second=0, microsecond=0)

        scheduler.add_job(
            forward_once,
            trigger="date",
            run_date=run_time,
            args=[msg_id],
            id=name,
            replace_existing=True
        )

    show_next_run()

# ================================================================
# HEALTH CHECK (Every 5 minutes)
# ================================================================
async def health_check():
    logger.info("🟢 HEALTH CHECK: Bot is alive.")
    try:
        me = await safe_telegram_call(bot.get_me)
        if me:
            logger.info(f"🟢 Telegram OK: Logged in as {me.username}")
        else:
            logger.warning("🟡 Telegram get_me returned None.")
    except Exception as e:
        logger.error(f"🔴 Telegram connection issue: {e}")


# ================================================================
# DAILY RELOAD SETUP
# ================================================================
def setup_daily_reload():
    scheduler.add_job(
        build_daily_schedule,
        trigger="cron",
        hour=4,
        minute=0,
        id="daily_reload",
        replace_existing=True
    )
    logger.info("🟢 Daily schedule reload set at 04:00 MYT")

# ================================================================
# SETUP HEALTH CHECK LOOP
# ================================================================
def setup_health_check():
    scheduler.add_job(
        health_check,
        trigger="interval",
        minutes=5,
        id="health_check",
        replace_existing=True
    )
    logger.info("🟢 Health check every 5 minutes enabled")

# ================================================================
# MAIN
# ================================================================
async def main():
    logger.info("🟢 Bot starting…")

    scheduler.remove_all_jobs()

    logger.info("🟢 Initial schedule build")
    build_daily_schedule()

    setup_daily_reload()
    setup_health_check()

    scheduler.start()

    try:
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        logger.info("🔴 Shutdown signal received — exiting…")

# RUN
if __name__ == "__main__":
    asyncio.run(main())
