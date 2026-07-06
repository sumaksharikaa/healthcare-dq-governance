"""
app.py — Healthcare Data Quality & Governance Dashboard
Run: streamlit run app/app.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from engine.dq_engine import DQEngine

st.set_page_config(
    page_title="HC Data Quality & Governance",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

# ── colours & constants ───────────────────────────────────────────────────────
SEV_COLORS   = {"Critical":"#e74c3c","High":"#e67e22","Medium":"#f1c40f","Low":"#2ecc71"}
GRADE_COLORS = {"A":"#2ecc71","B":"#27ae60","C":"#f39c12","D":"#e67e22","F":"#e74c3c"}
CAT_COLORS   = {"Completeness":"#3498db","Validity":"#e74c3c","Uniqueness":"#9b59b6",
                "Referential":"#e67e22","Timeliness":"#1abc9c","Consistency":"#f39c12"}

# ── load / run engine ─────────────────────────────────────────────────────────
@st.cache_data(show_spinner="Running DQ Engine...")
def run_engine():
    engine = DQEngine(DATA_DIR)
    engine.load()
    engine.run_rules()
    results   = pd.DataFrame(engine.results)
    scores    = engine.score()
    profile   = engine.profile()
    recon     = engine.reconcile({"patients":800,"encounters":3000,
                                   "lab_results":6000,"medications":4000})
    impact    = engine.downstream_impact()
    audit     = engine.audit_log()
    return results, scores, profile, recon, impact, audit

results, scores, profile, recon, impact, audit = run_engine()

# ── sidebar ───────────────────────────────────────────────────────────────────
st.sidebar.title("🏥 DQ Governance")
st.sidebar.markdown("**Run ID:** `RUN_LATEST`")
st.sidebar.markdown(f"**Tables scanned:** {results['table_name'].nunique()}")
st.sidebar.markdown(f"**Total rules:** {len(results)}")
total_issues = results[results["status"]=="FAIL"]["failed_records"].sum()
st.sidebar.markdown(f"**Total issues:** {total_issues:,}")
st.sidebar.divider()
sel_tables   = st.sidebar.multiselect("Filter Table",
    results["table_name"].unique().tolist(),
    default=results["table_name"].unique().tolist())
sel_severity = st.sidebar.multiselect("Filter Severity",
    ["Critical","High","Medium","Low"], default=["Critical","High","Medium","Low"])

fres = results[results["table_name"].isin(sel_tables) & results["severity"].isin(sel_severity)]

# ── header ────────────────────────────────────────────────────────────────────
st.title("🏥 Healthcare Data Quality & Governance")
st.caption("Automated DQ rules engine · Data profiling · Audit trail · Downstream impact · Reconciliation")
st.divider()

# ── top KPI cards ─────────────────────────────────────────────────────────────
k1,k2,k3,k4,k5,k6 = st.columns(6)
overall_score = scores["dq_score"].mean()
critical_fails= results[(results["severity"]=="Critical")&(results["status"]=="FAIL")]["failed_records"].sum()
pass_rate     = (results["status"]=="PASS").mean()*100
open_issues   = len(audit[audit["resolved"]==False])
affected_rpts = len(impact)

k1.metric("Overall DQ Score",      f"{overall_score:.1f}%")
k2.metric("Total Issues Found",    f"{total_issues:,}")
k3.metric("Critical Issues",       f"{critical_fails:,}")
k4.metric("Rule Pass Rate",        f"{pass_rate:.1f}%")
k5.metric("Open Audit Issues",     f"{open_issues}")
k6.metric("Reports Affected",      f"{affected_rpts}")
st.divider()

# ── tabs ──────────────────────────────────────────────────────────────────────
tab1,tab2,tab3,tab4,tab5,tab6 = st.tabs([
    "📊 DQ Scorecard","🔍 Issue Drill-Down",
    "📈 Trend & Heatmap","🔗 Downstream Impact",
    "📋 Data Profile","📜 Audit Log"
])

# ══ TAB 1 — DQ SCORECARD ═════════════════════════════════════════════════════
with tab1:
    st.subheader("Data Quality Scorecard by Table")
    c1,c2 = st.columns([1,2])

    with c1:
        # Gauge per table
        for _, row in scores.iterrows():
            fig = go.Figure(go.Indicator(
                mode="gauge+number",
                value=row["dq_score"],
                title={"text": f"{row['table_name'].replace('_',' ').title()}<br><span style='font-size:0.8em'>Grade: {row['grade']}</span>"},
                gauge={
                    "axis":  {"range":[0,100]},
                    "bar":   {"color": GRADE_COLORS.get(row["grade"],"#95a5a6")},
                    "steps": [{"range":[0,60],"color":"#fadbd8"},
                              {"range":[60,80],"color":"#fdebd0"},
                              {"range":[80,100],"color":"#d5f5e3"}],
                    "threshold":{"line":{"color":"#2c3e50","width":3},"value":80}
                },
                number={"suffix":"%","font":{"size":22}},
            ))
            fig.update_layout(height=200, margin=dict(t=50,b=10,l=20,r=20))
            st.plotly_chart(fig, use_container_width=True)

    with c2:
        # Waterfall — total records through pipeline per table
        st.subheader("Records: Source → Loaded → Passed → Failed")
        for _, row in recon.iterrows():
            table  = row["table_name"]
            src    = row["source_count"]
            loaded = row["loaded_count"]
            srow   = scores[scores["table_name"]==table]
            if srow.empty: continue
            passed_pct = srow.iloc[0]["passed_rules"]/srow.iloc[0]["total_rules"]
            passed_rec = int(loaded * passed_pct)
            failed_rec = loaded - passed_rec

            fig = go.Figure(go.Waterfall(
                orientation="h",
                measure=["absolute","relative","relative"],
                x=[src, passed_rec-src, failed_rec],
                base=0,
                y=["Source","Passed Rules","Failed Rules"],
                connector={"line":{"color":"#bdc3c7"}},
                increasing={"marker":{"color":"#2ecc71"}},
                decreasing={"marker":{"color":"#e74c3c"}},
                totals={"marker":{"color":"#3498db"}},
            ))
            fig.update_layout(title=table.replace("_"," ").title(),
                              height=160, margin=dict(t=35,b=5,l=5,r=5),
                              showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

    # Summary table
    st.subheader("Rule Summary by Table")
    summary = (fres.groupby(["table_name","status"])
               .size().unstack(fill_value=0).reset_index())
    if "PASS" not in summary.columns: summary["PASS"]=0
    if "FAIL" not in summary.columns: summary["FAIL"]=0
    summary = summary.merge(scores[["table_name","dq_score","grade"]], on="table_name")
    st.dataframe(summary.rename(columns={"table_name":"Table","PASS":"✅ Pass",
                                          "FAIL":"❌ Fail","dq_score":"DQ Score","grade":"Grade"}),
                 use_container_width=True, hide_index=True)

# ══ TAB 2 — ISSUE DRILL-DOWN ═════════════════════════════════════════════════
with tab2:
    c1,c2 = st.columns(2)
    with c1:
        st.subheader("Issues by Severity")
        sev = (fres[fres["status"]=="FAIL"]
               .groupby("severity")["failed_records"].sum().reset_index()
               .sort_values("failed_records",ascending=False))
        sev["color"] = sev["severity"].map(SEV_COLORS)
        fig = px.bar(sev, x="severity", y="failed_records",
                     color="severity", color_discrete_map=SEV_COLORS,
                     labels={"failed_records":"Issues","severity":"Severity"})
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.subheader("Issues by DQ Category")
        cat = (fres[fres["status"]=="FAIL"]
               .groupby("category")["failed_records"].sum().reset_index())
        fig2 = px.pie(cat, values="failed_records", names="category", hole=0.45,
                      color="category", color_discrete_map=CAT_COLORS)
        fig2.update_traces(textinfo="label+percent")
        st.plotly_chart(fig2, use_container_width=True)

    st.subheader("All Failed Rules — Drill-Down")
    failed = fres[fres["status"]=="FAIL"][
        ["rule_id","table_name","category","severity","description","failed_records","pass_rate_pct"]
    ].sort_values(["severity","failed_records"],
                  key=lambda x: x.map({"Critical":0,"High":1,"Medium":2,"Low":3}) if x.name=="severity" else x,
                  ascending=[True,False])

    def sev_color(val):
        return f"color: {SEV_COLORS.get(val,'black')}; font-weight:bold"
    st.dataframe(
        failed.rename(columns={"rule_id":"Rule","table_name":"Table","category":"Category",
                                "severity":"Severity","description":"Description",
                                "failed_records":"Issues","pass_rate_pct":"Pass Rate %"})
              .style.map(sev_color, subset=["Severity"]),
        use_container_width=True, hide_index=True
    )

# ══ TAB 3 — TREND & HEATMAP ══════════════════════════════════════════════════
with tab3:
    st.subheader("DQ Score Heatmap — Table × Category")
    heat_data = (fres.groupby(["table_name","category"])
                 .apply(lambda x: round((x["status"]=="PASS").mean()*100,1))
                 .reset_index(name="pass_rate"))
    heat_pivot = heat_data.pivot(index="table_name", columns="category", values="pass_rate").fillna(100)
    fig = px.imshow(heat_pivot,
                    color_continuous_scale=["#e74c3c","#f39c12","#2ecc71"],
                    zmin=0, zmax=100, aspect="auto",
                    labels={"color":"Pass Rate %"},
                    text_auto=True)
    fig.update_layout(height=300, xaxis_title="DQ Category", yaxis_title="Table")
    st.plotly_chart(fig, use_container_width=True)

    c1,c2 = st.columns(2)
    with c1:
        st.subheader("Issue Volume by Table & Severity")
        sev_table = (fres[fres["status"]=="FAIL"]
                     .groupby(["table_name","severity"])["failed_records"]
                     .sum().reset_index())
        fig2 = px.bar(sev_table, x="table_name", y="failed_records",
                      color="severity", color_discrete_map=SEV_COLORS,
                      barmode="stack",
                      labels={"failed_records":"Issues","table_name":"Table","severity":"Severity"})
        fig2.update_layout(xaxis_title=None)
        st.plotly_chart(fig2, use_container_width=True)

    with c2:
        st.subheader("Data Quality Radar — Table Dimensions")
        categories_list = ["Completeness","Validity","Uniqueness","Referential"]
        radar_data = []
        for table in fres["table_name"].unique():
            row_vals = []
            tdf = fres[fres["table_name"]==table]
            for cat in categories_list:
                cdf = tdf[tdf["category"]==cat]
                if len(cdf)==0:
                    row_vals.append(100.0)
                else:
                    row_vals.append(round((cdf["status"]=="PASS").mean()*100,1))
            radar_data.append({"table":table, "values":row_vals})

        fig3 = go.Figure()
        colors_r = ["#3498db","#e74c3c","#2ecc71","#9b59b6"]
        for i, rd in enumerate(radar_data):
            fig3.add_trace(go.Scatterpolar(
                r=rd["values"]+[rd["values"][0]],
                theta=categories_list+[categories_list[0]],
                fill="toself", name=rd["table"],
                line_color=colors_r[i % len(colors_r)],
                opacity=0.6,
            ))
        fig3.update_layout(polar=dict(radialaxis=dict(range=[0,100])),
                           legend_title="Table", height=380)
        st.plotly_chart(fig3, use_container_width=True)

    st.subheader("Reconciliation — Source vs Loaded Record Counts")
    c1,c2 = st.columns(2)
    with c1:
        fig4 = px.bar(recon, x="table_name",
                      y=["source_count","loaded_count"],
                      barmode="group",
                      color_discrete_sequence=["#3498db","#e67e22"],
                      labels={"value":"Records","table_name":"Table","variable":"Type"})
        fig4.update_layout(xaxis_title=None, legend_title="Count")
        st.plotly_chart(fig4, use_container_width=True)
    with c2:
        recon_display = recon[["table_name","source_count","loaded_count","delta","delta_pct","status"]].copy()
        recon_display["status_icon"] = recon_display["status"].map({"MATCH":"✅ MATCH","MISMATCH":"⚠️ MISMATCH"})
        st.dataframe(recon_display.drop(columns="status")
                     .rename(columns={"table_name":"Table","source_count":"Source",
                                       "loaded_count":"Loaded","delta":"Delta",
                                       "delta_pct":"Delta %","status_icon":"Status"}),
                     use_container_width=True, hide_index=True)

# ══ TAB 4 — DOWNSTREAM IMPACT ════════════════════════════════════════════════
with tab4:
    st.subheader("🔗 Reports & Dashboards Affected by DQ Issues")

    c1,c2 = st.columns(2)
    with c1:
        crit_map = {"Critical":4,"High":3,"Medium":2,"Low":1}
        fig = px.scatter(impact,
                         x="total_issues", y="report",
                         size="total_issues",
                         color="criticality",
                         color_discrete_map={"Critical":"#e74c3c","High":"#e67e22","Medium":"#f1c40f"},
                         hover_data=["owner","refresh_cadence","affected_tables"],
                         labels={"total_issues":"Issues Affecting Report","report":"Report"})
        fig.update_layout(height=420, yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.subheader("Impact by Criticality")
        crit_cnt = impact["criticality"].value_counts().reset_index()
        crit_cnt.columns = ["Criticality","Count"]
        fig2 = px.pie(crit_cnt, values="Count", names="Criticality", hole=0.45,
                      color="Criticality",
                      color_discrete_map={"Critical":"#e74c3c","High":"#e67e22","Medium":"#f1c40f"})
        st.plotly_chart(fig2, use_container_width=True)

    st.dataframe(
        impact[["report","owner","criticality","refresh_cadence","affected_tables","total_issues","impact_level"]]
        .rename(columns={"report":"Report","owner":"Owner","criticality":"Criticality",
                          "refresh_cadence":"Refresh","affected_tables":"Affected Tables",
                          "total_issues":"Issues","impact_level":"Impact"}),
        use_container_width=True, hide_index=True
    )

# ══ TAB 5 — DATA PROFILE ═════════════════════════════════════════════════════
with tab5:
    st.subheader("📋 Column-Level Data Profile")
    sel_table_p = st.selectbox("Select Table", profile["table_name"].unique())
    prof_filt   = profile[profile["table_name"]==sel_table_p]

    c1,c2 = st.columns(2)
    with c1:
        st.subheader("Null % by Column")
        null_df = prof_filt[["column_name","null_pct"]].sort_values("null_pct",ascending=False)
        fig = px.bar(null_df, x="null_pct", y="column_name", orientation="h",
                     color="null_pct",
                     color_continuous_scale=["#2ecc71","#f39c12","#e74c3c"],
                     labels={"null_pct":"Null %","column_name":"Column"})
        fig.update_layout(yaxis=dict(autorange="reversed"), coloraxis_showscale=False)
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.subheader("Uniqueness % by Column")
        uniq_df = prof_filt[["column_name","uniqueness_pct"]].sort_values("uniqueness_pct",ascending=False)
        fig2 = px.bar(uniq_df, x="uniqueness_pct", y="column_name", orientation="h",
                      color="uniqueness_pct",
                      color_continuous_scale=["#e74c3c","#f39c12","#2ecc71"],
                      labels={"uniqueness_pct":"Uniqueness %","column_name":"Column"})
        fig2.update_layout(yaxis=dict(autorange="reversed"), coloraxis_showscale=False)
        st.plotly_chart(fig2, use_container_width=True)

    st.subheader("Full Profile Table")
    display_cols = ["column_name","total_count","null_count","null_pct",
                    "unique_count","uniqueness_pct","min_value","max_value","mean_value"]
    st.dataframe(prof_filt[display_cols].rename(columns={
        "column_name":"Column","total_count":"Total","null_count":"Nulls",
        "null_pct":"Null %","unique_count":"Unique","uniqueness_pct":"Uniqueness %",
        "min_value":"Min","max_value":"Max","mean_value":"Mean"}),
        use_container_width=True, hide_index=True)

# ══ TAB 6 — AUDIT LOG ════════════════════════════════════════════════════════
with tab6:
    st.subheader("📜 Audit Log — DQ Violations & Governance Events")

    c1,c2,c3 = st.columns(3)
    c1.metric("Total Log Entries",   len(audit))
    c2.metric("Unresolved Issues",   (audit["resolved"]==False).sum())
    c3.metric("Critical Unresolved", ((audit["resolved"]==False)&(audit["severity"]=="Critical")).sum())

    c1,c2 = st.columns(2)
    with c1:
        st.subheader("Issues by Table & Severity")
        aud_sev = (audit.groupby(["table_name","severity"])
                   .size().reset_index(name="count"))
        fig = px.bar(aud_sev, x="table_name", y="count", color="severity",
                     color_discrete_map=SEV_COLORS, barmode="stack",
                     labels={"count":"Violations","table_name":"Table"})
        fig.update_layout(xaxis_title=None)
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.subheader("Records Affected by Severity")
        aud_rec = (audit.groupby("severity")["records_affected"]
                   .sum().reset_index().sort_values("records_affected",ascending=False))
        fig2 = px.bar(aud_rec, x="severity", y="records_affected",
                      color="severity", color_discrete_map=SEV_COLORS,
                      labels={"records_affected":"Records Affected","severity":"Severity"})
        fig2.update_layout(showlegend=False)
        st.plotly_chart(fig2, use_container_width=True)

    st.subheader("Audit Log Detail")
    st.dataframe(
        audit[["log_id","table_name","rule_id","severity","description",
               "records_affected","action_taken","resolved"]]
        .rename(columns={"log_id":"Log ID","table_name":"Table","rule_id":"Rule",
                          "severity":"Severity","description":"Description",
                          "records_affected":"Records","action_taken":"Action","resolved":"Resolved"})
        .style.map(sev_color, subset=["Severity"]),
        use_container_width=True, hide_index=True
    )

# ── footer ────────────────────────────────────────────────────────────────────
st.divider()
st.caption("Healthcare Data Quality & Governance · PostgreSQL · Python Rules Engine · Streamlit · sumaksharika.com")
