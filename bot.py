from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
import asyncio
import os

TOKEN = os.getenv("TOKEN")

if not TOKEN:
    raise ValueError("TOKEN not set")


# /start menu
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🎬 Vote Movie", callback_data="vote")],
        [InlineKeyboardButton("✍️ Suggest Movie", callback_data="suggest")],
        [InlineKeyboardButton("📜 Rules", callback_data="rules")],
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Welcome to the movie group 🎬\nChoose an option:",
        reply_markup=reply_markup,
    )


# Button actions
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "rules":
        await query.message.reply_text(
            "📜 Group Rules:\n\n"
            "1. Respect everyone 🤝\n"
            "2. No spam 🚫\n"
            "3. Keep discussion movie-related 🎬\n"
            "4. No unnecessary forwards ❌\n"
            "5. Join meetups only if you're serious 😄"
        )

    elif query.data == "vote":
        await query.message.reply_poll(
            question="🎬 Which movie should we watch?",
            options=[
                "Interstellar",
                "Dune Part Two",
                "John Wick",
                "Suggest your own below ✍️",
            ],
            is_anonymous=False,
        )

    elif query.data == "suggest":
        await query.message.reply_text(
            "✍️ Reply in chat with your movie suggestion.\n\nExample:\nDeadpool & Wolverine"
        )


# Welcome message
async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.new_chat_members:
        for user in update.message.new_chat_members:
            name = user.first_name

            msg = await update.message.reply_text(
                f"Welcome {name}! 🎬\nTap /start to see options."
            )

            await asyncio.sleep(10)
            await msg.delete()


app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button_handler))
app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))

print("Bot running 🚀")
app.run_polling()
