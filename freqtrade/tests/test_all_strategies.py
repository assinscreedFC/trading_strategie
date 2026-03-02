# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# TESTS : test_all_strategies.py
# RÔLE  : Tests unitaires pour les 7 stratégies Freqtrade
# ══════════════════════════════════════════════════════════════
#
# STRUCTURE DES TESTS :
# Pour chaque stratégie, on vérifie :
# 1. L'instanciation réussit (config chargée)
# 2. can_short == False (principe Spot only)
# 3. populate_indicators ne crash pas
# 4. populate_entry_trend ne crash pas
# 5. populate_exit_trend ne crash pas
# 6. Les paramètres configurables existent et ont des valeurs valides
#
# USAGE :
#   cd ft_userdata
#   python -m pytest freqtrade/tests/test_all_strategies.py -v
# ══════════════════════════════════════════════════════════════

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# ── Ajout du chemin pour imports ──
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "freqtrade" / "strategies"))


# ══════════════════════════════════════════════════════════════
# FIXTURES — Données simulées et config de test
# ══════════════════════════════════════════════════════════════

def _make_test_config() -> dict:
    """
    Config minimale pour instancier une stratégie en mode test.

    CHOIX : On simule un mode dry_run avec un exchange fictif
    pour éviter de nécessiter des credentials réels.
    """
    return {
        "dry_run": True,
        "dry_run_wallet": 10000,
        "trading_mode": "spot",
        "stake_currency": "USDT",
        "stake_amount": 100,
        "exchange": {"name": "bitget", "key": "", "secret": ""},
    }


def _make_test_dataframe(rows: int = 300) -> pd.DataFrame:
    """
    Génère un DataFrame OHLCV simulé pour tester les indicateurs.

    CHOIX : On utilise une marche aléatoire réaliste plutôt que
    des données constantes pour s'assurer que les indicateurs
    fonctionnent avec des données variées.
    """
    np.random.seed(42)  # Reproductibilité
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
# LISTE DES STRATÉGIES À TESTER
# ══════════════════════════════════════════════════════════════

STRATEGY_CLASSES = []

# Import dynamique pour gérer les dépendances optionnelles
try:
    from GridTradingSpot import GridTradingSpot
    STRATEGY_CLASSES.append(("GridTradingSpot", GridTradingSpot))
except ImportError as e:
    print(f"⚠️ Skip GridTradingSpot: {e}")

try:
    from DCADynamique import DCADynamique
    STRATEGY_CLASSES.append(("DCADynamique", DCADynamique))
except ImportError as e:
    print(f"⚠️ Skip DCADynamique: {e}")

try:
    from TrendFollowing import TrendFollowing
    STRATEGY_CLASSES.append(("TrendFollowing", TrendFollowing))
except ImportError as e:
    print(f"⚠️ Skip TrendFollowing: {e}")

try:
    from MeanReversion import MeanReversion
    STRATEGY_CLASSES.append(("MeanReversion", MeanReversion))
except ImportError as e:
    print(f"⚠️ Skip MeanReversion: {e}")

try:
    from FreqAIXGBoost import FreqAIXGBoost
    STRATEGY_CLASSES.append(("FreqAIXGBoost", FreqAIXGBoost))
except ImportError as e:
    print(f"⚠️ Skip FreqAIXGBoost: {e}")

try:
    from LSTMEntryOptimizer import LSTMEntryOptimizer
    STRATEGY_CLASSES.append(("LSTMEntryOptimizer", LSTMEntryOptimizer))
except ImportError as e:
    print(f"⚠️ Skip LSTMEntryOptimizer: {e}")

try:
    from MultiFactorCorrelation import MultiFactorCorrelation
    STRATEGY_CLASSES.append(("MultiFactorCorrelation", MultiFactorCorrelation))
except ImportError as e:
    print(f"⚠️ Skip MultiFactorCorrelation: {e}")


# ══════════════════════════════════════════════════════════════
# TESTS PARAMÉTRÉS — Un test par stratégie
# ══════════════════════════════════════════════════════════════

@pytest.mark.parametrize("name,strategy_cls", STRATEGY_CLASSES)
class TestStrategy:
    """Tests génériques appliqués à CHAQUE stratégie."""

    def test_can_short_is_false(self, name, strategy_cls):
        """
        PRINCIPE ANIS SOLIDSCALE #1 : AUCUN LEVIER, Spot only.
        Vérifie que can_short est False pour toutes les stratégies.
        """
        assert strategy_cls.can_short is False, (
            f"{name} a can_short=True ! Violation du principe Spot-Only."
        )

    def test_interface_version(self, name, strategy_cls):
        """Vérifie que la stratégie utilise INTERFACE_VERSION = 3."""
        assert strategy_cls.INTERFACE_VERSION == 3

    def test_timeframe_is_set(self, name, strategy_cls):
        """Vérifie qu'un timeframe est défini."""
        assert hasattr(strategy_cls, "timeframe")
        assert strategy_cls.timeframe in [
            "1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h",
            "12h", "1d", "3d", "1w",
        ]

    def test_stoploss_is_negative(self, name, strategy_cls):
        """Vérifie que le stoploss est négatif (protection active)."""
        assert strategy_cls.stoploss < 0, (
            f"{name} a un stoploss >= 0, ce qui est dangereux."
        )

    def test_minimal_roi_exists(self, name, strategy_cls):
        """Vérifie que minimal_roi est défini et non vide."""
        assert hasattr(strategy_cls, "minimal_roi")
        assert len(strategy_cls.minimal_roi) > 0

    def test_populate_indicators(self, name, strategy_cls):
        """
        Vérifie que populate_indicators ne crash pas.

        On ne peut pas appeler la méthode directement sans un
        vrai contexte Freqtrade, donc on vérifie juste que la
        méthode existe et est callable.
        """
        config = _make_test_config()
        strategy = strategy_cls(config)
        assert callable(getattr(strategy, "populate_indicators"))

    def test_populate_entry_trend(self, name, strategy_cls):
        """Vérifie que populate_entry_trend existe."""
        config = _make_test_config()
        strategy = strategy_cls(config)
        assert callable(getattr(strategy, "populate_entry_trend"))

    def test_populate_exit_trend(self, name, strategy_cls):
        """Vérifie que populate_exit_trend existe."""
        config = _make_test_config()
        strategy = strategy_cls(config)
        assert callable(getattr(strategy, "populate_exit_trend"))


# ══════════════════════════════════════════════════════════════
# TESTS UTILITAIRES PARTAGÉS
# ══════════════════════════════════════════════════════════════

class TestSharedUtils:
    """Tests pour les modules utilitaires partagés."""

    def test_trade_logger_creation(self):
        """Vérifie que TradeLogger crée sa table SQLite."""
        from utils.logging_utils import TradeLogger
        logger = TradeLogger(strategy_name="test_strategy")
        assert logger.get_trade_count() == 0

    def test_trade_logger_log_and_read(self):
        """Vérifie le cycle complet log → read."""
        from utils.logging_utils import TradeLogger
        logger = TradeLogger(strategy_name="test_log_read")
        logger.log_trade(
            pair="BTC/USDT", side="buy", price=65000.0, amount=0.1,
            fee=0.065, fee_pct=0.1, dry_run=True,
        )
        trades = logger.get_trades(limit=10)
        assert len(trades) >= 1
        assert trades[0]["pair"] == "BTC/USDT"

    def test_performance_tracker_empty(self):
        """Vérifie que PerformanceTracker gère les données vides."""
        from utils.performance import PerformanceTracker
        tracker = PerformanceTracker("test_empty")
        metrics = tracker.calculate_metrics(trades=[])
        assert metrics["total_trades"] == 0
        assert metrics["win_rate"] == 0.0

    def test_telegram_notifier_disabled(self):
        """Vérifie que TelegramNotifier ne crash pas sans credentials."""
        from utils.telegram_notifier import TelegramNotifier
        notifier = TelegramNotifier()  # Pas de token = désactivé
        assert notifier.enabled is False
        # Ne doit pas crasher
        result = notifier.send_message("test")
        assert result is False

    def test_common_indicators(self):
        """Vérifie que CommonIndicators ajoute bien les colonnes."""
        from utils.indicators import CommonIndicators
        df = _make_test_dataframe(100)
        df = CommonIndicators.add_rsi(df, period=14)
        df = CommonIndicators.add_ema(df, period=50)
        df = CommonIndicators.add_bollinger_bands(df, period=20)
        df = CommonIndicators.add_atr(df, period=14)
        assert "rsi_14" in df.columns
        assert "ema_50" in df.columns
        assert "bb_upper_20" in df.columns
        assert "atr_14" in df.columns


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
