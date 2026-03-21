# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATEGIE : TwiggsMoneyFlow
# CATEGORIE : Volume-Trend — Twiggs Money Flow
# ══════════════════════════════════════════════════════════════
#
# LOGIQUE :
# TMF utilise le True Range et un lissage EMA pour mesurer le flux
# monetaire. Plus fiable que le CMF standard (moins de faux signaux).
# 1. TMF cross au-dessus de 0 + prix > EMA(50) → long
# 2. Sortie : TMF cross sous 0
# SOURCE : QuantifiedStrategies — WR 78% sur actions
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


class TwiggsMoneyFlow(IStrategy):
    INTERFACE_VERSION = 3
    can_short = False
    timeframe = "4h"
    startup_candle_count = 80

    minimal_roi = {"0": 0.12, "240": 0.06, "720": 0.03, "1440": 0.01}
    stoploss = -0.07
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.035
    trailing_only_offset_is_reached = True

    # ── Buy params ──
    tmf_period = IntParameter(10, 30, default=21, space="buy")
    ema_period = IntParameter(30, 80, default=50, space="buy")

    # ── Sell params ──
    tmf_exit_threshold = IntParameter(-10, 5, default=0, space="sell")  # /100

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
            self._logger = TradeLogger(strategy_name="TwiggsMoneyFlow")
            self._notifier = TelegramNotifier()

    @staticmethod
    def _calc_tmf(dataframe: DataFrame, period: int) -> None:
        """Calcule le Twiggs Money Flow."""
        col_name = f"tmf_{period}"
        # True Range High/Low (utilise le close precedent)
        prev_close = dataframe["close"].shift(1)
        tr_high = np.maximum(dataframe["high"], prev_close)
        tr_low = np.minimum(dataframe["low"], prev_close)

        # AD volume: position du close dans le True Range
        tr_range = tr_high - tr_low
        tr_range = tr_range.replace(0, np.nan)
        ad = ((dataframe["close"] - tr_low) - (tr_high - dataframe["close"])) / tr_range
        ad = ad.fillna(0) * dataframe["volume"]

        # EMA smoothing
        ema_ad = ad.ewm(span=period, adjust=False).mean()
        ema_vol = dataframe["volume"].ewm(span=period, adjust=False).mean()

        dataframe[col_name] = ema_ad / ema_vol.replace(0, np.nan)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()

        # EMA pour toutes les valeurs
        for ema_p in range(self.ema_period.low, self.ema_period.high + 1):
            dataframe = CommonIndicators.add_ema(dataframe, period=ema_p)

        # TMF pour toutes les valeurs
        for tmf_p in range(self.tmf_period.low, self.tmf_period.high + 1):
            self._calc_tmf(dataframe, tmf_p)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        tmf_col = f"tmf_{self.tmf_period.value}"
        ema_col = f"ema_{self.ema_period.value}"

        conditions = (
            (dataframe[tmf_col] > 0)
            & (dataframe[tmf_col].shift(1) <= 0)  # Cross au-dessus de 0
            & (dataframe["close"] > dataframe[ema_col])
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        tmf_col = f"tmf_{self.tmf_period.value}"
        exit_thresh = self.tmf_exit_threshold.value / 100

        conditions = (
            (dataframe[tmf_col] < exit_thresh)
            & (dataframe[tmf_col].shift(1) >= exit_thresh)  # Cross sous seuil
        )

        dataframe.loc[conditions, "exit_long"] = 1
        return dataframe
