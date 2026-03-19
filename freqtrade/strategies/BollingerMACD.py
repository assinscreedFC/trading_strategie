# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATÉGIE : BollingerMACD
# CATÉGORIE : Nouvelle — Mean Reversion + Momentum
# ══════════════════════════════════════════════════════════════
#
# DESCRIPTION :
# Combine Bollinger Bands (survente) + MACD (momentum revient)
# pour identifier les rebonds avec confirmation de momentum.
# Documenté à 78% win rate dans la littérature.
#
# LOGIQUE :
# 1. Prix sous BB lower (survente extrême)
# 2. MACD histogram en hausse (momentum revient)
# 3. RSI < seuil (confirmation survente)
# 4. Sortie : prix >= BB middle OU RSI > seuil exit
# ══════════════════════════════════════════════════════════════

import sys
from pathlib import Path

from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from utils.indicators import CommonIndicators
from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier


class BollingerMACD(IStrategy):
    """
    BollingerMACD — BB survente + MACD momentum reversal.

    PRINCIPES ANIS SOLIDSCALE :
    ✅ Long-Only (Spot)
    ✅ Triple confirmation (BB + MACD + RSI)
    ✅ Tous paramètres configurables
    """

    INTERFACE_VERSION = 3
    can_short = False
    timeframe = "1h"
    startup_candle_count = 50

    # ── ROI ──
    minimal_roi = {
        "0": 0.08,
        "60": 0.04,
        "180": 0.02,
        "360": 0.01,
    }

    # ── Stoploss ──
    stoploss = -0.06
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.03
    trailing_only_offset_is_reached = True

    # ── Paramètres optimisables (buy) ──
    bb_period = IntParameter(10, 40, default=20, space="buy")
    bb_std_dev = DecimalParameter(1.5, 3.5, default=2.0, decimals=1, space="buy")
    rsi_period = IntParameter(7, 30, default=14, space="buy")
    rsi_entry_threshold = IntParameter(20, 50, default=40, space="buy")
    volume_period = IntParameter(10, 50, default=20, space="buy")
    volume_mult = DecimalParameter(0.8, 3.0, default=1.0, decimals=1, space="buy")

    # ── Paramètres optimisables (sell) ──
    rsi_exit_threshold = IntParameter(55, 85, default=70, space="sell")

    # ── Logging ──
    _logger = None
    _notifier = None

    def _init_utils(self) -> None:
        if self._logger is None:
            self._logger = TradeLogger(strategy_name="BollingerMACD")
            self._notifier = TelegramNotifier()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()

        # Bollinger Bands
        dataframe = CommonIndicators.add_bollinger_bands(
            dataframe, period=self.bb_period.value, std_dev=self.bb_std_dev.value
        )

        # RSI
        dataframe = CommonIndicators.add_rsi(dataframe, period=self.rsi_period.value)

        # MACD
        dataframe = CommonIndicators.add_macd(dataframe)

        # Volume SMA
        dataframe = CommonIndicators.add_volume_sma(dataframe, period=self.volume_period.value)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        bb_col = f"bb_lower_{self.bb_period.value}"
        bb_mid = f"bb_middle_{self.bb_period.value}"
        rsi_col = f"rsi_{self.rsi_period.value}"
        vol_col = f"volume_ratio_{self.volume_period.value}"

        conditions = (
            (dataframe["close"] < dataframe[bb_col])
            & (dataframe["macd_histogram"] > dataframe["macd_histogram"].shift(1))
            & (dataframe[rsi_col] < self.rsi_entry_threshold.value)
            & (dataframe[vol_col] > self.volume_mult.value)
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        bb_mid = f"bb_middle_{self.bb_period.value}"
        rsi_col = f"rsi_{self.rsi_period.value}"

        conditions = (
            (dataframe["close"] >= dataframe[bb_mid])
            | (dataframe[rsi_col] > self.rsi_exit_threshold.value)
        )

        dataframe.loc[conditions, "exit_long"] = 1
        return dataframe
