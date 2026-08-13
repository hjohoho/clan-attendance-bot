import requests
import json
import sqlite3
import time
import re
from datetime import datetime, timedelta

BOT_TOKEN = "8975094107:AAHAyExCPty9LsFavS1u2b31Od4sGYbrNkg"
ADMIN_IDS = [1462367346, 8785617232]
CREATOR_ID = 1462367346  # @PD777DP

conn = sqlite3.connect("attendance.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, last_seen TEXT, warnings INTEGER DEFAULT 0, missed_gatherings INTEGER DEFAULT 0)")
cursor.execute("CREATE TABLE IF NOT EXISTS attendance (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, present TEXT, absent TEXT, fines TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS fines (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, username TEXT, first_name TEXT, amount INTEGER, reason TEXT, date TEXT, paid INTEGER DEFAULT 0)")
cursor.execute("CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY, username TEXT)")
conn.commit()

# Добавляем создателя (виджет @PD777DP)
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

def is_creator(user_id):
    return user_id == CREATOR_ID

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
    cursor.execute("INSERT INTO fines (user_id, username, first_name, amount, reason, date, paid) VALUES (?, ?, ?, ?, ?, ?, ?)", 
                   (user_id, username, first_name, amount, reason, datetime.now().strftime("%d.%m.%Y %H:%M"), 0))
    conn.commit()
    fine_id = cursor.lastrowid
    send(user_id, f"⚠️ <b>ВЫ ПОЛУЧИЛИ ШТРАФ!</b>\n\n💰 Сумма: {amount} г\n📝 {reason}\n📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\nОплатите штраф администратору.")
    return fine_id

def pay_fine(fine_id):
    cursor.execute("UPDATE fines SET paid = 1 WHERE id = ?", (fine_id,))
    conn.commit()

def delete_fine(fine_id):
    cursor.execute("DELETE FROM fines WHERE id = ?", (fine_id,))
    conn.commit()

def get_user_fines(user_id):
    cursor.execute("SELECT id, amount, reason, date, paid FROM fines WHERE user_id = ? ORDER BY date DESC", (user_id,))
    return cursor.fetchall()

def get_fines_by_user(user_id):
    cursor.execute("SELECT id, amount, reason, date, paid FROM fines WHERE user_id = ? AND paid = 0 ORDER BY date DESC", (user_id,))
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
        [{"text": "📋 Массовый штраф", "callback_data": "mass_fine"}],
        [{"text": "✅ Подтвердить оплату", "callback_data": "confirm_payment"}],
        [{"text": "✅ Массовая оплата", "callback_data": "mass_pay"}],
        [{"text": "❌ Удалить штраф", "callback_data": "delete_fine_menu"}],
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
        [{"text": "📌 Пункт 10: Нарушение в строю (3-30 г)", "callback_data": "fine_punkt_10"}]
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
        10: {"name": "Нарушение в строю", "base": 5}
    }
    return punkte.get(punkt_num, {"name": "Неизвестно", "base": 0})

def handle(update):
    global state
    if "message" in update:
        m = update["message"]
        cid = m["chat"]["id"]
        uid = m["from"]["id"]
        
        if "text" in m:
            t = m["text"]
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
                    return
                name = t.strip()
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
                send(cid, f"✅ Игрок <b>{first_name}</b> добавлен!")
                del state[uid]
                return
            
            # Удаление игрока
            if uid in state and state[uid].get("step") == "remove_player":
                if not is_admin(uid):
                    send(cid, "⛔ Только админ!")
                    return
                name = t.strip()
                cursor.execute("SELECT user_id FROM users WHERE first_name = ? OR username = ?", (name, name.replace("@", "")))
                r = cursor.fetchone()
                if r:
                    if r[0] == CREATOR_ID:
                        send(cid, "⛔ Нельзя удалить создателя бота!")
                    else:
                        remove_player_from_db(r[0])
                        send(cid, f"❌ Игрок <b>{name}</b> удалён!")
                else:
                    send(cid, f"❌ Игрок <b>{name}</b> не найден!")
                del state[uid]
                return
            
            # Добавление админа
            if uid in state and state[uid].get("step") == "add_admin":
                if not is_admin(uid):
                    send(cid, "⛔ Только админ!")
                    return
                username_db = t.strip().replace("@", "")
                cursor.execute("SELECT user_id FROM users WHERE username = ?", (username_db,))
                r = cursor.fetchone()
                if r:
                    add_admin(r[0], username_db)
                    send(cid, f"✅ <b>@{username_db}</b> теперь админ!")
                else:
                    send(cid, f"❌ @{username_db} не найден в базе!")
                del state[uid]
                return
            
            # Удаление админа
            if uid in state and state[uid].get("step") == "remove_admin":
                if not is_admin(uid):
                    send(cid, "⛔ Только админ!")
                    return
                username_db = t.strip().replace("@", "")
                cursor.execute("SELECT user_id FROM admins WHERE username = ?", (username_db,))
                r = cursor.fetchone()
                if r:
                    if r[0] == CREATOR_ID:
                        send(cid, "⛔ Нельзя удалить создателя бота!")
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
                    return
                state[uid]["name"] = t.strip()
                state[uid]["step"] = "inactive_date"
                send(cid, f"👤 <b>{t}</b>\n\n📅 Введи последнюю дату входа (ДД.ММ.ГГГГ):")
                return
            
            if uid in state and state[uid].get("step") == "inactive_date":
                if not is_admin(uid):
                    send(cid, "⛔ Только админ!")
                    return
                try:
                    last_date = datetime.strptime(t.strip(), "%d.%m.%Y")
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
                        reason = f"Неактивность {days} дней"
                        add_fine(user_id, username_db, first_name, amount, reason)
                        send(cid, f"⚠️ <b>ШТРАФ ЗА НЕАКТИВНОСТЬ</b>\n\n👤 {mention(user_id, username_db, first_name)}\n📅 Не был {days} дней\n💰 {amount} г")
                    else:
                        send(cid, f"✅ {mention(user_id, username_db, first_name)} — {days} дней, штраф не требуется.")
                    cursor.execute("UPDATE users SET last_seen = ? WHERE user_id = ?", (t.strip(), user_id))
                    conn.commit()
                except:
                    send(cid, "❌ Неверный формат! Используй ДД.ММ.ГГГГ")
                del state[uid]
                return
            
            # Массовый штраф (ввод списка имён)
            if uid in state and state[uid].get("step") == "mass_fine_names":
                if not is_admin(uid):
                    send(cid, "⛔ Только админ!")
                    return
                names = [x.strip() for x in t.split(',')]
                state[uid]["mass_names"] = names
                send(cid, f"✅ Найдено {len(names)} имён\n\n📌 <b>ВЫБЕРИ ПУНКТ ШТРАФА:</b>", fine_punkt_menu())
                return
            
            # Массовая оплата (ввод списка имён)
            if uid in state and state[uid].get("step") == "mass_pay_names":
                if not is_admin(uid):
                    send(cid, "⛔ Только админ!")
                    return
                names = [x.strip() for x in t.split(',')]
                state[uid]["mass_pay_names"] = names
                send(cid, f"✅ Найдено {len(names)} имён\n\n📌 <b>ВЫБЕРИ ПУНКТ ДЛЯ ОПЛАТЫ:</b>", fine_punkt_menu())
                return
            
            # ===== НАЗНАЧЕНИЕ ШТРАФА - ВВОД ИМЕНИ =====
            if uid in state and state[uid].get("step") == "fine_name":
                if not is_admin(uid):
                    send(cid, "⛔ Только админ!")
                    return
                state[uid]["fine_name"] = t.strip()
                send(cid, f"👤 <b>{t}</b>\n\n📌 <b>ВЫБЕРИ ПУНКТ ШТРАФА:</b>", fine_punkt_menu())
                return
    
    if "callback_query" in update:
        c = update["callback_query"]
        cid = c["message"]["chat"]["id"]
        uid = c["from"]["id"]
        data = c["data"]
        
        # Игроки
        if data == "my_fines":
            show_my_fines(cid, uid)
            return
        if data == "report":
            show_gathering_reports(cid)
            return
        
        if not is_admin(uid):
            send(cid, "⛔ Только админ!")
            return
        
        # Админские кнопки
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
            send(cid, "📅 <b>ОТМЕТИТЬ НЕАКТИВНЫХ</b>\n\nВведи имя игрока:")
            return
        
        if data == "new_fine":
            state[uid] = {"step": "fine_name"}
            send(cid, "💰 <b>НАЗНАЧИТЬ ШТРАФ</b>\n\nВведи имя игрока:")
            return
        
        if data == "mass_fine":
            state[uid] = {"step": "mass_fine_names"}
            send(cid, "📋 <b>МАССОВЫЙ ШТРАФ</b>\n\nВведи список имён через запятую:")
            return
        
        if data == "mass_pay":
            state[uid] = {"step": "mass_pay_names"}
            send(cid, "✅ <b>МАССОВАЯ ОПЛАТА</b>\n\nВведи список имён через запятую:")
            return
        
        # Обработка выбора пункта
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
                            reason = f"Пункт 2: Пропуск сбора (пропусков: {missed + 1})"
                        else:
                            amount = punkt_info["base"]
                            reason = f"Пункт {punkt_num}: {punkt_info['name']}"
                        add_fine(user_id, username_db, first_name, amount, reason)
                        count += 1
                send(cid, f"✅ Назначено штрафов: {count}")
                del state[uid]
                return
            
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
                            pay_fine(fine_id)
                            count += 1
                send(cid, f"✅ Оплачено штрафов: {count}")
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
                        reason = f"Пункт 2: Пропуск сбора (пропусков: {missed + 1})"
                    else:
                        amount = punkt_info["base"]
                        reason = f"Пункт {punkt_num}: {punkt_info['name']}"
                    add_fine(user_id, username_db, first_name, amount, reason)
                    send(cid, f"✅ Штраф назначен!\n\n👤 {mention(user_id, username_db, first_name)}\n💰 {amount} г\n📝 {reason}")
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
    fines = get_user_fines(uid)
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
        reason = f"Пункт 2: Пропуск сбора (пропусков: {missed_count + 1})"
        add_fine(user_id, username_db, first_name, amount, reason)
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
