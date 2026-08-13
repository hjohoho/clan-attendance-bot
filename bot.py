import requests
import json
import sqlite3
import time
import re
from datetime import datetime, timedelta

BOT_TOKEN = "8975094107:AAHAyExCPty9LsFavS1u2b31Od4sGYbrNkg"
ADMIN_IDS = [1462367346, 8785617232]
CREATOR_ID = 1462367346

conn = sqlite3.connect("attendance.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, last_seen TEXT, warnings INTEGER DEFAULT 0, missed_gatherings INTEGER DEFAULT 0)")
cursor.execute("CREATE TABLE IF NOT EXISTS attendance (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, present TEXT, absent TEXT, fines TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS fines (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, username TEXT, first_name TEXT, amount INTEGER, reason TEXT, date TEXT, paid INTEGER DEFAULT 0)")
cursor.execute("CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY, username TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS warnings (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, reason TEXT, date TEXT, type TEXT)")
conn.commit()

cursor.execute("INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)", (CREATOR_ID, "PD777DP", "виджет"))
cursor.execute("INSERT OR IGNORE INTO admins (user_id, username) VALUES (?, ?)", (CREATOR_ID, "PD777DP"))
for uid in ADMIN_IDS:
    cursor.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (uid,))
conn.commit()

def is_admin(user_id):
    if user_id == CREATOR_ID:
        return True
    cursor.execute("SELECT user_id FROM admins WHERE user_id = ?", (user_id,))
    return cursor.fetchone() is not None

def send(chat_id, text, kb=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if kb:
        data["reply_markup"] = json.dumps(kb)
    try:
        requests.post(url, json=data, timeout=10)
    except:
        pass

def mention(user_id, username, name):
    if username:
        return f'<a href="tg://user?id={user_id}">@{username}</a>'
    return name

def get_members():
    cursor.execute("SELECT user_id, username, first_name, last_seen, warnings, missed_gatherings FROM users")
    return cursor.fetchall()

def add_fine(user_id, username, first_name, amount, reason):
    try:
        cursor.execute("INSERT INTO fines (user_id, username, first_name, amount, reason, date, paid) VALUES (?, ?, ?, ?, ?, ?, ?)", 
                       (user_id, username, first_name, amount, reason, datetime.now().strftime("%d.%m.%Y %H:%M"), 0))
        conn.commit()
        fine_id = cursor.lastrowid
        # Отправка в ЛС
        send(user_id, f"⚠️ <b>ВЫ ПОЛУЧИЛИ ШТРАФ!</b>\n\n💰 Сумма: {amount} г\n📝 {reason}\n📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\nДля оплаты нажми /start и выбери 'Мои штрафы'")
        return fine_id
    except Exception as e:
        print("Ошибка add_fine:", e)
        return None

def add_warning(user_id, reason, warning_type="warning"):
    cursor.execute("INSERT INTO warnings (user_id, reason, date, type) VALUES (?, ?, ?, ?)", 
                   (user_id, reason, datetime.now().strftime("%d.%m.%Y %H:%M"), warning_type))
    conn.commit()
    cursor.execute("UPDATE users SET warnings = warnings + 1 WHERE user_id = ?", (user_id,))
    conn.commit()

def pay_fine(fine_id):
    try:
        cursor.execute("UPDATE fines SET paid = 1 WHERE id = ?", (fine_id,))
        conn.commit()
        return True
    except:
        return False

def get_fines_by_user(user_id):
    cursor.execute("SELECT id, amount, reason, date, paid FROM fines WHERE user_id = ? ORDER BY date DESC", (user_id,))
    return cursor.fetchall()

def update_missed_gatherings(user_id):
    cursor.execute("UPDATE users SET missed_gatherings = missed_gatherings + 1 WHERE user_id = ?", (user_id,))
    conn.commit()

def get_missed_gatherings(user_id):
    cursor.execute("SELECT missed_gatherings FROM users WHERE user_id = ?", (user_id,))
    r = cursor.fetchone()
    return r[0] if r else 0

def remove_player_from_db(user_id):
    if user_id == CREATOR_ID:
        return False
    cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
    conn.commit()
    cursor.execute("DELETE FROM fines WHERE user_id = ?", (user_id,))
    conn.commit()
    cursor.execute("DELETE FROM warnings WHERE user_id = ?", (user_id,))
    conn.commit()
    return True

def add_admin(user_id, username):
    cursor.execute("INSERT OR IGNORE INTO admins (user_id, username) VALUES (?, ?)", (user_id, username))
    conn.commit()

def remove_admin(user_id):
    if user_id == CREATOR_ID:
        return False
    cursor.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
    conn.commit()
    return True

def get_admins():
    cursor.execute("SELECT user_id, username FROM admins")
    return cursor.fetchall()

state = {}

def admin_menu():
    return {"inline_keyboard": [
        [{"text": "➕ Добавить игрока", "callback_data": "add_player"}],
        [{"text": "❌ Удалить игрока", "callback_data": "remove_player"}],
        [{"text": "📝 Начать сбор", "callback_data": "start"}],
        [{"text": "📅 Отметить неактивных", "callback_data": "inactive"}],
        [{"text": "💰 Назначить штраф", "callback_data": "new_fine"}],
        [{"text": "✅ Оплатить штраф", "callback_data": "pay_fine"}],
        [{"text": "📋 Массовый штраф", "callback_data": "mass_fine"}],
        [{"text": "✅ Массовая оплата", "callback_data": "mass_pay"}],
        [{"text": "📊 Отчёты по сборам", "callback_data": "report"}],
        [{"text": "💰 Все штрафы", "callback_data": "fines"}],
        [{"text": "👥 Список клана", "callback_data": "list"}],
        [{"text": "👑 Добавить админа", "callback_data": "add_admin"}],
        [{"text": "👑 Удалить админа", "callback_data": "remove_admin"}]
    ]}

def player_menu():
    return {"inline_keyboard": [
        [{"text": "💰 Мои штрафы", "callback_data": "my_fines"}],
        [{"text": "📊 Отчёты по сборам", "callback_data": "report"}]
    ]}

def fine_punkt_menu():
    return {"inline_keyboard": [
        [{"text": "📌 Пункт 1: Убийство союзника (5 г)", "callback_data": "fine_punkt_1"}],
        [{"text": "📌 Пункт 2: Пропуск сбора (5 г +10 за повтор)", "callback_data": "fine_punkt_2"}],
        [{"text": "📌 Пункт 3: Спам в чате (5 г +5 за повтор)", "callback_data": "fine_punkt_3"}],
        [{"text": "📌 Пункт 4: Самовольный захват базы (10 г)", "callback_data": "fine_punkt_4"}],
        [{"text": "📌 Пункт 5: Неявка на защиту базы (10 г)", "callback_data": "fine_punkt_5"}],
        [{"text": "📌 Пункт 6: Неявка на босса (10 г)", "callback_data": "fine_punkt_6"}],
        [{"text": "📌 Пункт 7: Неактивность 4+ дней (15 г)", "callback_data": "fine_punkt_7"}],
        [{"text": "📌 Пункт 8: Выход во время строя (15 г)", "callback_data": "fine_punkt_8"}],
        [{"text": "📌 Пункт 9: Оскорбления (5-50 г)", "callback_data": "fine_punkt_9"}],
        [{"text": "📌 Пункт 10: Нарушение в строю (3-30 г)", "callback_data": "fine_punkt_10"}],
        [{"text": "📌 Пункт 11: Оскорбление руководства (50 г)", "callback_data": "fine_punkt_11"}],
        [{"text": "📌 Пункт 12: Продажа экипировки (50 г)", "callback_data": "fine_punkt_12"}],
        [{"text": "📌 Пункт 13: Провокация войны (50 г)", "callback_data": "fine_punkt_13"}],
        [{"text": "📌 Пункт 14: Убийство союзника умышл. (50 г)", "callback_data": "fine_punkt_14"}],
        [{"text": "📌 Пункт 15: Шпионство (ЧС+КИК)", "callback_data": "fine_punkt_15"}],
        [{"text": "📌 Пункт 16: Скам (ЧС+КИК)", "callback_data": "fine_punkt_16"}]
    ]}

def pay_punkt_menu():
    return {"inline_keyboard": [
        [{"text": "✅ Оплатить пункт 1", "callback_data": "pay_punkt_1"}],
        [{"text": "✅ Оплатить пункт 2", "callback_data": "pay_punkt_2"}],
        [{"text": "✅ Оплатить пункт 3", "callback_data": "pay_punkt_3"}],
        [{"text": "✅ Оплатить пункт 4", "callback_data": "pay_punkt_4"}],
        [{"text": "✅ Оплатить пункт 5", "callback_data": "pay_punkt_5"}],
        [{"text": "✅ Оплатить пункт 6", "callback_data": "pay_punkt_6"}],
        [{"text": "✅ Оплатить пункт 7", "callback_data": "pay_punkt_7"}],
        [{"text": "✅ Оплатить пункт 8", "callback_data": "pay_punkt_8"}],
        [{"text": "✅ Оплатить пункт 9", "callback_data": "pay_punkt_9"}],
        [{"text": "✅ Оплатить пункт 10", "callback_data": "pay_punkt_10"}],
        [{"text": "✅ Оплатить пункт 11", "callback_data": "pay_punkt_11"}],
        [{"text": "✅ Оплатить пункт 12", "callback_data": "pay_punkt_12"}],
        [{"text": "✅ Оплатить пункт 13", "callback_data": "pay_punkt_13"}],
        [{"text": "✅ Оплатить пункт 14", "callback_data": "pay_punkt_14"}],
        [{"text": "✅ Оплатить пункт 15", "callback_data": "pay_punkt_15"}],
        [{"text": "✅ Оплатить пункт 16", "callback_data": "pay_punkt_16"}]
    ]}

def get_punkt_info(punkt_num):
    punkte = {
        1: {"name": "Убийство союзника", "base": 5},
        2: {"name": "Пропуск сбора", "base": 5},
        3: {"name": "Спам в чате", "base": 5},
        4: {"name": "Самовольный захват базы", "base": 10},
        5: {"name": "Неявка на защиту базы", "base": 10},
        6: {"name": "Неявка на босса", "base": 10},
        7: {"name": "Неактивность 4+ дней", "base": 15},
        8: {"name": "Выход во время строя", "base": 15},
        9: {"name": "Оскорбления", "base": 10},
        10: {"name": "Нарушение в строю", "base": 5},
        11: {"name": "Оскорбление руководства", "base": 50},
        12: {"name": "Продажа экипировки из казны", "base": 50},
        13: {"name": "Провокация войны", "base": 50},
        14: {"name": "Умышленное убийство союзника", "base": 50},
        15: {"name": "Шпионство/слив данных", "base": 0},
        16: {"name": "Скам игрока", "base": 0}
    }
    return punkte.get(punkt_num, {"name": "Неизвестно", "base": 0})

def handle(update):
    global state
    if "message" in update:
        m = update["message"]
        cid = m["chat"]["id"]
        uid = m["from"]["id"]
        
        if "text" not in m:
            return
        t = m["text"].strip()
        
        if t == "/start":
            if is_admin(uid):
                send(cid, "👑 <b>АДМИН-ПАНЕЛЬ</b>\n\nВыбери действие:", admin_menu())
            else:
                send(cid, "📋 <b>ПАНЕЛЬ ИГРОКА</b>\n\nТы можешь смотреть свои штрафы и отчёты:", player_menu())
            return
        
        # Добавление игрока
        if uid in state and state[uid].get("step") == "add_player":
            if not is_admin(uid):
                send(cid, "⛔ Только админ!")
                del state[uid]
                return
            name = t
            username_db = None
            first_name = name
            if "@" in name:
                parts = name.split()
                for p in parts:
                    if p.startswith("@"):
                        username_db = p.replace("@", "")
                        first_name = name.replace(p, "").strip()
                if not first_name:
                    first_name = username_db
            cursor.execute("INSERT OR IGNORE INTO users (user_id, username, first_name, last_seen) VALUES (?, ?, ?, ?)", 
                           (0, username_db, first_name, datetime.now().strftime("%d.%m.%Y")))
            conn.commit()
            send(cid, f"✅ Игрок <b>{first_name}</b> добавлен в клан!")
            del state[uid]
            return
        
        # Удаление игрока
        if uid in state and state[uid].get("step") == "remove_player":
            if not is_admin(uid):
                send(cid, "⛔ Только админ!")
                del state[uid]
                return
            name = t
            cursor.execute("SELECT user_id FROM users WHERE first_name = ? OR username = ?", (name, name.replace("@", "")))
            r = cursor.fetchone()
            if r:
                if r[0] == CREATOR_ID:
                    send(cid, "⛔ Нельзя удалить создателя!")
                else:
                    remove_player_from_db(r[0])
                    send(cid, f"❌ Игрок <b>{name}</b> удалён из клана!")
            else:
                send(cid, f"❌ Игрок <b>{name}</b> не найден!")
            del state[uid]
            return
        
        # Добавление админа
        if uid in state and state[uid].get("step") == "add_admin":
            if not is_admin(uid):
                send(cid, "⛔ Только админ!")
                del state[uid]
                return
            username_db = t.replace("@", "")
            cursor.execute("SELECT user_id FROM users WHERE username = ?", (username_db,))
            r = cursor.fetchone()
            if r:
                add_admin(r[0], username_db)
                send(cid, f"✅ <b>@{username_db}</b> теперь админ!")
            else:
                send(cid, f"❌ @{username_db} не найден в базе игроков! Сначала добавь его через /add")
            del state[uid]
            return
        
        # Удаление админа
        if uid in state and state[uid].get("step") == "remove_admin":
            if not is_admin(uid):
                send(cid, "⛔ Только админ!")
                del state[uid]
                return
            username_db = t.replace("@", "")
            cursor.execute("SELECT user_id FROM admins WHERE username = ?", (username_db,))
            r = cursor.fetchone()
            if r:
                if r[0] == CREATOR_ID:
                    send(cid, "⛔ Нельзя удалить создателя!")
                else:
                    remove_admin(r[0])
                    send(cid, f"❌ <b>@{username_db}</b> больше не админ!")
            else:
                send(cid, f"❌ Админ @{username_db} не найден!")
            del state[uid]
            return
        
        # Сбор
        if uid in state and state[uid].get("step") == "present":
            if not is_admin(uid):
                send(cid, "⛔ Только админ!")
                del state[uid]
                return
            names = [x.strip() for x in t.split(",")]
            state[uid]["present"] = names
            state[uid]["step"] = "done"
            report_gathering(cid, uid)
            return
        
        # Неактивные
        if uid in state and state[uid].get("step") == "inactive_name":
            if not is_admin(uid):
                send(cid, "⛔ Только админ!")
                del state[uid]
                return
            state[uid]["name"] = t
            state[uid]["step"] = "inactive_date"
            send(cid, f"👤 <b>{t}</b>\n\n📅 Введи последнюю дату входа (ДД.ММ.ГГГГ):")
            return
        
        if uid in state and state[uid].get("step") == "inactive_date":
            if not is_admin(uid):
                send(cid, "⛔ Только админ!")
                del state[uid]
                return
            try:
                last_date = datetime.strptime(t, "%d.%m.%Y")
                name = state[uid]["name"]
                days = (datetime.now() - last_date).days
                cursor.execute("SELECT user_id, username, first_name FROM users WHERE first_name = ? OR username = ?", (name, name.replace("@", "")))
                r = cursor.fetchone()
                if not r:
                    send(cid, f"❌ Игрок <b>{name}</b> не найден!")
                    del state[uid]
                    return
                user_id, username_db, first_name = r
                if days >= 4:
                    amount = 15
                    reason = f"Пункт 7: Неактивность {days} дней"
                    add_fine(user_id, username_db, first_name, amount, reason)
                    add_warning(user_id, f"Неактивность {days} дней (авто)", "reprimand")
                    send(cid, f"⚠️ <b>ШТРАФ ЗА НЕАКТИВНОСТЬ</b>\n\n👤 {mention(user_id, username_db, first_name)}\n📅 Не был {days} дней\n💰 {amount} г\n📌 + Выговор")
                else:
                    send(cid, f"✅ {mention(user_id, username_db, first_name)} — {days} дней, штраф не требуется.")
                cursor.execute("UPDATE users SET last_seen = ? WHERE user_id = ?", (t, user_id))
                conn.commit()
            except:
                send(cid, "❌ Неверный формат! Используй ДД.ММ.ГГГГ")
            del state[uid]
            return
        
        # Массовый штраф
        if uid in state and state[uid].get("step") == "mass_fine_names":
            if not is_admin(uid):
                send(cid, "⛔ Только админ!")
                del state[uid]
                return
            names = [x.strip() for x in t.split(',')]
            state[uid]["mass_names"] = names
            send(cid, f"✅ Найдено {len(names)} имён\n\n📌 <b>ВЫБЕРИ ПУНКТ ШТРАФА:</b>", fine_punkt_menu())
            return
        
        # Массовая оплата
        if uid in state and state[uid].get("step") == "mass_pay_names":
            if not is_admin(uid):
                send(cid, "⛔ Только админ!")
                del state[uid]
                return
            names = [x.strip() for x in t.split(',')]
            state[uid]["mass_pay_names"] = names
            send(cid, f"✅ Найдено {len(names)} имён\n\n📌 <b>ВЫБЕРИ ПУНКТ ДЛЯ ОПЛАТЫ:</b>", pay_punkt_menu())
            return
        
        # Оплата штрафа - ввод имени
        if uid in state and state[uid].get("step") == "pay_name":
            if not is_admin(uid):
                send(cid, "⛔ Только админ!")
                del state[uid]
                return
            state[uid]["pay_name"] = t
            send(cid, f"👤 <b>{t}</b>\n\n📌 <b>ВЫБЕРИ ПУНКТ ДЛЯ ОПЛАТЫ:</b>", pay_punkt_menu())
            return
        
        # Назначение штрафа - ввод имени
        if uid in state and state[uid].get("step") == "fine_name":
            if not is_admin(uid):
                send(cid, "⛔ Только админ!")
                del state[uid]
                return
            state[uid]["fine_name"] = t
            send(cid, f"👤 <b>{t}</b>\n\n📌 <b>ВЫБЕРИ ПУНКТ ШТРАФА:</b>", fine_punkt_menu())
            return
    
    if "callback_query" in update:
        c = update["callback_query"]
        cid = c["message"]["chat"]["id"]
        uid = c["from"]["id"]
        data = c["data"]
        
        # Игрок: мои штрафы
        if data == "my_fines":
            show_my_fines(cid, uid)
            return
        
        if data == "report":
            show_gathering_reports(cid)
            return
        
        # Проверка админа
        if not is_admin(uid):
            send(cid, "⛔ Только админ!")
            return
        
        # Админ: добавление/удаление
        if data == "add_player":
            state[uid] = {"step": "add_player"}
            send(cid, "➕ <b>ДОБАВИТЬ ИГРОКА</b>\n\nВведи имя (можно с @username):")
            return
        
        if data == "remove_player":
            state[uid] = {"step": "remove_player"}
            send(cid, "❌ <b>УДАЛИТЬ ИГРОКА</b>\n\nВведи имя или @username:")
            return
        
        if data == "add_admin":
            state[uid] = {"step": "add_admin"}
            send(cid, "👑 <b>ДОБАВИТЬ АДМИНА</b>\n\nВведи @username:")
            return
        
        if data == "remove_admin":
            state[uid] = {"step": "remove_admin"}
            send(cid, "👑 <b>УДАЛИТЬ АДМИНА</b>\n\nВведи @username:")
            return
        
        if data == "start":
            state[uid] = {"step": "present", "present": []}
            send(cid, "📝 <b>НАЧАТЬ СБОР</b>\n\nВведи список ПРИСУТСТВУЮЩИХ через запятую:")
            return
        
        if data == "inactive":
            state[uid] = {"step": "inactive_name"}
            send(cid, "📅 <b>ОТМЕТИТЬ НЕАКТИВНЫХ</b>\n\nВведи имя:")
            return
        
        if data == "new_fine":
            state[uid] = {"step": "fine_name"}
            send(cid, "💰 <b>НАЗНАЧИТЬ ШТРАФ</b>\n\nВведи имя:")
            return
        
        if data == "pay_fine":
            state[uid] = {"step": "pay_name"}
            send(cid, "✅ <b>ОПЛАТИТЬ ШТРАФ</b>\n\nВведи имя:")
            return
        
        if data == "mass_fine":
            state[uid] = {"step": "mass_fine_names"}
            send(cid, "📋 <b>МАССОВЫЙ ШТРАФ</b>\n\nВведи список имён через запятую:")
            return
        
        if data == "mass_pay":
            state[uid] = {"step": "mass_pay_names"}
            send(cid, "✅ <b>МАССОВАЯ ОПЛАТА</b>\n\nВведи список имён через запятую:")
            return
        
        # НАЗНАЧЕНИЕ ШТРАФА ПО ПУНКТУ
        if data.startswith("fine_punkt_"):
            punkt_num = int(data.split("_")[2])
            punkt_info = get_punkt_info(punkt_num)
            
            # Массовый штраф
            if "mass_names" in state.get(uid, {}):
                names = state[uid]["mass_names"]
                count = 0
                for name in names:
                    cursor.execute("SELECT user_id, username, first_name, missed_gatherings FROM users WHERE first_name = ? OR username = ?", (name, name.replace("@", "")))
                    r = cursor.fetchone()
                    if r:
                        user_id, username_db, first_name, missed = r
                        if punkt_num == 2:
                            amount = 5 + (missed * 10)
                            reason = f"Пункт 2: Пропуск сбора (пропусков подряд: {missed + 1})"
                        elif punkt_num == 3:
                            cursor.execute("SELECT COUNT(*) FROM fines WHERE user_id = ? AND reason LIKE '%Пункт 3%'", (user_id,))
                            spam_count = cursor.fetchone()[0]
                            amount = 5 + (spam_count * 5)
                            reason = f"Пункт 3: Спам в чате (повторов: {spam_count + 1})"
                        elif punkt_num in [15, 16]:
                            amount = 0
                            reason = f"Пункт {punkt_num}: {punkt_info['name']} - ЧС + КИК!"
                            add_warning(user_id, f"Пункт {punkt_num}: {punkt_info['name']}", "cs")
                            send(user_id, f"⛔ <b>ВЫ ИСКЛЮЧЕНЫ ИЗ КЛАНА!</b>\n\n{reason}")
                            remove_player_from_db(user_id)
                            continue
                        else:
                            amount = punkt_info["base"]
                            reason = f"Пункт {punkt_num}: {punkt_info['name']}"
                        
                        if punkt_num not in [15, 16]:
                            add_fine(user_id, username_db, first_name, amount, reason)
                            if punkt_num == 1:
                                add_warning(user_id, f"Пункт {punkt_num}: {punkt_info['name']}", "warning")
                            count += 1
                send(cid, f"✅ Назначено штрафов: {count}")
                del state[uid]
                return
            
            # Обычный штраф
            if "fine_name" in state.get(uid, {}):
                name = state[uid]["fine_name"]
                cursor.execute("SELECT user_id, username, first_name, missed_gatherings FROM users WHERE first_name = ? OR username = ?", (name, name.replace("@", "")))
                r = cursor.fetchone()
                if r:
                    user_id, username_db, first_name, missed = r
                    if punkt_num == 2:
                        amount = 5 + (missed * 10)
                        reason = f"Пункт 2: Пропуск сбора (пропусков подряд: {missed + 1})"
                    elif punkt_num == 3:
                        cursor.execute("SELECT COUNT(*) FROM fines WHERE user_id = ? AND reason LIKE '%Пункт 3%'", (user_id,))
                        spam_count = cursor.fetchone()[0]
                        amount = 5 + (spam_count * 5)
                        reason = f"Пункт 3: Спам в чате (повторов: {spam_count + 1})"
                    elif punkt_num in [15, 16]:
                        amount = 0
                        reason = f"Пункт {punkt_num}: {punkt_info['name']} - ЧС + КИК!"
                        add_warning(user_id, f"Пункт {punkt_num}: {punkt_info['name']}", "cs")
                        send(user_id, f"⛔ <b>ВЫ ИСКЛЮЧЕНЫ ИЗ КЛАНА!</b>\n\n{reason}")
                        send(cid, f"⛔ <b>{mention(user_id, username_db, first_name)} ИСКЛЮЧЕН!</b>\n\n{reason}")
                        remove_player_from_db(user_id)
                        del state[uid]
                        return
                    else:
                        amount = punkt_info["base"]
                        reason = f"Пункт {punkt_num}: {punkt_info['name']}"
                    
                    if punkt_num not in [15, 16]:
                        add_fine(user_id, username_db, first_name, amount, reason)
                        if punkt_num == 1:
                            add_warning(user_id, f"Пункт {punkt_num}: {punkt_info['name']}", "warning")
                        send(cid, f"✅ Штраф назначен!\n\n👤 {mention(user_id, username_db, first_name)}\n💰 {amount} г\n📝 {reason}")
                else:
                    send(cid, f"❌ Игрок <b>{name}</b> не найден!")
                del state[uid]
                return
        
        # ОПЛАТА ШТРАФА ПО ПУНКТУ
        if data.startswith("pay_punkt_"):
            punkt_num = int(data.split("_")[2])
            punkt_info = get_punkt_info(punkt_num)
            
            # Массовая оплата
            if "mass_pay_names" in state.get(uid, {}):
                names = state[uid]["mass_pay_names"]
                count = 0
                for name in names:
                    cursor.execute("SELECT user_id FROM users WHERE first_name = ? OR username = ?", (name, name.replace("@", "")))
                    r = cursor.fetchone()
                    if r:
                        user_id = r[0]
                        fines = get_fines_by_user(user_id)
                        for fine_id, amount, reason, date, paid in fines:
                            if paid == 0 and f"Пункт {punkt_num}:" in reason:
                                pay_fine(fine_id)
                                count += 1
                send(cid, f"✅ Оплачено штрафов: {count} по пункту {punkt_num}")
                del state[uid]
                return
            
            # Оплата для одного игрока
            if "pay_name" in state.get(uid, {}):
                name = state[uid]["pay_name"]
                cursor.execute("SELECT user_id FROM users WHERE first_name = ? OR username = ?", (name, name.replace("@", "")))
                r = cursor.fetchone()
                if r:
                    user_id = r[0]
                    fines = get_fines_by_user(user_id)
                    count = 0
                    for fine_id, amount, reason, date, paid in fines:
                        if paid == 0 and f"Пункт {punkt_num}:" in reason:
                            pay_fine(fine_id)
                            count += 1
                    if count > 0:
                        send(cid, f"✅ Оплачено {count} штрафов для <b>{name}</b> по пункту {punkt_num}!")
                    else:
                        send(cid, f"❌ У <b>{name}</b> нет неоплаченных штрафов по пункту {punkt_num}!")
                else:
                    send(cid, f"❌ Игрок <b>{name}</b> не найден!")
                del state[uid]
                return
        
        if data == "fines":
            show_all_fines(cid)
            return
        
        if data == "list":
            show_clan_list(cid)
            return

def show_my_fines(cid, uid):
    cursor.execute("SELECT id, amount, reason, date, paid FROM fines WHERE user_id = ? ORDER BY date DESC", (uid,))
    fines = cursor.fetchall()
    if not fines:
        send(cid, "💰 У вас нет штрафов.")
        return
    text = "💰 <b>ВАШИ ШТРАФЫ</b>\n\n"
    total = 0
    for fine_id, amount, reason, date, paid in fines:
        status = "✅ Оплачен" if paid else "❌ Не оплачен"
        text += f"• #{fine_id} — {amount} г ({status})\n  📝 {reason}\n  📅 {date}\n"
        total += amount if not paid else 0
    text += f"\n<b>Всего к оплате: {total} г</b>"
    send(cid, text)

def show_all_fines(cid):
    cursor.execute("SELECT id, user_id, username, first_name, amount, reason, date, paid FROM fines ORDER BY date DESC LIMIT 30")
    fines = cursor.fetchall()
    if not fines:
        send(cid, "💰 Нет штрафов.")
        return
    text = "💰 <b>ВСЕ ШТРАФЫ</b>\n\n"
    for fine_id, user_id, username_db, first_name, amount, reason, date, paid in fines:
        name = mention(user_id, username_db, first_name)
        status = "✅" if paid else "❌"
        text += f"• #{fine_id} {name} — {amount} г {status}\n  📝 {reason}\n  📅 {date}\n"
    send(cid, text)

def show_clan_list(cid):
    members = get_members()
    if not members:
        send(cid, "👥 Список клана пуст.")
        return
    text = "👥 <b>СПИСОК КЛАНА</b>\n\n"
    for user_id, username_db, first_name, last_seen, warnings, missed in members:
        name = mention(user_id, username_db, first_name)
        last = f" (последний раз: {last_seen})" if last_seen else ""
        warn = f" ⚠️{warnings}" if warnings > 0 else ""
        missed_text = f" 📝{missed}" if missed > 0 else ""
        text += f"• {name}{last}{warn}{missed_text}\n"
    send(cid, text)

def show_gathering_reports(cid):
    cursor.execute("SELECT date, present, absent FROM attendance ORDER BY date DESC LIMIT 10")
    reports = cursor.fetchall()
    if not reports:
        send(cid, "📊 Нет записей о сборах.")
        return
    text = "📊 <b>ОТЧЁТЫ ПО СБОРАМ</b>\n\n"
    for date, present, absent in reports:
        text += f"📅 {date}\n✅ {present if present else '—'}\n❌ {absent if absent else 'Все на месте!'}\n\n"
    send(cid, text)

def report_gathering(cid, uid):
    present = state[uid].get("present", [])
    all_users = get_members()
    
    all_names = [x[2] for x in all_users]
    present_norm = [x.lower().strip() for x in present]
    all_norm = [x.lower().strip() for x in all_names]
    
    absent = []
    absent_data = []
    for i, name in enumerate(all_names):
        if all_norm[i] not in present_norm:
            absent.append(name)
            absent_data.append(all_users[i])
    
    fines = ""
    for user_id, username_db, first_name, last_seen, warnings, missed in absent_data:
        missed_count = get_missed_gatherings(user_id)
        amount = 5 + (missed_count * 10)
        reason = f"Пункт 2: Пропуск сбора (пропусков подряд: {missed_count + 1})"
        add_fine(user_id, username_db, first_name, amount, reason)
        add_warning(user_id, f"Пункт 2: Пропуск сбора (пропусков: {missed_count + 1})", "reprimand")
        fines += f"{mention(user_id, username_db, first_name)} — {amount} г\n"
    
    cursor.execute("INSERT INTO attendance (date, present, absent, fines) VALUES (?, ?, ?, ?)", 
                   (datetime.now().strftime("%d.%m.%Y %H:%M"), 
                    ", ".join(present) if present else "—", 
                    ", ".join(absent) if absent else "—", 
                    fines if fines else "—"))
    conn.commit()
    
    send(cid, f"📊 <b>ОТЧЁТ ПО СБОРУ</b>\n📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n✅ <b>Присутствовали ({len(present)} чел):</b>\n{', '.join(present) if present else '—'}\n\n❌ <b>Отсутствовали ({len(absent)} чел):</b>\n{', '.join(absent) if absent else 'Все на месте! 🎉'}\n\n💰 <b>ШТРАФЫ:</b>\n{fines if fines else '—'}")
    
    if uid in state:
        del state[uid]

def main():
    print("🤖 БОТ ДЛЯ СБОРОВ ЗАПУЩЕН!")
    print("👑 Админы:", [x[1] for x in get_admins()])
    offset = 0
    while True:
        try:
            r = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates", params={"offset": offset, "timeout": 30})
            data = r.json()
            for u in data.get("result", []):
                if "message" in u:
                    handle(u)
                if "callback_query" in u:
                    handle(u)
                offset = u["update_id"] + 1
        except Exception as e:
            print("Ошибка:", e)
            time.sleep(5)

if __name__ == "__main__":
    main()
