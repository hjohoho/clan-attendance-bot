import requests
import json
import sqlite3
import time
from datetime import datetime, timedelta

BOT_TOKEN = "8975094107:AAHAyExCPty9LsFavS1u2b31Od4sGYbrNkg"
CREATOR_ID = 1462367346
THREAD_ID = 17405

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
conn.commit()

def is_admin(user_id):
    if user_id == CREATOR_ID:
        return True
    cursor.execute("SELECT user_id FROM admins WHERE user_id = ?", (user_id,))
    return cursor.fetchone() is not None

def send(chat_id, text, kb=None):
    if not chat_id or chat_id == 0:
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "message_thread_id": THREAD_ID}
    if kb:
        data["reply_markup"] = json.dumps(kb)
    try:
        requests.post(url, json=data, timeout=10)
    except:
        pass

def send_dm(user_id, text):
    if not user_id or user_id == 0:
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": user_id, "text": text, "parse_mode": "HTML"}
    try:
        requests.post(url, json=data, timeout=10)
    except:
        pass

def mention(user_id, username, name):
    if username:
        return f'<a href="tg://user?id={user_id}">@{username}</a>'
    return name

def get_members():
    cursor.execute("SELECT user_id, username, first_name, warnings, missed_gatherings FROM users")
    return cursor.fetchall()

def get_user_id_by_username(username):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getChat"
    data = {"chat_id": f"@{username}"}
    try:
        r = requests.post(url, json=data, timeout=10)
        result = r.json()
        if result.get("ok"):
            return result["result"]["id"]
        return None
    except:
        return None

def add_fine(user_id, username, first_name, amount, reason):
    try:
        if not user_id or user_id == 0:
            if username:
                uid = get_user_id_by_username(username)
                if uid:
                    user_id = uid
                    cursor.execute("UPDATE users SET user_id = ? WHERE username = ?", (user_id, username))
                    conn.commit()
        
        cursor.execute("INSERT INTO fines (user_id, username, first_name, amount, reason, date, paid, overdue) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", 
                       (user_id, username, first_name, amount, reason, datetime.now().strftime("%d.%m.%Y %H:%M"), 0, 0))
        conn.commit()
        fine_id = cursor.lastrowid
        
        # ОТПРАВКА В ЛС ИГРОКУ
        msg = f"⚠️ <b>ВЫ ПОЛУЧИЛИ ШТРАФ!</b>\n\n💰 Сумма: {amount} г\n📝 {reason}\n📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        if user_id and user_id != 0:
            send_dm(user_id, msg)
        elif username:
            uid = get_user_id_by_username(username)
            if uid:
                send_dm(uid, msg)
                cursor.execute("UPDATE users SET user_id = ? WHERE username = ?", (uid, username))
                conn.commit()
        
        # ОТПРАВКА АДМИНАМ В ЛС
        cursor.execute("SELECT user_id FROM admins")
        for admin in cursor.fetchall():
            if admin[0] != user_id:
                send_dm(admin[0], f"📢 <b>ВЫПИСАН ШТРАФ</b>\n👤 {mention(user_id, username, first_name)}\n💰 {amount} г")
        
        return fine_id
    except Exception as e:
        print("Ошибка add_fine:", e)
        return None

def add_admin_by_username(username):
    user_id = get_user_id_by_username(username)
    if not user_id:
        return False, "❌ Не найден @{username}"
    cursor.execute("INSERT OR IGNORE INTO admins (user_id, username) VALUES (?, ?)", (user_id, username))
    conn.commit()
    send_dm(user_id, f"👑 <b>ТЫ СТАЛ АДМИНОМ!</b>")
    return True, f"✅ @{username} теперь админ!"

def remove_admin_by_username(username):
    cursor.execute("SELECT user_id FROM admins WHERE username = ?", (username,))
    r = cursor.fetchone()
    if not r:
        return False, f"❌ Админ @{username} не найден"
    user_id = r[0]
    if user_id == CREATOR_ID:
        return False, "⛔ Нельзя удалить создателя!"
    cursor.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
    conn.commit()
    send_dm(user_id, f"❌ <b>ТЫ БОЛЬШЕ НЕ АДМИН!</b>")
    return True, f"❌ @{username} больше не админ"

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
                    send_dm(user_id, f"⏰ <b>ПРОСРОЧКА</b>\n💰 Штраф #{fine_id} просрочен!\n➕ {extra_amount} г")

state = {}

def main_menu_kb():
    return {"inline_keyboard": [
        [{"text": "🏠 В главное меню", "callback_data": "back_admin"}]
    ]}

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
        [{"text": "👥 Список клана", "callback_data": "list"}]
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
        send(cid, f"✅ У <b>{first_name}</b> нет штрафов", main_menu_kb())
        return
    text = f"💰 <b>ШТРАФЫ {first_name}</b>\n\n"
    for fine_id, amount, reason, date, overdue in fines:
        overdue_text = f" + {overdue*10}г" if overdue > 0 else ""
        text += f"• #{fine_id} — {amount} г{overdue_text}\n  📝 {reason}\n  📅 {date}\n\n"
    kb = {"inline_keyboard": []}
    for fine_id, amount, reason, date, overdue in fines:
        kb["inline_keyboard"].append([{"text": f"✅ Оплатить #{fine_id} ({amount} г)", "callback_data": f"pay_fine_id_{fine_id}"}])
    kb["inline_keyboard"].append([{"text": "🔙 Назад", "callback_data": "back_admin"}])
    send(cid, text, kb)

def add_players_from_text(cid, text, admin_id):
    if not is_admin(admin_id):
        send(cid, "⛔ Только админ!", main_menu_kb())
        return
    names = [x.strip() for x in text.replace('\n', ',').split(',') if x.strip()]
    if not names:
        send(cid, "❌ Ни одного имени", main_menu_kb())
        return
    added = []
    for name in names:
        username = None
        first_name = name
        if "@" in name:
            parts = name.split()
            for p in parts:
                if p.startswith("@"):
                    username = p.replace("@", "")
                    first_name = name.replace(p, "").strip()
            if not first_name:
                first_name = username
        cursor.execute("INSERT OR IGNORE INTO users (username, first_name, last_seen) VALUES (?, ?, ?)", 
                       (username, first_name, datetime.now().strftime("%d.%m.%Y")))
        if cursor.rowcount > 0:
            added.append(first_name)
    send(cid, f"✅ Добавлено: {', '.join(added)}" if added else "❌ Никого не добавлено", main_menu_kb())

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
                send(cid, "👑 <b>АДМИН-ПАНЕЛЬ</b>", admin_menu())
            else:
                send(cid, "📋 <b>ПАНЕЛЬ ИГРОКА</b>", player_menu())
            return
        
        # ===== ДОБАВЛЕНИЕ АДМИНА ЧЕРЕЗ КОМАНДУ =====
        if t.startswith("/addadmin"):
            if not is_admin(uid):
                send(cid, "⛔ Только админ!", main_menu_kb())
                return
            parts = t.split()
            if len(parts) < 2:
                send(cid, "❌ /addadmin @username", main_menu_kb())
                return
            username = parts[1].replace("@", "")
            success, msg = add_admin_by_username(username)
            send(cid, msg, main_menu_kb())
            return
        
        # ===== УДАЛЕНИЕ АДМИНА ЧЕРЕЗ КОМАНДУ =====
        if t.startswith("/removeadmin"):
            if not is_admin(uid):
                send(cid, "⛔ Только админ!", main_menu_kb())
                return
            parts = t.split()
            if len(parts) < 2:
                send(cid, "❌ /removeadmin @username", main_menu_kb())
                return
            username = parts[1].replace("@", "")
            success, msg = remove_admin_by_username(username)
            send(cid, msg, main_menu_kb())
            return
        
        # ===== ВЫПИСАТЬ ШТРАФ ЧЕРЕЗ КОМАНДУ =====
        if t.startswith("/fine"):
            if not is_admin(uid):
                send(cid, "⛔ Только админ!", main_menu_kb())
                return
            parts = t.split()
            if len(parts) < 3:
                send(cid, "❌ /fine @username 10 причина", main_menu_kb())
                return
            username = parts[1].replace("@", "")
            try:
                amount = int(parts[2])
            except:
                send(cid, "❌ Сумма должна быть числом", main_menu_kb())
                return
            reason = " ".join(parts[3:]) if len(parts) > 3 else "Нарушение"
            
            cursor.execute("SELECT user_id, first_name FROM users WHERE username = ?", (username,))
            r = cursor.fetchone()
            if not r:
                send(cid, f"❌ Игрок @{username} не найден", main_menu_kb())
                return
            user_id, first_name = r
            add_fine(user_id, username, first_name, amount, reason)
            send(cid, f"✅ Штраф {amount}г для @{username} выписан!", main_menu_kb())
            return
        
        # ===== МОИ ШТРАФЫ ЧЕРЕЗ КОМАНДУ =====
        if t == "/myfines":
            fines = get_fines_by_user(uid)
            if not fines:
                send(cid, "💰 У вас нет штрафов", player_menu())
                return
            text = "💰 <b>ВАШИ ШТРАФЫ</b>\n\n"
            total = 0
            for fine_id, amount, reason, date, paid, overdue in fines:
                status = "✅" if paid else "❌"
                overdue_text = f" +{overdue*10}г" if overdue > 0 else ""
                text += f"• #{fine_id} — {amount} г{overdue_text} ({status})\n  📝 {reason}\n  📅 {date}\n"
                total += amount if not paid else 0
            text += f"\n<b>К оплате: {total} г</b>"
            send(cid, text, player_menu())
            return
        
        # ===== ВСЕ ШТРАФЫ ЧЕРЕЗ КОМАНДУ =====
        if t == "/fines":
            if not is_admin(uid):
                send(cid, "⛔ Только админ!", main_menu_kb())
                return
            cursor.execute("SELECT id, user_id, username, first_name, amount, reason, date, paid, overdue FROM fines ORDER BY date DESC LIMIT 30")
            fines = cursor.fetchall()
            if not fines:
                send(cid, "💰 Нет штрафов", main_menu_kb())
                return
            text = "💰 <b>ВСЕ ШТРАФЫ</b>\n\n"
            for fine_id, user_id, username, first_name, amount, reason, date, paid, overdue in fines:
                name = f"@{username} ({first_name})" if username else first_name
                status = "✅" if paid else "❌"
                overdue_text = f" +{overdue*10}г" if overdue > 0 else ""
                text += f"• #{fine_id} {name} — {amount} г{overdue_text} {status}\n  📝 {reason}\n  📅 {date}\n"
            send(cid, text, main_menu_kb())
            return
        
        # ===== СПИСОК КЛАНА =====
        if t == "/list":
            members = get_members()
            if not members:
                send(cid, "👥 Список клана пуст", main_menu_kb())
                return
            text = "👥 <b>СПИСОК КЛАНА</b>\n\n"
            for user_id, username, first_name, warnings, missed in members:
                name = f"@{username} ({first_name})" if username else first_name
                text += f"• {name}"
                if warnings > 0:
                    text += f" ⚠️{warnings}"
                if missed > 0:
                    text += f" 📝{missed}"
                text += "\n"
            send(cid, text, main_menu_kb())
            return
        
        # ===== ДОБАВИТЬ ИГРОКА =====
        if uid in state and state[uid].get("step") == "add_player":
            if not is_admin(uid):
                send(cid, "⛔ Только админ!", main_menu_kb())
                del state[uid]
                return
            add_players_from_text(cid, t, uid)
            del state[uid]
            return
        
        # ===== УДАЛИТЬ ИГРОКА =====
        if uid in state and state[uid].get("step") == "remove_player":
            if not is_admin(uid):
                send(cid, "⛔ Только админ!", main_menu_kb())
                del state[uid]
                return
            name = t
            cursor.execute("SELECT user_id FROM users WHERE first_name = ? OR username = ?", (name, name.replace("@", "")))
            r = cursor.fetchone()
            if r:
                if r[0] == CREATOR_ID:
                    send(cid, "⛔ Нельзя удалить создателя!", main_menu_kb())
                else:
                    remove_player_from_db(r[0])
                    send(cid, f"❌ Игрок {name} удалён", main_menu_kb())
            else:
                send(cid, f"❌ Игрок {name} не найден", main_menu_kb())
            del state[uid]
            return
        
        # ===== НАЧАТЬ СБОР =====
        if uid in state and state[uid].get("step") == "present":
            if not is_admin(uid):
                send(cid, "⛔ Только админ!", main_menu_kb())
                del state[uid]
                return
            names = [x.strip() for x in t.replace('\n', ',').split(',') if x.strip()]
            if not names:
                send(cid, "❌ Список пуст", main_menu_kb())
                del state[uid]
                return
            state[uid]["present"] = names
            state[uid]["step"] = "done"
            report_gathering(cid, uid)
            return
        
        # ===== НЕАКТИВНЫЕ =====
        if uid in state and state[uid].get("step") == "inactive_name":
            if not is_admin(uid):
                send(cid, "⛔ Только админ!", main_menu_kb())
                del state[uid]
                return
            state[uid]["name"] = t
            state[uid]["step"] = "inactive_date"
            send(cid, f"👤 {t}\n📅 Введи дату (ДД.ММ.ГГГГ):")
            return
        
        if uid in state and state[uid].get("step") == "inactive_date":
            if not is_admin(uid):
                send(cid, "⛔ Только админ!", main_menu_kb())
                del state[uid]
                return
            try:
                last_date = datetime.strptime(t, "%d.%m.%Y")
                name = state[uid]["name"]
                days = (datetime.now() - last_date).days
                cursor.execute("SELECT user_id, username, first_name FROM users WHERE first_name = ? OR username = ?", (name, name.replace("@", "")))
                r = cursor.fetchone()
                if not r:
                    send(cid, f"❌ Игрок {name} не найден", main_menu_kb())
                    del state[uid]
                    return
                user_id, username, first_name = r
                if days >= 4:
                    add_fine(user_id, username, first_name, 15, f"Неактивность {days} дней")
                    send(cid, f"⚠️ ШТРАФ {first_name} - 15г ({days} дней)", main_menu_kb())
                else:
                    send(cid, f"✅ {first_name} - {days} дней, штрафа нет", main_menu_kb())
                cursor.execute("UPDATE users SET last_seen = ? WHERE user_id = ?", (t, user_id))
                conn.commit()
            except:
                send(cid, "❌ Неверный формат! ДД.ММ.ГГГГ", main_menu_kb())
            del state[uid]
            return
        
        # ===== НАЗНАЧИТЬ ШТРАФ =====
        if uid in state and state[uid].get("step") == "fine_name":
            if not is_admin(uid):
                send(cid, "⛔ Только админ!", main_menu_kb())
                del state[uid]
                return
            state[uid]["fine_name"] = t
            send(cid, f"👤 {t}\n⚔️ Выбери категорию:", fine_category_menu())
            return
        
        # ===== ОПЛАТИТЬ ШТРАФ =====
        if uid in state and state[uid].get("step") == "pay_name":
            if not is_admin(uid):
                send(cid, "⛔ Только админ!", main_menu_kb())
                del state[uid]
                return
            name = t
            cursor.execute("SELECT user_id, first_name FROM users WHERE first_name = ? OR username = ?", (name, name.replace("@", "")))
            r = cursor.fetchone()
            if r:
                show_player_fines_for_pay(cid, r[0], r[1])
            else:
                send(cid, f"❌ Игрок {name} не найден", main_menu_kb())
            del state[uid]
            return
        
        # ===== ВВОД СУММЫ ШТРАФА =====
        if uid in state and state[uid].get("step") == "fine_amount":
            if not is_admin(uid):
                send(cid, "⛔ Только админ!", main_menu_kb())
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
                        send(cid, f"❌ Сумма от {min_amt} до {max_amt}г!", main_menu_kb())
                        return
                name = state[uid]["fine_name"]
                cursor.execute("SELECT user_id, username, first_name FROM users WHERE first_name = ? OR username = ?", (name, name.replace("@", "")))
                r = cursor.fetchone()
                if not r:
                    send(cid, f"❌ Игрок {name} не найден", main_menu_kb())
                    del state[uid]
                    return
                user_id, username, first_name = r
                reason = f"Пункт {punkt_num}: {punkt_info['name']} ({amount}г)"
                add_fine(user_id, username, first_name, amount, reason)
                send(cid, f"✅ Штраф {amount}г для {first_name}", main_menu_kb())
                del state[uid]
            except:
                send(cid, "❌ Введи число!", main_menu_kb())
            return
    
    if "callback_query" in update:
        c = update["callback_query"]
        cid = c["message"]["chat"]["id"]
        uid = c["from"]["id"]
        data = c["data"]
        
        if data == "my_fines":
            fines = get_fines_by_user(uid)
            if not fines:
                send(cid, "💰 У вас нет штрафов", player_menu())
                return
            text = "💰 <b>ВАШИ ШТРАФЫ</b>\n\n"
            total = 0
            for fine_id, amount, reason, date, paid, overdue in fines:
                status = "✅" if paid else "❌"
                overdue_text = f" +{overdue*10}г" if overdue > 0 else ""
                text += f"• #{fine_id} — {amount} г{overdue_text} ({status})\n  📝 {reason}\n  📅 {date}\n"
                total += amount if not paid else 0
            text += f"\n<b>К оплате: {total} г</b>"
            send(cid, text, player_menu())
            return
        
        if data == "report":
            cursor.execute("SELECT date, present, absent FROM attendance ORDER BY date DESC LIMIT 10")
            reports = cursor.fetchall()
            if not reports:
                send(cid, "📊 Нет записей", main_menu_kb())
                return
            text = "📊 <b>ИСТОРИЯ СБОРОВ</b>\n\n"
            for date, present, absent in reports:
                text += f"📅 {date}\n✅ {present if present else '—'}\n❌ {absent if absent else 'Все'}\n\n"
            send(cid, text, main_menu_kb())
            return
        
        if data == "back_admin":
            if is_admin(uid):
                send(cid, "👑 <b>АДМИН-ПАНЕЛЬ</b>", admin_menu())
            else:
                send(cid, "📋 <b>ПАНЕЛЬ ИГРОКА</b>", player_menu())
            return
        
        if data == "back_medium":
            send(cid, "🟡 <b>СРЕДНИЕ</b>", medium_fines_menu())
            return
        
        if not is_admin(uid):
            send(cid, "⛔ Только админ!", main_menu_kb())
            return
        
        if data == "add_player":
            state[uid] = {"step": "add_player"}
            send(cid, "➕ Введи имена через запятую")
            return
        
        if data == "remove_player":
            state[uid] = {"step": "remove_player"}
            send(cid, "❌ Введи имя или @username")
            return
        
        if data == "start":
            state[uid] = {"step": "present", "present": []}
            send(cid, "📝 Введи присутствующих через запятую")
            return
        
        if data == "inactive":
            state[uid] = {"step": "inactive_name"}
            send(cid, "📅 Введи имя")
            return
        
        if data == "new_fine":
            state[uid] = {"step": "fine_name"}
            send(cid, "💰 Введи имя")
            return
        
        if data == "pay_fine":
            state[uid] = {"step": "pay_name"}
            send(cid, "✅ Введи имя игрока")
            return
        
        if data == "fines":
            cursor.execute("SELECT id, user_id, username, first_name, amount, reason, date, paid, overdue FROM fines ORDER BY date DESC LIMIT 30")
            fines = cursor.fetchall()
            if not fines:
                send(cid, "💰 Нет штрафов", main_menu_kb())
                return
            text = "💰 <b>ВСЕ ШТРАФЫ</b>\n\n"
            for fine_id, user_id, username, first_name, amount, reason, date, paid, overdue in fines:
                name = f"@{username} ({first_name})" if username else first_name
                status = "✅" if paid else "❌"
                overdue_text = f" +{overdue*10}г" if overdue > 0 else ""
                text += f"• #{fine_id} {name} — {amount} г{overdue_text} {status}\n  📝 {reason}\n  📅 {date}\n"
            send(cid, text, main_menu_kb())
            return
        
        if data == "list":
            members = get_members()
            if not members:
                send(cid, "👥 Список клана пуст", main_menu_kb())
                return
            text = "👥 <b>СПИСОК КЛАНА</b>\n\n"
            for user_id, username, first_name, warnings, missed in members:
                name = f"@{username} ({first_name})" if username else first_name
                text += f"• {name}"
                if warnings > 0:
                    text += f" ⚠️{warnings}"
                if missed > 0:
                    text += f" 📝{missed}"
                text += "\n"
            send(cid, text, main_menu_kb())
            return
        
        if data == "cat_light":
            send(cid, "🟢 <b>ЛЁГКИЕ</b>", light_fines_menu())
            return
        
        if data == "cat_medium":
            send(cid, "🟡 <b>СРЕДНИЕ</b>", medium_fines_menu())
            return
        
        if data == "cat_heavy":
            send(cid, "🔴 <b>ТЯЖКИЕ</b>", heavy_fines_menu())
            return
        
        if data == "cat_critical":
            send(cid, "⛔ <b>КРИТИЧЕСКИЕ</b>", critical_fines_menu())
            return
        
        if data == "back_categories":
            send(cid, "⚔️ <b>ВЫБЕРИ КАТЕГОРИЮ</b>", fine_category_menu())
            return
        
        if data.startswith("fine_9_"):
            sub_num = int(data.split("_")[2])
            punkt_info = get_punkt_info(9, sub_num)
            min_amt, max_amt = punkt_info["range"]
            state[uid]["punkt_num"] = 9
            state[uid]["sub_num"] = sub_num
            state[uid]["step"] = "fine_amount"
            send(cid, f"{punkt_info['emoji']} <b>{punkt_info['name']}</b>\n💰 Введи сумму ({min_amt}-{max_amt}г):")
            return
        
        if data.startswith("fine_10_"):
            sub_num = int(data.split("_")[2])
            punkt_info = get_punkt_info(10, sub_num)
            min_amt, max_amt = punkt_info["range"]
            state[uid]["punkt_num"] = 10
            state[uid]["sub_num"] = sub_num
            state[uid]["step"] = "fine_amount"
            send(cid, f"{punkt_info['emoji']} <b>{punkt_info['name']}</b>\n💰 Введи сумму ({min_amt}-{max_amt}г):")
            return
        
        if data.startswith("fine_"):
            punkt_num = int(data.split("_")[1])
            punkt_info = get_punkt_info(punkt_num)
            
            if punkt_num in [9, 10]:
                if punkt_num == 9:
                    send(cid, "🟡 <b>ОСКОРБЛЕНИЯ</b>", fine_9_submenu())
                else:
                    send(cid, "🔟 <b>НАРУШЕНИЕ В СТРОЮ</b>", fine_10_submenu())
                return
            
            if "fine_name" not in state.get(uid, {}):
                send(cid, "❌ Сначала выбери игрока", main_menu_kb())
                return
            
            name = state[uid]["fine_name"]
            cursor.execute("SELECT user_id, username, first_name, missed_gatherings FROM users WHERE first_name = ? OR username = ?", (name, name.replace("@", "")))
            r = cursor.fetchone()
            if not r:
                send(cid, f"❌ Игрок {name} не найден", main_menu_kb())
                del state[uid]
                return
            
            user_id, username, first_name, missed = r
            
            if punkt_num in [15, 16]:
                reason = f"Пункт {punkt_num}: {punkt_info['name']} - ЧС+КИК!"
                add_warning(user_id, reason, "cs")
                send_dm(user_id, f"⛔ ВЫ ИСКЛЮЧЕНЫ!\n{reason}")
                send(cid, f"⛔ {first_name} ИСКЛЮЧЕН!", main_menu_kb())
                remove_player_from_db(user_id)
                del state[uid]
                return
            
            if punkt_num == 2:
                amount = 5 + (missed * 10)
                reason = f"Пункт 2: Пропуск сбора ({missed+1} раз)"
            elif punkt_num == 3:
                cursor.execute("SELECT COUNT(*) FROM fines WHERE user_id = ? AND reason LIKE '%Пункт 3%'", (user_id,))
                spam_count = cursor.fetchone()[0]
                amount = 5 + (spam_count * 5)
                reason = f"Пункт 3: Спам ({spam_count+1} раз)"
            else:
                amount = punkt_info["base"]
                reason = f"Пункт {punkt_num}: {punkt_info['name']}"
            
            add_fine(user_id, username, first_name, amount, reason)
            if punkt_num == 1:
                add_warning(user_id, f"Пункт 1: {punkt_info['name']}", "warning")
            
            send(cid, f"✅ Штраф {amount}г для {first_name}", main_menu_kb())
            del state[uid]
            return
        
        if data.startswith("pay_fine_id_"):
            fine_id = int(data.split("_")[3])
            cursor.execute("SELECT user_id, amount FROM fines WHERE id = ? AND paid = 0", (fine_id,))
            r = cursor.fetchone()
            if not r:
                send(cid, "❌ Штраф оплачен", main_menu_kb())
                return
            user_id, amount = r
            if user_id != uid and not is_admin(uid):
                send(cid, "⛔ Не ваш штраф", main_menu_kb())
                return
            if pay_fine(fine_id):
                send(cid, f"✅ Штраф #{fine_id} ({amount}г) оплачен", main_menu_kb())
                if is_admin(uid):
                    send(cid, "👑 <b>АДМИН-ПАНЕЛЬ</b>", admin_menu())
            return

def report_gathering(cid, uid):
    present = state[uid].get("present", [])
    if not present:
        send(cid, "❌ Список пуст", main_menu_kb())
        if uid in state:
            del state[uid]
        return
    
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
    for user_id, username, first_name in absent_data:
        missed_count = get_missed_gatherings(user_id)
        amount = 5 + (missed_count * 10)
        reason = f"Пропуск сбора ({missed_count+1} раз)"
        add_fine(user_id, username, first_name, amount, reason)
        add_warning(user_id, reason, "reprimand")
        fines += f"{mention(user_id, username, first_name)} — {amount} г\n"
    
    cursor.execute("INSERT INTO attendance (date, present, absent, fines) VALUES (?, ?, ?, ?)", 
                   (datetime.now().strftime("%d.%m.%Y %H:%M"), 
                    ", ".join(present) if present else "—", 
                    ", ".join(absent) if absent else "—", 
                    fines if fines else "—"))
    conn.commit()
    
    send(cid, f"📊 <b>ОТЧЁТ ПО СБОРУ</b>\n📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n✅ Были ({len(present)}):\n{', '.join(present) if present else '—'}\n\n❌ Не были ({len(absent)}):\n{', '.join(absent) if absent else 'Все на месте! 🎉'}\n\n💰 ШТРАФЫ:\n{fines if fines else '—'}", main_menu_kb())
    
    if uid in state:
        del state[uid]

def main():
    print("🤖 БОТ ЗАПУЩЕН!")
    print(f"📌 Топик: {THREAD_ID}")
    offset = 0
    while True:
        try:
            check_overdue_fines()
            r = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates", params={"offset": offset, "timeout": 30})
            for u in r.json().get("result", []):
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
