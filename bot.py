"""
Telegram Bot Interface for VC Due Diligence Copilot.
Loads configuration from bot_config.json, sys.argv, or environment variables.
Prints verbose terminal logs for every incoming message and sent response.
"""

import os
import sys
import json
import time
import html
import urllib.request
import urllib.parse
import asyncio

sys.path.append(os.path.join(os.path.dirname(__file__), ".agents", "skills", "adaptive-ontological-search", "scripts"))
from vc_due_diligence_orchestrator import VCDueDiligenceOrchestrator, StartupProfile


# Load Config from bot_config.json if present
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "bot_config.json")
config_data = {}
if os.path.exists(CONFIG_FILE):
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config_data = json.load(f)
    except Exception as e:
        print(f"[Config Warning] Failed to read bot_config.json: {e}")

TELEGRAM_BOT_TOKEN = (
    (sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else None)
    or os.environ.get("TELEGRAM_BOT_TOKEN")
    or config_data.get("token", "")
)

ADMIN_CHAT_ID = (
    (sys.argv[2] if len(sys.argv) > 2 else None)
    or os.environ.get("ADMIN_CHAT_ID")
    or config_data.get("admin_chat_id", "15579099")
)

NETLIFY_BASE_URL = "https://incomparable-chebakia-bb5490.netlify.app"


class TelegramVCBot:
    def __init__(self, token: str, admin_chat_id: str):
        self.token = token
        self.admin_chat_id = str(admin_chat_id)
        self.api_url = f"https://api.telegram.org/bot{self.token}"
        self.orchestrator = VCDueDiligenceOrchestrator()
        self.last_update_id = 0
        self.pending_requests = {}

    def send_message(self, chat_id: str, text: str, parse_mode: str = "HTML", reply_markup: dict = None):
        url = f"{self.api_url}/sendMessage"
        payload = {
            "chat_id": str(chat_id),
            "text": text,
            "parse_mode": parse_mode
        }
        if reply_markup:
            payload["reply_markup"] = json.dumps(reply_markup)

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                print(f"[Bot Success] Delivered message to chat_id={chat_id}")
                return res
        except Exception as e:
            print(f"[Bot Error] Failed HTML delivery to {chat_id}: {e}. Retrying without HTML formatting...")
            # Fallback to plain text if HTML parsing failed
            try:
                payload["parse_mode"] = ""
                data = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req) as resp:
                    res = json.loads(resp.read().decode("utf-8"))
                    print(f"[Bot Success Fallback] Delivered plain text to chat_id={chat_id}")
                    return res
            except Exception as e2:
                print(f"[Bot Error Critical] Plain text delivery failed: {e2}")
            return None

    def get_updates(self):
        url = f"{self.api_url}/getUpdates?offset={self.last_update_id + 1}&timeout=10"
        try:
            with urllib.request.urlopen(url) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("ok"):
                    return data.get("result", [])
        except Exception as e:
            print(f"[Bot Polling Error] {e}")
        return []

    async def handle_message(self, message: dict):
        chat_id = str(message["chat"]["id"])
        text = message.get("text", "").strip()
        user_name = message.get("from", {}).get("first_name", "Investor")
        username = message.get("from", {}).get("username", "")

        print(f"\n[Bot Received] Message from {user_name} (chat_id={chat_id}): '{text}'")

        if text.startswith("/start"):
            welcome_msg = (
                f"👋 <b>Welcome, {html.escape(user_name)}!</b>\n\n"
                f"🛡️ <b>Adaptive Evidence Search — VC Due Diligence Platform</b>\n\n"
                f"Your Chat ID is: <code>{chat_id}</code>\n"
                f"Admin Chat ID set to: <code>{self.admin_chat_id}</code>\n\n"
                f"<b>Commands:</b>\n"
                f"• Send any startup URL (e.g. <code>Moodro.tech</code>) to run an audit.\n"
                f"• Type <code>/testclient Moodro.tech</code> to test the Client-to-Admin approval buttons!"
            )
            self.send_message(chat_id, welcome_msg)
            return

        if not text:
            return

        # SIMULATE CLIENT REQUEST FOR ADMIN TESTING
        if text.startswith("/testclient"):
            parts = text.split(maxsplit=1)
            target_url = parts[1] if len(parts) > 1 else "Moodro.tech"
            request_id = str(int(time.time()))
            self.pending_requests[request_id] = {
                "chat_id": chat_id,
                "text": target_url,
                "user_name": "Test Client (Simulated)",
                "username": "client_demo"
            }
            admin_msg = (
                f"🔔 <b>NEW AUDIT REQUEST FOR APPROVAL!</b>\n"
                f"👤 <b>User:</b> Test Client (@client_demo) [ID: 9999999]\n"
                f"🎯 <b>Requested Startup:</b> <code>{html.escape(target_url)}</code>\n\n"
                f"Do you approve running this Due Diligence audit?"
            )
            approval_keyboard = {
                "inline_keyboard": [
                    [{"text": f"✅ Approve & Run ({target_url[:15]})", "callback_data": f"approve_{request_id}"}],
                    [{"text": "❌ Decline Request", "callback_data": f"decline_{request_id}"}]
                ]
            }
            self.send_message(chat_id, admin_msg, reply_markup=approval_keyboard)
            return

        is_admin = (self.admin_chat_id and str(chat_id) == str(self.admin_chat_id))

        if is_admin:
            # Direct Admin command: execute immediately and send private report
            self.send_message(chat_id, f"👑 <b>Admin Command Recognized.</b> Executing audit for: <code>{html.escape(text)}</code>...")
            await self.execute_and_send_audit(chat_id, text)
        else:
            # Client request: Send to Admin for manual approval
            request_id = str(int(time.time()))
            self.pending_requests[request_id] = {
                "chat_id": chat_id,
                "text": text,
                "user_name": user_name,
                "username": username
            }

            # Inform Client
            self.send_message(
                chat_id,
                f"📥 <b>Audit Request Received for:</b> <code>{html.escape(text)}</code>\n\n"
                f"Your request has been logged and queued for Admin review.\n"
                f"You will receive your confidential Due Diligence brief right here as soon as approved!"
            )

            # Notify Admin for Approval
            if self.admin_chat_id:
                admin_msg = (
                    f"🔔 <b>NEW AUDIT REQUEST FOR APPROVAL!</b>\n"
                    f"👤 <b>User:</b> {html.escape(user_name)} (@{html.escape(username)}) [ID: {chat_id}]\n"
                    f"🎯 <b>Requested Startup:</b> <code>{html.escape(text)}</code>\n\n"
                    f"Do you approve running this Due Diligence audit?"
                )
                approval_keyboard = {
                    "inline_keyboard": [
                        [{"text": f"✅ Approve & Run ({text[:15]})", "callback_data": f"approve_{request_id}"}],
                        [{"text": "❌ Decline Request", "callback_data": f"decline_{request_id}"}]
                    ]
                }
                self.send_message(self.admin_chat_id, admin_msg, reply_markup=approval_keyboard)

    async def handle_callback_query(self, callback: dict):
        callback_id = callback["id"]
        data = callback.get("data", "")
        from_chat_id = str(callback["from"]["id"])

        print(f"[Bot Callback] Received callback '{data}' from {from_chat_id}")

        if data.startswith("approve_"):
            req_id = data.replace("approve_", "")
            req = self.pending_requests.get(req_id)
            if req:
                client_chat_id = req["chat_id"]
                target_text = req["text"]
                self.send_message(from_chat_id, f"✅ <b>Request Approved!</b> Executing audit for <code>{html.escape(target_text)}</code>...")
                if client_chat_id != from_chat_id:
                    self.send_message(client_chat_id, f"🎉 <b>Request Approved!</b> Generating your Due Diligence brief now...")
                await self.execute_and_send_audit(client_chat_id, target_text)

        elif data.startswith("decline_"):
            req_id = data.replace("decline_", "")
            req = self.pending_requests.get(req_id)
            if req:
                client_chat_id = req["chat_id"]
                self.send_message(from_chat_id, f"❌ Request declined.")
                if client_chat_id != from_chat_id:
                    self.send_message(client_chat_id, f"ℹ️ Your audit request could not be processed at this time.")

    async def execute_and_send_audit(self, target_chat_id: str, text: str):
        name = text.replace("http://", "").replace("https://", "").split("/")[0].title()
        
        # Categorize
        if "moodro" in text.lower() or "helsing" in text.lower() or "miltech" in text.lower() or "defense" in text.lower():
            category = "AI + MilTech"
        else:
            category = "AI & Tech Venture"

        profile = StartupProfile(
            name=name,
            category=category,
            website=text if text.startswith("http") else f"https://{text.lower()}",
            founders=["Founding Team"],
            stated_mission=f"VC evaluation for {name}",
            target_market="Global Tech Venture Market"
        )

        report = await self.orchestrator.analyze_startup(profile)

        # Private Telegram Delivery with html.escape protection
        recommendation_emoji = "🟢" if "STRONG" in report.investment_recommendation else "🟡"
        
        red_flags_text = ""
        for i, rf in enumerate(report.red_flags, 1):
            red_flags_text += f"<b>{i}. [{rf['severity']} RISK]</b> {html.escape(rf['title'])}\n<i>{html.escape(rf['evidence'])}</i>\n<i>Source: {html.escape(rf['source'])}</i>\n\n"

        questions_text = ""
        for i, q in enumerate(report.key_questions_for_founders, 1):
            questions_text += f"• {html.escape(q)}\n"

        private_report = (
            f"🛡️ <b>CONFIDENTIAL DUE DILIGENCE BRIEF</b>\n"
            f"<b>Company:</b> {html.escape(report.startup_name)} ({html.escape(report.category)})\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{recommendation_emoji} <b>Verdict:</b> {html.escape(report.investment_recommendation)}\n"
            f"🎯 <b>Conviction Score:</b> {int(report.conviction_score * 100)}%\n\n"
            f"📄 <b>Executive Summary:</b>\n{html.escape(report.executive_summary)}\n\n"
            f"🚨 <b>IDENTIFIED RED FLAGS:</b>\n{red_flags_text}"
            f"⚡ <b>IP MOAT AUDIT:</b>\n"
            f"• Rating: {html.escape(str(report.tech_moat_evaluation.get('moat_rating')))}\n"
            f"• Patents: {report.tech_moat_evaluation.get('patent_count')} Active Patents\n"
            f"• Dataset: {html.escape(str(report.tech_moat_evaluation.get('proprietary_dataset')))}\n\n"
            f"❓ <b>PRIORITY QUESTIONS FOR FOUNDERS:</b>\n{questions_text}\n"
            f"🔒 <i>Confidential Brief. Generated by Adaptive Evidence Search.</i>"
        )

        self.send_message(target_chat_id, private_report)

    def run(self):
        if not self.token:
            print("\n=========================================================================")
            print("ERROR: TELEGRAM_BOT_TOKEN is missing!")
            print("Please pass your token directly: python3 bot.py YOUR_TOKEN")
            print("=========================================================================\n")
            return

        print(f"\n=========================================================================")
        print(f"TELEGRAM VC DUE DILIGENCE BOT IS LIVE & LISTENING...")
        print(f"Admin Chat ID: {self.admin_chat_id}")
        print(f"=========================================================================\n")

        while True:
            updates = self.get_updates()
            for update in updates:
                self.last_update_id = update["update_id"]
                if "message" in update:
                    asyncio.run(self.handle_message(update["message"]))
                elif "callback_query" in update:
                    asyncio.run(self.handle_callback_query(update["callback_query"]))
            time.sleep(1)


if __name__ == "__main__":
    bot = TelegramVCBot(TELEGRAM_BOT_TOKEN, ADMIN_CHAT_ID)
    bot.run()
