# Rapport — 2026-03-22 01:11

## Parametres de validation
- IS (In-Sample): 20250301-20251130 (9 mois — hyperopt)
- OOS (Out-of-Sample): 20251201-20260319 (3.5 mois — validation)
- Min trades OOS: 20

## Resultats par strategie et regime

| Strategie | Regime | Trades | Profit% | DD% | WR% | PF | Sharpe | Expectancy | ConsecLoss |
|-----------|--------|--------|---------|-----|-----|-----|--------|------------|------------|
| ADXRegimeFilter | is_9m | 15 | 2.92 | 0.61 | 86.7 | 5.70 | 0.85 | 0.19 | 1 |
| BollingerMACDReversal | is_9m | 4 | 0.66 | 0.00 | 100.0 | 0.00 | 0.80 | 0.17 | 0 |
| EMATripleCross | is_9m | 7 | 2.22 | 0.00 | 100.0 | 0.00 | 1.31 | 0.32 | 0 |
| FibonacciPullback | is_9m | 11 | 1.73 | 0.00 | 100.0 | 0.00 | 1.08 | 0.16 | 1 |
| IchimokuBreakout | is_9m | 87 | -1.75 | 3.87 | 42.5 | 0.87 | -0.40 | -0.02 | 9 |
| KAMAAdaptiveTrend | is_9m | 4 | 1.16 | 0.00 | 100.0 | 0.00 | 0.70 | 0.29 | 0 |
| MACDDivergence | is_9m | 94 | 10.33 | 3.83 | 48.9 | 1.71 | 1.56 | 0.11 | 8 |
| MARibbonStack | is_9m | 72 | 7.79 | 3.31 | 38.9 | 1.85 | 1.20 | 0.11 | 13 |
| MoneyFlowIndex | is_9m | 16 | 2.18 | 0.00 | 100.0 | 0.00 | 1.62 | 0.14 | 3 |
| OBVDivergence | is_9m | 27 | 3.95 | 0.62 | 74.1 | 3.85 | 1.06 | 0.15 | 1 |
| OBVTrendConfirm | is_9m | 7 | 0.73 | 0.04 | 85.7 | 18.17 | 0.75 | 0.10 | 1 |
| RSIDivergence | is_9m | 47 | 6.91 | 0.24 | 80.9 | 9.25 | 3.22 | 0.15 | 2 |
| RangeBreakoutVolume | is_9m | 36 | 1.82 | 1.01 | 41.7 | 1.95 | 0.71 | 0.05 | 8 |
| SmartMoneyConcepts | is_9m | 59 | 6.72 | 0.47 | 66.1 | 4.56 | 2.64 | 0.11 | 4 |
| TripleScreenElder | is_9m | 4 | 0.94 | 0.00 | 100.0 | 0.00 | 0.81 | 0.23 | 0 |
| VolatilityBreakout | is_9m | 25 | 1.84 | 0.06 | 88.0 | 27.25 | 1.94 | 0.07 | 2 |
| WyckoffAccumulation | is_9m | 8 | 6.32 | 0.00 | 100.0 | 0.00 | 1.18 | 0.79 | 0 |
| ZScoreMeanReversion | is_9m | 3 | 0.36 | 0.00 | 100.0 | 0.00 | 0.37 | 0.12 | 0 |

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