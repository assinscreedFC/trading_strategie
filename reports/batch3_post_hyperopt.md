# Rapport Batch 1 — 2026-03-21 03:36

## Resultats par strategie et regime de marche

| Strategie | Regime | Trades | Profit% | DD% | WR% | PF | Sharpe | Expectancy | ConsecLoss |
|-----------|--------|--------|---------|-----|-----|-----|--------|------------|------------|
| BollingerMACDReversal | full_12m | 3 | 1.87 | 0.00 | 100.0 | 0.00 | 0.40 | 0.62 | 0 |
| BollingerMACDReversal | full_12m_post_hyperopt | 7 | 5.16 | 0.00 | 100.0 | 0.00 | 0.99 | 0.74 | 0 |
| CCIMomentumTrend | full_12m | 9 | 6.58 | 0.98 | 66.7 | 4.27 | 0.28 | 0.73 | 1 |
| CCIMomentumTrend | full_12m_post_hyperopt | 14 | 8.30 | 1.84 | 64.3 | 3.01 | 0.30 | 0.59 | 2 |
| FibonacciPullback | full_12m | 18 | 15.54 | 0.00 | 100.0 | 0.00 | 2.12 | 0.86 | 1 |
| FibonacciPullback | full_12m_post_hyperopt | 20 | 17.59 | 0.17 | 90.0 | 95.84 | 1.71 | 0.88 | 1 |
| HeikinAshiTrend | full_12m | 328 | -47.74 | 48.43 | 58.2 | 0.72 | -2.35 | -0.15 | 9 |
| HeikinAshiTrend | full_12m_post_hyperopt | 197 | -21.17 | 37.29 | 57.4 | 0.85 | -0.65 | -0.11 | 9 |
| IchimokuBreakout | full_12m | 104 | -9.25 | 16.31 | 43.3 | 0.86 | -0.35 | -0.09 | 7 |
| IchimokuBreakout | full_12m_post_hyperopt | 104 | -4.75 | 13.91 | 43.3 | 0.93 | -0.18 | -0.05 | 7 |
| KAMAAdaptiveTrend | full_12m | 31 | -23.37 | 23.37 | 51.6 | 0.29 | -0.88 | -0.75 | 4 |
| KAMAAdaptiveTrend | full_12m_post_hyperopt | 7 | 7.36 | 0.00 | 100.0 | 0.00 | 0.60 | 1.05 | 0 |
| OBVTrendConfirm | full_12m | 179 | -31.74 | 32.73 | 54.7 | 0.69 | -1.48 | -0.18 | 7 |
| OBVTrendConfirm | full_12m_post_hyperopt | 10 | 4.66 | 0.21 | 90.0 | 22.64 | 0.77 | 0.47 | 1 |
| RSIRangeMeanRevert | full_12m | 50 | 6.29 | 17.11 | 74.0 | 1.16 | 0.16 | 0.13 | 4 |
| RSIRangeMeanRevert | full_12m_post_hyperopt | 51 | 9.48 | 16.79 | 76.5 | 1.27 | 0.26 | 0.19 | 4 |
| SuperTrendADX | full_12m | 41 | 20.29 | 7.35 | 65.9 | 2.68 | 0.62 | 0.49 | 3 |
| SuperTrendADX | full_12m_post_hyperopt | 49 | 25.27 | 7.62 | 65.3 | 3.27 | 0.81 | 0.52 | 3 |
| VolumeProfileAccumulation | full_12m | 39 | 14.32 | 19.01 | 71.8 | 1.47 | 0.25 | 0.37 | 3 |
| VolumeProfileAccumulation | full_12m_post_hyperopt | 38 | 11.02 | 20.68 | 68.4 | 1.35 | 0.18 | 0.29 | 3 |

## Classement (12 mois, trie par profit)

| # | Strategie | Profit% | DD% | WR% | PF | Sharpe | Trades |
|---|-----------|---------|-----|-----|-----|--------|--------|
| 1 | SuperTrendADX | 20.29 | 7.35 | 65.9 | 2.68 | 0.62 | 41 |
| 2 | FibonacciPullback | 15.54 | 0.00 | 100.0 | 0.00 | 2.12 | 18 |
| 3 | VolumeProfileAccumulation | 14.32 | 19.01 | 71.8 | 1.47 | 0.25 | 39 |
| 4 | CCIMomentumTrend | 6.58 | 0.98 | 66.7 | 4.27 | 0.28 | 9 |
| 5 | RSIRangeMeanRevert | 6.29 | 17.11 | 74.0 | 1.16 | 0.16 | 50 |
| 6 | BollingerMACDReversal | 1.87 | 0.00 | 100.0 | 0.00 | 0.40 | 3 |
| 7 | IchimokuBreakout | -9.25 | 16.31 | 43.3 | 0.86 | -0.35 | 104 |
| 8 | KAMAAdaptiveTrend | -23.37 | 23.37 | 51.6 | 0.29 | -0.88 | 31 |
| 9 | OBVTrendConfirm | -31.74 | 32.73 | 54.7 | 0.69 | -1.48 | 179 |
| 10 | HeikinAshiTrend | -47.74 | 48.43 | 58.2 | 0.72 | -2.35 | 328 |

## Validation OOS

| Strategie | Profit OOS% | DD OOS% | WR% | Trades | Status |
|-----------|-------------|---------|-----|--------|--------|