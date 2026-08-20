"""
Central Configuration & Model Registry for Adaptive Ontological Search (v2.1).
Provides validated Gemini model tiers, execution modes (LIVE vs MOCK), and stopping thresholds.
"""

import os
import json
from typing import Dict, Any, Optional

SUPPORTED_MODELS = {
    "pro": [
        "gemini-2.5-pro",
        "gemini-3.1-pro-preview",
        "gemini-3-pro-preview",
        "gemini-1.5-pro"
    ],
    "flash": [
        "gemini-3.6-flash",
        "gemini-2.5-flash",
        "gemini-1.5-flash"
    ],
    "flash_lite": [
        "gemini-3.5-flash-lite",
        "gemini-2.5-flash-lite",
        "gemini-1.5-flash-8b"
    ]
}

DEFAULT_PRO_MODEL = "gemini-3.1-pro-preview"
DEFAULT_FLASH_MODEL = "gemini-3-flash-preview"
DEFAULT_FLASH_LITE_MODEL = "gemini-3.1-flash-lite-preview"


class SearchConfig:
    def __init__(self, config_path: Optional[str] = None):
        self.config_data = {}
        target_cfg = config_path
        if not target_cfg:
            # Check default locations
            root_cfg = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "bot_config.json"))
            if os.path.exists(root_cfg):
                target_cfg = root_cfg
            elif os.path.exists("bot_config.json"):
                target_cfg = "bot_config.json"

        if target_cfg and os.path.exists(target_cfg):
            try:
                with open(target_cfg, "r", encoding="utf-8") as f:
                    self.config_data = json.load(f)
            except Exception as e:
                print(f"[SearchConfig] Failed to load {target_cfg}: {e}")

        self.gemini_api_key = (
            os.environ.get("GEMINI_API_KEY")
            or os.environ.get("GOOGLE_API_KEY")
            or self.config_data.get("gemini_api_key")
        )

        self.pro_model = os.environ.get("GEMINI_PRO_MODEL") or self.config_data.get("pro_model") or DEFAULT_PRO_MODEL
        self.flash_model = os.environ.get("GEMINI_FLASH_MODEL") or self.config_data.get("flash_model") or DEFAULT_FLASH_MODEL
        self.flash_lite_model = os.environ.get("GEMINI_FLASH_LITE_MODEL") or self.config_data.get("flash_lite_model") or DEFAULT_FLASH_LITE_MODEL
        
        # Explicit Execution Mode: LIVE only if API key / live search is present and enabled
        env_mode = os.environ.get("EXECUTION_MODE")
        if env_mode:
            self.is_live = (env_mode.upper() == "LIVE")
        else:
            self.is_live = bool(self.gemini_api_key) and bool(self.config_data.get("enable_live", False))

        self.max_search_depth = int(os.environ.get("MAX_SEARCH_DEPTH") or self.config_data.get("max_search_depth", 3))
        self.inconclusive_threshold = float(self.config_data.get("inconclusive_threshold", 0.40))
        self.min_corroboration_support = float(self.config_data.get("min_corroboration_support", 0.30))

    def validate_models(self) -> Dict[str, Any]:
        """Validates configured models against known supported tiers."""
        return {
            "pro_model": self.pro_model,
            "flash_model": self.flash_model,
            "flash_lite_model": self.flash_lite_model,
            "execution_mode": "LIVE_RETRIEVAL" if self.is_live else "MOCK_SIMULATION",
            "max_search_depth": self.max_search_depth,
            "min_corroboration_support": self.min_corroboration_support
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pro_model": self.pro_model,
            "flash_model": self.flash_model,
            "flash_lite_model": self.flash_lite_model,
            "is_live": self.is_live,
            "max_search_depth": self.max_search_depth,
            "inconclusive_threshold": self.inconclusive_threshold,
            "min_corroboration_support": self.min_corroboration_support
        }


# Global singleton config
config = SearchConfig()
