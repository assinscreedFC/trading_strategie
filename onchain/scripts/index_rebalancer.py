# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# SCRIPT    : index_rebalancer.py
# CATÉGORIE : 4 — On-Chain (Smart Money)
# ══════════════════════════════════════════════════════════════
#
# DESCRIPTION :
# Gestion d'un panier d'actifs thématique avec rééquilibrage
# automatique des poids pour maintenir l'exposition cible.
#
# LOGIQUE :
# 1. Récupère les prix actuels de chaque actif du panier
# 2. Calcule la valeur de chaque position vs poids cible
# 3. Si déviation > seuil → vend le surpondéré, achète le sous-pondéré
# ══════════════════════════════════════════════════════════════

import sys
import time
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "configs"))
import config_index_rebalancer as cfg

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier
from utils.performance import PerformanceTracker

try:
    import ccxt
except ImportError:
    ccxt = None  # type: ignore


class IndexRebalancer:
    """
    Index Rebalancer — Rééquilibrage automatique de panier crypto.

    LOGIQUE :
    1. Portfolio = {BTC: 30%, ETH: 25%, SOL: 15%, ...}
    2. Chaque cycle : vérifier si un actif a dévié de son poids cible
    3. Exemple : BTC a monté et représente maintenant 35% → vendre 5%
       et redistribuer aux actifs sous-pondérés

    AVANTAGE :
    - Prend les profits mécaniquement (vend le gagnant)
    - Achète les dips mécaniquement (renforce le perdant)
    - Discipline émotionnelle automatisée
    """

    def __init__(self):
        self.dry_run = cfg.DRY_RUN

        self.logger = TradeLogger(strategy_name="IndexRebalancer")
        self.notifier = TelegramNotifier()
        self.performance = PerformanceTracker(
            "IndexRebalancer", trade_logger=self.logger,
            telegram_notifier=self.notifier,
        )

        # ── Exchange CCXT ──
        self.exchange = None
        if ccxt and cfg.EXCHANGE:
            cls = getattr(ccxt, cfg.EXCHANGE, None)
            if cls:
                self.exchange = cls({
                    "apiKey": cfg.API_KEY,
                    "secret": cfg.API_SECRET,
                    "password": getattr(cfg, "API_PASSWORD", ""),
                    "enableRateLimit": True,
                })

        # ── Paramètres (depuis config) ──
        self.composition = cfg.INDEX_COMPOSITION
        self.total_portfolio = cfg.TOTAL_PORTFOLIO_USDT
        self.rebalance_threshold = cfg.REBALANCE_THRESHOLD_PCT
        self.rebalance_interval = cfg.REBALANCE_INTERVAL_HOURS * 3600
        self.min_trade = cfg.MIN_TRADE_USDT
        self.fee_pct = cfg.ESTIMATED_FEE_PCT

        # ── Holdings simulés (initialisés à la composition cible) ──
        self._holdings: dict[str, float] = {}
        self._init_holdings()

        self.notifier.send_startup_message("IndexRebalancer", dry_run=self.dry_run)

    def _init_holdings(self) -> None:
        """Initialise les positions simulées en DRY_RUN."""
        for pair, weight in self.composition.items():
            self._holdings[pair] = self.total_portfolio * weight / 100

    def get_current_prices(self) -> dict[str, float]:
        """
        Récupère les prix actuels de tous les actifs du panier.

        CHOIX : Utilise CCXT si disponible, sinon des prix par défaut
        pour le DRY_RUN.
        """
        prices = {}
        if self.exchange:
            try:
                tickers = self.exchange.fetch_tickers(list(self.composition.keys()))
                for pair in self.composition:
                    if pair in tickers:
                        prices[pair] = tickers[pair].get("last", 0)
            except Exception as e:
                print(f"[IndexRebalancer] Erreur fetch tickers: {e}")

        # Fallback prix simulés
        default_prices = {
            "BTC/USDT": 65000, "ETH/USDT": 3500, "SOL/USDT": 150,
            "BNB/USDT": 600, "XRP/USDT": 0.55, "ADA/USDT": 0.45,
            "AVAX/USDT": 35,
        }
        for pair in self.composition:
            if pair not in prices or prices[pair] == 0:
                prices[pair] = default_prices.get(pair, 100)

        return prices

    def calculate_deviations(self, prices: dict[str, float]) -> dict[str, dict]:
        """
        Calcule la déviation actuelle par rapport aux poids cibles.

        Returns:
            Dict par paire avec : valeur actuelle, poids actuel, poids cible, déviation.
        """
        # ── Valeur totale du portfolio ──
        total_value = sum(self._holdings.values())

        deviations = {}
        for pair, target_weight in self.composition.items():
            current_value = self._holdings.get(pair, 0)
            current_weight = (current_value / total_value * 100) if total_value > 0 else 0
            deviation = current_weight - target_weight

            deviations[pair] = {
                "current_value": current_value,
                "current_weight": round(current_weight, 2),
                "target_weight": target_weight,
                "deviation": round(deviation, 2),
                "needs_rebalance": abs(deviation) > self.rebalance_threshold,
            }

        return deviations

    def rebalance(self) -> list[dict]:
        """
        Exécute le rééquilibrage si nécessaire.

        MÉTHODE :
        1. Identifier les actifs surpondérés (à vendre)
        2. Identifier les actifs sous-pondérés (à acheter)
        3. Calculer les montants de chaque trade
        4. Exécuter (ou simuler en DRY_RUN)
        """
        prices = self.get_current_prices()
        deviations = self.calculate_deviations(prices)
        trades = []

        to_sell = []
        to_buy = []

        for pair, dev in deviations.items():
            if not dev["needs_rebalance"]:
                continue
            if dev["deviation"] > 0:
                # Surpondéré → vendre l'excédent
                excess_value = self._holdings[pair] * (dev["deviation"] / dev["current_weight"])
                if excess_value > self.min_trade:
                    to_sell.append((pair, excess_value, prices.get(pair, 0)))
            else:
                # Sous-pondéré → acheter le déficit
                deficit_value = abs(dev["deviation"]) / 100 * sum(self._holdings.values())
                if deficit_value > self.min_trade:
                    to_buy.append((pair, deficit_value, prices.get(pair, 0)))

        # ── Équilibrer les montants (ventes financent les achats) ──
        total_sell = sum(v for _, v, _ in to_sell)
        total_buy = sum(v for _, v, _ in to_buy)

        if total_sell > 0 and total_buy > 0:
            # Normaliser pour que sell = buy (après frais)
            ratio = min(total_sell * (1 - self.fee_pct / 100), total_buy) / total_buy

            for pair, amount, price in to_sell:
                trade_amount = amount * ratio
                trade = {
                    "pair": pair, "side": "sell", "amount_usdt": trade_amount,
                    "price": price,
                }
                trades.append(trade)
                self._holdings[pair] -= trade_amount

                if self.dry_run:
                    self.logger.log_trade(
                        pair=pair, side="sell", price=price,
                        amount=trade_amount / price if price > 0 else 0,
                        dry_run=True,
                        extra_info=f"rebalance|value:{trade_amount:.2f}",
                    )

            for pair, amount, price in to_buy:
                trade_amount = amount * ratio
                trade = {
                    "pair": pair, "side": "buy", "amount_usdt": trade_amount,
                    "price": price,
                }
                trades.append(trade)
                self._holdings[pair] += trade_amount

                if self.dry_run:
                    self.logger.log_trade(
                        pair=pair, side="buy", price=price,
                        amount=trade_amount / price if price > 0 else 0,
                        dry_run=True,
                        extra_info=f"rebalance|value:{trade_amount:.2f}",
                    )

            # ── Résumé ──
            if trades:
                summary = "\n".join(
                    f"  {t['side'].upper()} {t['pair']}: {t['amount_usdt']:.2f} USDT"
                    for t in trades
                )
                print(f"[{'DRY_RUN' if self.dry_run else 'LIVE'}] Rebalance:\n{summary}")
                self.notifier.send_message(
                    f"📊 *IndexRebalancer* | Rebalance\n```\n{summary}\n```"
                )

        return trades

    def print_portfolio(self) -> None:
        """Affiche l'état actuel du portfolio."""
        total = sum(self._holdings.values())
        print(f"\n{'═'*50}")
        print(f"📊 Portfolio ({total:.2f} USDT)")
        print(f"{'═'*50}")
        for pair, value in sorted(self._holdings.items(), key=lambda x: x[1], reverse=True):
            weight = value / total * 100 if total > 0 else 0
            target = self.composition.get(pair, 0)
            diff = weight - target
            arrow = "↑" if diff > 0 else ("↓" if diff < 0 else "=")
            print(f"  {pair:12} {value:>10.2f} USDT  ({weight:5.1f}% / {target}%)  {arrow}{abs(diff):.1f}%")
        print(f"{'═'*50}\n")

    def run(self) -> None:
        """Boucle principale."""
        print(f"📊 IndexRebalancer démarré | DRY_RUN={self.dry_run}")
        self.print_portfolio()

        try:
            while True:
                trades = self.rebalance()
                if trades:
                    self.print_portfolio()
                time.sleep(self.rebalance_interval)
        except KeyboardInterrupt:
            print("\n⏹ IndexRebalancer arrêté.")
            self.performance.log_performance()


if __name__ == "__main__":
    bot = IndexRebalancer()
    bot.run()
