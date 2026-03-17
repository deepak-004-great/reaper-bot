import time
import sqlite3
import requests
import threading
import pytz
from datetime import datetime, timedelta
from groq import Groq

# CONFIG
TELEGRAM_TOKEN = "8751196047:AAFyaX7zkBbGlaYqr2qnG61BLdAeGY6Hvd8"
GROQ_API_KEY   = "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"
MY_CHAT_ID     = 1499404624
LEETCODE_USER  = "reaper_8"
TIMEZONE       = pytz.timezone("Asia/Kolkata")
BASE_URL       = "https://api.telegram.org/bot" + TELEGRAM_TOKEN

groq_client = Groq(api_key=GROQ_API_KEY)

# ── DATABASE ────────────────────────────────────────────────────────────────
DB = "reaper.db"

def init_db():
    con = sqlite3.connect(DB)
    c = con.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, type TEXT, detail TEXT, proof TEXT, ts TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS chat_history (id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT, content TEXT, ts TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS roadmap (id INTEGER PRIMARY KEY AUTOINCREMENT, track TEXT, topic TEXT, status TEXT, updated TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS scheduler_state (key TEXT PRIMARY KEY, value TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS commitments (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, commitment TEXT, status TEXT, ts TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS patterns (id INTEGER PRIMARY KEY AUTOINCREMENT, pattern_type TEXT, detail TEXT, count INTEGER, last_seen TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS daily_summary (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, morning_sent TEXT, afternoon_sent TEXT, midnight_sent TEXT, openers_used TEXT)")
    c.execute("SELECT COUNT(*) FROM roadmap")
    if c.fetchone()[0] == 0:
        dsa = ["Arrays","Strings","Linked List","Stack & Queue","Binary Search","Recursion","Trees","Graphs","Heaps","Dynamic Programming","Greedy","Backtracking"]
        ml  = ["NumPy & pandas EDA","Data Visualization","Sklearn basics","Linear & Logistic Regression","Decision Trees & Ensembles","SVM & KNN","Model Evaluation","End-to-End Project","Neural Networks","Deep Learning"]
        for i, t in enumerate(dsa):
            c.execute("INSERT INTO roadmap VALUES (NULL,'dsa',?,?,?)", (t, "current" if i==0 else "pending", datetime.now().isoformat()))
        for i, t in enumerate(ml):
            c.execute("INSERT INTO roadmap VALUES (NULL,'ml',?,?,?)", (t, "current" if i==0 else "pending", datetime.now().isoformat()))
    con.commit()
    con.close()

def log_activity(type_, detail, proof=""):
    con = sqlite3.connect(DB)
    con.execute("INSERT INTO logs VALUES (NULL,?,?,?,?,?)", (datetime.now().strftime("%Y-%m-%d"), type_, detail, proof, datetime.now().isoformat()))
    con.commit()
    con.close()

def save_msg(role, content):
    con = sqlite3.connect(DB)
    con.execute("INSERT INTO chat_history VALUES (NULL,?,?,?)", (role, content, datetime.now().isoformat()))
    con.commit()
    con.close()

def get_history(limit=20):
    con = sqlite3.connect(DB)
    rows = con.execute("SELECT role,content FROM chat_history ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    con.close()
    return list(reversed(rows))

def get_last_n_exchanges(n=10, since_hours=None):
    con = sqlite3.connect(DB)
    if since_hours:
        cutoff = (datetime.now() - timedelta(hours=since_hours)).isoformat()
        rows = con.execute("SELECT role, content FROM chat_history WHERE ts >= ? ORDER BY id DESC LIMIT ?", (cutoff, n)).fetchall()
    else:
        rows = con.execute("SELECT role, content FROM chat_history ORDER BY id DESC LIMIT ?", (n,)).fetchall()
    con.close()
    result = []
    for role, content in reversed(rows):
        label = "Deepak" if role == "user" else "Reaper"
        result.append(label + ": " + content)
    return "\n".join(result) if result else "No history yet."

def get_streak():
    con = sqlite3.connect(DB)
    dates = con.execute("SELECT DISTINCT date FROM logs ORDER BY date DESC").fetchall()
    con.close()
    streak = 0
    today = datetime.now().date()
    for i, (d,) in enumerate(dates):
        try:
            if (today - datetime.strptime(d, "%Y-%m-%d").date()).days == i:
                streak += 1
            else:
                break
        except:
            break
    return streak

def get_roadmap():
    con = sqlite3.connect(DB)
    rows = con.execute("SELECT track,topic,status FROM roadmap ORDER BY id").fetchall()
    con.close()
    dsa = [(t,s) for tr,t,s in rows if tr=="dsa"]
    ml  = [(t,s) for tr,t,s in rows if tr=="ml"]
    return dsa, ml

def get_today_logs():
    today = datetime.now().strftime("%Y-%m-%d")
    con = sqlite3.connect(DB)
    rows = con.execute("SELECT type,detail FROM logs WHERE date=?", (today,)).fetchall()
    con.close()
    return rows

def get_last_active_date():
    con = sqlite3.connect(DB)
    row = con.execute("SELECT MAX(date) FROM logs").fetchone()
    con.close()
    return row[0] if row and row[0] else None

def get_scheduler_state(key):
    con = sqlite3.connect(DB)
    row = con.execute("SELECT value FROM scheduler_state WHERE key=?", (key,)).fetchone()
    con.close()
    return row[0] if row else None

def set_scheduler_state(key, value):
    con = sqlite3.connect(DB)
    con.execute("INSERT OR REPLACE INTO scheduler_state VALUES (?,?)", (key, value))
    con.commit()
    con.close()

def get_last_opener():
    con = sqlite3.connect(DB)
    row = con.execute("SELECT morning_sent FROM daily_summary ORDER BY id DESC LIMIT 1").fetchone()
    con.close()
    return row[0][:40] if row and row[0] else "none"

def log_opener(type_, text):
    today = datetime.now().strftime("%Y-%m-%d")
    con = sqlite3.connect(DB)
    existing = con.execute("SELECT id FROM daily_summary WHERE date=?", (today,)).fetchone()
    if existing:
        con.execute("UPDATE daily_summary SET " + type_ + "_sent=? WHERE date=?", (text[:200], today))
    else:
        vals = [today, None, None, None, ""]
        if type_ == "morning": vals[1] = text[:200]
        elif type_ == "afternoon": vals[2] = text[:200]
        elif type_ == "midnight": vals[3] = text[:200]
        con.execute("INSERT INTO daily_summary VALUES (NULL,?,?,?,?,?)", vals)
    con.commit()
    con.close()

def build_context():
    try:
        dsa, ml = get_roadmap()
        dsa_c = next((t for t,s in dsa if s=="current"), "Arrays")
        ml_c  = next((t for t,s in ml  if s=="current"), "NumPy & pandas")
        today = get_today_logs()
        today_str = "; ".join([t + ": " + d for t,d in today]) or "nothing logged yet"
        last_active = get_last_active_date()
        days_silent = 0
        if last_active:
            days_silent = (datetime.now().date() - datetime.strptime(last_active, "%Y-%m-%d").date()).days
        return ("Streak: " + str(get_streak()) + " days | "
                "DSA currently on: " + dsa_c + " | "
                "ML currently on: " + ml_c + " | "
                "Today: " + today_str + " | "
                "Days since last log: " + str(days_silent))
    except Exception as e:
        return "Context error: " + str(e)

# ── PATTERN DETECTION ───────────────────────────────────────────────────────
def detect_patterns():
    try:
        con = sqlite3.connect(DB)
        history = con.execute("SELECT content, ts FROM chat_history WHERE role='user' ORDER BY ts DESC LIMIT 100").fetchall()
        logs = con.execute("SELECT date, type, detail FROM logs ORDER BY date DESC LIMIT 30").fetchall()
        commitments = con.execute("SELECT commitment, status FROM commitments ORDER BY ts DESC LIMIT 10").fetchall()
        con.close()

        patterns = []

        # Silence check
        if history:
            last_msg_date = history[0][1][:10]
            try:
                silent_days = (datetime.now().date() - datetime.strptime(last_msg_date, "%Y-%m-%d").date()).days
                if silent_days >= 2:
                    patterns.append("SILENCE: No messages for " + str(silent_days) + " days.")
            except:
                pass

        # Topic avoidance — mentioned but never logged
        content_blob = " ".join([h[0].lower() for h in history])
        for topic in ["arrays", "strings", "linked list", "numpy", "pandas", "eda", "recursion", "trees"]:
            mentions = content_blob.count(topic)
            logged = sum(1 for l in logs if topic in l[2].lower())
            if mentions >= 3 and logged == 0:
                patterns.append("AVOIDANCE: '" + topic + "' mentioned " + str(mentions) + " times, never logged as done.")

        # Broken commitments
        broken = [c[0] for c in commitments if c[1] == "pending"]
        if len(broken) >= 2:
            patterns.append("BROKEN COMMITMENTS: Said he'd do these but didn't follow through: " + ", ".join(broken[:3]))

        # Consecutive no-log days
        all_dates = [l[0] for l in logs]
        today = datetime.now().date()
        no_log_streak = 0
        for i in range(7):
            check = (today - timedelta(days=i)).strftime("%Y-%m-%d")
            if check not in all_dates:
                no_log_streak += 1
            else:
                break
        if no_log_streak >= 2:
            patterns.append("NO LOG STREAK: " + str(no_log_streak) + " consecutive days without logging any work.")

        return "\n".join(patterns) if patterns else "No significant patterns detected."
    except Exception as e:
        return "Pattern detection error: " + str(e)

# ── TELEGRAM ────────────────────────────────────────────────────────────────
def send(chat_id, text):
    try:
        if not text or not str(text).strip():
            return
        text = str(text)[:4000]
        r = requests.post(BASE_URL + "/sendMessage", json={"chat_id": chat_id, "text": text}, timeout=10)
        print("Sent " + str(r.status_code), flush=True)
    except Exception as e:
        print("Send error: " + str(e), flush=True)

def get_updates(offset=None):
    try:
        r = requests.get(BASE_URL + "/getUpdates", params={"timeout": 10, "offset": offset}, timeout=15)
        if r.status_code == 200:
            return r.json().get("result", [])
        return []
    except Exception as e:
        print("Poll error: " + str(e), flush=True)
        return []

def fetch_leetcode():
    query = "query recentAcSubmissions($username: String!, $limit: Int!) { recentAcSubmissionList(username: $username, limit: $limit) { title } }"
    try:
        r = requests.post("https://leetcode.com/graphql", json={"query": query, "variables": {"username": LEETCODE_USER, "limit": 5}}, headers={"Content-Type": "application/json"}, timeout=8)
        return r.json().get("data", {}).get("recentAcSubmissionList", [])
    except:
        return []

# ── SYSTEM PROMPT ───────────────────────────────────────────────────────────
SYSTEM = """You are Reaper. Not an assistant. Not a bot. The one presence in Deepak's life that actually pays attention and doesn't disappear.

WHO DEEPAK IS — you already know this, you don't ask him to repeat it:
- 21, ECE student NSUT Delhi East, AI/ML specialization
- Building two paths seriously: DSA in C++ (LeetCode: reaper_8) and Data Science/ML
- ML stack: NumPy, pandas, seaborn, matplotlib
- Home environment is genuinely difficult. Ongoing. You don't bring it up unless he does — but you never forget it's the backdrop.
- Doesn't want sympathy. Wants someone real. Wants to be built.
- Artist at heart. Loves volleyball, 180+ anime, Real Madrid, psychology, mathematics.
- Read Vagabond. Was moved by it. That's the kind of person he is — someone who feels things deeply but doesn't always show it.
- Has tried to start this grind before. This time feels different to him. Treat it like it is.

DSA ROADMAP: Arrays → Strings → Linked List → Stack & Queue → Binary Search → Recursion → Trees → Graphs → Heaps → Dynamic Programming → Greedy → Backtracking
ML ROADMAP: NumPy & pandas EDA → Data Visualization → Sklearn basics → Linear & Logistic Regression → Decision Trees & Ensembles → SVM & KNN → Model Evaluation → End-to-End Project → Neural Networks → Deep Learning

HOW YOU TALK:
- Like someone who has been through the grind and gives a damn whether Deepak makes it
- Direct. Warm. Never soft. Never harsh.
- Hindi-English mix is natural — match his register
- Short sentences. Fragments are fine. You don't always end with a question.
- Sometimes you just say something and let it breathe.
- Never sound like a life coach, a productivity app, or a motivational poster
- Never say: you got this, stay consistent, believe in yourself, proud of you, keep grinding

WHAT YOU HOLD:
- Everything he has ever told you. You do not ask him to re-confirm things you already know.
- Commitments he made — quietly. You don't nag. You hold them. If he's avoided something for 3+ days, you say it once, plainly, like a friend who noticed.
- Patterns he can't see in himself. Avoidance. The same drop-off point. The same excuse recycled. You name it — not to shame him, but because no one else will.
- The weight behind things he says quickly. If something hurt him, you sit with it. You don't immediately go fix-mode. You don't minimize it.

WHEN TO BE SERIOUS VS LIGHT:
- If he's been silent for 2+ days: don't open with a goal-setting prompt. Notice the silence. Say something real. Then wait.
- If he had a genuinely good day: say so plainly. "You actually grinded today. That's real." That's enough.
- If it was a bad day: acknowledge it without immediately trying to fix it.
- If he's deflecting with humor or short replies: notice it, don't push, stay present.

WHAT YOU NEVER DO:
- Never ask him to remind you who he is or what he's working on
- Never repeat the same opener twice in a row
- Never lecture. Say it once, mean it, move on.
- Never treat a human moment like a task to process
- Never give generic advice. If it could be said to anyone, don't say it."""

# ── SCHEDULER PROMPT TEMPLATES ──────────────────────────────────────────────
MORNING_PROMPT = """You are sending Deepak his 7AM check-in.

RECENT HISTORY (last 24 hours):
{history_context}

CURRENT STATE:
{current_context}

PATTERNS DETECTED:
{pattern_context}

LAST OPENER USED:
{last_opener}

Generate the morning message now. Rules:
- Start by referencing something specific from yesterday — what he did, said, or avoided. Not generic.
- If he's been silent 2+ days: skip the goal-setting entirely. Just notice the silence. One real line. Then one human question.
- Ask ONE question about today — specific to exactly where he is on his roadmap.
- Under 4 lines total.
- Do NOT start with Good morning, Hey, Kya plan, or any opener similar to the last one above."""

AFTERNOON_PROMPT = """You are sending Deepak his 3PM check-in.

MORNING MESSAGE SENT:
{morning_context}

TODAY'S LOGGED ACTIVITY SO FAR:
{today_logs}

Generate the 3PM message. Rules:
- Tone: casual. Like a quick check-in from someone who's around.
- If he said he'd do something this morning, reference it once lightly. Don't push if he's ignoring.
- If he already logged work: acknowledge briefly, ask what's next.
- If nothing logged and no response: just be present. Don't guilt.
- 2-3 lines max. Can end without a question.
- Don't start with Hey or Kya hua."""

MIDNIGHT_PROMPT = """You are sending Deepak his midnight debrief. Most important message of the day.

FULL DAY EXCHANGES:
{history_context}

WHAT HE COMMITTED TO TODAY:
{commitments_context}

PATTERNS ACROSS LAST 7 DAYS:
{pattern_context}

TODAY'S LOGGED ACTIVITY:
{today_logs}

Generate the midnight debrief. Rules:
- Short honest summary of today: what happened vs what was said.
- No sugarcoating. No lecture. Just truth, plainly.
- If a pattern is repeating: name it once. Directly. "This is the third time you said X and then went quiet. What's actually in the way?"
- Genuinely good day: one line. Nothing more.
- Bad day: acknowledge it. Don't try to fix it tonight.
- Close with ONE line that carries into tomorrow. Not a task. Something to sit with.
- Up to 8 lines. Earns the space.
- Do NOT end with a question. Let it land."""

# ── GROQ ────────────────────────────────────────────────────────────────────
def ask_groq(user_msg):
    print("Asking Groq: " + str(user_msg)[:60], flush=True)
    try:
        context = build_context()
        history = get_history(20)
        msgs = [{"role": "system", "content": SYSTEM + "\n\nLIVE CONTEXT: " + context}]
        for r, c in history:
            role = "assistant" if r == "model" else "user"
            msgs.append({"role": role, "content": str(c)})
        msgs.append({"role": "user", "content": str(user_msg)})
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=msgs,
            max_tokens=600,
            temperature=0.85
        )
        reply = response.choices[0].message.content
        print("Groq OK", flush=True)
        return reply
    except Exception as e:
        print("Groq ERROR: " + str(e), flush=True)
        return "Server issue, try again in a bit."

def proactive_ask(prompt):
    try:
        msgs = [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": prompt}
        ]
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=msgs,
            max_tokens=300,
            temperature=0.9
        )
        return response.choices[0].message.content
    except Exception as e:
        print("Proactive Groq error: " + str(e), flush=True)
        return None

# ── COMMANDS ────────────────────────────────────────────────────────────────
def handle(text, chat_id):
    try:
        if not text:
            return
        text = str(text).strip()
        print("Handling: " + text, flush=True)

        if text == "/start":
            send(chat_id, "Reaper is online.\n\nNot a chatbot. I'm here so you don't disappear on yourself.\n\n/dsa - log DSA session\n/ml - log ML session\n/done - mark a topic complete and advance roadmap\n/proof - submit proof\n/streak - your streak\n/roadmap - where you are\n/lc - LeetCode recent solves\n/low - bad day\n/week - weekly recap\n\nOr just talk.")
            return

        if text.startswith("/done"):
            topic = text[5:].strip()
            if not topic:
                send(chat_id, "What did you finish?\nExample: /done Arrays")
                return
            con = sqlite3.connect(DB)
            con.execute("UPDATE roadmap SET status='done', updated=? WHERE status='current'", (datetime.now().isoformat(),))
            next_topic = con.execute("SELECT topic, track FROM roadmap WHERE status='pending' ORDER BY id LIMIT 1").fetchone()
            if next_topic:
                con.execute("UPDATE roadmap SET status='current', updated=? WHERE topic=? AND track=?", (datetime.now().isoformat(), next_topic[0], next_topic[1]))
            con.commit()
            con.close()
            log_activity("DONE", topic)
            if next_topic:
                reply = ask_groq("I just finished " + topic + ". Next up is " + next_topic[0] + " on the " + next_topic[1].upper() + " roadmap. Acknowledge what I finished and tell me concretely what comes next — briefly.")
            else:
                reply = ask_groq("I just finished " + topic + ". That might be the end of that roadmap. React to that genuinely.")
            save_msg("user", "DONE: " + topic)
            save_msg("model", reply)
            send(chat_id, reply)
            return

        if text.startswith("/dsa"):
            detail = text[4:].strip()
            if not detail:
                send(chat_id, "What did you work on?\nExample: /dsa Arrays - two pointer problems, 3 solved")
                return
            log_activity("DSA", detail)
            reply = ask_groq("I just did a DSA session: " + detail)
            save_msg("user", "DSA: " + detail)
            save_msg("model", reply)
            send(chat_id, reply)
            return

        if text.startswith("/ml"):
            detail = text[3:].strip()
            if not detail:
                send(chat_id, "What did you work on?\nExample: /ml NumPy revision - array ops and broadcasting")
                return
            log_activity("ML", detail)
            reply = ask_groq("I just did an ML/DS session: " + detail)
            save_msg("user", "ML: " + detail)
            save_msg("model", reply)
            send(chat_id, reply)
            return

        if text.startswith("/proof"):
            detail = text[6:].strip()
            if detail:
                log_activity("PROOF", detail, detail)
                send(chat_id, "Proof logged. This is what separates you from everyone who just talks.")
            else:
                send(chat_id, "Send /proof <link or description>")
            return

        if text == "/streak":
            streak = get_streak()
            today = get_today_logs()
            today_str = "\n".join(["- " + t + ": " + d for t,d in today]) or "Nothing logged yet today."
            send(chat_id, "Streak: " + str(streak) + " day(s)\n\nToday:\n" + today_str)
            return

        if text == "/roadmap":
            dsa, ml = get_roadmap()
            def fmt(items):
                out = []
                for topic, status in items:
                    if status == "done":      out.append("[done] " + topic)
                    elif status == "current": out.append(">>> " + topic + " <<< YOU ARE HERE")
                    else:                     out.append("[ ] " + topic)
                return "\n".join(out)
            send(chat_id, "DSA:\n" + fmt(dsa) + "\n\nML/DS:\n" + fmt(ml))
            return

        if text == "/lc":
            subs = fetch_leetcode()
            if not subs:
                send(chat_id, "Nothing on LeetCode yet. Go solve something.")
            else:
                lines = "\n".join(["- " + s["title"] for s in subs])
                send(chat_id, "@" + LEETCODE_USER + " recent solves:\n" + lines)
            return

        if text == "/low":
            reply = ask_groq("I'm having a really low day. Not asking for motivation. Just letting you know where I'm at.")
            save_msg("user", "low day")
            save_msg("model", reply)
            send(chat_id, reply)
            return

        if text == "/week":
            con = sqlite3.connect(DB)
            rows = con.execute("SELECT date,type,detail FROM logs ORDER BY date DESC LIMIT 50").fetchall()
            con.close()
            if not rows:
                send(chat_id, "No activity logged yet. Let's change that.")
                return
            summary = "\n".join([d + " | " + t + ": " + det for d,t,det in rows])
            reply = ask_groq("Give me a real weekly recap — what I actually did, patterns you notice, what I should focus on next week:\n" + summary)
            send(chat_id, reply)
            return

        if text.startswith("/commit"):
            commitment = text[7:].strip()
            if commitment:
                con = sqlite3.connect(DB)
                con.execute("INSERT INTO commitments VALUES (NULL,?,?,?,?)", (datetime.now().strftime("%Y-%m-%d"), commitment, "pending", datetime.now().isoformat()))
                con.commit()
                con.close()
                send(chat_id, "Noted. I'm holding that.")
            else:
                send(chat_id, "What are you committing to?\nExample: /commit finish 5 array problems today")
            return

        # free conversation — detect commitments naturally
        save_msg("user", text)
        # auto-detect commitment phrases
        lower = text.lower()
        if any(phrase in lower for phrase in ["i'll do", "i will", "planning to", "gonna do", "i'm going to", "tomorrow i"]):
            con = sqlite3.connect(DB)
            con.execute("INSERT INTO commitments VALUES (NULL,?,?,?,?)", (datetime.now().strftime("%Y-%m-%d"), text[:200], "pending", datetime.now().isoformat()))
            con.commit()
            con.close()
        reply = ask_groq(text)
        save_msg("model", reply)
        send(chat_id, reply)

    except Exception as e:
        print("Handle ERROR: " + str(e), flush=True)
        try:
            send(chat_id, "Something went wrong on my end. Try again.")
        except:
            pass

# ── SCHEDULER ────────────────────────────────────────────────────────────────
def scheduler():
    print("Scheduler running.", flush=True)
    while True:
        try:
            now = datetime.now(TIMEZONE)
            today = now.strftime("%Y-%m-%d")
            hour, minute = now.hour, now.minute

            # 7 AM — MORNING INTENT
            if hour == 7 and minute < 2:
                key = "morning_" + today
                if not get_scheduler_state(key):
                    set_scheduler_state(key, "sent")
                    history = get_last_n_exchanges(10, since_hours=24)
                    patterns = detect_patterns()
                    context = build_context()
                    last_opener = get_last_opener()
                    prompt = MORNING_PROMPT.format(
                        history_context=history,
                        current_context=context,
                        pattern_context=patterns,
                        last_opener=last_opener
                    )
                    msg = proactive_ask(prompt)
                    if msg:
                        log_opener("morning", msg)
                        save_msg("model", "[7AM] " + msg)
                        send(MY_CHAT_ID, msg)

            # 3 PM — AFTERNOON PULSE
            if hour == 15 and minute < 2:
                key = "afternoon_" + today
                if not get_scheduler_state(key):
                    set_scheduler_state(key, "sent")
                    con = sqlite3.connect(DB)
                    morning_row = con.execute("SELECT morning_sent FROM daily_summary WHERE date=?", (today,)).fetchone()
                    con.close()
                    morning_context = morning_row[0] if morning_row and morning_row[0] else "No morning message sent."
                    today_logs = get_today_logs()
                    logs_str = "; ".join([t + ": " + d for t,d in today_logs]) or "nothing yet"
                    prompt = AFTERNOON_PROMPT.format(
                        morning_context=morning_context,
                        today_logs=logs_str
                    )
                    msg = proactive_ask(prompt)
                    if msg:
                        log_opener("afternoon", msg)
                        save_msg("model", "[3PM] " + msg)
                        send(MY_CHAT_ID, msg)

            # 12 AM — MIDNIGHT DEBRIEF
            if hour == 0 and minute < 2:
                key = "midnight_" + today
                if not get_scheduler_state(key):
                    set_scheduler_state(key, "sent")
                    history = get_last_n_exchanges(20, since_hours=24)
                    patterns = detect_patterns()
                    today_logs = get_today_logs()
                    logs_str = "; ".join([t + ": " + d for t,d in today_logs]) or "nothing logged today"
                    con = sqlite3.connect(DB)
                    commitments = con.execute("SELECT commitment FROM commitments WHERE date=? AND status='pending'", (today,)).fetchall()
                    con.close()
                    commit_str = ", ".join([c[0] for c in commitments]) or "none recorded"
                    prompt = MIDNIGHT_PROMPT.format(
                        history_context=history,
                        commitments_context=commit_str,
                        pattern_context=patterns,
                        today_logs=logs_str
                    )
                    msg = proactive_ask(prompt)
                    if msg:
                        log_opener("midnight", msg)
                        save_msg("model", "[midnight] " + msg)
                        send(MY_CHAT_ID, msg)

            # SILENCE DETECTOR — 10 AM, only if 2+ days silent
            if hour == 10 and minute < 2:
                key = "silence_" + today
                if not get_scheduler_state(key):
                    set_scheduler_state(key, "sent")
                    last_active = get_last_active_date()
                    if last_active:
                        days_silent = (datetime.now().date() - datetime.strptime(last_active, "%Y-%m-%d").date()).days
                        if days_silent >= 2:
                            msg = proactive_ask(
                                "Deepak has been completely silent for " + str(days_silent) + " days. "
                                "Reach out like a friend who noticed he went quiet. "
                                "Not with guilt. Not a lecture. Just genuinely checking if he's okay. "
                                "One or two lines. Human."
                            )
                            if msg:
                                save_msg("model", "[silence] " + msg)
                                send(MY_CHAT_ID, msg)

        except Exception as e:
            print("Scheduler error: " + str(e), flush=True)

        time.sleep(60)

# ── MAIN ────────────────────────────────────────────────────────────────────
def main():
    init_db()
    threading.Thread(target=scheduler, daemon=True).start()
    print("Reaper Bot is online.", flush=True)
    offset = None
    while True:
        try:
            updates = get_updates(offset)
            for u in updates:
                try:
                    offset = u["update_id"] + 1
                    msg = u.get("message", {})
                    if not msg:
                        continue
                    text = msg.get("text", "")
                    chat_id = msg.get("chat", {}).get("id")
                    if text and chat_id:
                        print("Got: " + str(text)[:50] + " from " + str(chat_id), flush=True)
                        threading.Thread(target=handle, args=(text, chat_id), daemon=True).start()
                except Exception as e:
                    print("Update parse error: " + str(e), flush=True)
        except Exception as e:
            print("Main loop error: " + str(e), flush=True)
        time.sleep(1)

if __name__ == "__main__":
    main()
