# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATEGIE : MARibbonStackLite
# CATEGORIE : Trend Following avec MA Ribbon (Simplifie)
# ══════════════════════════════════════════════════════════════
# Version simplifiee de MARibbonStack :
# - 2 params hyperopt seulement : ema_fast, volume_mult
# - Les 5 EMAs sont derivees : ema_fast, ema_fast*2, *3, *4, *5
# - volume_mult est un IntParameter /10 pour eviter DecimalParameter
# ══════════════════════════════════════════════════════════════

import sys
from pathlib import Path

from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from utils.indicators import CommonIndicators
from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier


class MARibbonStackLite(IStrategy):
    INTERFACE_VERSION = 3
    can_short = False
    timeframe = "4h"
    startup_candle_count = 100

    minimal_roi = {"0": 0.12, "480": 0.06, "1440": 0.03}
    stoploss = -0.06
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.04
    trailing_only_offset_is_reached = True

    # ── Hyperopt params (2 buy + 1 sell) ──
    ema_fast = IntParameter(5, 15, default=8, space="buy")
    volume_mult = IntParameter(5, 20, default=10, space="buy")  # /10 = 0.5 a 2.0
    exit_sensitivity = IntParameter(1, 3, default=2, space="sell")

    # ── Param fixe ──
    VOLUME_PERIOD = 20

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
            self._logger = TradeLogger(strategy_name="MARibbonStackLite")
            self._notifier = TelegramNotifier()

    def _ema_periods(self, base: int) -> tuple[int, int, int, int, int]:
        """Retourne les 5 periodes EMA derivees du base."""
        return base, base * 2, base * 3, base * 4, base * 5

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()

        # Pre-calc toutes les EMAs possibles pour hyperopt
        all_ema_values: set[int] = set()
        for base in range(self.ema_fast.low, self.ema_fast.high + 1):
            for p in self._ema_periods(base):
                all_ema_values.add(p)

        for ema_p in sorted(all_ema_values):
            dataframe = CommonIndicators.add_ema(dataframe, period=ema_p)

        dataframe = CommonIndicators.add_volume_sma(dataframe, period=self.VOLUME_PERIOD)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        p1, p2, p3, p4, p5 = self._ema_periods(self.ema_fast.value)
        e1 = f"ema_{p1}"
        e2 = f"ema_{p2}"
        e3 = f"ema_{p3}"
        e4 = f"ema_{p4}"
        e5 = f"ema_{p5}"
        vol_col = f"volume_ratio_{self.VOLUME_PERIOD}"
        vol_threshold = self.volume_mult.value / 10.0

        conditions = (
            (dataframe[e1] > dataframe[e2])
            & (dataframe[e2] > dataframe[e3])
            & (dataframe[e3] > dataframe[e4])
            & (dataframe[e4] > dataframe[e5])
            & (dataframe["close"] > dataframe[e1])
            & (dataframe[vol_col] > vol_threshold)
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        p1, p2, p3, _, p5 = self._ema_periods(self.ema_fast.value)
        e1 = f"ema_{p1}"
        e2 = f"ema_{p2}"
        e3 = f"ema_{p3}"
        e5 = f"ema_{p5}"
        sens = self.exit_sensitivity.value

        # exit_sensitivity controle combien de conditions doivent etre vraies (1-3)
        cond1 = (dataframe[e1] < dataframe[e2]).astype(int)
        cond2 = (dataframe[e2] < dataframe[e3]).astype(int)
        cond3 = (dataframe["close"] < dataframe[e5]).astype(int)
        total = cond1 + cond2 + cond3

        # sens=1: exit des qu'1 condition, sens=2: 2 conditions, sens=3: les 3
        conditions = total >= sens

        dataframe.loc[conditions, "exit_long"] = 1
        return dataframe
