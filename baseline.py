#!/usr/bin/env python3
"""
Бейзлайн-проверка сгенерированного датасета: насколько таргет предсказуем по панели.
  python baseline.py data/teacher_burnout.db
Валидация — GroupKFold по user_id. Таргет — burnout_level >= 2.
"""
import sqlite3
import sys

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score, average_precision_score
from sklearn.model_selection import GroupKFold

F = ["event_hours", "activity_hours", "act_avg_participants_per_hour", "act_msg_cnt", "act_msg_char_cnt"]


def add_features(p: pd.DataFrame) -> pd.DataFrame:
    p = p.sort_values(["user_id", "week_dt"]).copy()
    p["chars_per_msg"] = p.act_msg_char_cnt / p.act_msg_cnt.replace(0, np.nan)
    g = p.groupby("user_id")
    for f in F + ["chars_per_msg"]:
        p[f + "_r4"] = g[f].transform(lambda s: s.rolling(4, 1).mean())
        # личная норма — медиана первых 6 недель работы (без заглядывания в будущее дальше этого окна)
        base = g[f].transform(lambda s: s.iloc[:6].median())
        p[f + "_rel"] = p[f + "_r4"] / (base + 1e-6)
        p[f + "_d4"] = p[f] - g[f].transform(lambda s: s.shift(1).rolling(4, 1).mean())
    p["week_of_year"] = pd.to_datetime(p.week_dt).dt.isocalendar().week.astype(int)
    return p


def cv_auc(d, cols, y):
    pr = np.zeros(len(d))
    for tr, te in GroupKFold(5).split(d, y, d.user_id):
        m = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, max_leaf_nodes=15)
        m.fit(d.iloc[tr][cols], y.iloc[tr])
        pr[te] = m.predict_proba(d.iloc[te][cols])[:, 1]
    return roc_auc_score(y, pr), average_precision_score(y, pr)


def main(db):
    con = sqlite3.connect(db)
    p = pd.read_sql("SELECT * FROM teacher_burnout_panel", con)
    print(f"Панель: {len(p):,} строк, учителей {p.user_id.nunique()}, с таргетом {p.burnout_level.notna().sum():,}")
    print("Распределение таргета:", p.burnout_level.value_counts(normalize=True).sort_index().round(3).to_dict())
    p = add_features(p)
    d = p.dropna(subset=["burnout_level"]).reset_index(drop=True)
    y = (d.burnout_level >= 2).astype(int)
    print(f"Доля позитивного класса (level>=2): {y.mean():.3f}")
    rel = [c for c in p.columns if c not in ("user_id", "week_dt", "burnout_level")]
    for name, cols in [("сырые признаки панели", F), ("+ скользящие/относительные", rel)]:
        auc, ap = cv_auc(d, cols, y)
        print(f"  {name:28s} ROC-AUC {auc:.3f}   PR-AUC {ap:.3f}")
    try:
        tr = pd.read_sql("SELECT user_id, profile FROM _gen_teacher_truth", con)
        x = d.merge(tr, on="user_id")
        print("\nУровень по профилям (доля ответов):")
        print(pd.crosstab(x.profile, x.burnout_level, normalize="index").round(2))
    except Exception:
        pass


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "data/teacher_burnout.db")
