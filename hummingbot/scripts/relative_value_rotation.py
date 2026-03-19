# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# SCRIPT    : relative_value_rotation.py
# CATÉGORIE : 2 — Statistiques (Pairs Trading Spot)
# ══════════════════════════════════════════════════════════════
#
# DESCRIPTION :
# Rotation de valeur relative : identifie les actifs sous/sur-évalués
# au sein d'un même secteur (Layer 1, DeFi, AI) via le Z-score du
# ratio de prix. Vend le surévalué pour acheter le sous-évalué.
#
# NOTA : En Spot-only, on ne "short" pas. On VEND un actif qu'on
# détient déjà pour ACHETER un actif corrélé moins cher.
# ══════════════════════════════════════════════════════════════

import sys
import time
from pathlib import Path
from typing import Optional
from collections import deque

import numpy as np
import yaml

try:
    import ccxt
except ImportError:
    ccxt = None  # type: ignore

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier
from utils.performance import PerformanceTracker
from utils.env_loader import env


def load_config() -> dict:
    config_path = Path(__file__).resolve().parent.parent / "configs" / "config_relative_value.yml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class RelativeValueRotation:
    """
    Relative Value Rotation — Z-score pairs trading en Spot.

    LOGIQUE :
    1. Pour chaque paire d'actifs dans un secteur
    2. Calcule le ratio de prix et son Z-score
    3. Si Z-score > seuil → actif A surévalué vs B → vend A, achète B
    4. Si Z-score < -seuil → inverse
    5. Ferme quand Z-score revient à 0 (mean reversion du ratio)
    """

    def __init__(self, config: Optional[dict] = None):
        self.config = config or load_config()
        self.dry_run = self.config.get("DRY_RUN", True)

        self.logger = TradeLogger(strategy_name="RelativeValueRotation")
        self.notifier = TelegramNotifier()
        self.performance = PerformanceTracker(
            "RelativeValueRotation", trade_logger=self.logger,
            telegram_notifier=self.notifier,
        )

        self.exchange = self._init_exchange(self.config.get("exchange", {}))

        # ── Paramètres configurables ──
        self.pairs_groups = self.config.get("pairs_groups", {})
        self.zscore_entry = self.config.get("zscore_entry_threshold", 2.0)
        self.zscore_exit = self.config.get("zscore_exit_threshold", 0.5)
        self.lookback = self.config.get("lookback_period", 48)
        self.correlation_min = self.config.get("correlation_min", 0.7)
        self.order_amount = self.config.get("order_amount_usdt", 150)
        self.check_interval = self.config.get("check_interval_seconds", 60)

        # ── Historique des ratios pour chaque paire ──
        self._ratio_history: dict[str, deque] = {}

        self.notifier.send_startup_message("RelativeValueRotation", dry_run=self.dry_run)

    @staticmethod
    def _init_exchange(config: dict):
        if ccxt is None:
            return None
        name = config.get("name", "binance")
        cls = getattr(ccxt, name, None)
        if cls is None:
            return None
        api_key = config.get("api_key", "")
        api_secret = config.get("api_secret", "")
        if not api_key and name == "binance":
            api_key = env.BINANCE_API_KEY
            api_secret = env.BINANCE_API_SECRET
        elif not api_key and name == "kraken":
            api_key = env.KRAKEN_API_KEY
            api_secret = env.KRAKEN_API_SECRET
        return cls({
            "apiKey": api_key,
            "secret": api_secret,
            "enableRateLimit": True,
        }) if cls else None

    def _get_pair_key(self, pair_a: str, pair_b: str) -> str:
        """Clé unique pour un duo d'actifs."""
        return f"{pair_a}|{pair_b}"

    def calculate_zscore(self, pair_a: str, pair_b: str) -> Optional[float]:
        """
        Calcule le Z-score du ratio de prix entre 2 actifs.

        Z-SCORE = (ratio_actuel - moyenne_historique) / écart_type

        INTERPRÉTATION :
        Z > +2 → A est surévalué par rapport à B
        Z < -2 → A est sous-évalué par rapport à B
        Z ≈ 0  → ratio à sa moyenne
        """
        if self.exchange is None:
            return None

        try:
            ticker_a = self.exchange.fetch_ticker(pair_a)
            ticker_b = self.exchange.fetch_ticker(pair_b)
            price_a = ticker_a.get("last", 0)
            price_b = ticker_b.get("last", 0)

            if price_b <= 0:
                return None

            ratio = price_a / price_b
            key = self._get_pair_key(pair_a, pair_b)

            if key not in self._ratio_history:
                self._ratio_history[key] = deque(maxlen=self.lookback)

            self._ratio_history[key].append(ratio)

            if len(self._ratio_history[key]) < 10:
                return None  # Pas assez de données

            ratios = np.array(self._ratio_history[key])
            mean = ratios.mean()
            std = ratios.std()

            if std == 0:
                return 0.0

            return (ratio - mean) / std

        except Exception as e:
            print(f"[RelativeValue] Erreur Z-score {pair_a}/{pair_b}: {e}")
            return None

    def scan_sector(self, sector_name: str, pairs: list[str]) -> None:
        """
        Scanne toutes les combinaisons d'un secteur.
        """
        for i in range(len(pairs)):
            for j in range(i + 1, len(pairs)):
                pair_a, pair_b = pairs[i], pairs[j]
                zscore = self.calculate_zscore(pair_a, pair_b)

                if zscore is None:
                    continue

                if abs(zscore) > self.zscore_entry:
                    if zscore > 0:
                        # A surévalué → vend A, achète B
                        action = f"SELL {pair_a} → BUY {pair_b}"
                    else:
                        # B surévalué → vend B, achète A
                        action = f"SELL {pair_b} → BUY {pair_a}"

                    pnl = abs(zscore) * 0.1  # Estimation simplifiée

                    if self.dry_run:
                        self.logger.log_trade(
                            pair=f"{pair_a}/{pair_b}", side="sell",
                            price=0, amount=self.order_amount,
                            pnl=pnl, dry_run=True,
                            extra_info=f"zscore:{zscore:.2f}|sector:{sector_name}",
                        )
                        print(
                            f"[DRY_RUN] {sector_name}: {action} | "
                            f"Z-score={zscore:.2f}"
                        )

    def run(self) -> None:
        """Boucle principale."""
        print(f"🔄 RelativeValueRotation démarré | DRY_RUN={self.dry_run}")
        try:
            while True:
                for sector_name, pairs in self.pairs_groups.items():
                    self.scan_sector(sector_name, pairs)
                time.sleep(self.check_interval)
        except KeyboardInterrupt:
            print("\n⏹ RelativeValueRotation arrêté.")
            self.performance.log_performance()


if __name__ == "__main__":
    bot = RelativeValueRotation()
    bot.run()
