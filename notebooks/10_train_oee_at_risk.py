# Databricks notebook source
# MAGIC %md
# MAGIC # Stage 3a · Next-shift OEE at-risk model
# MAGIC
# MAGIC **Question a shift supervisor asks at handover:** *which assets will miss the OEE floor next shift, and why?*
# MAGIC
# MAGIC * **Data:** `gold_shift_features` — one row per asset per shift, built by the Lakeflow pipeline from OT condition
# MAGIC   signals (vibration, temperature, power, alarms, minor stops) and IT outcomes (MES counts → OEE).
# MAGIC * **Label:** `next_shift_oee < 0.65` (the plant's at-risk floor; plant average is ~0.74).
# MAGIC * **Split:** by time — train on the first 20 days, test on the last 8, so the test mimics using the model on future shifts.
# MAGIC * **Baseline:** "flag the asset if THIS shift's OEE is already under 0.65" — what a supervisor does today.
# MAGIC * **Output:** MLflow model with signature registered in Unity Catalog (alias `champion`), and the latest-shift
# MAGIC   risk for every asset written to `gold_asset_risk` with the top drivers per asset (SHAP).
# MAGIC
# MAGIC Runs on serverless (this workspace allows serverless compute only), so the ML libraries are pip-installed below.

# COMMAND ----------

# MAGIC %pip install -q "mlflow>=3.1" "scikit-learn>=1.5" shap
# MAGIC %restart_python

# COMMAND ----------

dbutils.widgets.text("catalog", "nraameast1_catalog")
dbutils.widgets.text("schema", "plant_floor_oee_febar")
dbutils.widgets.text("risk_threshold", "0.5")
CATALOG, SCHEMA = dbutils.widgets.get("catalog"), dbutils.widgets.get("schema")
THRESHOLD = float(dbutils.widgets.get("risk_threshold"))
S = f"{CATALOG}.{SCHEMA}"
MODEL_NAME = f"{S}.oee_at_risk_model"
OEE_FLOOR = 0.65
TRAIN_DAYS = 20

# COMMAND ----------

import mlflow, numpy as np, pandas as pd, shap
from mlflow.models import infer_signature
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score, average_precision_score, precision_score, recall_score, f1_score, confusion_matrix

mlflow.set_registry_uri("databricks-uc")
NUMERIC = ["vib_mean_running", "vib_max", "vib_p95", "vib_trend_vs_prev6", "temp_mean", "temp_max", "power_mean",
           "vib_alarms", "temp_alarms", "fault_alarms", "minor_stop_count", "unplanned_down_min",
           "oee", "availability", "performance", "quality", "scrap_rate", "oee_prev3_avg"]
WORK_CENTERS = ["WC_MACH", "WC_GRND", "WC_COAT", "WC_WELD", "WC_INSP"]
FEATURES = NUMERIC + [f"wc_{w}" for w in WORK_CENTERS]

def featurize(pdf):
    X = pdf[NUMERIC].astype("float64").copy()
    for w in WORK_CENTERS:
        X[f"wc_{w}"] = (pdf["work_center"] == w).astype("float64")
    return X[FEATURES]

df = spark.table(f"{S}.gold_shift_features").toPandas().sort_values(["shift_start", "asset_id"])
labelled = df[df.next_shift_oee.notna()].copy()
labelled["label"] = (labelled.next_shift_oee < OEE_FLOOR).astype(int)
cutoff = labelled.shift_start.min() + pd.Timedelta(days=TRAIN_DAYS)
train, test = labelled[labelled.shift_start < cutoff], labelled[labelled.shift_start >= cutoff]
print(f"rows: train={len(train)} test={len(test)} | at-risk rate train={train.label.mean():.3f} test={test.label.mean():.3f} | cutoff={cutoff}")

# COMMAND ----------

# MAGIC %md ## Train, evaluate against the supervisor baseline, register in Unity Catalog

# COMMAND ----------

mlflow.set_experiment(f"/Users/{spark.sql('select current_user()').first()[0]}/plant_oee_at_risk")
params = dict(max_iter=300, learning_rate=0.05, max_depth=4, l2_regularization=1.0, class_weight="balanced", random_state=7)

with mlflow.start_run(run_name="hgb_next_shift_oee_at_risk") as run:
    model = HistGradientBoostingClassifier(**params).fit(featurize(train), train.label)
    p_test = model.predict_proba(featurize(test))[:, 1]
    yhat = (p_test >= THRESHOLD).astype(int)
    base = (test.oee < OEE_FLOOR).astype(int)

    def scores(y, pred):
        return dict(precision=precision_score(y, pred, zero_division=0), recall=recall_score(y, pred), f1=f1_score(y, pred))
    m_model, m_base = scores(test.label, yhat), scores(test.label, base)
    metrics = {"test_auc": roc_auc_score(test.label, p_test), "test_avg_precision": average_precision_score(test.label, p_test),
               **{f"test_{k}": v for k, v in m_model.items()}, **{f"baseline_{k}": v for k, v in m_base.items()}}
    mlflow.log_params({**params, "threshold": THRESHOLD, "oee_floor": OEE_FLOOR, "train_days": TRAIN_DAYS})
    mlflow.log_metrics(metrics)

    X_example = featurize(train.head(5))
    signature = infer_signature(X_example, model.predict_proba(X_example)[:, 1])
    info = mlflow.sklearn.log_model(model, name="model", signature=signature, input_example=X_example,
                                    pyfunc_predict_fn="predict_proba", registered_model_name=MODEL_NAME)

print(f"run_id={run.info.run_id}")
print(pd.DataFrame({"model (threshold %.2f)" % THRESHOLD: m_model, "baseline: current OEE < 0.65": m_base}).round(3).to_string())
print(f"\nAUC={metrics['test_auc']:.3f}  avg_precision={metrics['test_avg_precision']:.3f}")
tn, fp, fn, tp = confusion_matrix(test.label, yhat).ravel()
print(f"confusion (model): tp={tp} fp={fp} fn={fn} tn={tn}")
tn, fp, fn, tp = confusion_matrix(test.label, base).ravel()
print(f"confusion (baseline): tp={tp} fp={fp} fn={fn} tn={tn}")

# COMMAND ----------

from mlflow import MlflowClient
client = MlflowClient()
version = max(int(v.version) for v in client.search_model_versions(f"name='{MODEL_NAME}'"))
client.set_registered_model_alias(MODEL_NAME, "champion", version)
client.update_registered_model(MODEL_NAME, description=(
    "Probability that an asset's NEXT-shift OEE falls below 0.65, from this shift's OT condition signals and IT outcomes. "
    "Trained on gold_shift_features. Input: 23 float features (see signature). Output: risk probability."))
print(f"registered {MODEL_NAME} v{version} -> alias champion")
print("signature:\n", mlflow.models.get_model_info(f"models:/{MODEL_NAME}/{version}").signature)

# COMMAND ----------

# MAGIC %md ## Early-warning check — how far ahead did the model flag the real failures? (test window)

# COMMAND ----------

test = test.assign(risk=p_test)
fails = (spark.table(f"{S}.gold_downtime_events").where("is_major_failure")
         .select("asset_id", "start_ts", "reason_code", "duration_min").toPandas())
rows = []
for f in fails.itertuples():
    prior = test[(test.asset_id == f.asset_id) & (test.shift_start < f.start_ts) &
                 (test.shift_start >= f.start_ts - pd.Timedelta(days=4))].sort_values("shift_start")
    if prior.empty:
        continue
    flagged = prior[prior.risk >= THRESHOLD]
    rows.append(dict(asset_id=f.asset_id, failure_start=f.start_ts, failure=f.reason_code,
                     first_flag=flagged.shift_start.min() if len(flagged) else None,
                     hours_of_warning=round((f.start_ts - flagged.shift_start.min()).total_seconds() / 3600, 1) if len(flagged) else 0.0,
                     shifts_flagged_of_prior=f"{len(flagged)}/{len(prior)}"))
print(pd.DataFrame(rows).to_string(index=False) if rows else "no major failures in the test window")

# COMMAND ----------

# MAGIC %md ## Score the latest shift for every asset → `gold_asset_risk` (with top SHAP drivers)

# COMMAND ----------

champion = mlflow.pyfunc.load_model(f"models:/{MODEL_NAME}@champion")
latest = df.sort_values("shift_start").groupby("asset_id").tail(1).copy()
X_latest = featurize(latest)
pred = np.asarray(champion.predict(X_latest), dtype=float)          # pyfunc -> predict_proba: [n, 2]
latest["risk_score"] = pred[:, 1] if pred.ndim == 2 else pred

explainer = shap.TreeExplainer(model)
sv = np.asarray(explainer.shap_values(X_latest))
if sv.ndim == 3:   # some shap versions return [n, features, classes]
    sv = sv[..., -1]
def drivers(i):
    order = np.argsort(-sv[i])[:3]
    return [f"{FEATURES[j]}={X_latest.iloc[i, j]:.2f} (+{sv[i, j]:.2f})" for j in order if sv[i, j] > 0]
latest["top_drivers"] = [drivers(i) for i in range(len(latest))]
latest["at_risk"] = latest.risk_score >= THRESHOLD
latest["model_version"] = str(version)

out = latest.rename(columns={"shift_id": "scored_shift_id"})[["asset_id", "work_center", "scored_shift_id", "shift_start", "oee", "vib_mean_running", "vib_trend_vs_prev6",
              "temp_max", "vib_alarms", "risk_score", "at_risk", "top_drivers", "model_version"]]
(spark.createDataFrame(out)
 .write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{S}.gold_asset_risk"))
spark.sql(f"COMMENT ON TABLE {S}.gold_asset_risk IS 'Latest-shift next-shift-OEE risk per asset from {MODEL_NAME}@champion, with top SHAP drivers.'")
print(out.sort_values("risk_score", ascending=False)[["asset_id", "scored_shift_id", "oee", "vib_mean_running", "risk_score", "at_risk", "top_drivers"]].to_string(index=False))
