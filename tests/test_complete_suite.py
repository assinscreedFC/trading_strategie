# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# TESTS : test_complete_suite.py
# RÔLE  : Test complet unifié de TOUTES les stratégies
# ══════════════════════════════════════════════════════════════
#
# Ce fichier teste l'importation et l'initialisation de chaque
# stratégie sans nécessiter des credentials réels ni des
# connexions aux exchanges.
#
# USAGE :
#   cd ft_userdata
#   python -m pytest tests/test_complete_suite.py -v
# ══════════════════════════════════════════════════════════════

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# ── Ajout des chemins pour imports ──
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "hummingbot" / "scripts"))
sys.path.insert(0, str(ROOT / "onchain" / "scripts"))
sys.path.insert(0, str(ROOT / "onchain" / "configs"))


# ══════════════════════════════════════════════════════════════
# FIXTURES
# ══════════════════════════════════════════════════════════════

def _make_test_dataframe(rows: int = 200) -> pd.DataFrame:
    """Génère un DataFrame OHLCV simulé pour tester les indicateurs."""
    np.random.seed(42)
    base_price = 50000.0
    returns = np.random.normal(0, 0.02, rows)
    close = base_price * np.exp(np.cumsum(returns))
    high = close * (1 + np.abs(np.random.normal(0, 0.01, rows)))
    low = close * (1 - np.abs(np.random.normal(0, 0.01, rows)))
    open_ = close * (1 + np.random.normal(0, 0.005, rows))
    volume = np.random.uniform(100, 10000, rows)

    return pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=rows, freq="1h"),
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    })


# ══════════════════════════════════════════════════════════════
# TESTS — Utilitaires partagés
# ══════════════════════════════════════════════════════════════

class TestEnvLoader:
    """Tests pour env_loader.py."""

    def test_import(self):
        from utils.env_loader import env
        assert env is not None

    def test_properties_exist(self):
        from utils.env_loader import env
        # Toutes les propriétés doivent exister et retourner des strings
        assert isinstance(env.BINANCE_API_KEY, str)
        assert isinstance(env.BINANCE_API_SECRET, str)
        assert isinstance(env.KRAKEN_API_KEY, str)
        assert isinstance(env.KRAKEN_API_SECRET, str)
        assert isinstance(env.TELEGRAM_BOT_TOKEN, str)
        assert isinstance(env.TELEGRAM_CHAT_ID, str)
        assert isinstance(env.ETH_RPC_URL, str)
        assert isinstance(env.ETH_WS_URL, str)
        assert isinstance(env.ETH_PRIVATE_KEY, str)
        assert isinstance(env.ETH_WALLET_ADDRESS, str)
        assert isinstance(env.DEXSCREENER_API_URL, str)

    def test_helpers(self):
        from utils.env_loader import env
        assert isinstance(env.get_binance_config(), dict)
        assert isinstance(env.get_kraken_config(), dict)
        assert isinstance(env.is_telegram_configured(), bool)
        assert isinstance(env.is_blockchain_configured(), bool)


class TestTradeLogger:
    """Tests pour logging_utils.py."""

    def test_creation(self):
        from utils.logging_utils import TradeLogger
        logger = TradeLogger(strategy_name="test_create")
        assert logger.get_trade_count() >= 0

    def test_log_and_read(self):
        from utils.logging_utils import TradeLogger
        logger = TradeLogger(strategy_name="test_log_read_suite")
        logger.log_trade(
            pair="BTC/USDT", side="buy", price=65000.0, amount=0.1,
            fee=0.065, fee_pct=0.1, dry_run=True,
        )
        trades = logger.get_trades(limit=10)
        assert len(trades) >= 1
        assert trades[0]["pair"] == "BTC/USDT"

    def test_get_all_trades(self):
        from utils.logging_utils import TradeLogger
        logger = TradeLogger(strategy_name="test_get_all")
        logger.log_trade(
            pair="ETH/USDT", side="sell", price=3500.0, amount=1.0,
            pnl=50.0, dry_run=True,
        )
        all_trades = logger.get_all_trades()
        assert isinstance(all_trades, list)


class TestTelegramNotifier:
    """Tests pour telegram_notifier.py."""

    def test_disabled_without_credentials(self):
        from utils.telegram_notifier import TelegramNotifier
        notifier = TelegramNotifier()
        assert notifier.enabled is False

    def test_send_message_no_crash(self):
        from utils.telegram_notifier import TelegramNotifier
        notifier = TelegramNotifier()
        result = notifier.send_message("test message")
        assert result is False  # Désactivé sans credentials

    def test_send_trade_alert_no_crash(self):
        from utils.telegram_notifier import TelegramNotifier
        notifier = TelegramNotifier()
        result = notifier.send_trade_alert(
            "TestStrategy", "BTC/USDT", "buy", 65000.0, 0.1, dry_run=True,
        )
        assert result is False

    def test_send_error_alert_no_crash(self):
        from utils.telegram_notifier import TelegramNotifier
        notifier = TelegramNotifier()
        result = notifier.send_error_alert("TestStrategy", "Test error")
        assert result is False

    def test_send_startup_message_no_crash(self):
        from utils.telegram_notifier import TelegramNotifier
        notifier = TelegramNotifier()
        result = notifier.send_startup_message("TestStrategy", dry_run=True)
        assert result is False

    def test_send_performance_report_no_crash(self):
        from utils.telegram_notifier import TelegramNotifier
        notifier = TelegramNotifier()
        result = notifier.send_performance_report(
            "TestStrategy", win_rate=50.0, total_trades=10,
            total_pnl=100.0, max_drawdown=5.0,
        )
        assert result is False


class TestPerformanceTracker:
    """Tests pour performance.py."""

    def test_empty_metrics(self):
        from utils.performance import PerformanceTracker
        tracker = PerformanceTracker("test_empty_suite")
        metrics = tracker.calculate_metrics(trades=[])
        assert metrics["total_trades"] == 0
        assert metrics["win_rate"] == 0.0
        assert metrics["total_pnl"] == 0.0
        assert metrics["max_drawdown"] == 0.0

    def test_metrics_with_data(self):
        from utils.performance import PerformanceTracker
        tracker = PerformanceTracker("test_data")
        trades = [
            {"side": "sell", "pnl": 10.0, "fee": 0.1},
            {"side": "sell", "pnl": -5.0, "fee": 0.1},
            {"side": "sell", "pnl": 20.0, "fee": 0.1},
            {"side": "buy", "pnl": 0.0, "fee": 0.1},  # buy = ignoré pour PnL
        ]
        metrics = tracker.calculate_metrics(trades=trades)
        assert metrics["total_trades"] == 3
        assert metrics["winning_trades"] == 2
        assert metrics["losing_trades"] == 1
        assert metrics["total_pnl"] == 25.0

    def test_log_performance_no_crash(self):
        from utils.performance import PerformanceTracker
        tracker = PerformanceTracker("test_log_perf")
        metrics = tracker.log_performance()
        assert isinstance(metrics, dict)

    def test_generate_weekly_report(self):
        from utils.performance import PerformanceTracker
        tracker = PerformanceTracker("test_report")
        report = tracker.generate_weekly_report(send_telegram=False)
        assert isinstance(report, str)
        assert "test_report" in report


class TestCommonIndicators:
    """Tests pour indicators.py."""

    def test_rsi(self):
        from utils.indicators import CommonIndicators
        df = _make_test_dataframe(100)
        df = CommonIndicators.add_rsi(df, period=14)
        assert "rsi_14" in df.columns
        # RSI doit être entre 0 et 100 (NaN pour les premières lignes)
        valid = df["rsi_14"].dropna()
        assert (valid >= 0).all() and (valid <= 100).all()

    def test_ema(self):
        from utils.indicators import CommonIndicators
        df = _make_test_dataframe(100)
        df = CommonIndicators.add_ema(df, period=50)
        assert "ema_50" in df.columns

    def test_bollinger_bands(self):
        from utils.indicators import CommonIndicators
        df = _make_test_dataframe(100)
        df = CommonIndicators.add_bollinger_bands(df, period=20, std_dev=2.0)
        assert "bb_upper_20" in df.columns
        assert "bb_middle_20" in df.columns
        assert "bb_lower_20" in df.columns

    def test_atr(self):
        from utils.indicators import CommonIndicators
        df = _make_test_dataframe(100)
        df = CommonIndicators.add_atr(df, period=14)
        assert "atr_14" in df.columns

    def test_adx(self):
        from utils.indicators import CommonIndicators
        df = _make_test_dataframe(100)
        df = CommonIndicators.add_adx(df, period=14)
        assert "adx_14" in df.columns

    def test_volume_sma(self):
        from utils.indicators import CommonIndicators
        df = _make_test_dataframe(100)
        df = CommonIndicators.add_volume_sma(df, period=20)
        assert "volume_sma_20" in df.columns
        assert "volume_ratio_20" in df.columns

    def test_breakout_levels(self):
        from utils.indicators import CommonIndicators
        df = _make_test_dataframe(100)
        df = CommonIndicators.add_breakout_levels(df, period=20)
        assert "breakout_high_20" in df.columns
        assert "breakout_low_20" in df.columns

    def test_macd(self):
        from utils.indicators import CommonIndicators
        df = _make_test_dataframe(100)
        df = CommonIndicators.add_macd(df)
        assert "macd" in df.columns
        assert "macd_signal" in df.columns
        assert "macd_histogram" in df.columns

    def test_add_all_basic(self):
        from utils.indicators import CommonIndicators
        df = _make_test_dataframe(200)
        df = CommonIndicators.add_all_basic(df)
        assert "rsi_14" in df.columns
        assert "ema_50" in df.columns
        assert "ema_200" in df.columns
        assert "bb_upper_20" in df.columns
        assert "atr_14" in df.columns
        assert "volume_sma_20" in df.columns


# ══════════════════════════════════════════════════════════════
# TESTS — Hummingbot Scripts (6 scripts)
# ══════════════════════════════════════════════════════════════

class TestHummingbotScripts:
    """Tests d'importation et d'initialisation des scripts Hummingbot."""

    def test_arbitrage_spatial_import(self):
        from hummingbot.scripts.arbitrage_spatial import ArbitrageSpatial
        bot = ArbitrageSpatial()
        assert bot.dry_run is True
        assert isinstance(bot.pairs, list)
        assert len(bot.pairs) > 0

    def test_arbitrage_triangulaire_import(self):
        from hummingbot.scripts.arbitrage_triangulaire import ArbitrageTriangulaire
        bot = ArbitrageTriangulaire()
        assert bot.dry_run is True
        assert isinstance(bot.triangles, list)

    def test_market_making_dex_import(self):
        from hummingbot.scripts.market_making_dex import MarketMakingDEX
        bot = MarketMakingDEX()
        assert bot.dry_run is True
        assert bot.range_width_pct > 0

    def test_order_flow_tracker_import(self):
        from hummingbot.scripts.order_flow_tracker import OrderFlowTracker
        bot = OrderFlowTracker()
        assert bot.dry_run is True
        assert isinstance(bot.pairs, list)
        assert bot.min_wall_ratio > 0

    def test_relative_value_rotation_import(self):
        from hummingbot.scripts.relative_value_rotation import RelativeValueRotation
        bot = RelativeValueRotation()
        assert bot.dry_run is True
        assert isinstance(bot.pairs_groups, dict)
        assert bot.zscore_entry > 0

    def test_vwap_twap_execution_import(self):
        from hummingbot.scripts.vwap_twap_execution import VWAPTWAPExecution
        bot = VWAPTWAPExecution()
        assert bot.dry_run is True
        assert bot.total_amount > 0

    # ── Tests de fonctionnalité basiques ──

    def test_arbitrage_spatial_check_spread_no_exchange(self):
        """check_spread doit gérer gracieusement l'absence d'exchange."""
        from hummingbot.scripts.arbitrage_spatial import ArbitrageSpatial
        bot = ArbitrageSpatial()
        result = bot.check_spread("BTC/USDT")
        assert result["profitable"] is False

    def test_arbitrage_triangulaire_check_no_exchange(self):
        from hummingbot.scripts.arbitrage_triangulaire import ArbitrageTriangulaire
        bot = ArbitrageTriangulaire()
        result = bot.check_triangle({"cycle": ["BTC/USDT", "ETH/BTC", "ETH/USDT"]})
        assert result["profitable"] is False

    def test_order_flow_detect_walls_no_exchange(self):
        from hummingbot.scripts.order_flow_tracker import OrderFlowTracker
        bot = OrderFlowTracker()
        walls = bot.detect_walls("BTC/USDT")
        assert isinstance(walls, list)

    def test_relative_value_zscore_no_exchange(self):
        from hummingbot.scripts.relative_value_rotation import RelativeValueRotation
        bot = RelativeValueRotation()
        result = bot.calculate_zscore("ETH/USDT", "SOL/USDT")
        assert result is None  # Pas d'exchange

    def test_market_making_deploy_position(self):
        from hummingbot.scripts.market_making_dex import MarketMakingDEX
        bot = MarketMakingDEX()
        # get_current_price retourne 0.0 (scaffold)
        price = bot.get_current_price()
        assert price == 0.0

    def test_market_making_rebalance_check(self):
        from hummingbot.scripts.market_making_dex import MarketMakingDEX
        bot = MarketMakingDEX()
        # Pas de rebalance si deviation=0
        assert bot.check_rebalance_needed(100.0, 100.0) is False
        # Rebalance si grande deviation
        assert bot.check_rebalance_needed(110.0, 100.0) is True


# ══════════════════════════════════════════════════════════════
# TESTS — On-Chain Scripts (3 scripts)
# ══════════════════════════════════════════════════════════════

class TestOnChainScripts:
    """Tests d'importation et d'initialisation des scripts On-Chain."""

    def test_sniper_bot_import(self):
        from sniper_bot import SniperBot
        bot = SniperBot()
        assert bot.dry_run is True

    def test_whale_tracker_import(self):
        from whale_tracker import WhaleTracker
        bot = WhaleTracker()
        assert bot.dry_run is True
        assert isinstance(bot.tracked_wallets, dict)

    def test_index_rebalancer_import(self):
        from index_rebalancer import IndexRebalancer
        bot = IndexRebalancer()
        assert bot.dry_run is True

    def test_index_rebalancer_portfolio_init(self):
        from index_rebalancer import IndexRebalancer
        bot = IndexRebalancer()
        total = sum(bot._holdings.values())
        assert abs(total - bot.total_portfolio) < 1

    def test_index_rebalancer_deviations(self):
        from index_rebalancer import IndexRebalancer
        bot = IndexRebalancer()
        prices = bot.get_current_prices()
        devs = bot.calculate_deviations(prices)
        # À l'init, toutes les déviations doivent être ~0
        for pair, dev in devs.items():
            assert abs(dev["deviation"]) < 1, f"{pair} deviation too large at init"

    def test_sniper_bot_execute_dry_run(self):
        from sniper_bot import SniperBot
        bot = SniperBot()
        result = bot.execute_snipe("0x123456", "0x654321")
        assert result is True  # DRY_RUN retourne True

    def test_whale_tracker_no_activity_without_web3(self):
        from whale_tracker import WhaleTracker
        bot = WhaleTracker()
        activities = bot.check_wallet_activity("test", "0x000")
        assert activities == []  # Pas de Web3 connecté


# ══════════════════════════════════════════════════════════════
# TESTS — Configs On-Chain
# ══════════════════════════════════════════════════════════════

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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
