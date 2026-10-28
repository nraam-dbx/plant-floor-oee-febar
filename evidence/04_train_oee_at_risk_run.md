# Evidence 04 — Next-shift OEE at-risk model: training, baseline comparison, UC registration (job run)

Job task run `590103516604432` exported with outputs. Full run (all code + outputs): [`raw/04_train_oee_at_risk_run.ipynb`](raw/04_train_oee_at_risk_run.ipynb) · source: `notebooks/10_train_oee_at_risk.py`.

# Stage 3a · Next-shift OEE at-risk model

**Question a shift supervisor asks at handover:** *which assets will miss the OEE floor next shift, and why?*

* **Data:** `gold_shift_features` — one row per asset per shift, built by the Lakeflow pipeline from OT condition
  signals (vibration, temperature, power, alarms, minor stops) and IT outcomes (MES counts → OEE).
* **Label:** `next_shift_oee < 0.65` (the plant's at-risk floor; plant average is ~0.74).
* **Split:** by time — train on the first 20 days, test on the last 8, so the test mimics using the model on future shifts.
* **Baseline:** "flag the asset if THIS shift's OEE is already under 0.65" — what a supervisor does today.
* **Output:** MLflow model with signature registered in Unity Catalog (alias `champion`), and the latest-shift
  risk for every asset written to `gold_asset_risk` with the top drivers per asset (SHAP).

Runs on serverless (this workspace allows serverless compute only), so the ML libraries are pip-installed below.

```python
dbutils.widgets.text("catalog", "nraameast1_catalog")
dbutils.widgets.text("schema", "plant_floor_oee_febar")
dbutils.widgets.text("risk_threshold", "0.5")
CATALOG, SCHEMA = dbutils.widgets.get("catalog"), dbutils.widgets.get("schema")
THRESHOLD = float(dbutils.widgets.get("risk_threshold"))
S = f"{CATALOG}.{SCHEMA}"
# … 3 more lines (see notebooks/10_train_oee_at_risk.py)
```

```python
import mlflow, numpy as np, pandas as pd, shap
from mlflow.models import infer_signature
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score, average_precision_score, precision_score, recall_score, f1_score, confusion_matrix

mlflow.set_registry_uri("databricks-uc")
# … 18 more lines (see notebooks/10_train_oee_at_risk.py)
```

Output:
```
rows: train=720 test=276 | at-risk rate train=0.114 test=0.156 | cutoff=2026-10-11 06:00:00
```

## Train, evaluate against the supervisor baseline, register in Unity Catalog

```python
mlflow.set_experiment(f"/Users/{spark.sql('select current_user()').first()[0]}/plant_oee_at_risk")
params = dict(max_iter=300, learning_rate=0.05, max_depth=4, l2_regularization=1.0, class_weight="balanced", random_state=7)

with mlflow.start_run(run_name="hgb_next_shift_oee_at_risk") as run:
    model = HistGradientBoostingClassifier(**params).fit(featurize(train), train.label)
    p_test = model.predict_proba(featurize(test))[:, 1]
# … 23 more lines (see notebooks/10_train_oee_at_risk.py)
```

Output:
```
Registered model 'nraameast1_catalog.plant_floor_oee_febar.oee_at_risk_model' already exists. Creating a new version of this model...

🔗 Created version '4' of model 'nraameast1_catalog.plant_floor_oee_febar.oee_at_risk_model': https://fevm-nraameast1.cloud.databricks.com/explore/data/models/nraameast1_catalog/plant_floor_oee_febar/oee_at_risk_model/version/4?o=7474650251978703

run_id=3e8d59b1cacf4d7a9723ae027f9a9f02
           model (threshold 0.50)  baseline: current OEE < 0.65
precision                   0.816                         0.667
recall                      0.721                         0.651
f1                          0.765                         0.659

AUC=0.869  avg_precision=0.806
confusion (model): tp=31 fp=7 fn=12 tn=226
confusion (baseline): tp=28 fp=14 fn=15 tn=219
```

```python
from mlflow import MlflowClient
client = MlflowClient()
version = max(int(v.version) for v in client.search_model_versions(f"name='{MODEL_NAME}'"))
client.set_registered_model_alias(MODEL_NAME, "champion", version)
client.update_registered_model(MODEL_NAME, description=(
    "Probability that an asset's NEXT-shift OEE falls below 0.65, from this shift's OT condition signals and IT outcomes. "
# … 3 more lines (see notebooks/10_train_oee_at_risk.py)
```

Output:
```
registered nraameast1_catalog.plant_floor_oee_febar.oee_at_risk_model v4 -> alias champion

signature:
 inputs: 
  ['vib_mean_running': double (required), 'vib_max': double (required), 'vib_p95': double (required), 'vib_trend_vs_prev6': double (optional), 'temp_mean': double (required), 'temp_max': double (required), 'power_mean': double (required), 'vib_alarms': double (required), 'temp_alarms': double (required), 'fault_alarms': double (required), 'minor_stop_count': double (required), 'unplanned_down_min': double (required), 'oee': double (required), 'availability': double (required), 'performance': double (required), 'quality': double (required), 'scrap_rate': double (required), 'oee_prev3_avg': double (optional), 'wc_WC_MACH': double (required), 'wc_WC_GRND': double (required), 'wc_WC_COAT': double (required), 'wc_WC_WELD': double (required), 'wc_WC_INSP': double (required)]
outputs: 
  [Tensor('float64', (-1,))]
params: 
  None
```

## Early-warning check — how far ahead did the model flag the real failures? (test window)

```python
test = test.assign(risk=p_test)
fails = (spark.table(f"{S}.gold_downtime_events").where("is_major_failure")
         .select("asset_id", "start_ts", "reason_code", "duration_min").toPandas())
rows = []
for f in fails.itertuples():
    prior = test[(test.asset_id == f.asset_id) & (test.shift_start < f.start_ts) &
# … 9 more lines (see notebooks/10_train_oee_at_risk.py)
```

Output:
```
asset_id       failure_start         failure          first_flag  hours_of_warning shifts_flagged_of_prior
  CNC-03 2026-10-14 20:24:00 SPINDLE_BEARING 2026-10-11 06:00:00              86.4                   11/11
  GRD-02 2026-10-15 14:57:00   WHEEL_SPINDLE 2026-10-12 06:00:00              81.0                   10/12
  WLD-02 2026-10-14 06:57:00       WIRE_FEED 2026-10-11 22:00:00              57.0                    7/10
```

## Score the latest shift for every asset → `gold_asset_risk` (with top SHAP drivers)

```python
champion = mlflow.pyfunc.load_model(f"models:/{MODEL_NAME}@champion")
latest = df.sort_values("shift_start").groupby("asset_id").tail(1).copy()
X_latest = featurize(latest)
pred = np.asarray(champion.predict(X_latest), dtype=float)          # pyfunc -> predict_proba: [n, 2]
latest["risk_score"] = pred[:, 1] if pred.ndim == 2 else pred

# … 17 more lines (see notebooks/10_train_oee_at_risk.py)
```

Output:
```
asset_id scored_shift_id    oee  vib_mean_running  risk_score  at_risk                                                                          top_drivers
  CNC-02    2026-10-18-C 0.5155          6.040306    0.998113     True [vib_trend_vs_prev6=1.77 (+3.70), performance=0.65 (+2.56), temp_mean=56.38 (+0.81)]
  CNC-04    2026-10-18-C 0.8267          2.196757    0.068236    False            [performance=0.90 (+0.86), vib_p95=2.63 (+0.65), temp_mean=48.53 (+0.59)]
  CMM-01    2026-10-18-C 0.8333          0.298798    0.037044    False    [minor_stop_count=0.00 (+0.47), vib_max=0.40 (+0.28), oee_prev3_avg=0.75 (+0.27)]
  GRD-02    2026-10-18-C 0.8067          1.831286    0.029060    False        [availability=0.93 (+0.47), scrap_rate=0.01 (+0.24), temp_mean=48.19 (+0.22)]
  WLD-01    2026-10-18-C 0.7622          0.903417    0.017924    False    [minor_stop_count=0.00 (+0.46), vib_max=1.26 (+0.45), oee_prev3_avg=0.70 (+0.32)]
  CMM-02    2026-10-18-C 0.8444          0.303649    0.016864    False          [temp_mean=49.16 (+0.32), power_mean=3.40 (+0.26), scrap_rate=0.00 (+0.18)]
  WLD-02    2026-10-18-C 0.7466          0.900661    0.014596    False                [performance=0.84 (+0.59), oee=0.75 (+0.18), temp_mean=48.47 (+0.13)]
  CTG-02    2026-10-18-C 0.8001          1.199292    0.014369    False        [availability=0.94 (+0.42), temp_max=86.32 (+0.26), performance=0.88 (+0.24)]
  CTG-01    2026-10-18-C 0.7555          1.201117    0.006071    False                    [oee=0.76 (+0.28), scrap_rate=0.00 (+0.23), quality=1.00 (+0.12)]
  CNC-03    2026-10-18-C 0.8178          2.190846    0.004004    False             [vib_p95=2.62 (+0.68), temp_mean=48.40 (+0.44), scrap_rate=0.00 (+0.19)]
  GRD-01    2026-10-18-C 0.6667          1.795893    0.003449    False       [oee=0.67 (+0.46), unplanned_down_min=62.00 (+0.35), power_mean=16.83 (+0.24)]
  CNC-01    2026-10-18-C 0.7378          2.175634    0.002635    False                   [oee=0.74 (+0.25), vib_p95=2.58 (+0.14), performance=0.87 (+0.04)]
```
