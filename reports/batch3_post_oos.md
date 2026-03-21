# Rapport Batch 1 — 2026-03-21 03:41

## Resultats par strategie et regime de marche

| Strategie | Regime | Trades | Profit% | DD% | WR% | PF | Sharpe | Expectancy | ConsecLoss |
|-----------|--------|--------|---------|-----|-----|-----|--------|------------|------------|
| BollingerMACDReversal | full_12m | 7 | 5.16 | 0.00 | 100.0 | 0.00 | 0.99 | 0.74 | 0 |
| CCIMomentumTrend | full_12m | 14 | 8.30 | 1.84 | 64.3 | 3.01 | 0.30 | 0.59 | 2 |
| FibonacciPullback | full_12m | 20 | 17.59 | 0.17 | 90.0 | 95.84 | 1.71 | 0.88 | 1 |
| HeikinAshiTrend | full_12m | 197 | -21.17 | 37.29 | 57.4 | 0.85 | -0.65 | -0.11 | 9 |
| IchimokuBreakout | full_12m | 104 | -4.75 | 13.91 | 43.3 | 0.93 | -0.18 | -0.05 | 7 |
| KAMAAdaptiveTrend | full_12m | 7 | 7.36 | 0.00 | 100.0 | 0.00 | 0.60 | 1.05 | 0 |
| OBVTrendConfirm | full_12m | 10 | 4.66 | 0.21 | 90.0 | 22.64 | 0.77 | 0.47 | 1 |
| RSIRangeMeanRevert | full_12m | 51 | 9.48 | 16.79 | 76.5 | 1.27 | 0.26 | 0.19 | 4 |
| SuperTrendADX | full_12m | 49 | 25.27 | 7.62 | 65.3 | 3.27 | 0.81 | 0.52 | 3 |
| VolumeProfileAccumulation | full_12m | 38 | 11.02 | 20.68 | 68.4 | 1.35 | 0.18 | 0.29 | 3 |

## Classement (12 mois, trie par profit)

| # | Strategie | Profit% | DD% | WR% | PF | Sharpe | Trades |
|---|-----------|---------|-----|-----|-----|--------|--------|
| 1 | SuperTrendADX | 25.27 | 7.62 | 65.3 | 3.27 | 0.81 | 49 |
| 2 | FibonacciPullback | 17.59 | 0.17 | 90.0 | 95.84 | 1.71 | 20 |
| 3 | VolumeProfileAccumulation | 11.02 | 20.68 | 68.4 | 1.35 | 0.18 | 38 |
| 4 | RSIRangeMeanRevert | 9.48 | 16.79 | 76.5 | 1.27 | 0.26 | 51 |
| 5 | CCIMomentumTrend | 8.30 | 1.84 | 64.3 | 3.01 | 0.30 | 14 |
| 6 | KAMAAdaptiveTrend | 7.36 | 0.00 | 100.0 | 0.00 | 0.60 | 7 |
| 7 | BollingerMACDReversal | 5.16 | 0.00 | 100.0 | 0.00 | 0.99 | 7 |
| 8 | OBVTrendConfirm | 4.66 | 0.21 | 90.0 | 22.64 | 0.77 | 10 |
| 9 | IchimokuBreakout | -4.75 | 13.91 | 43.3 | 0.93 | -0.18 | 104 |
| 10 | HeikinAshiTrend | -21.17 | 37.29 | 57.4 | 0.85 | -0.65 | 197 |

## Validation OOS

| Strategie | Profit OOS% | DD OOS% | WR% | Trades | Status |
|-----------|-------------|---------|-----|--------|--------|