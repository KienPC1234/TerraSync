# utils.py - Utilities Remain
import math
from datetime import datetime, timedelta

def generate_schedule():
    schedule = []
    base_date = datetime.now()
    for i in range(7):
        date = base_date + timedelta(days=i)
        schedule.append({'date': date.strftime('%Y-%m-%d'), 'water': 450 + i*10, 'end_time': '13:00'})
    return schedule