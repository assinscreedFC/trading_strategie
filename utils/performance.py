# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# MODULE : performance.py
# RÔLE  : Calcul de métriques et génération de rapports
# ══════════════════════════════════════════════════════════════
#
# ARCHITECTURE DE REFACTORING :
# → Ce module est le SEUL endroit où les métriques sont calculées.
# → Toutes les stratégies utilisent PerformanceTracker pour :
#   1. Calculer Win-Rate, Max Drawdown, Profit cumulé
#   2. Générer un rapport hebdomadaire
#   3. Vérifier le mode DRY_RUN
#
# CHOIX TECHNIQUES :
# 1. Lit les données depuis SQLite (via TradeLogger.get_all_trades)
# 2. Calculs purement fonctionnels (entrée = trades, sortie = métriques)
# 3. Rapport au format Markdown (lisible dans le terminal et Telegram)
#
# USAGE :
#   from utils.performance import PerformanceTracker
#   tracker = PerformanceTracker("GridTradingSpot")
#   metrics = tracker.calculate_metrics()
#   report = tracker.generate_weekly_report()
# ══════════════════════════════════════════════════════════════

from datetime import datetime, timezone, timedelta
from typing import Optional

from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier


class PerformanceTracker:
    """
    Calculateur de performances et générateur de rapports.

    PRINCIPE ANIS SOLIDSCALE :
    - Chaque stratégie instancie son propre PerformanceTracker
    - Les métriques sont calculées à partir des données SQLite
    - Le rapport peut être envoyé automatiquement via Telegram
    - Inclut la vérification DRY_RUN obligatoire
    """

    def __init__(
        self,
        strategy_name: str,
        trade_logger: Optional[TradeLogger] = None,
        telegram_notifier: Optional[TelegramNotifier] = None,
    ):
        """
        Args:
            strategy_name: Nom de la stratégie
            trade_logger: Instance TradeLogger. Si None, en crée un nouveau.
            telegram_notifier: Instance TelegramNotifier. Si None, en crée un.
        """
        self.strategy_name = strategy_name
        self.logger = trade_logger or TradeLogger(strategy_name)
        self.notifier = telegram_notifier or TelegramNotifier()

    def calculate_metrics(self, trades: Optional[list[dict]] = None) -> dict:
        """
        Calcule les métriques de performance à partir des trades.

        MÉTRIQUES CALCULÉES :
        - total_trades : Nombre total de trades
        - winning_trades : Nombre de trades gagnants (PnL > 0)
        - losing_trades : Nombre de trades perdants (PnL < 0)
        - win_rate : Pourcentage de trades gagnants
        - total_pnl : Profit/Perte cumulé
        - avg_pnl : PnL moyen par trade
        - max_drawdown : Drawdown maximum (%)
        - best_trade : Meilleur PnL sur un seul trade
        - worst_trade : Pire PnL sur un seul trade
        - avg_trade_duration : (placeholder, nécessite timestamps open/close)

        Args:
            trades: Liste de dicts de trades. Si None, lit depuis SQLite.

        Returns:
            Dict avec toutes les métriques calculées.
        """
        if trades is None:
            trades = self.logger.get_all_trades()

        # ── Cas trivial : aucun trade ──
        if not trades:
            return {
                "strategy_name": self.strategy_name,
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0.0,
                "total_pnl": 0.0,
                "avg_pnl": 0.0,
                "max_drawdown": 0.0,
                "best_trade": 0.0,
                "worst_trade": 0.0,
                "total_fees": 0.0,
            }

        # ── Extraire les PnL des trades "sell" (les clôtures) ──
        # CHOIX : On ne compte que les sells car le PnL n'est réalisé
        # qu'à la clôture de la position.
        sell_trades = [t for t in trades if t.get("side") == "sell"]
        pnls = [t.get("pnl", 0.0) for t in sell_trades]

        if not pnls:
            pnls = [0.0]

        winning = [p for p in pnls if p > 0]
        losing = [p for p in pnls if p < 0]
        total_pnl = sum(pnls)
        total_fees = sum(t.get("fee", 0.0) for t in trades)

        # ── Calcul du Max Drawdown ──
        # CHOIX : On utilise la méthode du "peak-to-trough" sur le PnL cumulé.
        # C'est la méthode standard en finance quantitative.
        max_drawdown = self._calculate_max_drawdown(pnls)

        return {
            "strategy_name": self.strategy_name,
            "total_trades": len(sell_trades),
            "winning_trades": len(winning),
            "losing_trades": len(losing),
            "win_rate": (len(winning) / len(sell_trades) * 100) if sell_trades else 0.0,
            "total_pnl": total_pnl,
            "avg_pnl": total_pnl / len(sell_trades) if sell_trades else 0.0,
            "max_drawdown": max_drawdown,
            "best_trade": max(pnls) if pnls else 0.0,
            "worst_trade": min(pnls) if pnls else 0.0,
            "total_fees": total_fees,
        }

    @staticmethod
    def _calculate_max_drawdown(pnls: list[float]) -> float:
        """
        Calcule le drawdown maximum en pourcentage.

        MÉTHODE : Peak-to-Trough sur le PnL cumulé.
        Le drawdown est mesuré comme la chute maximale depuis un pic.

        Exemple : PnL cumulé = [100, 150, 120, 180]
        → Drawdown max = (150 - 120) / 150 = 20%
        """
        if not pnls:
            return 0.0

        # Capital de référence (initial fictif pour le calcul)
        initial_capital = 10000.0
        cumulative = initial_capital
        peak = initial_capital
        max_dd = 0.0

        for pnl in pnls:
            cumulative += pnl
            if cumulative > peak:
                peak = cumulative
            drawdown = (peak - cumulative) / peak * 100 if peak > 0 else 0.0
            max_dd = max(max_dd, drawdown)

        return round(max_dd, 2)

    def generate_weekly_report(self, send_telegram: bool = True) -> str:
        """
        Génère un rapport hebdomadaire au format Markdown.

        PROTOCOLE ANIS SOLIDSCALE :
        - Appelé automatiquement en fin de session
        - Inclut Win-Rate, Drawdown max, Profit cumulé
        - Optionnellement envoyé sur Telegram

        Args:
            send_telegram: Si True, envoie aussi le rapport sur Telegram.

        Returns:
            Le rapport au format Markdown.
        """
        metrics = self.calculate_metrics()
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        pnl_str = (
            f"+{metrics['total_pnl']:.2f}"
            if metrics["total_pnl"] >= 0
            else f"{metrics['total_pnl']:.2f}"
        )

        report = (
            f"# 📋 Rapport Hebdomadaire — {self.strategy_name}\n"
            f"*Généré le {now}*\n\n"
            f"## Métriques\n"
            f"| Métrique | Valeur |\n"
            f"|---|---|\n"
            f"| Total Trades | {metrics['total_trades']} |\n"
            f"| Win Rate | {metrics['win_rate']:.1f}% |\n"
            f"| Trades Gagnants | {metrics['winning_trades']} |\n"
            f"| Trades Perdants | {metrics['losing_trades']} |\n"
            f"| PnL Total | {pnl_str} USDT |\n"
            f"| PnL Moyen | {metrics['avg_pnl']:.2f} USDT |\n"
            f"| Max Drawdown | {metrics['max_drawdown']:.2f}% |\n"
            f"| Meilleur Trade | {metrics['best_trade']:.2f} USDT |\n"
            f"| Pire Trade | {metrics['worst_trade']:.2f} USDT |\n"
            f"| Frais Totaux | {metrics['total_fees']:.2f} USDT |\n"
        )

        # ── Envoi Telegram si activé ──
        if send_telegram:
            self.notifier.send_performance_report(
                strategy_name=self.strategy_name,
                win_rate=metrics["win_rate"],
                total_trades=metrics["total_trades"],
                total_pnl=metrics["total_pnl"],
                max_drawdown=metrics["max_drawdown"],
                period="Hebdomadaire",
            )

        return report

    def log_performance(self) -> dict:
        """
        Wrapper rapide pour calculer et afficher les performances.

        PROTOCOLE §4 : Fonction log_performance() obligatoire.
        Calcule Win-Rate, Drawdown maximum et Profit cumulé.

        Returns:
            Dict des métriques (même format que calculate_metrics).
        """
        metrics = self.calculate_metrics()
        print(f"\n{'='*50}")
        print(f"📊 Performance — {self.strategy_name}")
        print(f"{'='*50}")
        print(f"  Win Rate     : {metrics['win_rate']:.1f}%")
        print(f"  Total PnL    : {metrics['total_pnl']:.2f} USDT")
        print(f"  Max Drawdown : {metrics['max_drawdown']:.2f}%")
        print(f"  Total Trades : {metrics['total_trades']}")
        print(f"{'='*50}\n")
        return metrics
