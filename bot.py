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
import random
import requests
import urllib.parse
from datetime import datetime, time, timezone, timedelta

TOKEN = os.getenv("TOKEN")
OMDB_API_KEY = os.getenv("OMDB_API_KEY")
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
XAI_API_KEY = os.getenv("XAI_API_KEY")

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
join_times = {}
recent_messages = []

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
    "🎬 Best movie sequel ever?",
    "🍿 Most underrated movie?",
    "😱 Best thriller ever?",
    "😂 Funniest movie you've watched?",
    "❤️ Best romance movie?",
    "🔥 Which actor never disappoints?",
    "🎥 One movie you'd watch again fresh?",
]

GENRE_MAP = {
    "comedy": 35,
    "action": 28,
    "horror": 27,
    "romance": 10749,
    "scifi": 878,
    "drama": 18,
}

recent_genre = {
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


async def auto_daily(context: ContextTypes.DEFAULT_TYPE):
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


async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.new_chat_members:
        for user in update.message.new_chat_members:
            join_times[user.id] = datetime.now(timezone.utc)
            
            msg = await update.message.reply_text(
                f"Welcome {user.first_name}! 🎬\n\n"
                "Introduce yourself 👋\n"
                "• Name:\n"
                "• Area:\n"
                "• Favorite Movies:\n"
                "• Favorite Genre:"
            )

            await asyncio.sleep(20)

            try:
                await msg.delete()
            except Exception:
                pass


def fetch_movies(genre_key):
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
        results = requests.get(url, timeout=15).json()["results"]
    except Exception:
        return []

    fresh = [
        m for m in results
        if m["id"] not in recent_genre[genre_key]
    ]

    if len(fresh) < 5:
        recent_genre[genre_key] = []
        fresh = results

    picks = random.sample(fresh, 5)

    recent_genre[genre_key].extend(
        [m["id"] for m in picks]
    )

    recent_genre[genre_key] = recent_genre[genre_key][-50:]

    return picks

async def send_genre_recommendations(query, genre_key):
    movies = fetch_movies(genre_key)

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
        title = movie.get("title", "Unknown")
        release = movie.get("release_date", "")
        year = release[:4] if release else "N/A"

        trailer = (
            "https://www.youtube.com/results?search_query="
            + urllib.parse.quote(f"{title} trailer")
        )

        lines.append(
            f"{i}. "
            f"<a href='{trailer}'>"
            f"{title} ({year})"
            f"</a>"
        )

    await query.message.reply_text(
        "\n".join(lines),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


async def movie_lookup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.message.delete()
    except Exception:
        pass

    if not context.args:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Usage: /movie movie name"
        )
        return

    movie_name = " ".join(context.args)

    url = (
        f"http://www.omdbapi.com/?apikey={OMDB_API_KEY}"
        f"&t={urllib.parse.quote(movie_name)}"
    )

    try:
        data = requests.get(url, timeout=10).json()
    except Exception:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Couldn't fetch movie info 😅"
        )
        return

    if data.get("Response") == "False":
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Movie not found 😅"
        )
        return

    title = data.get("Title", "N/A")
    year = data.get("Year", "N/A")
    rating = data.get("imdbRating", "N/A")
    plot = data.get("Plot", "N/A")

    trailer = (
        "https://www.youtube.com/results?search_query="
        + urllib.parse.quote(f"{title} trailer")
    )

    keyboard = [
        [InlineKeyboardButton("▶ Watch Trailer", url=trailer)]
    ]

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=(
            f"🎬 {title} ({year})\n"
            f"⭐ IMDb: {rating}\n\n"
            f"{plot}"
        ),
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data

    await query.answer()

    if data == "rules":
        await query.message.reply_text(
            "📜 Rules:\n"
            "• Respect everyone\n"
            "• No spam\n"
            "• No abusive language\n"
            "• Keep chat friendly"
        )

    elif data == "suggest":
        waiting_for_movie.add(user_id)
        await query.message.reply_text(
            "✍️ Send movie name in chat."
        )

    elif data == "vote":
        if not movie_suggestions:
            await query.message.reply_text(
                "No suggestions yet 😅"
            )
            return

        await query.message.reply_poll(
            question="🎬 Which movie should we watch?",
            options=movie_suggestions[:9] + ["NOTA 🙅"],
            is_anonymous=False,
        )

    elif data == "daily":
        await query.message.reply_text(
            random.choice(DAILY_QUESTIONS)
        )

    elif data == "trailer_help":
        await query.message.reply_text(
            "Use:\n/movie Interstellar"
        )

    elif data == "genre_menu":
        keyboard = [
            [
                InlineKeyboardButton(
                    "😂 Comedy",
                    callback_data="genre_comedy"
                ),
                InlineKeyboardButton(
                    "🔥 Action",
                    callback_data="genre_action"
                ),
            ],
            [
                InlineKeyboardButton(
                    "😱 Horror",
                    callback_data="genre_horror"
                ),
                InlineKeyboardButton(
                    "❤️ Romance",
                    callback_data="genre_romance"
                ),
            ],
            [
                InlineKeyboardButton(
                    "🧠 Sci-Fi",
                    callback_data="genre_scifi"
                ),
                InlineKeyboardButton(
                    "🎭 Drama",
                    callback_data="genre_drama"
                ),
            ],
            [
                InlineKeyboardButton(
                    "🎲 Random",
                    callback_data="genre_random"
                )
            ],
        ]

        await query.message.reply_text(
            "Pick genre 🎬",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    elif data.startswith("genre_"):
        genre = data.replace("genre_", "")
        await send_genre_recommendations(
            query,
            genre,
        )
        
async def f_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.message.delete()
    except Exception:
        pass

    if context.args:
        name = " ".join(context.args)

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"🪦 Rest in peace, {name}"
        )

    elif update.message.reply_to_message:
        name = update.message.reply_to_message.from_user.first_name

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"🪦 Rest in peace, {name}"
        )

    else:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="🪦 Rest in peace"
        )
        
async def vs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.message.delete()
    except Exception:
        pass

    full_text = update.message.text.replace("/vs", "").strip()

    if "|" not in full_text:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Use:\n/vs Movie 1 | Movie 2"
        )
        return

    movie1, movie2 = full_text.split("|", 1)

    movie1 = movie1.strip()
    movie2 = movie2.strip()

    if not movie1 or not movie2:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Use:\n/vs Movie 1 | Movie 2"
        )
        return

    await context.bot.send_poll(
        chat_id=update.effective_chat.id,
        question="🎬 Which is better?",
        options=[
            movie1,
            movie2,
            "NOTA 🙅"
        ],
        is_anonymous=False,
    ) 
    
async def plot_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.message.delete()
    except Exception:
        pass

    if not context.args:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Use:\n/plot movie name"
        )
        return

    movie_name = " ".join(context.args)

    url = (
        f"http://www.omdbapi.com/?apikey={OMDB_API_KEY}"
        f"&t={urllib.parse.quote(movie_name)}"
    )

    try:
        data = requests.get(url, timeout=10).json()
    except Exception:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Couldn't fetch plot 😅"
        )
        return

    if data.get("Response") == "False":
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Movie not found 😅"
        )
        return

    title = data.get("Title", "Unknown")
    year = data.get("Year", "N/A")
    plot = data.get("Plot", "No plot found.")

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=(
            f"🎬 {title} ({year})\n\n"
            f"{plot}"
        )
    )
async def actor_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.message.delete()
    except Exception:
        pass

    if not context.args:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Use:\n/actor actor name"
        )
        return

    actor_name = " ".join(context.args)

    search_url = (
        "https://api.themoviedb.org/3/search/person"
        f"?api_key={TMDB_API_KEY}"
        f"&query={urllib.parse.quote(actor_name)}"
    )

    try:
        search = requests.get(search_url, timeout=10).json()
        results = search.get("results", [])
    except Exception:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Couldn't fetch actor 😅"
        )
        return

    if not results:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Actor not found 😅"
        )
        return

    person = results[0]
    person_id = person["id"]
    name = person.get("name", actor_name)
    known = person.get("known_for_department", "Acting")

    details_url = (
        f"https://api.themoviedb.org/3/person/{person_id}"
        f"?api_key={TMDB_API_KEY}"
    )

    credits_url = (
        f"https://api.themoviedb.org/3/person/{person_id}/movie_credits"
        f"?api_key={TMDB_API_KEY}"
    )

    try:
        details = requests.get(details_url, timeout=10).json()
        credits = requests.get(credits_url, timeout=10).json()
    except Exception:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Couldn't fetch actor details 😅"
        )
        return

    birthday = details.get("birthday", "Unknown")
    bio = details.get("biography", "No biography available.")

    movies = credits.get("cast", [])
    movies = sorted(
        movies,
        key=lambda x: x.get("popularity", 0),
        reverse=True,
    )[:5]

    top_movies = ", ".join(
        [m.get("title", "") for m in movies]
    ) or "N/A"

    short_bio = bio[:500]
    if len(bio) > 500:
        short_bio += "..."

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=(
            f"🎭 {name}\n"
            f"🎂 Born: {birthday}\n"
            f"🎬 Known for: {known}\n"
            f"⭐ Popular movies: {top_movies}\n\n"
            f"{short_bio}"
        )
    )
    
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.message.delete()
    except Exception:
        pass

    text = (
        "Commands\n\n"
        "/movie movie name → trailer + info\n"
        "/plot movie name → story/plot\n"
        "/actor actor name → actor details\n"
        "/f name → RIP meme command\n"
        "/vs Movie 1 | Movie 2 → battle poll\n"
        "/start → open menu\n"
        "/help → show commands\n\n"
        "🎭 Buttons also available for genres, voting and suggestions."
    )

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
    )
    
async def meme_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.message.delete()
    except Exception:
        pass

    if not recent_messages:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Chat is too quiet to roast 😴"
        )
        return

    convo = "\n".join(recent_messages[-15:])

    headers = {
        "Authorization": f"Bearer {XAI_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "grok-3-mini",
        "messages": [
            {
                "role": "user",
                "content": (
                    "Make ONE short savage meme line from this chat:\n\n"
                    + convo
                ),
            }
        ],
        "temperature": 1.1,
        "max_tokens": 50,
    }

    try:
        r = requests.post(
            "https://api.x.ai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=20,
        )

        data = r.json()
        print(data)  # debug in Railway logs

        if "choices" in data:
            meme = data["choices"][0]["message"]["content"].strip()
        else:
            meme = "Braincells left the chat ☠️"

    except Exception as e:
        print("MEME ERROR:", e)
        meme = "Collective IQ in freefall 📉"

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=meme,
    )
    
async def warn_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(
        update.effective_chat.id,
        update.effective_user.id,
        context,
    ):
        return

    if not update.message.reply_to_message:
        return

    target = update.message.reply_to_message.from_user
    target_id = target.id

    warns[target_id] = warns.get(target_id, 0) + 1

    if warns[target_id] >= 3:
        until = datetime.now(
            timezone.utc
        ) + timedelta(hours=1)

        await context.bot.restrict_chat_member(
            chat_id=update.effective_chat.id,
            user_id=target_id,
            permissions=ChatPermissions(
                can_send_messages=False
            ),
            until_date=until,
        )

        warns[target_id] = 0

        await update.message.reply_text(
            f"{target.first_name} muted for 1 hour 🔇"
        )
async def member_left(update: Update, context: ContextTypes.DEFAULT_TYPE):
    left_user = update.message.left_chat_member

    if not left_user:
        return

    joined_at = join_times.get(left_user.id)

    if joined_at:
        diff = datetime.now(timezone.utc) - joined_at

        if diff.total_seconds() <= 86400:
            await update.message.reply_text(
                f"{left_user.first_name} left for the milk 🥛"
            )

        del join_times[left_user.id]

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user = update.effective_user
    user_id = user.id
    chat_id = update.effective_chat.id
    text = update.message.text.strip()
    lower = text.lower()

    recent_messages.append(text)

    if len(recent_messages) > 20:
        recent_messages.pop(0)

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
            except Exception:
                pass
            return

    words = re.findall(r"\b\w+\b", lower)

    if any(w in BAD_WORDS for w in words):
        if not await is_admin(chat_id, user_id, context):
            try:
                await update.message.delete()
            except Exception:
                pass
            return

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
                    permissions=ChatPermissions(
                        can_send_messages=False
                    ),
                    until_date=until,
                )
            except Exception:
                pass
            return

    if user_id in waiting_for_movie:
        try:
            url = (
                f"http://www.omdbapi.com/?apikey={OMDB_API_KEY}"
                f"&t={urllib.parse.quote(text)}"
            )

            data = requests.get(url, timeout=10).json()

            if data.get("Response") == "False":
                await update.message.reply_text(
                    "❌ Movie not found.\nSend a valid movie name."
                )
                return

            title = data.get("Title", text)

            if title.lower() in [
                m.lower() for m in movie_suggestions
            ]:
                await update.message.reply_text(
                    "🎬 Already suggested"
                )
            else:
                movie_suggestions.append(title)

                await update.message.reply_text(
                    f"✅ Added: {title}"
                )

            waiting_for_movie.remove(user_id)

        except Exception:
            await update.message.reply_text(
                "Couldn't verify movie 😅"
            )
            waiting_for_movie.remove(user_id)

app = ApplicationBuilder().token(TOKEN).build()

app.job_queue.run_daily(
    auto_daily,
    time=time(hour=14, minute=30, tzinfo=timezone.utc),
)

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("movie", movie_lookup))
app.add_handler(CommandHandler("warn", warn_user))
app.add_handler(CommandHandler("f", f_command))
app.add_handler(CommandHandler("vs", vs_command))
app.add_handler(CommandHandler("plot", plot_command))
app.add_handler(CommandHandler("actor", actor_command))
app.add_handler(CommandHandler("help", help_command))
app.add_handler(CommandHandler("meme", meme_command))
app.add_handler(CallbackQueryHandler(button_handler))
app.add_handler(
    MessageHandler(
        filters.StatusUpdate.NEW_CHAT_MEMBERS,
        welcome,
    )
)
app.add_handler(
    MessageHandler(
        filters.StatusUpdate.LEFT_CHAT_MEMBER,
        member_left,
    )
)
app.add_handler(
    MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_text,
    )
)

print("Bot running 🚀")
app.run_polling()
