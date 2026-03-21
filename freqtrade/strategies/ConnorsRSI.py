# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATEGIE : ConnorsRSI (CRSI)
# CATEGORIE : Mean-Reversion — Triple composant RSI
# ══════════════════════════════════════════════════════════════
#
# LOGIQUE :
# CRSI = (RSI(3) + StreakRSI + RankPercentile) / 3
# - RSI(3) : momentum court terme
# - StreakRSI : RSI applique aux streaks up/down consecutifs
# - RankPercentile : rang du rendement actuel sur N periodes
# CRSI < 10 → long, CRSI > 90 → exit
# SOURCE : Larry Connors — version amelioree du RSI2
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


class ConnorsRSI(IStrategy):
    INTERFACE_VERSION = 3
    can_short = False
    timeframe = "4h"
    startup_candle_count = 210

    minimal_roi = {"0": 0.10, "120": 0.05, "360": 0.03, "720": 0.01}
    stoploss = -0.06
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.03
    trailing_only_offset_is_reached = True

    # ── Buy params ──
    rsi_period = IntParameter(2, 5, default=3, space="buy")
    streak_rsi_period = IntParameter(2, 5, default=2, space="buy")
    rank_period = IntParameter(50, 150, default=100, space="buy")
    crsi_entry = IntParameter(5, 20, default=10, space="buy")
    sma_trend = IntParameter(150, 250, default=200, space="buy")

    # ── Sell params ──
    crsi_exit = IntParameter(80, 95, default=90, space="sell")

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
            self._logger = TradeLogger(strategy_name="ConnorsRSI")
            self._notifier = TelegramNotifier()

    @staticmethod
    def _calc_streak(series):
        """Calcule la serie de jours consecutifs up/down."""
        streak = np.zeros(len(series))
        for i in range(1, len(series)):
            if series.iloc[i] > series.iloc[i - 1]:
                streak[i] = streak[i - 1] + 1 if streak[i - 1] > 0 else 1
            elif series.iloc[i] < series.iloc[i - 1]:
                streak[i] = streak[i - 1] - 1 if streak[i - 1] < 0 else -1
            else:
                streak[i] = 0
        return streak

    @staticmethod
    def _calc_percent_rank(series, period: int):
        """Rang percentile du rendement actuel sur N periodes."""
        pct_change = series.pct_change()
        result = np.full(len(series), np.nan)
        for i in range(period, len(series)):
            window = pct_change.iloc[i - period:i]
            current = pct_change.iloc[i]
            if not np.isnan(current):
                result[i] = (window < current).sum() / period * 100
        return result

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()

        # RSI pour toutes les valeurs
        for rsi_p in range(self.rsi_period.low, self.rsi_period.high + 1):
            dataframe = CommonIndicators.add_rsi(dataframe, period=rsi_p)

        # SMA trend
        for sma_p in range(self.sma_trend.low, self.sma_trend.high + 1):
            dataframe = CommonIndicators.add_sma(dataframe, period=sma_p)

        # Streak
        streak = self._calc_streak(dataframe["close"])
        dataframe["streak"] = streak

        # Streak RSI pour toutes les valeurs
        for srsi_p in range(self.streak_rsi_period.low, self.streak_rsi_period.high + 1):
            dataframe = CommonIndicators.add_rsi(dataframe, period=srsi_p, column="streak")

        # Percent Rank pour toutes les valeurs
        for rank_p in range(self.rank_period.low, self.rank_period.high + 1):
            dataframe[f"pct_rank_{rank_p}"] = self._calc_percent_rank(dataframe["close"], rank_p)

        # Pre-calc CRSI pour toutes les combinaisons
        for rsi_p in range(self.rsi_period.low, self.rsi_period.high + 1):
            for srsi_p in range(self.streak_rsi_period.low, self.streak_rsi_period.high + 1):
                for rank_p in range(self.rank_period.low, self.rank_period.high + 1):
                    rsi_col = f"rsi_{rsi_p}"
                    # Streak RSI uses same add_rsi but on streak column
                    streak_rsi_col = f"rsi_{srsi_p}"
                    rank_col = f"pct_rank_{rank_p}"
                    crsi_col = f"crsi_{rsi_p}_{srsi_p}_{rank_p}"
                    dataframe[crsi_col] = (dataframe[rsi_col] + dataframe[streak_rsi_col] + dataframe[rank_col]) / 3

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        crsi_col = f"crsi_{self.rsi_period.value}_{self.streak_rsi_period.value}_{self.rank_period.value}"
        sma_col = f"sma_{self.sma_trend.value}"

        conditions = (
            (dataframe[crsi_col] < self.crsi_entry.value)
            & (dataframe["close"] > dataframe[sma_col])
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        crsi_col = f"crsi_{self.rsi_period.value}_{self.streak_rsi_period.value}_{self.rank_period.value}"

        conditions = (
            dataframe[crsi_col] > self.crsi_exit.value
        )

        dataframe.loc[conditions, "exit_long"] = 1
        return dataframe
