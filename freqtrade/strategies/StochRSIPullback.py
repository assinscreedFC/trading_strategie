# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATÉGIE : StochRSIPullback
# CATÉGORIE : Nouvelle — Pullback en Tendance Haussière
# ══════════════════════════════════════════════════════════════
#
# LOGIQUE :
# Acheter les pullbacks dans une tendance haussière confirmée.
# 1. EMA fast > EMA slow → tendance haussière
# 2. StochRSI K < seuil → pullback (RSI survendu relatif)
# 3. Volume > multiplicateur * moyenne → confirmation
# 4. Sortie : StochRSI K > seuil exit OU close > BB upper
# ══════════════════════════════════════════════════════════════

import sys
from pathlib import Path

from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from utils.indicators import CommonIndicators
from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier


class StochRSIPullback(IStrategy):
    INTERFACE_VERSION = 3
    can_short = False
    timeframe = "1h"
    startup_candle_count = 250

    minimal_roi = {"0": 0.08, "240": 0.04, "720": 0.02}
    stoploss = -0.04
    trailing_stop = True
    trailing_stop_positive = 0.015
    trailing_stop_positive_offset = 0.025
    trailing_only_offset_is_reached = True

    # ── Buy params ──
    ema_fast = IntParameter(30, 70, default=50, space="buy")
    ema_slow = IntParameter(150, 250, default=200, space="buy")
    stoch_period = IntParameter(7, 21, default=14, space="buy")
    stoch_k = IntParameter(3, 7, default=3, space="buy")
    rsi_period = IntParameter(7, 21, default=14, space="buy")
    stoch_entry = IntParameter(10, 30, default=20, space="buy")
    volume_period = IntParameter(10, 50, default=20, space="buy")
    volume_mult = DecimalParameter(0.8, 2.0, default=1.2, decimals=1, space="buy")

    # ── Sell params ──
    stoch_exit = IntParameter(70, 90, default=80, space="sell")

    _logger = None
    _notifier = None

    def _init_utils(self) -> None:
        if self._logger is None:
            self._logger = TradeLogger(strategy_name="StochRSIPullback")
            self._notifier = TelegramNotifier()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()
        dataframe = CommonIndicators.add_ema(dataframe, period=self.ema_fast.value)
        dataframe = CommonIndicators.add_ema(dataframe, period=self.ema_slow.value)
        dataframe = CommonIndicators.add_rsi(dataframe, period=self.rsi_period.value)
        dataframe = CommonIndicators.add_volume_sma(dataframe, period=self.volume_period.value)
        dataframe = CommonIndicators.add_bollinger_bands(dataframe, period=20, std_dev=2.0)

        # StochRSI calc manuelle : stochastique appliquée sur le RSI
        rsi_col = f"rsi_{self.rsi_period.value}"
        stoch_len = self.stoch_period.value
        smooth_k = self.stoch_k.value

        rsi_min = dataframe[rsi_col].rolling(window=stoch_len).min()
        rsi_max = dataframe[rsi_col].rolling(window=stoch_len).max()
        stoch_rsi_raw = ((dataframe[rsi_col] - rsi_min) / (rsi_max - rsi_min)) * 100
        dataframe["stochrsi_k"] = stoch_rsi_raw.rolling(window=smooth_k).mean()

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        ema_f = f"ema_{self.ema_fast.value}"
        ema_s = f"ema_{self.ema_slow.value}"
        vol_col = f"volume_ratio_{self.volume_period.value}"

        conditions = (
            (dataframe[ema_f] > dataframe[ema_s])
            & (dataframe["stochrsi_k"] < self.stoch_entry.value)
            & (dataframe[vol_col] > self.volume_mult.value)
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = (
            (dataframe["stochrsi_k"] > self.stoch_exit.value)
            | (dataframe["close"] > dataframe["bb_upper_20"])
        )

        dataframe.loc[conditions, "exit_long"] = 1
        return dataframe
