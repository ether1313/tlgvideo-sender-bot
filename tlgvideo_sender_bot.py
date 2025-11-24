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

GROUP_A = ["ipay9", "bybid9", "bp77", "crown9", "kangaroobet88", "rolex9", "micky13", "bugatti13"]
GROUP_B = ["kingbet9", "me99", "gucci9", "pokemon13", "mrbean9",
           "novabet13", "xpay33", "queen13", "spongbob13", "winnie13"]

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
# DAILY SCHEDULE (BUILD TODAY ALWAYS)
# ================================================================
def build_daily_schedule():
    logger.info("🔄 Building schedule for today…")
    scheduler.remove_all_jobs()

    weekday = datetime.datetime.now(MY_TZ).weekday()  # 0=Mon ... 6=Sun

    # Monday, Wednesday, Friday → Group A
    if weekday in [0, 2, 4]:
        selected = GROUP_A
    else:
        selected = GROUP_B

    logger.info(f"📌 Today weekday={weekday} → Using group: {selected}")

    start_hour = 8

    for i, name in enumerate(selected):
        msg_id = VIDEO_MAP[name]
        hour = start_hour + i * 2

        # Cross-day handling
        if hour >= 24:
            hour -= 24
            day = (weekday + 1) % 7
        else:
            day = weekday

        scheduler.add_job(
            forward_once,
            trigger="cron",
            hour=hour,
            minute=0,
            day_of_week=str(day),
            args=[msg_id],
            id=name,
            replace_existing=True
        )

    show_next_run()

# ================================================================
# DAILY RELOAD (04:00)
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
    logger.info("🔁 Daily reload at 04:00 configured")

# ================================================================
# MAIN
# ================================================================
async def main():
    logger.info("🚀 Bot started...")

    now = datetime.datetime.now(MY_TZ)
    if now.hour >= 4:
        logger.info("⏱️ Bot started after 04:00 → Rebuilding today's schedule now")
        build_daily_schedule()
    else:
        logger.info("⏱️ Bot started before 04:00 → Today's schedule will run normally")
        build_daily_schedule()

    setup_daily_reload()
    scheduler.start()

    try:
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        logger.info("🟡 Shutdown signal received. Exiting cleanly...")

# RUN BOT
if __name__ == "__main__":
    asyncio.run(main())
