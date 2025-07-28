from telegram import Update, ReplyKeyboardMarkup, ForceReply
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters, ConversationHandler
import os, re
from datetime import datetime
from gtts import gTTS
from pydub import AudioSegment
from pydub.utils import which
from telegram.request import HTTPXRequest

# === FFmpeg Setup ===
AudioSegment.converter = which("ffmpeg") or "C:/ffmpeg/bin/ffmpeg.exe"
AudioSegment.ffprobe = which("ffprobe") or "C:/ffmpeg/bin/ffprobe.exe"

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

# === Voice Helper ===
def make_voice_file(text):
    tts = gTTS(text=text, lang="en")
    tts.save("tts.mp3")
    sound = AudioSegment.from_mp3("tts.mp3")
    sound.export("tts.ogg", format="ogg", codec="libopus", bitrate="24k")
    return "tts.ogg"

# === BOT LOGIC ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_type = update.message.chat.type
    if chat_type == "private":
        cats = [f"{CATEGORY_EMOJI.get(c, '🍱')} {c}" for c in read_categories()]
        keyboard = [cats[i:i+2] for i in range(0, len(cats), 2)]
        keyboard += [
            ["➕ Add Category", "🗑️ Delete Category"],
            ["🗑️ Delete Entry", "✏️ Edit Entry"],
            ["📋 Show Expenses"],
            ["💵 Paid"]
        ]
    else:
        keyboard = [["📋 Show Expenses"], ["💵 Paid"]]

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
    if choice in ["📋 Show Expenses", "Show Expenses"]:
        return await show_expenses(update, context)
    if choice in ["💵 Paid", "Paid"]:
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
        await update.message.reply_text("💰 Enter the amount spent (e.g. 12.50):",
            reply_markup=ForceReply(input_field_placeholder="Enter amount"))
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
        await update.message.reply_text("❌ Please enter a valid number.")
    return await start(update, context)

async def save_expense(update: Update, context: ContextTypes.DEFAULT_TYPE, amount: float):
    cat = context.user_data["category"]
    total = read_total() + amount
    write_total(total)
    add_expense_line(f"{cat}: ${amount:.2f}")

    await update.message.reply_text(f"✅ Added: {cat} – ${amount:.2f}\n🧾 Current Total: ${total:.2f}")

    if GROUP_CHAT_ID:
        try:
            await context.bot.send_message(GROUP_CHAT_ID, f"📢 {cat} ${amount:.2f} was added. Total is now ${total:.2f}")
        except Exception as e:
            print(f"[Warning] Could not send to group: {e}")

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
        await update.message.reply_text(f"🗑️ Category {name} deleted.")
    return await start(update, context)

# === Entry Deletion ===
async def show_deletable_entries(update: Update, context: ContextTypes.DEFAULT_TYPE):
    entries = read_expenses()
    if not entries:
        await update.message.reply_text("📭 No entries to delete.")
        return await start(update, context)
    msg = "🗑️ Send me the number of the entry to delete:\n" + "\n".join([f"{i+1}. {line}" for i, line in enumerate(entries)])
    await update.message.reply_text(msg)
    context.user_data["entries"] = entries
    return DELETING_ENTRY

async def delete_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        i = int(update.message.text.strip()) - 1
        entries = context.user_data["entries"]
        deleted = entries.pop(i)
        write_expenses(entries)
        total = sum(extract_amount(e) for e in entries)
        write_total(total)
        await update.message.reply_text(f"🗑️ Deleted: {deleted}\n🧾 Current Total: ${total:.2f}")
    except:
        await update.message.reply_text("❌ Invalid number.")
    return await start(update, context)

# === Edit Entry ===
async def edit_entry_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    entries = read_expenses()
    if not entries:
        await update.message.reply_text("📭 No entries to edit.")
        return await start(update, context)
    msg = "✏️ Send me the number of the entry to edit:\n" + "\n".join([f"{i+1}. {line}" for i, line in enumerate(entries)])
    await update.message.reply_text(msg)
    context.user_data["entries"] = entries
    return EDITING_ENTRY_SELECT

async def edit_entry_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        i = int(update.message.text.strip()) - 1
        entries = context.user_data["entries"]
        if i < 0 or i >= len(entries): raise ValueError
        context.user_data["edit_index"] = i
        await update.message.reply_text(f"💰 Enter the new amount for:\n{entries[i]}")
        return EDITING_ENTRY_AMOUNT
    except:
        await update.message.reply_text("❌ Invalid number.")
        return await start(update, context)

async def edit_entry_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        new_amount = float(update.message.text.strip())
        i = context.user_data["edit_index"]
        entries = context.user_data["entries"]

        parts = entries[i].split("|", 1)
        date_part, desc = parts if len(parts) == 2 else (current_date(), entries[i])
        category = desc.split(":")[0].strip()
        entries[i] = f"{date_part.strip()} | {category}: ${new_amount:.2f}"

        write_expenses(entries)
        total = sum(extract_amount(e) for e in entries)
        write_total(total)

        await update.message.reply_text(f"✏️ Updated entry to ${new_amount:.2f}\n🧾 Current Total: ${total:.2f}")
    except:
        await update.message.reply_text("❌ Invalid amount.")
    return await start(update, context)

# === Show Expenses ===
async def show_expenses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lines = read_expenses()
    if not lines:
        await update.message.reply_text("📭 No expenses recorded yet.")
    else:
        grouped, total = {}, 0.0
        for line in lines:
            d, item = line.split(" | ", 1)
            grouped.setdefault(d, []).append(item)
            total += extract_amount(item)

        msg = "📋 Expenses by Date:\n"
        for d, items in grouped.items():
            msg += f"\n📅 {d}\n" + "\n".join([f" - {i}" for i in items]) + "\n"
        msg += f"\n💵 Current Total: ${total:.2f}"

        await update.message.reply_text(msg)

        try:
            voice_file = make_voice_file(f"The current total is {total:.2f} dollars")
            with open(voice_file, "rb") as f:
                await update.message.reply_voice(voice=f)
        except Exception as e:
            print(f"[Warning] Voice send failed: {e}")

    return await start(update, context)

# === Paid ===
async def paid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    total = read_total()
    await update.message.reply_text("✅ All paid. Total reset to $0.00")

    try:
        voice_file = make_voice_file(f"{total:.2f} dollars has been paid. Total reset to zero.")
        with open(voice_file, "rb") as f:
            await update.message.reply_voice(voice=f)
    except Exception as e:
        print(f"[Warning] Voice send failed: {e}")

    write_total(0.0)
    clear_expenses()
    return await start(update, context)

# === MAIN ===
if __name__ == "__main__":
    request = HTTPXRequest(connect_timeout=30.0, read_timeout=30.0)
    import os
BOT_TOKEN = os.getenv("BOT_TOKEN")
app = ApplicationBuilder().token(BOT_TOKEN).request(request).build()


    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SELECTING_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, category_selected)],
            ENTERING_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_quick_amount)],
            MANUAL_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, manual_amount)],
            ADDING_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_new_category)],
            DELETING_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_category_choice)],
            DELETING_ENTRY: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_entry)],
            EDITING_ENTRY_SELECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_entry_number)],
            EDITING_ENTRY_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_entry_amount)],
        },
        fallbacks=[CommandHandler("start", start)],
    )

    app.add_handler(conv)
    print("🤖 Bot (Final Version with Fixed Functions + Category Emojis) is running...")
    app.add_handler(CommandHandler("menu", start))
    app.run_polling()
