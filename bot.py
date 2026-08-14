"""
Telegram Bot Interface for VC Due Diligence Copilot with Admin Control & Auto Netlify Publishing Mode.
All incoming client requests require Admin approval before executing audits.
Admin can also run direct audits instantly. Automatically pushes generated reports to Netlify.
"""

import os
import sys
import json
import time
import urllib.request
import urllib.parse
import asyncio
import subprocess

sys.path.append(os.path.join(os.path.dirname(__file__), ".agents", "skills", "adaptive-ontological-search", "scripts"))
from vc_due_diligence_orchestrator import VCDueDiligenceOrchestrator, StartupProfile


TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID", "")
NETLIFY_BASE_URL = "https://incomparable-chebakia-bb5490.netlify.app"


class TelegramVCBot:
    def __init__(self, token: str):
        self.token = token
        self.api_url = f"https://api.telegram.org/bot{self.token}"
        self.orchestrator = VCDueDiligenceOrchestrator()
        self.last_update_id = 0
        self.pending_requests = {}

    def send_message(self, chat_id: str, text: str, parse_mode: str = "HTML", reply_markup: dict = None):
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
        chat_id = str(message["chat"]["id"])
        text = message.get("text", "").strip()
        user_name = message.get("from", {}).get("first_name", "Investor")
        username = message.get("from", {}).get("username", "")

        if text.startswith("/start"):
            welcome_msg = (
                f"👋 <b>Welcome, {user_name}!</b>\n\n"
                f"🛡️ <b>Adaptive Evidence Search — VC Due Diligence Platform</b>\n\n"
                f"Your Chat ID is: <code>{chat_id}</code>\n"
                f"<i>(Save this ID to set ADMIN_CHAT_ID='{chat_id}' for full manual approval control)</i>\n\n"
                f"<b>To request a Due Diligence Audit:</b>\n"
                f"Send any startup name or website URL (e.g., <code>https://lensa.ai</code>).\n"
                f"Our team will approve and deliver the audit brief."
            )
            self.send_message(chat_id, welcome_msg)
            return

        if not text:
            return

        # IF ADMIN (You): Run Audit Instantly
        if ADMIN_CHAT_ID and chat_id == str(ADMIN_CHAT_ID):
            self.send_message(chat_id, f"👑 <b>Admin Command Recognized.</b> Starting audit for: <code>{text}</code>...")
            await self.execute_and_send_audit(chat_id, text)
            return

        # IF CLIENT: Send request to Admin for manual approval
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
            f"📥 <b>Audit Request Received for:</b> <code>{text}</code>\n\n"
            f"Your request has been logged and queued for Admin review.\n"
            f"You will receive your Due Diligence brief as soon as it is approved!"
        )

        # Notify Admin for Approval (if ADMIN_CHAT_ID set)
        if ADMIN_CHAT_ID:
            admin_msg = (
                f"🔔 <b>NEW AUDIT REQUEST FOR APPROVAL!</b>\n"
                f"👤 <b>User:</b> {user_name} (@{username}) [ID: {chat_id}]\n"
                f"🎯 <b>Requested Startup:</b> <code>{text}</code>\n\n"
                f"Do you approve running this Due Diligence audit?"
            )
            approval_keyboard = {
                "inline_keyboard": [
                    [{"text": f"✅ Approve & Run ({text[:15]})", "callback_data": f"approve_{request_id}"}],
                    [{"text": "❌ Decline Request", "callback_data": f"decline_{request_id}"}]
                ]
            }
            self.send_message(ADMIN_CHAT_ID, admin_msg, reply_markup=approval_keyboard)
        else:
            print(f"[ADMIN NOTICE] Request from {user_name} for '{text}'. ADMIN_CHAT_ID is not set yet.")

    async def handle_callback_query(self, callback: dict):
        callback_id = callback["id"]
        data = callback.get("data", "")
        from_chat_id = str(callback["from"]["id"])

        if data.startswith("approve_"):
            req_id = data.replace("approve_", "")
            req = self.pending_requests.get(req_id)
            if req:
                client_chat_id = req["chat_id"]
                target_text = req["text"]
                self.send_message(from_chat_id, f"✅ Request approved! Running audit for <code>{target_text}</code>...")
                self.send_message(client_chat_id, f"🎉 <b>Request Approved!</b> Generating your Due Diligence brief now...")
                await self.execute_and_send_audit(client_chat_id, target_text)

        elif data.startswith("decline_"):
            req_id = data.replace("decline_", "")
            req = self.pending_requests.get(req_id)
            if req:
                client_chat_id = req["chat_id"]
                self.send_message(from_chat_id, f"❌ Request declined.")
                self.send_message(client_chat_id, f"ℹ️ Your audit request could not be processed at this time.")

    async def execute_and_send_audit(self, target_chat_id: str, text: str):
        name = text.replace("http://", "").replace("https://", "").split("/")[0].title()
        profile = StartupProfile(
            name=name,
            category="AI & Tech Venture",
            website=text if text.startswith("http") else f"https://{text.lower()}.ai",
            founders=["Founding Team"],
            stated_mission=f"VC evaluation for {name}",
            target_market="Global Tech Venture Market"
        )

        report = await self.orchestrator.analyze_startup(profile)

        # Save to JSON database
        json_path = os.path.join(os.path.dirname(__file__), "web", "public", "data", "showcase_reports.json")
        json_path_alt = os.path.join(os.path.dirname(__file__), "web", "data", "showcase_reports.json")
        os.makedirs(os.path.dirname(json_path), exist_ok=True)
        os.makedirs(os.path.dirname(json_path_alt), exist_ok=True)

        try:
            if os.path.exists(json_path):
                with open(json_path, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            else:
                existing = []

            # Add or update report
            existing.insert(0, report.dict())
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(existing, f, indent=2, ensure_ascii=False)
            with open(json_path_alt, "w", encoding="utf-8") as f:
                json.dump(existing, f, indent=2, ensure_ascii=False)

            print(f"[Netlify Auto-Publish] Saved report for '{name}'. Publishing to GitHub...")

            # Push update to GitHub for auto-deploy on Netlify
            subprocess.run(
                f'git add web/ && git commit -m "Auto-publish Due Diligence report for {name}" && git push origin main',
                shell=True,
                cwd=os.path.dirname(__file__)
            )

        except Exception as e:
            print(f"[Auto-Publish Error] {e}")

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
            f"👇 <b>View full report with primary evidence sources:</b>"
        )

        inline_keyboard = {
            "inline_keyboard": [
                [{"text": "📊 Open Full Report on Netlify", "url": NETLIFY_BASE_URL}]
            ]
        }

        self.send_message(target_chat_id, teaser, reply_markup=inline_keyboard)

    def run(self):
        if not self.token:
            print("=========================================================================")
            print("ERROR: TELEGRAM_BOT_TOKEN environment variable is missing!")
            print("Please set TELEGRAM_BOT_TOKEN='your_token' and run again.")
            print("=========================================================================\n")
            return

        print(f"=========================================================================")
        print(f"TELEGRAM VC DUE DILIGENCE BOT (ADMIN + AUTO-PUBLISH MODE) IS LIVE...")
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
    bot = TelegramVCBot(TELEGRAM_BOT_TOKEN)
    bot.run()
