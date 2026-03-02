# ══════════════════════════════════════════════════════════════
# TESTS : Hummingbot Scripts
# ══════════════════════════════════════════════════════════════

import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "hummingbot" / "scripts"))

SCRIPTS_DIR = ROOT / "hummingbot" / "scripts"
CONFIGS_DIR = ROOT / "hummingbot" / "configs"


class TestHummingbotConfigs:
    """Vérifie que tous les fichiers config existent et sont valides."""

    @pytest.mark.parametrize("config_file", [
        "config_arbitrage_spatial.yml",
        "config_arbitrage_triangulaire.yml",
        "config_relative_value.yml",
        "config_market_making.yml",
        "config_vwap_twap.yml",
        "config_order_flow.yml",
    ])
    def test_config_exists(self, config_file):
        assert (CONFIGS_DIR / config_file).exists(), f"Config manquante: {config_file}"

    @pytest.mark.parametrize("config_file", [
        "config_arbitrage_spatial.yml",
        "config_arbitrage_triangulaire.yml",
        "config_relative_value.yml",
        "config_market_making.yml",
        "config_vwap_twap.yml",
        "config_order_flow.yml",
    ])
    def test_config_has_dry_run(self, config_file):
        """Chaque config doit avoir DRY_RUN = true par défaut."""
        import yaml
        with open(CONFIGS_DIR / config_file, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        assert cfg.get("DRY_RUN") is True, f"{config_file} n'a pas DRY_RUN=true"


class TestHummingbotScripts:
    """Vérifie l'importation et la structure des scripts."""

    def test_arbitrage_spatial_import(self):
        from arbitrage_spatial import ArbitrageSpatial
        bot = ArbitrageSpatial()
        assert bot.dry_run is True

    def test_arbitrage_triangulaire_import(self):
        from arbitrage_triangulaire import ArbitrageTriangulaire
        bot = ArbitrageTriangulaire()
        assert bot.dry_run is True

    def test_relative_value_import(self):
        from relative_value_rotation import RelativeValueRotation
        bot = RelativeValueRotation()
        assert bot.dry_run is True

    def test_market_making_import(self):
        from market_making_dex import MarketMakingDEX
        bot = MarketMakingDEX()
        assert bot.dry_run is True

    def test_vwap_twap_import(self):
        from vwap_twap_execution import VWAPTWAPExecution
        bot = VWAPTWAPExecution()
        assert bot.dry_run is True

    def test_order_flow_import(self):
        from order_flow_tracker import OrderFlowTracker
        bot = OrderFlowTracker()
        assert bot.dry_run is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
