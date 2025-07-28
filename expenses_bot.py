from telegram import Update, ReplyKeyboardMarkup, ForceReply
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters, ConversationHandler
import os, re
from datetime import datetime
from gtts import gTTS
from telegram.request import HTTPXRequest

# === Group Chat ID ===
GROUP_CHAT_ID = -4842826753

# === Files ===
TOTAL_FILE = "total.txt"
EXPENSE_FILE = "expenses.txt"
CATEGORIES_FILE = "categories.txt"

# === States ===
SELECTING_CATEGORY, ENTERING_AMOUNT, ADDING_CATEGORY, DELETING_CATEGORY, MANUAL_AMOUNT = range(5)

CATEGORY_EMOJI = {"Lunch": "🍽️", "Dinner": "🍽️", "Groceries": "🛒"}

# === Helpers ===
def current_date():
    return datetime.now().strftime("%d-%m") + f" ({datetime.now().strftime('%a')})"

def read_total():
    try: return float(open(TOTAL_FILE).read())
    except: return 0.0

def write_total(v): open(TOTAL_FILE, "w").write(str(v))

def add_expense_line(line): open(EXPENSE_FILE, "a").write(f"{current_date()} | {line}\n")

def read_expenses(): return [l.strip() for l in open(EXPENSE_FILE).readlines()] if os.path.exists(EXPENSE_FILE) else []

def write_expenses(lines): open(EXPENSE_FILE, "w").write("\n".join(lines) + "\n")

def clear_expenses(): open(EXPENSE_FILE, "w").close()

def read_categories():
    if not os.path.exists(CATEGORIES_FILE): open(CATEGORIES_FILE, "w").write("Lunch\nDinner\nGroceries\n")
    return [c.strip() for c in open(CATEGORIES_FILE).readlines()]

def add_category(c):
    cats = read_categories()
    if c not in cats: open(CATEGORIES_FILE, "a").write(c + "\n")

def delete_category(c): write_expenses([x for x in read_categories() if x != c])

def extract_amount(text):
    m = re.search(r"\$([0-9]+(\.[0-9]+)?)", text)
    return float(m.group(1)) if m else 0.0

# === Voice without pydub ===
async def send_tts(update, text):
    try:
        tts = gTTS(text=text, lang="en")
        filename = "tts.mp3"
        tts.save(filename)
        with open(filename, "rb") as f:
            await update.message.reply_audio(audio=f)
    except Exception as e:
        print("[Voice Error]", e)

# === Bot Logic ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [["📋 SHOW EXPENSES"], ["💵 PAID"]]
    if update.message.chat.type == "private":
        cats = [f"{CATEGORY_EMOJI.get(c,'🍱')} {c}" for c in read_categories()]
        kb = [cats[i:i+2] for i in range(0, len(cats), 2)] + [["➕ Add Category", "🗑️ Delete Category"], ["📋 SHOW EXPENSES"], ["💵 PAID"]]
    await update.message.reply_text("🤔 What will you like to do?", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
    return SELECTING_CATEGORY

async def category_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text.strip()
    if choice.startswith("🍱") or choice.startswith("🍽️") or choice.startswith("🛒"):
        choice = choice.split(" ",1)[1]
    if choice == "➕ Add Category":
        await update.message.reply_text("✏️ Send me new category name:"); return ADDING_CATEGORY
    if choice == "🗑️ Delete Category":
        await update.message.reply_text("🗑️ Send category name to delete:"); return DELETING_CATEGORY
    if choice == "📋 SHOW EXPENSES": return await show_expenses(update, context)
    if choice == "💵 PAID": return await paid(update, context)
    context.user_data["category"] = choice
    await update.message.reply_text(f"🍱 {choice} selected. Enter amount or choose:", reply_markup=ReplyKeyboardMarkup([["10","12"],["15","20"],["Manual Input"]], resize_keyboard=True))
    return ENTERING_AMOUNT

async def handle_quick_amount(update, context):
    if update.message.text=="Manual Input":
        await update.message.reply_text("💰 Enter amount:", reply_markup=ForceReply()); return MANUAL_AMOUNT
    try: await save_expense(update, context, float(update.message.text))
    except: await update.message.reply_text("❌ Invalid number.")
    return await start(update, context)

async def manual_amount(update, context):
    try: await save_expense(update, context, float(update.message.text))
    except: await update.message.reply_text("❌ Invalid number.")
    return await start(update, context)

async def save_expense(update, context, amt):
    cat = context.user_data["category"]; total = read_total() + amt
    write_total(total); add_expense_line(f"{cat}: ${amt:.2f}")
    await update.message.reply_text(f"✅ Added {cat} ${amt:.2f}\n💵 Current Total ${total:.2f}")
    if GROUP_CHAT_ID: await context.bot.send_message(GROUP_CHAT_ID, f"📢 {cat} ${amt:.2f} added. Total ${total:.2f}")

async def add_new_category(update, context): add_category(update.message.text); await update.message.reply_text("✅ Added."); return await start(update, context)
async def delete_category_choice(update, context): delete_category(update.message.text); await update.message.reply_text("🗑️ Deleted."); return await start(update, context)

async def show_expenses(update, context):
    lines = read_expenses()
    if not lines: await update.message.reply_text("📭 No expenses."); return await start(update, context)
    total = sum(extract_amount(l) for l in lines)
    msg = "📋 Expenses:\n" + "\n".join(lines) + f"\n\n💵 Current Total ${total:.2f}"
    await update.message.reply_text(msg)
    await send_tts(update, f"Your current total is {total:.2f} dollars")
    return await start(update, context)

async def paid(update, context):
    total = read_total(); write_total(0.0); clear_expenses()
    await update.message.reply_text("✅ Paid. Total reset to $0.00")
    await send_tts(update, f"{total:.2f} dollars has been paid. Total reset to zero.")
    return await start(update, context)

# === MAIN ===
if __name__ == "__main__":
    BOT_TOKEN = os.getenv("BOT_TOKEN", "8297091916:AAEKGh-uo2c6mm-IJW10HPhvNwcaT9XcN0g")
    app = ApplicationBuilder().token(BOT_TOKEN).request(HTTPXRequest(connect_timeout=30.0, read_timeout=30.0)).build()
    conv = ConversationHandler(entry_points=[CommandHandler("start", start)], states={
        SELECTING_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, category_selected)],
        ENTERING_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_quick_amount)],
        MANUAL_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, manual_amount)],
        ADDING_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_new_category)],
        DELETING_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_category_choice)],
    }, fallbacks=[CommandHandler("start", start)])
    app.add_handler(conv)
    app.add_handler(CommandHandler("menu", start))
    print("🤖 Bot (Render Clean Version) running...")
    app.run_polling()