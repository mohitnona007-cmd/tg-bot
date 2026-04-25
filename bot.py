from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
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
import re
import requests
import urllib.parse
import random
from datetime import datetime

TOKEN = os.getenv("TOKEN")
OMDB_API_KEY = os.getenv("OMDB_API_KEY")

if not TOKEN:
    raise ValueError("TOKEN not set")

if not OMDB_API_KEY:
    raise ValueError("OMDB_API_KEY not set")

movie_suggestions = []
waiting_for_movie = set()
warns = {}
user_message_times = {}

BAD_WORDS = {
    "fuck",
    "bitch",
    "shit",
    "mc",
    "bc",
    "madarchod",
    "behenchod",
    "gandu",
    "chutiya",
}

DAILY_QUESTIONS = [
    "🎬 What's the best movie sequel ever made?",
    "🍿 Which movie deserved an Oscar but got ignored?",
    "😱 Best thriller movie of all time?",
    "😂 Funniest movie you've watched?",
    "❤️ Best romantic movie ever?",
    "🔥 Which actor never disappoints?",
    "🎥 One movie you wish you could watch again for the first time?",
]


async def is_admin(chat_id, user_id, context):
    member = await context.bot.get_chat_member(chat_id, user_id)
    return member.status in ["administrator", "creator"]


# ---------------- START MENU ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🎬 Vote Movie", callback_data="vote")],
        [InlineKeyboardButton("✍️ Suggest Movie", callback_data="suggest")],
        [InlineKeyboardButton("📜 Rules", callback_data="rules")],
        [InlineKeyboardButton("💬 Daily Question", callback_data="daily")],
        [InlineKeyboardButton("🎞 Trailer Search", callback_data="trailer_help")],
    ]

    await update.message.reply_text(
        "Welcome 👋\nChoose an option:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# ---------------- BUTTONS ----------------
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    chat_id = query.message.chat_id

    await query.answer()

    if query.data == "rules":
        await query.message.reply_text(
            "📜 Group Rules:\n\n"
            "1. Respect everyone 🤝\n"
            "2. No spam 🚫\n"
            "3. No abusive language ❌\n"
            "4. No harassment / personal attacks 🚫\n"
            "5. No unnecessary forwards ❌\n"
            "6. Keep things chill and friendly 😄"
        )

    elif query.data == "suggest":
        waiting_for_movie.add(user_id)
        await query.message.reply_text("✍️ Send your movie suggestion in chat.")

    elif query.data == "vote":
        if not await is_admin(chat_id, user_id, context):
            await query.message.reply_text("Only admins can start polls 👮")
            return

        if not movie_suggestions:
            await query.message.reply_text(
                "No movie suggestions yet 😅\nUse ✍️ Suggest Movie first."
            )
            return

        await query.message.reply_poll(
            question="🎬 Which movie should we watch?",
            options=movie_suggestions[:9] + ["NOTA 🙅"],
            is_anonymous=False,
        )

    elif query.data == "daily":
        if not await is_admin(chat_id, user_id, context):
            await query.message.reply_text("Only admins can post daily questions 👮")
            return

        await query.message.reply_text(random.choice(DAILY_QUESTIONS))

    elif query.data == "trailer_help":
        await query.message.reply_text(
            "Use:\n/movie movie name\n\nExample:\n/movie Interstellar"
        )


# ---------------- SAVE MOVIE SUGGESTIONS ----------------
async def save_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user_id = update.message.from_user.id
    text = update.message.text.strip()

    if user_id in waiting_for_movie:
        if text.lower() in [m.lower() for m in movie_suggestions]:
            await update.message.reply_text("That movie is already suggested 🎬")
        else:
            movie_suggestions.append(text)
            await update.message.reply_text(f"Added: {text} ✅")

        waiting_for_movie.remove(user_id)


# ---------------- MOVIE LOOKUP ----------------
async def movie_lookup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /movie movie name")
        return

    movie_name = " ".join(context.args)

    url = f"http://www.omdbapi.com/?apikey={OMDB_API_KEY}&t={urllib.parse.quote(movie_name)}"
    response = requests.get(url).json()

    if response.get("Response") == "False":
        await update.message.reply_text("Movie not found 😅")
        return

    title = response.get("Title", "N/A")
    year = response.get("Year", "N/A")
    rating = response.get("imdbRating", "N/A")
    genre = response.get("Genre", "N/A")
    runtime = response.get("Runtime", "N/A")
    plot = response.get("Plot", "N/A")

    trailer_url = (
        "https://www.youtube.com/results?search_query="
        + urllib.parse.quote(f"{title} trailer")
    )

    keyboard = [
        [InlineKeyboardButton("▶ Watch Trailer", url=trailer_url)]
    ]

    await update.message.reply_text(
        f"🎬 {title} ({year})\n"
        f"⭐ IMDb: {rating}\n"
        f"🎭 Genre: {genre}\n"
        f"⏱ Runtime: {runtime}\n\n"
        f"📝 {plot}",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# ---------------- WELCOME ----------------
async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.new_chat_members:
        for user in update.message.new_chat_members:
            msg = await update.message.reply_text(
                f"Welcome {user.first_name}! 🎬\n\n"
                "Introduce yourself 👋\n"
                "• Name:\n"
                "• Area:\n"
                "• Favorite Movies:\n"
                "• Favorite Genre:\n\n"
                "Tap /start for group options."
            )

            await asyncio.sleep(30)
            await msg.delete()
            # ---------------- WARN SYSTEM ----------------
async def warn_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_chat.id, update.effective_user.id, context):
        await update.message.reply_text("Admins only 👮")
        return

    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to a user's message with /warn")
        return

    target = update.message.reply_to_message.from_user
    target_id = target.id

    warns[target_id] = warns.get(target_id, 0) + 1
    count = warns[target_id]

    await update.message.reply_text(
        f"⚠ {target.first_name} has been warned ({count}/3)"
    )

    if count >= 3:
        until = datetime.utcnow().timestamp() + 3600

        try:
            await context.bot.restrict_chat_member(
                chat_id=update.effective_chat.id,
                user_id=target_id,
                permissions={},
                until_date=until,
            )

            warns[target_id] = 0

            await update.message.reply_text(
                f"🔇 {target.first_name} muted for 1 hour."
            )
        except Exception:
            await update.message.reply_text(
                "Couldn't mute user (check bot admin permissions)."
            )


# ---------------- MAIN TEXT HANDLER ----------------
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user = update.effective_user
    user_id = user.id
    chat_id = update.effective_chat.id
    text = update.message.text.strip()

    # -------- ANTI LINK SPAM --------
    if "http://" in text.lower() or "https://" in text.lower() or "t.me/" in text.lower():
        try:
            if not await is_admin(chat_id, user_id, context):
                await update.message.delete()
                warn = await update.effective_chat.send_message(
                    f"{user.first_name}, links are not allowed 🚫"
                )
                await asyncio.sleep(5)
                await warn.delete()
                return
        except Exception:
            pass

    # -------- FLOOD CONTROL --------
    now = datetime.utcnow().timestamp()

    if user_id not in user_message_times:
        user_message_times[user_id] = []

    user_message_times[user_id] = [
        t for t in user_message_times[user_id]
        if now - t <= 10
    ]

    user_message_times[user_id].append(now)

    if len(user_message_times[user_id]) >= 5:
        try:
            if not await is_admin(chat_id, user_id, context):
                until = now + 300

                await context.bot.restrict_chat_member(
                    chat_id=chat_id,
                    user_id=user_id,
                    permissions={},
                    until_date=until,
                )

                msg = await update.effective_chat.send_message(
                    f"{user.first_name} muted for spam (5 mins) 🚫"
                )

                await asyncio.sleep(5)
                await msg.delete()
                return
        except Exception:
            pass

    # -------- CUSS FILTER --------
    clean_words = re.findall(r"\b\w+\b", text.lower())

    if any(word in BAD_WORDS for word in clean_words):
        try:
            if not await is_admin(chat_id, user_id, context):
                await update.message.delete()

                warn = await update.effective_chat.send_message(
                    f"{user.first_name}, keep chat clean 👍"
                )

                await asyncio.sleep(5)
                await warn.delete()
                return
        except Exception:
            return

    # -------- SAVE MOVIE SUGGESTION --------
    if user_id in waiting_for_movie:
        if text.lower() in [m.lower() for m in movie_suggestions]:
            await update.message.reply_text("That movie is already suggested 🎬")
        else:
            movie_suggestions.append(text)
            await update.message.reply_text(f"Added: {text} ✅")

        waiting_for_movie.remove(user_id)


# ---------------- APP START ----------------
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("movie", movie_lookup))
app.add_handler(CommandHandler("warn", warn_user))

app.add_handler(CallbackQueryHandler(button_handler))

app.add_handler(
    MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome)
)

app.add_handler(
    MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)
)

print("Bot running 🚀")
app.run_polling()
