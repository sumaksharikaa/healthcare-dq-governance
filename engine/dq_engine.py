"""
dq_engine.py
Healthcare Data Quality & Governance — Rules Engine
Runs configurable validation rules across datasets and produces
scored results, issue logs, and reconciliation reports.
"""

import pandas as pd
import numpy as np
from datetime import datetime, date
import json, os, logging

log = logging.getLogger(__name__)

# =============================================================================
# RULE DEFINITIONS — fully configurable
# =============================================================================

RULES = {
    "patients": [
        {"rule_id":"PAT-001","category":"Completeness","severity":"Critical",
         "description":"patient_id must not be null",
         "check": lambda df: df["patient_id"].isna()},
        {"rule_id":"PAT-002","category":"Completeness","severity":"Critical",
         "description":"date_of_birth must not be null",
         "check": lambda df: df["date_of_birth"].isna()},
        {"rule_id":"PAT-003","category":"Completeness","severity":"High",
         "description":"gender must not be null",
         "check": lambda df: df["gender"].isna()},
        {"rule_id":"PAT-004","category":"Completeness","severity":"Medium",
         "description":"state must not be null",
         "check": lambda df: df["state"].isna()},
        {"rule_id":"PAT-005","category":"Validity","severity":"High",
         "description":"gender must be M, F, or Other",
         "check": lambda df: df["gender"].notna() & ~df["gender"].isin(["M","F","Other"])},
        {"rule_id":"PAT-006","category":"Validity","severity":"Medium",
         "description":"zip_code must be 5 digits",
         "check": lambda df: df["zip_code"].astype(str).str.len().ne(5) |
                             ~df["zip_code"].astype(str).str.isdigit()},
        {"rule_id":"PAT-007","category":"Uniqueness","severity":"Critical",
         "description":"patient_id must be unique",
         "check": lambda df: df.duplicated(subset=["patient_id"], keep=False)},
        {"rule_id":"PAT-008","category":"Validity","severity":"High",
         "description":"date_of_birth must be a valid past date",
         "check": lambda df: pd.to_datetime(df["date_of_birth"], errors="coerce").isna() |
                             (pd.to_datetime(df["date_of_birth"], errors="coerce") >
                              pd.Timestamp.now())},
        {"rule_id":"PAT-009","category":"Completeness","severity":"Low",
         "description":"email should be populated",
         "check": lambda df: df["email"].isna()},
    ],
    "encounters": [
        {"rule_id":"ENC-001","category":"Completeness","severity":"Critical",
         "description":"encounter_id must not be null",
         "check": lambda df: df["encounter_id"].isna()},
        {"rule_id":"ENC-002","category":"Completeness","severity":"Critical",
         "description":"patient_id must not be null",
         "check": lambda df: df["patient_id"].isna()},
        {"rule_id":"ENC-003","category":"Completeness","severity":"High",
         "description":"admission_date must not be null",
         "check": lambda df: df["admission_date"].isna()},
        {"rule_id":"ENC-004","category":"Completeness","severity":"High",
         "description":"primary_diagnosis must not be null",
         "check": lambda df: df["primary_diagnosis"].isna()},
        {"rule_id":"ENC-005","category":"Validity","severity":"Critical",
         "description":"discharge_date must not be before admission_date",
         "check": lambda df: (
             pd.to_datetime(df["discharge_date"], errors="coerce") <
             pd.to_datetime(df["admission_date"], errors="coerce"))},
        {"rule_id":"ENC-006","category":"Validity","severity":"Critical",
         "description":"discharge_date must not be in the future",
         "check": lambda df: pd.to_datetime(df["discharge_date"], errors="coerce") >
                             pd.Timestamp.now()},
        {"rule_id":"ENC-007","category":"Validity","severity":"High",
         "description":"total_charges_usd must be positive",
         "check": lambda df: pd.to_numeric(df["total_charges_usd"], errors="coerce") < 0},
        {"rule_id":"ENC-008","category":"Referential","severity":"Critical",
         "description":"patient_id must exist in patients table",
         "check": None},   # resolved at runtime with cross-table check
        {"rule_id":"ENC-009","category":"Uniqueness","severity":"Critical",
         "description":"encounter_id must be unique",
         "check": lambda df: df.duplicated(subset=["encounter_id"], keep=False)},
    ],
    "lab_results": [
        {"rule_id":"LAB-001","category":"Completeness","severity":"Critical",
         "description":"lab_id must not be null",
         "check": lambda df: df["lab_id"].isna()},
        {"rule_id":"LAB-002","category":"Completeness","severity":"Critical",
         "description":"result_value must not be null",
         "check": lambda df: df["result_value"].isna()},
        {"rule_id":"LAB-003","category":"Completeness","severity":"Medium",
         "description":"unit must not be null",
         "check": lambda df: df["unit"].isna()},
        {"rule_id":"LAB-004","category":"Validity","severity":"High",
         "description":"result_value must be >= -999 (extreme outlier check)",
         "check": lambda df: pd.to_numeric(df["result_value"], errors="coerce") < -999},
        {"rule_id":"LAB-005","category":"Validity","severity":"High",
         "description":"result_date must not precede collection_date",
         "check": lambda df: (
             pd.to_datetime(df["result_date"], errors="coerce") <
             pd.to_datetime(df["collection_date"], errors="coerce"))},
        {"rule_id":"LAB-006","category":"Referential","severity":"Critical",
         "description":"patient_id must exist in patients table",
         "check": None},
        {"rule_id":"LAB-007","category":"Validity","severity":"Medium",
         "description":"status must be Final, Preliminary, Corrected, or Cancelled",
         "check": lambda df: df["status"].notna() &
                             ~df["status"].isin(["Final","Preliminary","Corrected","Cancelled"])},
    ],
    "medications": [
        {"rule_id":"MED-001","category":"Completeness","severity":"Critical",
         "description":"med_id must not be null",
         "check": lambda df: df["med_id"].isna()},
        {"rule_id":"MED-002","category":"Completeness","severity":"High",
         "description":"dose must not be null",
         "check": lambda df: df["dose"].isna()},
        {"rule_id":"MED-003","category":"Completeness","severity":"High",
         "description":"start_date must not be null",
         "check": lambda df: df["start_date"].isna()},
        {"rule_id":"MED-004","category":"Validity","severity":"High",
         "description":"end_date must not precede start_date",
         "check": lambda df: (
             pd.to_datetime(df["end_date"], errors="coerce") <
             pd.to_datetime(df["start_date"], errors="coerce"))},
        {"rule_id":"MED-005","category":"Validity","severity":"Medium",
         "description":"frequency must be a known value",
         "check": lambda df: df["frequency"].notna() &
                             ~df["frequency"].isin(["Daily","BID","TID","QID","Weekly","PRN","Monthly"])},
    ],
}

SEVERITY_WEIGHT = {"Critical":4, "High":3, "Medium":2, "Low":1}

# =============================================================================
# DOWNSTREAM IMPACT REGISTRY
# =============================================================================

DOWNSTREAM_REGISTRY = [
    {"report":"Patient Demographics Report",  "tables":["patients"],
     "owner":"Analytics Team", "refresh":"Daily","criticality":"High"},
    {"report":"Readmission KPI Dashboard",    "tables":["encounters","patients"],
     "owner":"Quality Team",   "refresh":"Daily","criticality":"Critical"},
    {"report":"Lab Trends Dashboard",         "tables":["lab_results","patients"],
     "owner":"Clinical Team",  "refresh":"Weekly","criticality":"High"},
    {"report":"Medication Adherence Report",  "tables":["medications","patients"],
     "owner":"Pharmacy Team",  "refresh":"Monthly","criticality":"Medium"},
    {"report":"Payer Mix Dashboard",          "tables":["patients","encounters"],
     "owner":"Finance Team",   "refresh":"Weekly","criticality":"High"},
    {"report":"Regulatory Compliance Report", "tables":["patients","encounters","lab_results","medications"],
     "owner":"Compliance",     "refresh":"Monthly","criticality":"Critical"},
    {"report":"Clinical Quality Measures",    "tables":["lab_results","medications","encounters"],
     "owner":"Quality Team",   "refresh":"Daily","criticality":"Critical"},
]


# =============================================================================
# ENGINE
# =============================================================================

class DQEngine:
    def __init__(self, data_dir: str):
        self.data_dir   = data_dir
        self.datasets   = {}
        self.results    = []
        self.run_time   = datetime.now()
        self.run_id     = self.run_time.strftime("RUN_%Y%m%d_%H%M%S")

    # ── load ──────────────────────────────────────────────────────────────────
    def load(self):
        for name in ["patients","encounters","lab_results","medications"]:
            path = os.path.join(self.data_dir, f"{name}.csv")
            self.datasets[name] = pd.read_csv(path, low_memory=False)
            log.info(f"Loaded {name}: {len(self.datasets[name]):,} rows")

    # ── run all rules ─────────────────────────────────────────────────────────
    def run_rules(self):
        all_patients = set(self.datasets["patients"]["patient_id"].dropna().tolist())

        for table, rules in RULES.items():
            df = self.datasets[table]
            for rule in rules:
                # cross-table referential check
                if rule["check"] is None:
                    if "patient_id" in df.columns:
                        mask = ~df["patient_id"].isin(all_patients)
                    else:
                        mask = pd.Series([False]*len(df), index=df.index)
                else:
                    try:
                        mask = rule["check"](df)
                    except Exception as e:
                        log.warning(f"Rule {rule['rule_id']} error: {e}")
                        mask = pd.Series([False]*len(df), index=df.index)

                mask = mask.fillna(False)
                failed_count = int(mask.sum())
                total        = len(df)
                pass_rate    = round((total - failed_count) / total * 100, 2) if total else 0

                self.results.append({
                    "run_id":        self.run_id,
                    "run_time":      self.run_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "table_name":    table,
                    "rule_id":       rule["rule_id"],
                    "category":      rule["category"],
                    "severity":      rule["severity"],
                    "description":   rule["description"],
                    "total_records": total,
                    "failed_records":failed_count,
                    "passed_records":total - failed_count,
                    "pass_rate_pct": pass_rate,
                    "status":        "PASS" if failed_count == 0 else "FAIL",
                })

    # ── data profile ──────────────────────────────────────────────────────────
    def profile(self):
        profiles = []
        for table, df in self.datasets.items():
            for col in df.columns:
                s = df[col]
                profiles.append({
                    "table_name":     table,
                    "column_name":    col,
                    "total_count":    len(s),
                    "null_count":     int(s.isna().sum()),
                    "null_pct":       round(s.isna().mean()*100, 2),
                    "unique_count":   int(s.nunique()),
                    "uniqueness_pct": round(s.nunique()/len(s)*100, 2) if len(s) else 0,
                    "is_numeric":     pd.api.types.is_numeric_dtype(s),
                    "min_value":      str(s.min()) if pd.api.types.is_numeric_dtype(s) else None,
                    "max_value":      str(s.max()) if pd.api.types.is_numeric_dtype(s) else None,
                    "mean_value":     round(float(s.mean()),2) if pd.api.types.is_numeric_dtype(s) else None,
                    "sample_values":  str(s.dropna().sample(min(3,s.notna().sum())).tolist()) if s.notna().sum()>0 else "[]",
                })
        return pd.DataFrame(profiles)

    # ── reconciliation ────────────────────────────────────────────────────────
    def reconcile(self, source_counts: dict):
        """Compare source record counts to loaded counts."""
        recon = []
        for table, df in self.datasets.items():
            src = source_counts.get(table, len(df))
            loaded = len(df)
            delta  = loaded - src
            recon.append({
                "table_name":      table,
                "source_count":    src,
                "loaded_count":    loaded,
                "delta":           delta,
                "delta_pct":       round(delta/src*100, 2) if src else 0,
                "status":          "MATCH" if delta == 0 else "MISMATCH",
                "run_time":        self.run_time.strftime("%Y-%m-%d %H:%M:%S"),
            })
        return pd.DataFrame(recon)

    # ── DQ scores ─────────────────────────────────────────────────────────────
    def score(self):
        if not self.results:
            return pd.DataFrame()
        df = pd.DataFrame(self.results)

        # Weighted score per table
        table_scores = []
        for table in df["table_name"].unique():
            tdf = df[df["table_name"]==table]
            total_weight  = tdf["severity"].map(SEVERITY_WEIGHT).sum()
            passed_weight = tdf[tdf["status"]=="PASS"]["severity"].map(SEVERITY_WEIGHT).sum()
            score = round(passed_weight / total_weight * 100, 1) if total_weight else 0
            table_scores.append({
                "table_name":    table,
                "total_rules":   len(tdf),
                "passed_rules":  (tdf["status"]=="PASS").sum(),
                "failed_rules":  (tdf["status"]=="FAIL").sum(),
                "dq_score":      score,
                "grade":         "A" if score>=90 else "B" if score>=80 else "C" if score>=70 else "D" if score>=60 else "F",
                "run_time":      self.run_time.strftime("%Y-%m-%d %H:%M:%S"),
            })
        return pd.DataFrame(table_scores)

    # ── downstream impact ─────────────────────────────────────────────────────
    def downstream_impact(self):
        if not self.results:
            return pd.DataFrame()
        failed_tables = set(
            r["table_name"] for r in self.results
            if r["status"] == "FAIL" and r["severity"] in ["Critical","High"]
        )
        impacts = []
        for reg in DOWNSTREAM_REGISTRY:
            affected_tables = [t for t in reg["tables"] if t in failed_tables]
            if affected_tables:
                issue_count = sum(
                    r["failed_records"] for r in self.results
                    if r["table_name"] in affected_tables and r["status"]=="FAIL"
                )
                impacts.append({
                    "report":           reg["report"],
                    "owner":            reg["owner"],
                    "refresh_cadence":  reg["refresh"],
                    "criticality":      reg["criticality"],
                    "affected_tables":  ", ".join(affected_tables),
                    "total_issues":     issue_count,
                    "impact_level":     "High" if reg["criticality"]=="Critical" else "Medium",
                    "run_time":         self.run_time.strftime("%Y-%m-%d %H:%M:%S"),
                })
        return pd.DataFrame(impacts)

    # ── audit log ─────────────────────────────────────────────────────────────
    def audit_log(self):
        """Simulate audit log entries based on DQ run results."""
        log_entries = []
        base = self.run_time
        for r in self.results:
            if r["status"] == "FAIL":
                log_entries.append({
                    "log_id":       f"AUD{len(log_entries)+1:06d}",
                    "event_time":   base.strftime("%Y-%m-%d %H:%M:%S"),
                    "table_name":   r["table_name"],
                    "rule_id":      r["rule_id"],
                    "event_type":   "DQ_VIOLATION",
                    "severity":     r["severity"],
                    "description":  r["description"],
                    "records_affected": r["failed_records"],
                    "action_taken": "Flagged for review" if r["severity"] in ["Medium","Low"]
                                    else "Quarantined pending remediation",
                    "resolved":     False,
                })
        return pd.DataFrame(log_entries)

    # ── run full pipeline ─────────────────────────────────────────────────────
    def run(self):
        log.info(f"DQ Engine run: {self.run_id}")
        self.load()
        self.run_rules()

        results_df  = pd.DataFrame(self.results)
        scores_df   = self.score()
        profile_df  = self.profile()
        recon_df    = self.reconcile({"patients":800,"encounters":3000,
                                      "lab_results":6000,"medications":4000})
        impact_df   = self.downstream_impact()
        audit_df    = self.audit_log()

        out = self.data_dir
        results_df.to_csv(f"{out}/dq_results.csv",       index=False)
        scores_df.to_csv(f"{out}/dq_scores.csv",         index=False)
        profile_df.to_csv(f"{out}/data_profile.csv",     index=False)
        recon_df.to_csv(f"{out}/reconciliation.csv",     index=False)
        impact_df.to_csv(f"{out}/downstream_impact.csv", index=False)
        audit_df.to_csv(f"{out}/audit_log.csv",          index=False)

        print(f"\n{'='*55}")
        print(f"DQ RUN COMPLETE — {self.run_id}")
        print(f"{'='*55}")
        for _, row in scores_df.iterrows():
            bar = "█"*int(row['dq_score']//5) + "░"*(20-int(row['dq_score']//5))
            print(f"  {row['table_name']:<15} [{bar}] {row['dq_score']:5.1f}%  Grade: {row['grade']}")
        total_issues = sum(r["failed_records"] for r in self.results if r["status"]=="FAIL")
        print(f"\n  Total issues found: {total_issues:,}")
        print(f"  Downstream reports affected: {len(impact_df)}")
        print(f"{'='*55}\n")
        return results_df, scores_df, profile_df, recon_df, impact_df, audit_df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    engine = DQEngine(data_dir)
    engine.run()
