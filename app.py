from flask import Flask
import os
import time
import httpx
import logging
from google import genai
from telegram import Bot

app = Flask(__name__)

# ================== CONFIG ==================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

bot = Bot(token=TELEGRAM_TOKEN)

# Configurare agresivă pentru early buys + momentum
MIN_MCAP = 5000
MAX_MCAP = 1000000      # crescut mult
MIN_VOL_5M = 1000       # redus puternic
MIN_VOL_1H = 5000       # redus
MIN_SCORE = 4           # redus ca să treacă mai multe

# ===========================================

@app.route("/")
def home():
    return "CRS Momentum Bot is running on Render!"

@app.route("/scan")
def scan():
    try:
        with httpx.Client(timeout=15) as client:
            r = client.get("https://api.dexscreener.com/latest/dex/search?q=solana")
            data = r.json()

        pairs = data.get("pairs", [])[:40]
        sent = 0

        for p in pairs:
            try:
                fdv = p.get("fdv") or p.get("marketCap") or 0
                vol5m = p.get("volume", {}).get("m5", 0)
                vol1h = p.get("volume", {}).get("h1", 0)

                if not (MIN_MCAP < fdv < MAX_MCAP):
                    continue
                if vol5m < MIN_VOL_5M and vol1h < MIN_VOL_1H:
                    continue

                # Analiză AI
                prompt = f"""
                Analizează rapid acest token Solana pentru early momentum:

                Nume: {p['baseToken'].get('name', 'Unknown')}
                Simbol: {p['baseToken'].get('symbol', 'N/A')}
                MCAP: ~{fdv/1000:.0f}k
                Volum 5m: ~{vol5m/1000:.0f}k
                Volum 1h: ~{vol1h/1000:.0f}k

                Răspunde STRICT cu JSON:
                {{"potential_score": număr 1-10, "potential_2x": "DA" sau "NU", "reason": "scurt în română", "scam_risk": "DA" sau "NU"}}
                """

                response = model.generate_content(prompt)
                ai_text = response.text.strip()
                ai = eval(ai_text) if "{" in ai_text else {"potential_score": 6, "potential_2x": "NU", "reason": "Analiză rapidă", "scam_risk": "NU"}

                if ai.get("potential_score", 0) >= MIN_SCORE:
                    message = f"""
🚨 <b>CRS Momentum Signal</b>

{p['baseToken']['name']} ({p['baseToken']['symbol']})
MCAP: ~{fdv/1000:.0f}k
Vol 5m: ~{vol5m/1000:.0f}k
Score: {ai['potential_score']}/10 | 2x: {ai['potential_2x']}
Reason: {ai['reason']}
Scam Risk: {ai['scam_risk']}

🔗 https://dexscreener.com/solana/{p.get('pairAddress','')}
                    """

                    bot.send_message(chat_id=CHAT_ID, text=message.strip(), parse_mode='HTML')
                    sent += 1
                    log.info(f"Semnal trimis: {p['baseToken']['symbol']}")
                    time.sleep(2)

            except Exception as e:
                log.error(f"Eroare la token: {e}")
                continue

        return f"Scan completat. Trimise {sent} semnale."
    except Exception as e:
        log.error(f"Eroare generală scan: {e}")
        return f"Eroare: {str(e)}"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
