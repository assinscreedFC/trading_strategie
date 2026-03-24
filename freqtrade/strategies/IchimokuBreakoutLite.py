# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATEGIE : IchimokuBreakoutLite
# CATEGORIE : Tendance / Ichimoku Kinko Hyo (Simplifie)
# ══════════════════════════════════════════════════════════════
# Version simplifiee de IchimokuBreakout :
# - 2 params hyperopt seulement : tenkan_period, kijun_period
# - senkou_b_period=52 fixe (standard Ichimoku)
# ══════════════════════════════════════════════════════════════

import sys
from pathlib import Path

from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from utils.indicators import CommonIndicators
from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier


class IchimokuBreakoutLite(IStrategy):
    INTERFACE_VERSION = 3
    can_short = False
    timeframe = "4h"
    startup_candle_count = 100

    minimal_roi = {"0": 0.15, "720": 0.08, "1440": 0.04, "2880": 0.02}
    stoploss = -0.06
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.04
    trailing_only_offset_is_reached = True

    # ── Hyperopt params (2 buy + 1 sell) ──
    tenkan_period = IntParameter(7, 12, default=9, space="buy")
    kijun_period = IntParameter(22, 30, default=26, space="buy")
    exit_lookback = IntParameter(1, 3, default=1, space="sell")

    # ── Param fixe ──
    SENKOU_B_PERIOD = 52

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
            self._logger = TradeLogger(strategy_name="IchimokuBreakoutLite")
            self._notifier = TelegramNotifier()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()

        # Tenkan pour toutes les valeurs possibles
        for tenkan_p in range(self.tenkan_period.low, self.tenkan_period.high + 1):
            col = f"tenkan_{tenkan_p}"
            dataframe[col] = (
                dataframe["high"].rolling(window=tenkan_p).max()
                + dataframe["low"].rolling(window=tenkan_p).min()
            ) / 2

        # Kijun pour toutes les valeurs possibles
        for kijun_p in range(self.kijun_period.low, self.kijun_period.high + 1):
            col = f"kijun_{kijun_p}"
            dataframe[col] = (
                dataframe["high"].rolling(window=kijun_p).max()
                + dataframe["low"].rolling(window=kijun_p).min()
            ) / 2

        # Senkou B fixe
        dataframe["senkou_b"] = (
            dataframe["high"].rolling(window=self.SENKOU_B_PERIOD).max()
            + dataframe["low"].rolling(window=self.SENKOU_B_PERIOD).min()
        ) / 2

        # Senkou A pour toutes les combos tenkan x kijun
        for tenkan_p in range(self.tenkan_period.low, self.tenkan_period.high + 1):
            for kijun_p in range(self.kijun_period.low, self.kijun_period.high + 1):
                col = f"senkou_a_{tenkan_p}_{kijun_p}"
                dataframe[col] = (
                    dataframe[f"tenkan_{tenkan_p}"] + dataframe[f"kijun_{kijun_p}"]
                ) / 2

        dataframe = CommonIndicators.add_volume_sma(dataframe, period=20)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        tenkan_col = f"tenkan_{self.tenkan_period.value}"
        kijun_col = f"kijun_{self.kijun_period.value}"
        senkou_a_col = f"senkou_a_{self.tenkan_period.value}_{self.kijun_period.value}"

        kumo_top = dataframe[[senkou_a_col, "senkou_b"]].max(axis=1)
        kumo_top_prev = kumo_top.shift(1)

        conditions = (
            (dataframe["close"] > kumo_top)
            & (dataframe[tenkan_col] > dataframe[kijun_col])
            & (dataframe["close"].shift(1) <= kumo_top_prev)
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        tenkan_col = f"tenkan_{self.tenkan_period.value}"
        kijun_col = f"kijun_{self.kijun_period.value}"
        senkou_a_col = f"senkou_a_{self.tenkan_period.value}_{self.kijun_period.value}"
        lb = self.exit_lookback.value

        kumo_bottom = dataframe[[senkou_a_col, "senkou_b"]].min(axis=1)

        # exit_lookback controle la confirmation : close < kumo pendant N bougies
        close_below_kumo = dataframe["close"] < kumo_bottom
        confirmed_below = close_below_kumo
        for i in range(1, lb):
            confirmed_below = confirmed_below & close_below_kumo.shift(i)

        conditions = (
            confirmed_below
            | (dataframe[tenkan_col] < dataframe[kijun_col])
        )

        dataframe.loc[conditions, "exit_long"] = 1
        return dataframe
