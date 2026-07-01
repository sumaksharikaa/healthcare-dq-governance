-- =============================================================================
-- schema.sql
-- Healthcare Data Quality & Governance — PostgreSQL Schema
-- =============================================================================

-- ── extensions ────────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ── drop existing ─────────────────────────────────────────────────────────────
DROP TABLE IF EXISTS downstream_impact  CASCADE;
DROP TABLE IF EXISTS audit_log          CASCADE;
DROP TABLE IF EXISTS reconciliation     CASCADE;
DROP TABLE IF EXISTS data_profile       CASCADE;
DROP TABLE IF EXISTS dq_scores          CASCADE;
DROP TABLE IF EXISTS dq_results         CASCADE;
DROP TABLE IF EXISTS dq_rule_registry   CASCADE;
DROP TABLE IF EXISTS dq_runs            CASCADE;

-- =============================================================================
-- DQ RUNS — one record per pipeline execution
-- =============================================================================
CREATE TABLE dq_runs (
    run_id          VARCHAR(30)     PRIMARY KEY,
    run_time        TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    triggered_by    VARCHAR(50)     DEFAULT 'automated',
    status          VARCHAR(20)     CHECK (status IN ('Running','Completed','Failed')),
    total_tables    SMALLINT,
    total_rules     SMALLINT,
    total_issues    INT,
    notes           TEXT
);

-- =============================================================================
-- RULE REGISTRY — master list of all DQ rules
-- =============================================================================
CREATE TABLE dq_rule_registry (
    rule_id         VARCHAR(10)     PRIMARY KEY,
    table_name      VARCHAR(50)     NOT NULL,
    category        VARCHAR(30)     NOT NULL CHECK (category IN
                    ('Completeness','Validity','Uniqueness','Referential','Timeliness','Consistency')),
    severity        VARCHAR(10)     NOT NULL CHECK (severity IN ('Critical','High','Medium','Low')),
    description     TEXT            NOT NULL,
    remediation     TEXT,
    is_active       BOOLEAN         DEFAULT TRUE,
    created_at      TIMESTAMP       DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================================
-- DQ RESULTS — one record per rule per run
-- =============================================================================
CREATE TABLE dq_results (
    result_id       SERIAL          PRIMARY KEY,
    run_id          VARCHAR(30)     NOT NULL REFERENCES dq_runs(run_id),
    run_time        TIMESTAMP       NOT NULL,
    table_name      VARCHAR(50)     NOT NULL,
    rule_id         VARCHAR(10)     NOT NULL,
    category        VARCHAR(30)     NOT NULL,
    severity        VARCHAR(10)     NOT NULL,
    description     TEXT,
    total_records   INT             NOT NULL,
    failed_records  INT             NOT NULL DEFAULT 0,
    passed_records  INT             NOT NULL DEFAULT 0,
    pass_rate_pct   NUMERIC(5,2),
    status          VARCHAR(10)     CHECK (status IN ('PASS','FAIL')),
    created_at      TIMESTAMP       DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_dq_results_run      ON dq_results(run_id);
CREATE INDEX idx_dq_results_table    ON dq_results(table_name);
CREATE INDEX idx_dq_results_severity ON dq_results(severity, status);

-- =============================================================================
-- DQ SCORES — weighted quality score per table per run
-- =============================================================================
CREATE TABLE dq_scores (
    score_id        SERIAL          PRIMARY KEY,
    run_id          VARCHAR(30)     REFERENCES dq_runs(run_id),
    run_time        TIMESTAMP,
    table_name      VARCHAR(50)     NOT NULL,
    total_rules     SMALLINT,
    passed_rules    SMALLINT,
    failed_rules    SMALLINT,
    dq_score        NUMERIC(5,1),
    grade           CHAR(1)         CHECK (grade IN ('A','B','C','D','F')),
    created_at      TIMESTAMP       DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_scores_table ON dq_scores(table_name, run_time);

-- =============================================================================
-- DATA PROFILE — column-level completeness & uniqueness stats
-- =============================================================================
CREATE TABLE data_profile (
    profile_id      SERIAL          PRIMARY KEY,
    run_time        TIMESTAMP       DEFAULT CURRENT_TIMESTAMP,
    table_name      VARCHAR(50)     NOT NULL,
    column_name     VARCHAR(100)    NOT NULL,
    total_count     INT,
    null_count      INT,
    null_pct        NUMERIC(5,2),
    unique_count    INT,
    uniqueness_pct  NUMERIC(5,2),
    is_numeric      BOOLEAN,
    min_value       VARCHAR(50),
    max_value       VARCHAR(50),
    mean_value      NUMERIC(15,4),
    sample_values   TEXT
);

CREATE INDEX idx_profile_table ON data_profile(table_name);

-- =============================================================================
-- RECONCILIATION — source vs loaded record counts
-- =============================================================================
CREATE TABLE reconciliation (
    recon_id        SERIAL          PRIMARY KEY,
    run_time        TIMESTAMP       NOT NULL,
    table_name      VARCHAR(50)     NOT NULL,
    source_count    INT             NOT NULL,
    loaded_count    INT             NOT NULL,
    delta           INT,
    delta_pct       NUMERIC(6,2),
    status          VARCHAR(10)     CHECK (status IN ('MATCH','MISMATCH')),
    notes           TEXT
);

CREATE INDEX idx_recon_table ON reconciliation(table_name, run_time);

-- =============================================================================
-- AUDIT LOG — all DQ violations and governance events
-- =============================================================================
CREATE TABLE audit_log (
    log_id          VARCHAR(12)     PRIMARY KEY,
    event_time      TIMESTAMP       NOT NULL,
    table_name      VARCHAR(50)     NOT NULL,
    rule_id         VARCHAR(10),
    event_type      VARCHAR(30)     NOT NULL,
    severity        VARCHAR(10),
    description     TEXT,
    records_affected INT            DEFAULT 0,
    action_taken    TEXT,
    resolved        BOOLEAN         DEFAULT FALSE,
    resolved_by     VARCHAR(50),
    resolved_at     TIMESTAMP,
    created_at      TIMESTAMP       DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_table    ON audit_log(table_name);
CREATE INDEX idx_audit_severity ON audit_log(severity);
CREATE INDEX idx_audit_resolved ON audit_log(resolved);
CREATE INDEX idx_audit_time     ON audit_log(event_time);

-- =============================================================================
-- DOWNSTREAM IMPACT — reports/dashboards affected by DQ issues
-- =============================================================================
CREATE TABLE downstream_impact (
    impact_id       SERIAL          PRIMARY KEY,
    run_time        TIMESTAMP       NOT NULL,
    report          VARCHAR(100)    NOT NULL,
    owner           VARCHAR(50),
    refresh_cadence VARCHAR(20),
    criticality     VARCHAR(20),
    affected_tables TEXT,
    total_issues    INT,
    impact_level    VARCHAR(20),
    notified        BOOLEAN         DEFAULT FALSE,
    created_at      TIMESTAMP       DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================================
-- VIEW: Latest DQ scores per table
-- =============================================================================
CREATE OR REPLACE VIEW vw_latest_dq_scores AS
SELECT DISTINCT ON (table_name)
    table_name, dq_score, grade, total_rules,
    passed_rules, failed_rules, run_time
FROM dq_scores
ORDER BY table_name, run_time DESC;

-- =============================================================================
-- VIEW: Open audit issues (unresolved Critical/High)
-- =============================================================================
CREATE OR REPLACE VIEW vw_open_critical_issues AS
SELECT
    log_id, table_name, rule_id, severity,
    description, records_affected, action_taken, event_time
FROM audit_log
WHERE resolved = FALSE
  AND severity IN ('Critical','High')
ORDER BY
    CASE severity WHEN 'Critical' THEN 1 WHEN 'High' THEN 2 END,
    records_affected DESC;
