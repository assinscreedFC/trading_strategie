# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATÉGIE : FreqAIXGBoost
# CATÉGORIE : 5 — Intelligence Artificielle
# OUTIL     : Freqtrade + FreqAI (IStrategy)
# ══════════════════════════════════════════════════════════════
#
# DESCRIPTION :
# Modèle prédictif XGBoost intégré via FreqAI.
# Utilise un ensemble de features techniques pour prédire la
# variation de prix future et générer des signaux d'entrée/sortie.
#
# ARCHITECTURE FREQAI :
# 1. Les features sont définies dans feature_engineering_*
# 2. FreqAI entraîne un modèle XGBoost sur ces features
# 3. Le modèle produit des prédictions (colonne &-xxx)
# 4. populate_entry_trend utilise les prédictions pour trader
#
# CONFIGURABILITÉ :
# → Seuils de prédiction, nombre de features, périodes
# → Tous via IntParameter/DecimalParameter
#
# PRÉ-REQUIS :
# → FreqAI doit être activé dans config.json
# → Section "freqai" requise dans la config
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


class FreqAIXGBoost(IStrategy):
    """
    FreqAI XGBoost — Modèle prédictif ML pour entrées Spot.

    PRINCIPES ANIS SOLIDSCALE :
    ✅ Long-Only (Spot)
    ✅ Modèle ML (XGBoost) via FreqAI
    ✅ Features techniques configurables
    ✅ Seuils de prédiction ajustables
    """

    INTERFACE_VERSION = 3
    can_short = False
    timeframe = "1h"
    startup_candle_count = 100

    # ═══════════════════════════════════════════════════════
    # PARAMÈTRES CONFIGURABLES
    # ═══════════════════════════════════════════════════════

    # ── Seuil de prédiction pour entrer (le modèle prédit un % de hausse) ──
    # CHOIX : 0.5% par défaut. Le modèle doit prédire au moins cette
    # hausse pour déclencher un achat.
    prediction_entry_threshold = DecimalParameter(
        0.1, 2.0, default=0.5, decimals=1,
        space="buy", optimize=True, load=True,
    )

    # ── Seuil de prédiction pour sortir ──
    prediction_exit_threshold = DecimalParameter(
        -1.0, 0.5, default=-0.3, decimals=1,
        space="sell", optimize=True, load=True,
    )

    # ── RSI comme feature et filtre ──
    rsi_period = IntParameter(7, 30, default=14, space="buy",
                              optimize=True, load=True)

    # ── Nombre de périodes pour les features ──
    feature_lookback = IntParameter(5, 30, default=10, space="buy",
                                    optimize=True, load=True)

    # ── ROI ──
    minimal_roi = {
        "0": 0.10,
        "240": 0.05,
        "720": 0.02,
    }

    stoploss = -0.06

    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.04
    trailing_only_offset_is_reached = True

    # ═══════════════════════════════════════════════════════
    # INITIALISATION
    # ═══════════════════════════════════════════════════════

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self._trade_logger = TradeLogger(strategy_name="FreqAIXGBoost")
        self._notifier = TelegramNotifier()
        self._notifier.send_startup_message(
            "FreqAIXGBoost", dry_run=config.get("dry_run", True)
        )

    # ═══════════════════════════════════════════════════════
    # FEATURE ENGINEERING — FreqAI
    # ═══════════════════════════════════════════════════════

    def feature_engineering_expand_all(
        self, dataframe: DataFrame, period: int, metadata: dict, **kwargs,
    ) -> DataFrame:
        """
        Features avec expansion automatique par période.

        FreqAI appelle cette méthode pour chaque période dans
        "include_timeframes". Les features sont automatiquement
        étiquetées avec la période.

        FEATURES GÉNÉRÉES :
        - RSI : force relative
        - MACD : momentum
        - Volume ratio : activité relative
        - Returns : rendements sur N périodes
        """
        # ── RSI ──
        dataframe = CommonIndicators.add_rsi(dataframe, period=self.rsi_period.value)
        dataframe["%-rsi"] = dataframe[f"rsi_{self.rsi_period.value}"]

        # ── MACD ──
        dataframe = CommonIndicators.add_macd(dataframe)
        dataframe["%-macd"] = dataframe["macd"]
        dataframe["%-macd_signal"] = dataframe["macd_signal"]
        dataframe["%-macd_histogram"] = dataframe["macd_histogram"]

        # ── Volume ratio ──
        dataframe = CommonIndicators.add_volume_sma(dataframe, period=20)
        dataframe["%-volume_ratio"] = dataframe["volume_ratio_20"]

        # ── Returns (rendements log) ──
        dataframe["%-return_1"] = np.log(dataframe["close"] / dataframe["close"].shift(1))
        dataframe["%-return_5"] = np.log(dataframe["close"] / dataframe["close"].shift(5))
        dataframe["%-return_10"] = np.log(
            dataframe["close"]
            / dataframe["close"].shift(self.feature_lookback.value)
        )

        # ── Volatilité ──
        dataframe["%-volatility"] = dataframe["close"].pct_change().rolling(
            self.feature_lookback.value
        ).std()

        # ── High-Low range ──
        dataframe["%-hl_range"] = (dataframe["high"] - dataframe["low"]) / dataframe["close"]

        return dataframe

    def feature_engineering_expand_basic(
        self, dataframe: DataFrame, metadata: dict, **kwargs,
    ) -> DataFrame:
        """
        Features de base sans expansion par période.

        FEATURES :
        - Price position relative aux BB
        - ATR normalisé
        """
        dataframe = CommonIndicators.add_bollinger_bands(dataframe, period=20)
        dataframe = CommonIndicators.add_atr(dataframe, period=14)

        # Position du prix dans les BB (0 = bande basse, 1 = bande haute)
        bb_range = dataframe["bb_upper_20"] - dataframe["bb_lower_20"]
        dataframe["%-bb_position"] = (
            (dataframe["close"] - dataframe["bb_lower_20"])
            / bb_range.replace(0, np.nan)
        )

        # ATR normalisé par le prix
        dataframe["%-atr_normalized"] = dataframe["atr_14"] / dataframe["close"]

        return dataframe

    def set_freqai_targets(self, dataframe: DataFrame, metadata: dict, **kwargs) -> DataFrame:
        """
        Définit la target pour l'entraînement du modèle.

        TARGET : Variation du prix dans les N prochaines bougies.
        Le modèle apprend à prédire cette variation pour anticiper
        les mouvements.
        """
        # CHOIX : On prédit la variation sur les 4 prochaines heures (4 bougies 1h)
        # Configurable via feature_lookback pour d'autres timeframes
        dataframe["&-s_close"] = (
            dataframe["close"]
            .shift(-4)
            .pct_change(4)
            * 100  # En pourcentage
        )
        return dataframe

    # ═══════════════════════════════════════════════════════
    # INDICATEURS
    # ═══════════════════════════════════════════════════════

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Les indicateurs principaux sont gérés par FreqAI.
        On ajoute ici uniquement les indicateurs pour le filtrage.
        """
        dataframe = CommonIndicators.add_rsi(dataframe, period=self.rsi_period.value)
        return dataframe

    # ═══════════════════════════════════════════════════════
    # SIGNAUX D'ENTRÉE
    # ═══════════════════════════════════════════════════════

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Entrée basée sur la prédiction du modèle XGBoost.

        LOGIQUE :
        - Le modèle prédit une hausse > seuil → BUY
        - Filtré par RSI (pas d'achat en surachat extrême)
        """
        rsi_col = f"rsi_{self.rsi_period.value}"

        # ── La colonne de prédiction FreqAI ──
        # FreqAI crée automatiquement la colonne "&-s_close"
        # avec les prédictions du modèle
        if "&-s_close" in dataframe.columns:
            dataframe.loc[
                (
                    (dataframe["&-s_close"] > self.prediction_entry_threshold.value)
                    &
                    (dataframe[rsi_col] < 75)
                    &
                    (dataframe["volume"] > 0)
                ),
                "enter_long",
            ] = 1

        return dataframe

    # ═══════════════════════════════════════════════════════
    # SIGNAUX DE SORTIE
    # ═══════════════════════════════════════════════════════

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Sortie quand le modèle prédit une baisse.
        """
        if "&-s_close" in dataframe.columns:
            dataframe.loc[
                (
                    (dataframe["&-s_close"] < self.prediction_exit_threshold.value)
                    &
                    (dataframe["volume"] > 0)
                ),
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
            dry_run=is_dry, extra_info="freqai_xgboost",
        )
        self._notifier.send_trade_alert(
            "FreqAIXGBoost", pair, "buy", rate, amount, dry_run=is_dry,
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
            "FreqAIXGBoost", pair, "sell", rate, amount, pnl=pnl, dry_run=is_dry,
        )
        return True
