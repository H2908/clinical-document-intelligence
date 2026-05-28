"""
Quick data explorer — run this to verify everything loaded correctly
Usage: python explore_data.py
"""
import csv
from collections import Counter
from pathlib import Path

DATA_DIR = Path(__file__).parent

def load(filename):
    with open(DATA_DIR / filename) as f:
        return list(csv.DictReader(f))

print("=" * 60)
print("NHS Synthetic Dataset Explorer")
print("=" * 60)

# Patients
patients = load('patients.csv')
print(f"\n📋 PATIENTS: {len(patients)}")
print(f"   Male: {sum(1 for p in patients if p['sex']=='M')}")
print(f"   Female: {sum(1 for p in patients if p['sex']=='F')}")
ages = [int(p['age']) for p in patients]
print(f"   Age range: {min(ages)}-{max(ages)} (avg: {sum(ages)//len(ages)})")
print(f"\n   Sample: {patients[0]['first_name']} {patients[0]['last_name']}, "
      f"NHS {patients[0]['nhs_number']}, age {patients[0]['age']}")

# Conditions
conditions = load('conditions.csv')
print(f"\n🩺 CONDITIONS: {len(conditions)}")
top_conds = Counter(c['description'] for c in conditions).most_common(5)
print("   Top 5:")
for cond, count in top_conds:
    print(f"     {count}× {cond}")

# Medications
medications = load('medications.csv')
print(f"\n💊 MEDICATIONS: {len(medications)}")
top_meds = Counter(m['drug_name'] for m in medications).most_common(5)
print("   Top 5:")
for med, count in top_meds:
    print(f"     {count}× {med}")

# Observations
observations = load('observations.csv')
print(f"\n🔬 OBSERVATIONS: {len(observations)}")
top_obs = Counter(o['observation_name'] for o in observations).most_common(5)
print("   Top 5:")
for obs, count in top_obs:
    print(f"     {count}× {obs}")

# Flags
flags = load('flags.csv')
print(f"\n🚩 FLAGS: {len(flags)}")
by_severity = Counter(f['severity'] for f in flags)
for sev in ['HIGH', 'MEDIUM', 'LOW']:
    print(f"   {sev}: {by_severity[sev]}")

# Contradictions
contradictions = load('contradictions.csv')
print(f"\n⚠️  CONTRADICTIONS: {len(contradictions)}")
for c in contradictions[:3]:
    print(f"   • {c['category']} ({c['severity']})")

# Documents
documents = load('documents.csv')
print(f"\n📄 DOCUMENTS: {len(documents)}")
by_type = Counter(d['doc_type'] for d in documents)
for dtype, count in by_type.most_common():
    print(f"   {count}× {dtype}")

# Sample patient deep dive
print(f"\n" + "=" * 60)
print(f"DEEP DIVE: Patient {patients[0]['patient_id']}")
print("=" * 60)
pid = patients[0]['patient_id']
p = patients[0]
print(f"Name: {p['first_name']} {p['last_name']}")
print(f"NHS: {p['nhs_number']}")
print(f"DOB: {p['dob']} (age {p['age']})")
print(f"Address: {p['address']}, {p['city']}")

pt_conds = [c for c in conditions if c['patient_id'] == pid]
print(f"\nConditions ({len(pt_conds)}):")
for c in pt_conds:
    print(f"  • {c['description']} ({c['icd10_code']})")

pt_meds = [m for m in medications if m['patient_id'] == pid]
print(f"\nMedications ({len(pt_meds)}):")
for m in pt_meds:
    print(f"  • {m['drug_name']} {m['dose']}")

pt_flags = [f for f in flags if f['patient_id'] == pid]
if pt_flags:
    print(f"\nFlags ({len(pt_flags)}):")
    for f in pt_flags:
        print(f"  [{f['severity']}] {f['category']}: {f['description'][:60]}...")

print("\n✅ All data loaded successfully!")
print(f"📁 Data location: {DATA_DIR}")
