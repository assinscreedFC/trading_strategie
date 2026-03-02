# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATÉGIE : MeanReversion
# CATÉGORIE : 1 — Fondations
# OUTIL     : Freqtrade (IStrategy)
# ══════════════════════════════════════════════════════════════
#
# DESCRIPTION :
# Mean Reversion via Bollinger Bands : achète lors de déviations
# extrêmes sous la bande basse, vend au retour vers la moyenne.
# Stratégie contre-tendance qui profite de la "reversion to the mean".
#
# LOGIQUE :
# 1. Prix ferme sous la Bollinger Band basse → signal d'entrée
# 2. RSI confirme la survente (< seuil configurable)
# 3. Volume spike confirme l'intérêt du marché
# 4. Sortie quand le prix atteint la bande médiane (SMA)
#
# QUAND UTILISER :
# - Marchés en range/consolidation (pas de tendance forte)
# - Fonctionne mal en tendance baissière prolongée
# ══════════════════════════════════════════════════════════════

import sys
from pathlib import Path

from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from utils.indicators import CommonIndicators
from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier


class MeanReversion(IStrategy):
    """
    Mean Reversion — Bollinger Bands bounce.

    PRINCIPES ANIS SOLIDSCALE :
    ✅ Long-Only (Spot)
    ✅ Triple confirmation (BB + RSI + Volume)
    ✅ Tous paramètres configurables
    """

    INTERFACE_VERSION = 3
    can_short = False
    timeframe = "1h"
    startup_candle_count = 50

    # ═══════════════════════════════════════════════════════
    # PARAMÈTRES CONFIGURABLES
    # ═══════════════════════════════════════════════════════

    # ── Bollinger Bands : période ──
    bb_period = IntParameter(10, 40, default=20, space="buy",
                             optimize=True, load=True)

    # ── Bollinger Bands : écart-type ──
    # CHOIX : 2.0σ standard. 2.5σ pour crypto (plus volatile).
    bb_std_dev = DecimalParameter(1.5, 3.5, default=2.0, decimals=1,
                                  space="buy", optimize=True, load=True)

    # ── RSI : période ──
    rsi_period = IntParameter(7, 30, default=14, space="buy",
                              optimize=True, load=True)

    # ── RSI : seuil d'entrée (survente) ──
    rsi_entry_threshold = IntParameter(20, 45, default=35, space="buy",
                                       optimize=True, load=True)

    # ── RSI : seuil de sortie (surachat) ──
    rsi_exit_threshold = IntParameter(55, 80, default=65, space="sell",
                                      optimize=True, load=True)

    # ── Volume : multiplicateur minimum pour spike ──
    # CHOIX : 1.2x par défaut. Un spike de volume léger suffit car
    # on ne cherche pas un breakout mais une réaction.
    volume_spike_mult = DecimalParameter(0.8, 3.0, default=1.2, decimals=1,
                                         space="buy", optimize=True, load=True)

    # ── Volume : période moyenne ──
    volume_period = IntParameter(10, 50, default=20, space="buy",
                                 optimize=True, load=True)

    # ── ROI ──
    minimal_roi = {
        "0": 0.06,
        "60": 0.04,
        "180": 0.025,
        "360": 0.01,
    }

    stoploss = -0.04

    trailing_stop = True
    trailing_stop_positive = 0.015
    trailing_stop_positive_offset = 0.03
    trailing_only_offset_is_reached = True

    # ═══════════════════════════════════════════════════════
    # INITIALISATION
    # ═══════════════════════════════════════════════════════

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self._trade_logger = TradeLogger(strategy_name="MeanReversion")
        self._notifier = TelegramNotifier()
        self._notifier.send_startup_message(
            "MeanReversion", dry_run=config.get("dry_run", True)
        )

    # ═══════════════════════════════════════════════════════
    # INDICATEURS
    # ═══════════════════════════════════════════════════════

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        REFACTORING : Utilise CommonIndicators pour BB, RSI, Volume.
        """
        dataframe = CommonIndicators.add_bollinger_bands(
            dataframe, period=self.bb_period.value, std_dev=self.bb_std_dev.value,
        )
        dataframe = CommonIndicators.add_rsi(dataframe, period=self.rsi_period.value)
        dataframe = CommonIndicators.add_volume_sma(
            dataframe, period=self.volume_period.value,
        )
        return dataframe

    # ═══════════════════════════════════════════════════════
    # SIGNAUX D'ENTRÉE
    # ═══════════════════════════════════════════════════════

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Entrée Mean Reversion : triple confirmation.

        LOGIQUE :
        1. Prix ferme SOUS la Bollinger Band basse
        2. RSI < seuil de survente
        3. Volume > moyenne * multiplicateur (spike)
        """
        rsi_col = f"rsi_{self.rsi_period.value}"
        bb_lower = f"bb_lower_{self.bb_period.value}"
        vol_ratio = f"volume_ratio_{self.volume_period.value}"

        dataframe.loc[
            (
                # Condition 1 : Prix sous la BB basse
                (dataframe["close"] < dataframe[bb_lower])
                &
                # Condition 2 : RSI en survente
                (dataframe[rsi_col] < self.rsi_entry_threshold.value)
                &
                # Condition 3 : Volume spike
                (dataframe[vol_ratio] > self.volume_spike_mult.value)
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
        Sortie quand le prix revient à la moyenne.

        LOGIQUE :
        - Prix atteint la BB médiane (SMA) → objectif atteint
        - OU RSI > seuil de surachat → le rebond est terminé
        """
        rsi_col = f"rsi_{self.rsi_period.value}"
        bb_middle = f"bb_middle_{self.bb_period.value}"

        dataframe.loc[
            (
                (dataframe["close"] >= dataframe[bb_middle])
                |
                (dataframe[rsi_col] > self.rsi_exit_threshold.value)
            )
            &
            (dataframe["volume"] > 0),
            "exit_long",
        ] = 1

        return dataframe

    # ═══════════════════════════════════════════════════════
    # CALLBACKS
    # ═══════════════════════════════════════════════════════

    def confirm_trade_entry(self, pair, order_type, amount, rate, time_in_force,
                            current_time, entry_tag, side, **kwargs) -> bool:
        is_dry = self.config.get("dry_run", True)
        self._trade_logger.log_trade(
            pair=pair, side="buy", price=rate, amount=amount, dry_run=is_dry,
        )
        self._notifier.send_trade_alert(
            "MeanReversion", pair, "buy", rate, amount, dry_run=is_dry,
        )
        return True

    def confirm_trade_exit(self, pair, trade, order_type, amount, rate,
                           time_in_force, exit_reason, current_time,
                           **kwargs) -> bool:
        is_dry = self.config.get("dry_run", True)
        pnl = trade.calc_profit_ratio(rate) * 100
        self._trade_logger.log_trade(
            pair=pair, side="sell", price=rate, amount=amount,
            pnl=pnl, dry_run=is_dry, extra_info=f"exit:{exit_reason}",
        )
        self._notifier.send_trade_alert(
            "MeanReversion", pair, "sell", rate, amount, pnl=pnl, dry_run=is_dry,
        )
        return True
