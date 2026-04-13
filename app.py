from flask import Flask
import requests
import os
import time
import google.generativeai as genai

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload)
    except:
        pass

@app.route("/")
def home():
    return "Momentum AI Bot is running!"

@app.route("/scan")
def scan():
    try:
        resp = requests.get("https://api.dexscreener.com/latest/dex/search?q=solana")
        data = resp.json()

        pairs = data.get("pairs", [])[:20]

        for pair in pairs:
            if not pair or not pair.get("baseToken"):
                continue

            fdv = pair.get("fdv") or pair.get("marketCap") or 0
            vol5m = pair.get("volume", {}).get("m5", 0)
            vol1h = pair.get("volume", {}).get("h1", 0)
            age_minutes = pair.get("pairCreatedAt", 0)
            if age_minutes:
                age_minutes = (time.time() * 1000 - age_minutes) / 60000

            # Filtru pentru tokenuri mai vechi cu volum spike
            if 10000 < fdv < 500000 and (vol5m > 4000 or vol1h > 20000) and age_minutes > 30:
                token = {
                    "name": pair["baseToken"].get("name", "Unknown"),
                    "symbol": pair["baseToken"].get("symbol", "N/A"),
                    "mcap": round(fdv / 1000),
                    "volume5m": round(vol5m / 1000),
                    "volume1h": round(vol1h / 1000),
                    "age_minutes": round(age_minutes)
                }

                # Prompt AI pentru momentum
                prompt = f"""
                Analizează acest token Solana care a început să prindă volum recent.

                Nume: {token['name']}
                Simbol: {token['symbol']}
                MCAP: ~{token['mcap']}k
                Volum 5m: ~{token['volume5m']}k
                Volum 1h: ~{token['volume1h']}k
                Vârstă: ~{token['age_minutes']} minute

                Răspunde DOAR cu JSON:
                {{
                  "potential_score": scor 1-10,
                  "potential_2x": "DA" or "NU",
                  "reason": "motiv scurt în română",
                  "scam_risk": "DA" or "NU"
                }}
                """

                try:
                    response = model.generate_content(prompt)
                    ai_text = response.text
                except:
                    ai_text = "Eroare AI"

                message = f"""🚨 <b>Momentum AI Signal</b>

{token['name']} ({token['symbol']})
MCAP: ~{token['mcap']}k
Volum 5m: ~{token['volume5m']}k
Volum 1h: ~{token['volume1h']}k
Vârstă: ~{token['age_minutes']} min

AI Analysis:
{ai_text}

🔗 https://dexscreener.com/solana/{pair.get('pairAddress', '')}

DYOR!"""

                send_telegram(message)
                time.sleep(3)

        return "Scan momentum completat."
    except Exception as e:
        return f"Eroare: {str(e)}"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
