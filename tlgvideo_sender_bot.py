import os
import datetime
import asyncio
import logging
from zoneinfo import ZoneInfo
from telegram import Bot
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
    raise ValueError("❌ Missing BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
scheduler = AsyncIOScheduler(timezone=MY_TZ)

# ================================================================
# VIDEO LIST
# ================================================================
VIDEO_MAP = {
    "ipay9": 25, "bybid9": 31, "bp77": 27, "crown9": 39,
    "kangaroobet88": 40, "rolex9": 30, "micky13": 34, "bugatti13": 42,
    "kingbet9": 26, "me99": 28, "gucci9": 29, "pokemon13": 33,
    "mrbean9": 32, "novabet13": 41, "xpay33": 38, "queen13": 37,
    "spongbob13": 36, "winnie13": 35
}

GROUP_A = ["ipay9", "bybid9", "bp77", "crown9", "kangaroobet88", "rolex9", "micky13", "bugatti13", "winnie13"]
GROUP_B = ["kingbet9", "me99", "gucci9", "pokemon13", "mrbean9",
           "novabet13", "xpay33", "queen13", "spongbob13"]

TARGET_CHANNELS = ["@tpaaustralia"]

# ================================================================
# FORWARD ONE VIDEO
# ================================================================
async def forward_once(message_id):
    logger.info(f"🚀 Forwarding message_id={message_id}")
    for channel in TARGET_CHANNELS:
        try:
            await bot.forward_message(
                chat_id=channel,
                from_chat_id=GROUP_ID,
                message_id=message_id
            )
            logger.info(f"✓ Forwarded → {channel}")
        except Exception as e:
            logger.error(f"❌ Failed to forward to {channel}: {e}")
    show_next_run()

# ================================================================
# PRINT NEXT RUN
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
        logger.info(f"⭐ NEXT RUN: {jid} → {t}")

# ================================================================
# DAILY SCHEDULE
# ================================================================
def build_daily_schedule():
    logger.info("🔄 Rebuilding today's schedule…")

    # Remove all jobs except daily reload
    for job in scheduler.get_jobs():
        if job.id != "daily_reload":
            scheduler.remove_job(job.id)

    now = datetime.datetime.now(MY_TZ)
    weekday = now.weekday()  # Monday=0 ... Sunday=6

    # ========================================================
    # Only run on Monday (Group A) and Friday (Group B)
    # ========================================================
    if weekday == 0:
        selected = GROUP_A
        logger.info(f"📌 Today = Monday → Using Group A: {selected}")
    elif weekday == 4:
        selected = GROUP_B
        logger.info(f"📌 Today = Friday → Using Group B: {selected}")
    else:
        logger.info(f"⛔ Today weekday={weekday}. Not Monday/Friday → No schedule created.")
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
# DAILY RELOAD at 04:00
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
    logger.info("🔁 Daily reload set at 04:00 (MY time)")

# ================================================================
# MAIN
# ================================================================
async def main():
    logger.info("🚀 Bot started...")

    scheduler.remove_all_jobs()

    logger.info("🔧 Initial build")
    build_daily_schedule()

    setup_daily_reload()

    scheduler.start()

    try:
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        logger.info("🟡 Shutdown signal — exiting…")

# RUN BOT
if __name__ == "__main__":
    asyncio.run(main())
