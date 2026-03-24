# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATEGIE : KeltnerChannelMomentumLite
# CATEGORIE : Breakout — Keltner Channel (Simplifie)
# ══════════════════════════════════════════════════════════════
# Version simplifiee de KeltnerChannelMomentum :
# - 2 params : kc_period (buy) + rsi_exit (sell)
# - rsi_period=14, rsi_entry=70, atr_mult=1.5 fixes
# ══════════════════════════════════════════════════════════════

import sys
from pathlib import Path

from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from utils.indicators import CommonIndicators
from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier


class KeltnerChannelMomentumLite(IStrategy):
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
    kc_period = IntParameter(15, 30, default=20, space="buy")
    rsi_exit = IntParameter(70, 85, default=80, space="sell")

    # ── Params fixes ──
    RSI_PERIOD = 14
    RSI_ENTRY = 70
    ATR_MULT = 1.5

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
            self._logger = TradeLogger(strategy_name="KeltnerChannelMomentumLite")
            self._notifier = TelegramNotifier()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()

        for p in range(self.kc_period.low, self.kc_period.high + 1):
            dataframe = CommonIndicators.add_keltner_channels(dataframe, period=p, atr_mult=self.ATR_MULT)

        dataframe = CommonIndicators.add_rsi(dataframe, period=self.RSI_PERIOD)
        dataframe = CommonIndicators.add_volume_sma(dataframe, period=20)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        kc_upper = f"keltner_upper_{self.kc_period.value}"
        rsi_col = f"rsi_{self.RSI_PERIOD}"

        conditions = (
            (dataframe["close"] > dataframe[kc_upper])
            & (dataframe[rsi_col] < self.RSI_ENTRY)
            & (dataframe["volume"] > dataframe["volume_sma_20"])
            & (dataframe["close"] > dataframe["open"])
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        kc_middle = f"keltner_middle_{self.kc_period.value}"
        rsi_col = f"rsi_{self.RSI_PERIOD}"

        conditions = (
            (dataframe["close"] < dataframe[kc_middle])
            | (dataframe[rsi_col] > self.rsi_exit.value)
        )

        dataframe.loc[conditions, "exit_long"] = 1
        return dataframe
