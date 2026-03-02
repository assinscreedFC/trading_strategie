# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# SCRIPT    : vwap_twap_execution.py
# CATÉGORIE : 3 — Exécution
# ══════════════════════════════════════════════════════════════
#
# DESCRIPTION :
# VWAP/TWAP : Algorithmes de fractionnement d'ordres pour accumuler
# de grosses positions sans impacter le marché ("pump" le prix).
#
# TWAP : Découpe l'ordre en N tranches exécutées à intervalles réguliers
# VWAP : Adapte la taille de chaque tranche au volume du marché
# ══════════════════════════════════════════════════════════════

import sys
import time
import random
from pathlib import Path
from typing import Optional

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
    config_path = Path(__file__).resolve().parent.parent / "configs" / "config_vwap_twap.yml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class VWAPTWAPExecution:
    """
    VWAP/TWAP Execution — Fractionnement intelligent d'ordres.

    CHOIX TWAP vs VWAP :
    - TWAP : Plus simple, adapté aux marchés avec volume stable
    - VWAP : Plus intelligent, adapte la taille aux conditions de marché
    - Les deux peuvent fonctionner ensemble
    """

    def __init__(self, config: Optional[dict] = None):
        self.config = config or load_config()
        self.dry_run = self.config.get("DRY_RUN", True)

        self.logger = TradeLogger(strategy_name="VWAPTWAPExecution")
        self.notifier = TelegramNotifier()
        self.performance = PerformanceTracker(
            "VWAPTWAPExecution", trade_logger=self.logger,
            telegram_notifier=self.notifier,
        )

        self.exchange = self._init_exchange(self.config.get("exchange", {}))

        # ── Paramètres de l'ordre ──
        order_cfg = self.config.get("order", {})
        self.pair = order_cfg.get("pair", "BTC/USDT")
        self.side = order_cfg.get("side", "buy")
        self.total_amount = order_cfg.get("total_amount", 0.5)

        # ── Paramètres TWAP ──
        twap_cfg = self.config.get("twap", {})
        self.twap_enabled = twap_cfg.get("enabled", True)
        self.twap_slices = twap_cfg.get("num_slices", 20)
        self.twap_interval = twap_cfg.get("interval_seconds", 300)
        self.twap_randomize = twap_cfg.get("randomize_time", True)
        self.twap_rand_range = twap_cfg.get("randomize_range_pct", 20)

        # ── Paramètres VWAP ──
        vwap_cfg = self.config.get("vwap", {})
        self.vwap_enabled = vwap_cfg.get("enabled", False)
        self.vwap_participation = vwap_cfg.get("target_participation_pct", 5.0)
        self.vwap_lookback = vwap_cfg.get("lookback_candles", 20)

        # ── Limites ──
        self.max_slippage = self.config.get("max_slippage_pct", 0.3)
        self.price_limit_pct = self.config.get("price_limit_pct", 0.5)

        self.notifier.send_startup_message("VWAPTWAPExecution", dry_run=self.dry_run)

    @staticmethod
    def _init_exchange(config: dict):
        if ccxt is None:
            return None
        name = config.get("name", "mexc")
        cls = getattr(ccxt, name, None)
        if cls is None:
            return None
        api_key = config.get("api_key", "")
        api_secret = config.get("api_secret", "")
        if not api_key and name == "mexc":
            api_key = env.MEXC_API_KEY
            api_secret = env.MEXC_API_SECRET
        elif not api_key and name == "bitget":
            api_key = env.BITGET_API_KEY
            api_secret = env.BITGET_API_SECRET
        return cls({
            "apiKey": api_key,
            "secret": api_secret,
            "enableRateLimit": True,
        })

    def execute_twap(self) -> None:
        """
        TWAP : découpe l'ordre en tranches temporelles égales.

        CHOIX : Ajouter du bruit aléatoire sur le timing empêche
        les autres bots de détecter un pattern d'accumulation.
        """
        slice_amount = self.total_amount / self.twap_slices
        executed = 0
        total_cost = 0.0

        print(f"📊 TWAP: {self.total_amount} {self.pair} en {self.twap_slices} tranches")

        for i in range(self.twap_slices):
            try:
                # ── Récupérer le prix actuel ──
                if self.exchange:
                    ticker = self.exchange.fetch_ticker(self.pair)
                    price = ticker.get("last", 0)
                else:
                    price = 65000.0  # Fallback pour DRY_RUN sans exchange

                if self.dry_run:
                    cost = slice_amount * price
                    total_cost += cost
                    executed += slice_amount

                    self.logger.log_trade(
                        pair=self.pair, side=self.side, price=price,
                        amount=slice_amount, dry_run=True,
                        extra_info=f"TWAP_slice_{i+1}/{self.twap_slices}",
                    )
                    print(
                        f"  [TWAP {i+1}/{self.twap_slices}] "
                        f"{self.side.upper()} {slice_amount:.6f} @ {price:.2f} "
                        f"({executed/self.total_amount*100:.1f}% done)"
                    )

                # ── Attente avec bruit aléatoire ──
                if i < self.twap_slices - 1:
                    wait = self.twap_interval
                    if self.twap_randomize:
                        noise = wait * self.twap_rand_range / 100
                        wait += random.uniform(-noise, noise)
                    time.sleep(max(1, wait))

            except Exception as e:
                print(f"  [TWAP] Erreur slice {i+1}: {e}")
                self.notifier.send_error_alert("VWAPTWAPExecution", str(e))

        # ── Résumé ──
        avg_price = total_cost / executed if executed > 0 else 0
        print(
            f"✅ TWAP terminé: {executed:.6f} {self.pair} | "
            f"Prix moyen: {avg_price:.2f}"
        )
        self.performance.log_performance()

    def execute_vwap(self) -> None:
        """
        VWAP : adapte la taille de chaque tranche au volume du marché.

        LOGIQUE : On ne veut pas représenter plus de X% du volume
        d'une bougie pour éviter d'impacter le prix.
        """
        remaining = self.total_amount
        total_cost = 0.0

        print(f"📊 VWAP: {self.total_amount} {self.pair} | "
              f"Participation max: {self.vwap_participation}%")

        while remaining > 0:
            try:
                if self.exchange:
                    ticker = self.exchange.fetch_ticker(self.pair)
                    price = ticker.get("last", 0)
                    volume_24h = ticker.get("quoteVolume", 0)
                    # Volume moyen par 5min (approximation)
                    volume_5min = volume_24h / (24 * 12) if volume_24h else 1000
                else:
                    price = 65000.0
                    volume_5min = 100000

                # ── Taille de la tranche = X% du volume 5min ──
                max_slice_usdt = volume_5min * self.vwap_participation / 100
                max_slice_amount = max_slice_usdt / price if price > 0 else 0
                slice_amount = min(remaining, max_slice_amount)

                if slice_amount <= 0:
                    time.sleep(60)
                    continue

                if self.dry_run:
                    cost = slice_amount * price
                    total_cost += cost
                    remaining -= slice_amount

                    self.logger.log_trade(
                        pair=self.pair, side=self.side, price=price,
                        amount=slice_amount, dry_run=True,
                        extra_info=f"VWAP|remaining:{remaining:.6f}",
                    )
                    print(
                        f"  [VWAP] {self.side.upper()} {slice_amount:.6f} @ {price:.2f} | "
                        f"Remaining: {remaining:.6f}"
                    )

                time.sleep(300 + random.uniform(-60, 60))

            except Exception as e:
                print(f"  [VWAP] Erreur: {e}")
                time.sleep(30)

        executed = self.total_amount
        avg_price = total_cost / executed if executed > 0 else 0
        print(f"✅ VWAP terminé | Prix moyen: {avg_price:.2f}")
        self.performance.log_performance()

    def run(self) -> None:
        """Point d'entrée principal."""
        print(f"📦 VWAPTWAPExecution | DRY_RUN={self.dry_run}")
        if self.twap_enabled:
            self.execute_twap()
        elif self.vwap_enabled:
            self.execute_vwap()
        else:
            print("⚠️ Ni TWAP ni VWAP activé dans la config.")


if __name__ == "__main__":
    bot = VWAPTWAPExecution()
    bot.run()
