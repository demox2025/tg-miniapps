import os, sqlite3, asyncio
from flask import Flask, request, render_template, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_IDS = [int(x) for x in os.environ.get("ADMIN_IDS", "6065882445").split(",") if x.strip().isdigit()]
AD_CREDIT = float(os.environ.get("AD_CREDIT", "0.02"))
FRONTEND_URL = "https://tg-miniapps.onrender.com"

app = Flask(__name__, template_folder="templates")

# DB setup
conn = sqlite3.connect("data.db", check_same_thread=False)
cur = conn.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT, referrer_id INTEGER, balance REAL DEFAULT 0)")
cur.execute("CREATE TABLE IF NOT EXISTS withdrawals (id INTEGER PRIMARY KEY, user_id INTEGER, amount REAL, status TEXT)")
conn.commit()

def ensure_user(user_id, username="", ref=None):
    cur.execute("SELECT id FROM users WHERE id=?", (user_id,))
    if not cur.fetchone():
        cur.execute("INSERT INTO users (id, username, referrer_id) VALUES (?,?,?)",
                    (user_id, username, ref))
        conn.commit()

# BOT setup
application = Application.builder().token(BOT_TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ref = None
    if context.args:
        try: ref = int(context.args[0])
        except: pass
    ensure_user(update.effective_user.id, update.effective_user.username, ref)
    kb = [[InlineKeyboardButton("🚀 Open App", web_app=WebAppInfo(url=FRONTEND_URL))]]
    await update.message.reply_text("স্বাগতম! নিচের বাটনে চাপুন Mini App খোলার জন্য।", reply_markup=InlineKeyboardMarkup(kb))

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id in ADMIN_IDS:
        cur.execute("SELECT COUNT(*) FROM users")
        total_users = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM withdrawals WHERE status='pending'")
        pending = cur.fetchone()[0]
        await update.message.reply_text(f"👥 Users: {total_users}\n⌛ Pending Withdrawals: {pending}")

async def withdraw_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    cur.execute("SELECT amount, status FROM withdrawals WHERE user_id=?", (uid,))
    rows = cur.fetchall()
    if not rows:
        await update.message.reply_text("No withdraw history.")
    else:
        text = "\n".join([f"{amt} - {status}" for amt, status in rows])
        await update.message.reply_text(text)

application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("admin", admin))
application.add_handler(CommandHandler("withdraw_history", withdraw_history))

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/claim", methods=["POST"])
def claim():
    data = request.get_json()
    uid = data.get("user_id")
    if not uid:
        return jsonify({"message":"Telegram এর ভিতর থেকে খুলুন"})
    ensure_user(uid)
    cur.execute("UPDATE users SET balance = COALESCE(balance,0) + ? WHERE id=?", (AD_CREDIT, uid))
    conn.commit()
    return jsonify({"message":f"✅ {AD_CREDIT} ক্রেডিট যোগ হয়েছে!"})

@app.post(f"/webhook/{BOT_TOKEN}")
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    asyncio.run(application.process_update(update))
    return "ok"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
