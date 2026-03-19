# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATÉGIE : VWAPBounce
# CATÉGORIE : Price Action — Rebond sur VWAP en tendance
# ══════════════════════════════════════════════════════════════
#
# LOGIQUE :
# 1. VWAP (Volume Weighted Average Price) sert de support dynamique
#    en tendance haussière
# 2. Entrée : close > EMA50 (tendance up) + prix pullback vers VWAP
#    (proximité < 0.5%) + close > VWAP (rebond confirmé) + RSI en
#    zone neutre (40-60, ni surachat ni survente)
# 3. Sortie : close < VWAP - 1*ATR (cassure du support) OU RSI > 75
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


class VWAPBounce(IStrategy):
    INTERFACE_VERSION = 3
    can_short = False
    timeframe = "1h"
    startup_candle_count = 100

    minimal_roi = {"0": 0.10, "360": 0.05, "720": 0.02}
    stoploss = -0.04
    trailing_stop = True
    trailing_stop_positive = 0.015
    trailing_stop_positive_offset = 0.02
    trailing_only_offset_is_reached = True

    # ── Buy params ──
    ema_period = IntParameter(30, 70, default=50, space="buy")
    vwap_period = IntParameter(12, 48, default=24, space="buy")
    proximity_pct = DecimalParameter(0.002, 0.01, default=0.005, space="buy")
    rsi_period = IntParameter(7, 21, default=14, space="buy")
    rsi_min = IntParameter(30, 50, default=40, space="buy")
    rsi_max = IntParameter(55, 70, default=60, space="buy")
    atr_period = IntParameter(10, 20, default=14, space="buy")

    # ── Sell params ──
    rsi_exit = IntParameter(65, 85, default=75, space="sell")

    _logger = None
    _notifier = None

    def _init_utils(self) -> None:
        if self._logger is None:
            self._logger = TradeLogger(strategy_name="VWAPBounce")
            self._notifier = TelegramNotifier()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()

        # Pre-calculer RSI pour TOUTES les valeurs possibles (hyperopt-safe)
        for rsi_p in range(self.rsi_period.low, self.rsi_period.high + 1):
            dataframe = CommonIndicators.add_rsi(dataframe, period=rsi_p)

        # Pre-calculer EMA pour TOUTES les valeurs possibles
        for ema_p in range(self.ema_period.low, self.ema_period.high + 1):
            dataframe = CommonIndicators.add_ema(dataframe, period=ema_p)

        # Pre-calculer ATR pour TOUTES les valeurs possibles
        for atr_p in range(self.atr_period.low, self.atr_period.high + 1):
            dataframe = CommonIndicators.add_atr(dataframe, period=atr_p)

        # VWAP rolling pour TOUTES les valeurs de vwap_period
        # VWAP = cumsum(close * volume) / cumsum(volume) sur une fenêtre rolling
        for vwap_p in range(self.vwap_period.low, self.vwap_period.high + 1):
            typical_price = dataframe["close"]
            tp_vol = typical_price * dataframe["volume"]
            dataframe[f"vwap_{vwap_p}"] = (
                tp_vol.rolling(window=vwap_p).sum()
                / dataframe["volume"].rolling(window=vwap_p).sum()
            )

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        rsi_col = f"rsi_{self.rsi_period.value}"
        ema_col = f"ema_{self.ema_period.value}"
        vwap_col = f"vwap_{self.vwap_period.value}"

        # Proximité au VWAP : abs(close - vwap) / vwap < proximity_pct
        proximity = (
            ((dataframe["close"] - dataframe[vwap_col]).abs() / dataframe[vwap_col])
            < self.proximity_pct.value
        )

        conditions = (
            (dataframe["close"] > dataframe[ema_col])
            & proximity
            & (dataframe["close"] > dataframe[vwap_col])
            & (dataframe[rsi_col] > self.rsi_min.value)
            & (dataframe[rsi_col] < self.rsi_max.value)
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        rsi_col = f"rsi_{self.rsi_period.value}"
        vwap_col = f"vwap_{self.vwap_period.value}"
        atr_col = f"atr_{self.atr_period.value}"

        # Sortie : close < VWAP - 1*ATR OU RSI > seuil exit
        conditions = (
            (dataframe["close"] < dataframe[vwap_col] - dataframe[atr_col])
            | (dataframe[rsi_col] > self.rsi_exit.value)
        )

        dataframe.loc[conditions, "exit_long"] = 1
        return dataframe
