# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# SCRIPT    : order_flow_tracker.py
# CATÉGORIE : 3 — Exécution (Order Flow)
# ══════════════════════════════════════════════════════════════
#
# DESCRIPTION :
# Analyse les "murs" dans le carnet d'ordres pour se placer
# stratégiquement devant les grosses pressions acheteuses.
#
# LOGIQUE :
# 1. Lit l'orderbook en profondeur (20+ niveaux)
# 2. Identifie les niveaux avec un volume anormalement élevé (murs)
# 3. Place un ordre JUSTE devant le mur (meilleure priorité)
# 4. Le mur agit comme support → scalp rapide avec SL serré
# ══════════════════════════════════════════════════════════════

import sys
import time
from pathlib import Path
from typing import Optional

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
    config_path = Path(__file__).resolve().parent.parent / "configs" / "config_order_flow.yml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class OrderFlowTracker:
    """
    Order Flow Tracker — Détection de murs et placement stratégique.

    PRINCIPE :
    Un "mur" dans l'orderbook est un niveau de prix avec un volume
    significativement supérieur à la moyenne. Ces murs agissent
    comme des supports (bids) ou résistances (asks) temporaires.
    """

    def __init__(self, config: Optional[dict] = None):
        self.config = config or load_config()
        self.dry_run = self.config.get("DRY_RUN", True)

        self.logger = TradeLogger(strategy_name="OrderFlowTracker")
        self.notifier = TelegramNotifier()
        self.performance = PerformanceTracker(
            "OrderFlowTracker", trade_logger=self.logger,
            telegram_notifier=self.notifier,
        )

        self.exchange = self._init_exchange(self.config.get("exchange", {}))

        # ── Paramètres configurables ──
        self.pairs = self.config.get("pairs", ["BTC/USDT"])
        wall_cfg = self.config.get("wall_detection", {})
        self.min_wall_ratio = wall_cfg.get("min_wall_ratio", 3.0)
        self.depth_levels = wall_cfg.get("depth_levels", 20)

        place_cfg = self.config.get("placement", {})
        self.offset_pct = place_cfg.get("offset_from_wall_pct", 0.05)
        self.order_amount = place_cfg.get("order_amount_usdt", 100)
        self.take_profit_pct = place_cfg.get("take_profit_pct", 0.3)
        self.stop_loss_pct = place_cfg.get("stop_loss_pct", 0.2)

        self.check_interval = self.config.get("check_interval_seconds", 2)

        self.notifier.send_startup_message("OrderFlowTracker", dry_run=self.dry_run)

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
        })

    def detect_walls(self, pair: str) -> list[dict]:
        """
        Détecte les murs dans le carnet d'ordres.

        MÉTHODE :
        1. Récupère l'orderbook avec N niveaux
        2. Calcule le volume moyen par niveau (côté bid)
        3. Un niveau est un "mur" si son volume > moyenne * min_wall_ratio

        Returns:
            Liste de murs détectés avec prix, volume et côté.
        """
        if self.exchange is None:
            return []

        try:
            ob = self.exchange.fetch_order_book(pair, limit=self.depth_levels)
            walls = []

            for side, orders in [("bid", ob.get("bids", [])), ("ask", ob.get("asks", []))]:
                if not orders:
                    continue

                volumes = [level[1] for level in orders]
                avg_volume = np.mean(volumes)

                for price, volume in orders:
                    if volume > avg_volume * self.min_wall_ratio:
                        walls.append({
                            "pair": pair,
                            "side": side,
                            "price": price,
                            "volume": volume,
                            "ratio": volume / avg_volume,
                        })

            return walls

        except Exception as e:
            print(f"[OrderFlow] Erreur detect_walls {pair}: {e}")
            return []

    def place_front_order(self, wall: dict) -> bool:
        """
        Place un ordre juste devant un mur détecté.

        LOGIQUE :
        - Mur BID (support) → acheter juste au-dessus du mur
        - Mur ASK (résistance) → ne pas acheter (obstacle)
        """
        if wall["side"] != "bid":
            return False  # On ne scalpe que devant les supports

        wall_price = wall["price"]
        entry_price = wall_price * (1 + self.offset_pct / 100)

        if self.dry_run:
            amount = self.order_amount / entry_price
            self.logger.log_trade(
                pair=wall["pair"], side="buy", price=entry_price,
                amount=amount, dry_run=True,
                extra_info=f"wall_price:{wall_price:.2f}|ratio:{wall['ratio']:.1f}x",
            )
            self.notifier.send_trade_alert(
                "OrderFlowTracker", wall["pair"], "buy (front-run)",
                entry_price, amount, dry_run=True,
            )
            print(
                f"[DRY_RUN] 🧱 Mur détecté {wall['pair']}: "
                f"{wall['volume']:.2f} @ {wall_price:.2f} ({wall['ratio']:.1f}x avg) | "
                f"→ BUY @ {entry_price:.2f}"
            )
            return True
        return False

    def run(self) -> None:
        """Boucle principale."""
        print(f"📋 OrderFlowTracker démarré | DRY_RUN={self.dry_run}")
        try:
            while True:
                for pair in self.pairs:
                    walls = self.detect_walls(pair)
                    for wall in walls:
                        self.place_front_order(wall)
                time.sleep(self.check_interval)
        except KeyboardInterrupt:
            print("\n⏹ OrderFlowTracker arrêté.")
            self.performance.log_performance()


if __name__ == "__main__":
    bot = OrderFlowTracker()
    bot.run()
