from flask import Flask, request, jsonify, send_file
import requests

app = Flask(__name__)

# 🔑 GANTI DENGAN API KEY BARU LO (yang tadi udah bocor, jangan dipakai lagi)
API_KEY = "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"

# 🧠 MEMORY
chat_history = []

# 🔄 FALLBACK (kalau API error)
def fallback_ai(text):
    text = text.lower()
    if "halo" in text:
        return "Halo juga 😄 (mode offline)"
    return "AI lagi gangguan, coba lagi bentar ya 😅"

# 🤖 AI PINTAR
def smart_ai(text):
    url = "https://openrouter.ai/api/v1/chat/completions"

    chat_history.append({"role": "user", "content": text})

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "meta-llama/llama-3-8b-instruct",
        "messages": [
            {"role": "system", "content": "Kamu adalah AI asisten pintar, jelas, dan membantu."},
            *chat_history[-6:]
        ]
    }

    try:
        res = requests.post(url, headers=headers, json=data, timeout=15)

        if res.status_code != 200:
            print("API ERROR:", res.text)
            return fallback_ai(text)

        result = res.json()

        if "choices" not in result:
            print("FORMAT ERROR:", result)
            return fallback_ai(text)

        reply = result["choices"][0]["message"]["content"]

        chat_history.append({"role": "assistant", "content": reply})

        return reply

    except Exception as e:
        print("SYSTEM ERROR:", str(e))
        return fallback_ai(text)


# 🌐 UI
@app.route("/")
def home():
    return send_file("chat.html")


# 💬 CHAT API
@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    user_text = data.get("message", "")

    reply = smart_ai(user_text)

    return jsonify({"reply": reply})


# 🔄 RESET CHAT
@app.route("/reset", methods=["POST"])
def reset():
    chat_history.clear()
    return {"status": "ok"}


# 🚀 RUN
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)