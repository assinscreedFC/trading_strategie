# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATÉGIE : DCADynamique
# CATÉGORIE : 1 — Fondations
# OUTIL     : Freqtrade (IStrategy)
# ══════════════════════════════════════════════════════════════
#
# DESCRIPTION :
# Dollar Cost Averaging Dynamique : automatise les entrées avec
# pondération RSI. Achète PLUS quand le RSI est bas (marché survendu),
# achète MOINS quand le RSI est haut. Utilise adjust_trade_position()
# pour les entrées DCA multiples sur une même position.
#
# LOGIQUE :
# 1. Première entrée quand le RSI < seuil d'achat
# 2. DCA (renforcement) via adjust_trade_position() avec des
#    paliers RSI : plus le RSI est bas, plus on achète
# 3. Sortie via ROI milestones configurables
#
# CONFIGURABILITÉ :
# → RSI seuils (buy, oversold, overbought)
# → Multiplicateurs DCA par palier RSI
# → ROI milestones
# → Nombre max de DCA
# ══════════════════════════════════════════════════════════════

import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional

from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter
from freqtrade.persistence import Trade

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from utils.indicators import CommonIndicators
from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier


class DCADynamique(IStrategy):
    """
    DCA Dynamique — Accumulation pondérée par RSI.

    PRINCIPES ANIS SOLIDSCALE :
    ✅ Long-Only (Spot)
    ✅ Pondération intelligente (RSI bas → plus d'achat)
    ✅ Nombre de DCA limité (risque contrôlé)
    ✅ Logging SQLite + Telegram par stratégie
    """

    INTERFACE_VERSION = 3
    can_short = False
    timeframe = "1h"
    startup_candle_count = 50

    # ═══════════════════════════════════════════════════════
    # PARAMÈTRES CONFIGURABLES
    # ═══════════════════════════════════════════════════════

    # ── RSI : période ──
    rsi_period = IntParameter(7, 30, default=14, space="buy",
                              optimize=True, load=True)

    # ── RSI : seuil d'achat initial ──
    # CHOIX : 45 pour entrer tôt dans la tendance baissière.
    # L'hyperopt peut ajuster entre 30-55.
    rsi_buy_threshold = IntParameter(25, 55, default=45, space="buy",
                                     optimize=True, load=True)

    # ── RSI : seuil de survente profonde (DCA agressif) ──
    rsi_oversold = IntParameter(15, 35, default=30, space="buy",
                                optimize=True, load=True)

    # ── RSI : seuil de sortie (surachat) ──
    rsi_sell_threshold = IntParameter(60, 85, default=70, space="sell",
                                      optimize=True, load=True)

    # ── DCA : nombre maximum d'entrées additionnelles ──
    # CHOIX : 4 max par défaut. Chaque DCA divise le risque mais
    # augmente l'exposition. Plus de 6 est rarement optimal.
    max_dca_entries = IntParameter(1, 8, default=4, space="buy",
                                   optimize=True, load=True)

    # ── DCA : multiplicateur pour RSI très bas (< oversold) ──
    # CHOIX : 2.0x = on achète le double quand le marché est très survendu
    dca_multiplier_oversold = DecimalParameter(1.5, 3.0, default=2.0, decimals=1,
                                               space="buy", optimize=True, load=True)

    # ── DCA : multiplicateur pour RSI modéré (oversold < RSI < buy_threshold) ──
    dca_multiplier_moderate = DecimalParameter(1.0, 2.0, default=1.5, decimals=1,
                                               space="buy", optimize=True, load=True)

    # ── DCA : drop minimum pour déclencher un DCA (% depuis l'entrée) ──
    # CHOIX : 2% de baisse minimum pour renforcer. Évite les DCA trop rapprochés.
    dca_min_drop_pct = DecimalParameter(1.0, 10.0, default=2.0, decimals=1,
                                        space="buy", optimize=True, load=True)

    # ── ROI Milestones ──
    minimal_roi = {
        "0": 0.08,      # 8% max
        "120": 0.05,    # 5% après 2h
        "360": 0.03,    # 3% après 6h
        "720": 0.015,   # 1.5% après 12h
    }

    stoploss = -0.15  # -15% : large car DCA permet de moyenner

    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.04
    trailing_only_offset_is_reached = True

    # position stacking (nécessaire pour le DCA multi-entrées)
    position_adjustment_enable = True

    # ═══════════════════════════════════════════════════════
    # INITIALISATION
    # ═══════════════════════════════════════════════════════

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self._trade_logger = TradeLogger(strategy_name="DCADynamique")
        self._notifier = TelegramNotifier()
        self._notifier.send_startup_message(
            "DCADynamique", dry_run=config.get("dry_run", True)
        )

    # ═══════════════════════════════════════════════════════
    # INDICATEURS
    # ═══════════════════════════════════════════════════════

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Indicateurs pour le DCA Dynamique.

        REFACTORING : Utilise CommonIndicators pour le RSI.
        Ajoute aussi l'EMA-200 comme filtre de tendance long terme.
        """
        dataframe = CommonIndicators.add_rsi(dataframe, period=self.rsi_period.value)
        dataframe = CommonIndicators.add_ema(dataframe, period=200)
        return dataframe

    # ═══════════════════════════════════════════════════════
    # SIGNAUX D'ENTRÉE
    # ═══════════════════════════════════════════════════════

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Entrée initiale DCA : RSI sous le seuil d'achat.

        LOGIQUE :
        - RSI < rsi_buy_threshold : signal d'achat
        - Volume > 0 : vérification de liquidité
        - Pas de filtre EMA ici car le DCA est conçu pour accumuler
          dans les baisses (même sous l'EMA-200)
        """
        rsi_col = f"rsi_{self.rsi_period.value}"

        dataframe.loc[
            (
                (dataframe[rsi_col] < self.rsi_buy_threshold.value)
                &
                (dataframe["volume"] > 0)
            ),
            "enter_long",
        ] = 1

        return dataframe

    # ═══════════════════════════════════════════════════════
    # SIGNAUX DE SORTIE
    # ═══════════════════════════════════════════════════════

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Sortie quand RSI en zone de surachat.

        LOGIQUE : Le DCA a accumulé à bas prix, on vend quand
        le marché se retourne (RSI > seuil de vente).
        """
        rsi_col = f"rsi_{self.rsi_period.value}"

        dataframe.loc[
            (
                (dataframe[rsi_col] > self.rsi_sell_threshold.value)
                &
                (dataframe["volume"] > 0)
            ),
            "exit_long",
        ] = 1

        return dataframe

    # ═══════════════════════════════════════════════════════
    # DCA — RENFORCEMENT DE POSITION
    # ═══════════════════════════════════════════════════════

    def adjust_trade_position(
        self,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        min_stake: Optional[float],
        max_stake: float,
        current_entry_rate: float,
        current_exit_rate: float,
        current_entry_profit: float,
        current_exit_profit: float,
        **kwargs,
    ) -> Optional[float]:
        """
        Logique DCA : renforce la position quand le prix baisse.

        MÉCANISME DE PONDÉRATION RSI :
        ┌────────────────────┬───────────────────┬─────────────┐
        │ Condition RSI      │ Multiplicateur    │ Signification│
        ├────────────────────┼───────────────────┼─────────────┤
        │ RSI < oversold     │ dca_mult_oversold │ Très survendu│
        │ RSI < buy_thresh   │ dca_mult_moderate │ Modéré      │
        │ RSI > buy_thresh   │ 0 (skip)          │ Pas de DCA  │
        └────────────────────┴───────────────────┴─────────────┘

        SÉCURITÉ :
        - Max DCA limité par max_dca_entries
        - Drop minimum requis (dca_min_drop_pct) entre chaque DCA
        """
        # ── Vérifier le nombre de DCA déjà effectués ──
        filled_entries = trade.nr_of_successful_entries
        if filled_entries >= self.max_dca_entries.value + 1:
            return None  # Limite atteinte

        # ── Vérifier le drop minimum depuis l'entrée ──
        drop_pct = abs(current_profit * 100)
        min_drop = self.dca_min_drop_pct.value * filled_entries
        if current_profit > 0 or drop_pct < min_drop:
            return None  # Pas assez de baisse

        # ── Obtenir le RSI actuel ──
        dataframe, _ = self.dp.get_analyzed_dataframe(trade.pair, self.timeframe)
        if dataframe.empty:
            return None

        rsi_col = f"rsi_{self.rsi_period.value}"
        current_rsi = dataframe[rsi_col].iloc[-1]

        # ── Calculer le multiplicateur basé sur le RSI ──
        if current_rsi < self.rsi_oversold.value:
            multiplier = self.dca_multiplier_oversold.value
        elif current_rsi < self.rsi_buy_threshold.value:
            multiplier = self.dca_multiplier_moderate.value
        else:
            return None  # RSI trop haut, pas de DCA

        # ── Calculer le stake pour ce DCA ──
        try:
            stake = trade.stake_amount * multiplier
            # Respecter les limites
            if min_stake is not None:
                stake = max(stake, min_stake)
            stake = min(stake, max_stake)
        except Exception:
            return None

        # ── Log le DCA ──
        is_dry = self.config.get("dry_run", True)
        self._trade_logger.log_trade(
            pair=trade.pair, side="buy", price=current_rate, amount=stake,
            dry_run=is_dry,
            extra_info=f"DCA#{filled_entries}|RSI:{current_rsi:.1f}|mult:{multiplier}",
        )
        self._notifier.send_trade_alert(
            strategy_name="DCADynamique", pair=trade.pair, side="buy (DCA)",
            price=current_rate, amount=stake, dry_run=is_dry,
        )

        return stake

    # ═══════════════════════════════════════════════════════
    # CALLBACKS
    # ═══════════════════════════════════════════════════════

    def confirm_trade_exit(self, pair, trade, order_type, amount, rate,
                           time_in_force, exit_reason, current_time,
                           **kwargs) -> bool:
        is_dry = self.config.get("dry_run", True)
        pnl = trade.calc_profit_ratio(rate) * 100
        self._trade_logger.log_trade(
            pair=pair, side="sell", price=rate, amount=amount,
            pnl=pnl, dry_run=is_dry,
            extra_info=f"exit:{exit_reason}|entries:{trade.nr_of_successful_entries}",
        )
        self._notifier.send_trade_alert(
            strategy_name="DCADynamique", pair=pair, side="sell",
            price=rate, amount=amount, pnl=pnl, dry_run=is_dry,
        )
        return True
