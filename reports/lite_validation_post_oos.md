# Rapport — 2026-03-22 16:06

## Parametres de validation
- IS (In-Sample): 20230101-20251130 (9 mois — hyperopt)
- OOS (Out-of-Sample): 20251201-20260319 (3.5 mois — validation)
- Min trades OOS: 20

## Resultats par strategie et regime

| Strategie | Regime | Trades | Profit% | DD% | WR% | PF | Sharpe | Expectancy | ConsecLoss |
|-----------|--------|--------|---------|-----|-----|-----|--------|------------|------------|
| DCASimple | oos | 42 | -4.09 | 8.84 | 61.9 | 0.72 | -1.10 | -0.10 | 6 |
| EMATripleCrossLite | oos | 6 | 0.35 | 0.58 | 66.7 | 1.60 | 0.25 | 0.06 | 2 |
| IchimokuBreakoutLite | oos | 42 | -2.77 | 5.07 | 40.5 | 0.66 | -1.35 | -0.07 | 9 |
| MACDDivergenceLite | oos | 10 | -2.42 | 2.47 | 40.0 | 0.17 | -1.24 | -0.24 | 5 |
| MARibbonStackLite | oos | 41 | -4.80 | 4.97 | 34.1 | 0.45 | -2.73 | -0.12 | 8 |
| OBVDivergenceLite | oos | 22 | -0.91 | 3.27 | 72.7 | 0.73 | -0.47 | -0.04 | 4 |
| RSIDivergenceLite | oos | 20 | 2.52 | 0.61 | 95.0 | 5.10 | 2.35 | 0.13 | 1 |

## Classement IS (trie par profit)

| # | Strategie | Profit% | DD% | WR% | PF | Sharpe | Trades |
|---|-----------|---------|-----|-----|-----|--------|--------|

## Validation OOS (classification)

- Benchmark B&H: +0.00%
- Min trades: 20

| # | Strategie | Profit% | DD% | WR% | PF | Trades | Tier | Significatif | > B&H |
|---|-----------|---------|-----|-----|-----|--------|------|-------------|-------|
| 1 | RSIDivergenceLite | +2.52 | 0.61 | 95.0 | 5.10 | 20 | **TIER 3** | OUI | OUI |
| 2 | EMATripleCrossLite | +0.35 | 0.58 | 66.7 | 1.60 | 6 | **TIER 3 (NS)** | NON | OUI |
| 3 | OBVDivergenceLite | -0.91 | 3.27 | 72.7 | 0.73 | 22 | **ECHEC** | OUI | NON |
| 4 | MACDDivergenceLite | -2.42 | 2.47 | 40.0 | 0.17 | 10 | **ECHEC** | NON | NON |
| 5 | IchimokuBreakoutLite | -2.77 | 5.07 | 40.5 | 0.66 | 42 | **ECHEC** | OUI | NON |
| 6 | DCASimple | -4.09 | 8.84 | 61.9 | 0.72 | 42 | **ECHEC** | OUI | NON |
| 7 | MARibbonStackLite | -4.80 | 4.97 | 34.1 | 0.45 | 41 | **ECHEC** | OUI | NON |