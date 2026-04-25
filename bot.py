from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
import asyncio
import os

TOKEN = os.getenv("TOKEN")

async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.new_chat_members:
        for user in update.message.new_chat_members:
            name = user.first_name

            msg = await update.message.reply_text(
                f"Welcome {name}! 🎬\nIntroduce yourself + your favorite movie"
            )

            await asyncio.sleep(10)
            await msg.delete()

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))

app.run_polling()
