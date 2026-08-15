"""
Mock Startup Profile Test Fixtures.
Explicitly tagged for MOCK testing and benchmark verification only.
"""

from dataclasses import dataclass
from typing import List


@dataclass
class MockStartupProfile:
    name: str
    category: str
    website: str
    founders: List[str]
    stated_mission: str
    target_market: str
    is_mock_fixture: bool = True


MOCK_MILTECH_PROFILE = MockStartupProfile(
    name="Moodro MilTech",
    category="AI + MilTech & Defense",
    website="https://moodro-defense.local",
    founders=["Col. R. Vance", "Dr. A. Stone"],
    stated_mission="Autonomous electronic warfare & GPS-denied UAV navigation",
    target_market="Defense & Aerospace UAV Fleets"
)

MOCK_CONSUMER_LENSA_PROFILE = MockStartupProfile(
    name="Lensa AI",
    category="AI + Consumer & Creative",
    website="https://lensa-ai.local",
    founders=["Alexey Moiseenkov", "Prisma Labs Team"],
    stated_mission="AI-powered photo and video editing & Magic Avatars",
    target_market="Consumer Generative AI & Mobile Media"
)

MOCK_PHARMA_PROFILE = MockStartupProfile(
    name="Insilico Pharma",
    category="AI + Pharma & Biotech",
    website="https://insilico-pharma.local",
    founders=["Dr. Alex Zhavoronkov"],
    stated_mission="Generative small-molecule oncology drug discovery",
    target_market="Oncology & Rare Disease Therapeutics"
)

MOCK_PROPTECH_PROFILE = MockStartupProfile(
    name="PropTech AI",
    category="AI + PropTech",
    website="https://proptech-zoning.local",
    founders=["E. Harrison"],
    stated_mission="Generative zoning feasibility and MLS spatial property valuation",
    target_market="Commercial & Residential Real Estate Development"
)

ALL_MOCK_PROFILES = [
    MOCK_MILTECH_PROFILE,
    MOCK_CONSUMER_LENSA_PROFILE,
    MOCK_PHARMA_PROFILE,
    MOCK_PROPTECH_PROFILE
]
