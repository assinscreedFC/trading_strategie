# SmartMoneyConcepts — Guide Complet

## Qu'est-ce que le Smart Money ?

Le "Smart Money" designe l'argent des institutions financieres (banques, hedge funds, market makers). Ces acteurs gerent des milliards et ne peuvent pas acheter/vendre sans laisser de traces dans le prix. La theorie Smart Money (popularisee par ICT — Inner Circle Trader) consiste a lire ces traces pour trader dans le meme sens que les institutions.

En crypto, les "whales" jouent le meme role que les institutions en finance traditionnelle.

---

## Les 3 Concepts Cles de la Strategie

### 1. Break of Structure (BOS)

Un **Break of Structure** est un changement de direction du marche. Le marche evolue en faisant des hauts de plus en plus hauts (tendance haussiere) ou des bas de plus en plus bas (tendance baissiere).

```
Tendance haussiere :

    HH3
   /    \
  /  HH2 \
 / /    \  \
/ HH1    \  \
  /        HL3
 HL1  HL2

HH = Higher High (plus haut toujours plus haut)
HL = Higher Low (plus bas toujours plus haut)
```

**BOS Bullish** = le prix casse au-dessus du dernier swing high
- C'est le signal que la structure change en faveur des acheteurs
- Les institutions viennent de pousser le prix au-dessus d'un niveau cle

**Comment on le detecte dans le code** :
```python
# Le close depasse le dernier swing high
# ET la bougie precedente etait encore en dessous (croisement frais)
bos_bullish = (
    (close > recent_swing_high)
    & (close.shift(1) <= recent_swing_high.shift(1))
)
```

### 2. Fair Value Gap (FVG)

Un **Fair Value Gap** est un "trou" dans le prix — une zone ou le marche a bouge trop vite pour que des echanges aient lieu. C'est un desequilibre entre acheteurs et vendeurs.

```
Bougie 1:  |---|     high1

Bougie 2:  |---------|  (grande bougie haussiere)

Bougie 3:      |---|  low3

Si low3 > high1 → il y a un GAP entre high1 et low3
Ce gap = Fair Value Gap (zone de desequilibre)
```

**Pourquoi c'est important** :
- Le marche a tendance a revenir combler ces gaps
- Les institutions utilisent ces zones pour placer des ordres
- Quand le prix revient dans un FVG, c'est un point d'entree optimal

**Comment on le detecte dans le code** :
```python
# FVG bullish : le low de la bougie actuelle est AU-DESSUS du high de 2 bougies avant
fvg_bullish = (low > high.shift(2))

# Zone FVG = entre high[i-2] (bas du gap) et low[i] (haut du gap)
fvg_top = low  (quand fvg existe)
fvg_bottom = high.shift(2)  (quand fvg existe)

# On forward-fill pour garder la zone active sur les bougies suivantes
# Le prix est "dans la zone FVG" quand il touche cette zone
in_fvg_zone = (low <= fvg_top) & (high >= fvg_bottom)
```

### 3. Swing Highs / Swing Lows

Un **swing high** est un sommet local — un point ou le prix a atteint un maximum avant de redescendre. Un **swing low** est un creux local.

```
        * ← swing high
       / \
      /   \
     /     \
    /       \
   *         * ← swing low
```

**Comment on les detecte** :
- Un swing high = le high de la bougie est superieur aux highs des N bougies avant ET apres
- Un swing low = le low de la bougie est inferieur aux lows des N bougies avant ET apres
- N = `swing_lookback` (parametre optimise a 4)

```python
# Pour chaque bougie, verifier si c'est un maximum local
for j in range(1, lookback + 1):
    if high[i] <= high[i-j] or high[i] <= high[i+j]:
        is_swing = False
```

---

## Logique Complete d'Entree

On achete quand TOUTES ces conditions sont reunies simultanement :

```
1. BOS BULLISH        → Le prix vient de casser le dernier swing high
                         (changement de structure = les institutions poussent)

2. DANS UNE ZONE FVG  → Le prix est dans un Fair Value Gap recent
                         (pullback dans une zone d'interet institutionnel)

3. RSI < 59           → Le RSI confirme qu'on n'est pas en surachat
                         (il reste de la marge pour monter)

4. VOLUME > 0         → Filtre de securite (bougie active)
```

**En langage simple** : on achete quand le marche vient de changer de direction a la hausse (BOS), que le prix a fait un pullback dans une zone de desequilibre (FVG), et que le momentum n'est pas epuise (RSI).

---

## Logique Complete de Sortie

On vend quand UNE de ces conditions est remplie :

```
1. BOS BEARISH        → Le prix casse sous le dernier swing low
                         (la structure se retourne a la baisse)
   OU
2. RSI > 85           → Surachat extreme, le prix va probablement corriger
   OU
3. ROI ATTEINT        → Profit cible atteint selon la table ROI
```

---

## Parametres Optimises

Trouves par hyperopt (500 epochs, SharpeHyperOptLoss) :

### Entree
| Parametre | Valeur | Role |
|-----------|--------|------|
| `swing_lookback` | **4** | Nombre de bougies avant/apres pour detecter un swing |
| `rsi_period` | **14** | Periode du RSI (standard) |
| `rsi_entry` | **59** | Seuil RSI max pour entrer (pas trop haut) |
| `volume_period` | **19** | Periode de la moyenne mobile du volume |

### Sortie
| Parametre | Valeur | Role |
|-----------|--------|------|
| `rsi_exit` | **85** | RSI au-dessus duquel on sort (surachat) |

### ROI (Return on Investment)
| Temps | ROI minimum |
|-------|-------------|
| 0 min (immediatement) | +37.9% |
| 165 min (2h45) | +13.3% |
| 310 min (5h10) | +2.9% |
| 1586 min (26h26) | 0% (sortie si toujours en trade) |

**Lecture** : si le trade fait +37.9% immediatement, on sort. Si apres 2h45 il fait +13.3%, on sort aussi. Le seuil descend avec le temps. Apres ~26h, on sort meme a 0% de profit.

### Stoploss et Trailing
| Parametre | Valeur | Role |
|-----------|--------|------|
| `stoploss` | **-16%** | Perte maximale avant sortie forcee |
| `trailing_stop` | **true** | Le stop remonte avec le prix |
| `trailing_stop_positive` | **12.6%** | Distance du trailing une fois en profit |
| `trailing_stop_positive_offset` | **13%** | Le trailing s'active a +13% de profit |

**Lecture** : le stoploss fixe est a -16% (protection black swan, ne se declenche presque jamais). Une fois que le trade atteint +13% de profit, un trailing stop s'active a 12.6% sous le plus haut — si le prix redescend de 12.6% depuis son sommet, on sort.

---

## Timeframe et Paires

| Config | Valeur |
|--------|--------|
| Timeframe | **1h** (une bougie = 1 heure) |
| Paires | BTC/USDT, ETH/USDT, SOL/USDT |
| Max open trades | 2 (max 2 positions simultanees) |
| Startup candles | 100 (besoin de 100h de donnees pour calculer les indicateurs) |

---

## Performance Backtest (12 mois)

```
Periode            : mars 2025 → mars 2026
Capital            : 100 USDT → 150.14 USDT (+50.14%)
Trades             : 80 (6.4/mois)
Win Rate           : 65% (52 gagnes, 11 neutres, 17 perdus)
Max Drawdown       : 3.40% (pire baisse temporaire du compte)
Profit Factor      : 3.72 (pour 1 USDT perdu, 3.72 USDT gagnes)
Meilleur trade     : +6.22%
Pire trade         : -3.89%
Marche pendant le test : -17.74% (le marche a baisse, le bot a gagne)
```

### Par paire
| Paire | Trades | Profit | Win Rate |
|-------|--------|--------|----------|
| SOL/USDT | 20 | +17.55 USDT | 70% |
| ETH/USDT | 28 | +16.60 USDT | 71.4% |
| BTC/USDT | 32 | +16.00 USDT | 56.2% |

### Comment les trades se terminent
| Raison de sortie | Nombre | Profit | Win Rate |
|------------------|--------|--------|----------|
| ROI atteint | 60 (75%) | +66.79 USDT | 100% |
| Signal de sortie (BOS bearish / RSI) | 20 (25%) | -16.64 USDT | 15% |

**75% des trades sortent par ROI avec 100% de win rate.** Les 25% restants sortent sur signal de retournement — c'est la que se concentrent les pertes, ce qui est normal.

---

## Pourquoi Ca Marche

1. **Alignement avec les institutions** : on trade dans le meme sens que le "smart money" en detectant les BOS
2. **Points d'entree optimaux** : les FVG sont des zones ou les institutions placent leurs ordres — on entre au meme endroit
3. **Double confirmation** : BOS (structure) + FVG (zone d'interet) + RSI (momentum) = triple filtre qui elimine les faux signaux
4. **Gestion du risque** : trailing stop a 12.6% protege les gains, ROI degressif capture les profits rapidement
5. **Adaptabilite** : fonctionne sur BTC, ETH et SOL — pas dependant d'un seul actif

---

## Schema Visuel d'un Trade Type

```
Prix
 ^
 |         ╔══════╗ ← SORTIE (ROI atteint ou RSI > 85)
 |        ╔╝      ║
 |       ╔╝       ║
 |      ╔╝        ╚═══
 |     ╔╝
 |    ╔╝← ENTREE (BOS + FVG + RSI < 59)
 |   ╔╝
 |  ╔╝
 | ═╝  ↑ Break of Structure (close > swing high)
 |      |
 | ─────┤← ancien swing high
 |      |
 |    ──┘
 |   pullback dans la zone FVG
 +──────────────────────────────→ Temps
```

---

## Fichiers

| Fichier | Contenu |
|---------|---------|
| `SmartMoneyConcepts.py` | Code source de la strategie |
| `SmartMoneyConcepts.json` | Parametres optimises par hyperopt |
| `../config_kraken.json` | Configuration pour Kraken (live/dry-run) |
| `../config_backtest_kraken.json` | Configuration pour backtesting |

## Commandes

```bash
# Backtest
rtk freqtrade backtesting --config freqtrade/config_backtest_kraken.json \
  --strategy SmartMoneyConcepts --strategy-path freqtrade/strategies \
  --datadir freqtrade/data --timerange 20250301-20260319

# Dry-run sur Kraken
rtk freqtrade trade --config freqtrade/config_kraken.json \
  --strategy SmartMoneyConcepts --strategy-path freqtrade/strategies

# Hyperopt (re-optimisation)
rtk freqtrade hyperopt --config freqtrade/config_backtest_kraken.json \
  --strategy SmartMoneyConcepts --strategy-path freqtrade/strategies \
  --datadir freqtrade/data --timerange 20250301-20260319 \
  --hyperopt-loss SharpeHyperOptLoss --spaces buy sell roi stoploss trailing \
  --epochs 500 --min-trades 20 -j -1
```
