# Project context for Claude Code

WC2026 Monte Carlo simulator. Two parts:

1. **Front end** — `index.html`, a single self-contained file (vanilla JS, no build step, no deps). Embeds two posterior parameter sets and runs the tournament simulation client-side. Edit the `<script>` block directly.
2. **Backend** — `retrain.py`, a standalone Python script (numpy/scipy) that downloads match history, fits an attack/defence Poisson model with temporal decay, and writes `POST.json` in the schema the front end expects: `{teams[], att[team][draw], deff[team][draw], base[draw], home_adv[draw]}`.

To refresh the model end to end: `python retrain.py` → produces `POST.json` → re-embed that JSON into the `POST_B` constant inside `index.html`.

Knockout logic uses the official FIFA 2026 bracket (matches 73–104) with the Annex C third-place allocation constraints. The Monte Carlo lives in the `runT()` function in `index.html`.

No test suite yet. Validate changes by checking: champion probabilities sum to 1.0, and exactly 32 teams reach the round of 32.
