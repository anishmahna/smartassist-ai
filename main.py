import os
import json
import sqlite3
import requests
import re
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__, static_folder="static")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
DB = "/tmp/smartassist.db"


# ---------------- DB INIT ---------------- #

def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        description TEXT,
        status TEXT DEFAULT 'pending',
        priority TEXT DEFAULT 'medium'
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        content TEXT
    )''')

    conn.commit()
    conn.close()

init_db()


# ---------------- GEMINI CALL (FIXED 2.5 MODEL) ---------------- #

def call_gemini(messages, system_text):
    if not GEMINI_API_KEY:
        return "Missing API key"

    # ✅ FIXED MODEL (THIS IS THE IMPORTANT PART)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"

    contents = [
        {"role": "user", "parts": [{"text": system_text}]}
    ]

    for m in messages:
        role = "user" if m["role"] == "user" else "model"
        contents.append({"role": role, "parts": [{"text": m["content"]}]})

    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": 0.4,
            "maxOutputTokens": 1024
        }
    }

    try:
        r = requests.post(url, json=payload, timeout=30)
        data = r.json()

        print("DEBUG GEMINI:", data)

        if "candidates" not in data:
            return f"AI ERROR: {data}"

        return data["candidates"][0]["content"]["parts"][0]["text"]

    except Exception as e:
        return f"AI ERROR: {str(e)}"


# ---------------- SIMPLE SYSTEM PROMPT ---------------- #

SYSTEM = """
You are SmartAssist AI. If tool needed respond:
TOOL_CALL: {"tool":"tool_name","params":{}}
"""


# ---------------- ROUTE ---------------- #

@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    messages = data.get("messages", [])

    reply = call_gemini(messages, SYSTEM)

    return jsonify({"reply": reply})


@app.route("/")
def home():
    return send_from_directory("static", "index.html")


# ---------------- RUN ---------------- #

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
