# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATEGIE : RSIRangeMeanRevert
# CATEGORIE : Mean-reversion — RSI Adaptatif (Cardwell)
# ══════════════════════════════════════════════════════════════
#
# LOGIQUE :
# Les seuils RSI fixes (30/70) ratent 60% des signaux (Cardwell).
# En bull, RSI oscille entre 40-80 → RSI 40 est deja oversold.
# 1. Calculer RSI_range = rolling max/min RSI
# 2. Entree : RSI < RSI_low + 20% du range (bas adaptatif)
# 3. Filtre : EMA200 rising (bull market)
# 4. Sortie : RSI > RSI_low + 80% du range (haut adaptatif)
# ══════════════════════════════════════════════════════════════

import sys
from pathlib import Path

from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from utils.indicators import CommonIndicators
from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier


class RSIRangeMeanRevert(IStrategy):
    INTERFACE_VERSION = 3
    can_short = False
    timeframe = "4h"
    startup_candle_count = 250

    minimal_roi = {"0": 0.08, "240": 0.04, "720": 0.02, "1440": 0.01}
    stoploss = -0.06
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.03
    trailing_only_offset_is_reached = True

    # ── Buy params ──
    rsi_period = IntParameter(7, 21, default=14, space="buy")
    range_lookback = IntParameter(30, 80, default=50, space="buy")
    entry_pct = IntParameter(15, 30, default=20, space="buy")  # % du range
    ema_trend = IntParameter(150, 250, default=200, space="buy")

    # ── Sell params ──
    exit_pct = IntParameter(70, 90, default=80, space="sell")  # % du range

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
            self._logger = TradeLogger(strategy_name="RSIRangeMeanRevert")
            self._notifier = TelegramNotifier()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()

        for p in range(self.rsi_period.low, self.rsi_period.high + 1):
            dataframe = CommonIndicators.add_rsi(dataframe, period=p)

        for p in range(self.ema_trend.low, self.ema_trend.high + 1):
            dataframe = CommonIndicators.add_ema(dataframe, period=p)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        rsi_col = f"rsi_{self.rsi_period.value}"
        ema_col = f"ema_{self.ema_trend.value}"
        lb = self.range_lookback.value
        entry_frac = self.entry_pct.value / 100.0

        rsi_high = dataframe[rsi_col].rolling(window=lb).max()
        rsi_low = dataframe[rsi_col].rolling(window=lb).min()
        rsi_range = rsi_high - rsi_low
        entry_level = rsi_low + entry_frac * rsi_range

        # Filtre : EMA rising (bull market)
        ema_rising = dataframe[ema_col] > dataframe[ema_col].shift(5)

        conditions = (
            (dataframe[rsi_col] < entry_level)
            & ema_rising
            & (rsi_range > 5)  # eviter les ranges trop etroits
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        rsi_col = f"rsi_{self.rsi_period.value}"
        lb = self.range_lookback.value
        exit_frac = self.exit_pct.value / 100.0

        rsi_high = dataframe[rsi_col].rolling(window=lb).max()
        rsi_low = dataframe[rsi_col].rolling(window=lb).min()
        rsi_range = rsi_high - rsi_low
        exit_level = rsi_low + exit_frac * rsi_range

        conditions = (
            dataframe[rsi_col] > exit_level
        )

        dataframe.loc[conditions, "exit_long"] = 1
        return dataframe
