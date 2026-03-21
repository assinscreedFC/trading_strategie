# Rapport Batch 1 — 2026-03-20 10:21

## Resultats par strategie et regime de marche

| Strategie | Regime | Trades | Profit% | DD% | WR% | PF | Sharpe | Expectancy | ConsecLoss |
|-----------|--------|--------|---------|-----|-----|-----|--------|------------|------------|
| BollingerMACDReversal | full_12m | 0 | 0.00 | 0.00 | 0.0 | 0.00 | 0.00 | 0.00 | 0 |
| CCIMomentumTrend | full_12m | 186 | -28.02 | 29.82 | 58.6 | 0.74 | -1.27 | -0.15 | 7 |
| FibonacciPullback | full_12m | 172 | -55.45 | 57.56 | 61.6 | 0.53 | -2.27 | -0.32 | 7 |
| HeikinAshiTrend | full_12m | 328 | -47.74 | 48.43 | 58.2 | 0.72 | -2.35 | -0.15 | 9 |
| IchimokuBreakout | full_12m | 127 | -35.59 | 36.19 | 35.4 | 0.59 | -1.61 | -0.28 | 10 |
| KAMAAdaptiveTrend | full_12m | 31 | -23.37 | 23.37 | 51.6 | 0.29 | -0.88 | -0.75 | 4 |
| OBVTrendConfirm | full_12m | 181 | -34.47 | 35.42 | 55.8 | 0.65 | -1.70 | -0.19 | 7 |
| RSIRangeMeanRevert | full_12m | 95 | -15.71 | 29.72 | 74.7 | 0.77 | -0.57 | -0.17 | 8 |
| SuperTrendADX | full_12m | 167 | -18.78 | 30.24 | 69.5 | 0.83 | -0.66 | -0.11 | 6 |
| VolumeProfileAccumulation | full_12m | 88 | -35.44 | 38.41 | 65.9 | 0.48 | -1.34 | -0.40 | 4 |

## Classement (12 mois, trie par profit)

| # | Strategie | Profit% | DD% | WR% | PF | Sharpe | Trades |
|---|-----------|---------|-----|-----|-----|--------|--------|
| 1 | BollingerMACDReversal | 0.00 | 0.00 | 0.0 | 0.00 | 0.00 | 0 |
| 2 | RSIRangeMeanRevert | -15.71 | 29.72 | 74.7 | 0.77 | -0.57 | 95 |
| 3 | SuperTrendADX | -18.78 | 30.24 | 69.5 | 0.83 | -0.66 | 167 |
| 4 | KAMAAdaptiveTrend | -23.37 | 23.37 | 51.6 | 0.29 | -0.88 | 31 |
| 5 | CCIMomentumTrend | -28.02 | 29.82 | 58.6 | 0.74 | -1.27 | 186 |
| 6 | OBVTrendConfirm | -34.47 | 35.42 | 55.8 | 0.65 | -1.70 | 181 |
| 7 | VolumeProfileAccumulation | -35.44 | 38.41 | 65.9 | 0.48 | -1.34 | 88 |
| 8 | IchimokuBreakout | -35.59 | 36.19 | 35.4 | 0.59 | -1.61 | 127 |
| 9 | HeikinAshiTrend | -47.74 | 48.43 | 58.2 | 0.72 | -2.35 | 328 |
| 10 | FibonacciPullback | -55.45 | 57.56 | 61.6 | 0.53 | -2.27 | 172 |

## Validation OOS

| Strategie | Profit OOS% | DD OOS% | WR% | Trades | Status |
|-----------|-------------|---------|-----|--------|--------|