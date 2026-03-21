# Audit Expert — 18 Strategies Validees + Config
> Date: 2026-03-21 | Capital: 100 USDT | Exchange: Kraken | TF: 4h | Spot/Long only

---

## 1. PROBLEMES CRITIQUES (bloquants avant dry-run)

### C1 — Position Sizing catastrophique
- `stake_amount: "unlimited"` + `max_open_trades: 2` = **~50% du capital par trade**
- Impact : un seul SL a -6% = perte de 3% du capital. Deux SL simultanes = -6%
- **Correction** : `stake_amount: 20`, `max_open_trades: 4`

### C2 — Aucune protection configuree
- Pas de CooldownPeriod → re-entree immediate apres SL (revenge trading)
- Pas de MaxDrawdown → continue de trader pendant drawdown severe
- Pas de StoplossGuard → accumulation de pertes en cascade
- **Correction** : ajouter protections dans la config (voir section Recommandations)

### C3 — Look-Ahead Bias dans SmartMoneyConcepts
- La detection de swing utilise `dataframe["high"].iloc[i + j]` → regarde le futur
- Les resultats backtest/OOS sont **surestime**
- **Impact** : SmartMoneyConcepts (Tier 2, OOS +10.77%) n'est PAS fiable
- **Correction** : remplacer par rolling max/min (comme FibonacciPullback)

### C4 — Bug potentiel `volume_ratio` (3 strategies)
- EMATripleCross, MARibbonStack, RangeBreakoutVolume referencent `volume_ratio_{period}`
- CommonIndicators genere probablement `volume_sma_{period}` → crash en runtime
- **A verifier** dans `utils/indicators.py`

---

## 2. WARNINGS (a corriger avant passage live)

### W1 — Detection de divergence naive (3 strategies)
- RSIDivergence, MACDDivergence, OBVDivergence utilisent `shift(N)` simple
- Ce n'est PAS une vraie divergence sur swing points → faux positifs
- Impact : les performances backtest sont probablement optimistes

### W2 — Filtre volume absent ou inutile (13/18 strategies)
- `volume > 0` est present sur presque toute bougie → filtre inutile
- Seules MACDDivergence et EMATripleCross ont un vrai filtre volume
- **Correction** : remplacer par `volume > X * volume_sma_20`

### W3 — Pas de custom_stoploss (18/18 strategies)
- Aucune strategy n'implemente de stoploss dynamique
- Un SL fixe a -5/-6% ne protege pas contre les flash crashes ou la volatilite extreme
- **Recommandation** : implementer un ATR-based stoploss

### W4 — Pickling manquant (8 strategies)
- Strategies sans `__getstate__`/`__setstate__` : SmartMoneyConcepts, MACDDivergence,
  OBVDivergence, EMATripleCross, MARibbonStack, RangeBreakoutVolume,
  WyckoffAccumulation, VolatilityBreakout
- Risque de crash en hyperopt ou dry-run avec persistence

### W5 — Parametres declares mais jamais utilises (code mort)
- IchimokuBreakout : `exit_confirm_candles` → jamais utilise dans populate_exit_trend
- KAMAAdaptiveTrend : `exit_confirm_candles` → idem
- RangeBreakoutVolume : `bb_std` → BB toujours calculees avec std=2.0
- Volume SMA calcule mais inutilise dans : ZScoreMeanReversion, MoneyFlowIndex,
  BollingerMACDReversal
- WyckoffAccumulation : `import numpy` jamais utilise

### W6 — VolatilityBreakout : performance catastrophique
- `apply(lambda...)` dans `populate_entry_trend` → recalcule O(n*window) a chaque appel
- 256 combinaisons BB pre-calculees mais une seule utilisee → gaspillage memoire
- **Note** : 4.5/10, la pire du lot

---

## 3. NOTES PAR STRATEGIE

### Top 8 All-Weather

| # | Strategie | Tier | OOS% | Note | Forces | Faiblesses |
|---|-----------|------|------|------|--------|------------|
| 1 | FibonacciPullback | T3 | +8.64 | **7.5** | ADX filter unique, tolerance fib, target exit | Fib dynamiques (pas vrais swings), vol>0 |
| 2 | EMATripleCross | T3 | +5.72 | **7.5** | Meilleur combo entree, RSI bande, vrai filtre vol | Bug volume_ratio, pas pickling |
| 3 | MACDDivergence | T2 | +18.0 | **7.0** | Vrai filtre volume, MACD params fixes, bonne sortie | Divergence naive, pas pickling |
| 4 | IchimokuBreakout | T3 | +6.13 | **7.0** | Breakout frais, sortie structurelle | Ichimoku incomplet, exit_confirm mort |
| 5 | RSIDivergence | T1 | +20.0 | **6.5** | Meilleur OOS, trailing correct | Divergence naive, vol>0, sortie basique |
| 6 | OBVDivergence | T3 | +9.86 | **6.5** | Sortie symetrique (div baissiere) | Divergence naive, vol>0 |
| 7 | MARibbonStack | T3 | +5.22 | **6.0** | Sortie multi-niveau | Entree trop restrictive, 0 trades en range |
| 8 | SmartMoneyConcepts | T2 | +10.8 | **5.5** | Concept SMC original | **LOOK-AHEAD BIAS** — ne pas deployer |

### 10 Strategies Tier 3 restantes

| # | Strategie | OOS% | Note | Forces | Faiblesses |
|---|-----------|------|------|--------|------------|
| 1 | TripleScreenElder | +5.19 | **7.5** | Multi-TF Elder, propre | Simplifie (2 TF au lieu de 3) |
| 2 | ADXRegimeFilter | +10.1 | **7.0** | Double mode trend/range | Seuils ADX chevauchables |
| 3 | OBVTrendConfirm | +1.10 | **7.0** | OBV rising N bougies, propre | obv_rising=6 trop restrictif |
| 4 | BollingerMACDReversal | +1.91 | **6.5** | Triple confirmation, MACD fixe | Vol SMA inutilise, vol>0 |
| 5 | KAMAAdaptiveTrend | +1.55 | **6.5** | Seul a utiliser vol>SMA en entree | exit_confirm_candles mort |
| 6 | ZScoreMeanReversion | +8.38 | **6.5** | Z-score + BB, bougie verte | Pas filtre tendance, vol SMA mort |
| 7 | MoneyFlowIndex | +3.64 | **6.0** | MFI + EMA filtre | Attrape-couteaux, vol mort |
| 8 | RangeBreakoutVolume | +7.39 | **6.0** | BB compress + breakout + ADX | bb_std mort, bug volume_ratio |
| 9 | WyckoffAccumulation | +3.38 | **5.5** | Spring detection | Div 5 bougies trop courte, numpy mort |
| 10 | VolatilityBreakout | +3.23 | **4.5** | ATR expansion | Lambda perf, 256 BB, bug vol_ratio |

---

## 4. PATTERNS RECURRENTS IDENTIFIES

| Pattern | Count | Strategies concernees |
|---------|-------|-----------------------|
| Filtre volume `> 0` inutile | 13/18 | Toutes sauf MACD, EMA, KAMAAdaptive |
| Divergence naive (shift) | 3 | RSIDivergence, MACDDivergence, OBVDivergence |
| Volume SMA calcule mais inutilise | 4 | ZScore, MoneyFlow, Bollinger, RangeBreakout |
| Pas de `__getstate__` | 8 | SMC, MACD, OBV, EMA, MARibbon, Range, Wyckoff, Volatility |
| Pas de `custom_stoploss` | 18/18 | Toutes |
| Parametres morts | 5 | Ichimoku, KAMA, RangeBreakout, WyckoffAccum, VolBreakout |

---

## 5. CLASSEMENT FINAL DE CONFIANCE (deploy-ready)

### Tier A — Deploiement recommande (note >= 7.0, pas de bug critique)
1. **FibonacciPullback** (7.5) — la plus solide techniquement
2. **MACDDivergence** (7.0) — bon equilibre, vrai filtre volume
3. **IchimokuBreakout** (7.0) — sortie structurelle
4. **TripleScreenElder** (7.5) — multi-TF, code le plus propre

### Tier B — Deploiement apres corrections mineures
5. **RSIDivergence** (6.5) — meilleur OOS mais divergence naive
6. **EMATripleCross** (7.5) — top signaux MAIS verifier bug volume_ratio
7. **OBVDivergence** (6.5) — correct
8. **ADXRegimeFilter** (7.0) — verifier seuils ADX

### Tier C — Corrections significatives necessaires
9-14. BollingerMACDReversal, KAMAAdaptive, ZScore, OBVTrendConfirm, MoneyFlowIndex, RangeBreakoutVolume

### Tier D — Refonte necessaire
15. **MARibbonStack** (6.0) — trop restrictif
16. **WyckoffAccumulation** (5.5) — divergence trop courte
17. **SmartMoneyConcepts** (5.5) — **LOOK-AHEAD BIAS**
18. **VolatilityBreakout** (4.5) — performance catastrophique

---

## 6. RECOMMANDATIONS

### Config corrigee pour dry-run (100 USDT)
```json
{
  "stake_amount": 20,
  "max_open_trades": 4,
  "tradable_balance_ratio": 0.95,
  "dry_run_wallet": 100,
  "order_types": {
    "entry": "limit",
    "exit": "limit",
    "stoploss": "market",
    "stoploss_on_exchange": true
  },
  "protections": [
    {
      "method": "CooldownPeriod",
      "stop_duration_candles": 5,
      "trade_limit": 1
    },
    {
      "method": "MaxDrawdown",
      "lookback_period_candles": 48,
      "trade_limit": 2,
      "stop_duration_candles": 12,
      "max_allowed_drawdown": 0.10
    },
    {
      "method": "StoplossGuard",
      "lookback_period_candles": 24,
      "trade_limit": 2,
      "stop_duration_candles": 12,
      "only_per_pair": false
    }
  ]
}
```

### Portfolio recommande pour dry-run
- **FibonacciPullback** + **MACDDivergence** + **IchimokuBreakout** + **RSIDivergence**
- 4 strategies, 4 approches differentes (pullback, divergence MACD, breakout, divergence RSI)
- 20 USDT/trade x 4 max = 80 USDT max expose, 20 USDT en reserve

### Protocole de passage live
1. Corriger C1-C4 (critiques)
2. Dry-run 2-4 semaines minimum
3. Comparer resultats dry-run vs backtest (ecart < 20%)
4. Commencer live avec 50% du capital (50 USDT)
5. Augmenter progressivement sur 2-4 semaines
6. Monitoring Telegram obligatoire

### Axes d'amelioration long terme
1. Implementer une vraie detection de divergence sur swing points
2. Ajouter `custom_stoploss` ATR-based a toutes les strategies
3. Ajouter un vrai filtre volume (`volume > X * volume_sma`)
4. Corriger le look-ahead bias de SmartMoneyConcepts
5. Ajouter `__getstate__`/`__setstate__` aux 8 strategies manquantes
6. Nettoyer le code mort (params inutilises, imports morts)
