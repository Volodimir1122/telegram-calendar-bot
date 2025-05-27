import requests
import datetime
import time
import threading
import pytz
from ics import Calendar
from telegram import Bot

# === ���Բ����ֲ� ===
API_TOKEN = '7541705762:AAEkCpMBSJbakGN1mlgwC2UEui56Rm_w0h0'
GROUP_ID = -29944289
ICS_URL = 'https://calendar.google.com/calendar/ical/vvhhoorrbbaall%40gmail.com/public/basic.ics'
TIMEZONE = 'Europe/Kyiv'

bot = Bot(token=API_TOKEN)

# === ����ֲ� ===

def fetch_events():
    try:
        r = requests.get(ICS_URL)
        calendar = Calendar(r.text)
        now = datetime.datetime.now(pytz.timezone(TIMEZONE))
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + datetime.timedelta(days=1)

        events_today = []
        for event in calendar.timeline.start_after(today_start).on(today_start):
            if today_start <= event.begin.astimezone(pytz.timezone(TIMEZONE)) < today_end:
                events_today.append(event)

        return events_today
    except Exception as e:
        print(f"[ERROR] �� ������� �������� ��䳿: {e}")
        return []

def format_event(event):
    start = event.begin.astimezone(pytz.timezone(TIMEZONE)).strftime('%H:%M')
    return f"?? {start} � {event.name or '��� �����'}"

def send_daily_schedule():
    events = fetch_events()
    if not events:
        message = "������� ���� ������������ ���� ??"
    else:
        message = "?? *������ ������� �� �������:*\n\n"
        message += "\n".join([format_event(e) for e in events])
    bot.send_message(chat_id=GROUP_ID, text=message, parse_mode="Markdown")

def schedule_checker():
    notified = set()
    while True:
        now = datetime.datetime.now(pytz.timezone(TIMEZONE))

        # ������� ����������� � 07:55
        if now.hour == 7 and now.minute == 55 and "daily" not in notified:
            send_daily_schedule()
            notified.add("daily")

        # �������� ������� �� ����� ����
        if now.hour == 0 and now.minute == 1:
            notified.clear()

        # �������� �� ��䳿 ����� 5 ��
        events = fetch_events()
        for event in events:
            start = event.begin.astimezone(pytz.timezone(TIMEZONE))
            delta = (start - now).total_seconds()
            uid = f"{event.uid}_{start.strftime('%Y%m%d%H%M')}"
            if 240 <= delta <= 300 and uid not in notified:  # �� 4 � 5 ���������
                bot.send_message(
                    chat_id=GROUP_ID,
                    text=f"?? ����� 5 ������: *{event.name or '��� �����'}* � {start.strftime('%H:%M')}",
                    parse_mode="Markdown"
                )
                notified.add(uid)

        time.sleep(30)

# === ����� ===

if __name__ == "__main__":
    print("? ��� ��������.")
    threading.Thread(target=schedule_checker).start()