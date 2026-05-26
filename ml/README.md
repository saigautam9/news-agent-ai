# NewsAgent AI — ML module

A Python / scikit-learn module that brings **machine-learning news
classification** to NewsAgent AI — analysing and scoring news stories with
trained models instead of LLM API calls.

## Models

| Model | Task | Type | Trained on |
|---|---|---|---|
| Topic classifier | World / Sports / Business / Sci-Tech | Classification | AG News — 120k articles |
| Domain classifier | Geopolitics / Markets / Technology / Health / Climate / Society | Classification | NewsAgent AI corpus |
| Severity classifier | CRITICAL / HIGH / MEDIUM / LOW | Classification | NewsAgent AI corpus |
| Urgency regressor | a 1–10 urgency score | Regression | NewsAgent AI corpus |

All four use **TF-IDF features** (unigrams + bigrams). The classifiers are
`LogisticRegression`; the urgency predictor is a `RandomForestRegressor`.
Models are evaluated on a held-out test set (and cross-validation for the
smaller corpus).

## Two data sources

1. **AG News** — a standard public benchmark of 120,000 labelled news
   articles. The topic classifier trains on it for a real, reproducible
   accuracy score.
2. **NewsAgent AI corpus** — the stories NewsAgent AI collects and auto-labels
   itself (`ml/data/corpus.csv` + `data/log.json`). It **grows every day** the
   deployed app runs, so re-running `train.py` keeps improving the domain,
   severity and urgency models.

## Pipeline

```
download_data.py / collect-corpus  →  datasets.py  →  train.py  →  models/  →  predict.py
   (get + label data)                  (loaders)      (train+eval)  (saved)     (inference)
```

## Usage

```bash
cd ml
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python download_data.py      # fetch AG News (120k articles)
python train.py              # train + evaluate all models -> models/
python predict.py "Central bank raises interest rates to fight inflation"
```

`train.py` prints an EDA summary, per-model metrics and a classification
report, and writes `ml/models/metrics.json`.

To grow the NewsAgent AI corpus, run `npm run collect-corpus` from the project
root (limited by Gemini's free-tier quota of 20 requests/day).
