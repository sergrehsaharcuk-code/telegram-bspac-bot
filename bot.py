import telebot
from telebot.types import ReplyKeyboardRemove, LabeledPrice, InlineKeyboardMarkup, InlineKeyboardButton
import requests
from bs4 import BeautifulSoup
import re
import json
import os
import time
import threading
from datetime import datetime, timedelta, date
from urllib.parse import urljoin
import PyPDF2
import io
import hashlib

# ===== НАСТРОЙКИ =====
TOKEN = os.environ.get("BOT_TOKEN", "8598725231:AAE9kXzwUo3f2yU7Uvse9kSTUDmQWd_Iyrc")
bot = telebot.TeleBot(TOKEN)

BASE_URL = "http://bspc.bstu.by/ru/"
ZVONKI_URL = urljoin(BASE_URL, "uchashchimsya/raspisanie-zvonkov")

USERS_FILE = "users.json"
LAST_SENT_FILE = "last_sent.json"
PAID_FILE = "paid_users.json"
PAGE_STATE_FILE = "page_state.json"
user_states = {}

# ===== ПЛАТЁЖНАЯ СИСТЕМА =====
SPECIAL_USERS = []
STAR_PRICE = 100
ADMIN_ID = 1526536345

def load_paid_users():
    if os.path.exists(PAID_FILE):
        try:
            with open(PAID_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"⚠️ Файл {PAID_FILE} повреждён. Создаётся новый.")
            return {}
    return {}

def save_paid_users(paid_dict):
    with open(PAID_FILE, "w", encoding="utf-8") as f:
        json.dump(paid_dict, f, indent=2, ensure_ascii=False)

def has_paid(user_id):
    paid = load_paid_users()
    return str(user_id) in paid

def mark_paid(user_id):
    paid = load_paid_users()
    paid[str(user_id)] = True
    save_paid_users(paid)

# ===== СЛОВАРЬ ССЫЛОК НА РАСПИСАНИЕ (PDF) =====
SCHEDULE_LINKS = {
    "С102": "https://bspc.bstu.by/files/rasp/1/S1.pdf",
    "С103": "https://bspc.bstu.by/files/rasp/1/S1.pdf",
    "С104": "https://bspc.bstu.by/files/rasp/1/S1.pdf",
    "Д6": "https://bspc.bstu.by/files/rasp/1/D1.pdf",
    "ТГВ1": "https://bspc.bstu.by/files/rasp/1/D1.pdf",
    "РТ7": "https://bspc.bstu.by/files/rasp/1/R1.pdf",
    "ПЭУ67": "https://bspc.bstu.by/files/rasp/1/R1.pdf",
    "ПЭУ68": "https://bspc.bstu.by/files/rasp/1/R1.pdf",
    "М77": "https://bspc.bstu.by/files/rasp/1/M1.pdf",
    "М78": "https://bspc.bstu.by/files/rasp/1/M1.pdf",
    "Ю59": "https://bspc.bstu.by/files/rasp/1/U1.pdf",
    "Ю60": "https://bspc.bstu.by/files/rasp/1/U1.pdf",
    "С99": "https://bspc.bstu.by/files/rasp/2/S2.pdf",
    "С100": "https://bspc.bstu.by/files/rasp/2/S2.pdf",
    "С101": "https://bspc.bstu.by/files/rasp/2/S2.pdf",
    "Д5": "https://bspc.bstu.by/files/rasp/2/D2.pdf",
    "ПЭУ66": "https://bspc.bstu.by/files/rasp/2/R2.pdf",
    "ПЭУ65": "https://bspc.bstu.by/files/rasp/2/R2.pdf",
    "РТ6": "https://bspc.bstu.by/files/rasp/2/R2.pdf",
    "М74": "https://bspc.bstu.by/files/rasp/2/M2.pdf",
    "М75": "https://bspc.bstu.by/files/rasp/2/M2.pdf",
    "МС76": "https://bspc.bstu.by/files/rasp/2/M2.pdf",
    "Ю56": "https://bspc.bstu.by/files/rasp/2/U2.pdf",
    "Ю57": "https://bspc.bstu.by/files/rasp/2/U2.pdf",
    "ЮС58": "https://bspc.bstu.by/files/rasp/2/U2.pdf",
    "С96": "https://bspc.bstu.by/files/rasp/3/S3.pdf",
    "С97": "https://bspc.bstu.by/files/rasp/3/S3.pdf",
    "С98": "https://bspc.bstu.by/files/rasp/3/S3.pdf",
    "Д4": "https://bspc.bstu.by/files/rasp/3/D3.pdf",
    "ПЭУ63": "https://bspc.bstu.by/files/rasp/3/R3.pdf",
    "ПЭУ64": "https://bspc.bstu.by/files/rasp/3/R3.pdf",
    "РТ5": "https://bspc.bstu.by/files/rasp/3/R3.pdf",
    "М71": "https://bspc.bstu.by/files/rasp/3/M3.pdf",
    "М72": "https://bspc.bstu.by/files/rasp/3/M3.pdf",
    "МС73": "https://bspc.bstu.by/files/rasp/3/M3.pdf",
    "Ю54": "https://bspc.bstu.by/files/rasp/3/U3.pdf",
    "ЮС55": "https://bspc.bstu.by/files/rasp/3/U3.pdf",
    "С94": "https://bspc.bstu.by/files/rasp/4/S4.pdf",
    "С95": "https://bspc.bstu.by/files/rasp/4/S4.pdf",
    "Ср27": "https://bspc.bstu.by/files/rasp/4/S4.pdf",
    "Д3": "https://bspc.bstu.by/files/rasp/4/D4.pdf",
    "Р61": "https://bspc.bstu.by/files/rasp/4/R4.pdf",
    "Р62": "https://bspc.bstu.by/files/rasp/4/R4.pdf",
    "Э4": "https://bspc.bstu.by/files/rasp/4/R4.pdf",
    "М68": "https://bspc.bstu.by/files/rasp/4/M4.pdf",
    "М69": "https://bspc.bstu.by/files/rasp/4/M4.pdf",
    "МС70": "https://bspc.bstu.by/files/rasp/4/M4.pdf",
}

# ===== ПРЯМЫЕ ССЫЛКИ НА ДНИ =====
DAY_URLS = {
    "понедельник": "http://bspc.bstu.by/ru/uchashchimsya/zamena-zanyatij/169-zamena-ponedelnik",
    "вторник": "http://bspc.bstu.by/ru/uchashchimsya/zamena-zanyatij/170-zamena-vtornik",
    "среда": "http://bspc.bstu.by/ru/uchashchimsya/zamena-zanyatij/171-zamena-sreda",
    "четверг": "http://bspc.bstu.by/ru/uchashchimsya/zamena-zanyatij/172-zamena-chetverg",
    "пятница": "http://bspc.bstu.by/ru/uchashchimsya/zamena-zanyatij/173-zamena-pyatnica",
    "суббота": "http://bspc.bstu.by/ru/uchashchimsya/zamena-zanyatij/174-zamena-subotta",
}

# ===== РАБОТА С БАЗОЙ ДАННЫХ =====
def load_users():
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"⚠️ Файл {USERS_FILE} повреждён. Создаётся новый.")
            return {}
    return {}

def save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def get_user_data(user_id):
    users = load_users()
    return users.get(str(user_id), {})

def is_user_registered(user_id):
    user = get_user_data(user_id)
    return all(k in user for k in ("first_name", "last_name", "group"))

def set_user_data(user_id, first_name, last_name, group, role="студент"):
    users = load_users()
    users[str(user_id)] = {"first_name": first_name, "last_name": last_name, "group": group.upper(), "role": role}
    save_users(users)

def update_user_name(user_id, first_name, last_name):
    users = load_users()
    if str(user_id) in users:
        users[str(user_id)]["first_name"] = first_name
        users[str(user_id)]["last_name"] = last_name
        save_users(users)
        return True
    return False

def update_user_group(user_id, group):
    users = load_users()
    if str(user_id) in users:
        users[str(user_id)]["group"] = group.upper()
        save_users(users)
        return True
    return False

# ===== ВАЛИДАЦИЯ ИМЕНИ =====
PROFANITY_ROOTS = ["бля", "хуй", "пизд", "еб", "ёб", "залуп", "гандон", "пидор", "чмо", "шмар", "лох"]

def normalize_for_profanity(text):
    replacements = {
        'x': 'х', 'X': 'Х', 'b': 'б', 'B': 'Б', '3': 'з', '0': 'о', '@': 'а',
        'y': 'у', 'Y': 'У', 'c': 'с', 'C': 'С', 'e': 'е', 'E': 'Е', 'a': 'а',
        'A': 'А', 'o': 'о', 'O': 'О', 'p': 'р', 'P': 'Р', 'k': 'к', 'K': 'К',
        'm': 'м', 'M': 'М', 'n': 'н', 'N': 'Н', 't': 'т', 'T': 'Т',
    }
    for lat, rus in replacements.items():
        text = text.replace(lat, rus)
    return text.lower()

def contains_profanity(word):
    normalized = normalize_for_profanity(word)
    for root in PROFANITY_ROOTS:
        if root in normalized:
            return True
    return False

def validate_full_name(full_name):
    parts = full_name.strip().split(maxsplit=1)
    if len(parts) != 2:
        return None
    first, last = parts[0], parts[1]
    if not (re.fullmatch(r'[a-zA-Zа-яА-ЯёЁ-]+', first) and re.fullmatch(r'[a-zA-Zа-яА-ЯёЁ-]+', last)):
        return None
    if len(first) < 2 or len(last) < 2:
        return None
    if contains_profanity(first) or contains_profanity(last):
        return None
    return first, last

# ===== ОПРЕДЕЛЕНИЕ НЕДЕЛИ =====
def get_week_type():
    week_number = datetime.now().isocalendar()[1]
    return "верхняя" if week_number % 2 == 0 else "нижняя"

# ===== ОТПРАВКА PDF =====
def send_pdf(chat_id, pdf_url, group_name):
    try:
        response = requests.get(pdf_url, timeout=15)
        if response.status_code != 200:
            bot.send_message(chat_id, "❌ Не удалось скачать файл расписания.")
            return
        bot.send_document(chat_id, (f"rasp_{group_name}.pdf", response.content), caption=f"📚 Расписание для группы {group_name}")
    except Exception as e:
        bot.send_message(chat_id, f"❌ Ошибка при отправке файла: {e}")

# ===== РАСПИСАНИЕ ЗВОНКОВ =====
def get_zvonki():
    return ("🔔 РАСПИСАНИЕ ЗВОНКОВ\n\n"
            "📆 Понедельник - пятница\n"
            "1 пара: 08:00-08:45 / 08:55-09:40\n"
            "2 пара: 09:50-10:35 / 10:45-11:30\n"
            "3 пара: 11:50-12:35 / 12:45-13:30\n"
            "4 пара: 14:25-15:10 / 15:20-16:05\n"
            "5 пара: 16:25-17:10 / 17:20-18:05\n"
            "6 пара: 18:15-19:00 / 19:10-19:55\n\n"
            "📆 Суббота\n"
            "1 пара: 08:00-08:45 / 08:55-09:40\n"
            "2 пара: 09:50-10:35 / 10:45-11:30\n"
            "3 пара: 11:40-12:25 / 12:35-13:20\n"
            "4 пара: 13:35-14:20 / 14:30-15:15\n"
            "5 пара: 15:25-16:10 / 16:20-17:05\n"
            "6 пара: 17:15-18:00 / 18:10-18:55\n\n"
            "📆 Сокращённые дни\n"
            "1 пара: 08:00-09:00\n"
            "2 пара: 09:10-10:10\n"
            "3 пара: 10:20-11:20\n"
            "4 пара: 11:30-12:30\n"
            "5 пара: 12:40-13:40\n"
            "6 пара: 13:50-14:50")

# ===== ФУНКЦИИ ДЛЯ ОБРАБОТКИ ТАБЛИЦ ЗАМЕН =====
def time_to_lesson_number(time_str, day_name):
    normalized = time_str.replace('.', ':')
    start = normalized.split('-')[0].strip() if '-' in normalized else normalized.strip()
    weekday_map = {
        "08:00": "1", "08:55": "1",
        "09:50": "2", "10:45": "2",
        "11:50": "3", "12:45": "3",
        "14:25": "4", "15:20": "4",
        "16:25": "5", "17:20": "5",
        "18:15": "6", "19:10": "6"
    }
    saturday_map = {
        "08:00": "1", "08:55": "1",
        "09:50": "2", "10:45": "2",
        "11:40": "3", "12:35": "3",
        "13:35": "4", "14:30": "4",
        "15:25": "5", "16:20": "5",
        "17:15": "6", "18:10": "6"
    }
    if day_name == "суббота":
        mapping = saturday_map
    else:
        mapping = weekday_map
    return mapping.get(start, time_str)

def filter_replacements_by_group(replacements, group_name):
    result = []
    for rep in replacements:
        group_val = None
        for key in rep:
            if 'групп' in key.lower():
                group_val = rep[key]
                break
        if not group_val:
            for val in rep.values():
                if group_name.upper() in val.upper():
                    result.append(rep)
                    break
        elif group_name.upper() in group_val.upper():
            result.append(rep)
    return result

def format_replacements(replacements, group_name, day_name, date_str):
    if not replacements:
        return f"На {day_name} ({date_str}) замен для группы {group_name} нет."
    lines = [f"Замены на {day_name} {date_str} (группа {group_name}):\n"]
    for rep in replacements:
        def find_val(keywords):
            for key in rep:
                for kw in keywords:
                    if kw.lower() in key.lower():
                        return rep[key]
            return None
        para = find_val(["№ учёб. зан.", "пара", "№"]) or "?"
        if re.search(r'\d+[.:]\d+\s*-\s*\d+[.:]\d+', para):
            para = time_to_lesson_number(para, day_name)
        old = find_val(["заменяется", "отменяется", "было"]) or "—"
        new = find_val(["проведено", "стало", "будет"]) or "—"
        teacher = find_val(["преподаватель", "ф.и.о.", "фио"]) or "?"
        room = find_val(["каб.", "ауд.", "кабинет"]) or "?"
        
        if not old or old.strip() == "-":
            old = "—"
        if not new or new.strip() == "-":
            new = "—"
            
        lines.append(f"{date_str} ({day_name}) у тебя замена на {para} пару.")
        lines.append(f"Было: {old}.")
        lines.append(f"Стало: {new}.")
        
        if teacher and teacher != "?":
            if re.match(r'^[\d/]+$', teacher) or teacher.isdigit():
                if not room or room == "?" or room == teacher:
                    lines.append(f"Аудитория: {teacher}.")
                else:
                    lines.append(f"Аудитория: {room}.")
            else:
                lines.append(f"Преподаватель: {teacher}.")
                if room and room != "?":
                    lines.append(f"Аудитория: {room}.")
        else:
            if room and room != "?":
                lines.append(f"Аудитория: {room}.")
                
        lines.append("")
    return "\n".join(lines)

# ===== ОСНОВНАЯ ФУНКЦИЯ ПОЛУЧЕНИЯ ЗАМЕН ДЛЯ ДАТЫ =====
def get_replacements_for_date(target_date):
    weekdays_ru = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота"]
    target_day_name = weekdays_ru[target_date.weekday()] if target_date.weekday() < 6 else None
    if not target_day_name or target_day_name not in DAY_URLS:
        return None, None, None

    url = DAY_URLS[target_day_name]
    try:
        print(f"Загружаю страницу {target_day_name}: {url}")
        r = requests.get(url, timeout=600)
        r.encoding = 'utf-8'
        html = r.text
        soup = BeautifulSoup(html, 'html.parser')

        headers = soup.find_all(['h1', 'h2', 'h3', 'h4'])
        target_header = None
        day_prefix = target_day_name[:4].lower()
        for header in headers:
            text = header.get_text().lower()
            if 'замена' in text and day_prefix in text:
                target_header = header
                break

        if not target_header:
            print(f"   Не найден заголовок с заменой для {target_day_name}")
            return None, None, None

        header_text = target_header.get_text()
        date_match = re.search(r'(\d{2}\.\d{2}\.\d{4})', header_text)
        if not date_match:
            print(f"   В заголовке нет даты: {header_text}")
            return None, None, None

        found_date_str = date_match.group(1)
        found_date = datetime.strptime(found_date_str, "%d.%m.%Y").date()
        print(f"   Найдена дата в заголовке: {found_date_str}")
        if found_date != target_date:
            print(f"   Не совпадает с целевой {target_date.strftime('%d.%m.%Y')}")
            return None, None, None

        print(f"   ✅ ДАТА СОВПАДАЕТ!")

        tables = soup.find_all('table')
        reps = []
        for table in tables:
            rows = table.find_all('tr')
            if len(rows) < 2:
                continue
            header_cells = rows[0].find_all(['th', 'td'])
            headers = [cell.get_text(strip=True) for cell in header_cells]
            for row in rows[1:]:
                cells = row.find_all(['td', 'th'])
                if len(cells) < 2:
                    continue
                row_data = [cell.get_text(strip=True) for cell in cells]
                if len(row_data) == len(headers):
                    item = dict(zip(headers, row_data))
                else:
                    item = {"raw": " | ".join(row_data)}
                reps.append(item)

        if reps:
            print(f"   Найдено {len(reps)} записей")
            return reps, target_day_name.capitalize(), target_date.strftime("%d.%m.%Y")
        else:
            print("   Таблицы пусты")
            return None, None, None
    except Exception as e:
        print(f"   Ошибка при загрузке: {e}")
        return None, None, None

# ===== НОВАЯ ФУНКЦИЯ ДЛЯ РАССЫЛКИ (С ПОВТОРНЫМИ ПОПЫТКАМИ) =====
def load_page_with_retry(url, max_attempts=999, delay=300):
    attempt = 0
    while attempt < max_attempts:
        try:
            print(f"🔄 Попытка загрузки {url} (попытка {attempt + 1})")
            r = requests.get(url, timeout=600)
            if r.status_code == 200:
                print(f"✅ Страница загружена успешно")
                r.encoding = 'utf-8'
                return r
            elif r.status_code == 500:
                print(f"⚠️ Ошибка 500 на сервере. Повтор через {delay} сек...")
                attempt += 1
                if attempt < max_attempts:
                    time.sleep(delay)
                else:
                    print("❌ Исчерпаны все попытки")
                    return None
            else:
                print(f"⚠️ Неожиданный код ответа: {r.status_code}")
                return None
        except Exception as e:
            print(f"⚠️ Исключение при загрузке: {e}")
            attempt += 1
            if attempt < max_attempts:
                print(f"Повтор через {delay} сек...")
                time.sleep(delay)
            else:
                print("❌ Исчерпаны все попытки")
                return None
    return None

def parse_reps_from_page(target_date):
    weekdays_ru = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота"]
    target_day_name = weekdays_ru[target_date.weekday()] if target_date.weekday() < 6 else None
    if not target_day_name or target_day_name not in DAY_URLS:
        return None, None, None

    url = DAY_URLS[target_day_name]
    r = load_page_with_retry(url)
    if not r:
        print(f"❌ Не удалось загрузить страницу {target_day_name}")
        return None, None, None
    
    try:
        html = r.text
        soup = BeautifulSoup(html, 'html.parser')

        tables = soup.find_all('table')
        reps = []
        for table in tables:
            rows = table.find_all('tr')
            if len(rows) < 2:
                continue
            header_cells = rows[0].find_all(['th', 'td'])
            headers = [cell.get_text(strip=True) for cell in header_cells]
            for row in rows[1:]:
                cells = row.find_all(['td', 'th'])
                if len(cells) < 2:
                    continue
                row_data = [cell.get_text(strip=True) for cell in cells]
                if len(row_data) == len(headers):
                    item = dict(zip(headers, row_data))
                else:
                    item = {"raw": " | ".join(row_data)}
                reps.append(item)

        header_date = None
        headers_tag = soup.find_all(['h1', 'h2', 'h3', 'h4'])
        for h in headers_tag:
            text = h.get_text()
            match = re.search(r'(\d{2}\.\d{2}\.\d{4})', text)
            if match:
                header_date = match.group(1)
                break
        date_str = header_date if header_date else target_date.strftime("%d.%m.%Y")
        day_name = target_day_name.capitalize()

        if reps:
            print(f"   Найдено {len(reps)} записей")
            return reps, day_name, date_str
        else:
            print("   Таблицы пусты")
            return None, day_name, date_str
    except Exception as e:
        print(f"   Ошибка при парсинге: {e}")
        return None, None, None

# ===== ФУНКЦИЯ ДЛЯ ВЫЧИСЛЕНИЯ ХЕША =====
def get_tables_hash(url):
    try:
        r = requests.get(url, timeout=30)
        r.encoding = 'utf-8'
        soup = BeautifulSoup(r.text, 'html.parser')
        tables = soup.find_all('table')
        if not tables:
            return None
        tables_text = ''.join(table.get_text(strip=True) for table in tables)
        return hashlib.md5(tables_text.encode('utf-8')).hexdigest()
    except Exception as e:
        print(f"Ошибка при получении хеша: {e}")
        return None

# ===== ФУНКЦИИ ДЛЯ РАБОТЫ С СОСТОЯНИЕМ СТРАНИЦ =====
def load_page_state():
    if os.path.exists(PAGE_STATE_FILE):
        try:
            with open(PAGE_STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_page_state(state):
    with open(PAGE_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

def get_current_page_state():
    state = load_page_state()
    today = date.today().strftime("%Y-%m-%d")
    return state.get(today, {})

def update_page_state(day_name, page_hash, groups):
    state = load_page_state()
    today = date.today().strftime("%Y-%m-%d")
    if today not in state:
        state[today] = {}
    state[today][day_name] = {
        "hash": page_hash,
        "groups": groups
    }
    save_page_state(state)

# ===== ФУНКЦИИ ДЛЯ РАБОТЫ С УВЕДОМЛЕНИЯМИ =====
NOTIFIED_FILE = "notified_groups.json"

def load_notified():
    if os.path.exists(NOTIFIED_FILE):
        try:
            with open(NOTIFIED_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_notified(notified):
    with open(NOTIFIED_FILE, "w", encoding="utf-8") as f:
        json.dump(notified, f, indent=2, ensure_ascii=False)

def get_notified_today():
    today = date.today().strftime("%Y-%m-%d")
    data = load_notified()
    return data.get(today, {})

def mark_group_notified_for_date(group, date_obj):
    today = date.today().strftime("%Y-%m-%d")
    date_str = date_obj.strftime("%Y-%m-%d")
    data = load_notified()
    
    if today not in data:
        data[today] = {}
    
    if group not in data[today]:
        data[today][group] = {}
    elif not isinstance(data[today][group], dict):
        data[today][group] = {}
    
    data[today][group][date_str] = True
    save_notified(data)

def is_group_notified_for_date(group, date_obj):
    notified = get_notified_today()
    date_str = date_obj.strftime("%Y-%m-%d")
    group_data = notified.get(group, {})
    if isinstance(group_data, dict):
        return group_data.get(date_str, False)
    return False

def extract_groups_from_reps(reps):
    groups = set()
    for rep in reps:
        for key, value in rep.items():
            if 'групп' in key.lower():
                for g in re.split(r'[,/ ]+', value.upper()):
                    g = g.strip()
                    if g in SCHEDULE_LINKS:
                        groups.add(g)
                break
    return list(groups)

# ===== ОСНОВНАЯ ФУНКЦИЯ ПРОВЕРКИ И ОТПРАВКИ =====
def check_and_notify_new_replacements():
    try:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Проверка новых замен...")
        dates_to_check = get_dates_to_check()
        current_state = get_current_page_state()
        
        for d in dates_to_check:
            reps, day_name, date_str = parse_reps_from_page(d)
            if not reps:
                continue
            
            url = DAY_URLS[day_name.lower()]
            current_hash = get_tables_hash(url)
            if not current_hash:
                continue
            
            current_groups = extract_groups_from_reps(reps)
            prev_state = current_state.get(day_name.lower(), {})
            prev_hash = prev_state.get("hash")
            prev_groups = set(prev_state.get("groups", []))
            current_groups_set = set(current_groups)
            
            if prev_hash == current_hash:
                continue
            
            print(f"  🔄 Изменение на странице {day_name}!")
            
            new_groups = current_groups_set - prev_groups
            for group in new_groups:
                print(f"    ➕ Новые замены для группы {group}")
                filtered = filter_replacements_by_group(reps, group)
                if filtered:
                    answer = format_replacements(filtered, group, day_name, date_str)
                    users = load_users()
                    for uid_str, data in users.items():
                        if data.get("group") == group:
                            uid = int(uid_str)
                            try:
                                bot.send_message(uid, answer)
                                print(f"      ✅ Отправлено пользователю {uid}")
                                time.sleep(0.1)
                            except Exception as e:
                                print(f"      ❌ Ошибка отправки {uid}: {e}")
                    mark_group_notified_for_date(group, d)
            
            common_groups = current_groups_set & prev_groups
            if common_groups and prev_hash != current_hash:
                for group in common_groups:
                    print(f"    🔄 Обновлённые замены для группы {group}")
                    filtered = filter_replacements_by_group(reps, group)
                    if filtered:
                        answer = format_replacements(filtered, group, day_name, date_str)
                        users = load_users()
                        for uid_str, data in users.items():
                            if data.get("group") == group:
                                uid = int(uid_str)
                                try:
                                    bot.send_message(uid, answer)
                                    print(f"      ✅ Отправлено пользователю {uid}")
                                    time.sleep(0.1)
                                except Exception as e:
                                    print(f"      ❌ Ошибка отправки {uid}: {e}")
                        mark_group_notified_for_date(group, d)
            
            removed_groups = prev_groups - current_groups_set
            for group in removed_groups:
                print(f"    ➖ Отменены замены для группы {group}")
                answer = f"🔄 ОТМЕНА: замены на {day_name} {date_str} для группы {group} больше не актуальны."
                users = load_users()
                for uid_str, data in users.items():
                    if data.get("group") == group:
                        uid = int(uid_str)
                        try:
                            bot.send_message(uid, answer)
                            print(f"      ✅ Отправлено пользователю {uid}")
                            time.sleep(0.1)
                        except Exception as e:
                            print(f"      ❌ Ошибка отправки {uid}: {e}")
            
            update_page_state(day_name.lower(), current_hash, current_groups)
        
        print(f"  ✅ Проверка завершена")
    except Exception as e:
        import traceback
        error_text = f"❌ Ошибка в check_and_notify_new_replacements:\n{str(e)}\n{traceback.format_exc()}"
        print(error_text)
        try:
            bot.send_message(ADMIN_ID, error_text[:4000])
        except:
            pass

# ===== ФУНКЦИИ ДЛЯ РАССЫЛКИ =====
def load_last_sent():
    if os.path.exists(LAST_SENT_FILE):
        try:
            with open(LAST_SENT_FILE, "r") as f:
                return json.load(f).get("date")
        except:
            return None
    return None

def save_last_sent(date_str):
    with open(LAST_SENT_FILE, "w") as f:
        json.dump({"date": date_str}, f)

def get_dates_to_check():
    today = date.today()
    weekday = today.weekday()
    dates = []
    if weekday == 4:
        dates.append(today + timedelta(days=1))
        dates.append(today + timedelta(days=3))
    elif weekday >= 5:
        if weekday == 5:
            dates.append(today + timedelta(days=2))
        else:
            dates.append(today + timedelta(days=1))
    else:
        next_day = today + timedelta(days=1)
        while next_day.weekday() == 6:
            next_day += timedelta(days=1)
        dates.append(next_day)
    return dates

def send_final_updates():
    """Отправляет сообщения 'нет замен' в 17:20 для групп, у которых не было замен"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Финальная рассылка...")
    users = load_users()
    dates_to_check = get_dates_to_check()
    state = get_current_page_state()
    
    all_groups_in_tables = set()
    for day_name, data in state.items():
        all_groups_in_tables.update(data.get("groups", []))
    
    groups_users = {}
    for uid_str, data in users.items():
        group = data.get("group")
        if group:
            if group not in groups_users:
                groups_users[group] = []
            groups_users[group].append(int(uid_str))
    
    replacements_by_date = []
    for d in dates_to_check:
        reps, day_name, date_str = parse_reps_from_page(d)
        replacements_by_date.append((reps, day_name, date_str))
    
    for group, uids in groups_users.items():
        if group in all_groups_in_tables:
            continue
        
        for idx, (reps, day_name, date_str) in enumerate(replacements_by_date):
            target_date = dates_to_check[idx]
            weekdays_ru = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота"]
            target_day = weekdays_ru[target_date.weekday()].capitalize()
            target_date_str = target_date.strftime("%d.%m.%Y")
            answer = f"❌ На {target_day} {target_date_str} замен для группы {group} нет."
            
            for uid in uids:
                try:
                    bot.send_message(uid, answer)
                    time.sleep(0.05)
                except Exception as e:
                    print(f"    ❌ Ошибка отправки {uid}: {e}")

# ===== ПЛАНИРОВЩИКИ =====
def monitor_updates():
    """Мониторинг сайта КРУГЛОСУТОЧНО (без ограничения по времени)"""
    while True:
        now = datetime.now()
        # Мониторим круглосуточно
        check_and_notify_new_replacements()
        time.sleep(900)  # каждые 15 минут

def final_scheduler():
    """Запускает финальную рассылку в 17:20"""
    while True:
        now = datetime.now()
        target = now.replace(hour=17, minute=20, second=0, microsecond=0)
        if now >= target:
            target += timedelta(days=1)
        sleep_seconds = (target - now).total_seconds()
        print(f"📅 Следующая финальная рассылка: {target.strftime('%Y-%m-%d %H:%M')}")
        time.sleep(sleep_seconds)
        
        today_str = datetime.now().strftime("%Y-%m-%d")
        if load_last_sent() != today_str:
            send_final_updates()
            save_last_sent(today_str)
        else:
            print("Сегодня уже отправляли, пропускаю.")

# ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ КОМАНД =====
def get_today_replacements():
    today = date.today()
    weekdays_ru = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
    day_name = weekdays_ru[today.weekday()].capitalize()
    date_str = today.strftime("%d.%m.%Y")
    if today.weekday() == 6:
        return None, day_name, date_str
    reps, _, _ = get_replacements_for_date(today)
    return reps, day_name, date_str

def get_next_replacements():
    dates_to_check = get_dates_to_check()
    results = []
    for d in dates_to_check:
        reps, day_name, date_str = get_replacements_for_date(d)
        if reps is not None:
            results.append((reps, day_name, date_str))
        else:
            weekdays_ru = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота"]
            day_name = weekdays_ru[d.weekday()].capitalize()
            date_str = d.strftime("%d.%m.%Y")
            results.append((None, day_name, date_str))
    return results

def normalize_group(text):
    return re.sub(r'\s+', '', text).upper()

# ===== ПЛАТЁЖНЫЕ ОБРАБОТЧИКИ =====
@bot.message_handler(commands=['buy'])
def cmd_buy(message):
    user_id = message.from_user.id
    if user_id not in SPECIAL_USERS:
        bot.reply_to(message, "❌ Эта команда не для вас.")
        return
    if has_paid(user_id):
        bot.reply_to(message, "✅ Вы уже оплатили доступ.")
        return
    prices = [LabeledPrice(label="Доступ к боту", amount=STAR_PRICE)]
    bot.send_invoice(
        user_id,
        title="Платная подписка",
        description=f"Оплатите доступ к боту ({STAR_PRICE} звёзд).",
        invoice_payload="special_access",
        provider_token="284685063:TEST:STARS",
        currency="XTR",
        prices=prices,
        start_parameter="subscribe",
        need_name=False,
        need_phone_number=False,
        need_email=False,
        need_shipping_address=False,
        is_flexible=False
    )

@bot.pre_checkout_query_handler(func=lambda query: True)
def process_pre_checkout(pre_checkout_query):
    bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def process_successful_payment(message):
    user_id = message.from_user.id
    if user_id in SPECIAL_USERS:
        mark_paid(user_id)
        bot.send_message(user_id, "✅ Оплата прошла успешно! Доступ открыт.")
    else:
        bot.send_message(user_id, "Оплата получена, но вы не в списке платных пользователей.")

# ===== БЛОКИРУЮЩИЙ ПЕРЕХВАТЧИК =====
@bot.message_handler(func=lambda message: message.from_user.id in SPECIAL_USERS and not has_paid(message.from_user.id) and message.text != '/buy' and message.content_type != 'successful_payment')
def block_special_users(message):
    bot.reply_to(
        message,
        f"⭐ Для вашего аккаунта доступ к боту платный.\n"
        f"Стоимость: {STAR_PRICE} звёзд.\n"
        f"Чтобы оплатить, отправьте /buy"
    )

# ===== МАССОВАЯ РАССЫЛКА =====
@bot.message_handler(commands=['broadcast'])
def cmd_broadcast(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ У вас нет прав.")
        return
    
    users_count = len(load_users())
    markup = InlineKeyboardMarkup()
    btn_text = InlineKeyboardButton("📝 Текстовое сообщение", callback_data="broadcast_text")
    btn_photo = InlineKeyboardButton("📸 Фото", callback_data="broadcast_photo")
    markup.add(btn_text, btn_photo)
    
    bot.send_message(
        message.chat.id, 
        f"📤 Выберите тип рассылки для {users_count} пользователей:",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data == "broadcast_text")
def callback_broadcast_text(call):
    bot.edit_message_text(
        "✏️ Отправьте текст для рассылки:",
        call.message.chat.id,
        call.message.message_id
    )
    bot.register_next_step_handler(call.message, process_broadcast_text)

@bot.callback_query_handler(func=lambda call: call.data == "broadcast_photo")
def callback_broadcast_photo(call):
    bot.edit_message_text(
        "📸 Отправьте фото (можно с подписью):",
        call.message.chat.id,
        call.message.message_id
    )
    bot.register_next_step_handler(call.message, process_broadcast_photo)

def process_broadcast_text(message):
    text = message.text.strip()
    if not text:
        bot.reply_to(message, "❌ Текст не может быть пустым. Попробуйте снова.")
        return
    
    users = load_users()
    msg = bot.reply_to(message, f"📤 Отправить текст всем {len(users)} пользователям?\n\n{text}\n\n(да/нет)")
    bot.register_next_step_handler(msg, confirm_broadcast_text, text)

def confirm_broadcast_text(message, broadcast_text):
    if message.text.lower() not in ['да', 'lf']:
        bot.reply_to(message, "❌ Отменено.")
        return
    
    users = load_users()
    success = 0
    failed = 0
    status_msg = bot.reply_to(message, "🔄 Рассылка текста...")
    
    for uid_str, data in users.items():
        try:
            uid = int(uid_str)
            if uid in SPECIAL_USERS and not has_paid(uid):
                failed += 1
                continue
            bot.send_message(uid, broadcast_text)
            success += 1
            time.sleep(0.05)
        except:
            failed += 1
    
    bot.edit_message_text(
        f"✅ Готово! Успешно: {success}, ошибок: {failed}",
        status_msg.chat.id,
        status_msg.message_id
    )

def process_broadcast_photo(message):
    if not message.photo:
        bot.reply_to(message, "❌ Это не фото. Отправьте фото командой /broadcast")
        return
    
    uid = message.from_user.id
    file_id = message.photo[-1].file_id
    caption = message.caption if message.caption else ""
    
    if uid not in user_states:
        user_states[uid] = {}
    user_states[uid]['broadcast_photo'] = {'file_id': file_id, 'caption': caption}
    
    users = load_users()
    markup = InlineKeyboardMarkup()
    btn_yes = InlineKeyboardButton("✅ Да", callback_data="confirm_photo_yes")
    btn_no = InlineKeyboardButton("❌ Нет", callback_data="confirm_photo_no")
    markup.add(btn_yes, btn_no)
    
    bot.send_photo(
        message.chat.id,
        file_id,
        caption=f"📤 Отправить это фото всем {len(users)} пользователям?\n\nПодпись: {caption}",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data == "confirm_photo_yes")
def callback_confirm_photo(call):
    uid = call.from_user.id
    data = user_states.get(uid, {}).get('broadcast_photo', {})
    file_id = data.get('file_id')
    caption = data.get('caption', '')
    
    if not file_id:
        bot.answer_callback_query(call.id, "❌ Данные не найдены. Попробуйте снова.")
        return
    
    bot.edit_message_caption(
        caption="🔄 Рассылка фото...",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id
    )
    
    users = load_users()
    success = 0
    failed = 0
    
    for uid_str, data in users.items():
        try:
            uid = int(uid_str)
            if uid in SPECIAL_USERS and not has_paid(uid):
                failed += 1
                continue
            bot.send_photo(uid, file_id, caption=caption)
            success += 1
            time.sleep(0.05)
        except Exception as e:
            print(f"Ошибка отправки пользователю {uid}: {e}")
            failed += 1
    
    bot.edit_message_caption(
        caption=f"✅ Готово! Успешно: {success}, ошибок: {failed}",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id
    )
    
    if uid in user_states and 'broadcast_photo' in user_states[uid]:
        del user_states[uid]['broadcast_photo']

@bot.callback_query_handler(func=lambda call: call.data == "confirm_photo_no")
def callback_cancel_photo(call):
    uid = call.from_user.id
    bot.edit_message_caption(
        caption="❌ Рассылка отменена.",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id
    )
    if uid in user_states and 'broadcast_photo' in user_states[uid]:
        del user_states[uid]['broadcast_photo']

# ===== КОМАНДА ДЛЯ ЛИЧНЫХ СООБЩЕНИЙ =====
@bot.message_handler(commands=['sendto'])
def cmd_sendto(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        parts = message.text.split(maxsplit=2)
        target_id = int(parts[1])
        text = parts[2]
        bot.send_message(target_id, text)
        bot.reply_to(message, "✅ Отправлено")
    except:
        bot.reply_to(message, "❌ Ошибка. Используйте: /sendto ID текст")

# ===== СТАТИСТИКА =====
@bot.message_handler(commands=['stats'])
def cmd_stats(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Нет прав.")
        return
    users = load_users()
    total = len(users)
    group_stats = {}
    for u in users.values():
        if u.get("group"):
            group_stats[u["group"]] = group_stats.get(u["group"], 0) + 1
    top_groups = sorted(group_stats.items(), key=lambda x: x[1], reverse=True)[:5]
    groups_text = "\n".join(f"  {g}: {c} чел." for g, c in top_groups)
    last_sent = load_last_sent()
    today = datetime.now().strftime("%Y-%m-%d")
    sent_today = "✅ Да" if last_sent == today else "❌ Нет"
    stats_text = (
        f"📊 **Статистика**\n\n"
        f"👥 Всего: {total}\n"
        f"📚 Популярные группы:\n{groups_text}\n\n"
        f"📅 Финальная рассылка сегодня: {sent_today}"
    )
    bot.send_message(message.chat.id, stats_text, parse_mode='Markdown')
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'rb') as f:
            bot.send_document(message.chat.id, f, caption="📁 users.json")

# ===== ОБРАБОТЧИКИ ОСНОВНЫХ КОМАНД =====
@bot.message_handler(commands=['start'])
def cmd_start(message):
    uid = message.from_user.id
    if is_user_registered(uid):
        ud = get_user_data(uid)
        bot.send_message(uid, f"👋 С возвращением, {ud['first_name']} {ud['last_name']}!\nВаша группа: {ud['group']}\n\nИспользуйте /help.", reply_markup=ReplyKeyboardRemove())
    else:
        if uid in user_states:
            bot.send_message(uid, "Вы уже начали регистрацию.")
            return
        user_states[uid] = {'action': 'register', 'step': 'fullname'}
        bot.send_message(uid, "Добро пожаловать! Введите ваши Имя и Фамилию одной строкой (например, Иван Иванов):", reply_markup=ReplyKeyboardRemove())

@bot.message_handler(commands=['help'])
def cmd_help(message):
    user_id = message.from_user.id
    is_admin = (user_id == ADMIN_ID)
    
    help_text = "📋 Список команд:\n\n"
    help_text += "/start — Начните использовать бота\n"
    help_text += "/help — Справка\n"
    help_text += "/edit_name — Изменить имя и фамилию\n"
    help_text += "/setgroup — Изменить группу\n"
    help_text += "/getrasp — Расписание на сегодня (PDF)\n"
    help_text += "/tomorrow — Расписание на завтра (PDF)\n"
    help_text += "/getdata — Замены на ближайшие дни\n"
    help_text += "/gettoday — Замены на сегодня\n"
    help_text += "/getbell — Расписание звонков\n"
    help_text += "/getweek — Тип недели\n"
    
    if is_admin:
        help_text += "\n🔐 Админ-команды:\n"
        help_text += "/stats — Статистика пользователей\n"
        help_text += "/broadcast — Массовая рассылка\n"
        help_text += "/sendto — Отправить личное сообщение\n"
    
    bot.send_message(message.chat.id, help_text)

@bot.message_handler(commands=['edit_name'])
def cmd_edit_name(message):
    uid = message.from_user.id
    if not is_user_registered(uid):
        bot.send_message(uid, "❌ Сначала зарегистрируйтесь.")
        return
    if uid in user_states:
        bot.send_message(uid, "❌ Вы уже в процессе.")
        return
    user_states[uid] = {'action': 'edit_name', 'step': 'fullname'}
    bot.send_message(uid, "Введите новые Имя и Фамилию одной строкой:")

@bot.message_handler(commands=['setgroup'])
def cmd_setgroup(message):
    uid = message.from_user.id
    if not is_user_registered(uid):
        bot.send_message(uid, "❌ Сначала зарегистрируйтесь.")
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        bot.reply_to(message, "❌ Вы не указали группу. Просто напишите её в чат, например: ПЭУ65")
        return
    group = normalize_group(args[1])
    if group not in SCHEDULE_LINKS:
        bot.reply_to(message, f"❌ Группа {group} не найдена.")
        return
    if update_user_group(uid, group):
        bot.send_message(uid, f"✅ Группа изменена на {group}.")
    else:
        bot.send_message(uid, "❌ Ошибка.")

@bot.message_handler(commands=['getweek'])
def cmd_getweek(message):
    uid = message.from_user.id
    if not is_user_registered(uid):
        bot.send_message(uid, "❌ Сначала зарегистрируйтесь.")
        return
    bot.send_message(uid, f"📅 Сейчас {get_week_type()} неделя.")

@bot.message_handler(commands=['getrasp'])
def cmd_getrasp(message):
    uid = message.from_user.id
    if not is_user_registered(uid):
        bot.send_message(uid, "❌ Сначала зарегистрируйтесь.")
        return
    ud = get_user_data(uid)
    group = ud['group']
    url = SCHEDULE_LINKS.get(group.upper())
    if not url:
        bot.send_message(uid, f"❌ Для группы {group} нет ссылки.")
        return
    bot.send_message(uid, f"📥 Загружаю расписание...")
    send_pdf(uid, url, group)

@bot.message_handler(commands=['tomorrow'])
def cmd_tomorrow(message):
    cmd_getrasp(message)

@bot.message_handler(commands=['gettoday'])
def cmd_gettoday(message):
    uid = message.from_user.id
    if not is_user_registered(uid):
        bot.send_message(uid, "❌ Сначала зарегистрируйтесь через /start.")
        return
    ud = get_user_data(uid)
    group = ud['group']

    bot.send_message(uid, "🔍 Ищу замены на сегодня...")

    reps, day_name, date_str = get_today_replacements()
    if reps is None:
        bot.send_message(uid, f"❌ На сегодня ({day_name} {date_str}) замен нет.")
        return
    filtered = filter_replacements_by_group(reps, group)
    if filtered:
        answer = format_replacements(filtered, group, day_name, date_str)
    else:
        answer = f"❌ На сегодня ({day_name} {date_str}) замен для группы {group} нет."
    bot.send_message(uid, answer)

@bot.message_handler(commands=['getdata'])
def cmd_getdata(message):
    uid = message.from_user.id
    if not is_user_registered(uid):
        bot.send_message(uid, "❌ Сначала зарегистрируйтесь.")
        return
    ud = get_user_data(uid)
    group = ud['group']

    bot.send_message(uid, "🔍 Ищу замены...")

    replacements_list = get_next_replacements()
    for reps, day_name, date_str in replacements_list:
        if reps is not None:
            filtered = filter_replacements_by_group(reps, group)
            if filtered:
                answer = format_replacements(filtered, group, day_name, date_str)
            else:
                answer = f"❌ На {day_name} {date_str} замен для группы {group} нет."
        else:
            answer = f"❌ На {day_name} {date_str} замен для группы {group} нет."
        bot.send_message(uid, answer)

@bot.message_handler(commands=['getbell'])
def cmd_getbell(message):
    uid = message.from_user.id
    if not is_user_registered(uid):
        bot.send_message(uid, "❌ Сначала зарегистрируйтесь.")
        return
    bot.send_message(uid, get_zvonki())

# ===== ОБРАБОТЧИК ТЕКСТОВЫХ СООБЩЕНИЙ =====
@bot.message_handler(func=lambda m: not m.text.startswith('/'))
def handle_text(message):
    uid = message.from_user.id
    text = message.text.strip()

    if uid in user_states:
        state = user_states[uid]
        action = state['action']
        if action == 'register':
            if state['step'] == 'fullname':
                validated = validate_full_name(text)
                if not validated:
                    bot.send_message(uid, "❌ Некорректные имя или фамилия.")
                    return
                first_name, last_name = validated
                state['temp_data'] = {'first_name': first_name, 'last_name': last_name}
                state['step'] = 'group'
                bot.send_message(uid, "Теперь введите вашу группу (например, ПЭУ65):")
                return
            elif state['step'] == 'group':
                group = normalize_group(text)
                if group not in SCHEDULE_LINKS:
                    bot.send_message(uid, f"❌ Группа '{group}' не найдена.")
                    return
                temp = state.get('temp_data', {})
                first_name = temp.get('first_name')
                last_name = temp.get('last_name')
                if not first_name or not last_name:
                    bot.send_message(uid, "❌ Ошибка. Начните заново.")
                    del user_states[uid]
                    return
                set_user_data(uid, first_name, last_name, group)
                del user_states[uid]
                bot.send_message(uid, f"✅ Регистрация завершена, {first_name} {last_name}!\nВаша группа: {group}")
                return
        elif action == 'edit_name':
            if state['step'] == 'fullname':
                validated = validate_full_name(text)
                if not validated:
                    bot.send_message(uid, "❌ Некорректные имя или фамилия.")
                    return
                first_name, last_name = validated
                if update_user_name(uid, first_name, last_name):
                    bot.send_message(uid, f"✅ Имя и фамилия изменены.")
                else:
                    bot.send_message(uid, "❌ Ошибка.")
                del user_states[uid]
                return

    if is_user_registered(uid):
        group = normalize_group(text)
        if group in SCHEDULE_LINKS:
            if update_user_group(uid, group):
                bot.send_message(uid, f"✅ Группа изменена на {group}.")
            else:
                bot.send_message(uid, "❌ Ошибка.")
        else:
            bot.send_message(uid, "❌ Неизвестная команда. Введите /help.")
        return

    bot.send_message(uid, "❌ Пожалуйста, начните с /start.")

# ===== ЗАПУСК =====
if __name__ == "__main__":
    print("Бот запущен...")
    
    # Запускаем мониторинг (круглосуточно, каждые 15 минут)
    monitor_thread = threading.Thread(target=monitor_updates)
    monitor_thread.daemon = True
    monitor_thread.start()
    
    # Запускаем планировщик финальной рассылки (в 17:20)
    final_thread = threading.Thread(target=final_scheduler)
    final_thread.daemon = True
    final_thread.start()
    
    bot.infinity_polling()
