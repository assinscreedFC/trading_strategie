# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATÉGIE : ParabolicSARTrend
# CATÉGORIE : Nouvelle — Trend Following avec Parabolic SAR
# ══════════════════════════════════════════════════════════════
#
# LOGIQUE :
# 1. SAR flip bullish (close > SAR ET close.shift(1) < SAR.shift(1))
# 2. Close > EMA (filtre de tendance)
# 3. ADX > seuil (force de tendance suffisante)
# 4. Sortie : SAR flip bearish (close < SAR)
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


def _manual_psar(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    af_step: float = 0.02,
    af_max: float = 0.2,
) -> np.ndarray:
    """Calcul manuel du Parabolic SAR (fallback sans pandas_ta)."""
    length = len(close)
    psar = np.full(length, np.nan)
    bull = True
    af = af_step
    ep = low[0]
    hp = high[0]
    lp = low[0]
    psar[0] = high[0]

    for i in range(1, length):
        if bull:
            psar[i] = psar[i - 1] + af * (hp - psar[i - 1])
            psar[i] = min(psar[i], low[i - 1])
            if i >= 2:
                psar[i] = min(psar[i], low[i - 2])
            if low[i] < psar[i]:
                bull = False
                psar[i] = hp
                lp = low[i]
                af = af_step
            else:
                if high[i] > hp:
                    hp = high[i]
                    af = min(af + af_step, af_max)
        else:
            psar[i] = psar[i - 1] + af * (lp - psar[i - 1])
            psar[i] = max(psar[i], high[i - 1])
            if i >= 2:
                psar[i] = max(psar[i], high[i - 2])
            if high[i] > psar[i]:
                bull = True
                psar[i] = lp
                hp = high[i]
                af = af_step
            else:
                if low[i] < lp:
                    lp = low[i]
                    af = min(af + af_step, af_max)

    return psar


class ParabolicSARTrend(IStrategy):
    INTERFACE_VERSION = 3
    can_short = False
    timeframe = "1h"
    startup_candle_count = 100

    minimal_roi = {"0": 0.10, "360": 0.05, "720": 0.02}
    stoploss = -0.05
    trailing_stop = True
    trailing_stop_positive = 0.015
    trailing_stop_positive_offset = 0.025
    trailing_only_offset_is_reached = True

    # ── Buy params ──
    sar_af = DecimalParameter(0.01, 0.04, default=0.02, decimals=2, space="buy")
    sar_max_af = DecimalParameter(0.1, 0.3, default=0.2, decimals=1, space="buy")
    ema_period = IntParameter(30, 70, default=50, space="buy")
    adx_period = IntParameter(7, 30, default=14, space="buy")
    adx_threshold = IntParameter(15, 35, default=25, space="buy")

    _logger = None
    _notifier = None

    def _init_utils(self) -> None:
        if self._logger is None:
            self._logger = TradeLogger(strategy_name="ParabolicSARTrend")
            self._notifier = TelegramNotifier()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()
        dataframe = CommonIndicators.add_ema(dataframe, period=self.ema_period.value)
        dataframe = CommonIndicators.add_adx(dataframe, period=self.adx_period.value)

        # Parabolic SAR
        try:
            import pandas_ta as pta
            psar_df = pta.psar(
                dataframe["high"], dataframe["low"], dataframe["close"],
                af0=self.sar_af.value, af=self.sar_af.value, max_af=self.sar_max_af.value,
            )
            if psar_df is not None:
                # pandas_ta retourne long/short/af/reversal — on combine long et short
                long_col = [c for c in psar_df.columns if "PSARl" in c]
                short_col = [c for c in psar_df.columns if "PSARs" in c]
                if long_col and short_col:
                    dataframe["psar"] = psar_df[long_col[0]].fillna(psar_df[short_col[0]])
                else:
                    raise ValueError("Colonnes PSAR non trouvées")
            else:
                raise ValueError("psar retourne None")
        except Exception:
            dataframe["psar"] = _manual_psar(
                dataframe["high"].values,
                dataframe["low"].values,
                dataframe["close"].values,
                af_step=self.sar_af.value,
                af_max=self.sar_max_af.value,
            )

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        ema_col = f"ema_{self.ema_period.value}"
        adx_col = f"adx_{self.adx_period.value}"

        conditions = (
            (dataframe["close"] > dataframe["psar"])
            & (dataframe["close"].shift(1) < dataframe["psar"].shift(1))
            & (dataframe["close"] > dataframe[ema_col])
            & (dataframe[adx_col] > self.adx_threshold.value)
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = (
            dataframe["close"] < dataframe["psar"]
        )

        dataframe.loc[conditions, "exit_long"] = 1
        return dataframe
