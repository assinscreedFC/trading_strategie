# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATÉGIE : VolatilityBreakout
# CATÉGORIE : Nouvelle — Volatility Breakout
# ══════════════════════════════════════════════════════════════
#
# LOGIQUE :
# 1. BB width à son minimum (compression, < percentile d'entrée)
# 2. Breakout au-dessus de la bande supérieure de Bollinger
# 3. Volume > multiplicateur * moyenne
# 4. ATR en expansion (atr > atr précédent)
# 5. Sortie : BB width revient à la normale (> percentile de sortie)
# ══════════════════════════════════════════════════════════════

import sys
from pathlib import Path

from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from utils.indicators import CommonIndicators
from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier


class VolatilityBreakout(IStrategy):
    INTERFACE_VERSION = 3
    can_short = False
    timeframe = "1h"
    startup_candle_count = 200

    minimal_roi = {"0": 0.10, "360": 0.05, "720": 0.02}
    stoploss = -0.06
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.03
    trailing_only_offset_is_reached = True

    # ── Buy params ──
    bb_period = IntParameter(15, 30, default=20, space="buy")
    bb_std = DecimalParameter(1.5, 3.0, default=2.0, decimals=1, space="buy")
    atr_period = IntParameter(10, 20, default=14, space="buy")
    volume_period = IntParameter(10, 50, default=20, space="buy")
    volume_mult = DecimalParameter(1.0, 3.0, default=1.5, decimals=1, space="buy")
    width_entry_pct = IntParameter(10, 30, default=20, space="buy")

    # ── Sell params ──
    width_exit_pct = IntParameter(40, 60, default=50, space="sell")

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
            self._logger = TradeLogger(strategy_name="VolatilityBreakout")
            self._notifier = TelegramNotifier()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()

        # Pre-calculer BB pour toutes combinaisons period x std_dev (hyperopt-safe)
        for bb_p in range(self.bb_period.low, self.bb_period.high + 1):
            for bb_s_10 in range(int(self.bb_std.low * 10), int(self.bb_std.high * 10) + 1):
                bb_s = bb_s_10 / 10.0
                dataframe = CommonIndicators.add_bollinger_bands(
                    dataframe, period=bb_p, std_dev=bb_s
                )
            # BB width pour chaque period (using default std for width calc)
            # Width is computed per period in entry/exit using actual columns

        # Pre-calculer ATR pour toutes valeurs possibles
        for atr_p in range(self.atr_period.low, self.atr_period.high + 1):
            dataframe = CommonIndicators.add_atr(dataframe, period=atr_p)

        # Pre-calculer volume SMA pour toutes valeurs possibles
        for vol_p in range(self.volume_period.low, self.volume_period.high + 1):
            dataframe = CommonIndicators.add_volume_sma(dataframe, period=vol_p)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        bb_p = self.bb_period.value
        bb_s = self.bb_std.value
        atr_col = f"atr_{self.atr_period.value}"
        vol_col = f"volume_ratio_{self.volume_period.value}"

        # BB width pour la combinaison actuelle
        upper_col = f"bb_upper_{bb_p}"
        lower_col = f"bb_lower_{bb_p}"
        middle_col = f"bb_middle_{bb_p}"

        bb_width = (dataframe[upper_col] - dataframe[lower_col]) / dataframe[middle_col]

        # BB width rolling percentile pour détecter la compression
        bb_width_pct = bb_width.rolling(window=100).apply(
            lambda x: x.rank(pct=True).iloc[-1], raw=False
        )

        conditions = (
            (bb_width_pct < self.width_entry_pct.value / 100.0)
            & (dataframe["close"] > dataframe[upper_col])
            & (dataframe[vol_col] > self.volume_mult.value)
            & (dataframe[atr_col] > dataframe[atr_col].shift(1))
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        bb_p = self.bb_period.value
        upper_col = f"bb_upper_{bb_p}"
        lower_col = f"bb_lower_{bb_p}"
        middle_col = f"bb_middle_{bb_p}"

        bb_width = (dataframe[upper_col] - dataframe[lower_col]) / dataframe[middle_col]

        bb_width_pct = bb_width.rolling(window=100).apply(
            lambda x: x.rank(pct=True).iloc[-1], raw=False
        )

        conditions = (
            bb_width_pct > self.width_exit_pct.value / 100.0
        )

        dataframe.loc[conditions, "exit_long"] = 1
        return dataframe
