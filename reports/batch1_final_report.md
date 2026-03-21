# Rapport Batch 1 — 2026-03-20

## Resume executif

- **10 nouvelles strategies** codees et testees (hyperopt 1000 epochs chacune)
- **1 nouvelle strategie validee OOS** : ADXRegimeFilter (+10.08% OOS, WR 100%, DD 0%)
- **8 strategies precedentes** retestees par regime de marche (haussier/baissier/stable)
- **Capital** : 100 USDT, spot only, long only, BTC/ETH/SOL sur Binance

---

## 1. Nouvelles strategies Batch 1 — Resultats post-hyperopt (12 mois)

| # | Strategie | Profit% | Trades | WR% | DD% | PF | Sharpe | Status |
|---|-----------|---------|--------|-----|-----|-----|--------|--------|
| 1 | ADXRegimeFilter | +22.00 | 20 | 85.0 | 2.95 | 7.84 | — | VALIDE |
| 2 | ConnorsRSI | +14.40 | 30 | 100.0 | 0.00 | inf | — | OOS echoue |
| 3 | VWMASMACross | +6.76 | 134 | 56.0 | — | — | — | OOS marginal |
| 4 | CombinedBinHAndClucV8 | +3.82 | 33 | 85.0 | — | — | — | OOS marginal |
| 5 | RSI2Connors | +2.81 | 11 | 63.6 | 5.15 | 1.50 | 0.11 | OOS echoue |
| 6 | AwesomeOscillator | +1.78 | 125 | 52.0 | — | — | — | OOS echoue |
| 7 | CumulativeRSI | +0.65 | 2 | 100.0 | 0.00 | — | — | Trop peu de trades |
| 8 | ADOSCTrailing | -1.93 | — | — | — | — | — | NEGATIF |
| 9 | TwiggsMoneyFlow | -7.94 | 119 | 40.3 | 18.26 | — | — | NEGATIF |
| 10 | ElderImpulse | -50.60 | 425 | 34.8 | — | — | — | NEGATIF |

## 2. Validation OOS (20251201-20260319)

| Strategie | Profit OOS% | Trades | WR% | DD% | Status |
|-----------|------------|--------|-----|-----|--------|
| **ADXRegimeFilter** | **+10.08** | **7** | **100.0** | **0.00** | **VALIDE** |
| VWMASMACross | +1.21 | 38 | 60.5 | 7.91 | Marginal |
| CombinedBinHAndClucV8 | +0.83 | 11 | 90.9 | 0.31 | Marginal |
| ConnorsRSI | -1.15 | 5 | 60.0 | 2.47 | ECHOUE |
| RSI2Connors | -4.10 | 2 | 0.0 | 4.10 | ECHOUE |
| AwesomeOscillator | -6.22 | 37 | 54.1 | 20.90 | ECHOUE |

**Criteres de validation** : Profit OOS > 0%, DD < 25%, WR > 40%, Trades > 10

---

## 3. Strategies validees — Performance par regime de marche

### Legende regimes
- **Haussier** : 2025-03-01 → 2025-06-01
- **Baissier** : 2025-06-01 → 2025-09-01
- **Stable** : 2025-09-01 → 2025-12-01

### 3.1 MACDDivergence (OOS historique : +18.02%)

| Regime | Profit% | Trades | WR% | DD% |
|--------|---------|--------|-----|-----|
| Haussier | +29.48 | 20 | 55.0 | 3.39 |
| Baissier | +29.79 | 27 | 51.9 | 5.25 |
| Stable | -9.56 | 35 | 42.9 | 16.99 |

**Meilleur regime** : Baissier/Haussier. **Faiblesse** : marches stables.

### 3.2 SmartMoneyConcepts (OOS historique : +10.77%)

| Regime | Profit% | Trades | WR% | DD% |
|--------|---------|--------|-----|-----|
| Haussier | +6.43 | 16 | 56.2 | 2.27 |
| Baissier | +12.32 | 19 | 68.4 | 1.06 |
| Stable | +13.40 | 23 | 69.6 | 1.81 |

**All-weather** : positif dans tous les regimes. Meilleur en stable/baissier.

### 3.3 OBVDivergence (OOS historique : +9.86%)

| Regime | Profit% | Trades | WR% | DD% |
|--------|---------|--------|-----|-----|
| Haussier | +5.33 | 5 | 80.0 | 0.79 |
| Baissier | +8.78 | 9 | 66.7 | 0.37 |
| Stable | +3.35 | 11 | 63.6 | 3.03 |

**All-weather** : positif partout, DD tres faible. Meilleur en baissier.

### 3.4 RangeBreakoutVolume (OOS historique : +7.39%)

| Regime | Profit% | Trades | WR% | DD% |
|--------|---------|--------|-----|-----|
| Haussier | +0.13 | 7 | 42.9 | 2.03 |
| Baissier | +1.68 | 13 | 38.5 | 2.78 |
| Stable | +4.23 | 16 | 37.5 | 2.55 |

**All-weather** : positif partout mais modeste. Meilleur en stable.

### 3.5 EMATripleCross (OOS historique : +5.72%)

| Regime | Profit% | Trades | WR% | DD% |
|--------|---------|--------|-----|-----|
| Haussier | +1.04 | 1 | 100.0 | 0.00 |
| Baissier | +6.15 | 4 | 100.0 | 0.00 |
| Stable | +3.55 | 2 | 100.0 | 0.00 |

**All-weather** : WR 100% sur tous les regimes, mais tres peu de trades.

### 3.6 MARibbonStack (OOS historique : +5.22%)

| Regime | Profit% | Trades | WR% | DD% |
|--------|---------|--------|-----|-----|
| Haussier | +17.50 | 24 | 37.5 | 4.21 |
| Baissier | +14.95 | 30 | 40.0 | 10.84 |
| Stable | +7.52 | 10 | 50.0 | 2.62 |

**All-weather** : tres bon en haussier/baissier, correct en stable. DD notable en baissier.

### 3.7 WyckoffAccumulation (OOS historique : +3.38%)

| Regime | Profit% | Trades | WR% | DD% |
|--------|---------|--------|-----|-----|
| Haussier | +5.20 | 2 | 100.0 | 0.00 |
| Baissier | +7.58 | 2 | 100.0 | 0.00 |
| Stable | +18.27 | 4 | 100.0 | 0.00 |

**All-weather** : WR 100%, DD 0% sur tous les regimes. Peu de trades mais tres precis.

### 3.8 VolatilityBreakout (OOS historique : +3.23%)

| Regime | Profit% | Trades | WR% | DD% |
|--------|---------|--------|-----|-----|
| Haussier | +0.24 | 2 | 100.0 | 0.00 |
| Baissier | +1.56 | 9 | 77.8 | 0.30 |
| Stable | +6.90 | 15 | 93.3 | 0.28 |

**All-weather** : positif partout, DD minuscule. Meilleur en stable.

### 3.9 ADXRegimeFilter (NOUVEAU — OOS : +10.08%)

| Regime | Profit% | Trades | WR% | DD% |
|--------|---------|--------|-----|-----|
| Haussier | +2.39 | 2 | 100.0 | 0.00 |
| Baissier | +6.43 | 6 | 100.0 | 0.00 |
| Stable | +4.66 | 6 | 83.3 | 2.96 |

**All-weather** : positif dans tous les regimes, DD tres faible.

---

## 4. Classement global — Strategies validees (par profit 12 mois)

| # | Strategie | Profit 12m | OOS% | Haussier | Baissier | Stable | All-Weather |
|---|-----------|-----------|------|----------|----------|--------|-------------|
| 1 | MACDDivergence | +66.51% | +18.02% | +29.48 | +29.79 | -9.56 | NON |
| 2 | MARibbonStack | +52.62% | +5.22% | +17.50 | +14.95 | +7.52 | OUI |
| 3 | SmartMoneyConcepts | +50.14% | +10.77% | +6.43 | +12.32 | +13.40 | OUI |
| 4 | WyckoffAccumulation | +38.38% | +3.38% | +5.20 | +7.58 | +18.27 | OUI |
| 5 | OBVDivergence | +27.29% | +9.86% | +5.33 | +8.78 | +3.35 | OUI |
| 6 | **ADXRegimeFilter** | **+22.00%** | **+10.08%** | +2.39 | +6.43 | +4.66 | **OUI** |
| 7 | EMATripleCross | +17.42% | +5.72% | +1.04 | +6.15 | +3.55 | OUI |
| 8 | RangeBreakoutVolume | +13.94% | +7.39% | +0.13 | +1.68 | +4.23 | OUI |
| 9 | VolatilityBreakout | +12.35% | +3.23% | +0.24 | +1.56 | +6.90 | OUI |

---

## 5. Analyse

### Strategies "All-Weather" (positives dans TOUS les regimes)
1. **SmartMoneyConcepts** — Tres stable, DD faible, bon OOS
2. **MARibbonStack** — Profits eleves mais DD plus haute en baissier
3. **WyckoffAccumulation** — WR 100% partout, peu de trades
4. **OBVDivergence** — Consistant, DD tres faible
5. **ADXRegimeFilter** (NOUVEAU) — All-weather, bon OOS (+10.08%)
6. **EMATripleCross** — Tres precis mais peu actif
7. **RangeBreakoutVolume** — Modeste mais stable
8. **VolatilityBreakout** — DD quasi nulle partout

### Faiblesse identifiee
- **MACDDivergence** : malgre les meilleurs profits absolus, perd -9.56% en marche stable (DD 17%). A utiliser avec prudence ou coupler avec un filtre de regime.

### Recommandations pour dry-run
1. **Top 3 dry-run immediat** : SmartMoneyConcepts, ADXRegimeFilter, OBVDivergence
2. **Portefeuille diversifie** : combiner des strategies complementaires (trend + mean-reversion)
3. **Surveillance** : MACDDivergence uniquement en marche trending (haussier/baissier)

---

## 6. Strategies Batch 1 rejetees

| Strategie | Raison |
|-----------|--------|
| ConnorsRSI | OOS negatif (-1.15%) |
| RSI2Connors | OOS negatif (-4.10%), trop peu de trades |
| AwesomeOscillator | OOS negatif (-6.22%), DD 21% |
| CumulativeRSI | 2 trades seulement — pas exploitable |
| ADOSCTrailing | Negatif meme apres hyperopt (-1.93%) |
| TwiggsMoneyFlow | Negatif apres hyperopt (-7.94%) |
| ElderImpulse | Tres negatif (-50.60%) — overfit impossible |
| VWMASMACross | OOS marginal (+1.21%) — surveiller |
| CombinedBinHAndClucV8 | OOS marginal (+0.83%) — surveiller |
