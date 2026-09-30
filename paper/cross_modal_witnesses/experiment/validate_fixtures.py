from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FIX = ROOT / "fixtures"
REQUIRED_TRACE = {"schema_version","trace_id","fixture_kind","invariant","condition","ground_truth","events"}
REQUIRED_EVENT = {"t","event","page","principal","revision_before","route","legal_keys","selected_key","receipt","state_delta"}

errors = []
for path in sorted(FIX.glob("*.json")):
    data = json.loads(path.read_text(encoding="utf-8"))
    missing = REQUIRED_TRACE - data.keys()
    if missing: errors.append(f"{path.name}: missing trace fields {sorted(missing)}")
    if data.get("schema_version") != "0.1": errors.append(f"{path.name}: wrong schema version")
    if data.get("condition") not in {"aligned","violation"}: errors.append(f"{path.name}: bad condition")
    gt = data.get("ground_truth", {})
    if bool(gt.get("invariant_satisfied")) != (data.get("condition") == "aligned"):
        errors.append(f"{path.name}: condition/ground_truth mismatch")
    for i,event in enumerate(data.get("events", [])):
        m = REQUIRED_EVENT - event.keys()
        if m: errors.append(f"{path.name} event {i}: missing {sorted(m)}")
        if event.get("selected_key") is not None and event.get("selected_key_source") in {"host-table","rederived-host-table"}:
            if event["selected_key"] not in event.get("legal_keys", []):
                # Allowed only in the explicit action-set violation fixture.
                if data.get("trace_id") != "action-set-validity.violation":
                    errors.append(f"{path.name} event {i}: host-table key not offered")
        rec = event.get("receipt")
        if rec and rec.get("accepted") is False and event.get("state_delta"):
            if data.get("trace_id") != "host-validation.violation":
                errors.append(f"{path.name} event {i}: rejected receipt has state delta")
if errors:
    raise SystemExit("\n".join(errors))
print(f"validated {len(list(FIX.glob('*.json')))} fixtures")
