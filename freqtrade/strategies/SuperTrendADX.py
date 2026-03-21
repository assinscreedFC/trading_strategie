# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATEGIE : SuperTrendADX
# CATEGORIE : Trend Following Dynamique (ATR-adaptatif)
# ══════════════════════════════════════════════════════════════
#
# LOGIQUE :
# SuperTrend = bandes dynamiques basees sur ATR (plus reactif que EMA)
# 1. SuperTrend en mode haussier (prix au-dessus de la bande)
# 2. ADX > seuil → tendance forte confirmee
# 3. Close > EMA longue → filtre directionnel
# 4. Sortie : SuperTrend passe baissier OU ADX faiblit
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

    ub = upper_basic
    lb = lower_basic

    st_lower[0] = lb[0]
    st_upper[0] = ub[0]

    for i in range(1, n):
        st_lower[i] = lb[i] if (lb[i] > st_lower[i - 1] or close[i - 1] < st_lower[i - 1]) else st_lower[i - 1]
        st_upper[i] = ub[i] if (ub[i] < st_upper[i - 1] or close[i - 1] > st_upper[i - 1]) else st_upper[i - 1]

        if direction[i - 1] == 1:
            direction[i] = -1 if close[i] < st_lower[i] else 1
        else:
            direction[i] = 1 if close[i] > st_upper[i] else -1

    return direction


class SuperTrendADX(IStrategy):
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

    # ── Buy params ──
    atr_period = IntParameter(7, 20, default=10, space="buy")
    atr_mult_x10 = IntParameter(15, 35, default=30, space="buy")  # /10 → 1.5-3.5
    adx_period = IntParameter(10, 25, default=14, space="buy")
    adx_threshold = IntParameter(15, 35, default=25, space="buy")
    ema_period = IntParameter(100, 250, default=200, space="buy")

    # ── Sell params ──
    adx_exit = IntParameter(10, 25, default=20, space="sell")

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
            self._logger = TradeLogger(strategy_name="SuperTrendADX")
            self._notifier = TelegramNotifier()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()

        close = dataframe["close"].values
        high = dataframe["high"].values
        low = dataframe["low"].values

        # Pre-calc ATR pour toutes les valeurs
        for p in range(self.atr_period.low, self.atr_period.high + 1):
            dataframe = CommonIndicators.add_atr(dataframe, period=p)

        # Pre-calc ADX pour toutes les valeurs
        for p in range(self.adx_period.low, self.adx_period.high + 1):
            dataframe = CommonIndicators.add_adx(dataframe, period=p)

        # Pre-calc EMA pour toutes les valeurs
        for p in range(self.ema_period.low, self.ema_period.high + 1):
            dataframe = CommonIndicators.add_ema(dataframe, period=p)

        # Pre-calc SuperTrend pour toutes les combinaisons (atr_period, atr_mult)
        for atr_p in range(self.atr_period.low, self.atr_period.high + 1):
            atr_vals = dataframe[f"atr_{atr_p}"].values
            for mult_x10 in range(self.atr_mult_x10.low, self.atr_mult_x10.high + 1):
                mult = mult_x10 / 10.0
                col = f"st_dir_{atr_p}_{mult_x10}"
                dataframe[col] = _calc_supertrend(close, high, low, atr_vals, mult)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        st_col = f"st_dir_{self.atr_period.value}_{self.atr_mult_x10.value}"
        adx_col = f"adx_{self.adx_period.value}"
        ema_col = f"ema_{self.ema_period.value}"

        conditions = (
            (dataframe[st_col] == 1)
            & (dataframe[adx_col] > self.adx_threshold.value)
            & (dataframe["close"] > dataframe[ema_col])
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        st_col = f"st_dir_{self.atr_period.value}_{self.atr_mult_x10.value}"
        adx_col = f"adx_{self.adx_period.value}"

        conditions = (
            (dataframe[st_col] == -1)
            | (dataframe[adx_col] < self.adx_exit.value)
        )

        dataframe.loc[conditions, "exit_long"] = 1
        return dataframe
