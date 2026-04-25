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

movie_suggestions = []
waiting_for_movie = set()


# /start
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


# buttons
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id

    await query.answer()

    if query.data == "rules":
        await query.message.reply_text(
            "📜 Group Rules:\n\n"
            "1. Respect everyone 🤝\n"
            "2. No spam 🚫\n"
            "3. Keep discussion movie-related 🎬\n"
            "4. No unnecessary forwards ❌\n"
            "5. Join meetups only if serious 😄"
        )

    elif query.data == "suggest":
        waiting_for_movie.add(user_id)
        await query.message.reply_text(
            "✍️ Send your movie suggestion in chat."
        )

    elif query.data == "vote":
        if not movie_suggestions:
            await query.message.reply_text(
                "No movie suggestions yet 😅\nUse ✍️ Suggest Movie first."
            )
            return

        await query.message.reply_poll(
            question="🎬 Which movie should we watch?",
            options=movie_suggestions[:10],
            is_anonymous=False,
        )


# capture suggested movie
async def save_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text.strip()

    if user_id in waiting_for_movie:
        if text.lower() in [m.lower() for m in movie_suggestions]:
            await update.message.reply_text("That movie is already suggested 🎬")
        else:
            movie_suggestions.append(text)
            await update.message.reply_text(f"Added: {text} ✅")

        waiting_for_movie.remove(user_id)


# welcome
async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.new_chat_members:
        for user in update.message.new_chat_members:
            name = user.first_name

            msg = await update.message.reply_text(
                f"Welcome {name}! 🎬\n\n"
                "Please introduce yourself 👋\n"
                "• Name:\n"
                "• Area:\n"
                "• Favorite Movies:\n\n"
                "Then tap /start for group options."
            )

            await asyncio.sleep(30)
            await msg.delete()


app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button_handler))
app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, save_movie))

print("Bot running 🚀")
app.run_polling()
