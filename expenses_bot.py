import os
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

TOKEN = os.getenv("8297091916:AAEKGh-uo2c6mm-IJW10HPhvNwcaT9XcN0g")

# In-memory store for user expenses
user_expenses = {}

# Keyboard with "Paid" button
keyboard = ReplyKeyboardMarkup([["Paid"]], resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_expenses[user_id] = []
    await update.message.reply_text("👋 Hello! Send me your expenses (e.g. 5.50 lunch).", reply_markup=keyboard)

async def add_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if text.lower() == "paid":
        await reset(update, context)
        return

    # Try to extract the amount
    try:
        amount = float(text.split()[0])
    except ValueError:
        await update.message.reply_text("❌ Please send an expense like: 5.50 coffee")
        return

    # Store the expense
    if user_id not in user_expenses:
        user_expenses[user_id] = []
    user_expenses[user_id].append(amount)

    total = sum(user_expenses[user_id])
    await update.message.reply_text(f"✅ Added: {amount:.2f}\n💰 Total: {total:.2f}")

async def show_total(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    total = sum(user_expenses.get(user_id, []))
    await update.message.reply_text(f"💰 Current total: {total:.2f}")

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_expenses[user_id] = []
    await update.message.reply_text("✅ Total has been reset to 0.00")

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("total", show_total))
    app.add_handler(CommandHandler("paid", reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, add_expense))

    print("🤖 Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
