import requests
import json
import sqlite3
import time
from datetime import datetime, timedelta

BOT_TOKEN = "8975094107:AAHAyExCPty9LsFavS1u2b31Od4sGYbrNkg"
ADMIN_IDS = [1462367346, 8785617232]
CREATOR_ID = 1462367346

conn = sqlite3.connect("attendance.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, last_seen TEXT, warnings INTEGER DEFAULT 0, missed_gatherings INTEGER DEFAULT 0)")
cursor.execute("CREATE TABLE IF NOT EXISTS attendance (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, present TEXT, absent TEXT, fines TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS fines (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, username TEXT, first_name TEXT, amount INTEGER, reason TEXT, date TEXT, paid INTEGER DEFAULT 0, overdue INTEGER DEFAULT 0)")
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
        cursor.execute("INSERT INTO fines (user_id, username, first_name, amount, reason, date, paid, overdue) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", 
                       (user_id, username, first_name, amount, reason, datetime.now().strftime("%d.%m.%Y %H:%M"), 0, 0))
        conn.commit()
        fine_id = cursor.lastrowid
        send(user_id, f"⚠️ <b>ВЫ ПОЛУЧИЛИ ШТРАФ!</b>\n\n💰 Сумма: {amount} г\n📝 {reason}\n📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n⏰ Штраф нужно оплатить в течение 2 дней!")
        return fine_id
    except:
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
    cursor.execute("SELECT id, amount, reason, date, paid, overdue FROM fines WHERE user_id = ? ORDER BY date DESC", (user_id,))
    return cursor.fetchall()

def get_unpaid_fines_by_user(user_id):
    cursor.execute("SELECT id, amount, reason, date, overdue FROM fines WHERE user_id = ? AND paid = 0 ORDER BY date DESC", (user_id,))
    return cursor.fetchall()

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

def check_overdue_fines():
    cursor.execute("SELECT id, user_id, amount, date FROM fines WHERE paid = 0")
    fines = cursor.fetchall()
    now = datetime.now()
    for fine_id, user_id, amount, date_str in fines:
        fine_date = datetime.strptime(date_str, "%d.%m.%Y %H:%M")
        days_passed = (now - fine_date).days
        if days_passed >= 2:
            overdue_count = (days_passed - 1) // 2
            cursor.execute("SELECT overdue FROM fines WHERE id = ?", (fine_id,))
            current_overdue = cursor.fetchone()[0]
            if overdue_count > current_overdue:
                new_overdue = overdue_count
                extra_amount = new_overdue * 10
                cursor.execute("UPDATE fines SET amount = amount + ?, overdue = ? WHERE id = ?", (extra_amount, new_overdue, fine_id))
                conn.commit()
                cursor.execute("SELECT user_id, username, first_name FROM users WHERE user_id = ?", (user_id,))
                user = cursor.fetchone()
                if user:
                    send(user_id, f"⏰ <b>ПРОСРОЧКА ШТРАФА!</b>\n\n💰 Штраф #{fine_id} просрочен!\n➕ Начислено {extra_amount} г за просрочку\n📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}")

state = {}

def admin_menu():
    return {"inline_keyboard": [
        [{"text": "➕ Добавить игрока", "callback_data": "add_player"}],
        [{"text": "❌ Удалить игрока", "callback_data": "remove_player"}],
        [{"text": "📝 Начать сбор", "callback_data": "start"}],
        [{"text": "📅 Отметить неактивных", "callback_data": "inactive"}],
        [{"text": "💰 Назначить штраф", "callback_data": "new_fine"}],
        [{"text": "✅ Оплатить штраф", "callback_data": "pay_fine"}],
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

def fine_category_menu():
    return {"inline_keyboard": [
        [{"text": "🟢 ЛЁГКИЕ (5-10 г)", "callback_data": "cat_light"}],
        [{"text": "🟡 СРЕДНИЕ (15-25 г)", "callback_data": "cat_medium"}],
        [{"text": "🔴 ТЯЖКИЕ (50 г)", "callback_data": "cat_heavy"}],
        [{"text": "⛔ КРИТИЧЕСКИЕ", "callback_data": "cat_critical"}],
        [{"text": "🔙 Назад", "callback_data": "back_admin"}]
    ]}

def light_fines_menu():
    return {"inline_keyboard": [
        [{"text": "1️⃣ Убийство союзника (5 г)", "callback_data": "fine_1"}],
        [{"text": "2️⃣ Пропуск сбора (5 г +10)", "callback_data": "fine_2"}],
        [{"text": "3️⃣ Спам в чате (5 г +5)", "callback_data": "fine_3"}],
        [{"text": "4️⃣ Самовольный захват базы (10 г)", "callback_data": "fine_4"}],
        [{"text": "5️⃣ Неявка на защиту базы (10 г)", "callback_data": "fine_5"}],
        [{"text": "6️⃣ Неявка на босса (10 г)", "callback_data": "fine_6"}],
        [{"text": "🔙 Назад", "callback_data": "back_categories"}]
    ]}

def medium_fines_menu():
    return {"inline_keyboard": [
        [{"text": "7️⃣ Неактивность 4+ дней (15 г)", "callback_data": "fine_7"}],
        [{"text": "8️⃣ Выход во время строя (15 г)", "callback_data": "fine_8"}],
        [{"text": "9️⃣ Оскорбления (5-50 г)", "callback_data": "fine_9"}],
        [{"text": "🔟 Нарушение в строю (3-30 г)", "callback_data": "fine_10"}],
        [{"text": "🔙 Назад", "callback_data": "back_categories"}]
    ]}

def heavy_fines_menu():
    return {"inline_keyboard": [
        [{"text": "1️⃣1️⃣ Оскорбление руководства (50 г)", "callback_data": "fine_11"}],
        [{"text": "1️⃣2️⃣ Продажа экипировки (50 г)", "callback_data": "fine_12"}],
        [{"text": "1️⃣3️⃣ Провокация войны (50 г)", "callback_data": "fine_13"}],
        [{"text": "1️⃣4️⃣ Убийство союзника умышл. (50 г)", "callback_data": "fine_14"}],
        [{"text": "🔙 Назад", "callback_data": "back_categories"}]
    ]}

def critical_fines_menu():
    return {"inline_keyboard": [
        [{"text": "1️⃣5️⃣ Шпионство/слив (ЧС+КИК)", "callback_data": "fine_15"}],
        [{"text": "1️⃣6️⃣ Скам игрока (ЧС+КИК)", "callback_data": "fine_16"}],
        [{"text": "🔙 Назад", "callback_data": "back_categories"}]
    ]}

def fine_9_submenu():
    return {"inline_keyboard": [
        [{"text": "🟡 Лёгкие (5-10 г)", "callback_data": "fine_9_1"}],
        [{"text": "🟠 Средние (15-20 г)", "callback_data": "fine_9_2"}],
        [{"text": "🔴 Тяжёлые (25-50 г)", "callback_data": "fine_9_3"}],
        [{"text": "🔙 Назад", "callback_data": "back_medium"}]
    ]}

def fine_10_submenu():
    return {"inline_keyboard": [
        [{"text": "🟢 Незначительное (3-5 г)", "callback_data": "fine_10_1"}],
        [{"text": "🟡 Среднее (10-15 г)", "callback_data": "fine_10_2"}],
        [{"text": "🔴 Грубое (20-30 г)", "callback_data": "fine_10_3"}],
        [{"text": "🔙 Назад", "callback_data": "back_medium"}]
    ]}

def get_punkt_info(punkt_num, sub_num=0):
    punkte = {
        1: {"name": "Убийство союзника", "base": 5, "emoji": "1️⃣", "range": None},
        2: {"name": "Пропуск сбора", "base": 5, "emoji": "2️⃣", "range": None},
        3: {"name": "Спам в чате", "base": 5, "emoji": "3️⃣", "range": None},
        4: {"name": "Самовольный захват базы", "base": 10, "emoji": "4️⃣", "range": None},
        5: {"name": "Неявка на защиту базы", "base": 10, "emoji": "5️⃣", "range": None},
        6: {"name": "Неявка на босса", "base": 10, "emoji": "6️⃣", "range": None},
        7: {"name": "Неактивность 4+ дней", "base": 15, "emoji": "7️⃣", "range": None},
        8: {"name": "Выход во время строя", "base": 15, "emoji": "8️⃣", "range": None},
        9: {
            1: {"name": "Оскорбления (лёгкие)", "base": 7, "emoji": "🟡", "range": (5, 10)},
            2: {"name": "Оскорбления (средние)", "base": 17, "emoji": "🟠", "range": (15, 20)},
            3: {"name": "Оскорбления (тяжёлые)", "base": 35, "emoji": "🔴", "range": (25, 50)}
        },
        10: {
            1: {"name": "Нарушение в строю (незнач.)", "base": 4, "emoji": "🟢", "range": (3, 5)},
            2: {"name": "Нарушение в строю (среднее)", "base": 12, "emoji": "🟡", "range": (10, 15)},
            3: {"name": "Нарушение в строю (грубое)", "base": 25, "emoji": "🔴", "range": (20, 30)}
        },
        11: {"name": "Оскорбление руководства", "base": 50, "emoji": "1️⃣1️⃣", "range": None},
        12: {"name": "Продажа экипировки из казны", "base": 50, "emoji": "1️⃣2️⃣", "range": None},
        13: {"name": "Провокация войны", "base": 50, "emoji": "1️⃣3️⃣", "range": None},
        14: {"name": "Умышленное убийство союзника", "base": 50, "emoji": "1️⃣4️⃣", "range": None},
        15: {"name": "Шпионство/слив данных", "base": 0, "emoji": "1️⃣5️⃣", "range": None},
        16: {"name": "Скам игрока", "base": 0, "emoji": "1️⃣6️⃣", "range": None}
    }
    if punkt_num in [9, 10]:
        return punkte[punkt_num].get(sub_num, {"name": "Неизвестно", "base": 0, "emoji": "❓", "range": None})
    return punkte.get(punkt_num, {"name": "Неизвестно", "base": 0, "emoji": "❓", "range": None})

def show_player_fines_for_pay(cid, user_id, first_name):
    fines = get_unpaid_fines_by_user(user_id)
    if not fines:
        send(cid, f"✅ У <b>{first_name}</b> нет неоплаченных штрафов!")
        return
    
    text = f"💰 <b>ШТРАФЫ {first_name}</b>\n\n"
    for fine_id, amount, reason, date, overdue in fines:
        overdue_text = f" + {overdue*10}г просрочка" if overdue > 0 else ""
        text += f"• #{fine_id} — {amount} г{overdue_text}\n  📝 {reason}\n  📅 {date}\n\n"
    
    kb = {"inline_keyboard": []}
    for fine_id, amount, reason, date, overdue in fines:
        kb["inline_keyboard"].append([{"text": f"✅ Оплатить #{fine_id} ({amount} г)", "callback_data": f"pay_fine_id_{fine_id}"}])
    kb["inline_keyboard"].append([{"text": "🔙 Назад", "callback_data": "back_admin"}])
    
    send(cid, text, kb)

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
                send(cid, f"❌ @{username_db} не найден в базе игроков!")
            del state[uid]
            return
        
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
        
        if uid in state and state[uid].get("step") == "fine_name":
            if not is_admin(uid):
                send(cid, "⛔ Только админ!")
                del state[uid]
                return
            state[uid]["fine_name"] = t
            send(cid, f"👤 <b>{t}</b>\n\n⚔️ <b>ВЫБЕРИ КАТЕГОРИЮ ШТРАФА:</b>", fine_category_menu())
            return
        
        if uid in state and state[uid].get("step") == "pay_name":
            if not is_admin(uid):
                send(cid, "⛔ Только админ!")
                del state[uid]
                return
            name = t
            cursor.execute("SELECT user_id, first_name FROM users WHERE first_name = ? OR username = ?", (name, name.replace("@", "")))
            r = cursor.fetchone()
            if r:
                user_id, first_name = r
                show_player_fines_for_pay(cid, user_id, first_name)
            else:
                send(cid, f"❌ Игрок <b>{name}</b> не найден!")
            del state[uid]
            return
        
        if uid in state and state[uid].get("step") == "fine_amount":
            if not is_admin(uid):
                send(cid, "⛔ Только админ!")
                del state[uid]
                return
            try:
                amount = int(t)
                punkt_num = state[uid]["punkt_num"]
                sub_num = state[uid].get("sub_num", 0)
                punkt_info = get_punkt_info(punkt_num, sub_num)
                if punkt_info.get("range"):
                    min_amt, max_amt = punkt_info["range"]
                    if amount < min_amt or amount > max_amt:
                        send(cid, f"❌ Сумма должна быть от {min_amt} до {max_amt} г! Попробуй снова:")
                        return
                name = state[uid]["fine_name"]
                cursor.execute("SELECT user_id, username, first_name FROM users WHERE first_name = ? OR username = ?", (name, name.replace("@", "")))
                r = cursor.fetchone()
                if not r:
                    send(cid, f"❌ Игрок <b>{name}</b> не найден!")
                    del state[uid]
                    return
                user_id, username_db, first_name = r
                reason = f"Пункт {punkt_num}: {punkt_info['name']} ({amount} г)"
                add_fine(user_id, username_db, first_name, amount, reason)
                send(cid, f"✅ Штраф назначен!\n\n{punkt_info['emoji']} {mention(user_id, username_db, first_name)}\n💰 {amount} г\n📝 {reason}")
                del state[uid]
            except:
                send(cid, "❌ Введи число! Например: 15")
            return
    
    if "callback_query" in update:
        c = update["callback_query"]
        cid = c["message"]["chat"]["id"]
        uid = c["from"]["id"]
        data = c["data"]
        
        if data == "my_fines":
            fines = get_fines_by_user(uid)
            if not fines:
                send(cid, "💰 У вас нет штрафов.")
                return
            text = "💰 <b>ВАШИ ШТРАФЫ</b>\n\n"
            total = 0
            for fine_id, amount, reason, date, paid, overdue in fines:
                status = "✅ Оплачен" if paid else "❌ Не оплачен"
                overdue_text = f" + {overdue*10}г просрочка" if overdue > 0 else ""
                text += f"• #{fine_id} — {amount} г{overdue_text} ({status})\n  📝 {reason}\n  📅 {date}\n"
                total += amount if not paid else 0
            text += f"\n<b>Всего к оплате: {total} г</b>"
            send(cid, text)
            return
        
        if data == "report":
            show_gathering_reports(cid)
            return
        
        if data == "back_admin":
            if is_admin(uid):
                send(cid, "👑 <b>АДМИН-ПАНЕЛЬ</b>\n\nВыбери действие:", admin_menu())
            else:
                send(cid, "📋 <b>ПАНЕЛЬ ИГРОКА</b>\n\nТы можешь смотреть свои штрафы и отчёты:", player_menu())
            return
        
        if data == "back_medium":
            send(cid, "🟡 <b>СРЕДНИЕ ШТРАФЫ (15-25 г)</b>\n\nВыбери пункт:", medium_fines_menu())
            return
        
        if not is_admin(uid):
            send(cid, "⛔ Только админ!")
            return
        
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
            send(cid, "✅ <b>ОПЛАТИТЬ ШТРАФ</b>\n\nВведи имя игрока:")
            return
        
        if data == "fines":
            show_all_fines(cid)
            return
        
        if data == "list":
            show_clan_list(cid)
            return
        
        if data == "cat_light":
            send(cid, "🟢 <b>ЛЁГКИЕ ШТРАФЫ (5-10 г)</b>\n\nВыбери пункт:", light_fines_menu())
            return
        
        if data == "cat_medium":
            send(cid, "🟡 <b>СРЕДНИЕ ШТРАФЫ (15-25 г)</b>\n\nВыбери пункт:", medium_fines_menu())
            return
        
        if data == "cat_heavy":
            send(cid, "🔴 <b>ТЯЖКИЕ ШТРАФЫ (50 г)</b>\n\nВыбери пункт:", heavy_fines_menu())
            return
        
        if data == "cat_critical":
            send(cid, "⛔ <b>КРИТИЧЕСКИЕ ШТРАФЫ (ЧС+КИК)</b>\n\nВыбери пункт:", critical_fines_menu())
            return
        
        if data == "back_categories":
            send(cid, "⚔️ <b>ВЫБЕРИ КАТЕГОРИЮ ШТРАФА:</b>", fine_category_menu())
            return
        
        if data.startswith("fine_9_"):
            sub_num = int(data.split("_")[2])
            punkt_info = get_punkt_info(9, sub_num)
            min_amt, max_amt = punkt_info["range"]
            state[uid]["punkt_num"] = 9
            state[uid]["sub_num"] = sub_num
            state[uid]["step"] = "fine_amount"
            send(cid, f"{punkt_info['emoji']} <b>{punkt_info['name']}</b>\n\n💰 Введи сумму штрафа от <b>{min_amt}</b> до <b>{max_amt}</b> г:")
            return
        
        if data.startswith("fine_10_"):
            sub_num = int(data.split("_")[2])
            punkt_info = get_punkt_info(10, sub_num)
            min_amt, max_amt = punkt_info["range"]
            state[uid]["punkt_num"] = 10
            state[uid]["sub_num"] = sub_num
            state[uid]["step"] = "fine_amount"
            send(cid, f"{punkt_info['emoji']} <b>{punkt_info['name']}</b>\n\n💰 Введи сумму штрафа от <b>{min_amt}</b> до <b>{max_amt}</b> г:")
            return
        
        if data.startswith("fine_"):
            punkt_num = int(data.split("_")[1])
            punkt_info = get_punkt_info(punkt_num)
            
            if punkt_num in [9, 10]:
                if punkt_num == 9:
                    send(cid, "🟡 <b>ОСКОРБЛЕНИЯ</b>\n\nВыбери степень тяжести:", fine_9_submenu())
                else:
                    send(cid, "🔟 <b>НАРУШЕНИЕ В СТРОЮ</b>\n\nВыбери степень тяжести:", fine_10_submenu())
                return
            
            if "fine_name" not in state.get(uid, {}):
                send(cid, "❌ Ошибка! Сначала выбери игрока.")
                return
            
            name = state[uid]["fine_name"]
            cursor.execute("SELECT user_id, username, first_name, missed_gatherings FROM users WHERE first_name = ? OR username = ?", (name, name.replace("@", "")))
            r = cursor.fetchone()
            if not r:
                send(cid, f"❌ Игрок <b>{name}</b> не найден!")
                del state[uid]
                return
            
            user_id, username_db, first_name, missed = r
            
            if punkt_num in [15, 16]:
                reason = f"Пункт {punkt_num}: {punkt_info['name']} - ЧС + КИК!"
                add_warning(user_id, f"Пункт {punkt_num}: {punkt_info['name']}", "cs")
                send(user_id, f"⛔ <b>ВЫ ИСКЛЮЧЕНЫ ИЗ КЛАНА!</b>\n\n{reason}")
                send(cid, f"⛔ <b>{mention(user_id, username_db, first_name)} ИСКЛЮЧЕН!</b>\n\n{reason}")
                remove_player_from_db(user_id)
                del state[uid]
                return
            
            if punkt_num == 2:
                amount = 5 + (missed * 10)
                reason = f"Пункт 2: Пропуск сбора (пропусков подряд: {missed + 1})"
            elif punkt_num == 3:
                cursor.execute("SELECT COUNT(*) FROM fines WHERE user_id = ? AND reason LIKE '%Пункт 3%'", (user_id,))
                spam_count = cursor.fetchone()[0]
                amount = 5 + (spam_count * 5)
                reason = f"Пункт 3: Спам в чате (повторов: {spam_count + 1})"
            else:
                amount = punkt_info["base"]
                reason = f"Пункт {punkt_num}: {punkt_info['name']}"
            
            add_fine(user_id, username_db, first_name, amount, reason)
            
            if punkt_num == 1:
                add_warning(user_id, f"Пункт {punkt_num}: {punkt_info['name']}", "warning")
            
            send(cid, f"✅ Штраф назначен!\n\n{punkt_info['emoji']} {mention(user_id, username_db, first_name)}\n💰 {amount} г\n📝 {reason}")
            del state[uid]
            return
        
        if data.startswith("pay_fine_id_"):
            fine_id = int(data.split("_")[3])
            cursor.execute("SELECT user_id, amount FROM fines WHERE id = ? AND paid = 0", (fine_id,))
            r = cursor.fetchone()
            if not r:
                send(cid, "❌ Штраф уже оплачен или не найден!")
                return
            user_id, amount = r
            if user_id != uid and not is_admin(uid):
                send(cid, "⛔ Это не ваш штраф!")
                return
            if pay_fine(fine_id):
                send(cid, f"✅ Штраф #{fine_id} на сумму {amount} г успешно оплачен!")
                if is_admin(uid):
                    send(cid, "👑 <b>АДМИН-ПАНЕЛЬ</b>\n\nВыбери действие:", admin_menu())
            return
        
        if data == "list":
            show_clan_list(cid)
            return

def show_all_fines(cid):
    cursor.execute("SELECT id, user_id, username, first_name, amount, reason, date, paid, overdue FROM fines ORDER BY date DESC LIMIT 30")
    fines = cursor.fetchall()
    if not fines:
        send(cid, "💰 Нет штрафов.")
        return
    text = "💰 <b>ВСЕ ШТРАФЫ</b>\n\n"
    for fine_id, user_id, username_db, first_name, amount, reason, date, paid, overdue in fines:
        name = mention(user_id, username_db, first_name)
        status = "✅" if paid else "❌"
        overdue_text = f" +{overdue*10}г просрочка" if overdue > 0 else ""
        text += f"• #{fine_id} {name} — {amount} г{overdue_text} {status}\n  📝 {reason}\n  📅 {date}\n"
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
        add_warning(user_id, f"Пункт 2: Пропуск сбора", "reprimand")
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
            check_overdue_fines()
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
