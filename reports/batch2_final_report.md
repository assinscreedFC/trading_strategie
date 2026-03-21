# Rapport Batch 2 — 2026-03-20

## Innovation : Detection Automatique des Regimes

**Methode** : ADX(14) + Direction EMA(50) sur BTC/USDT 1d
- Seuils de Wilder : ADX > 25 = tendance, ADX < 20 = range
- Direction : EMA(50) monte/descend vs 5 jours avant

**Regimes detectes (vs hardcodes Batch 1) :**

| Regime | Batch 1 (hardcode) | Batch 2 (auto-detecte) | Duree |
|--------|-------------------|------------------------|-------|
| Haussier | 20250301-20250601 | 20250427-20250531 | 35j |
| Baissier | 20250601-20250901 | 20260130-20260318 | 48j |
| Stable | 20250901-20251201 | 20250608-20250712 | 35j |

**Repartition reelle du marche** : Stable 31.9%, Baissier 30.3%, Transition 20.9%, Haussier 17.0%

---

## Resultats Post-Hyperopt 12 mois (20250301-20260301)

| # | Strategie | Profit% | Trades | WR% | DD% | Type |
|---|-----------|---------|--------|-----|-----|------|
| 1 | RSIDivergence | +49.78 | 61 | 82.0 | 3.64 | Divergence RSI |
| 2 | MoneyFlowIndex | +14.92 | 20 | 100 | 0.00 | Volume-RSI |
| 3 | StochasticMomentumIndex | +14.58 | 12 | 100 | 0.00 | Oscillateur |
| 4 | ChoppinessBreakout | +13.38 | 76 | 67.1 | 8.55 | Anti-chop |
| 5 | ZScoreMeanReversion | +10.27 | 8 | 100 | 0.00 | Mean-reversion stat |
| 6 | TripleScreenElder | +10.00 | 7 | 100 | 0.00 | Multi-TF |
| 7 | KeltnerChannelMomentum | +9.83 | 16 | 75.0 | 4.74 | Breakout ATR |
| 8 | DMICrossover | +3.64 | 5 | 60.0 | 0.66 | Directionnel |
| 9 | PivotPointReversal | +0.20 | 3 | 66.7 | 0.54 | S/R Reversal |
| 10 | ChandelierExit | -3.99 | 97 | 42.3 | 17.69 | Trailing ATR |

---

## Validation OOS Walk-Forward (20251201-20260319)

| Strategie | OOS Profit% | Trades | WR% | DD% | Status |
|-----------|-------------|--------|-----|-----|--------|
| RSIDivergence | +20.02 | 21 | 90.5 | 3.64 | VALIDATED |
| ZScoreMeanReversion | +8.38 | 5 | 100 | 0.00 | VALIDATED |
| TripleScreenElder | +5.19 | 3 | 100 | 0.00 | VALIDATED |
| MoneyFlowIndex | +3.64 | 4 | 100 | 0.00 | VALIDATED |
| StochasticMomentumIndex | +1.76 | 1 | 100 | 0.00 | Marginal (1 trade) |
| ChoppinessBreakout | -6.90 | 19 | 47.4 | 8.64 | FAILED |
| KeltnerChannelMomentum | -0.28 | 4 | 75.0 | 2.60 | FAILED |
| DMICrossover | 0.00 | 0 | — | — | FAILED (no trades) |
| PivotPointReversal | 0.00 | 0 | — | — | FAILED (no trades) |
| ChandelierExit | — | — | — | — | SKIP (negatif 12m) |

**4 strategies validees OOS** (RSIDivergence, ZScoreMeanReversion, TripleScreenElder, MoneyFlowIndex)

---

## Analyse par Regime Auto-Detecte

### Nouvelles strategies validees

| Strategie | Haussier (avr-mai) | Baissier (jan-mar) | Stable (jun-jul) | All-Weather? |
|-----------|-------------------|-------------------|------------------|-------------|
| RSIDivergence | +6.64% (10t) | +11.64% (9t) | +3.55% (8t) | YES |
| ZScoreMeanReversion | +1.05% (1t) | +2.48% (1t) | 0.00% (0t) | NON (0 trades stable) |
| TripleScreenElder | 0.00% (0t) | +5.19% (3t) | 0.00% (0t) | NON (0 trades H+S) |
| MoneyFlowIndex | +2.79% (4t) | 0.00% (0t) | +1.17% (2t) | NON (0 trades baissier) |

### 9 strategies validees existantes (regimes auto-detectes)

| Strategie | Haussier | Baissier | Stable | All-Weather? |
|-----------|----------|----------|--------|-------------|
| SmartMoneyConcepts | +0.97% | +4.09% | +5.61% | YES |
| MACDDivergence | +8.62% | +13.75% | +8.27% | YES |
| OBVDivergence | +3.01% | +6.77% | +3.62% | YES |
| RangeBreakoutVolume | -1.58% | +8.78% | -0.42% | NON (H-1.58, S-0.42) |
| EMATripleCross | +1.04% | +3.86% | +3.82% | YES |
| MARibbonStack | +12.03% | +1.61% | +1.58% | YES |
| WyckoffAccumulation | 0.00% | +4.10% | 0.00% | NON (0 trades H+S) |
| VolatilityBreakout | 0.00% | +1.41% | +0.02% | NON (0 trades H) |
| ADXRegimeFilter | 0.00% | +3.07% | +1.47% | NON (0 trades H) |

---

## Comparaison Regimes Hardcodes vs Auto-Detectes

| Strategie | Batch 1 (H/B/S hardcode) | Batch 2 (H/B/S auto) | Changement |
|-----------|-------------------------|---------------------|------------|
| SmartMoneyConcepts | +6.43/+12.32/+13.40 | +0.97/+4.09/+5.61 | Performances reelles plus basses |
| MACDDivergence | +29.48/+29.79/-9.56 | +8.62/+13.75/+8.27 | Devient ALL-WEATHER (etait NON) |
| RangeBreakoutVolume | +0.13/+1.68/+4.23 | -1.58/+8.78/-0.42 | Devient NON all-weather |
| WyckoffAccumulation | +5.20/+7.58/+18.27 | 0.00/+4.10/0.00 | Devient NON all-weather |
| VolatilityBreakout | +0.24/+1.56/+6.90 | 0.00/+1.41/+0.02 | Beaucoup plus faible |
| ADXRegimeFilter | +2.39/+6.43/+4.66 | 0.00/+3.07/+1.47 | Beaucoup plus faible |

**Conclusion** : Les regimes hardcodes surestimaient les performances. Avec la detection auto, seules 5 strategies sont reellement ALL-WEATHER : SmartMoneyConcepts, MACDDivergence, OBVDivergence, EMATripleCross, MARibbonStack + RSIDivergence (nouvelle).

---

## Classement Global (toutes strategies validees, trie par OOS)

| # | Strategie | 12m% | OOS% | WR OOS | DD OOS | All-Weather |
|---|-----------|------|------|--------|--------|-------------|
| 1 | RSIDivergence | +49.78 | +20.02 | 90.5% | 3.64% | YES |
| 2 | MACDDivergence | +66.51 | +18.02 | 50.4% | 27.74% | YES |
| 3 | SmartMoneyConcepts | +50.14 | +10.77 | 65.0% | 3.40% | YES |
| 4 | ADXRegimeFilter | +22.00 | +10.08 | 100% | 0.00% | NON |
| 5 | OBVDivergence | +27.29 | +9.86 | 70.7% | 3.86% | YES |
| 6 | ZScoreMeanReversion | +10.27 | +8.38 | 100% | 0.00% | NON |
| 7 | RangeBreakoutVolume | +13.94 | +7.39 | 45.1% | 4.94% | NON |
| 8 | EMATripleCross | +17.42 | +5.72 | 92.3% | 0.95% | YES |
| 9 | MARibbonStack | +52.62 | +5.22 | 41.0% | 12.65% | YES |
| 10 | TripleScreenElder | +10.00 | +5.19 | 100% | 0.00% | NON |
| 11 | MoneyFlowIndex | +14.92 | +3.64 | 100% | 0.00% | NON |
| 12 | WyckoffAccumulation | +38.38 | +3.38 | 81.2% | 8.13% | NON |
| 13 | VolatilityBreakout | +12.35 | +3.23 | 86.1% | 0.28% | NON |

---

## Recommandations Dry-Run

### Top 3 pour deploiement (risk-adjusted)
1. **RSIDivergence** — Meilleur OOS (+20.02%), all-weather, bon WR (90.5%), DD maitrise (3.64%)
2. **SmartMoneyConcepts** — OOS solide (+10.77%), all-weather, faible DD (3.40%)
3. **OBVDivergence** — OOS stable (+9.86%), all-weather, faible DD (3.86%)

### Portfolio diversifie suggere
- RSIDivergence (divergence) + SmartMoneyConcepts (price action) + EMATripleCross (trend) — 3 categories differentes, toutes all-weather

### Strategies a surveiller
- ZScoreMeanReversion : excellent OOS (+8.38%) mais trop peu de trades en regime stable
- TripleScreenElder : bon OOS mais ne trade que en baissier (MACD filter trop restrictif)

### Strategies echouees Batch 2
- ChoppinessBreakout : bon en 12m (+13.38%) mais overfit (OOS -6.90%)
- KeltnerChannelMomentum : OOS negatif
- DMICrossover / PivotPointReversal : 0 trades en OOS
- ChandelierExit : negatif meme apres hyperopt
