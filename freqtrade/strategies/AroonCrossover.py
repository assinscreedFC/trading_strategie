# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATÉGIE : AroonCrossover
# CATÉGORIE : Nouvelle — Trend Detection via Aroon Indicator
# ══════════════════════════════════════════════════════════════
#
# LOGIQUE :
# 1. Aroon Up > seuil minimum (tendance haussière forte)
# 2. Aroon Up > Aroon Down (les bulls dominent)
# 3. Aroon Up vient de croiser au-dessus de Aroon Down (crossover frais)
# 4. Close > EMA (confirmation de tendance)
# 5. RSI entre rsi_min et rsi_max (ni survendu ni suracheté)
# 6. Volume > multiplicateur * moyenne
# 7. Sortie : Aroon Down > Aroon Up OU Aroon Up < 50 OU RSI > seuil exit
# ══════════════════════════════════════════════════════════════

import sys
from pathlib import Path

import pandas_ta as ta
from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from utils.indicators import CommonIndicators
from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier


class AroonCrossover(IStrategy):
    INTERFACE_VERSION = 3
    can_short = False
    timeframe = "4h"
    startup_candle_count = 100

    minimal_roi = {"0": 0.10, "480": 0.05, "1440": 0.02}
    stoploss = -0.06
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.04
    trailing_only_offset_is_reached = True

    # ── Buy params ──
    aroon_period = IntParameter(10, 30, default=14, space="buy")
    aroon_up_min = IntParameter(50, 90, default=70, space="buy")
    ema_period = IntParameter(20, 60, default=50, space="buy")
    rsi_period = IntParameter(7, 21, default=14, space="buy")
    rsi_min = IntParameter(30, 50, default=35, space="buy")
    rsi_max = IntParameter(60, 80, default=70, space="buy")
    volume_period = IntParameter(10, 50, default=20, space="buy")
    volume_mult = DecimalParameter(0.8, 3.0, default=1.0, decimals=1, space="buy")

    # ── Sell params ──
    rsi_exit = IntParameter(65, 85, default=75, space="sell")

    _logger = None
    _notifier = None

    def _init_utils(self) -> None:
        if self._logger is None:
            self._logger = TradeLogger(strategy_name="AroonCrossover")
            self._notifier = TelegramNotifier()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()

        # Pre-calculer Aroon pour TOUTES les valeurs possibles (hyperopt-safe)
        for p in range(self.aroon_period.low, self.aroon_period.high + 1):
            aroon_result = ta.aroon(dataframe["high"], dataframe["low"], length=p)
            dataframe[f"aroon_up_{p}"] = aroon_result[f"AROONU_{p}"]
            dataframe[f"aroon_down_{p}"] = aroon_result[f"AROOND_{p}"]

        # EMA pour toutes les valeurs possibles
        for p in range(self.ema_period.low, self.ema_period.high + 1):
            dataframe = CommonIndicators.add_ema(dataframe, period=p)

        # RSI pour toutes les valeurs possibles
        for rsi_p in range(self.rsi_period.low, self.rsi_period.high + 1):
            dataframe = CommonIndicators.add_rsi(dataframe, period=rsi_p)

        # Volume SMA pour toutes les valeurs possibles
        for vol_p in range(self.volume_period.low, self.volume_period.high + 1):
            dataframe = CommonIndicators.add_volume_sma(dataframe, period=vol_p)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        aroon_up = f"aroon_up_{self.aroon_period.value}"
        aroon_down = f"aroon_down_{self.aroon_period.value}"
        ema_col = f"ema_{self.ema_period.value}"
        rsi_col = f"rsi_{self.rsi_period.value}"
        vol_col = f"volume_ratio_{self.volume_period.value}"

        conditions = (
            (dataframe[aroon_up] > self.aroon_up_min.value)
            & (dataframe[aroon_up] > dataframe[aroon_down])
            & (dataframe[aroon_up].shift(1) <= dataframe[aroon_down].shift(1))  # crossover frais
            & (dataframe["close"] > dataframe[ema_col])
            & (dataframe[rsi_col] > self.rsi_min.value)
            & (dataframe[rsi_col] < self.rsi_max.value)
            & (dataframe[vol_col] > self.volume_mult.value)
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        aroon_up = f"aroon_up_{self.aroon_period.value}"
        aroon_down = f"aroon_down_{self.aroon_period.value}"
        rsi_col = f"rsi_{self.rsi_period.value}"

        conditions = (
            (dataframe[aroon_down] > dataframe[aroon_up])
            | (dataframe[aroon_up] < 50)
            | (dataframe[rsi_col] > self.rsi_exit.value)
        )

        dataframe.loc[conditions, "exit_long"] = 1
        return dataframe
