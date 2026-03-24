# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATEGIE : ChandelierExitLite
# CATEGORIE : Trend Following — Chandelier Exit (Simplifie)
# ══════════════════════════════════════════════════════════════
# Version simplifiee de ChandelierExit :
# - 2 params : chandelier_period (buy) + atr_mult_exit_x10 (sell)
# - ema_filter=50, atr_mult_entry=3.0 fixes
# ══════════════════════════════════════════════════════════════

import sys
from pathlib import Path

from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from utils.indicators import CommonIndicators
from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier


class ChandelierExitLite(IStrategy):
    INTERFACE_VERSION = 3
    can_short = False
    timeframe = "4h"
    startup_candle_count = 80

    minimal_roi = {"0": 0.10, "240": 0.05, "720": 0.03, "1440": 0.01}
    stoploss = -0.06
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.03
    trailing_only_offset_is_reached = True

    # ── Hyperopt params (1 buy + 1 sell) ──
    chandelier_period = IntParameter(15, 30, default=22, space="buy")
    atr_mult_exit_x10 = IntParameter(20, 40, default=30, space="sell")  # /10 → 2.0-4.0

    # ── Params fixes ──
    EMA_FILTER = 50
    ATR_MULT_ENTRY = 3.0

    _logger = None
    _notifier = None

    def __getstate__(self):
        state = self.__dict__.copy()
        state["_logger"] = None
        state["_notifier"] = None
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)

    def _init_utils(self) -> None:
        if self._logger is None:
            self._logger = TradeLogger(strategy_name="ChandelierExitLite")
            self._notifier = TelegramNotifier()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()

        for cp in range(self.chandelier_period.low, self.chandelier_period.high + 1):
            dataframe = CommonIndicators.add_chandelier_exit(dataframe, period=cp, atr_mult=self.ATR_MULT_ENTRY)

        # ATR pour exit dynamique
        for cp in range(self.chandelier_period.low, self.chandelier_period.high + 1):
            dataframe = CommonIndicators.add_atr(dataframe, period=cp)

        dataframe = CommonIndicators.add_ema(dataframe, period=self.EMA_FILTER)
        dataframe = CommonIndicators.add_volume_sma(dataframe, period=20)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        chand_col = f"chandelier_long_{self.chandelier_period.value}"
        ema_col = f"ema_{self.EMA_FILTER}"

        conditions = (
            (dataframe["close"] > dataframe[chand_col])
            & (dataframe["close"].shift(1) <= dataframe[chand_col].shift(1))
            & (dataframe["close"] > dataframe[ema_col])
            & (dataframe["close"] > dataframe["open"])
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Exit dynamique : close < highest_high - atr_mult_exit * ATR
        cp = self.chandelier_period.value
        atr_col = f"atr_{cp}"
        mult_exit = self.atr_mult_exit_x10.value / 10.0

        highest = dataframe["high"].rolling(window=cp).max()
        exit_level = highest - mult_exit * dataframe[atr_col]

        conditions = dataframe["close"] < exit_level

        dataframe.loc[conditions, "exit_long"] = 1
        return dataframe
