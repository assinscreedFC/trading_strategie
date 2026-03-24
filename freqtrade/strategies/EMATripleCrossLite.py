# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATEGIE : EMATripleCrossLite
# CATEGORIE : Trend Following (Simplifie)
# ══════════════════════════════════════════════════════════════
# Version simplifiee de EMATripleCross :
# - 2 params : ema_fast (buy) + rsi_exit (sell)
# - ema_mid = ema_fast * 3, ema_slow = ema_fast * 6 (derives)
# - rsi_period=14, volume_period=20, volume_mult=1.2 fixes
# ══════════════════════════════════════════════════════════════

import sys
from pathlib import Path

from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from utils.indicators import CommonIndicators
from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier


class EMATripleCrossLite(IStrategy):
    INTERFACE_VERSION = 3
    can_short = False
    timeframe = "4h"
    startup_candle_count = 100

    minimal_roi = {"0": 0.10, "480": 0.05, "1440": 0.02}
    stoploss = -0.05
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.04
    trailing_only_offset_is_reached = True

    # ── Hyperopt params (1 buy + 1 sell) ──
    ema_fast = IntParameter(5, 15, default=9, space="buy")
    rsi_exit = IntParameter(65, 85, default=75, space="sell")

    # ── Params fixes ──
    RSI_PERIOD = 14
    VOLUME_PERIOD = 20
    VOLUME_MULT = 1.2

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
            self._logger = TradeLogger(strategy_name="EMATripleCrossLite")
            self._notifier = TelegramNotifier()

    def _ema_periods(self, base: int) -> tuple[int, int, int]:
        return base, base * 3, base * 6

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()

        all_ema: set[int] = set()
        for base in range(self.ema_fast.low, self.ema_fast.high + 1):
            for p in self._ema_periods(base):
                all_ema.add(p)

        for p in sorted(all_ema):
            dataframe = CommonIndicators.add_ema(dataframe, period=p)

        dataframe = CommonIndicators.add_rsi(dataframe, period=self.RSI_PERIOD)
        dataframe = CommonIndicators.add_volume_sma(dataframe, period=self.VOLUME_PERIOD)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        p_fast, p_mid, p_slow = self._ema_periods(self.ema_fast.value)
        ef = f"ema_{p_fast}"
        em = f"ema_{p_mid}"
        es = f"ema_{p_slow}"
        rsi_col = f"rsi_{self.RSI_PERIOD}"
        vol_col = f"volume_ratio_{self.VOLUME_PERIOD}"

        conditions = (
            (dataframe[ef] > dataframe[em])
            & (dataframe[em] > dataframe[es])
            & (dataframe[ef].shift(1) <= dataframe[em].shift(1))
            & (dataframe[rsi_col] > 40)
            & (dataframe[rsi_col] < 70)
            & (dataframe[vol_col] > self.VOLUME_MULT)
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        p_fast, p_mid, _ = self._ema_periods(self.ema_fast.value)
        ef = f"ema_{p_fast}"
        em = f"ema_{p_mid}"
        rsi_col = f"rsi_{self.RSI_PERIOD}"

        conditions = (
            (dataframe[ef] < dataframe[em])
            | (dataframe[rsi_col] > self.rsi_exit.value)
        )

        dataframe.loc[conditions, "exit_long"] = 1
        return dataframe
