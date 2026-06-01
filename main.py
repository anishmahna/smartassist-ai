import os
import json
import sqlite3
import requests
import re
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__, static_folder='static')

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
DB = "/tmp/smartassist.db"


# ---------------- DATABASE INIT ---------------- #

def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        status TEXT DEFAULT 'pending',
        priority TEXT DEFAULT 'medium',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS schedules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        date TEXT,
        time TEXT,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        content TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    conn.commit()
    conn.close()


init_db()


# ---------------- TASKS ---------------- #

def add_task(title, description="", priority="medium"):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute(
        "INSERT INTO tasks (title,description,priority) VALUES (?,?,?)",
        (title, description, priority)
    )
    conn.commit()
    conn.close()
    return f"Task '{title}' added successfully!"


def get_tasks():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT id,title,status,priority FROM tasks ORDER BY id DESC LIMIT 20")
    tasks = c.fetchall()
    conn.close()

    if not tasks:
        return "No tasks found."

    result = "Your Tasks:\n"
    for t in tasks:
        status_emoji = "✅" if t[2] == "completed" else "⏳"
        result += f"{status_emoji} [{t[0]}] {t[1]} ({t[3]})\n"
    return result


def complete_task(task_id):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("UPDATE tasks SET status='completed' WHERE id=?", (task_id,))
    conn.commit()
    conn.close()
    return f"Task {task_id} marked completed!"


# ---------------- SCHEDULE ---------------- #

def add_schedule(title, date, time, description=""):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute(
        "INSERT INTO schedules (title,date,time,description) VALUES (?,?,?,?)",
        (title, date, time, description)
    )
    conn.commit()
    conn.close()
    return f"Schedule '{title}' added!"


def get_schedules():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT id,title,date,time FROM schedules ORDER BY date,time")
    schedules = c.fetchall()
    conn.close()

    if not schedules:
        return "No schedules found."

    result = "Your Schedule:\n"
    for s in schedules:
        result += f"📅 [{s[0]}] {s[1]} - {s[2]} at {s[3]}\n"
    return result


# ---------------- NOTES ---------------- #

def add_note(title, content):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("INSERT INTO notes (title,content) VALUES (?,?)", (title, content))
    conn.commit()
    conn.close()
    return f"Note '{title}' saved!"


def get_notes():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT id,title,content FROM notes ORDER BY id DESC LIMIT 10")
    notes = c.fetchall()
    conn.close()

    if not notes:
        return "No notes found."

    result = "Your Notes:\n"
    for n in notes:
        result += f"📝 [{n[0]}] {n[1]}: {n[2][:100]}\n"
    return result


# ---------------- WEATHER ---------------- #

def get_weather(city):
    try:
        geo = requests.get(
            f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1",
            timeout=10
        ).json()

        if not geo.get("results"):
            return f"City {city} not found"

        r = geo["results"][0]

        w = requests.get(
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={r['latitude']}&longitude={r['longitude']}"
            f"&current=temperature_2m,relative_humidity_2m,wind_speed_10m",
            timeout=10
        ).json()

        cur = w["current"]

        return (
            f"Weather in {city}: "
            f"{cur['temperature_2m']}°C, "
            f"Humidity {cur['relative_humidity_2m']}%, "
            f"Wind {cur['wind_speed_10m']} km/h"
        )

    except Exception as e:
        return f"Weather error: {str(e)}"


# ---------------- GEMINI SEARCH ---------------- #

def search_info(query):
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"

        payload = {
            "contents": [{
                "role": "user",
                "parts": [{"text": f"Research: {query}"}]
            }],
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 1024
            }
        }

        r = requests.post(url, json=payload, timeout=30)
        response = r.json()

        if "candidates" not in response:
            return "No response from AI."

        return response["candidates"][0]["content"]["parts"][0]["text"]

    except Exception as e:
        return f"Search error: {str(e)}"


# ---------------- TOOLS MAP ---------------- #

TOOLS = {
    "add_task": add_task,
    "get_tasks": get_tasks,
    "complete_task": complete_task,
    "add_schedule": add_schedule,
    "get_schedules": get_schedules,
    "add_note": add_note,
    "get_notes": get_notes,
    "get_weather": get_weather,
    "search_info": search_info,
}


# ---------------- GEMINI CALL ---------------- #

def call_gemini(messages, system_text):
    if not GEMINI_API_KEY:
        return "ERROR: GEMINI_API_KEY not set"

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"

    contents = [
        {"role": "user", "parts": [{"text": system_text}]},
        {"role": "model", "parts": [{"text": "OK"}]}
    ]

    for m in messages:
        role = "user" if m["role"] == "user" else "model"
        contents.append({"role": role, "parts": [{"text": m["content"]}]})

    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 2048
        }
    }

    try:
        r = requests.post(url, json=payload, timeout=60)
        response = r.json()

        if "candidates" not in response:
            return "AI error: No response"

        return response["candidates"][0]["content"]["parts"][0]["text"]

    except Exception as e:
        return f"AI error: {str(e)}"


# ---------------- SYSTEM PROMPT ---------------- #

SYSTEM = """
You are SmartAssist AI built by Anish Mahna.

If user wants a tool, respond ONLY:
TOOL_CALL: {"tool":"tool_name","params":{}}

Otherwise reply normally.
"""


# ---------------- ROUTES ---------------- #

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')


@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        messages = data.get('messages', [])

        reply = call_gemini(messages, SYSTEM)

        if "TOOL_CALL:" in reply:
            try:
                json_str = reply.split("TOOL_CALL:")[1]
                match = re.search(r'\{.*\}', json_str, re.DOTALL)

                if match:
                    tool_call = json.loads(match.group())
                    tool_name = tool_call["tool"]
                    params = tool_call.get("params", {})

                    if tool_name in TOOLS:
                        result = TOOLS[tool_name](**params)

                        messages.append({"role": "assistant", "content": reply})
                        messages.append({
                            "role": "user",
                            "content": f"Tool result: {result}. Now respond naturally."
                        })

                        final_reply = call_gemini(messages, SYSTEM)
                        return jsonify({"reply": final_reply})

            except Exception as e:
                print("Tool error:", e)

        return jsonify({"reply": reply})

    except Exception as e:
        return jsonify({"reply": "Server error"}), 500


@app.route('/tasks')
def tasks():
    return jsonify({"result": get_tasks()})


@app.route('/schedules')
def schedules():
    return jsonify({"result": get_schedules()})


@app.route('/notes')
def notes():
    return jsonify({"result": get_notes()})


# ---------------- RUN ---------------- #

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)), debug=True)
