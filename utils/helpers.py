from datetime import datetime, date, timedelta
import calendar

def now_date():
    return datetime.now().date()

def month_key(dt=None):
    dt = dt or datetime.now()
    return f"{dt.year:04d}-{dt.month:02d}"

def month_name(key):
    y, m = key.split("-")
    nomes = ["janeiro","fevereiro","março","abril","maio","junho",
             "julho","agosto","setembro","outubro","novembro","dezembro"]
    return f"{nomes[int(m)-1].capitalize()}/{y}"

def normalize(text):
    return (text or "").strip().lower()

def business_days_until(vencimento_dia):
    today = now_date()
    last_day = calendar.monthrange(today.year, today.month)[1]
    target = date(today.year, today.month, min(vencimento_dia, last_day))
    if target < today:
        if today.month == 12:
            target = date(today.year + 1, 1, min(vencimento_dia, calendar.monthrange(today.year + 1, 1)[1]))
        else:
            target = date(today.year, today.month + 1, min(vencimento_dia, calendar.monthrange(today.year, today.month + 1)[1]))
    days = 0
    d = today
    while d < target:
        d += timedelta(days=1)
        if d.weekday() < 5:
            days += 1
    return days

def format_currency(value):
    return f"R$ {float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
