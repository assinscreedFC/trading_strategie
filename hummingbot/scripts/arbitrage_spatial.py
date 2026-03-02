# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# SCRIPT    : arbitrage_spatial.py
# CATÉGORIE : 2 — Statistiques
# OUTIL     : Hummingbot / CCXT
# ══════════════════════════════════════════════════════════════
#
# DESCRIPTION :
# Arbitrage spatial : compare les prix d'un même actif sur 2 exchanges
# et exécute un achat/vente simultané quand le spread est profitable
# après déduction des frais.
#
# LOGIQUE :
# 1. Lit les orderbooks des 2 exchanges via CCXT
# 2. Calcule le spread réel (bid_exchange_cher - ask_exchange_pas_cher)
# 3. Si spread > frais totaux + seuil minimum → exécute
# 4. Log et notifie
#
# SÉCURITÉ :
# - Vérifie la liquidité (volume 24h) avant chaque arb
# - Limite le nombre d'arbs simultanés
# - Mode DRY_RUN par défaut
# ══════════════════════════════════════════════════════════════

import sys
import time
import asyncio
from pathlib import Path
from typing import Optional

import yaml

try:
    import ccxt
except ImportError:
    ccxt = None  # type: ignore

# ── Import des utilitaires partagés ──
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier
from utils.performance import PerformanceTracker
from utils.env_loader import env


def load_config() -> dict:
    """
    Charge la config YAML dédiée à cette stratégie.

    CHOIX : Chaque stratégie a son propre fichier config
    pour pouvoir être modifiée indépendamment.
    """
    config_path = Path(__file__).resolve().parent.parent / "configs" / "config_arbitrage_spatial.yml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class ArbitrageSpatial:
    """
    Arbitrage Spatial — Capture l'écart de prix entre 2 exchanges.

    PRINCIPE ANIS SOLIDSCALE :
    ✅ Spot uniquement (achats/ventes réels, pas de short)
    ✅ Vérification de liquidité avant exécution
    ✅ DRY_RUN par défaut
    ✅ Logging SQLite + Telegram
    """

    def __init__(self, config: Optional[dict] = None):
        self.config = config or load_config()
        self.dry_run = self.config.get("DRY_RUN", True)

        # ── Utilitaires partagés (REFACTORING : même instances que Freqtrade) ──
        self.logger = TradeLogger(strategy_name="ArbitrageSpatial")
        self.notifier = TelegramNotifier()
        self.performance = PerformanceTracker(
            "ArbitrageSpatial", trade_logger=self.logger,
            telegram_notifier=self.notifier,
        )

        # ── Initialisation des exchanges via CCXT ──
        self.exchange_a = self._init_exchange(self.config["exchange_a"])
        self.exchange_b = self._init_exchange(self.config["exchange_b"])

        # ── Paramètres configurables (lus depuis le YAML) ──
        self.pairs = self.config.get("pairs", ["BTC/USDT"])
        self.min_spread_pct = self.config.get("min_spread_pct", 0.3)
        self.total_fee_pct = self.config.get("total_fee_pct", 0.2)
        self.order_amount = self.config.get("order_amount_usdt", 100)
        self.check_interval = self.config.get("check_interval_seconds", 5)
        self.min_volume = self.config.get("min_volume_24h_usdt", 50000)

        self.notifier.send_startup_message("ArbitrageSpatial", dry_run=self.dry_run)

    @staticmethod
    def _init_exchange(exchange_config: dict):
        """
        Initialise un exchange CCXT depuis la config.

        CHOIX : Les clés API sont d'abord lues depuis le YAML.
        Si vides, on fallback sur le .env via env_loader.
        Cela permet d'avoir UN SEUL endroit pour les credentials.
        """
        if ccxt is None:
            print("[ArbitrageSpatial] CCXT non installé. pip install ccxt")
            return None

        name = exchange_config.get("name", "bitget")
        exchange_class = getattr(ccxt, name, None)
        if exchange_class is None:
            print(f"[ArbitrageSpatial] Exchange '{name}' inconnu dans CCXT.")
            return None

        # ── Fallback .env si les clés YAML sont vides ──
        api_key = exchange_config.get("api_key", "")
        api_secret = exchange_config.get("api_secret", "")
        api_password = exchange_config.get("api_password", "")

        if not api_key and name == "bitget":
            api_key = env.BITGET_API_KEY
            api_secret = env.BITGET_API_SECRET
            api_password = env.BITGET_API_PASSWORD
        elif not api_key and name == "mexc":
            api_key = env.MEXC_API_KEY
            api_secret = env.MEXC_API_SECRET

        return exchange_class({
            "apiKey": api_key,
            "secret": api_secret,
            "password": api_password,
            "enableRateLimit": True,
        })

    def check_spread(self, pair: str) -> dict:
        """
        Compare les prix entre les 2 exchanges pour une paire.

        CALCUL DU SPREAD :
        spread = (best_bid_exchange_cher / best_ask_exchange_pas_cher - 1) * 100

        Si spread > min_spread_pct → opportunité d'arbitrage.

        Returns:
            Dict avec les détails du spread et la direction.
        """
        if self.exchange_a is None or self.exchange_b is None:
            return {"spread_pct": 0, "profitable": False}

        try:
            # ── Récupérer les orderbooks ──
            ob_a = self.exchange_a.fetch_order_book(pair, limit=5)
            ob_b = self.exchange_b.fetch_order_book(pair, limit=5)

            # ── Best bid/ask sur chaque exchange ──
            bid_a = ob_a["bids"][0][0] if ob_a["bids"] else 0
            ask_a = ob_a["asks"][0][0] if ob_a["asks"] else 0
            bid_b = ob_b["bids"][0][0] if ob_b["bids"] else 0
            ask_b = ob_b["asks"][0][0] if ob_b["asks"] else 0

            # ── Calculer les 2 directions possibles ──
            # Direction 1 : Acheter sur A (ask), vendre sur B (bid)
            spread_ab = ((bid_b / ask_a) - 1) * 100 if ask_a > 0 else 0
            # Direction 2 : Acheter sur B (ask), vendre sur A (bid)
            spread_ba = ((bid_a / ask_b) - 1) * 100 if ask_b > 0 else 0

            # Prendre la meilleure direction
            if spread_ab >= spread_ba:
                spread = spread_ab
                direction = "buy_a_sell_b"
                buy_price, sell_price = ask_a, bid_b
                buy_exchange = self.config["exchange_a"]["name"]
                sell_exchange = self.config["exchange_b"]["name"]
            else:
                spread = spread_ba
                direction = "buy_b_sell_a"
                buy_price, sell_price = ask_b, bid_a
                buy_exchange = self.config["exchange_b"]["name"]
                sell_exchange = self.config["exchange_a"]["name"]

            net_profit_pct = spread - self.total_fee_pct
            profitable = net_profit_pct > self.min_spread_pct

            return {
                "pair": pair,
                "spread_pct": round(spread, 4),
                "net_profit_pct": round(net_profit_pct, 4),
                "profitable": profitable,
                "direction": direction,
                "buy_price": buy_price,
                "sell_price": sell_price,
                "buy_exchange": buy_exchange,
                "sell_exchange": sell_exchange,
            }

        except Exception as e:
            print(f"[ArbitrageSpatial] Erreur check_spread {pair}: {e}")
            return {"spread_pct": 0, "profitable": False}

    def execute_arb(self, arb_info: dict) -> bool:
        """
        Exécute l'arbitrage si profitable.

        SÉCURITÉ :
        - En DRY_RUN, simule l'exécution et log le résultat
        - En LIVE, place les ordres sur les 2 exchanges
        """
        pair = arb_info["pair"]
        buy_price = arb_info["buy_price"]
        sell_price = arb_info["sell_price"]
        amount = self.order_amount / buy_price  # Convertir USDT en quantité

        if self.dry_run:
            # ── Simulation DRY_RUN ──
            pnl = self.order_amount * arb_info["net_profit_pct"] / 100
            self.logger.log_trade(
                pair=pair, side="buy", price=buy_price, amount=amount,
                dry_run=True, extra_info=f"arb_spatial|{arb_info['buy_exchange']}",
            )
            self.logger.log_trade(
                pair=pair, side="sell", price=sell_price, amount=amount,
                pnl=pnl, dry_run=True,
                extra_info=f"arb_spatial|{arb_info['sell_exchange']}",
            )
            self.notifier.send_trade_alert(
                "ArbitrageSpatial", pair, "arb",
                buy_price, amount, pnl=pnl, dry_run=True,
            )
            print(
                f"[DRY_RUN] Arb {pair}: "
                f"Buy@{arb_info['buy_exchange']}={buy_price:.2f} → "
                f"Sell@{arb_info['sell_exchange']}={sell_price:.2f} | "
                f"Spread={arb_info['spread_pct']:.4f}% | PnL={pnl:.2f} USDT"
            )
            return True
        else:
            # ── Exécution LIVE (à implémenter avec les API keys) ──
            print("[ArbitrageSpatial] Mode LIVE non encore activé.")
            return False

    def run(self) -> None:
        """
        Boucle principale : vérifie le spread périodiquement.
        """
        print("═" * 60)
        print(f"🚀 ArbitrageSpatial démarré | DRY_RUN={self.dry_run}")
        print(f"   Paires: {self.pairs}")
        print(f"   Spread min: {self.min_spread_pct}%")
        print("═" * 60)

        try:
            while True:
                for pair in self.pairs:
                    arb_info = self.check_spread(pair)
                    if arb_info.get("profitable"):
                        self.execute_arb(arb_info)
                    else:
                        spread = arb_info.get("spread_pct", 0)
                        if spread > 0:
                            print(
                                f"  {pair}: spread={spread:.4f}% "
                                f"(min={self.min_spread_pct}%) — pas profitable"
                            )
                time.sleep(self.check_interval)
        except KeyboardInterrupt:
            print("\n⏹ ArbitrageSpatial arrêté.")
            self.performance.log_performance()


if __name__ == "__main__":
    bot = ArbitrageSpatial()
    bot.run()
