from flask import Flask
import os
import time
import asyncio
import httpx
import logging
from datetime import datetime

import google.generativeai as genai
from telegram import Bot

app = Flask(__name__)

# Config
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

bot = Bot(token=TELEGRAM_TOKEN)

# Configurare scanare
SCAN_INTERVAL = 600  # 10 minute
MIN_MCAP = 8000
MAX_MCAP = 500000
MIN_VOL_5M = 3000
MIN_SCORE = 6

async def analyze_token(pair):
    try:
        prompt = f"""
        Analizează acest token Solana pentru potențial momentum:

        Nume: {pair.get('baseToken', {}).get('name', 'Unknown')}
        Simbol: {pair.get('baseToken', {}).get('symbol', 'N/A')}
        MCAP: ~{pair.get('fdv', 0)/1000:.0f}k
        Volum 5m: ~{pair.get('volume', {}).get('m5', 0)/1000:.0f}k
        Volum 1h: ~{pair.get('volume', {}).get('h1', 0)/1000:.0f}k

        Răspunde STRICT cu JSON:
        {{
          "potential_score": număr între 1 și 10,
          "potential_2x": "DA" sau "NU",
          "reason": "explicație scurtă în română",
          "scam_risk": "DA" sau "NU"
        }}
        """
        response = model.generate_content(prompt)
        return eval(response.text.strip())  # simplificat pentru test
    except:
        return {"potential_score": 5, "potential_2x": "NU", "reason": "Eroare analiză", "scam_risk": "NU"}

@app.route("/")
def home():
    return "Momentum Bot is running on Render!"

@app.route("/scan")
async def scan():
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get("https://api.dexscreener.com/latest/dex/search?q=solana")
            data = r.json()

        pairs = data.get("pairs", [])[:30]

        sent = 0
        for p in pairs:
            fdv = p.get("fdv") or p.get("marketCap") or 0
            vol5m = p.get("volume", {}).get("m5", 0)

            if not (MIN_MCAP < fdv < MAX_MCAP and vol5m > MIN_VOL_5M):
                continue

            ai = await analyze_token(p)

            if ai.get("potential_score", 0) >= MIN_SCORE:
                message = f"""
🚨 Momentum Signal

{p['baseToken']['name']} ({p['baseToken']['symbol']})
MCAP: ~{fdv/1000:.0f}k
Vol 5m: ~{vol5m/1000:.0f}k
Score: {ai['potential_score']}/10
Reason: {ai['reason']}
                """

                await bot.send_message(chat_id=CHAT_ID, text=message.strip())
                sent += 1
                await asyncio.sleep(2)

        return f"Scan completat. Trimise {sent} semnale."
    except Exception as e:
        log.error(f"Eroare scan: {e}")
        return f"Eroare: {str(e)}"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
