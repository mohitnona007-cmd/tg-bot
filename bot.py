from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ChatPermissions,
)
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
import asyncio
import os
import re
import requests
import urllib.parse
import random
from datetime import datetime, time, timezone, timedelta

TOKEN = os.getenv("TOKEN")
OMDB_API_KEY = os.getenv("OMDB_API_KEY")
TMDB_API_KEY = os.getenv("TMDB_API_KEY")

if not TOKEN:
    raise ValueError("TOKEN not set")
if not OMDB_API_KEY:
    raise ValueError("OMDB_API_KEY not set")
if not TMDB_API_KEY:
    raise ValueError("TMDB_API_KEY not set")

movie_suggestions = []
waiting_for_movie = set()
warns = {}
user_message_times = {}
GROUP_CHAT_ID = None

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

recent_genre_suggestions = {
    "comedy": [],
    "action": [],
    "horror": [],
    "romance": [],
    "scifi": [],
    "drama": [],
    "random": [],
}


async def is_admin(chat_id, user_id, context):
    member = await context.bot.get_chat_member(chat_id, user_id)
    return member.status in ["administrator", "creator"]


async def auto_daily_question(context: ContextTypes.DEFAULT_TYPE):
    global GROUP_CHAT_ID
    if GROUP_CHAT_ID:
        await context.bot.send_message(
            chat_id=GROUP_CHAT_ID,
            text=random.choice(DAILY_QUESTIONS),
        )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global GROUP_CHAT_ID
    GROUP_CHAT_ID = update.effective_chat.id

    keyboard = [
        [InlineKeyboardButton("🎬 Vote Movie", callback_data="vote")],
        [InlineKeyboardButton("✍️ Suggest Movie", callback_data="suggest")],
        [InlineKeyboardButton("🎭 Suggest by Genre", callback_data="genre_menu")],
        [InlineKeyboardButton("📜 Rules", callback_data="rules")],
        [InlineKeyboardButton("💬 Daily Question", callback_data="daily")],
        [InlineKeyboardButton("🎞 Trailer Search", callback_data="trailer_help")],
    ]

    await update.message.reply_text(
        "Welcome 👋\nChoose an option:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
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
        await query.message.reply_text(
            "✍️ Send your movie suggestion in chat."
        )

    elif query.data == "daily":
        await query.message.reply_text(
            random.choice(DAILY_QUESTIONS)
        )

    elif query.data == "trailer_help":
        await query.message.reply_text(
            "Use:\n/movie movie name\n\nExample:\n/movie Interstellar"
        )

    elif query.data == "genre_menu":
        genre_keyboard = [
            [
                InlineKeyboardButton("😂 Comedy", callback_data="genre_comedy"),
                InlineKeyboardButton("🔥 Action", callback_data="genre_action"),
            ],
            [
                InlineKeyboardButton("😱 Horror", callback_data="genre_horror"),
                InlineKeyboardButton("❤️ Romance", callback_data="genre_romance"),
            ],
            [
                InlineKeyboardButton("🧠 Sci-Fi", callback_data="genre_scifi"),
                InlineKeyboardButton("🎭 Drama", callback_data="genre_drama"),
            ],
            [
                InlineKeyboardButton("🎲 Random", callback_data="genre_random"),
            ],
        ]

        await query.message.reply_text(
            "Pick a genre 🎬",
            reply_markup=InlineKeyboardMarkup(genre_keyboard),
        )


async def movie_lookup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /movie movie name")
        return

    movie_name = " ".join(context.args)

    url = (
        f"http://www.omdbapi.com/?apikey={OMDB_API_KEY}"
        f"&t={urllib.parse.quote(movie_name)}"
    )

    try:
        response = requests.get(url, timeout=10).json()
    except Exception:
        await update.message.reply_text(
            "Couldn't fetch movie info 😅"
        )
        return

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

            try:
                await msg.delete()
            except Exception:
                pass

GENRE_MAP = {
    "comedy": 35,
    "action": 28,
    "horror": 27,
    "romance": 10749,
    "scifi": 878,
    "drama": 18,
}


def fetch_tmdb_movies(genre_key):
    if genre_key == "random":
        genre_id = random.choice(list(GENRE_MAP.values()))
    else:
        genre_id = GENRE_MAP[genre_key]

    page = random.randint(1, 10)

    url = (
        "https://api.themoviedb.org/3/discover/movie"
        f"?api_key={TMDB_API_KEY}"
        f"&with_genres={genre_id}"
        "&vote_count.gte=300"
        "&vote_average.gte=6.8"
        "&with_original_language=en"
        "&sort_by=popularity.desc"
        f"&page={page}"
    )

    try:
        data = requests.get(url, timeout=15).json()
        results = data.get("results", [])
    except Exception:
        return []

    filtered = []
    recent_ids = recent_genre_suggestions[genre_key]

    for movie in results:
        movie_id = movie.get("id")
        title = movie.get("title")
        year = (
            movie.get("release_date", "")[:4]
            if movie.get("release_date")
            else "N/A"
        )

        if movie_id and title and movie_id not in recent_ids:
            filtered.append(
                {
                    "id": movie_id,
                    "title": title,
                    "year": year,
                }
            )

    if len(filtered) < 5:
        recent_genre_suggestions[genre_key] = []
        return fetch_tmdb_movies(genre_key)

    picks = random.sample(filtered, 5)

    recent_genre_suggestions[genre_key].extend(
        [m["id"] for m in picks]
    )

    recent_genre_suggestions[genre_key] = (
        recent_genre_suggestions[genre_key][-50:]
    )

    return picks


async def send_genre_recommendations(query, genre_key):
    movies = fetch_tmdb_movies(genre_key)

    if not movies:
        await query.message.reply_text(
            "Couldn't fetch recommendations 😅"
        )
        return

    title_map = {
        "comedy": "😂 Comedy Picks",
        "action": "🔥 Action Picks",
        "horror": "😱 Horror Picks",
        "romance": "❤️ Romance Picks",
        "scifi": "🧠 Sci-Fi Picks",
        "drama": "🎭 Drama Picks",
        "random": "🎲 Random Picks",
    }

    lines = [f"{title_map[genre_key]}\n"]

    for i, movie in enumerate(movies, start=1):
        trailer_link = (
            "https://www.youtube.com/results?search_query="
            + urllib.parse.quote(
                f"{movie['title']} trailer"
            )
        )

        lines.append(
            f"{i}. "
            f"<a href='{trailer_link}'>"
            f"{movie['title']} ({movie['year']})"
            f"</a>"
        )

    await query.message.reply_text(
        "\n".join(lines),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


# extend button handler for genre buttons + vote
_old_button_handler = button_handler


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "vote":
        if not movie_suggestions:
            await query.message.reply_text(
                "No movie suggestions yet 😅\n"
                "Use ✍️ Suggest Movie first."
            )
            return

        await query.message.reply_poll(
            question="🎬 Which movie should we watch?",
            options=movie_suggestions[:9] + ["NOTA 🙅"],
            is_anonymous=False,
        )
        return

    if data.startswith("genre_"):
        genre_key = data.replace("genre_", "")

        if genre_key == "menu":
            await _old_button_handler(update, context)
            return

        await send_genre_recommendations(
            query,
            genre_key,
        )
        return

    await _old_button_handler(update, context)


async def save_movie_suggestion(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not update.message or not update.message.text:
        return

    user_id = update.message.from_user.id
    text = update.message.text.strip()

    if user_id in waiting_for_movie:
        if text.lower() in [
            m.lower() for m in movie_suggestions
        ]:
            await update.message.reply_text(
                "That movie is already suggested 🎬"
            )
        else:
            movie_suggestions.append(text)

            await update.message.reply_text(
                f"🎬 New Movie Suggested\n\n"
                f"By: {update.effective_user.first_name}\n"
                f"Movie: {text}\n"
                f"Added to next poll ✅"
            )

        waiting_for_movie.remove(user_id)
     async def warn_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(
        update.effective_chat.id,
        update.effective_user.id,
        context,
    ):
        await update.message.reply_text("Admins only 👮")
        return

    if not update.message.reply_to_message:
        await update.message.reply_text(
            "Reply to a user's message with /warn"
        )
        return

    target = update.message.reply_to_message.from_user
    target_id = target.id

    warns[target_id] = warns.get(target_id, 0) + 1
    count = warns[target_id]

    await update.message.reply_text(
        f"⚠ {target.first_name} warned ({count}/3)"
    )

    if count >= 3:
        until = datetime.now(timezone.utc) + timedelta(hours=1)

        try:
            await context.bot.restrict_chat_member(
                chat_id=update.effective_chat.id,
                user_id=target_id,
                permissions=ChatPermissions(can_send_messages=False),
                until_date=until,
            )

            warns[target_id] = 0

            await update.message.reply_text(
                f"🔇 {target.first_name} muted for 1 hour."
            )

        except Exception:
            await update.message.reply_text(
                "Couldn't mute user. Check admin permissions."
            )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user = update.effective_user
    user_id = user.id
    chat_id = update.effective_chat.id
    text = update.message.text.strip()
    lower = text.lower()

    suspicious = [
        "t.me/",
        "joinchat",
        "bit.ly",
        "tinyurl",
        "discord.gg",
    ]

    if any(x in lower for x in suspicious):
        if not await is_admin(chat_id, user_id, context):
            try:
                await update.message.delete()
                return
            except Exception:
                pass

    now = datetime.now().timestamp()

    if user_id not in user_message_times:
        user_message_times[user_id] = []

    user_message_times[user_id] = [
        t for t in user_message_times[user_id]
        if now - t <= 10
    ]

    user_message_times[user_id].append(now)

    if len(user_message_times[user_id]) >= 5:
        if not await is_admin(chat_id, user_id, context):
            try:
                until = datetime.now(timezone.utc) + timedelta(minutes=5)

                await context.bot.restrict_chat_member(
                    chat_id=chat_id,
                    user_id=user_id,
                    permissions=ChatPermissions(can_send_messages=False),
                    until_date=until,
                )

                msg = await update.effective_chat.send_message(
                    f"{user.first_name} muted for spam (5 mins) 🚫"
                )

                await asyncio.sleep(5)

                try:
                    await msg.delete()
                except Exception:
                    pass

                return

            except Exception:
                pass

    clean_words = re.findall(r"\b\w+\b", lower)

    if any(word in BAD_WORDS for word in clean_words):
        if not await is_admin(chat_id, user_id, context):
            try:
                await update.message.delete()

                warn = await update.effective_chat.send_message(
                    f"{user.first_name}, keep chat clean 👍"
                )

                await asyncio.sleep(5)

                try:
                    await warn.delete()
                except Exception:
                    pass

                return

            except Exception:
                return

    await save_movie_suggestion(update, context)


app = ApplicationBuilder().token(TOKEN).build()

app.job_queue.run_daily(
    auto_daily_question,
    time=time(hour=14, minute=30, tzinfo=timezone.utc),
)

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
