# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATEGIE : SuperTrendADXLite
# CATEGORIE : Trend Following Dynamique (Simplifie)
# ══════════════════════════════════════════════════════════════
# Version simplifiee de SuperTrendADX :
# - 2 params : atr_period (buy) + adx_exit (sell)
# - atr_mult=3.0, adx_period=14, adx_threshold=25, ema=200 fixes
# ══════════════════════════════════════════════════════════════

import sys
from pathlib import Path

import numpy as np
from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from utils.indicators import CommonIndicators
from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier


def _calc_supertrend(close, high, low, atr, mult):
    """Calcul SuperTrend vectorise avec boucle optimisee."""
    n = len(close)
    hl2 = (high + low) / 2
    upper_basic = hl2 + mult * atr
    lower_basic = hl2 - mult * atr

    st_upper = np.full(n, np.nan)
    st_lower = np.full(n, np.nan)
    direction = np.ones(n, dtype=int)

    st_lower[0] = lower_basic[0]
    st_upper[0] = upper_basic[0]

    for i in range(1, n):
        st_lower[i] = lower_basic[i] if (lower_basic[i] > st_lower[i - 1] or close[i - 1] < st_lower[i - 1]) else st_lower[i - 1]
        st_upper[i] = upper_basic[i] if (upper_basic[i] < st_upper[i - 1] or close[i - 1] > st_upper[i - 1]) else st_upper[i - 1]

        if direction[i - 1] == 1:
            direction[i] = -1 if close[i] < st_lower[i] else 1
        else:
            direction[i] = 1 if close[i] > st_upper[i] else -1

    return direction


class SuperTrendADXLite(IStrategy):
    INTERFACE_VERSION = 3
    can_short = False
    timeframe = "4h"
    startup_candle_count = 100

    minimal_roi = {"0": 0.10, "240": 0.05, "720": 0.03, "1440": 0.01}
    stoploss = -0.06
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.03
    trailing_only_offset_is_reached = True

    # ── Hyperopt params (1 buy + 1 sell) ──
    atr_period = IntParameter(7, 20, default=10, space="buy")
    adx_exit = IntParameter(10, 25, default=20, space="sell")

    # ── Params fixes ──
    ATR_MULT = 3.0
    ADX_PERIOD = 14
    ADX_THRESHOLD = 25
    EMA_PERIOD = 200

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
            self._logger = TradeLogger(strategy_name="SuperTrendADXLite")
            self._notifier = TelegramNotifier()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()

        close = dataframe["close"].values
        high = dataframe["high"].values
        low = dataframe["low"].values

        for p in range(self.atr_period.low, self.atr_period.high + 1):
            dataframe = CommonIndicators.add_atr(dataframe, period=p)
            atr_vals = dataframe[f"atr_{p}"].values
            mult_x10 = int(self.ATR_MULT * 10)
            col = f"st_dir_{p}_{mult_x10}"
            dataframe[col] = _calc_supertrend(close, high, low, atr_vals, self.ATR_MULT)

        dataframe = CommonIndicators.add_adx(dataframe, period=self.ADX_PERIOD)
        dataframe = CommonIndicators.add_ema(dataframe, period=self.EMA_PERIOD)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        mult_x10 = int(self.ATR_MULT * 10)
        st_col = f"st_dir_{self.atr_period.value}_{mult_x10}"
        adx_col = f"adx_{self.ADX_PERIOD}"
        ema_col = f"ema_{self.EMA_PERIOD}"

        conditions = (
            (dataframe[st_col] == 1)
            & (dataframe[adx_col] > self.ADX_THRESHOLD)
            & (dataframe["close"] > dataframe[ema_col])
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        mult_x10 = int(self.ATR_MULT * 10)
        st_col = f"st_dir_{self.atr_period.value}_{mult_x10}"
        adx_col = f"adx_{self.ADX_PERIOD}"

        conditions = (
            (dataframe[st_col] == -1)
            | (dataframe[adx_col] < self.adx_exit.value)
        )

        dataframe.loc[conditions, "exit_long"] = 1
        return dataframe
