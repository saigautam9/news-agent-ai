"""
NewsAgent AI — ML training pipeline.

Trains two sets of scikit-learn models, all on TF-IDF text features:

  A. News topic classifier — trained on AG News (120k labelled news articles).
     A real, reproducible benchmark result — the headline ML model.

  B. NewsAgent AI models — a domain classifier, a severity classifier and an
     urgency-score regressor, trained on the stories NewsAgent AI collects and
     auto-labels itself (ml/data/corpus.csv + data/log.json). This corpus grows
     every day the deployed app runs, so re-running this script keeps improving
     them.

Models and a metrics report are written to ml/models/.

Usage:  python ml/train.py
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from sklearn.ensemble import RandomForestRegressor  # noqa: E402
from sklearn.feature_extraction.text import TfidfVectorizer  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import (  # noqa: E402
    accuracy_score,
    classification_report,
    cohen_kappa_score,
    confusion_matrix,
    f1_score,
    matthews_corrcoef,
    mean_absolute_error,
    r2_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import (  # noqa: E402
    StratifiedKFold,
    cross_val_score,
    cross_validate,
    train_test_split,
)
from sklearn.pipeline import Pipeline  # noqa: E402
from sklearn.preprocessing import label_binarize  # noqa: E402
from sklearn.svm import LinearSVC  # noqa: E402

from datasets import load_agnews, load_signal_corpus

MODELS = Path(__file__).resolve().parent / "models"
ASSETS = Path(__file__).resolve().parent / "assets"
RANDOM_STATE = 42

# Colorblind-safe (Okabe-Ito) — one per AG News class.
TOPIC_COLORS = {
    "Business": "#E69F00", "Sci/Tech": "#56B4E9",
    "Sports": "#009E73", "World": "#0072B2",
}


def plot_confusion(cm, labels, path, title) -> None:
    fig, ax = plt.subplots(figsize=(5.0, 4.4))
    im = ax.imshow(cm, cmap="Blues")
    ax.set_xticks(range(len(labels)), labels, rotation=20)
    ax.set_yticks(range(len(labels)), labels)
    ax.set_xlabel("Predicted"); ax.set_ylabel("Actual"); ax.set_title(title)
    thresh = cm.max() / 2
    for i in range(len(labels)):
        for j in range(len(labels)):
            ax.text(j, i, f"{cm[i, j]:,}", ha="center", va="center",
                    color="white" if cm[i, j] > thresh else "black", fontsize=9)
    fig.colorbar(im, fraction=0.046, pad=0.04)
    fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)


def plot_roc(y_true, scores, labels, path, title) -> None:
    """OvR ROC from LinearSVC decision-function scores (columns = `labels`)."""
    yb = label_binarize(y_true, classes=labels)
    fig, ax = plt.subplots(figsize=(5.4, 4.4))
    for i, c in enumerate(labels):
        fpr, tpr, _ = roc_curve(yb[:, i], scores[:, i])
        ax.plot(fpr, tpr, color=TOPIC_COLORS.get(c, None), lw=2,
                label=f"{c} (AUC {roc_auc_score(yb[:, i], scores[:, i]):.3f})")
    ax.plot([0, 1], [0, 1], "--", color="gray", lw=1)
    ax.set_xlabel("False positive rate"); ax.set_ylabel("True positive rate")
    ax.set_title(title); ax.legend(loc="lower right", fontsize=9)
    fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)


def text_clf(max_features: int = 40000) -> Pipeline:
    """TF-IDF (unigrams + bigrams) -> LogisticRegression text classifier."""
    return Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    max_features=max_features,
                    ngram_range=(1, 2),
                    stop_words="english",
                    sublinear_tf=True,
                ),
            ),
            (
                "clf",
                LogisticRegression(
                    max_iter=1000,
                    class_weight="balanced",
                    random_state=RANDOM_STATE,
                ),
            ),
        ]
    )


# --------------------------------------------------------------------------
# A. News topic classifier — AG News
# --------------------------------------------------------------------------
def train_topic_classifier() -> dict:
    print("\n" + "=" * 56)
    print("  A. News topic classifier  —  AG News (120k articles)")
    print("=" * 56)

    train_df, test_df = load_agnews()
    labels = sorted(train_df["label"].unique())
    print(f"train: {len(train_df):,}   test: {len(test_df):,}")
    print("classes:", ", ".join(labels))

    # Linear SVM on TF-IDF (unigrams + bigrams) — the strongest linear text
    # model here; beats the Logistic Regression baseline on the held-out set.
    model = Pipeline(
        [
            ("tfidf", TfidfVectorizer(max_features=40000, ngram_range=(1, 2),
                                      stop_words="english", sublinear_tf=True)),
            ("clf", LinearSVC(class_weight="balanced", random_state=RANDOM_STATE)),
        ]
    )
    print("\ntraining ...")
    model.fit(train_df["text"], train_df["label"])

    pred = model.predict(test_df["text"])
    acc = accuracy_score(test_df["label"], pred)
    f1 = f1_score(test_df["label"], pred, average="macro")
    wf1 = f1_score(test_df["label"], pred, average="weighted")
    report = classification_report(test_df["label"], pred, output_dict=True, zero_division=0)
    cm = confusion_matrix(test_df["label"], pred, labels=labels)

    print(f"\ntest accuracy : {acc:.1%}")
    print(f"test macro-F1 : {f1:.3f}\n")
    print(classification_report(test_df["label"], pred, zero_division=0))

    # --- additional metrics --------------------------------------------------
    kappa = cohen_kappa_score(test_df["label"], pred)
    mcc = matthews_corrcoef(test_df["label"], pred)
    scores = model.decision_function(test_df["text"])  # (n, 4) OvR margins
    yb = label_binarize(test_df["label"], classes=labels)
    roc_auc = float(np.mean([roc_auc_score(yb[:, i], scores[:, i]) for i in range(len(labels))]))

    print("computing 5-fold cross-validation (this refits the model 5x) ...")
    cv = cross_validate(
        model, train_df["text"], train_df["label"],
        cv=StratifiedKFold(5, shuffle=True, random_state=RANDOM_STATE),
        scoring=["accuracy", "f1_macro"], n_jobs=-1,
    )
    cv_acc, cv_f1 = cv["test_accuracy"], cv["test_f1_macro"]
    print(f"  ROC-AUC (OvR macro): {roc_auc:.4f}   Cohen's kappa: {kappa:.4f}   MCC: {mcc:.4f}")
    print(f"  CV accuracy: {cv_acc.mean():.4f} ± {cv_acc.std():.4f}   "
          f"CV macro-F1: {cv_f1.mean():.4f} ± {cv_f1.std():.4f}")

    ASSETS.mkdir(exist_ok=True)
    plot_confusion(cm, labels, ASSETS / "topic_confusion_matrix.png",
                   "AG News topic classifier — confusion matrix")
    plot_roc(test_df["label"], scores, labels, ASSETS / "topic_roc_curves.png",
             "AG News topic classifier — ROC (one-vs-rest)")
    print(f"  saved plots -> {ASSETS}/")

    joblib.dump(model, MODELS / "topic_clf.joblib")
    return {
        "dataset": "AG News",
        "model": "TF-IDF (1-2 gram) + LinearSVC",
        "train_size": len(train_df),
        "test_size": len(test_df),
        "accuracy": round(acc, 4),
        "macro_f1": round(f1, 4),
        "weighted_f1": round(wf1, 4),
        "roc_auc_ovr_macro": round(roc_auc, 4),
        "cohen_kappa": round(float(kappa), 4),
        "matthews_corrcoef": round(float(mcc), 4),
        "cv_5fold": {
            "accuracy_mean": round(float(cv_acc.mean()), 4),
            "accuracy_std": round(float(cv_acc.std()), 4),
            "macro_f1_mean": round(float(cv_f1.mean()), 4),
            "macro_f1_std": round(float(cv_f1.std()), 4),
        },
        "labels": labels,
        "per_class": {
            c: {
                "precision": round(float(report[c]["precision"]), 3),
                "recall": round(float(report[c]["recall"]), 3),
                "f1": round(float(report[c]["f1-score"]), 3),
                "support": int(report[c]["support"]),
            }
            for c in labels
        },
        "confusion_matrix": cm.tolist(),
    }


# --------------------------------------------------------------------------
# B. NewsAgent AI models — the project's own collected corpus
# --------------------------------------------------------------------------
def _evaluate_classifier(name: str, df, target: str) -> dict:
    X, y = df["text"], df[target]
    min_class = y.value_counts().min()
    strat = y if min_class >= 2 else None

    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=0.25, random_state=RANDOM_STATE, stratify=strat
    )
    model = text_clf(max_features=4000)
    model.fit(X_tr, y_tr)
    pred = model.predict(X_te)
    acc = accuracy_score(y_te, pred)
    f1 = f1_score(y_te, pred, average="macro")

    folds = min(5, int(min_class))
    cv = (
        cross_val_score(model, X, y, cv=folds, scoring="accuracy").mean()
        if folds >= 2
        else None
    )

    print(f"\n  {name} classifier")
    print(f"    held-out accuracy : {acc:.1%}")
    print(f"    held-out macro-F1 : {f1:.3f}")
    if cv is not None:
        print(f"    {folds}-fold CV accuracy: {cv:.1%}")

    model.fit(X, y)  # refit on all data before saving
    joblib.dump(model, MODELS / f"{target}_clf.joblib")
    return {
        "test_accuracy": round(acc, 3),
        "test_macro_f1": round(f1, 3),
        "cv_accuracy": round(cv, 3) if cv is not None else None,
    }


def train_signal_models() -> dict:
    print("\n" + "=" * 56)
    print("  B. NewsAgent AI models  —  self-collected corpus")
    print("=" * 56)

    df = load_signal_corpus()
    print(f"corpus: {len(df)} labelled stories")

    if len(df) < 16:
        print(
            "\n  corpus too small to train yet — collect more with\n"
            "  `npm run collect-corpus` (the deployed app also grows it daily)."
        )
        return {"corpus_size": len(df), "status": "skipped — corpus too small"}

    if len(df) < 80:
        print("  note: small corpus — metrics are preliminary and improve as it grows.")

    print("\n  domain distribution :", df["domain"].value_counts().to_dict())
    print("  severity distribution:", df["severity"].value_counts().to_dict())

    result: dict = {"corpus_size": len(df)}
    result["domain_classifier"] = _evaluate_classifier("Domain", df, "domain")
    result["severity_classifier"] = _evaluate_classifier("Severity", df, "severity")

    # Urgency regressor — only stories that have an urgency label.
    urg = df.dropna(subset=["urgency"])
    if len(urg) >= 16:
        X_tr, X_te, y_tr, y_te = train_test_split(
            urg["text"], urg["urgency"], test_size=0.25, random_state=RANDOM_STATE
        )
        reg = Pipeline(
            [
                ("tfidf", TfidfVectorizer(max_features=4000, ngram_range=(1, 2),
                                          stop_words="english", sublinear_tf=True)),
                ("reg", RandomForestRegressor(n_estimators=300,
                                              random_state=RANDOM_STATE, n_jobs=-1)),
            ]
        )
        reg.fit(X_tr, y_tr)
        pred = reg.predict(X_te)
        mae = mean_absolute_error(y_te, pred)
        r2 = r2_score(y_te, pred)
        print(f"\n  Urgency regressor")
        print(f"    mean absolute error : {mae:.2f}  (1-10 scale)")
        print(f"    R^2                 : {r2:.2f}")
        reg.fit(urg["text"], urg["urgency"])
        joblib.dump(reg, MODELS / "urgency_reg.joblib")
        result["urgency_regressor"] = {
            "labelled_rows": len(urg),
            "test_mae": round(mae, 3),
            "test_r2": round(r2, 3),
        }
    else:
        print(f"\n  Urgency regressor skipped — only {len(urg)} labelled rows.")
        result["urgency_regressor"] = {"status": "skipped", "labelled_rows": len(urg)}

    return result


def main() -> None:
    MODELS.mkdir(exist_ok=True)
    report = {
        "topic_classifier": train_topic_classifier(),
        "signal_models": train_signal_models(),
    }
    (MODELS / "metrics.json").write_text(json.dumps(report, indent=2) + "\n")

    print("\n" + "=" * 56)
    print(f"  models + metrics.json saved to {MODELS}/")
    print("=" * 56 + "\n")


if __name__ == "__main__":
    main()
