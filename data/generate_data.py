"""
generate_data.py
Generates synthetic healthcare source data WITH intentional quality issues
so the DQ pipeline has real problems to catch and report.
Tables: patients, encounters, lab_results, medications, claims
"""

import pandas as pd
import numpy as np
import random, os
from datetime import datetime, timedelta

random.seed(77)
np.random.seed(77)

OUT = os.path.dirname(__file__)

START = datetime(2022, 1, 1)
END   = datetime(2024, 12, 31)

def rdate(s=START, e=END):
    return s + timedelta(days=random.randint(0, (e - s).days))
def fmt(d): return d.strftime("%Y-%m-%d")

STATES       = ["NC","TX","CA","FL","NY","GA","OH","PA","IL","AZ"]
GENDERS      = ["M","F","Other"]
ETHNICITIES  = ["Hispanic","Non-Hispanic","Unknown"]
RACES        = ["White","Black","Asian","Other","Unknown"]
ENC_TYPES    = ["Inpatient","Outpatient","Emergency","Observation"]
DIAGNOSES    = ["E11.9","I10","J18.9","K21.0","M54.5","N18.3","Z79.4","F32.9","G43.909","C34.10"]
DISPOSITIONS = ["Discharged","Transferred","Expired","Left AMA","Admitted"]
LAB_TESTS    = [
    ("Hemoglobin A1c",   "%",          4.0,  14.0, 4.0,  5.6),
    ("Serum Creatinine", "mg/dL",      0.5,   5.0, 0.5,  1.2),
    ("eGFR",             "mL/min",    15.0, 120.0,60.0,120.0),
    ("Fasting Glucose",  "mg/dL",     50.0, 500.0,70.0, 99.0),
    ("LDL Cholesterol",  "mg/dL",     20.0, 300.0,20.0,100.0),
    ("Hemoglobin",       "g/dL",       4.0,  20.0,12.0, 17.5),
    ("WBC Count",        "K/uL",       1.0,  30.0, 4.5, 11.0),
    ("Platelet Count",   "K/uL",      50.0, 800.0,150.0,400.0),
]
MEDS = [
    ("Metformin","metformin","Diabetes","500mg","Oral"),
    ("Lisinopril","lisinopril","Hypertension","10mg","Oral"),
    ("Atorvastatin","atorvastatin","Hyperlipidemia","20mg","Oral"),
    ("Amlodipine","amlodipine","Hypertension","5mg","Oral"),
    ("Omeprazole","omeprazole","GERD","20mg","Oral"),
    ("Levothyroxine","levothyroxine","Hypothyroidism","50mcg","Oral"),
    ("Gabapentin","gabapentin","Neuropathy","300mg","Oral"),
    ("Sertraline","sertraline","Depression","50mg","Oral"),
]

# ── patients (800) ────────────────────────────────────────────────────────────
n = 800
patient_ids = [f"PT{i:06d}" for i in range(1, n+1)]
dob_list    = [fmt(rdate(datetime(1940,1,1), datetime(2005,1,1))) for _ in range(n)]

patients = pd.DataFrame({
    "patient_id":       patient_ids,
    "first_name":       [f"FirstName{i}" for i in range(1, n+1)],
    "last_name":        [f"LastName{i}"  for i in range(1, n+1)],
    "date_of_birth":    dob_list,
    "gender":           np.random.choice(GENDERS, n, p=[0.48,0.49,0.03]),
    "race":             np.random.choice(RACES, n),
    "ethnicity":        np.random.choice(ETHNICITIES, n),
    "state":            np.random.choice(STATES, n),
    "zip_code":         [f"{random.randint(10000,99999)}" for _ in range(n)],
    "phone":            [f"704-{random.randint(100,999)}-{random.randint(1000,9999)}" for _ in range(n)],
    "email":            [f"patient{i}@email.com" if random.random()>0.1 else None for i in range(1,n+1)],
    "insurance_type":   np.random.choice(["Commercial","Medicare","Medicaid","Self-Pay"], n, p=[0.5,0.25,0.2,0.05]),
    "created_at":       [fmt(rdate(START, START+timedelta(days=60))) for _ in range(n)],
})

# ── inject quality issues into patients ───────────────────────────────────────
# Nulls in required fields
patients.loc[patients.sample(frac=0.04).index, "gender"]        = None
patients.loc[patients.sample(frac=0.03).index, "date_of_birth"] = None
patients.loc[patients.sample(frac=0.05).index, "state"]         = None
# Invalid values
patients.loc[patients.sample(frac=0.02).index, "gender"]        = "UNKNOWN"
patients.loc[patients.sample(frac=0.02).index, "zip_code"]      = "0000"
# Duplicates (5 duped patient records)
dupe_rows = patients.sample(5).copy()
dupe_rows["patient_id"] = [f"PT{i:06d}" for i in range(n+1, n+6)]
patients = pd.concat([patients, dupe_rows], ignore_index=True)
patients.to_csv(f"{OUT}/patients.csv", index=False)

# ── encounters (3000) ─────────────────────────────────────────────────────────
n_enc = 3000
enc_records = []
for i in range(1, n_enc+1):
    pat    = random.choice(patient_ids)
    adm_d  = rdate()
    los    = random.randint(0, 14)
    dis_d  = adm_d + timedelta(days=los)
    enc_records.append({
        "encounter_id":      f"ENC{i:07d}",
        "patient_id":        pat,
        "encounter_type":    random.choice(ENC_TYPES),
        "admission_date":    fmt(adm_d),
        "discharge_date":    fmt(dis_d) if random.random()>0.03 else None,
        "primary_diagnosis": random.choice(DIAGNOSES),
        "attending_provider":f"PRV{random.randint(1,50):04d}",
        "facility_id":       f"FAC{random.randint(1,10):03d}",
        "disposition":       random.choice(DISPOSITIONS),
        "length_of_stay":    los,
        "total_charges_usd": round(random.uniform(500, 85000), 2),
        "created_at":        fmt(adm_d),
    })

encounters = pd.DataFrame(enc_records)
# Inject issues
encounters.loc[encounters.sample(frac=0.03).index, "primary_diagnosis"] = None
encounters.loc[encounters.sample(frac=0.02).index, "total_charges_usd"] = -999
encounters.loc[encounters.sample(frac=0.01).index, "admission_date"]    = None
# Future dates
encounters.loc[encounters.sample(5).index, "discharge_date"] = "2027-01-01"
# Invalid patient FK
for idx in encounters.sample(10).index:
    encounters.loc[idx, "patient_id"] = "PT999999"
encounters.to_csv(f"{OUT}/encounters.csv", index=False)

# ── lab results (6000) ────────────────────────────────────────────────────────
lab_records = []
for i in range(1, 6001):
    pat       = random.choice(patient_ids)
    test_name, unit, lo, hi, ref_lo, ref_hi = random.choice(LAB_TESTS)
    value     = round(random.uniform(lo * 0.8, hi * 1.1), 2)
    coll_d    = rdate()
    lab_records.append({
        "lab_id":           f"LAB{i:07d}",
        "patient_id":       pat,
        "test_name":        test_name,
        "result_value":     value,
        "unit":             unit,
        "reference_low":    ref_lo,
        "reference_high":   ref_hi,
        "is_abnormal":      not (ref_lo <= value <= ref_hi),
        "collection_date":  fmt(coll_d),
        "result_date":      fmt(coll_d + timedelta(days=random.randint(0,3))),
        "ordering_provider":f"PRV{random.randint(1,50):04d}",
        "status":           random.choice(["Final","Preliminary","Corrected","Cancelled"]),
        "created_at":       fmt(coll_d),
    })

labs = pd.DataFrame(lab_records)
# Inject issues
labs.loc[labs.sample(frac=0.03).index, "result_value"] = None
labs.loc[labs.sample(frac=0.02).index, "result_value"] = -99999   # out of range
labs.loc[labs.sample(frac=0.01).index, "unit"]         = None
labs.loc[labs.sample(10).index, "patient_id"]          = "PT999999"  # broken FK
labs.to_csv(f"{OUT}/lab_results.csv", index=False)

# ── medications (4000) ────────────────────────────────────────────────────────
med_records = []
for i in range(1, 4001):
    pat    = random.choice(patient_ids)
    med    = random.choice(MEDS)
    start  = rdate()
    end    = start + timedelta(days=random.randint(30,365)) if random.random()>0.2 else None
    med_records.append({
        "med_id":           f"MED{i:07d}",
        "patient_id":       pat,
        "brand_name":       med[0],
        "generic_name":     med[1],
        "indication":       med[2],
        "dose":             med[3],
        "route":            med[4],
        "frequency":        random.choice(["Daily","BID","TID","QID","Weekly"]),
        "start_date":       fmt(start),
        "end_date":         fmt(end) if end else None,
        "prescriber_id":    f"PRV{random.randint(1,50):04d}",
        "is_active":        end is None,
        "created_at":       fmt(start),
    })

meds = pd.DataFrame(med_records)
# Inject issues
meds.loc[meds.sample(frac=0.03).index, "dose"]       = None
meds.loc[meds.sample(frac=0.02).index, "start_date"] = None
# End before start
bad_idx = meds.sample(15).index
meds.loc[bad_idx, "end_date"] = "2021-01-01"
meds.to_csv(f"{OUT}/medications.csv", index=False)

print("✅ Generated source data WITH quality issues:")
for name, df in [("patients",patients),("encounters",encounters),
                 ("lab_results",labs),("medications",meds)]:
    print(f"   {name+'.csv':<25} → {len(df):,} rows")
