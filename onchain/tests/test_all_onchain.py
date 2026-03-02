# ══════════════════════════════════════════════════════════════
# TESTS : OnChain Scripts
# ══════════════════════════════════════════════════════════════

import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "onchain" / "scripts"))
sys.path.insert(0, str(ROOT / "onchain" / "configs"))


class TestOnChainConfigs:
    """Vérifie que les configs On-Chain sont correctes."""

    def test_sniper_config_dry_run(self):
        import config_sniper as cfg
        assert cfg.DRY_RUN is True

    def test_whale_tracker_config_dry_run(self):
        import config_whale_tracker as cfg
        assert cfg.DRY_RUN is True

    def test_index_rebalancer_dry_run(self):
        import config_index_rebalancer as cfg
        assert cfg.DRY_RUN is True

    def test_index_composition_sums_to_100(self):
        import config_index_rebalancer as cfg
        total = sum(cfg.INDEX_COMPOSITION.values())
        assert total == 100, f"INDEX_COMPOSITION sums to {total}, expected 100"


class TestOnChainScripts:
    """Vérifie l'importation et l'initialisation des scripts."""

    def test_sniper_bot_import(self):
        from sniper_bot import SniperBot
        bot = SniperBot()
        assert bot.dry_run is True

    def test_whale_tracker_import(self):
        from whale_tracker import WhaleTracker
        bot = WhaleTracker()
        assert bot.dry_run is True

    def test_index_rebalancer_import(self):
        from index_rebalancer import IndexRebalancer
        bot = IndexRebalancer()
        assert bot.dry_run is True

    def test_index_rebalancer_portfolio_init(self):
        from index_rebalancer import IndexRebalancer
        bot = IndexRebalancer()
        total = sum(bot._holdings.values())
        assert abs(total - bot.total_portfolio) < 1, "Holdings should sum to portfolio value"

    def test_index_rebalancer_deviations(self):
        from index_rebalancer import IndexRebalancer
        bot = IndexRebalancer()
        prices = bot.get_current_prices()
        devs = bot.calculate_deviations(prices)
        # At init, all deviations should be ~0 (no drift yet)
        for pair, dev in devs.items():
            assert abs(dev["deviation"]) < 1, f"{pair} deviation too large at init"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
