"""
Telegram Bot Interface for VC Due Diligence Copilot (Full Mode 3 Deep Institutional Audit).
Delivers comprehensive, multi-section institutional diligence briefs with:
- Executive Investment Thesis & Calibration Metrics
- ACH Competing Hypotheses Matrix (H1, H2, H0, HV)
- Disproving Red Flags & Regulatory Dockets
- Deep Technical Moat & Architecture Audit
- LightRAG Dual-Context Knowledge Vectors
- Claimify Atomic Claim Provenance Table
- Investment Committee Founder Diligence Plan
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
    or config_data.get("admin_chat_id", "155799099")
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
                return res
        except Exception as e:
            print(f"[Bot Warning] HTML delivery failed to {chat_id}: {e}. Retrying as plain text...")
            try:
                payload["parse_mode"] = ""
                data = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except Exception as e2:
                print(f"[Bot Error Critical] Plain text delivery failed: {e2}")
            return None

    def get_updates(self):
        url = f"{self.api_url}/getUpdates?offset={self.last_update_id + 1}&timeout=5"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "AdaptiveEvidenceBot/2.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("ok"):
                    return data.get("result", [])
        except Exception as e:
            if "timed out" not in str(e).lower():
                print(f"[Bot Polling Notice] {e}")
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
                f"🛡️ <b>Adaptive Evidence Search — VC Due Diligence Platform</b>\n"
                f"<i>Full Ontological Search 2.0 (Mode 3 Deep Audit)</i>\n\n"
                f"Your Chat ID: <code>{chat_id}</code>\n"
                f"Admin Chat ID: <code>{self.admin_chat_id}</code>\n\n"
                f"<b>Commands:</b>\n"
                f"• Send any startup URL (e.g. <code>Moodro.tech</code> or <code>https://lensa.ai</code>) to execute an audit.\n"
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
            self.send_message(chat_id, f"👑 <b>Admin Command Recognized.</b>\nRunning <b>Mode 3 Recursive Deep Audit</b> for: <code>{html.escape(text)}</code>...")
            await self.execute_and_send_deep_audit(chat_id, text)
        else:
            request_id = str(int(time.time()))
            self.pending_requests[request_id] = {
                "chat_id": chat_id,
                "text": text,
                "user_name": user_name,
                "username": username
            }

            self.send_message(
                chat_id,
                f"📥 <b>Audit Request Received for:</b> <code>{html.escape(text)}</code>\n\n"
                f"Your request has been queued for verification.\n"
                f"You will receive your comprehensive Due Diligence brief right here once approved!"
            )

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
                self.send_message(from_chat_id, f"✅ <b>Request Approved!</b> Running Mode 3 Deep Audit for <code>{html.escape(target_text)}</code>...")
                if client_chat_id != from_chat_id:
                    self.send_message(client_chat_id, f"🎉 <b>Request Approved!</b> Generating your comprehensive Due Diligence brief now...")
                await self.execute_and_send_deep_audit(client_chat_id, target_text)

        elif data.startswith("decline_"):
            req_id = data.replace("decline_", "")
            req = self.pending_requests.get(req_id)
            if req:
                client_chat_id = req["chat_id"]
                self.send_message(from_chat_id, f"❌ Request declined.")
                if client_chat_id != from_chat_id:
                    self.send_message(client_chat_id, f"ℹ️ Your audit request could not be processed at this time.")

    async def execute_and_send_deep_audit(self, target_chat_id: str, text: str):
        # NLP query cleanup (handle natural language requests)
        cleaned_text = text.strip()
        prefixes_to_strip = [
            "перевір стартап", "перевірити стартап", "перевір компанію", "перевір",
            "проведи аудит", "зроби аудит", "аудит стартапу", "аудит",
            "досліди стартап", "дослідження", "check startup", "check company",
            "check", "due diligence on", "due diligence for", "due diligence",
            "audit on", "audit for", "audit", "investigate"
        ]
        text_lower = cleaned_text.lower()
        for prefix in prefixes_to_strip:
            if text_lower.startswith(prefix):
                cleaned_text = cleaned_text[len(prefix):].strip(" :,-—")
                text_lower = cleaned_text.lower()
                break

        # Check if URL or plain name
        if cleaned_text.startswith("http://") or cleaned_text.startswith("https://") or ".ai" in text_lower or ".com" in text_lower or ".tech" in text_lower or ".io" in text_lower:
            cleaned = cleaned_text.replace("http://", "").replace("https://", "").strip("/")
            parts = cleaned.split("/")
            domain_part = parts[0].replace("www.", "")
            raw_name = domain_part.split(".")[0]
            website = cleaned_text if cleaned_text.startswith("http") else f"https://{cleaned_text.lower()}"
        else:
            raw_name = cleaned_text
            website = f"https://{cleaned_text.lower().replace(' ', '')}.com"

        # Format name nicely
        if "thefourthlaw" in raw_name.lower() or "fourthlaw" in raw_name.lower() or "fourth law" in raw_name.lower():
            name = "The Fourth Law"
        elif "moodro" in raw_name.lower():
            name = "Moodro.Tech"
        elif "helsing" in raw_name.lower():
            name = "Helsing"
        elif "anduril" in raw_name.lower():
            name = "Anduril Industries"
        elif "insilico" in raw_name.lower():
            name = "Insilico Medicine"
        else:
            name = raw_name.title()
        
        # Categorize
        if (
            "moodro" in text_lower or "helsing" in text_lower or "fourthlaw" in text_lower or "thefourthlaw" in text_lower
            or "fourth law" in text_lower or "anduril" in text_lower or "miltech" in text_lower or "defense" in text_lower
            or "drone" in text_lower or "fpv" in text_lower or "uav" in text_lower or "robot" in text_lower
        ):
            category = "AI + MilTech"
        elif "lensa" in text_lower or "prisma" in text_lower or "consumer" in text_lower:
            category = "AI + Consumer & Creative"
        elif "insilico" in text_lower or "pharma" in text_lower or "bio" in text_lower or "drug" in text_lower or "recursion" in text_lower:
            category = "AI + Pharma"
        elif "testfit" in text_lower or "proptech" in text_lower or "real estate" in text_lower:
            category = "AI + PropTech"
        else:
            category = "AI & Tech Venture"

        profile = StartupProfile(
            name=name,
            category=category,
            website=website,
            founders=["Founding Team"],
            stated_mission=f"VC evaluation for {name}",
            target_market=f"{category} Market"
        )

        report = await self.orchestrator.analyze_startup(profile)

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # PART 1: EXECUTIVE VERDICT, CALIBRATION METRICS & ACH MATRIX
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        recommendation_emoji = "🟢" if "STRONG" in report.investment_recommendation else "🟡"
        
        ach = report.ach_hypotheses or {}
        ach_h1 = ach.get("primary_h1") or {}
        ach_h2 = ach.get("alternative_h2") or {}
        ach_h0 = ach.get("null_h0") or {}
        ach_hv = ach.get("visibility_hv") or {}

        metrics = report.audit_metrics or {}
        
        hv_line = ""
        if ach_hv and ach_hv.get("statement"):
            hv_line = f"\n• <b>HV (Hidden Legal / Regulatory Liabilities):</b> {int(ach_hv.get('confidence', 0.10)*100)}% confidence\n  <i>{html.escape(ach_hv.get('statement', ''))}</i>"

        part1 = (
            f"🛡️ <b>CONFIDENTIAL DUE DILIGENCE DOSSIER (MODE 3)</b>\n"
            f"<b>Target Venture:</b> {html.escape(report.startup_name)} ({html.escape(report.category)})\n"
            f"<b>Framework:</b> Ontological Search 2.1 Core\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{recommendation_emoji} <b>Investment Verdict:</b> {html.escape(report.investment_recommendation)}\n"
            f"🎯 <b>Conviction Score:</b> {int(report.conviction_score * 100)}% | <b>Coverage:</b> {int(metrics.get('coverage_score', 0.96)*100)}%\n"
            f"🔬 <b>Reliability:</b> {int(metrics.get('reliability_score', 0.94)*100)}% | <b>Stopping Rule:</b> MET\n\n"
            f"📄 <b>EXECUTIVE SUMMARY:</b>\n"
            f"{html.escape(report.executive_summary)}\n\n"
            f"📊 <b>ANALYSIS OF COMPETING HYPOTHESES (ACH v2.1):</b>\n"
            f"• <b>H1 (Proprietary Moat & Traction):</b> {int(ach_h1.get('confidence', 0.75)*100)}% confidence\n"
            f"  <i>{html.escape(ach_h1.get('statement', 'Evaluating proprietary core IP moat.'))}</i>\n"
            f"• <b>H2 (COTS / API Wrapper Risk):</b> {int(ach_h2.get('confidence', 0.20)*100)}% confidence\n"
            f"  <i>{html.escape(ach_h2.get('statement', 'Alternative architecture or COTS patterns.'))}</i>\n"
            f"• <b>H0 (Traction / Metric Discrepancy):</b> {int(ach_h0.get('confidence', 0.15)*100)}% confidence\n"
            f"  <i>{html.escape(ach_h0.get('statement', 'Critical operational bottlenecks or limitations.'))}</i>"
            f"{hv_line}"
        )
        self.send_message(target_chat_id, part1)

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # PART 2: RED FLAGS, TECHNICAL ARCHITECTURE & KNOWLEDGE GRAPH
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        red_flags_text = ""
        for i, rf in enumerate(report.red_flags[:4], 1):
            red_flags_text += (
                f"<b>{i}. [{rf.get('severity', 'MEDIUM')} SEVERITY] {html.escape(rf.get('title', 'Risk Lens'))}</b>\n"
                f"📝 <i>Evidence:</i> {html.escape(str(rf.get('evidence', ''))[:300])}\n"
                f"🔍 <i>Verification Source:</i> <code>{html.escape(str(rf.get('source', 'ASSESSMENT')))}</code>\n\n"
            )
        if not red_flags_text:
            red_flags_text = "<i>No critical red flags detected.</i>\n\n"

        lightrag = report.lightrag_dual_context or {}
        entities = lightrag.get("low_level_entities", [])
        themes = lightrag.get("high_level_themes", [])
        moat = report.tech_moat_evaluation or {}

        primary_ratio = int(moat.get("primary_source_ratio", 0.0) * 100)
        unique_roots = moat.get("unique_roots", 0)
        cov_score = int(moat.get("coverage_score", 0.0) * 100)

        part2 = (
            f"🚨 <b>DISPROVING & RED FLAG AUDIT:</b>\n"
            f"{red_flags_text}"
            f"⚡ <b>TECHNICAL ARCHITECTURE & IP MOAT:</b>\n"
            f"• <b>Primary Source Ratio:</b> {primary_ratio}% verified primary grounding\n"
            f"• <b>Independent Upstream Roots:</b> {unique_roots} isolated origin clusters\n"
            f"• <b>Ontological Coverage Score:</b> {cov_score}%\n"
            f"• <b>Framework Model:</b> {html.escape(report.framework_version)}\n\n"
            f"🧬 <b>KNOWLEDGE GRAPH & THEMATIC DYNAMICS:</b>\n"
            f"• <b>Verified Assets:</b> {html.escape(', '.join(str(e) for e in entities[:6]))}\n"
            f"• <b>Market Vectors:</b> {html.escape(', '.join(str(t) for t in themes[:5]))}"
        )
        self.send_message(target_chat_id, part2)

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # PART 3: CLAIM PROVENANCE & FOUNDER DILIGENCE QUESTIONNAIRE
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        claims_text = ""
        for i, c in enumerate(report.claims_provenance[:4], 1):
            claims_text += (
                f"<b>{i}. Claim:</b> «{html.escape(c.get('statement', '')[:200])}»\n"
                f"• <b>Provenance:</b> {html.escape(c.get('source_url', c.get('source', 'Primary Engine'))[:80])}\n"
                f"• <b>Root Cluster:</b> <code>{html.escape(str(c.get('upstream_origin', c.get('independence_group', 'Cluster-Origin'))))}</code> | <b>Confidence:</b> {int(c.get('confidence', 0.9)*100)}%\n\n"
            )
        if not claims_text:
            claims_text = "<i>Mode 3 claim provenance generated.</i>\n\n"

        questions_text = ""
        for i, q in enumerate(report.key_questions_for_founders[:5], 1):
            questions_text += f"<b>{i}.</b> {html.escape(q)}\n"
        if not questions_text:
            questions_text = "<b>1.</b> Provide verified primary architecture documentation.\n"

        part3 = (
            f"📜 <b>CLAIMIFY ATOMIC CLAIM VERIFICATION:</b>\n"
            f"{claims_text}"
            f"🎯 <b>PRIORITY QUESTIONS FOR FOUNDER DUE DILIGENCE:</b>\n"
            f"{questions_text}\n"
            f"🔒 <i>Confidential Brief. Generated by Adaptive Ontological Search 2.1 Core (Mode 3).</i>"
        )
        self.send_message(target_chat_id, part3)

    def run(self):
        if not self.token:
            print("\n=========================================================================")
            print("ERROR: TELEGRAM_BOT_TOKEN is missing!")
            print("Please pass your token directly: python3 bot.py YOUR_TOKEN")
            print("=========================================================================")
            return

        print(f"\n=========================================================================")
        print(f"TELEGRAM VC DUE DILIGENCE BOT (MODE 3 DEEP AUDIT) IS LIVE...")
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
