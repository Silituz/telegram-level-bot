import os
import json
from datetime import datetime
from telebot import TeleBot
import random
from flask import Flask
from threading import Thread

# === KONFIGURATION ===
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
bot = TeleBot(TELEGRAM_TOKEN)

DATA_FILE = "user_data.json"
SHOP_PETS = {
    "🐍": {"name": "Schlange", "emoji": "🐍"},
    "🐺": {"name": "Wolf", "emoji": "🐺"},
    "🐱": {"name": "Katze", "emoji": "🐱"},
    "🐶": {"name": "Hund", "emoji": "🐶"},
}

# Mapping Tiername zu Emoji (für Rückwärtskompatibilität)
NAME_TO_EMOJI = {v["name"].lower(): k for k, v in SHOP_PETS.items()}

DAILY_MESSAGES = [
    "🌞 {name} startet in den Tag mit Stil! (+{xp} XP)",
    "🎉 {name} schleicht sich als erster rein – wie ein echter Profi! (+{xp} XP)",
    "🦸‍♂️ {name} ist der Held des Tages! (+{xp} XP)",
    "💡 {name} bringt als erster Licht ins Dunkel! (+{xp} XP)",
    "🥐 {name} ist vor dem Croissant beim Bäcker da! (+{xp} XP)"
]

# === KEEP-ALIVE SERVER ===
app = Flask('')

@app.route('/')
def home():
    print(f"[PING] Keep-alive Ping erhalten um {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    return "Bot läuft!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# === DATENLADEN UND SPEICHERN ===
def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

# === BEREINIGUNG VON ALTEN TIERDATEN ===
def fix_old_pet_data(user):
    changed = False
    for pet in user.get("tiere", []):
        art = pet.get("art")
        if art and art not in SHOP_PETS and art.lower() in NAME_TO_EMOJI:
            pet["art"] = NAME_TO_EMOJI[art.lower()]
            changed = True
    return changed

# === XP-UPDATE-FUNKTION ===
def update_xp(user_id, name):
    data = load_data()
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    user = data.get(str(user_id), {
        "xp": 0,
        "lvl": 1,
        "last_active": "",
        "tiere": [],
        "last_message_time": "",
        "daily_greeted_date": ""
    })

    if fix_old_pet_data(user):
        data[str(user_id)] = user
        save_data(data)

    is_new_day = user.get("daily_greeted_date", "") != today
    xp_bonus = 1 + len(user.get("tiere", []))
    daily_message = None

    if is_new_day:
        user["daily_greeted_date"] = today
        bonus = user["lvl"] * 2
        xp_bonus += bonus
        msg = random.choice(DAILY_MESSAGES).format(name=name, xp=xp_bonus)
        daily_message = msg

    user["xp"] += xp_bonus
    user["last_active"] = today
    user["last_message_time"] = now.strftime("%Y-%m-%d %H:%M:%S")

    level_ups = 0
    while True:
        xp_for_next = user["lvl"] * 10
        if user["xp"] >= xp_for_next:
            user["xp"] -= xp_for_next
            user["lvl"] += 1
            level_ups += 1
        else:
            break

    data[str(user_id)] = user
    save_data(data)

    response = []
    if daily_message:
        response.append(daily_message)
    if level_ups:
        response.append(f"✨ LEVEL UP! {name} ist jetzt Level {user['lvl']}!")

    return "\n".join(response) if response else None

# === STATUS ABFRAGEN ===
def check_stats(user_id, name=""):
    data = load_data()
    user = data.get(str(user_id), {"xp": 0, "lvl": 1, "tiere": []})
    tiere_liste = []
    for t in user.get("tiere", []):
        art = t.get("art")
        emoji = SHOP_PETS.get(art, {}).get("emoji") or NAME_TO_EMOJI.get(art.lower(), "❓")
        tiere_liste.append(f"{emoji} {t.get('name', '')}")
    inventar = f"\nTiere: {', '.join(tiere_liste) if tiere_liste else '-'}"
    return f"{name} ist Level {user['lvl']} mit {user['xp']} XP.{inventar}"

# === SHOP ANZEIGEN ===
def show_shop():
    items = [f"{v['emoji']} {v['name']} – 30 XP" for v in SHOP_PETS.values()]
    return "🛒 *Shop – Haustiere kaufen*\n" + "\n".join(items)

# === TIER KAUFEN ===
def buy_pet(user_id, name, emoji):
    data = load_data()
    user = data.get(str(user_id), {"xp": 0, "lvl": 1, "tiere": []})

    if emoji in NAME_TO_EMOJI:
        emoji = NAME_TO_EMOJI[emoji]

    if emoji not in SHOP_PETS:
        return "❌ Dieses Tier gibt es nicht."
    if user["xp"] < 30:
        return "❌ Du hast nicht genug XP."
    if len(user["tiere"]) >= 2 + (user["lvl"] // 10):
        return "❌ Du kannst aktuell nicht mehr Tiere halten."

    user["xp"] -= 30
    user["tiere"].append({"art": emoji, "name": SHOP_PETS[emoji]["name"]})
    data[str(user_id)] = user
    save_data(data)
    return f"✅ {emoji} wurde zu deinem Inventar hinzugefügt!"

# === TIER UMBENENNEN ===
def rename_pet(user_id, emoji, new_name):
    data = load_data()
    user = data.get(str(user_id), {"tiere": []})
    for pet in user["tiere"]:
        if pet.get("art") == emoji:
            pet["name"] = new_name
            data[str(user_id)] = user
            save_data(data)
            return f"✅ Dein {emoji} heißt jetzt *{new_name}*."
    return "❌ Du besitzt dieses Tier nicht."

# === TELEGRAM HANDLER ===
@bot.message_handler(func=lambda m: True)
def handle_message(message):
    user_id = message.from_user.id
    name = message.from_user.first_name
    text = message.text.strip() if message.text else ""

    if text.startswith("!"):
        cmd = text.lower()
        if cmd == "!hilfe":
            antwort = (
                "📜 *Befehlsübersicht*\n"
                "!hilfe – Zeigt diese Hilfe\n"
                "!xp – Zeigt dein Level und XP\n"
                "!shop – Zeigt verfügbare Tiere\n"
                "!kauf [Emoji|Name] – Kauft ein Tier\n"
                "!benenne [Emoji] [NeuerName] – Benennt ein Haustier um"
            )
        elif cmd == "!xp":
            antwort = check_stats(user_id, name)
        elif cmd == "!shop":
            antwort = show_shop()
        elif cmd.startswith("!kauf"):
            parts = text.split()
            if len(parts) >= 2:
                antwort = buy_pet(user_id, name, parts[1])
            else:
                antwort = "❌ Bitte gib ein Tier-Emoji oder Namen an. Beispiel: !kauf 🐍 oder !kauf schlange"
        elif cmd.startswith("!benenne"):
            parts = text.split()
            if len(parts) >= 3:
                antwort = rename_pet(user_id, parts[1], " ".join(parts[2:]))
            else:
                antwort = "❌ Format: !benenne 🐍 NeuerName"
        else:
            antwort = "❓ Unbekannter Befehl."
    else:
        antwort = update_xp(user_id, name)

    if antwort:
        bot.reply_to(message, antwort)

# === BOT START ===
keep_alive()
bot.polling()
