# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATEGIE : RegimeSwitcherLite
# CATEGORIE : Meta — Switching automatique par regime de marche
# ══════════════════════════════════════════════════════════════
#
# ARCHITECTURE :
# 1. Detection regime sur BTC/USDT 1d (ADX + EMA direction)
#    - Bull  : ADX > 25 + EMA montante  → ChoppinessBreakout logic
#    - Bear  : ADX > 25 + EMA descendante → SuperTrendADX logic
#    - Stable: ADX < 20                   → DCA logic
#    - Transition: 20 <= ADX <= 25        → NO TRADE
#
# 2. Sous-logiques inlinees (0 params hyperopt, anti-overfitting)
#    - Bull  : Choppiness < 38 + breakout 20 + EMA50 filter
#    - Bear  : SuperTrend(ATR11, mult3.0) + ADX14>25 + EMA200
#    - Stable: DCA interval=30 bougies (achat regulier)
#
# 3. Gestion du risque adaptative par regime
#    - Bull  : stake=20, stoploss=-8%
#    - Bear  : stake=10, stoploss=-4%
#    - Stable: stake=15, stoploss=-6%
#
# Tous les params sont FIXES — valides par tournament Phase 2.
# ══════════════════════════════════════════════════════════════

import sys
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
from pandas import DataFrame

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy, merge_informative_pair

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from utils.indicators import CommonIndicators
from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier


def _calc_supertrend(close, high, low, atr, mult):
    """SuperTrend vectorise."""
    n = len(close)
    hl2 = (high + low) / 2
    ub = hl2 + mult * atr
    lb = hl2 - mult * atr

    st_upper = np.full(n, np.nan)
    st_lower = np.full(n, np.nan)
    direction = np.ones(n, dtype=int)

    st_lower[0] = lb[0]
    st_upper[0] = ub[0]

    for i in range(1, n):
        st_lower[i] = lb[i] if (lb[i] > st_lower[i - 1] or close[i - 1] < st_lower[i - 1]) else st_lower[i - 1]
        st_upper[i] = ub[i] if (ub[i] < st_upper[i - 1] or close[i - 1] > st_upper[i - 1]) else st_upper[i - 1]

        if direction[i - 1] == 1:
            direction[i] = -1 if close[i] < st_lower[i] else 1
        else:
            direction[i] = 1 if close[i] > st_upper[i] else -1

    return direction


class RegimeSwitcherLite(IStrategy):
    INTERFACE_VERSION = 3
    can_short = False
    timeframe = "4h"
    startup_candle_count = 250  # EMA200 + marge

    # ROI conservateur (compromis entre les 3 regimes)
    minimal_roi = {"0": 0.10, "240": 0.05, "720": 0.03, "1440": 0.01}
    stoploss = -0.06  # Default, override par custom_stoploss
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.04
    trailing_only_offset_is_reached = True

    # ── 0 params hyperopt — tout fixe ──

    # Regime detection (BTC 1d)
    REGIME_ADX_PERIOD = 14
    REGIME_EMA_PERIOD = 50
    REGIME_ADX_TREND = 25
    REGIME_ADX_RANGE = 20
    REGIME_EMA_LOOKBACK = 5

    # Bull logic (ChoppinessBreakout)
    BULL_CHOP_PERIOD = 14
    BULL_CHOP_THRESHOLD = 38
    BULL_BREAKOUT_PERIOD = 20
    BULL_EMA_FILTER = 50
    BULL_CHOP_EXIT = 70

    # Bear logic (SuperTrendADX)
    BEAR_ATR_PERIOD = 11
    BEAR_ATR_MULT = 3.0
    BEAR_ADX_PERIOD = 14
    BEAR_ADX_THRESHOLD = 25
    BEAR_EMA_PERIOD = 200
    BEAR_ADX_EXIT = 24

    # Stable logic (DCA)
    STABLE_DCA_INTERVAL = 30

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
            self._logger = TradeLogger(strategy_name="RegimeSwitcherLite")
            self._notifier = TelegramNotifier()

    def informative_pairs(self) -> List[Tuple[str, str]]:
        return [("BTC/USDT", "1d")]

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()

        # ── 1. Regime detection via BTC/USDT 1d ──
        btc_1d = self.dp.get_pair_dataframe("BTC/USDT", "1d")
        btc_1d = CommonIndicators.add_adx(btc_1d, period=self.REGIME_ADX_PERIOD)
        btc_1d = CommonIndicators.add_ema(btc_1d, period=self.REGIME_EMA_PERIOD)

        adx_col = f"adx_{self.REGIME_ADX_PERIOD}"
        ema_col = f"ema_{self.REGIME_EMA_PERIOD}"
        lb = self.REGIME_EMA_LOOKBACK

        ema_rising = btc_1d[ema_col] > btc_1d[ema_col].shift(lb)
        ema_falling = btc_1d[ema_col] < btc_1d[ema_col].shift(lb)

        btc_1d["regime"] = "transition"
        btc_1d.loc[(btc_1d[adx_col] > self.REGIME_ADX_TREND) & ema_rising, "regime"] = "bull"
        btc_1d.loc[(btc_1d[adx_col] > self.REGIME_ADX_TREND) & ema_falling, "regime"] = "bear"
        btc_1d.loc[btc_1d[adx_col] < self.REGIME_ADX_RANGE, "regime"] = "stable"

        dataframe = merge_informative_pair(dataframe, btc_1d, "4h", "1d", ffill=True)

        # ── 2. Bull indicators (Choppiness Breakout) ──
        dataframe = CommonIndicators.add_choppiness(dataframe, period=self.BULL_CHOP_PERIOD)
        dataframe = CommonIndicators.add_breakout_levels(dataframe, period=self.BULL_BREAKOUT_PERIOD)
        dataframe = CommonIndicators.add_ema(dataframe, period=self.BULL_EMA_FILTER)
        dataframe = CommonIndicators.add_volume_sma(dataframe, period=20)

        # ── 3. Bear indicators (SuperTrend + ADX) ──
        dataframe = CommonIndicators.add_atr(dataframe, period=self.BEAR_ATR_PERIOD)
        dataframe = CommonIndicators.add_adx(dataframe, period=self.BEAR_ADX_PERIOD)
        dataframe = CommonIndicators.add_ema(dataframe, period=self.BEAR_EMA_PERIOD)

        atr_vals = dataframe[f"atr_{self.BEAR_ATR_PERIOD}"].values
        dataframe["st_direction"] = _calc_supertrend(
            dataframe["close"].values, dataframe["high"].values,
            dataframe["low"].values, atr_vals, self.BEAR_ATR_MULT
        )

        # ── 4. Stable indicators (DCA) ──
        dataframe["candle_index"] = np.arange(len(dataframe))

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        regime = dataframe["regime_1d"]

        # Bull: Choppiness Breakout
        bull_entry = (
            (regime == "bull")
            & (dataframe[f"choppiness_{self.BULL_CHOP_PERIOD}"] < self.BULL_CHOP_THRESHOLD)
            & (dataframe["close"] > dataframe[f"breakout_high_{self.BULL_BREAKOUT_PERIOD}"].shift(1))
            & (dataframe["volume"] > dataframe["volume_sma_20"])
            & (dataframe["close"] > dataframe[f"ema_{self.BULL_EMA_FILTER}"])
        )

        # Bear: SuperTrend + ADX
        bear_entry = (
            (regime == "bear")
            & (dataframe["st_direction"] == 1)
            & (dataframe[f"adx_{self.BEAR_ADX_PERIOD}"] > self.BEAR_ADX_THRESHOLD)
            & (dataframe["close"] > dataframe[f"ema_{self.BEAR_EMA_PERIOD}"])
        )

        # Stable: DCA (buy every N candles)
        stable_entry = (
            (regime == "stable")
            & (dataframe["candle_index"] % self.STABLE_DCA_INTERVAL == 0)
        )

        dataframe.loc[
            (bull_entry | bear_entry | stable_entry) & (dataframe["volume"] > 0),
            "enter_long"
        ] = 1

        # Tag pour tracking
        dataframe.loc[bull_entry, "enter_tag"] = "bull_chop_breakout"
        dataframe.loc[bear_entry, "enter_tag"] = "bear_supertrend"
        dataframe.loc[stable_entry, "enter_tag"] = "stable_dca"

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        regime = dataframe["regime_1d"]

        # Bull exit: choppiness monte OU breakdown
        bull_exit = (
            (regime == "bull")
            & (
                (dataframe[f"choppiness_{self.BULL_CHOP_PERIOD}"] > self.BULL_CHOP_EXIT)
                | (dataframe["close"] < dataframe[f"breakout_low_{self.BULL_BREAKOUT_PERIOD}"].shift(1))
            )
        )

        # Bear exit: SuperTrend flip OU ADX faiblit
        bear_exit = (
            (regime == "bear")
            & (
                (dataframe["st_direction"] == -1)
                | (dataframe[f"adx_{self.BEAR_ADX_PERIOD}"] < self.BEAR_ADX_EXIT)
            )
        )

        # Stable exit: pas de signal actif, trailing stop gere
        # Mais on exit si le regime change vers bear
        regime_change_exit = (
            (regime == "bear")
            & (dataframe["regime_1d"].shift(1) != "bear")
        )

        dataframe.loc[bull_exit | bear_exit | regime_change_exit, "exit_long"] = 1
        return dataframe

    def confirm_trade_entry(
        self, pair: str, order_type: str, amount: float,
        rate: float, time_in_force: str, current_time, entry_tag: Optional[str],
        side: str, **kwargs
    ) -> bool:
        """Rejeter si regime == transition ou regime vient de changer."""
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df.empty:
            return False

        last = df.iloc[-1]
        regime = last.get("regime_1d", "transition")

        # Pas de trade en transition
        if regime == "transition":
            return False

        # Pas de trade si regime a change dans les 2 dernieres bougies
        if len(df) >= 3:
            prev_regimes = df["regime_1d"].iloc[-3:]
            if prev_regimes.nunique() > 1:
                return False

        return True

    def custom_stake_amount(
        self, pair: str, current_time, current_rate: float,
        proposed_stake: float, min_stake: Optional[float],
        max_stake: float, leverage: float, entry_tag: Optional[str],
        side: str, **kwargs
    ) -> float:
        """Stake adapte par regime."""
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df.empty:
            return proposed_stake

        regime = df.iloc[-1].get("regime_1d", "stable")

        if regime == "bull":
            return 20.0
        elif regime == "bear":
            return 10.0
        else:  # stable
            return 15.0

    def custom_stoploss(
        self, pair: str, trade: Trade, current_time,
        current_rate: float, current_profit: float, after_fill: bool,
        **kwargs
    ) -> float:
        """Stoploss adapte par regime."""
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df.empty:
            return self.stoploss

        regime = df.iloc[-1].get("regime_1d", "stable")

        if regime == "bull":
            return -0.08
        elif regime == "bear":
            return -0.04
        else:  # stable
            return -0.06
