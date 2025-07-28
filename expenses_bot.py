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
SELECTING_CATEGORY, ENTERING_AMOUNT, ADDING_CATEGORY, DELETING_CATEGORY, MANUAL_AMOUNT, DELETING_ENTRY, EDITING_ENTRY_SELECT, EDITING_ENTRY_AMOUNT = range(8)

# === Emoji Mapping for Categories ===
CATEGORY_EMOJI = {
    "Lunch": "🍽️",
    "Dinner": "🍽️",
    "Groceries": "🛒"
}

# === Helpers ===
def current_date():
    today = datetime.now()
    return today.strftime("%d-%m") + f" ({today.strftime('%a')})"

def read_total():
    try:
        with open(TOTAL_FILE, "r") as f:
            return float(f.read())
    except:
        return 0.0

def write_total(value):
    with open(TOTAL_FILE, "w") as f:
        f.write(str(value))

def add_expense_line(line):
    with open(EXPENSE_FILE, "a") as f:
        f.write(f"{current_date()} | {line}\n")

def read_expenses():
    if not os.path.exists(EXPENSE_FILE):
        return []
    with open(EXPENSE_FILE, "r") as f:
        return [l.strip() for l in f if l.strip()]

def write_expenses(lines):
    with open(EXPENSE_FILE, "w") as f:
        f.write("\n".join(lines) + "\n")

def clear_expenses():
    open(EXPENSE_FILE, "w").close()

def read_categories():
    if not os.path.exists(CATEGORIES_FILE):
        with open(CATEGORIES_FILE, "w") as f:
            f.write("Lunch\nDinner\nGroceries\n")
    with open(CATEGORIES_FILE, "r") as f:
        return [c.strip() for c in f.readlines() if c.strip()]

def write_categories(categories):
    with open(CATEGORIES_FILE, "w") as f:
        f.write("\n".join(categories) + "\n")

def add_category(name):
    cats = read_categories()
    if name not in cats:
        cats.append(name)
        write_categories(cats)

def delete_category(name):
    cats = [c for c in read_categories() if c != name]
    write_categories(cats)

def extract_amount(text):
    match = re.search(r"\$([0-9]+(\.[0-9]+)?)", text)
    return float(match.group(1)) if match else 0.0

# === Voice Helper (No Pydub) ===
async def send_tts(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    try:
        tts = gTTS(text=text, lang="en")
        filename = "tts.mp3"
        tts.save(filename)
        with open(filename, "rb") as f:
            await update.message.reply_audio(audio=f)
    except Exception as e:
        print(f"[Voice Error] {e}")

# === Bot Logic ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_type = update.message.chat.type
    if chat_type == "private":
        cats = [f"{CATEGORY_EMOJI.get(c, '🍱')} {c}" for c in read_categories()]
        keyboard = [cats[i:i+2] for i in range(0, len(cats), 2)]
        keyboard += [
            ["➕ Add Category", "🗑️ Delete Category"],
            ["🗑️ Delete Entry", "✏️ Edit Entry"],
            ["📋 SHOW EXPENSES"],
            ["💵 PAID"]
        ]
    else:
        keyboard = [["📋 SHOW EXPENSES"], ["💵 PAID"]]

    await update.message.reply_text("🤔 What will you like to do?",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    return SELECTING_CATEGORY

async def category_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text.strip()
    if any(choice.startswith(e) for e in CATEGORY_EMOJI.values()) or choice.startswith("🍱"):
        choice = choice.split(" ", 1)[1]

    if choice == "➕ Add Category":
        await update.message.reply_text("✏️ Send me the new category name:")
        return ADDING_CATEGORY
    if choice == "🗑️ Delete Category":
        kb = [[f"{CATEGORY_EMOJI.get(c, '🍱')} {c}" for c in read_categories()[i:i+2]] for i in range(0, len(read_categories()), 2)] + [["Cancel"]]
        await update.message.reply_text("🗑️ Choose a category to delete:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
        return DELETING_CATEGORY
    if choice == "🗑️ Delete Entry":
        return await show_deletable_entries(update, context)
    if choice == "✏️ Edit Entry":
        return await edit_entry_select(update, context)
    if choice in ["📋 SHOW EXPENSES"]:
        return await show_expenses(update, context)
    if choice in ["💵 PAID"]:
        return await paid(update, context)

    context.user_data["category"] = choice
    quick_buttons = [["10", "12"], ["15", "20"], ["Manual Input"]]
    await update.message.reply_text(f"🍱 {choice} selected. Choose amount or Manual Input:",
        reply_markup=ReplyKeyboardMarkup(quick_buttons, resize_keyboard=True))
    return ENTERING_AMOUNT

# === Expense Handling ===
async def handle_quick_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "Manual Input":
        await update.message.reply_text("💰 Enter the amount spent:", reply_markup=ForceReply())
        return MANUAL_AMOUNT
    try:
        await save_expense(update, context, float(text))
    except:
        await update.message.reply_text("❌ Invalid amount.")
    return await start(update, context)

async def manual_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await save_expense(update, context, float(update.message.text.strip()))
    except:
        await update.message.reply_text("❌ Invalid number.")
    return await start(update, context)

async def save_expense(update: Update, context: ContextTypes.DEFAULT_TYPE, amount: float):
    cat = context.user_data["category"]
    total = read_total() + amount
    write_total(total)
    add_expense_line(f"{cat}: ${amount:.2f}")
    await update.message.reply_text(f"✅ Added: {cat} – ${amount:.2f}\n💵 Current Total: ${total:.2f}")

    if GROUP_CHAT_ID:
        try:
            await context.bot.send_message(GROUP_CHAT_ID, f"📢 {cat} ${amount:.2f} added. Total now ${total:.2f}")
        except: pass

# === Category Management ===
async def add_new_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    add_category(update.message.text.strip())
    await update.message.reply_text("✅ Category added.")
    return await start(update, context)

async def delete_category_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip().replace("🍱 ", "").replace("🍽️ ", "").replace("🛒 ", "")
    if name == "Cancel":
        await update.message.reply_text("❌ Cancelled.")
    else:
        delete_category(name)
        await update.message.reply_text(f"🗑️ Deleted category {name}.")
    return await start(update, context)

# === Show Expenses ===
async def show_expenses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lines = read_expenses()
    if not lines:
        await update.message.reply_text("📭 No expenses recorded.")
    else:
        total = 0.0
        msg = "📋 Expenses:\n"
        for line in lines:
            msg += f" - {line}\n"
            total += extract_amount(line)
        msg += f"\n💵 Current Total: ${total:.2f}"

        await update.message.reply_text(msg)
        await send_tts(update, context, f"The current total is {total:.2f} dollars")
    return await start(update, context)

# === Paid ===
async def paid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    total = read_total()
    write_total(0.0)
    clear_expenses()
    await update.message.reply_text("✅ Paid. Total reset to $0.00")
    await send_tts(update, context, f"{total:.2f} dollars has been paid and reset to zero.")
    return await start(update, context)

# === Placeholder Functions for Entry Editing ===
async def show_deletable_entries(update, context): ...
async def edit_entry_select(update, context): ...

# === MAIN ===
if __name__ == "__main__":
    BOT_TOKEN = os.getenv("BOT_TOKEN", "8297091916:AAEKGh-uo2c6mm-IJW10HPhvNwcaT9XcN0g")
    request = HTTPXRequest(connect_timeout=30.0, read_timeout=30.0)
    app = ApplicationBuilder().token(BOT_TOKEN).request(request).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SELECTING_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, category_selected)],
            ENTERING_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_quick_amount)],
            MANUAL_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, manual_amount)],
            ADDING_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_new_category)],
            DELETING_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_category_choice)],
        },
        fallbacks=[CommandHandler("start", start)],
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler("menu", start))
    print("🤖 Bot (Render Compatible) is running...")
    app.run_polling()
