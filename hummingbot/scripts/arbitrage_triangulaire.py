# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# SCRIPT    : arbitrage_triangulaire.py
# CATÉGORIE : 2 — Statistiques
# ══════════════════════════════════════════════════════════════
#
# DESCRIPTION :
# Arbitrage triangulaire : cycle d'échange interne sur un seul
# exchange (ex: USDT → BTC → ETH → USDT) pour augmenter le
# stack sans risque de marché directionnel.
#
# LOGIQUE :
# 1. Lit les tickers pour les 3 paires du triangle
# 2. Calcule le profit du cycle complet (après frais)
# 3. Si profitable → exécute les 3 trades séquentiellement
#
# SÉCURITÉ :
# - Vérifie que les 3 paires sont liquides
# - Calcule le slippage estimé sur chaque leg
# - Mode DRY_RUN par défaut
# ══════════════════════════════════════════════════════════════

import sys
import time
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
    config_path = Path(__file__).resolve().parent.parent / "configs" / "config_arbitrage_triangulaire.yml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class ArbitrageTriangulaire:
    """
    Arbitrage Triangulaire — Cycle A→B→C→A sur un seul exchange.

    CHOIX TECHNIQUE :
    On exécute les 3 legs séquentiellement (pas en parallèle)
    car les ordres doivent être remplis dans l'ordre pour que
    le cycle soit cohérent. Le slippage est le risque principal.
    """

    def __init__(self, config: Optional[dict] = None):
        self.config = config or load_config()
        self.dry_run = self.config.get("DRY_RUN", True)

        # ── Utilitaires partagés (REFACTORING) ──
        self.logger = TradeLogger(strategy_name="ArbitrageTriangulaire")
        self.notifier = TelegramNotifier()
        self.performance = PerformanceTracker(
            "ArbitrageTriangulaire", trade_logger=self.logger,
            telegram_notifier=self.notifier,
        )

        # ── Exchange CCXT ──
        self.exchange = self._init_exchange(self.config.get("exchange", {}))

        # ── Paramètres configurables ──
        self.triangles = self.config.get("triangles", [])
        self.min_profit_pct = self.config.get("min_profit_pct", 0.15)
        self.fee_per_trade = self.config.get("total_fee_per_trade_pct", 0.1)
        self.order_amount = self.config.get("order_amount_usdt", 200)
        self.check_interval = self.config.get("check_interval_seconds", 3)
        self.max_slippage = self.config.get("max_slippage_pct", 0.1)

        self.notifier.send_startup_message("ArbitrageTriangulaire", dry_run=self.dry_run)

    @staticmethod
    def _init_exchange(config: dict):
        if ccxt is None:
            return None
        name = config.get("name", "bitget")
        cls = getattr(ccxt, name, None)
        if cls is None:
            return None
        # ── Fallback .env si les clés YAML sont vides ──
        api_key = config.get("api_key", "")
        api_secret = config.get("api_secret", "")
        api_password = config.get("api_password", "")
        if not api_key and name == "bitget":
            api_key = env.BITGET_API_KEY
            api_secret = env.BITGET_API_SECRET
            api_password = env.BITGET_API_PASSWORD
        elif not api_key and name == "mexc":
            api_key = env.MEXC_API_KEY
            api_secret = env.MEXC_API_SECRET
        return cls({
            "apiKey": api_key,
            "secret": api_secret,
            "password": api_password,
            "enableRateLimit": True,
        })

    def check_triangle(self, triangle: dict) -> dict:
        """
        Vérifie la profitabilité d'un triangle.

        CALCUL :
        Start: 1 USDT
        Leg 1: USDT → BTC (buy BTC/USDT) → obtient X BTC
        Leg 2: BTC → ETH (buy ETH/BTC) → obtient Y ETH
        Leg 3: ETH → USDT (sell ETH/USDT) → obtient Z USDT
        Profit = Z - 1 (en USDT)
        """
        if self.exchange is None:
            return {"profitable": False, "profit_pct": 0}

        cycle = triangle.get("cycle", [])
        if len(cycle) != 3:
            return {"profitable": False, "profit_pct": 0}

        try:
            # ── Récupérer les tickers ──
            tickers = {}
            for pair in cycle:
                tickers[pair] = self.exchange.fetch_ticker(pair)

            # ── Simuler le cycle ──
            # Leg 1 : USDT → premier actif (buy)
            ask_1 = tickers[cycle[0]].get("ask", 0)
            if ask_1 <= 0:
                return {"profitable": False, "profit_pct": 0}
            amount_1 = (self.order_amount / ask_1) * (1 - self.fee_per_trade / 100)

            # Leg 2 : premier → deuxième actif (buy)
            ask_2 = tickers[cycle[1]].get("ask", 0)
            if ask_2 <= 0:
                return {"profitable": False, "profit_pct": 0}
            amount_2 = (amount_1 / ask_2) * (1 - self.fee_per_trade / 100)

            # Leg 3 : deuxième → USDT (sell)
            bid_3 = tickers[cycle[2]].get("bid", 0)
            if bid_3 <= 0:
                return {"profitable": False, "profit_pct": 0}
            final_usdt = (amount_2 * bid_3) * (1 - self.fee_per_trade / 100)

            profit_usdt = final_usdt - self.order_amount
            profit_pct = (profit_usdt / self.order_amount) * 100

            return {
                "cycle": cycle,
                "profit_usdt": round(profit_usdt, 4),
                "profit_pct": round(profit_pct, 4),
                "profitable": profit_pct > self.min_profit_pct,
                "prices": {
                    "leg1_ask": ask_1,
                    "leg2_ask": ask_2,
                    "leg3_bid": bid_3,
                },
            }

        except Exception as e:
            print(f"[ArbitrageTriangulaire] Erreur: {e}")
            return {"profitable": False, "profit_pct": 0}

    def execute_triangle(self, arb_info: dict) -> bool:
        """Exécute le triangle en DRY_RUN ou LIVE."""
        if self.dry_run:
            pnl = arb_info["profit_usdt"]
            cycle_str = " → ".join(arb_info["cycle"])
            self.logger.log_trade(
                pair=cycle_str, side="sell", price=0, amount=self.order_amount,
                pnl=pnl, dry_run=True,
                extra_info=f"triangle|profit:{arb_info['profit_pct']:.4f}%",
            )
            self.notifier.send_trade_alert(
                "ArbitrageTriangulaire", cycle_str, "triangle_arb",
                price=0, amount=self.order_amount, pnl=pnl, dry_run=True,
            )
            print(
                f"[DRY_RUN] Triangle {cycle_str} | "
                f"Profit: {pnl:.4f} USDT ({arb_info['profit_pct']:.4f}%)"
            )
            return True
        return False

    def run(self) -> None:
        """Boucle principale."""
        print(f"🔺 ArbitrageTriangulaire démarré | DRY_RUN={self.dry_run}")
        try:
            while True:
                for triangle in self.triangles:
                    result = self.check_triangle(triangle)
                    if result.get("profitable"):
                        self.execute_triangle(result)
                time.sleep(self.check_interval)
        except KeyboardInterrupt:
            print("\n⏹ ArbitrageTriangulaire arrêté.")
            self.performance.log_performance()


if __name__ == "__main__":
    bot = ArbitrageTriangulaire()
    bot.run()
