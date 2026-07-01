"""
etl_pipeline.py
Healthcare DQ & Governance — ETL Pipeline
Runs DQ engine → loads all results into PostgreSQL governance warehouse
"""

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
import logging, os, sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from engine.dq_engine import DQEngine

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler("etl.log")])
log = logging.getLogger(__name__)

DATA_DIR  = os.path.join(os.path.dirname(__file__), "..", "data")
DB_CONFIG = {
    "host":     os.getenv("DB_HOST",     "localhost"),
    "port":     int(os.getenv("DB_PORT", "5432")),
    "dbname":   os.getenv("DB_NAME",     "hc_dq_db"),
    "user":     os.getenv("DB_USER",     "postgres"),
    "password": os.getenv("DB_PASSWORD", "postgres"),
}


class DQGovernanceETL:
    def __init__(self):
        self.conn   = None
        self.cur    = None

    def connect(self):
        log.info("Connecting to PostgreSQL...")
        self.conn = psycopg2.connect(**DB_CONFIG)
        self.cur  = self.conn.cursor()
        log.info("Connected ✓")

    def disconnect(self):
        if self.cur:  self.cur.close()
        if self.conn: self.conn.close()

    def _load(self, table, df, cols):
        if df.empty: return 0
        rows = [tuple(None if pd.isna(v) else v for v in r)
                for r in df[cols].itertuples(index=False)]
        ph   = ",".join(["%s"]*len(cols))
        self.cur.execute(f"DELETE FROM {table}")   # full refresh per run
        execute_values(self.cur, f"INSERT INTO {table} ({','.join(cols)}) VALUES %s", rows)
        self.conn.commit()
        log.info(f"  ✓ {table}: {len(rows):,} rows")
        return len(rows)

    def run(self):
        log.info("="*55)
        log.info("HC DQ GOVERNANCE ETL — STARTING")
        log.info("="*55)

        # Run engine
        engine = DQEngine(DATA_DIR)
        results, scores, profile, recon, impact, audit = engine.run()

        try:
            self.connect()

            # dq_runs
            self.cur.execute("""
                INSERT INTO dq_runs (run_id, run_time, status, total_tables, total_rules, total_issues)
                VALUES (%s, %s, 'Completed', %s, %s, %s)
                ON CONFLICT (run_id) DO NOTHING
            """, (engine.run_id, engine.run_time,
                  results["table_name"].nunique(), len(results),
                  int(results[results["status"]=="FAIL"]["failed_records"].sum())))
            self.conn.commit()

            self._load("dq_results",
                results[["run_id","run_time","table_name","rule_id","category","severity",
                          "description","total_records","failed_records","passed_records",
                          "pass_rate_pct","status"]],
                ["run_id","run_time","table_name","rule_id","category","severity",
                 "description","total_records","failed_records","passed_records",
                 "pass_rate_pct","status"])

            self._load("dq_scores",
                scores[["run_time","table_name","total_rules","passed_rules",
                         "failed_rules","dq_score","grade"]],
                ["run_time","table_name","total_rules","passed_rules",
                 "failed_rules","dq_score","grade"])

            self._load("data_profile",
                profile[["table_name","column_name","total_count","null_count","null_pct",
                          "unique_count","uniqueness_pct","is_numeric","min_value",
                          "max_value","mean_value","sample_values"]],
                ["table_name","column_name","total_count","null_count","null_pct",
                 "unique_count","uniqueness_pct","is_numeric","min_value",
                 "max_value","mean_value","sample_values"])

            self._load("reconciliation",
                recon[["run_time","table_name","source_count","loaded_count",
                        "delta","delta_pct","status"]],
                ["run_time","table_name","source_count","loaded_count",
                 "delta","delta_pct","status"])

            if not impact.empty:
                self._load("downstream_impact",
                    impact[["run_time","report","owner","refresh_cadence","criticality",
                             "affected_tables","total_issues","impact_level"]],
                    ["run_time","report","owner","refresh_cadence","criticality",
                     "affected_tables","total_issues","impact_level"])

            if not audit.empty:
                self._load("audit_log",
                    audit[["log_id","event_time","table_name","rule_id","event_type",
                            "severity","description","records_affected","action_taken","resolved"]],
                    ["log_id","event_time","table_name","rule_id","event_type",
                     "severity","description","records_affected","action_taken","resolved"])

        finally:
            self.disconnect()

        log.info("="*55)
        log.info("ETL COMPLETE")
        log.info("="*55)


if __name__ == "__main__":
    DQGovernanceETL().run()
