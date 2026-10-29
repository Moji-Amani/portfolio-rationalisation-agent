"""Generate the synthetic estate for the portfolio rationalisation agent demo.

Deterministic: every row is defined explicitly so the planted cases are known.
All names, vendors and owners are invented. Reference date for the scenario: 2026-10-27.
"""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
KEY_DIR = ROOT.parent.parent / "answer_key"   # outside the project folder: the agent must never read it
REF_DATE = "2026-10-27"

INV_COLS = ["tool_id", "name", "capability", "vendor", "type", "cost_type",
            "annual_cost_gbp", "contract_end", "licence_qty", "active_users",
            "utilisation_pct", "owner", "requirement_ids", "evidence_level"]

# name, capability, vendor, type, cost_type, cost, contract_end, licences, users, util, owner, reqs, evidence
TOOLS = [
    # monitoring
    ("PulseWatch Enterprise", "monitoring/network-performance", "Halvard Systems", "software", "opex", 180000, "2027-02-26", 400, 70, 22, "Network Ops Lead", "R001", "tested"),
    ("SignalScope", "monitoring/network-performance", "Brightline Labs", "software", "opex", 45000, "2027-09-30", 250, 210, 78, "Network Ops Lead", "R001", "tested"),
    ("TraceLens APM", "monitoring/application-apm", "Corvid Software", "software", "opex", 62000, "2027-11-30", 120, 98, 74, "Platform Engineering Lead", "R009", "demonstrated"),
    ("ProbeNode X4", "monitoring/synthetic-probing", "Halvard Systems", "hardware", "capex", 28000, "2028-03-31", 40, 35, 81, "Network Ops Lead", "R001", "tested"),
    ("AlarmFuse", "monitoring/alarm-correlation", "Northgate Analytics", "software", "opex", 54000, "2027-07-31", 150, 131, 69, "Assurance Lead", "R002", "tested"),
    ("LogHarbour", "monitoring/log-collection", "Corvid Software", "software", "opex", 41000, "2027-05-31", 200, 164, 66, "Platform Engineering Lead", "R006", "documented"),
    # inventory
    ("TopoLedger", "inventory/network-inventory", "Meridian Tech", "software", "opex", 96000, "2028-01-31", 300, 255, 83, "Inventory Lead", "R005", "tested"),
    ("ConfigBase CMDB", "inventory/cmdb", "Ostrava Digital", "software", "opex", 58000, "2027-08-31", 220, 180, 72, "Service Management Lead", "R012", "tested"),
    ("AddressGrid IPAM", "inventory/ip-address-management", "Meridian Tech", "software", "opex", 23000, "2027-12-31", 60, 52, 77, "Network Engineering Lead", "R005", "demonstrated"),
    ("ScoutScan Discovery", "inventory/asset-discovery", "Ostrava Digital", "software", "opex", 31000, "2027-06-30", 80, 61, 58, "Inventory Lead", "R005", "documented"),
    ("SpareTrack", "inventory/spares-tracking", "Kestrel Works", "software", "opex", 12000, "2027-10-31", 40, 33, 64, "Field Operations Lead", "", "documented"),
    # orchestration
    ("ServiceWeave", "orchestration/service-orchestration", "Brightline Labs", "software", "opex", 140000, "2028-06-30", 150, 124, 71, "Orchestration Lead", "R007", "tested"),
    ("FlowMesh Autopilot", "orchestration/closed-loop-remediation", "Halvard Systems", "software", "opex", 88000, "2027-12-31", 100, 72, 55, "Orchestration Lead", "R007", "claimed only"),
    ("TaskRelay", "orchestration/workflow-automation", "Kestrel Works", "software", "opex", 36000, "2027-04-30", 180, 149, 68, "Orchestration Lead", "R002", "demonstrated"),
    ("StateKeeper", "orchestration/config-management", "Ostrava Digital", "software", "opex", 47000, "2027-09-30", 90, 80, 79, "Network Engineering Lead", "R003;R012", "tested"),
    ("TestForge", "orchestration/test-automation", "Corvid Software", "software", "opex", 29000, "2027-03-31", 60, 41, 61, "Platform Engineering Lead", "", "tested"),
    # analytics
    ("ClearView BI", "analytics/bi-reporting", "Northgate Analytics", "software", "opex", 52000, "2027-08-31", 350, 290, 76, "Data Lead", "R009", "tested"),
    ("DepthStore", "analytics/data-warehouse", "Lumen Fabric", "software", "opex", 165000, "2028-03-31", 120, 104, 82, "Data Lead", "R009;R014", "tested"),
    ("InsightBox", "analytics/usage-analytics", "Northgate Analytics", "software", "opex", 38000, "2027-06-30", 50, 0, 0, "", "", "documented"),
    ("ModelYard", "analytics/ml-platform", "Lumen Fabric", "software", "opex", 74000, "2027-11-30", 40, 31, 57, "Data Science Lead", "R010", "demonstrated"),
    ("Atlas Catalogue", "analytics/data-catalogue", "Lumen Fabric", "software", "opex", 26000, "2027-07-31", 150, 112, 63, "Data Lead", "R014", "documented"),
    ("RiverStream", "analytics/stream-processing", "Brightline Labs", "software", "opex", 68000, "2028-02-29", 30, 27, 85, "Platform Engineering Lead", "R001", "tested"),
    # ticketing
    ("ResolveDesk", "ticketing/incident-management", "Ostrava Digital", "software", "opex", 110000, "2028-04-30", 600, 540, 88, "Service Management Lead", "R002;R004", "tested"),
    ("DispatchPoint", "ticketing/field-dispatch", "Kestrel Works", "software", "opex", 49000, "2027-10-31", 400, 352, 80, "Field Operations Lead", "R002", "tested"),
    ("ChangeBoard", "ticketing/change-management", "Ostrava Digital", "software", "opex", 33000, "2027-05-31", 250, 198, 71, "Service Management Lead", "R012", "tested"),
    ("QueueDesk Lite", "ticketing/customer-tickets", "Pellow & Finch", "software", "opex", 27000, "2026-12-11", 300, 48, 18, "Customer Service Lead", "R004", "documented"),
    ("KnowHow Base", "ticketing/knowledge-base", "Pellow & Finch", "software", "opex", 14000, "2027-09-30", 500, 362, 62, "Service Management Lead", "", "documented"),
    # security
    ("Sentinel Vault PAM", "security/privileged-access", "Ironwood Secure", "software", "opex", 50000, "2027-11-30", 200, 260, 97, "Security Lead", "R008", "tested"),
    ("HoleFinder", "security/vulnerability-scanning", "Ironwood Secure", "software", "opex", 39000, "2027-08-31", 2000, 1740, 87, "Security Lead", "R013", "tested"),
    ("WatchTower SIEM", "security/siem", "Corvid Software", "software", "opex", 125000, "2028-05-31", 60, 51, 84, "Security Lead", "R006", "tested"),
    ("ShieldPoint EDR", "security/endpoint-protection", "Ironwood Secure", "software", "opex", 72000, "2027-12-31", 3000, 2650, 88, "Security Lead", "", "tested"),
    ("KeyChest", "security/secrets-management", "Halvard Systems", "software", "opex", 21000, "2027-06-30", 80, 66, 73, "Platform Engineering Lead", "R008", "demonstrated"),
    # backup
    ("EdgeStore Array", "backup/storage-array", "Granite Hardware", "hardware", "capex", 64000, "2028-09-30", 4, 3, 15, "Infrastructure Lead", "R003", "tested"),
    ("CloudKeep Backup", "backup/cloud-backup", "Lumen Fabric", "software", "opex", 34000, "2027-10-31", 100, 78, 69, "Infrastructure Lead", "R011", "tested"),
    ("DeepFreeze Archive", "backup/archive", "Granite Hardware", "hardware", "capex", 22000, "2028-12-31", 2, 2, 52, "Infrastructure Lead", "", "tested"),
    ("FailSafe DR", "backup/disaster-recovery", "Brightline Labs", "software", "opex", 81000, "2028-01-31", 20, 18, 60, "Infrastructure Lead", "R011", "demonstrated"),
]

REQUIREMENTS = [
    ("R001", "Network performance monitoring across core and RAN", "Must", ">=99.5% element coverage at 5-minute granularity", "Network Ops Lead"),
    ("R002", "Incident management with SLA tracking", "Must", "P1 acknowledged within 15 minutes for >=98% of incidents", "Service Management Lead"),
    ("R003", "Backup of network configuration and OSS data", "Must", "RPO <=4 hours; retention >=90 days", "Infrastructure Lead"),
    ("R004", "Customer-facing ticket logging", "Should", ">=90% of customer tickets logged without agent help", "Customer Service Lead"),
    ("R005", "Accurate network inventory", "Must", ">=98% inventory accuracy against audit sample", "Inventory Lead"),
    ("R006", "24x7 security event monitoring", "Should", "Mean time to detect <1 hour", "Security Lead"),
    ("R007", "Closed-loop remediation for top fault types", "Must", ">=60% of top-20 fault types auto-resolved", "Orchestration Lead"),
    ("R008", "Privileged access control for admin accounts", "Must", "100% of admin accounts under managed access", "Security Lead"),
    ("R009", "Operational KPI reporting", "Should", "Daily refresh by 07:00", "Data Lead"),
    ("R010", "ML model deployment for assurance use cases", "Could", ">=3 models in production", "Data Science Lead"),
    ("R011", "Disaster recovery for OSS platforms", "Should", "RTO <=8 hours", "Infrastructure Lead"),
    ("R012", "Change management with audit trail", "Must", "100% of changes logged with approval record", "Service Management Lead"),
    ("R013", "Vulnerability scanning of exposed assets", "Should", "Weekly scan of 100% of internet-facing assets", "Security Lead"),
    ("R014", "Data catalogue for OSS datasets", "Could", ">=80% of OSS datasets catalogued", "Data Lead"),
]


def write_csv(path, cols, rows):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        w.writerows(rows)


def main():
    KEY_DIR.mkdir(exist_ok=True)
    inv = [(f"T{i:03d}", *t) for i, t in enumerate(TOOLS, start=1)]
    ids = {row[1]: row[0] for row in inv}
    write_csv(ROOT / "inventory.csv", INV_COLS, inv)
    write_csv(ROOT / "requirements.csv",
              ["requirement_id", "text", "priority", "threshold", "owner"], REQUIREMENTS)

    taxonomy = sorted({t[1] for t in TOOLS})
    write_csv(ROOT / "taxonomy.csv", ["capability", "domain"],
              [(c, c.split("/")[0]) for c in taxonomy])

    # Messy variant for the validation test: copy, then damage specific rows.
    messy = [list(r) for r in inv]
    messy[4][0] = messy[3][0]           # duplicate tool_id (T005 -> T004)
    messy[9][6] = ""                    # missing annual_cost_gbp (T010)
    messy[13][7] = "31/04/2027"         # malformed and impossible date (T014)
    messy[16][10] = "140"               # utilisation out of range (T017)
    messy[20][13] = "vendor says yes"   # evidence_level not in allowed set (T021)
    messy[24][11] = ""                  # owner removed (T025)
    messy[30][2] = "security/firewall"  # capability not in taxonomy (T031)
    write_csv(ROOT / "inventory_messy.csv", INV_COLS, messy)

    key = {
        "reference_date": REF_DATE,
        "cases": [
            {"case": 1, "name": "Overlap", "tools": [ids["PulseWatch Enterprise"], ids["SignalScope"]],
             "expected": f"Retire or merge {ids['PulseWatch Enterprise']} into {ids['SignalScope']}; "
                         "R001 stays covered; Two-Way Door (non-renewal at 2027-02-26); saving as a range",
             "reference_saving_gbp": {"low": 23000, "base": 94000, "high": 146000,
                                      "assumptions": "recoverable share 60/80/95% of 180k; migration 50/30/15k; "
                                                     "SignalScope uplift 35/20/10k (low/base/high)"}},
            {"case": 2, "name": "Renewal", "tools": [ids["QueueDesk Lite"]],
             "expected": "Do not renew (ends 2026-12-11, 45 days; 18% utilised); R004 still covered by "
                         f"{ids['ResolveDesk']}; Two-Way Door"},
            {"case": 3, "name": "Dependency", "tools": [ids["EdgeStore Array"]],
             "expected": "Keep despite 15% utilisation; flag that Must requirement R003 depends on it; "
                         "any decommissioning is One-Way Door"},
            {"case": 4, "name": "Orphan", "tools": [ids["InsightBox"]],
             "expected": "Retire candidate (no owner, 0 active users); ask for an owner before action; "
                         "no requirement dependency"},
            {"case": 5, "name": "Claimed only", "tools": [ids["FlowMesh Autopilot"]],
             "expected": "Flag closed-loop remediation as not delivered; do not count it as covering Must R007; "
                         f"R007 shows as partly or not covered (only {ids['ServiceWeave']} otherwise maps to it)"},
            {"case": 6, "name": "Under-provisioned", "tools": [ids["Sentinel Vault PAM"]],
             "expected": "Flag procurement need: 60-licence shortfall (200 owned, 260 active) on Must R008",
             "reference_cost_gbp": {"low": 12000, "base": 15000, "high": 16500,
                                    "assumptions": "unit price 250 (50k/200); 20% volume discount / list / "
                                                   "+10% mid-term premium"}},
        ],
        "messy_file_expected_errors": [
            "T004 duplicate tool_id (blocking)",
            "T010 missing annual_cost_gbp",
            "T014 invalid contract_end '31/04/2027'",
            "T017 utilisation_pct 140 out of range 0-100",
            "T021 evidence_level 'vendor says yes' not allowed",
            "T025 missing owner",
            "T031 capability 'security/firewall' not in taxonomy",
        ],
        "control_expectation": "All other tools should be Keep with no flags, except advisory notes the agent can justify.",
    }
    (KEY_DIR / "answer_key.json").write_text(json.dumps(key, indent=2))
    print(f"{len(inv)} tools, {len(taxonomy)} capabilities, {len(REQUIREMENTS)} requirements")


if __name__ == "__main__":
    main()
