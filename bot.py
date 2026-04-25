from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes
import asyncio
import os

# Get token from Railway environment
TOKEN = os.getenv("TOKEN")

if not TOKEN:
    raise ValueError("TOKEN not set")

# 🔹 /start command (for testing)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot is working ✅")

# 🔹 Welcome new members
async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.new_chat_members:
        for user in update.message.new_chat_members:
            name = user.first_name

            msg = await update.message.reply_text(
                f"Welcome {name}! 🎬\nIntroduce yourself + your favorite movie"
            )

            # Auto delete after 10 sec
            await asyncio.sleep(10)
            await msg.delete()

# 🔹 Create app
app = ApplicationBuilder().token(TOKEN).build()

# 🔹 Handlers
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))

# 🔹 Run bot
print("Bot started successfully 🚀")
app.run_polling()
