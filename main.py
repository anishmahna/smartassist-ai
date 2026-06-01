import os, json, sqlite3, requests, random, re
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__, static_folder='static')
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
DB = "/tmp/smartassist.db"

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

def add_task(title, description="", priority="medium"):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("INSERT INTO tasks (title,description,priority) VALUES (?,?,?)", (title,description,priority))
    conn.commit()
    conn.close()
    return f"Task '{title}' added successfully with {priority} priority!"

def get_tasks():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT id,title,status,priority FROM tasks ORDER BY id DESC LIMIT 20")
    tasks = c.fetchall()
    conn.close()
    if not tasks:
        return "No tasks found. Add your first task!"
    result = "Your Tasks:\n"
    for t in tasks:
        status_emoji = "✅" if t[2]=="completed" else "⏳"
        result += f"{status_emoji} [{t[0]}] {t[1]} ({t[3]} priority)\n"
    return result

def complete_task(task_id):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("UPDATE tasks SET status='completed' WHERE id=?", (task_id,))
    conn.commit()
    conn.close()
    return f"Task {task_id} marked as completed!"

def add_schedule(title, date, time, description=""):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("INSERT INTO schedules (title,date,time,description) VALUES (?,?,?,?)", (title,date,time,description))
    conn.commit()
    conn.close()
    return f"Schedule '{title}' added for {date} at {time}!"

def get_schedules():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT id,title,date,time FROM schedules ORDER BY date,time")
    schedules = c.fetchall()
    conn.close()
    if not schedules:
        return "No schedules found. Add your first schedule!"
    result = "Your Schedule:\n"
    for s in schedules:
        result += f"📅 [{s[0]}] {s[1]} - {s[2]} at {s[3]}\n"
    return result

def add_note(title, content):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("INSERT INTO notes (title,content) VALUES (?,?)", (title,content))
    conn.commit()
    conn.close()
    return f"Note '{title}' saved successfully!"

def get_notes():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT id,title,content FROM notes ORDER BY id DESC LIMIT 10")
    notes = c.fetchall()
    conn.close()
    if not notes:
        return "No notes found. Save your first note!"
    result = "Your Notes:\n"
    for n in notes:
        result += f"📝 [{n[0]}] {n[1]}: {n[2][:100]}\n"
    return result

def get_weather(city):
    try:
        geo = requests.get(f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1",timeout=10).json()
        if not geo.get("results"):
            return f"City {city} not found"
        r = geo["results"][0]
        w = requests.get(f"https://api.open-meteo.com/v1/forecast?latitude={r['latitude']}&longitude={r['longitude']}&current=temperature_2m,relative_humidity_2m,wind_speed_10m",timeout=10).json()
        cur = w["current"]
        return f"Weather in {city}: Temperature {cur['temperature_2m']}°C, Humidity {cur['relative_humidity_2m']}%, Wind {cur['wind_speed_10m']} km/h"
    except Exception as e:
        return f"Weather error: {str(e)}"

def search_info(query):
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
        payload = {"contents":[{"role":"user","parts":[{"text":f"Research and provide comprehensive information about: {query}"}]}],
                   "generationConfig":{"temperature":0.3,"maxOutputTokens":1024}}
        r = requests.post(url, json=payload, timeout=30)
        response = r.json()

        if "candidates" not in response:
            return "Sorry, I couldn't generate a response right now."

        return response["candidates"][0]["content"]["parts"][0]["text"]

    except Exception as e:
        return f"Search error: {str(e)}"

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

def call_gemini(messages, system_text):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    contents = [
        {"role":"user","parts":[{"text":system_text}]},
        {"role":"model","parts":[{"text":"Understood! I am SmartAssist AI ready to help!"}]}
    ]
    for m in messages:
        role = "user" if m["role"]=="user" else "model"
        contents.append({"role":role,"parts":[{"text":m["content"]}]})
    payload = {"contents":contents,"generationConfig":{"temperature":0.2,"maxOutputTokens":4096}}
    r = requests.post(url,json=payload,timeout=60)
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]

SYSTEM = """You are SmartAssist AI, an intelligent multi-agent productivity assistant built by Anish Mahna.

You have these agents and tools available:

TASK AGENT tools:
- add_task(title, description, priority) 
- get_tasks()
- complete_task(task_id)

SCHEDULE AGENT tools:
- add_schedule(title, date, time, description)
- get_schedules()

NOTES AGENT tools:
- add_note(title, content)
- get_notes()

WEATHER AGENT tools:
- get_weather(city)

RESEARCH AGENT tools:
- search_info(query)

IMPORTANT: When user wants to use a tool, respond ONLY with this exact JSON format:
TOOL_CALL: {"tool": "tool_name", "params": {"param1": "value1"}}

For example:
- User says "add task buy milk" → TOOL_CALL: {"tool": "add_task", "params": {"title": "buy milk", "description": "", "priority": "medium"}}
- User says "weather in Mumbai" → TOOL_CALL: {"tool": "get_weather", "params": {"city": "Mumbai"}}
- User says "show tasks" → TOOL_CALL: {"tool": "get_tasks", "params": {}}

For general conversation (not tool use), respond normally.
Never mention Google, Gemini. You are SmartAssist AI built by Anish Mahna."""

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
                json_str = reply.split('TOOL_CALL:')[1].strip()
                json_match = re.search(r'\{.*\}', json_str, re.DOTALL)
                if json_match:
                    tool_call = json.loads(json_match.group())
                    tool_name = tool_call.get("tool")
                    params = tool_call.get("params", {})
                    
                    if tool_name in TOOLS:
                        tool_result = TOOLS[tool_name](**params)
                        
                        followup_messages = messages + [
                            {"role": "assistant", "content": reply},
                            {"role": "user", "content": f"Tool executed successfully. Result: {tool_result}\n\nNow give a friendly, helpful response to the user about what was done. Be conversational and clear."}
                        ]
                        final_reply = call_gemini(followup_messages, SYSTEM)
                        return jsonify({"reply": final_reply})
            except Exception as e:
                print("Tool error:", str(e))
        
        return jsonify({"reply": reply})
    
    except Exception as e:
        print("ERROR:", str(e))
        return jsonify({"reply": "Something went wrong. Please try again!"}), 500

@app.route('/tasks', methods=['GET'])
def tasks():
    return jsonify({"result": get_tasks()})

@app.route('/schedules', methods=['GET'])  
def schedules():
    return jsonify({"result": get_schedules()})

@app.route('/notes', methods=['GET'])
def notes():
    return jsonify({"result": get_notes()})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

