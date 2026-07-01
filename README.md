# 🏥 Healthcare Data Quality & Governance Pipeline

[![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)](https://python.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-blue?logo=postgresql)](https://postgresql.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.35-red?logo=streamlit)](https://streamlit.io)
[![Plotly](https://img.shields.io/badge/Plotly-5.22-purple?logo=plotly)](https://plotly.com)

An enterprise-grade **Healthcare Data Quality & Governance** pipeline with a configurable rules engine, data profiling, audit trail, reconciliation reporting, and downstream impact assessment. Designed to mirror what a real-world health system data governance team would build.

---

## 🗂️ Project Structure

```
healthcare-dq-governance/
├── data/
│   └── generate_data.py         # Synthetic healthcare data WITH injected quality issues
├── engine/
│   └── dq_engine.py             # Configurable DQ rules engine (21 rules across 4 tables)
├── sql/
│   └── schema.sql               # PostgreSQL governance warehouse schema + views
├── etl/
│   └── etl_pipeline.py          # ETL: Run engine → load results into PostgreSQL
├── app/
│   └── app.py                   # Streamlit dashboard (6 tabs, 15+ visualizations)
├── requirements.txt
└── README.md
```

---

## 🏗️ Architecture

```
Source Data (CSV)
       │
       ▼
┌──────────────────────┐
│   DQ Rules Engine    │  ← 21 configurable rules
│  engine/dq_engine.py │    5 categories, 4 severities
└──────┬───────────────┘
       │ produces
       ▼
┌──────────────────────────────────────────────┐
│              Output Artifacts                │
│  dq_results  · dq_scores  · data_profile    │
│  reconciliation · audit_log · impact_report  │
└──────┬───────────────────────────────────────┘
       │
       ▼
┌──────────────────────┐       ┌───────────────────────┐
│  PostgreSQL Warehouse │       │  Streamlit Dashboard  │
│  (governance schema)  │──────►│  6 tabs · 15+ charts  │
└──────────────────────┘       └───────────────────────┘
```

---

## 📊 Dashboard — 6 Tabs, 15+ Visualizations

| Tab | Visualizations |
|---|---|
| **📊 DQ Scorecard** | Gauge per table · Waterfall (source→passed→failed) · Summary table |
| **🔍 Issue Drill-Down** | Bar by severity · Pie by category · Failed rules detail table |
| **📈 Trend & Heatmap** | DQ heatmap (table × category) · Stacked bar by severity · Radar chart · Reconciliation bar |
| **🔗 Downstream Impact** | Bubble chart (reports × issues) · Criticality pie · Impact table |
| **📋 Data Profile** | Null % bar · Uniqueness % bar · Full column profile table |
| **📜 Audit Log** | Violations by table/severity · Records affected bar · Audit detail table |

---

## 🔑 Key Technical Concepts

| Concept | Implementation |
|---|---|
| **Rules Engine** | 21 rules across Completeness, Validity, Uniqueness, Referential, Timeliness |
| **Severity Weighting** | Critical×4 · High×3 · Medium×2 · Low×1 → weighted DQ score |
| **Data Profiling** | Null %, uniqueness %, min/max/mean per column across all tables |
| **Reconciliation** | Source vs loaded record count comparison with delta % |
| **Audit Trail** | Full violation log with action taken, resolved status, record counts |
| **Downstream Impact** | Registry of 7 reports/dashboards mapped to source tables |
| **PostgreSQL Views** | `vw_latest_dq_scores` · `vw_open_critical_issues` |
| **Cross-table Checks** | Referential integrity between encounters/labs and patient master |

---

## ⚙️ Setup & Run

```bash
git clone https://github.com/sumaksharikaa/healthcare-dq-governance.git
cd healthcare-dq-governance
pip install -r requirements.txt

# Generate source data with injected quality issues
python data/generate_data.py

# Run DQ engine standalone (no DB needed)
python engine/dq_engine.py

# Launch dashboard (runs engine automatically)
streamlit run app/app.py

# Optional: Load into PostgreSQL
export DB_HOST=localhost DB_USER=postgres DB_PASSWORD=your_pw DB_NAME=hc_dq_db
psql -d hc_dq_db -f sql/schema.sql
python etl/etl_pipeline.py
```

---

## 📈 Sample DQ Results

| Table | Rules | Issues Found | DQ Score |
|---|---|---|---|
| patients | 9 | ~85 | ~30% (intentional issues) |
| encounters | 9 | ~210 | ~48% |
| lab_results | 7 | ~580 | ~41% |
| medications | 5 | ~120 | ~40% |

**Downstream reports affected:** 7 of 7 (all reports impacted due to cross-table issues)

---

## 🔗 Related Projects

- [Specialty Pharmacy Claims Analytics](https://github.com/sumaksharikaa/sp-claims-analytics)
- [Drug Utilization & Formulary Analytics](https://github.com/sumaksharikaa/drug-utilization-analytics)
- [Pharmacy Readmission Risk Predictor](https://github.com/sumaksharikaa/pharmacy-readmission-risk)

---

*Built by [Sumaksharika Nainavarapu](https://sumaksharika.com) · B.S. Pharmacy · M.S. Health Informatics & Analytics*
