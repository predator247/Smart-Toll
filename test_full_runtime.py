"""Expanded runtime verification for Smart Toll Control System.

Run with:  python test_full_runtime.py   (SMART_TOLL_SECRET_KEY is set inside)
"""
import os
import time
import json

os.environ["SMART_TOLL_SECRET_KEY"] = "test-secret-key-for-verification"

from app import app, init_db
init_db()

PASS = []
FAIL = []

def check(name, cond, detail=""):
    if cond:
        PASS.append(name)
        print(f"PASS  {name}")
    else:
        FAIL.append(name)
        print(f"FAIL  {name}  {detail}")

with app.test_client() as c:
    # --- pages ---
    for path in ["/", "/user", "/worker", "/analytics", "/reports"]:
        r = c.get(path)
        check(f"page {path}", r.status_code == 200, r.status_code)
    r = c.get("/database")
    check("database unauth -> 403", r.status_code == 403, r.status_code)

    # --- worker login ---
    r = c.post("/api/worker/login", json={"worker_id": "HAR001", "password": "pass001"})
    check("worker login", r.status_code == 200, r.status_code)
    worker = r.get_json() if r.status_code == 200 else {}

    # --- scan clear + stolen ---
    r = c.post("/api/worker/scan", json={"license_plate": "UK07AB1234",
                                         "scan_source": "manual",
                                         "nearest_toll": "Delhi-Jaipur NH48 Toll"})
    j = r.get_json() or {}
    check("scan clear", r.status_code == 200 and j.get("status") == "clear", j)
    r = c.post("/api/worker/scan", json={"license_plate": "PB10ZX7788",
                                         "scan_source": "camera",
                                         "nearest_toll": "Delhi-Jaipur NH48 Toll"})
    j = r.get_json() or {}
    check("scan stolen alert", r.status_code == 200 and j.get("status") == "alert", j)

    # --- face event (match) ---
    r = c.post("/api/worker/face-event", json={
        "observation_note": "runtime test",
        "review_status": "alert_raised",
        "matched_case_id": "CR-MH-1005",
    })
    j = r.get_json() or {}
    check("face-event match", r.status_code == 200 and "Don" in (j.get("alert_message") or ""),
          j)

    # --- criminal alert ---
    r = c.post("/api/worker/criminal-alert", json={"case_id": "CR-MH-1005"})
    check("criminal-alert", r.status_code == 200, r.get_json())

    # --- toll estimate ---
    r = c.get("/api/toll-estimate?lat=28.7&lon=77.1&vehicle_type=car")
    j = r.get_json() or {}
    check("toll-estimate", r.status_code == 200 and "nearest_toll" in j and "estimated_fare" in j, j)

    # --- stats / analytics / reports / transactions ---
    for ep in ["/api/stats", "/api/analytics", "/api/reports", "/api/transactions",
               "/api/toll-plazas", "/api/vehicles", "/api/criminal-records",
               "/api/face-descriptors", "/api/face-events", "/api/worker/alerts",
               "/api/worker/scans", "/api/police-stolen"]:
        r = c.get(ep)
        check(f"GET {ep}", r.status_code == 200, r.status_code)

    # --- face descriptor enrolment (128 floats) ---
    desc = [0.01 * i for i in range(128)]
    r = c.post("/api/worker/face-descriptor", json={
        "worker_id": "HAR001",
        "case_id": "CR-DEL-1001",
        "face_descriptor": desc,
        "photo_path": "test_assets/faces/CR-DEL-1001.jpg",
    })
    check("face-descriptor enrol", r.status_code == 200, r.get_json())
    r = c.get("/api/face-descriptors")
    j = r.get_json() or []
    ids = [d.get("case_id") for d in j]
    check("face-descriptors contains CR-DEL-1001", "CR-DEL-1001" in ids, ids)

    # --- user flow ---
    email = f"rt_{int(time.time())}@test.com"
    r = c.post("/api/user/signup", json={
        "email": email, "full_name": "Runtime Test", "password": "secret123",
        "phone_number": "9999999999", "address": "Test City",
    })
    j = r.get_json() or {}
    check("user signup", r.status_code == 200 and "user_id" in j, j)
    uid = j.get("user_id")
    r = c.post("/api/user/login", json={"email": email, "password": "secret123"})
    j = r.get_json() or {}
    check("user login", r.status_code == 200 and j.get("user_id") == uid, j)
    r = c.post("/api/user/register-vehicle", json={
        "user_id": uid, "license_plate": "RT00ZZ1111", "owner_name": "Runtime Test",
        "vehicle_type": "car", "mobile_number": "9999999999", "city": "Delhi",
        "fastag_balance": 500,
    })
    check("register-vehicle", r.status_code == 200, r.get_json())
    r = c.get(f"/api/user/profile?user_id={uid}")
    j = r.get_json() or {}
    check("user profile", r.status_code == 200 and j.get("profile") is not None, "profile missing")
    r = c.post("/api/user/pollution", json={
        "user_id": uid, "certificate_number": "PUC-RT-001",
        "emission_level": "BS6", "valid_until": "2027-01-01",
    })
    check("pollution submit", r.status_code == 200, r.get_json())
    r = c.post("/api/user/wallet", json={"user_id": uid, "amount": 100, "payment_method": "UPI"})
    check("wallet recharge", r.status_code == 200, r.get_json())
    r = c.post("/api/user/save-location", json={"user_id": uid, "lat": 28.7, "lon": 77.1})
    j = r.get_json() or {}
    check("save-location", r.status_code == 200 and "nearest_toll" in j, j)

    # --- unauth checks ---
    with app.test_client() as c2:
        r = c2.post("/api/worker/scan", json={"license_plate": "XX"})
        check("unauth /api/worker/scan", r.status_code == 401, r.status_code)
        r = c2.post("/api/worker/face-event", json={"observation_note": "x"})
        check("unauth /api/worker/face-event", r.status_code == 401, r.status_code)
        r = c2.post("/api/worker/criminal-alert", json={"case_id": "CR-MH-1005"})
        check("unauth /api/worker/criminal-alert", r.status_code == 401, r.status_code)

print()
print(f"PASS: {len(PASS)}   FAIL: {len(FAIL)}")
if FAIL:
    print("Failed:", FAIL)
    raise SystemExit(1)
print("ALL RUNTIME CHECKS PASSED")
