"""
Manual CLI Audit Runner for Antigravity VC Due Diligence.
Allows you to manually trigger a Mode 3 Due Diligence report for ANY startup directly from your terminal.

Usage:
    python3 run_audit.py "https://lensa.ai"
    python3 run_audit.py "Helsing MilTech"
"""

import sys
import os
import json
import asyncio

sys.path.append(os.path.join(os.path.dirname(__file__), ".agents", "skills", "adaptive-ontological-search", "scripts"))
from vc_due_diligence_orchestrator import VCDueDiligenceOrchestrator, StartupProfile


async def main():
    if len(sys.argv) < 2:
        print("\n=========================================================================")
        print("Usage: python3 run_audit.py <startup_name_or_url>")
        print("Example: python3 run_audit.py 'https://lensa.ai'")
        print("=========================================================================\n")
        sys.exit(1)

    target = sys.argv[1].strip()
    name = target.replace("http://", "").replace("https://", "").split("/")[0].title()
    category = sys.argv[2] if len(sys.argv) > 2 else "AI & Tech Venture"

    print(f"\n=========================================================================")
    print(f"MANUALLY TRIGGERING AUDIT FOR: '{name}'")
    print(f"=========================================================================\n")

    profile = StartupProfile(
        name=name,
        category=category,
        website=target if target.startswith("http") else f"https://{target.lower()}.ai",
        founders=["Founding Team"],
        stated_mission=f"Manual VC evaluation for {name}",
        target_market="Global Tech Venture Market"
    )

    orchestrator = VCDueDiligenceOrchestrator()
    report = await orchestrator.analyze_startup(profile)

    # Save report to JSON dataset
    json_path = os.path.join(os.path.dirname(__file__), "web", "public", "data", "showcase_reports.json")
    os.makedirs(os.path.dirname(json_path), exist_ok=True)

    try:
        if os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                existing_reports = json.load(f)
        else:
            existing_reports = []

        # Prepend new report
        existing_reports.insert(0, report.dict())
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(existing_reports, f, indent=2, ensure_ascii=False)

        print(f"\n✅ AUDIT COMPLETE! Report saved to: {json_path}")
        print(f"📊 Verdict: {report.investment_recommendation}")
        print(f"🎯 Conviction Score: {int(report.conviction_score * 100)}%")
        print(f"🔗 View online at: https://incomparable-chebakia-bb5490.netlify.app/\n")

    except Exception as e:
        print(f"❌ Error saving report JSON: {e}")


if __name__ == "__main__":
    asyncio.run(main())
