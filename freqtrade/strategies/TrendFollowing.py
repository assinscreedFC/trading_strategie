# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATÉGIE : TrendFollowing
# CATÉGORIE : 1 — Fondations
# OUTIL     : Freqtrade (IStrategy)
# ══════════════════════════════════════════════════════════════
#
# DESCRIPTION :
# Trend Following Long-Only : détecte les tendances haussières
# via deux méthodes configurables :
# 1. Golden Cross (EMA rapide croise au-dessus de EMA lente)
# 2. Breakout (prix casse le plus haut sur N périodes)
#
# Le mode d'entrée est configurable via un CategoricalParameter
# (golden_cross, breakout, ou both).
#
# LOGIQUE :
# - ADX > seuil : confirme qu'une tendance existe
# - Volume > moyenne * multiplicateur : confirme la force du mvt
# - Trailing stop adaptatif basé sur l'ATR
# ══════════════════════════════════════════════════════════════

import sys
from pathlib import Path

from pandas import DataFrame

from freqtrade.strategy import (
    IStrategy, IntParameter, DecimalParameter, CategoricalParameter,
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from utils.indicators import CommonIndicators
from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier


class TrendFollowing(IStrategy):
    """
    Trend Following — Golden Cross & Breakout.

    PRINCIPES ANIS SOLIDSCALE :
    ✅ Long-Only (Spot)
    ✅ Double mode d'entrée (configurable)
    ✅ ADX + Volume comme filtres de confirmation
    ✅ Trailing stop adapté à la volatilité
    """

    INTERFACE_VERSION = 3
    can_short = False
    timeframe = "4h"
    startup_candle_count = 210  # EMA-200 + marge

    # ═══════════════════════════════════════════════════════
    # PARAMÈTRES CONFIGURABLES
    # ═══════════════════════════════════════════════════════

    # ── EMA rapide (Golden Cross) ──
    ema_fast_period = IntParameter(10, 100, default=50, space="buy",
                                   optimize=True, load=True)

    # ── EMA lente (Golden Cross) ──
    ema_slow_period = IntParameter(100, 300, default=200, space="buy",
                                   optimize=True, load=True)

    # ── Breakout : période du plus haut ──
    breakout_period = IntParameter(10, 50, default=20, space="buy",
                                   optimize=True, load=True)

    # ── ADX : période ──
    adx_period = IntParameter(7, 30, default=14, space="buy",
                              optimize=True, load=True)

    # ── ADX : seuil minimum de force de tendance ──
    # CHOIX : 25 est le standard. < 20 = pas de tendance,
    # > 25 = tendance confirmée, > 50 = tendance très forte.
    adx_threshold = IntParameter(15, 40, default=25, space="buy",
                                 optimize=True, load=True)

    # ── Volume : multiplicateur minimum pour confirmation ──
    # CHOIX : 1.5x la moyenne. Breakout sans volume = faux signal.
    volume_multiplier = DecimalParameter(1.0, 3.0, default=1.5, decimals=1,
                                         space="buy", optimize=True, load=True)

    # ── Mode d'entrée ──
    # CHOIX : "both" par défaut pour maximiser les opportunités.
    # "golden_cross" seul = plus conservateur mais moins de trades.
    # "breakout" seul = plus agressif mais plus de faux signaux.
    entry_mode = CategoricalParameter(
        ["golden_cross", "breakout", "both"],
        default="both", space="buy", optimize=True, load=True,
    )

    # ── ATR pour le trailing stop adaptatif ──
    atr_period = IntParameter(7, 30, default=14, space="sell",
                              optimize=True, load=True)

    # ── ROI ──
    minimal_roi = {
        "0": 0.15,
        "480": 0.08,
        "960": 0.04,
        "1440": 0.02,
    }

    stoploss = -0.08

    # ── Trailing Stop ──
    trailing_stop = True
    trailing_stop_positive = 0.03
    trailing_stop_positive_offset = 0.05
    trailing_only_offset_is_reached = True

    # ═══════════════════════════════════════════════════════
    # INITIALISATION
    # ═══════════════════════════════════════════════════════

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self._trade_logger = TradeLogger(strategy_name="TrendFollowing")
        self._notifier = TelegramNotifier()
        self._notifier.send_startup_message(
            "TrendFollowing", dry_run=config.get("dry_run", True)
        )

    # ═══════════════════════════════════════════════════════
    # INDICATEURS
    # ═══════════════════════════════════════════════════════

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Indicateurs pour le Trend Following.

        REFACTORING : Tous les indicateurs viennent de CommonIndicators.
        """
        # ── EMAs pour Golden Cross ──
        dataframe = CommonIndicators.add_ema(dataframe, period=self.ema_fast_period.value)
        dataframe = CommonIndicators.add_ema(dataframe, period=self.ema_slow_period.value)

        # ── ADX pour force de tendance ──
        dataframe = CommonIndicators.add_adx(dataframe, period=self.adx_period.value)
        dataframe = CommonIndicators.add_atr(dataframe, period=self.atr_period.value)

        # ── Volume moyen ──
        dataframe = CommonIndicators.add_volume_sma(dataframe, period=20)

        # ── Niveaux de breakout ──
        dataframe = CommonIndicators.add_breakout_levels(
            dataframe, period=self.breakout_period.value
        )

        # ── Calcul du Golden Cross (croisement) ──
        # CHOIX : On détecte le MOMENT du croisement (transition),
        # pas juste la position relative. Cela évite les entrées tardives.
        fast_col = f"ema_{self.ema_fast_period.value}"
        slow_col = f"ema_{self.ema_slow_period.value}"
        dataframe["golden_cross"] = (
            (dataframe[fast_col] > dataframe[slow_col])
            & (dataframe[fast_col].shift(1) <= dataframe[slow_col].shift(1))
        ).astype(int)

        dataframe["death_cross"] = (
            (dataframe[fast_col] < dataframe[slow_col])
            & (dataframe[fast_col].shift(1) >= dataframe[slow_col].shift(1))
        ).astype(int)

        # ── Breakout detection ──
        bp = self.breakout_period.value
        dataframe["breakout_signal"] = (
            (dataframe["close"] > dataframe[f"breakout_high_{bp}"].shift(1))
        ).astype(int)

        return dataframe

    # ═══════════════════════════════════════════════════════
    # SIGNAUX D'ENTRÉE
    # ═══════════════════════════════════════════════════════

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Entrées Trend Following basées sur le mode configuré.

        CONDITIONS COMMUNES :
        - ADX > seuil (tendance confirmée)
        - Volume > moyenne * multiplicateur (liquidité)

        MODE GOLDEN_CROSS : EMA rapide croise au-dessus de EMA lente
        MODE BREAKOUT : Prix casse le plus haut sur N périodes
        MODE BOTH : L'un OU l'autre
        """
        adx_col = f"adx_{self.adx_period.value}"
        mode = self.entry_mode.value

        # ── Conditions communes ──
        common_conditions = (
            (dataframe[adx_col] > self.adx_threshold.value)
            & (dataframe["volume_ratio_20"] > self.volume_multiplier.value)
            & (dataframe["volume"] > 0)
        )

        # ── Golden Cross ──
        gc_condition = dataframe["golden_cross"] == 1

        # ── Breakout ──
        bo_condition = dataframe["breakout_signal"] == 1

        # ── Sélection selon le mode ──
        if mode == "golden_cross":
            entry_condition = gc_condition & common_conditions
        elif mode == "breakout":
            entry_condition = bo_condition & common_conditions
        else:  # "both"
            entry_condition = (gc_condition | bo_condition) & common_conditions

        dataframe.loc[entry_condition, "enter_long"] = 1
        return dataframe

    # ═══════════════════════════════════════════════════════
    # SIGNAUX DE SORTIE
    # ═══════════════════════════════════════════════════════

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Sortie quand la tendance se retourne.

        LOGIQUE :
        - Death Cross (EMA rapide passe sous EMA lente)
        - OU ADX < seuil bas (la tendance s'épuise)
        """
        adx_col = f"adx_{self.adx_period.value}"

        dataframe.loc[
            (
                (dataframe["death_cross"] == 1)
                |
                (dataframe[adx_col] < (self.adx_threshold.value * 0.6))
            )
            &
            (dataframe["volume"] > 0),
            "exit_long",
        ] = 1

        return dataframe

    # ═══════════════════════════════════════════════════════
    # CALLBACKS
    # ═══════════════════════════════════════════════════════

    def confirm_trade_entry(self, pair, order_type, amount, rate, time_in_force,
                            current_time, entry_tag, side, **kwargs) -> bool:
        is_dry = self.config.get("dry_run", True)
        self._trade_logger.log_trade(
            pair=pair, side="buy", price=rate, amount=amount,
            dry_run=is_dry, extra_info=f"mode:{self.entry_mode.value}",
        )
        self._notifier.send_trade_alert(
            "TrendFollowing", pair, "buy", rate, amount, dry_run=is_dry,
        )
        return True

    def confirm_trade_exit(self, pair, trade, order_type, amount, rate,
                           time_in_force, exit_reason, current_time,
                           **kwargs) -> bool:
        is_dry = self.config.get("dry_run", True)
        pnl = trade.calc_profit_ratio(rate) * 100
        self._trade_logger.log_trade(
            pair=pair, side="sell", price=rate, amount=amount,
            pnl=pnl, dry_run=is_dry, extra_info=f"exit:{exit_reason}",
        )
        self._notifier.send_trade_alert(
            "TrendFollowing", pair, "sell", rate, amount, pnl=pnl, dry_run=is_dry,
        )
        return True
