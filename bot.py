"""
Telegram Bot Interface for VC Due Diligence Copilot with Rate Limiting.
Uses Python Standard Library (urllib) to connect to Telegram Bot API with zero external dependencies.
Receives startup links/names, checks free trial quotas, triggers VCDueDiligenceOrchestrator,
and sends teaser cards + links to the Netlify Web Viewer.
"""

import os
import sys
import json
import time
import urllib.request
import urllib.parse
import asyncio

sys.path.append(os.path.join(os.path.dirname(__file__), ".agents", "skills", "adaptive-ontological-search", "scripts"))
from vc_due_diligence_orchestrator import VCDueDiligenceOrchestrator, StartupProfile


TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
NETLIFY_BASE_URL = "https://incomparable-chebakia-bb5490.netlify.app"


class TelegramVCBot:
    def __init__(self, token: str):
        self.token = token
        self.api_url = f"https://api.telegram.org/bot{self.token}"
        self.orchestrator = VCDueDiligenceOrchestrator()
        self.last_update_id = 0
        self.user_usage = {}  # Track free requests per chat_id: {chat_id: count}
        self.MAX_FREE_AUDITS = 1  # 1 Free trial audit per user before requiring payment

    def send_message(self, chat_id: int, text: str, parse_mode: str = "HTML", reply_markup: dict = None):
        url = f"{self.api_url}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode
        }
        if reply_markup:
            payload["reply_markup"] = json.dumps(reply_markup)

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            print(f"[Telegram Error] Failed to send message: {e}")
            return None

    def get_updates(self):
        url = f"{self.api_url}/getUpdates?offset={self.last_update_id + 1}&timeout=10"
        try:
            with urllib.request.urlopen(url) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("ok"):
                    return data.get("result", [])
        except Exception as e:
            print(f"[Telegram Error] Polling error: {e}")
        return []

    async def handle_message(self, message: dict):
        chat_id = message["chat"]["id"]
        text = message.get("text", "").strip()
        user_name = message.get("from", {}).get("first_name", "Investor")

        if text.startswith("/start"):
            welcome_msg = (
                f"👋 <b>Welcome, {user_name}!</b>\n\n"
                f"🛡️ <b>Adaptive Evidence Search — VC Due Diligence Copilot</b>\n\n"
                f"<b>How it works:</b>\n"
                f"Send me any startup name or website link (e.g., <code>https://lensa.ai</code> or <code>Helsing MilTech</code>).\n\n"
                f"🎁 <b>Free Demo Trial:</b> You have <b>1 Free Trial Report</b>.\n"
                f"To unlock unlimited searches, upgrade to Pro Unlimited ($299/mo)."
            )
            self.send_message(chat_id, welcome_msg)
            return

        if not text:
            return

        # Rate Limiting Check: Max 1 Free Audit per user
        current_usage = self.user_usage.get(chat_id, 0)
        if current_usage >= self.MAX_FREE_AUDITS:
            limit_msg = (
                f"🔒 <b>Free Trial Limit Reached!</b>\n\n"
                f"You have used your <b>1/1 free demo report</b>.\n\n"
                f"To analyze unlimited startups and access Founder Q&A generators, activate a Pro subscription ($299/mo) or order a single report ($49)."
            )
            pay_keyboard = {
                "inline_keyboard": [
                    [{"text": "💳 Upgrade to Pro ($299/mo)", "url": f"{NETLIFY_BASE_URL}#pricing"}],
                    [{"text": "📄 Order Single Report ($49)", "url": f"{NETLIFY_BASE_URL}#pricing"}]
                ]
            }
            self.send_message(chat_id, limit_msg, reply_markup=pay_keyboard)
            return

        # Increment usage counter for this chat_id
        self.user_usage[chat_id] = current_usage + 1

        # Notify user analysis started
        self.send_message(
            chat_id,
            f"⏳ <b>Audit Started for:</b> <code>{text}</code>\n\n"
            f"Scanning primary patents, ITAR registries, employee mobility, and court dockets...\n"
            f"<i>Estimated time: 10–15 seconds.</i>"
        )

        # Build startup profile
        profile = StartupProfile(
            name=text.replace("http://", "").replace("https://", "").split("/")[0].title(),
            category="AI & Tech Venture",
            website=text if text.startswith("http") else f"https://{text.lower()}.ai",
            founders=["Founding Team"],
            stated_mission=f"AI venture evaluation for {text}",
            target_market="Global Tech Venture Market"
        )

        # Execute Search Engine
        report = await self.orchestrator.analyze_startup(profile)

        # Format Telegram Teaser Card
        recommendation_emoji = "🟢" if "STRONG" in report.investment_recommendation else "🟡"
        
        red_flags_text = ""
        for i, rf in enumerate(report.red_flags[:3], 1):
            red_flags_text += f"<b>{i}. [{rf['severity']} RISK]</b> {rf['title']}\n<i>Source: {rf['source']}</i>\n\n"

        teaser = (
            f"🛡️ <b>DUE DILIGENCE BRIEF: {report.startup_name}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{recommendation_emoji} <b>Verdict:</b> {report.investment_recommendation}\n"
            f"🎯 <b>Conviction Score:</b> {int(report.conviction_score * 100)}%\n\n"
            f"🚨 <b>IDENTIFIED RED FLAGS:</b>\n{red_flags_text}"
            f"💡 <b>Market Dynamics:</b> {', '.join(report.lightrag_dual_context.get('high_level_themes', []))}\n\n"
            f"👇 <b>View full report with primary evidence sources:</b>"
        )

        inline_keyboard = {
            "inline_keyboard": [
                [{"text": "📊 Open Full Report on Netlify", "url": NETLIFY_BASE_URL}]
            ]
        }

        self.send_message(chat_id, teaser, reply_markup=inline_keyboard)

    def run(self):
        if not self.token:
            print("=========================================================================")
            print("ERROR: TELEGRAM_BOT_TOKEN environment variable is missing!")
            print("Please set TELEGRAM_BOT_TOKEN='your_token_from_botfather' and run again.")
            print("=========================================================================\n")
            return

        print(f"=========================================================================")
        print(f"TELEGRAM VC DUE DILIGENCE BOT IS LIVE & LISTENING...")
        print(f"=========================================================================\n")

        while True:
            updates = self.get_updates()
            for update in updates:
                self.last_update_id = update["update_id"]
                if "message" in update:
                    asyncio.run(self.handle_message(update["message"]))
            time.sleep(1)


if __name__ == "__main__":
    token = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("TELEGRAM_BOT_TOKEN", "")
    bot = TelegramVCBot(token)
    bot.run()
