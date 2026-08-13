"""
Showcase Lead Magnet Generator for VC Due Diligence Copilot.
Generates 4 full Mode 3 Due Diligence reports for:
1. AI + MilTech: Helsing
2. AI + Pharma: Insilico Medicine
3. AI + PropTech: TestFit
4. AI + Consumer & Creative: Lensa AI (Prisma Labs)
"""

import asyncio
import json
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".agents", "skills", "adaptive-ontological-search", "scripts"))

from vc_due_diligence_orchestrator import VCDueDiligenceOrchestrator, StartupProfile


async def generate_showcases():
    orchestrator = VCDueDiligenceOrchestrator()

    startups = [
        StartupProfile(
            name="Helsing",
            category="AI + MilTech",
            website="https://helsing.ai",
            founders=["Gundbert Scherf", "Torsten Reil", "Niklas Köhler"],
            stated_mission="Live data processing and autonomous sensor fusion for defense and electronic warfare superiority.",
            target_market="NATO Governments, Defense Procurement Agencies, Prime Contractors"
        ),
        StartupProfile(
            name="Insilico Medicine",
            category="AI + Pharma",
            website="https://insilico.com",
            founders=["Alex Zhavoronkov"],
            stated_mission="Accelerating drug discovery using end-to-end generative AI and biology target identification.",
            target_market="Global Pharmaceutical Enterprise, Biotech R&D Labs"
        ),
        StartupProfile(
            name="TestFit",
            category="AI + PropTech",
            website="https://testfit.io",
            founders=["Clifton Harness", "Ryan Griege"],
            stated_mission="Automating real estate site planning, spatial 3D feasibility studies, and commercial property valuation.",
            target_market="Real Estate Developers, Architects, Urban Planners, Property Funds"
        ),
        StartupProfile(
            name="Lensa AI (Prisma Labs)",
            category="AI + Consumer & Creative",
            website="https://prisma-labs.co/lensa",
            founders=["Andrey Usoltsev", "Alexey Moiseenkov"],
            stated_mission="AI-powered mobile photo/video editing and portrait avatar generation.",
            target_market="Consumer Mobile Users, Creators, Digital Artists"
        )
    ]

    results = []

    print("=========================================================================")
    print("GENERATING 4 SHOWCASE LEAD MAGNET REPORTS FOR LINKEDIN MARKETING")
    print("=========================================================================\n")

    for startup in startups:
        report = await orchestrator.analyze_startup(startup)
        results.append(report.dict())

    # Save to JSON database file for the Web Viewer
    output_dir = os.path.join(os.path.dirname(__file__), "web", "public", "data")
    os.makedirs(output_dir, exist_ok=True)
    json_path = os.path.join(output_dir, "showcase_reports.json")
    
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n=========================================================================")
    print(f"SUCCESSFULLY GENERATED 4 SHOWCASE REPORTS AT: {json_path}")
    print(f"=========================================================================\n")


if __name__ == "__main__":
    asyncio.run(generate_showcases())
