# Rapport — 2026-03-22 04:22

## Parametres de validation
- IS (In-Sample): 20250301-20251130 (9 mois — hyperopt)
- OOS (Out-of-Sample): 20251201-20260319 (3.5 mois — validation)
- Min trades OOS: 20

## Resultats par strategie et regime

| Strategie | Regime | Trades | Profit% | DD% | WR% | PF | Sharpe | Expectancy | ConsecLoss |
|-----------|--------|--------|---------|-----|-----|-----|--------|------------|------------|
| ADXRegimeFilter | baissier | 6 | -3.67 | 3.78 | 33.3 | 0.05 | -2.82 | -0.61 | 2 |
| ADXRegimeFilter | haussier | 1 | 0.25 | 0.00 | 100.0 | 0.00 | -100.00 | 0.25 | 0 |
| ADXRegimeFilter | is_9m | 15 | 2.92 | 0.61 | 86.7 | 5.70 | 0.85 | 0.19 | 1 |
| ADXRegimeFilter | is_9m_post_hyperopt | 8 | 2.10 | 0.00 | 100.0 | 0.00 | 1.35 | 0.26 | 0 |
| ADXRegimeFilter | oos | 9 | -3.39 | 3.77 | 44.4 | 0.13 | -1.09 | -0.38 | 2 |
| ADXRegimeFilter | stable | 1 | 0.23 | 0.00 | 100.0 | 0.00 | -100.00 | 0.23 | 0 |
| BollingerMACDReversal | baissier | 4 | -2.83 | 2.99 | 50.0 | 0.05 | -1.46 | -0.71 | 2 |
| BollingerMACDReversal | haussier | 0 | 0.00 | 0.00 | 0.0 | 0.00 | 0.00 | 0.00 | 0 |
| BollingerMACDReversal | is_9m | 4 | 0.66 | 0.00 | 100.0 | 0.00 | 0.80 | 0.17 | 0 |
| BollingerMACDReversal | is_9m_post_hyperopt | 10 | 2.60 | 0.00 | 100.0 | 0.00 | 1.50 | 0.26 | 0 |
| BollingerMACDReversal | oos | 7 | -2.87 | 3.17 | 57.1 | 0.10 | -0.73 | -0.41 | 3 |
| BollingerMACDReversal | stable | 1 | 0.49 | 0.00 | 100.0 | 0.00 | -100.00 | 0.49 | 0 |
| EMATripleCross | baissier | 0 | 0.00 | 0.00 | 0.0 | 0.00 | 0.00 | 0.00 | 0 |
| EMATripleCross | haussier | 1 | 0.30 | 0.00 | 100.0 | 0.00 | -100.00 | 0.30 | 0 |
| EMATripleCross | is_9m | 7 | 2.22 | 0.00 | 100.0 | 0.00 | 1.31 | 0.32 | 0 |
| EMATripleCross | is_9m_post_hyperopt | 9 | 3.33 | 0.00 | 100.0 | 0.00 | 1.08 | 0.37 | 1 |
| EMATripleCross | oos | 3 | 0.22 | 0.37 | 33.3 | 1.60 | 0.10 | 0.07 | 1 |
| EMATripleCross | stable | 0 | 0.00 | 0.00 | 0.0 | 0.00 | 0.00 | 0.00 | 0 |
| FibonacciPullback | baissier | 8 | -6.21 | 6.44 | 37.5 | 0.11 | -2.53 | -0.78 | 4 |
| FibonacciPullback | haussier | 0 | 0.00 | 0.00 | 0.0 | 0.00 | 0.00 | 0.00 | 0 |
| FibonacciPullback | is_9m | 11 | 1.73 | 0.00 | 100.0 | 0.00 | 1.08 | 0.16 | 1 |
| FibonacciPullback | is_9m_post_hyperopt | 39 | 5.41 | 0.41 | 87.2 | 9.45 | 2.35 | 0.14 | 1 |
| FibonacciPullback | oos | 12 | -6.94 | 7.16 | 33.3 | 0.10 | -1.42 | -0.58 | 5 |
| FibonacciPullback | stable | 5 | 0.59 | 0.09 | 80.0 | 7.74 | 1.48 | 0.12 | 1 |
| IchimokuBreakout | baissier | 18 | 0.40 | 0.80 | 44.4 | 1.18 | 0.53 | 0.02 | 3 |
| IchimokuBreakout | haussier | 11 | 1.07 | 0.37 | 54.5 | 2.51 | 2.19 | 0.10 | 2 |
| IchimokuBreakout | hyperopt | — | — | — | — | — | — | — | — |
| IchimokuBreakout | is_9m | 87 | -1.75 | 3.87 | 42.5 | 0.87 | -0.40 | -0.02 | 9 |
| IchimokuBreakout | oos | 38 | 0.93 | 1.16 | 47.4 | 1.22 | 0.57 | 0.02 | 5 |
| IchimokuBreakout | stable | 10 | 0.77 | 0.83 | 40.0 | 1.92 | 1.52 | 0.08 | 6 |
| KAMAAdaptiveTrend | baissier | 1 | 0.08 | 0.00 | 100.0 | 0.00 | -100.00 | 0.08 | 0 |
| KAMAAdaptiveTrend | haussier | 1 | -0.12 | 0.12 | 0.0 | 0.00 | -100.00 | -0.12 | 1 |
| KAMAAdaptiveTrend | hyperopt | — | — | — | — | — | — | — | — |
| KAMAAdaptiveTrend | is_9m | 4 | 1.16 | 0.00 | 100.0 | 0.00 | 0.70 | 0.29 | 0 |
| KAMAAdaptiveTrend | oos | 3 | 0.32 | 0.00 | 100.0 | 0.00 | 1.43 | 0.11 | 0 |
| KAMAAdaptiveTrend | stable | 0 | 0.00 | 0.00 | 0.0 | 0.00 | 0.00 | 0.00 | 0 |
| MACDDivergence | baissier | 17 | -2.00 | 4.73 | 35.3 | 0.58 | -1.55 | -0.12 | 11 |
| MACDDivergence | haussier | 12 | 3.81 | 0.28 | 66.7 | 9.15 | 5.59 | 0.32 | 1 |
| MACDDivergence | is_9m | 94 | 10.33 | 3.83 | 48.9 | 1.71 | 1.56 | 0.11 | 8 |
| MACDDivergence | is_9m_post_hyperopt | 63 | 11.61 | 2.38 | 54.0 | 2.60 | 1.81 | 0.18 | 6 |
| MACDDivergence | oos | 38 | -3.91 | 7.97 | 34.2 | 0.60 | -1.39 | -0.10 | 16 |
| MACDDivergence | stable | 4 | 1.88 | 0.21 | 75.0 | 9.94 | 2.60 | 0.47 | 1 |
| MARibbonStack | baissier | 3 | 0.25 | 0.26 | 66.7 | 1.98 | 0.42 | 0.08 | 1 |
| MARibbonStack | haussier | 5 | 2.07 | 0.38 | 60.0 | 6.40 | 2.10 | 0.41 | 2 |
| MARibbonStack | hyperopt | — | — | — | — | — | — | — | — |
| MARibbonStack | is_9m | 72 | 7.79 | 3.31 | 38.9 | 1.85 | 1.20 | 0.11 | 13 |
| MARibbonStack | oos | 26 | 0.33 | 1.78 | 34.6 | 1.08 | 0.16 | 0.01 | 7 |
| MARibbonStack | stable | 7 | 0.24 | 1.24 | 28.6 | 1.20 | 0.30 | 0.03 | 5 |
| MoneyFlowIndex | baissier | — | — | — | — | — | — | — | — |
| MoneyFlowIndex | haussier | — | — | — | — | — | — | — | — |
| MoneyFlowIndex | is_9m | 16 | 2.18 | 0.00 | 100.0 | 0.00 | 1.62 | 0.14 | 3 |
| MoneyFlowIndex | is_9m_post_hyperopt | 10 | 1.51 | 0.00 | 100.0 | 0.00 | 1.10 | 0.15 | 1 |
| MoneyFlowIndex | oos | 2 | 0.18 | 0.00 | 100.0 | 0.00 | 0.35 | 0.09 | 1 |
| MoneyFlowIndex | stable | — | — | — | — | — | — | — | — |
| OBVDivergence | baissier | 9 | -1.49 | 1.49 | 22.2 | 0.28 | -1.96 | -0.17 | 4 |
| OBVDivergence | haussier | 12 | 3.10 | 0.44 | 83.3 | 7.77 | 5.42 | 0.26 | 1 |
| OBVDivergence | is_9m | 27 | 3.95 | 0.62 | 74.1 | 3.85 | 1.06 | 0.15 | 1 |
| OBVDivergence | is_9m_post_hyperopt | 69 | 9.18 | 1.10 | 72.5 | 3.48 | 2.21 | 0.13 | 3 |
| OBVDivergence | oos | 33 | -5.82 | 7.59 | 39.4 | 0.36 | -1.41 | -0.18 | 8 |
| OBVDivergence | stable | 4 | -0.08 | 0.08 | 50.0 | 0.12 | -1.45 | -0.02 | 1 |
| OBVTrendConfirm | baissier | 0 | 0.00 | 0.00 | 0.0 | 0.00 | 0.00 | 0.00 | 0 |
| OBVTrendConfirm | haussier | 1 | 0.14 | 0.00 | 100.0 | 0.00 | -100.00 | 0.14 | 0 |
| OBVTrendConfirm | is_9m | 7 | 0.73 | 0.04 | 85.7 | 18.17 | 0.75 | 0.10 | 1 |
| OBVTrendConfirm | is_9m_post_hyperopt | 1 | 0.14 | 0.00 | 100.0 | 0.00 | -100.00 | 0.14 | 0 |
| OBVTrendConfirm | oos | 0 | 0.00 | 0.00 | 0.0 | 0.00 | 0.00 | 0.00 | 0 |
| OBVTrendConfirm | stable | 0 | 0.00 | 0.00 | 0.0 | 0.00 | 0.00 | 0.00 | 0 |
| RSIDivergence | baissier | 9 | 1.19 | 0.00 | 100.0 | 0.00 | 5.60 | 0.13 | 2 |
| RSIDivergence | haussier | 10 | 0.07 | 1.55 | 70.0 | 1.04 | 0.08 | 0.01 | 2 |
| RSIDivergence | is_9m | 47 | 6.91 | 0.24 | 80.9 | 9.25 | 3.22 | 0.15 | 2 |
| RSIDivergence | is_9m_post_hyperopt | 46 | 7.55 | 0.00 | 100.0 | 0.00 | 4.35 | 0.16 | 2 |
| RSIDivergence | oos | 27 | 0.88 | 3.43 | 77.8 | 1.23 | 0.29 | 0.03 | 4 |
| RSIDivergence | stable | 7 | 0.99 | 0.00 | 100.0 | 0.00 | 4.48 | 0.14 | 1 |
| RangeBreakoutVolume | baissier | 0 | 0.00 | 0.00 | 0.0 | 0.00 | 0.00 | 0.00 | 0 |
| RangeBreakoutVolume | haussier | 0 | 0.00 | 0.00 | 0.0 | 0.00 | 0.00 | 0.00 | 0 |
| RangeBreakoutVolume | is_9m | 36 | 1.82 | 1.01 | 41.7 | 1.95 | 0.71 | 0.05 | 8 |
| RangeBreakoutVolume | is_9m_post_hyperopt | 9 | 2.52 | 0.17 | 66.7 | 15.62 | 0.60 | 0.28 | 3 |
| RangeBreakoutVolume | oos | 3 | -0.27 | 0.27 | 0.0 | 0.00 | -1.06 | -0.09 | 3 |
| RangeBreakoutVolume | stable | 1 | -0.14 | 0.14 | 0.0 | 0.00 | -100.00 | -0.14 | 1 |
| SmartMoneyConcepts | baissier | 9 | 0.65 | 0.49 | 44.4 | 2.33 | 1.13 | 0.07 | 3 |
| SmartMoneyConcepts | haussier | 4 | -0.25 | 0.33 | 25.0 | 0.25 | -0.87 | -0.06 | 3 |
| SmartMoneyConcepts | is_9m | 59 | 6.72 | 0.47 | 66.1 | 4.56 | 2.64 | 0.11 | 4 |
| SmartMoneyConcepts | is_9m_post_hyperopt | 41 | 4.69 | 0.21 | 65.9 | 6.26 | 2.08 | 0.11 | 3 |
| SmartMoneyConcepts | oos | 18 | 1.19 | 0.57 | 55.6 | 2.51 | 1.13 | 0.07 | 4 |
| SmartMoneyConcepts | stable | 2 | 0.51 | 0.00 | 100.0 | 0.00 | 5.45 | 0.26 | 0 |
| TripleScreenElder | baissier | 5 | -0.29 | 1.04 | 40.0 | 0.72 | -0.28 | -0.06 | 3 |
| TripleScreenElder | haussier | 0 | 0.00 | 0.00 | 0.0 | 0.00 | 0.00 | 0.00 | 0 |
| TripleScreenElder | is_9m | 4 | 0.94 | 0.00 | 100.0 | 0.00 | 0.81 | 0.23 | 0 |
| TripleScreenElder | is_9m_post_hyperopt | 5 | 0.72 | 0.00 | 100.0 | 0.00 | 2.30 | 0.14 | 0 |
| TripleScreenElder | oos | 5 | -0.29 | 1.04 | 40.0 | 0.72 | -0.12 | -0.06 | 3 |
| TripleScreenElder | stable | 0 | 0.00 | 0.00 | 0.0 | 0.00 | 0.00 | 0.00 | 0 |
| VolatilityBreakout | baissier | 4 | 0.24 | 0.13 | 50.0 | 2.84 | 0.69 | 0.06 | 2 |
| VolatilityBreakout | haussier | 3 | -0.38 | 0.40 | 33.3 | 0.05 | -1.10 | -0.13 | 2 |
| VolatilityBreakout | is_9m | 25 | 1.84 | 0.06 | 88.0 | 27.25 | 1.94 | 0.07 | 2 |
| VolatilityBreakout | is_9m_post_hyperopt | 41 | 3.53 | 0.18 | 78.0 | 14.92 | 2.66 | 0.09 | 2 |
| VolatilityBreakout | oos | 15 | 0.81 | 0.39 | 86.7 | 3.06 | 1.14 | 0.05 | 2 |
| VolatilityBreakout | stable | 5 | 0.23 | 0.03 | 80.0 | 8.26 | 2.68 | 0.05 | 1 |
| WyckoffAccumulation | baissier | 3 | -1.41 | 2.99 | 66.7 | 0.53 | -0.32 | -0.47 | 1 |
| WyckoffAccumulation | haussier | 0 | 0.00 | 0.00 | 0.0 | 0.00 | 0.00 | 0.00 | 0 |
| WyckoffAccumulation | is_9m | 8 | 6.32 | 0.00 | 100.0 | 0.00 | 1.18 | 0.79 | 0 |
| WyckoffAccumulation | is_9m_post_hyperopt | 7 | 3.13 | 0.00 | 100.0 | 0.00 | 128.30 | 0.45 | 0 |
| WyckoffAccumulation | oos | 4 | -1.03 | 2.98 | 75.0 | 0.66 | -0.11 | -0.26 | 1 |
| WyckoffAccumulation | stable | 0 | 0.00 | 0.00 | 0.0 | 0.00 | 0.00 | 0.00 | 0 |
| ZScoreMeanReversion | baissier | 3 | -1.78 | 2.21 | 66.7 | 0.19 | -0.63 | -0.59 | 1 |
| ZScoreMeanReversion | haussier | 1 | 0.22 | 0.00 | 100.0 | 0.00 | -100.00 | 0.22 | 0 |
| ZScoreMeanReversion | is_9m | 3 | 0.36 | 0.00 | 100.0 | 0.00 | 0.37 | 0.12 | 0 |
| ZScoreMeanReversion | is_9m_post_hyperopt | 13 | 2.68 | 0.00 | 100.0 | 0.00 | 1.41 | 0.21 | 1 |
| ZScoreMeanReversion | oos | 8 | -2.36 | 4.33 | 75.0 | 0.46 | -0.37 | -0.29 | 2 |
| ZScoreMeanReversion | stable | 2 | 0.76 | 0.00 | 100.0 | 0.00 | 3.44 | 0.38 | 0 |

## Classement IS (trie par profit)

| # | Strategie | Profit% | DD% | WR% | PF | Sharpe | Trades |
|---|-----------|---------|-----|-----|-----|--------|--------|
| 1 | MACDDivergence | 10.33 | 3.83 | 48.9 | 1.71 | 1.56 | 94 |
| 2 | MARibbonStack | 7.79 | 3.31 | 38.9 | 1.85 | 1.20 | 72 |
| 3 | RSIDivergence | 6.91 | 0.24 | 80.9 | 9.25 | 3.22 | 47 |
| 4 | SmartMoneyConcepts | 6.72 | 0.47 | 66.1 | 4.56 | 2.64 | 59 |
| 5 | WyckoffAccumulation | 6.32 | 0.00 | 100.0 | 0.00 | 1.18 | 8 |
| 6 | OBVDivergence | 3.95 | 0.62 | 74.1 | 3.85 | 1.06 | 27 |
| 7 | ADXRegimeFilter | 2.92 | 0.61 | 86.7 | 5.70 | 0.85 | 15 |
| 8 | EMATripleCross | 2.22 | 0.00 | 100.0 | 0.00 | 1.31 | 7 |
| 9 | MoneyFlowIndex | 2.18 | 0.00 | 100.0 | 0.00 | 1.62 | 16 |
| 10 | VolatilityBreakout | 1.84 | 0.06 | 88.0 | 27.25 | 1.94 | 25 |
| 11 | RangeBreakoutVolume | 1.82 | 1.01 | 41.7 | 1.95 | 0.71 | 36 |
| 12 | FibonacciPullback | 1.73 | 0.00 | 100.0 | 0.00 | 1.08 | 11 |
| 13 | KAMAAdaptiveTrend | 1.16 | 0.00 | 100.0 | 0.00 | 0.70 | 4 |
| 14 | TripleScreenElder | 0.94 | 0.00 | 100.0 | 0.00 | 0.81 | 4 |
| 15 | OBVTrendConfirm | 0.73 | 0.04 | 85.7 | 18.17 | 0.75 | 7 |
| 16 | BollingerMACDReversal | 0.66 | 0.00 | 100.0 | 0.00 | 0.80 | 4 |
| 17 | ZScoreMeanReversion | 0.36 | 0.00 | 100.0 | 0.00 | 0.37 | 3 |
| 18 | IchimokuBreakout | -1.75 | 3.87 | 42.5 | 0.87 | -0.40 | 87 |

## Validation OOS (classification)

- Benchmark B&H: +0.00%
- Min trades: 20

| # | Strategie | Profit% | DD% | WR% | PF | Trades | Tier | Significatif | > B&H |
|---|-----------|---------|-----|-----|-----|--------|------|-------------|-------|
| 1 | SmartMoneyConcepts | +1.19 | 0.57 | 55.6 | 2.51 | 18 | **TIER 3 (NS)** | NON | OUI |
| 2 | IchimokuBreakout | +0.93 | 1.16 | 47.4 | 1.22 | 38 | **TIER 3** | OUI | OUI |
| 3 | RSIDivergence | +0.88 | 3.43 | 77.8 | 1.23 | 27 | **TIER 3** | OUI | OUI |
| 4 | VolatilityBreakout | +0.81 | 0.39 | 86.7 | 3.06 | 15 | **TIER 3 (NS)** | NON | OUI |
| 5 | MARibbonStack | +0.33 | 1.78 | 34.6 | 1.08 | 26 | **TIER 3** | OUI | OUI |
| 6 | KAMAAdaptiveTrend | +0.32 | 0.00 | 100.0 | 999* | 3 | **TIER 3 (NS)** | NON | OUI |
| 7 | EMATripleCross | +0.22 | 0.37 | 33.3 | 1.60 | 3 | **TIER 3 (NS)** | NON | OUI |
| 8 | MoneyFlowIndex | +0.18 | 0.00 | 100.0 | 999* | 2 | **TIER 3 (NS)** | NON | OUI |
| 9 | OBVTrendConfirm | +0.00 | 0.00 | 0.0 | 0.00 | 0 | **ECHEC** | NON | NON |
| 10 | RangeBreakoutVolume | -0.27 | 0.27 | 0.0 | 0.00 | 3 | **ECHEC** | NON | NON |
| 11 | TripleScreenElder | -0.29 | 1.04 | 40.0 | 0.72 | 5 | **ECHEC** | NON | NON |
| 12 | WyckoffAccumulation | -1.03 | 2.98 | 75.0 | 0.66 | 4 | **ECHEC** | NON | NON |
| 13 | ZScoreMeanReversion | -2.36 | 4.33 | 75.0 | 0.46 | 8 | **ECHEC** | NON | NON |
| 14 | BollingerMACDReversal | -2.87 | 3.17 | 57.1 | 0.10 | 7 | **ECHEC** | NON | NON |
| 15 | ADXRegimeFilter | -3.39 | 3.77 | 44.4 | 0.13 | 9 | **ECHEC** | NON | NON |
| 16 | MACDDivergence | -3.91 | 7.97 | 34.2 | 0.60 | 38 | **ECHEC** | OUI | NON |
| 17 | OBVDivergence | -5.82 | 7.59 | 39.4 | 0.36 | 33 | **ECHEC** | OUI | NON |
| 18 | FibonacciPullback | -6.94 | 7.16 | 33.3 | 0.10 | 12 | **ECHEC** | NON | NON |

## Sensitivity Analysis (robustesse des parametres)

| Strategie | Profit ref% | Max drop% | Avg sensitivity | Status |
|-----------|------------|-----------|----------------|--------|
| EMATripleCross | 3.33 | -3.36 | 1.73 | **FRAGILE** |
| IchimokuBreakout | -1.75 | -1.46 | 0.65 | **ROBUSTE** |
| KAMAAdaptiveTrend | 1.16 | -2.75 | 0.82 | **FRAGILE** |
| MARibbonStack | 7.79 | -4.70 | 1.78 | **FRAGILE** |
| MoneyFlowIndex | 1.51 | +0.00 | 0.00 | **ROBUSTE** |
| RSIDivergence | 7.55 | -6.76 | 3.78 | **FRAGILE** |
| SmartMoneyConcepts | 4.69 | -2.22 | 1.35 | **ROBUSTE** |
| VolatilityBreakout | 3.53 | -2.73 | 1.46 | **FRAGILE** |