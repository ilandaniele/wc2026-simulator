# WC2026 Bayesian Simulator

Monte Carlo simulator for the 2026 FIFA World Cup. Self-contained — the front end runs entirely in the browser, no server required.

## What's here

| File | Purpose |
|------|---------|
| `index.html` | The simulator. Single self-contained file (~630 KB). Open in any browser. |
| `retrain.py` | Backend: re-trains the attack/defence model with temporal decay and exports `POST.json`. |
| `requirements.txt` | Python deps for `retrain.py` (numpy, scipy). |

## Run the front end

Just open `index.html` in a browser, or serve it:

```bash
python -m http.server 8000
# http://localhost:8000/index.html
```

Tabs: **Title** (per-stage probabilities, official FIFA bracket), **Today's matches**, **vs Bookmaker** (model vs de-vigged odds + edge), **Head-to-head** (any pairing with a 90% credible interval), **Strength**. Controls: model selector (PyMC calibrated / retrained-decay), number of tournaments, and toggles (bivariate Poisson, form, injuries).

## Retrain the model

```bash
pip install -r requirements.txt
python retrain.py 3 400   # half-life 3 years, 400 posterior draws
```

Downloads the international results history (incl. live WC2026 results), weights matches by recency (temporal decay), fits a hierarchical Poisson attack/defence model via IRLS with a Gaussian prior, and approximates the posterior by Laplace. Writes `POST.json`. Runs in < 1 s.

## Model

- **Goals**: Poisson per team, `log λ = base + home_adv + attack_scorer − defence_conceder`. Optional bivariate (common-shock) term for goal correlation.
- **Prior**: ridge / Gaussian shrinkage toward the mean (hierarchical).
- **Knockout**: official FIFA bracket structure (matches 73–104) + best-eight third-placed assignment respecting the Annex C allowed-group lists.
- **Uncertainty**: posterior draws propagated through the Monte Carlo → credible intervals on every probability.

## Caveat

The model does not see last-minute lineups or injuries beyond the manual toggle. Where it disagrees strongly with the market, the market usually holds information the model lacks. Treat the credible interval as a confidence filter — wide = don't bet.
