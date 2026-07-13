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

## Evaluation results

Every number below is produced by `python train.py` (which also writes
`models/metrics.json`) and is fully reproducible from the committed data.

### Topic classifier — AG News benchmark

TF-IDF (unigram + bigram) + Logistic Regression, trained on **120,000**
labelled articles and evaluated on the held-out **7,600**-article test set.

| Metric | Score |
| --- | --- |
| Accuracy | **92.1%** |
| Macro F1 | **0.921** |

Per-class (precision / recall / F1):

| Class | Precision | Recall | F1 |
| --- | --- | --- | --- |
| Sports | 0.96 | 0.98 | **0.97** |
| World | 0.94 | 0.91 | **0.92** |
| Sci/Tech | 0.90 | 0.91 | **0.90** |
| Business | 0.90 | 0.89 | **0.89** |

### Domain & severity classifiers — self-collected corpus

Trained on NewsAgent AI's own auto-labelled corpus (**20 stories today** —
preliminary, and improves every day the deployed app collects more):

| Model | Classes | Held-out accuracy | Macro F1 | CV accuracy |
| --- | --- | --- | --- | --- |
| Domain | 6 | 60.0% | 0.25 | — |
| Severity | 4 | 60.0% | 0.375 | 55.0% |
| Urgency (regressor) | 1–10 | skipped — needs more labelled rows | | |

> These self-collected models are deliberately honest about their small-data
> stage: the corpus grows daily, and re-running `train.py` keeps improving them.
> The AG News topic classifier is the headline, benchmark-grade result.
