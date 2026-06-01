import os, json, sqlite3, requests, re
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__, static_folder='../static')
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

def call_gemini(messages):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    SYSTEM = """You are SmartAssist AI built by Anish Mahna.
You are a helpful AI assistant that can answer any question.
You can also manage tasks, schedules, notes and check weather.
Never mention Google or Gemini. Be friendly and helpful."""
    contents = [
        {"role":"user","parts":[{"text":SYSTEM}]},
        {"role":"model","parts":[{"text":"I am SmartAssist AI built by Anish Mahna. Ready to help!"}]}
    ]
    for m in messages:
        contents.append({"role":"user" if m["role"]=="user" else "model","parts":[{"text":m["content"]}]})
    r = requests.post(url, json={"contents":contents,"generationConfig":{"temperature":0.2,"maxOutputTokens":4096}}, timeout=60)
    data = r.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]

@app.route('/')
def index():
    return send_from_directory('../static', 'index.html')

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        messages = data.get('messages', [])
        reply = call_gemini(messages)
        return jsonify({"reply": reply})
    except Exception as e:
        print("ERROR:", str(e))
        return jsonify({"reply": f"Error: {str(e)}"}), 500

@app.route('/generate-image', methods=['POST'])
def generate_image():
    try:
        data = request.json
        prompt = data.get('prompt', '')
        encoded = requests.utils.quote(prompt + ', high quality, detailed')
        import random
        url = f"https://image.pollinations.ai/prompt/{encoded}?width=512&height=512&nologo=true&seed={random.randint(1,99999)}"
        return jsonify({"image_url": url})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
