import time
import sqlite3
import requests
import threading
import pytz
import random
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

# DATABASE
DB = "reaper.db"

def init_db():
    con = sqlite3.connect(DB)
    c = con.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, type TEXT, detail TEXT, proof TEXT, ts TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS chat_history (id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT, content TEXT, ts TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS roadmap (id INTEGER PRIMARY KEY AUTOINCREMENT, track TEXT, topic TEXT, status TEXT, updated TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS scheduler_state (key TEXT PRIMARY KEY, value TEXT)")
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

# TELEGRAM
def send(chat_id, text):
    try:
        if not text or not str(text).strip():
            return
        text = str(text)[:4000]
        r = requests.post(BASE_URL + "/sendMessage", json={"chat_id": chat_id, "text": text}, timeout=10)
        print("Sent " + str(len(text)) + " chars: " + str(r.status_code), flush=True)
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

# LEETCODE
def fetch_leetcode():
    query = "query recentAcSubmissions($username: String!, $limit: Int!) { recentAcSubmissionList(username: $username, limit: $limit) { title } }"
    try:
        r = requests.post("https://leetcode.com/graphql", json={"query": query, "variables": {"username": LEETCODE_USER, "limit": 5}}, headers={"Content-Type": "application/json"}, timeout=8)
        data = r.json()
        return data.get("data", {}).get("recentAcSubmissionList", [])
    except:
        return []

# SYSTEM PROMPT
SYSTEM = """You are Reaper. Deepak's accountability partner, senior, and the one presence that doesn't let him disappear on himself. You are not a bot or assistant. You are someone who genuinely gives a damn about this person.

WHO DEEPAK IS:
- 21 years old, ECE student at NSUT Delhi East, AI/ML specialization
- Building two serious paths: DSA in C++ (LeetCode: reaper_8) and Data Science/ML
- ML stack already has: NumPy, pandas, seaborn, matplotlib
- Starting DSA fresh from Arrays. Starting ML from NumPy/pandas EDA revision.
- Lives in a genuinely difficult home environment. Ongoing, daily reality. Not past history.
- Does NOT want sympathy. Does NOT want feelings-talk unless he brings it up.
- Wants to be built. Wants someone real in his corner.
- Artist at heart, loves volleyball, 180+ anime watched, Real Madrid fan, deeply drawn to psychology and math
- Read Vagabond and was moved by it. That tells you who he is at his core.

DSA ROADMAP: Arrays -> Strings -> Linked List -> Stack & Queue -> Binary Search -> Recursion -> Trees -> Graphs -> Heaps -> Dynamic Programming -> Greedy -> Backtracking

ML/DS ROADMAP: NumPy & pandas EDA -> Data Visualization -> Sklearn basics -> Linear & Logistic Regression -> Decision Trees & Ensembles -> SVM & KNN -> Model Evaluation -> End-to-End Project -> Neural Networks -> Deep Learning

HOW YOU TALK:
- Like a senior who has been through the grind and genuinely wants Deepak to make it
- Direct. Warm. Zero motivational poster garbage. Never say: you got this, believe in yourself, stay consistent, keep grinding
- Hindi-English mix is completely fine. Match his energy and tone.
- Short punchy replies in casual conversation. Go longer only when teaching or debugging.
- When he logs work: react to what he actually did, not just acknowledge it
- When he is low: one real line of acknowledgment, then gently pull toward one small concrete action
- When he slips or goes quiet: call it out honestly, no lecture, no guilt trip
- When he shares code or an error: actually debug it, ask clarifying questions, don't just explain theory
- When he solves something hard: be genuinely happy, not performative
- When he asks what to study next: know his exact roadmap position and give him the next concrete thing
- Reference things he told you before. You remember. You are continuous.
- Never bullet point lists in casual conversation. Talk like a human.
- Never be a yes-man. Push back when he is making excuses.
- Never give generic advice. Everything must feel specifically for Deepak."""

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
                "Days since last logged activity: " + str(days_silent))
    except Exception as e:
        return "Context unavailable: " + str(e)

# GROQ
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
        return "Server side issue, try again in a bit."

# PROACTIVE MESSAGES - called by scheduler
def proactive_ask(prompt):
    try:
        context = build_context()
        msgs = [
            {"role": "system", "content": SYSTEM + "\n\nLIVE CONTEXT: " + context},
            {"role": "user", "content": prompt}
        ]
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=msgs,
            max_tokens=200,
            temperature=0.9
        )
        return response.choices[0].message.content
    except Exception as e:
        return None

# COMMANDS
def handle(text, chat_id):
    try:
        if not text:
            return
        text = str(text).strip()
        print("Handling: " + text, flush=True)

        if text == "/start":
            send(chat_id, "Reaper is online.\n\nNot a chatbot. I'm here so you don't disappear on yourself.\n\n/dsa - log DSA session\n/ml - log ML session\n/proof - submit proof\n/streak - your streak\n/roadmap - where you are\n/lc - LeetCode recent solves\n/low - bad day\n/week - weekly recap\n\nOr just talk.")
            return

        if text.startswith("/dsa"):
            detail = text[4:].strip()
            if not detail:
                send(chat_id, "What did you work on?\nExample: /dsa Arrays - two pointer, 3 problems solved")
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
                send(chat_id, "What did you work on?\nExample: /ml EDA on Titanic, handled missing values and plotted distributions")
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
                send(chat_id, "Send /proof <link or description of what you built>")
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
                    if status == "done":
                        out.append("[done] " + topic)
                    elif status == "current":
                        out.append(">>> " + topic + " <<< YOU ARE HERE")
                    else:
                        out.append("[ ] " + topic)
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

        # free conversation
        save_msg("user", text)
        reply = ask_groq(text)
        save_msg("model", reply)
        send(chat_id, reply)

    except Exception as e:
        print("Handle ERROR: " + str(e), flush=True)
        try:
            send(chat_id, "Something went wrong on my end. Try again.")
        except:
            pass

# SCHEDULER - the proactive care system
def scheduler():
    print("Scheduler started.", flush=True)
    while True:
        try:
            now = datetime.now(TIMEZONE)
            today = now.strftime("%Y-%m-%d")
            hour = now.hour
            minute = now.minute

            # MORNING CHECK-IN — 8:00 AM
            if hour == 8 and minute < 2:
                key = "morning_" + today
                if not get_scheduler_state(key):
                    set_scheduler_state(key, "sent")
                    dsa, ml = get_roadmap()
                    dsa_c = next((t for t,s in dsa if s=="current"), "Arrays")
                    ml_c  = next((t for t,s in ml  if s=="current"), "NumPy & pandas")
                    msg = proactive_ask(
                        "Send Deepak a morning check-in. "
                        "Streak is " + str(get_streak()) + " days. "
                        "His DSA focus today is " + dsa_c + " and ML is " + ml_c + ". "
                        "Keep it short, direct, no fluff. Ask what he is targeting today."
                    )
                    if msg:
                        send(MY_CHAT_ID, msg)

            # MIDDAY NUDGE — 1:00 PM — only if nothing logged yet today
            if hour == 13 and minute < 2:
                key = "midday_" + today
                if not get_scheduler_state(key):
                    set_scheduler_state(key, "sent")
                    today_logs = get_today_logs()
                    if not today_logs:
                        msg = proactive_ask(
                            "It's 1PM and Deepak hasn't logged anything yet today. "
                            "Send a short, natural check-in — not pushy, not a lecture. "
                            "Just checking in like a friend would."
                        )
                        if msg:
                            send(MY_CHAT_ID, msg)

            # EVENING ACCOUNTABILITY — 9:30 PM
            if hour == 21 and minute >= 30 and minute < 32:
                key = "evening_" + today
                if not get_scheduler_state(key):
                    set_scheduler_state(key, "sent")
                    logs = get_today_logs()
                    if logs:
                        done = ", ".join([t + ": " + d for t,d in logs])
                        msg = proactive_ask(
                            "Evening check. Deepak logged: " + done + ". "
                            "React to what he actually did today — briefly acknowledge it, "
                            "ask if proof was submitted, and hint at tomorrow. Keep it short and real."
                        )
                    else:
                        msg = proactive_ask(
                            "Evening check. Deepak logged nothing today. "
                            "Call it out directly but not harshly. Ask what happened. "
                            "No lecture. Just a straight honest check-in from someone who cares."
                        )
                    if msg:
                        send(MY_CHAT_ID, msg)

            # SILENCE DETECTOR — if no activity for 2+ days, reach out
            if hour == 10 and minute < 2:
                key = "silence_check_" + today
                if not get_scheduler_state(key):
                    set_scheduler_state(key, "sent")
                    last_active = get_last_active_date()
                    if last_active:
                        days_silent = (datetime.now().date() - datetime.strptime(last_active, "%Y-%m-%d").date()).days
                        if days_silent >= 2:
                            msg = proactive_ask(
                                "Deepak has been completely silent for " + str(days_silent) + " days — no messages, no logs, nothing. "
                                "Reach out to him. Not with guilt. Not with a lecture. "
                                "Like a friend who noticed he went quiet and genuinely wants to know if he is okay. "
                                "Keep it human and short."
                            )
                            if msg:
                                send(MY_CHAT_ID, msg)

        except Exception as e:
            print("Scheduler error: " + str(e), flush=True)

        time.sleep(60)

# MAIN
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
