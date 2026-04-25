from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions
from telegram.ext import (
    ApplicationBuilder, MessageHandler, CommandHandler,
    CallbackQueryHandler, ContextTypes, filters
)
import asyncio, os, re, requests, urllib.parse, random
from datetime import datetime, time, timezone, timedelta

TOKEN = os.getenv("TOKEN")
OMDB_API_KEY = os.getenv("OMDB_API_KEY")
TMDB_API_KEY = os.getenv("TMDB_API_KEY")

if not TOKEN or not OMDB_API_KEY or not TMDB_API_KEY:
    raise ValueError("Missing environment variables")

movie_suggestions = []
waiting_for_movie = set()
warns = {}
user_message_times = {}
GROUP_CHAT_ID = None

BAD_WORDS = {"fuck","bitch","shit","mc","bc","madarchod","behenchod","gandu","chutiya"}

DAILY_QUESTIONS = [
    "🎬 Best movie sequel ever?",
    "🍿 Most underrated movie?",
    "😱 Best thriller?",
    "😂 Funniest movie?",
    "❤️ Best romance?",
    "🔥 Best actor?",
    "🎥 Movie you'd rewatch fresh?"
]

GENRE_MAP = {
    "comedy":35,"action":28,"horror":27,
    "romance":10749,"scifi":878,"drama":18
}

recent_genre = {k:[] for k in ["comedy","action","horror","romance","scifi","drama","random"]}


async def is_admin(chat_id,user_id,context):
    m = await context.bot.get_chat_member(chat_id,user_id)
    return m.status in ["administrator","creator"]


async def start(update:Update,context:ContextTypes.DEFAULT_TYPE):
    global GROUP_CHAT_ID
    GROUP_CHAT_ID = update.effective_chat.id

   kb = [
    [
        InlineKeyboardButton("Comedy", callback_data="g_comedy"),
        InlineKeyboardButton("Action", callback_data="g_action"),
    ],
    [
        InlineKeyboardButton("Horror", callback_data="g_horror"),
        InlineKeyboardButton("Romance", callback_data="g_romance"),
    ],
    [
        InlineKeyboardButton("Sci-Fi", callback_data="g_scifi"),
        InlineKeyboardButton("Drama", callback_data="g_drama"),
    ],
    [
        InlineKeyboardButton("Random", callback_data="g_random"),
    ],
]
    await update.message.reply_text("Choose:",reply_markup=InlineKeyboardMarkup(kb))


async def welcome(update:Update,context:ContextTypes.DEFAULT_TYPE):
    for u in update.message.new_chat_members:
        msg = await update.message.reply_text(
            f"Welcome {u.first_name}! 🎬\nIntroduce yourself!"
        )
        await asyncio.sleep(20)
        try: await msg.delete()
        except: pass


def fetch_movies(genre):
    gid = random.choice(list(GENRE_MAP.values())) if genre=="random" else GENRE_MAP[genre]
    page = random.randint(1,10)

    url = f"https://api.themoviedb.org/3/discover/movie?api_key={TMDB_API_KEY}&with_genres={gid}&vote_average.gte=6.8&vote_count.gte=300&with_original_language=en&page={page}"
    data = requests.get(url).json().get("results",[])

    fresh = [m for m in data if m["id"] not in recent_genre[genre]]

    if len(fresh)<5:
        recent_genre[genre]=[]
        return fetch_movies(genre)

    picks = random.sample(fresh,5)
    recent_genre[genre]+= [m["id"] for m in picks]
    return picks


async def send_genre(query,genre):
    movies = fetch_movies(genre)

    txt = f"🎬 {genre.title()} Picks\n\n"
    for i,m in enumerate(movies,1):
        link = "https://www.youtube.com/results?search_query=" + urllib.parse.quote(m["title"]+" trailer")
        year = m["release_date"][:4] if m.get("release_date") else ""
        txt += f"{i}. <a href='{link}'>{m['title']} ({year})</a>\n"

    await query.message.reply_text(txt,parse_mode="HTML",disable_web_page_preview=True)


async def movie(update:Update,context:ContextTypes.DEFAULT_TYPE):
    name = " ".join(context.args)
    if not name:
        await update.message.reply_text("Usage: /movie name")
        return

    url = f"http://www.omdbapi.com/?apikey={OMDB_API_KEY}&t={urllib.parse.quote(name)}"
    data = requests.get(url).json()

    if data.get("Response")=="False":
        await update.message.reply_text("Not found")
        return

    trailer = "https://www.youtube.com/results?search_query="+urllib.parse.quote(data["Title"]+" trailer")

    await update.message.reply_text(
        f"🎬 {data['Title']} ({data['Year']})\n⭐ {data['imdbRating']}\n{data['Plot']}",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("▶ Trailer",url=trailer)]])
    )


async def button(update:Update,context:ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    d = q.data

    if d=="rules":
        await q.message.reply_text("Respect everyone. No spam. No abuse.")

    elif d=="suggest":
        waiting_for_movie.add(q.from_user.id)
        await q.message.reply_text("Send movie name")

    elif d=="vote":
        if not movie_suggestions:
            await q.message.reply_text("No suggestions")
            return
        await q.message.reply_poll("Pick movie",movie_suggestions[:9]+["NOTA"])

    elif d=="daily":
        await q.message.reply_text(random.choice(DAILY_QUESTIONS))

    elif d=="genre":
        kb = [
            [InlineKeyboardButton("Comedy","g_comedy"),InlineKeyboardButton("Action","g_action")],
            [InlineKeyboardButton("Horror","g_horror"),InlineKeyboardButton("Romance","g_romance")],
            [InlineKeyboardButton("Sci-Fi","g_scifi"),InlineKeyboardButton("Drama","g_drama")],
            [InlineKeyboardButton("Random","g_random")]
        ]
        await q.message.reply_text("Pick genre",reply_markup=InlineKeyboardMarkup(kb))

    elif d.startswith("g_"):
        await send_genre(q,d.split("_")[1])


async def warn(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_chat.id,update.effective_user.id,context):
        return

    if not update.message.reply_to_message:
        return

    t = update.message.reply_to_message.from_user
    warns[t.id]=warns.get(t.id,0)+1

    if warns[t.id]>=3:
        until = datetime.now(timezone.utc)+timedelta(hours=1)
        await context.bot.restrict_chat_member(update.effective_chat.id,t.id,ChatPermissions(can_send_messages=False),until)
        warns[t.id]=0


async def handle(update:Update,context:ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.lower()
    uid = update.effective_user.id

    if any(x in txt for x in ["t.me","bit.ly","discord.gg"]):
        if not await is_admin(update.effective_chat.id,uid,context):
            await update.message.delete()
            return

    if any(w in txt for w in BAD_WORDS):
        if not await is_admin(update.effective_chat.id,uid,context):
            await update.message.delete()
            return

    if uid in waiting_for_movie:
        if txt not in movie_suggestions:
            movie_suggestions.append(txt)
            await update.message.reply_text(f"Added: {txt}")
        waiting_for_movie.remove(uid)


async def auto_q(context:ContextTypes.DEFAULT_TYPE):
    if GROUP_CHAT_ID:
        await context.bot.send_message(GROUP_CHAT_ID,random.choice(DAILY_QUESTIONS))


app = ApplicationBuilder().token(TOKEN).build()

app.job_queue.run_daily(auto_q,time=time(hour=14,minute=30,tzinfo=timezone.utc))

app.add_handler(CommandHandler("start",start))
app.add_handler(CommandHandler("movie",movie))
app.add_handler(CommandHandler("warn",warn))
app.add_handler(CallbackQueryHandler(button))
app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS,welcome))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,handle))

print("Bot running 🚀")
app.run_polling()
