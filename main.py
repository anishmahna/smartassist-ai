import os, json, sqlite3, requests, re
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__, static_folder='static')
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
DB = "/tmp/smartassist.db"

def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT, description TEXT,
        status TEXT DEFAULT 'pending',
        priority TEXT DEFAULT 'medium'
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS schedules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT, date TEXT, time TEXT, description TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT, content TEXT
    )''')
    conn.commit()
    conn.close()

init_db()

def add_task(title, description="", priority="medium"):
    conn = sqlite3.connect(DB)
    conn.execute("INSERT INTO tasks (title,description,priority) VALUES (?,?,?)", (title,description,priority))
    conn.commit()
    conn.close()
    return f"Task '{title}' added with {priority} priority!"

def get_tasks():
    conn = sqlite3.connect(DB)
    tasks = conn.execute("SELECT id,title,status,priority FROM tasks ORDER BY id DESC LIMIT 20").fetchall()
    conn.close()
    if not tasks: return "No tasks yet!"
    return "Your Tasks:\n" + "\n".join([f"{'✅' if t[2]=='completed' else '⏳'} [{t[0]}] {t[1]} ({t[3]})" for t in tasks])

def complete_task(task_id):
    conn = sqlite3.connect(DB)
    conn.execute("UPDATE tasks SET status='completed' WHERE id=?", (task_id,))
    conn.commit()
    conn.close()
    return f"Task {task_id} completed!"

def add_schedule(title, date, time, description=""):
    conn = sqlite3.connect(DB)
    conn.execute("INSERT INTO schedules (title,date,time,description) VALUES (?,?,?,?)", (title,date,time,description))
    conn.commit()
    conn.close()
    return f"Schedule '{title}' added for {date} at {time}!"

def get_schedules():
    conn = sqlite3.connect(DB)
    rows = conn.execute("SELECT id,title,date,time FROM schedules ORDER BY date,time").fetchall()
    conn.close()
    if not rows: return "No schedules yet!"
    return "Your Schedule:\n" + "\n".join([f"📅 [{r[0]}] {r[1]} - {r[2]} at {r[3]}" for r in rows])

def add_note(title, content):
    conn = sqlite3.connect(DB)
    conn.execute("INSERT INTO notes (title,content) VALUES (?,?)", (title,content))
    conn.commit()
    conn.close()
    return f"Note '{title}' saved!"

def get_notes():
    conn = sqlite3.connect(DB)
    notes = conn.execute("SELECT id,title,content FROM notes ORDER BY id DESC LIMIT 10").fetchall()
    conn.close()
    if not notes: return "No notes yet!"
    return "Your Notes:\n" + "\n".join([f"📝 [{n[0]}] {n[1]}: {n[2][:100]}" for n in notes])

def get_weather(city):
    try:
        geo = requests.get(f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1",timeout=10).json()
        if not geo.get("results"): return f"City {city} not found"
        r = geo["results"][0]
        w = requests.get(f"https://api.open-meteo.com/v1/forecast?latitude={r['latitude']}&longitude={r['longitude']}&current=temperature_2m,relative_humidity_2m,wind_speed_10m",timeout=10).json()
        cur = w["current"]
        return f"Weather in {city}: {cur['temperature_2m']}°C, Humidity {cur['relative_humidity_2m']}%, Wind {cur['wind_speed_10m']} km/h"
    except Exception as e:
        return f"Error: {str(e)}"

def search_info(query):
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
        r = requests.post(url, json={"contents":[{"role":"user","parts":[{"text":f"Research: {query}"}]}],"generationConfig":{"maxOutputTokens":1024}}, timeout=30)
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        return f"Error: {str(e)}"

TOOLS = {"add_task":add_task,"get_tasks":get_tasks,"complete_task":complete_task,
         "add_schedule":add_schedule,"get_schedules":get_schedules,
         "add_note":add_note,"get_notes":get_notes,
         "get_weather":get_weather,"search_info":search_info}

def call_gemini(messages, system_text):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    contents = [{"role":"user","parts":[{"text":system_text}]},{"role":"model","parts":[{"text":"Ready!"}]}]
    for m in messages:
        contents.append({"role":"user" if m["role"]=="user" else "model","parts":[{"text":m["content"]}]})
    r = requests.post(url, json={"contents":contents,"generationConfig":{"temperature":0.2,"maxOutputTokens":4096}}, timeout=60)
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]

SYSTEM = """You are SmartAssist AI built by Anish Mahna.
Use tools by responding: TOOL_CALL: {"tool":"name","params":{}}
Tools: add_task, get_tasks, complete_task, add_schedule, get_schedules, add_note, get_notes, get_weather, search_info
For normal chat respond helpfully. Never mention Google or Gemini."""

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        messages = data.get('messages', [])
        reply = call_gemini(messages, SYSTEM)
        if 'TOOL_CALL:' in reply:
            try:
                match = re.search(r'\{.*\}', reply.split('TOOL_CALL:')[1].strip(), re.DOTALL)
                if match:
                    tc = json.loads(match.group())
                    result = TOOLS[tc["tool"]](**tc.get("params",{}))
                    followup = messages + [{"role":"assistant","content":reply},{"role":"user","content":f"Result: {result}. Give friendly response."}]
                    return jsonify({"reply": call_gemini(followup, SYSTEM)})
            except: pass
        return jsonify({"reply": reply})
    except Exception as e:
        return jsonify({"reply": "Error. Try again!"}), 500

app = app
