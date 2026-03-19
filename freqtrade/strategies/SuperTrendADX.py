# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATÉGIE : SuperTrendADX
# CATÉGORIE : Nouvelle — Trend Following Dynamique
# ══════════════════════════════════════════════════════════════
#
# LOGIQUE :
# SuperTrend = bandes dynamiques basées sur ATR (plus réactif que EMA)
# 1. SuperTrend en mode haussier (prix au-dessus de la bande)
# 2. ADX > seuil → tendance forte confirmée
# 3. Close > EMA longue → filtre directionnel
# 4. Sortie : SuperTrend passe baissier OU ADX faiblit
# ══════════════════════════════════════════════════════════════

import sys
from pathlib import Path

import numpy as np
from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from utils.indicators import CommonIndicators
from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier


class SuperTrendADX(IStrategy):
    INTERFACE_VERSION = 3
    can_short = False
    timeframe = "1h"
    startup_candle_count = 300

    minimal_roi = {"0": 0.10, "480": 0.05, "1440": 0.02}
    stoploss = -0.06
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.03
    trailing_only_offset_is_reached = True

    # ── Buy params ──
    atr_period = IntParameter(7, 30, default=10, space="buy")
    atr_mult = DecimalParameter(1.0, 4.0, default=3.0, decimals=1, space="buy")
    adx_period = IntParameter(7, 30, default=14, space="buy")
    adx_threshold = IntParameter(15, 35, default=25, space="buy")
    ema_period = IntParameter(100, 300, default=200, space="buy")

    # ── Sell params ──
    adx_exit = IntParameter(10, 25, default=20, space="sell")

    _logger = None
    _notifier = None

    def _init_utils(self) -> None:
        if self._logger is None:
            self._logger = TradeLogger(strategy_name="SuperTrendADX")
            self._notifier = TelegramNotifier()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()
        dataframe = CommonIndicators.add_atr(dataframe, period=self.atr_period.value)
        dataframe = CommonIndicators.add_adx(dataframe, period=self.adx_period.value)
        dataframe = CommonIndicators.add_ema(dataframe, period=self.ema_period.value)

        # SuperTrend calc manuelle
        atr_col = f"atr_{self.atr_period.value}"
        hl2 = (dataframe["high"] + dataframe["low"]) / 2
        mult = self.atr_mult.value

        upper_basic = hl2 + mult * dataframe[atr_col]
        lower_basic = hl2 - mult * dataframe[atr_col]

        # Initialiser les bandes finales et la direction
        st_upper = np.full(len(dataframe), np.nan)
        st_lower = np.full(len(dataframe), np.nan)
        supertrend = np.full(len(dataframe), np.nan)
        direction = np.full(len(dataframe), 1)  # 1 = haussier, -1 = baissier

        close = dataframe["close"].values
        ub = upper_basic.values
        lb = lower_basic.values

        for i in range(1, len(dataframe)):
            # Lower band : ne descend jamais si close précédent était au-dessus
            if lb[i] > st_lower[i - 1] or close[i - 1] < st_lower[i - 1]:
                st_lower[i] = lb[i]
            else:
                st_lower[i] = st_lower[i - 1] if not np.isnan(st_lower[i - 1]) else lb[i]

            # Upper band : ne monte jamais si close précédent était en-dessous
            if ub[i] < st_upper[i - 1] or close[i - 1] > st_upper[i - 1]:
                st_upper[i] = ub[i]
            else:
                st_upper[i] = st_upper[i - 1] if not np.isnan(st_upper[i - 1]) else ub[i]

            # Direction
            if direction[i - 1] == 1:
                direction[i] = -1 if close[i] < st_lower[i] else 1
            else:
                direction[i] = 1 if close[i] > st_upper[i] else -1

            supertrend[i] = st_lower[i] if direction[i] == 1 else st_upper[i]

        dataframe["supertrend"] = supertrend
        dataframe["supertrend_dir"] = direction  # 1 = bull, -1 = bear

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        adx_col = f"adx_{self.adx_period.value}"
        ema_col = f"ema_{self.ema_period.value}"

        conditions = (
            (dataframe["supertrend_dir"] == 1)
            & (dataframe[adx_col] > self.adx_threshold.value)
            & (dataframe["close"] > dataframe[ema_col])
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        adx_col = f"adx_{self.adx_period.value}"

        conditions = (
            (dataframe["supertrend_dir"] == -1)
            | (dataframe[adx_col] < self.adx_exit.value)
        )

        dataframe.loc[conditions, "exit_long"] = 1
        return dataframe
