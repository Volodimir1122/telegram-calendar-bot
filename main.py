# -*- coding: utf-8 -*-
import logging
import pytz
import requests
import threading
import time
from icalevents.icalevents import events as icalevents_fetch
from datetime import datetime, timedelta
from telegram import Bot, Update, ReplyKeyboardMarkup
from telegram.ext import Updater, MessageHandler, Filters, CommandHandler, CallbackContext
from flask import Flask
from threading import Thread

# Налаштування
API_TOKEN = '7541705762:AAEkCpMBSJbakGN1mlgwC2UEui56Rm_w0h0'
GROUP_ID = -1002194694251
ICS_URL = 'https://calendar.google.com/calendar/ical/vvhhoorrbbaall%40gmail.com/public/basic.ics'
TIMEZONE = 'Europe/Kyiv'

# Логи
logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)

# Глобальні змінні
sent_reminders = set()
last_reminder_message_id = None


def fetch_events(day_offset=0):
    try:
        tz = pytz.timezone(TIMEZONE)
        start = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=day_offset)
        end = start + timedelta(days=1)

        event_list = icalevents_fetch(url=ICS_URL, start=start, end=end)
        result = []

        for event in event_list:
            start_time = event.start.astimezone(tz)
            end_time = event.end.astimezone(tz) if event.end else start_time + timedelta(minutes=30)
            result.append({
                'name': event.summary,
                'start': start_time,
                'end': end_time,
                'description': event.description or ''
            })

        return sorted(result, key=lambda x: x['start'])

    except Exception as e:
        logging.error(f"Не вдалося отримати події: {e}")
        return []


def send_daily_summary():
    events = fetch_events(0)
    if not events:
        bot.send_message(chat_id=GROUP_ID, text="Сьогодні немає запланованих подій.")
        return

    message = "📅 *План на сьогодні:*\n\n"
    for event in events:
        message += f"🕗 {event['start'].strftime('%H:%M')} — {event['name']}\n"

    msg = bot.send_message(chat_id=GROUP_ID, text=message, parse_mode='Markdown')
    schedule_deletion(msg.chat_id, msg.message_id, hours=4)


def send_event_reminders():
    global last_reminder_message_id

    events = fetch_events(0)
    now = datetime.now(pytz.timezone(TIMEZONE)).replace(second=0, microsecond=0)

    for event in events:
        reminder_time = (event['start'] - timedelta(minutes=5)).replace(second=0, microsecond=0)
        if abs((reminder_time - now).total_seconds()) <= 60:
            uid = f"{event['name']}_{event['start']}"
            if uid not in sent_reminders:
                msg = f"⏰ Нагадування!\n{event['name']} о {event['start'].strftime('%H:%M')}"

                try:
                    if last_reminder_message_id:
                        bot.delete_message(chat_id=GROUP_ID, message_id=last_reminder_message_id)

                    message = bot.send_message(chat_id=GROUP_ID, text=msg)
                    last_reminder_message_id = message.message_id
                    sent_reminders.add(uid)
                except Exception as e:
                    logging.error(f"Не вдалося надіслати або видалити нагадування: {e}")


def schedule_deletion(chat_id, message_id, hours=4):
    def delete():
        time.sleep(hours * 3600)
        try:
            bot.delete_message(chat_id=chat_id, message_id=message_id)
        except Exception as e:
            logging.warning(f"Не вдалося видалити повідомлення: {e}")
    threading.Thread(target=delete).start()


def scheduler():
    while True:
        try:
            now = datetime.now(pytz.timezone(TIMEZONE)).replace(second=0, microsecond=0)
            if now.hour == 7 and now.minute == 55:
                send_daily_summary()
            send_event_reminders()
            time.sleep(60)
        except Exception as e:
            logging.error(f"[scheduler] Помилка: {e}")
            time.sleep(10)


def show_menu(update: Update, context: CallbackContext):
    keyboard = [
        ["📌 Поточне завдання"],
        ["📅 Завдання на день"],
        ["📆 Завдання на завтра"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    update.message.reply_text("Привіт! Обери опцію:", reply_markup=reply_markup)


def handle_text(update: Update, context: CallbackContext):
    text = update.message.text
    now = datetime.now(pytz.timezone(TIMEZONE))

    try:
        if text == "📌 Поточне завдання":
            events = fetch_events(0)
            current_event = next((e for e in events if e['start'] <= now <= e['end']), None)
            if current_event:
                description = f"\n📝 {current_event['description']}" if current_event['description'] else ""
                msg = (
                    f"🔄 Поточне завдання:\n"
                    f"🕘 {current_event['start'].strftime('%H:%M')}–{current_event['end'].strftime('%H:%M')}\n"
                    f"📌 {current_event['name']}{description}"
                )
            else:
                msg = "Зараз немає активних завдань."

            sent_msg = context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
            schedule_deletion(sent_msg.chat_id, sent_msg.message_id, hours=4)

        elif text == "📅 Завдання на день":
            events = fetch_events(0)
            if not events:
                context.bot.send_message(chat_id=update.effective_chat.id, text="Сьогодні немає запланованих подій.")
                return

            msg = "📅 *Сьогоднішні завдання:*\n\n"
            for event in events:
                msg += f"🕗 {event['start'].strftime('%H:%M')} — {event['name']}\n"

            sent_msg = context.bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode='Markdown')
            schedule_deletion(sent_msg.chat_id, sent_msg.message_id, hours=4)

        elif text == "📆 Завдання на завтра":
            events = fetch_events(1)
            if not events:
                context.bot.send_message(chat_id=update.effective_chat.id, text="Завтра немає запланованих подій.")
                return

            msg = "📆 *Завтра:*\n\n"
            for event in events:
                msg += f"🕗 {event['start'].strftime('%H:%M')} — {event['name']}\n"

            sent_msg = context.bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode='Markdown')
            schedule_deletion(sent_msg.chat_id, sent_msg.message_id, hours=4)

    except Exception as e:
        logging.error(f"[handle_text] Помилка: {e}")


def keep_alive():
    app = Flask('')

    @app.route('/')
    def home():
        return "I'm alive!"

    def run():
        app.run(host='0.0.0.0', port=8080)

    Thread(target=run).start()


def main():
    try:
        updater = Updater(API_TOKEN, use_context=True)
        dp = updater.dispatcher

        dp.add_handler(CommandHandler("start", show_menu))
        dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_text))

        threading.Thread(target=scheduler, daemon=True).start()
        now = datetime.now(pytz.timezone(TIMEZONE))
        print(f"[DEBUG] Server time (Kyiv): {now}")
        updater.start_polling()
        logging.info("Бот запущено")
        updater.idle()
    except Exception as e:
        logging.critical(f"[main] Критична помилка: {e}")


if __name__ == '__main__':
    keep_alive()
    main()
