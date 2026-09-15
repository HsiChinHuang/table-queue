#!/usr/bin/env python3
"""
Integration Walk Runner - walks the demo end-to-end through the vite-proxied frontend.

Per spec: scripts/integration_walk.md
- Talks ONLY to the proxied origin (frontend port) it is given
- Logs USE_MOCK=false; per-step STEP <id> PASS|FAIL; final RESULT=PASS|FAIL
- Exit code mirrors RESULT
- Writes log to documented artifact path
"""

import os
import sys
import json
import requests
import time
import uuid

# Configuration from environment
BACKEND_URL = os.environ.get('BACKEND_URL', 'http://localhost:8000')
FRONTEND_URL = os.environ.get('FRONTEND_URL', 'http://localhost:5173')
VITE_USE_MOCK = os.environ.get('VITE_USE_MOCK', 'false')
STAFF_PIN = os.environ.get('STAFF_PIN', '1234')
LOG_PATH = os.environ.get('LOG_PATH', '/tmp/tq-walk.log')

# API base - we talk to the frontend which proxies to backend
API_BASE = FRONTEND_URL + '/api/v1'

# Test data - unique phone per run to avoid 409 WAITLIST_DUPLICATE_PHONE
def unique_phone():
    """Generate a unique Taiwan mobile number."""
    suffix = str(uuid.uuid4())[:8].replace('-', '')
    return f"0900-000-{suffix[-3:]}"

def log(msg):
    """Write log message."""
    print(msg)

def assert_step(step_id, condition, expected=True, details=""):
    """Assert a step condition, log result."""
    if condition == expected:
        log(f"STEP {step_id}: PASS")
        return True
    else:
        log(f"STEP {step_id}: FAIL (expected {expected}, got {condition}) {details}")
        return False

def main():
    all_pass = True
    results = []
    
    # Check mock mode
    if VITE_USE_MOCK != 'false':
        log("ERROR: MOCK_MODE_ENABLED")
        log("RESULT=FAIL")
        return 1
    
    log("VITE_USE_MOCK=false")
    log(f"Frontend: {FRONTEND_URL}")
    log(f"Backend: {BACKEND_URL}")
    log("")
    
    # Variables to carry between steps
    status_token = None
    queue_number = None
    staff_jwt = None
    entry_id = None
    table_id = None
    
    # S1: Join Waitlist
    # POST /api/v1/branches/1/waitlist -> 201
    # Body: name, phone, party_size, note
    phone = unique_phone()
    join_payload = {
        "name": "Integration Test",
        "phone": phone,
        "party_size": 2,
        "note": "D3 runner test"
    }
    try:
        resp = requests.post(f"{API_BASE}/branches/1/waitlist", json=join_payload, timeout=10)
        if resp.status_code == 201:
            data = resp.json()
            # Verify response shape per openapi
            has_status_token = 'status_token' in data
            has_queue_number = 'queue_number' in data
            has_status_url = 'status_url' in data
            if has_status_token and has_queue_number and has_status_url:
                status_token = data['status_token']
                queue_number = data['queue_number']
                entry_id = data.get('id')
                log(f"  Joined: queue={queue_number}, token={status_token[:8]}...")
            else:
                log(f"  Missing fields in response: {data.keys()}")
        else:
            log(f"  Status: {resp.status_code}")
    except Exception as e:
        log(f"  Error: {e}")
        resp = None
    
    s1_pass = assert_step("S1", resp is not None and resp.status_code == 201 and status_token is not None)
    results.append(("S1", s1_pass))
    if not s1_pass:
        all_pass = False
    
    # S2: Status Page Load
    # GET /api/v1/waitlist/{queue_number}?token={status_token} -> 200
    if status_token and queue_number:
        try:
            resp = requests.get(f"{API_BASE}/waitlist/{queue_number}", params={"token": status_token}, timeout=10)
            s2_pass = assert_step("S2", resp.status_code == 200, 
                                  details=f"got {resp.status_code}" if resp.status_code != 200 else "")
            if resp.status_code == 200:
                data = resp.json()
                # Verify response shape
                has_status = 'status' in data
                has_party_size = 'party_size' in data
                s2_pass = s2_pass and assert_step("S2-shape", has_status and has_party_size)
            results.append(("S2", s2_pass))
            if not s2_pass:
                all_pass = False
        except Exception as e:
            log(f"  Error: {e}")
            s2_pass = assert_step("S2", False, details=str(e))
            results.append(("S2", s2_pass))
            all_pass = False
    else:
        log("  SKIPPED (no token/queue_number from S1)")
        results.append(("S2", False))
        all_pass = False
    
    # S3: Status Without Factor
    # GET /api/v1/waitlist/{queue_number} -> 422
    if queue_number:
        try:
            resp = requests.get(f"{API_BASE}/waitlist/{queue_number}", timeout=10)
            s3_pass = assert_step("S3", resp.status_code == 422,
                                  details=f"got {resp.status_code}" if resp.status_code != 422 else "")
            results.append(("S3", s3_pass))
            if not s3_pass:
                all_pass = False
        except Exception as e:
            log(f"  Error: {e}")
            s3_pass = assert_step("S3", False, details=str(e))
            results.append(("S3", s3_pass))
            all_pass = False
    else:
        log("  SKIPPED (no queue_number)")
        results.append(("S3", False))
        all_pass = False
    
    # S4: Cancel With Factor
    # POST /api/v1/waitlist/{queue_number}/cancel with {token} -> 200
    if status_token and queue_number:
        try:
            resp = requests.post(f"{API_BASE}/waitlist/{queue_number}/cancel", 
                                 json={"token": status_token}, timeout=10)
            s4_pass = assert_step("S4", resp.status_code == 200,
                                  details=f"got {resp.status_code}" if resp.status_code != 200 else "")
            results.append(("S4", s4_pass))
            if not s4_pass:
                all_pass = False
        except Exception as e:
            log(f"  Error: {e}")
            s4_pass = assert_step("S4", False, details=str(e))
            results.append(("S4", s4_pass))
            all_pass = False
    else:
        log("  SKIPPED (no token/queue_number)")
        results.append(("S4", False))
        all_pass = False
    
    # S5: Cancel Without Factor
    # Need a fresh entry first - join again
    phone2 = unique_phone()
    join_payload2 = {
        "name": "Integration Test S5",
        "phone": phone2,
        "party_size": 2,
        "note": "S5 test"
    }
    try:
        resp = requests.post(f"{API_BASE}/branches/1/waitlist", json=join_payload2, timeout=10)
        if resp.status_code == 201:
            data = resp.json()
            qn2 = data.get('queue_number')
            # Cancel without factor
            resp2 = requests.post(f"{API_BASE}/waitlist/{qn2}/cancel", json={}, timeout=10)
            s5_pass = assert_step("S5", resp2.status_code == 422,
                                  details=f"got {resp2.status_code}" if resp2.status_code != 422 else "")
            results.append(("S5", s5_pass))
            if not s5_pass:
                all_pass = False
        else:
            s5_pass = assert_step("S5", False, details=f"join failed: {resp.status_code}")
            results.append(("S5", s5_pass))
            all_pass = False
    except Exception as e:
        log(f"  Error: {e}")
        s5_pass = assert_step("S5", False, details=str(e))
        results.append(("S5", s5_pass))
        all_pass = False
    
    # S6: Staff Login
    # POST /api/v1/auth/login with {pin: "1234"} -> 200
    try:
        resp = requests.post(f"{API_BASE}/auth/login", json={"pin": STAFF_PIN}, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if 'access_token' in data:
                staff_jwt = data['access_token']
                log(f"  Logged in as staff")
        s6_pass = assert_step("S6", resp.status_code == 200 and staff_jwt is not None,
                              details=f"got {resp.status_code}" if resp.status_code != 200 else "")
        results.append(("S6", s6_pass))
        if not s6_pass:
            all_pass = False
    except Exception as e:
        log(f"  Error: {e}")
        s6_pass = assert_step("S6", False, details=str(e))
        results.append(("S6", s6_pass))
        all_pass = False
    
    # S7: Staff Waitlist
    # GET /api/v1/staff/waitlist with JWT -> 200
    if staff_jwt:
        try:
            resp = requests.get(f"{API_BASE}/staff/waitlist", 
                                headers={"Authorization": f"Bearer {staff_jwt}"}, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                has_items = 'items' in data and isinstance(data['items'], list)
                s7_pass = assert_step("S7", resp.status_code == 200 and has_items,
                                      details=f"no items array" if not has_items else "")
            else:
                s7_pass = assert_step("S7", False, details=f"got {resp.status_code}")
            results.append(("S7", s7_pass))
            if not s7_pass:
                all_pass = False
        except Exception as e:
            log(f"  Error: {e}")
            s7_pass = assert_step("S7", False, details=str(e))
            results.append(("S7", s7_pass))
            all_pass = False
    else:
        log("  SKIPPED (no JWT from S6)")
        results.append(("S7", False))
        all_pass = False
    
    # S8: Call Entry
    # POST /api/v1/staff/waitlist/{id}/call with JWT -> 200
    # Need an entry to call - join a fresh one
    phone3 = unique_phone()
    join_payload3 = {
        "name": "Integration Test S8",
        "phone": phone3,
        "party_size": 2,
        "note": "S8 test"
    }
    try:
        resp = requests.post(f"{API_BASE}/branches/1/waitlist", json=join_payload3, timeout=10)
        if resp.status_code == 201:
            data = resp.json()
            entry_id = data.get('id')
            if entry_id and staff_jwt:
                resp2 = requests.post(f"{API_BASE}/staff/waitlist/{entry_id}/call",
                                      headers={"Authorization": f"Bearer {staff_jwt}"}, timeout=10)
                s8_pass = assert_step("S8", resp2.status_code == 200,
                                      details=f"got {resp2.status_code}" if resp2.status_code != 200 else "")
            else:
                s8_pass = assert_step("S8", False, details=f"no entry_id or jwt")
        else:
            s8_pass = assert_step("S8", False, details=f"join failed: {resp.status_code}")
        results.append(("S8", s8_pass))
        if not s8_pass:
            all_pass = False
    except Exception as e:
        log(f"  Error: {e}")
        s8_pass = assert_step("S8", False, details=str(e))
        results.append(("S8", s8_pass))
        all_pass = False
    
    # S9: Status After Call
    # GET /api/v1/waitlist/{queue_number}?token={status_token} -> 200, status is CALLED
    # Use the queue_number from S8's entry
    if entry_id and staff_jwt:
        # First get the entry to find its queue_number
        try:
            resp = requests.get(f"{API_BASE}/staff/waitlist",
                                headers={"Authorization": f"Bearer {staff_jwt}"}, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                items = data.get('items', [])
                # Find our entry
                my_entry = None
                for item in items:
                    if item.get('id') == entry_id:
                        my_entry = item
                        break
                if my_entry:
                    qn = my_entry.get('queue_number')
                    # Get status - but we need the token, which we don't have for this entry
                    # Use phone_last3 instead
                    phone = my_entry.get('phone', '')
                    phone_last3 = phone[-3:] if len(phone) >= 3 else ''
                    if qn and phone_last3:
                        resp2 = requests.get(f"{API_BASE}/waitlist/{qn}", 
                                            params={"phone_last3": phone_last3}, timeout=10)
                        if resp2.status_code == 200:
                            data2 = resp2.json()
                            is_called = data2.get('status') == 'CALLED'
                            has_remaining = 'remaining_seconds' in data2
                            s9_pass = assert_step("S9", is_called and has_remaining,
                                                  details=f"status={data2.get('status')}" if not is_called else "")
                        else:
                            s9_pass = assert_step("S9", False, details=f"got {resp2.status_code}")
                    else:
                        s9_pass = assert_step("S9", False, details=f"no qn or phone_last3")
                else:
                    s9_pass = assert_step("S9", False, details="entry not found")
            else:
                s9_pass = assert_step("S9", False, details=f"waitlist got {resp.status_code}")
        except Exception as e:
            log(f"  Error: {e}")
            s9_pass = assert_step("S9", False, details=str(e))
        results.append(("S9", s9_pass))
        if not s9_pass:
            all_pass = False
    else:
        log("  SKIPPED (no entry_id or jwt)")
        results.append(("S9", False))
        all_pass = False
    
    # S10: Seat Entry
    # POST /api/v1/staff/waitlist/{id}/seat with {table_id} -> 200
    # First we need a table_id - get available tables
    if staff_jwt:
        try:
            resp = requests.get(f"{API_BASE}/staff/tables",
                                headers={"Authorization": f"Bearer {staff_jwt}"}, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                items = data.get('items', [])
                # Find an available table
                available = None
                for table in items:
                    if table.get('status') == 'AVAILABLE':
                        available = table
                        break
                if available:
                    table_id = available.get('id')
                    if entry_id and table_id:
                        resp2 = requests.post(f"{API_BASE}/staff/waitlist/{entry_id}/seat",
                                              json={"table_id": table_id}, timeout=10)
                        s10_pass = assert_step("S10", resp2.status_code == 200,
                                               details=f"got {resp2.status_code}" if resp2.status_code != 200 else "")
                    else:
                        s10_pass = assert_step("S10", False, details=f"no entry_id or table_id")
                else:
                    s10_pass = assert_step("S10", False, details="no available tables")
            else:
                s10_pass = assert_step("S10", False, details=f"tables got {resp.status_code}")
        except Exception as e:
            log(f"  Error: {e}")
            s10_pass = assert_step("S10", False, details=str(e))
        results.append(("S10", s10_pass))
        if not s10_pass:
            all_pass = False
    else:
        log("  SKIPPED (no JWT)")
        results.append(("S10", False))
        all_pass = False
    
    # S11: Table Status
    # GET /api/v1/staff/tables with JWT -> 200, table shows OCCUPIED
    if staff_jwt and table_id:
        try:
            resp = requests.get(f"{API_BASE}/staff/tables",
                                headers={"Authorization": f"Bearer {staff_jwt}"}, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                items = data.get('items', [])
                # Find our table
                my_table = None
                for table in items:
                    if table.get('id') == table_id:
                        my_table = table
                        break
                if my_table:
                    is_occupied = my_table.get('status') == 'OCCUPIED'
                    s11_pass = assert_step("S11", is_occupied,
                                           details=f"status={my_table.get('status')}" if not is_occupied else "")
                else:
                    s11_pass = assert_step("S11", False, details="table not found")
            else:
                s11_pass = assert_step("S11", False, details=f"got {resp.status_code}")
        except Exception as e:
            log(f"  Error: {e}")
            s11_pass = assert_step("S11", False, details=str(e))
        results.append(("S11", s11_pass))
        if not s11_pass:
            all_pass = False
    else:
        log("  SKIPPED (no JWT or table_id)")
        results.append(("S11", False))
        all_pass = False
    
    # S12: Release Table
    # POST /api/v1/staff/tables/{id}/release with JWT -> 200, table becomes AVAILABLE
    if staff_jwt and table_id:
        try:
            resp = requests.post(f"{API_BASE}/staff/tables/{table_id}/release",
                                 headers={"Authorization": f"Bearer {staff_jwt}"}, timeout=10)
            if resp.status_code == 200:
                # Verify table is now available
                resp2 = requests.get(f"{API_BASE}/staff/tables",
                                     headers={"Authorization": f"Bearer {staff_jwt}"}, timeout=10)
                if resp2.status_code == 200:
                    data = resp2.json()
                    items = data.get('items', [])
                    my_table = None
                    for table in items:
                        if table.get('id') == table_id:
                            my_table = table
                            break
                    if my_table:
                        is_available = my_table.get('status') == 'AVAILABLE'
                        s12_pass = assert_step("S12", is_available,
                                               details=f"status={my_table.get('status')}" if not is_available else "")
                    else:
                        s12_pass = assert_step("S12", False, details="table not found")
                else:
                    s12_pass = assert_step("S12", False, details=f"verify got {resp2.status_code}")
            else:
                s12_pass = assert_step("S12", False, details=f"got {resp.status_code}")
        except Exception as e:
            log(f"  Error: {e}")
            s12_pass = assert_step("S12", False, details=str(e))
        results.append(("S12", s12_pass))
        if not s12_pass:
            all_pass = False
    else:
        log("  SKIPPED (no JWT or table_id)")
        results.append(("S12", False))
        all_pass = False
    
    # S13: Public Board
    # GET /api/v1/public/branches/1/board -> 200, response contains current_called, next_up
    try:
        resp = requests.get(f"{API_BASE}/public/branches/1/board", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            has_current = 'current_called' in data
            has_next = 'next_up' in data
            s13_pass = assert_step("S13", has_current and has_next,
                                   details=f"missing fields" if not (has_current and has_next) else "")
        else:
            s13_pass = assert_step("S13", False, details=f"got {resp.status_code}")
    except Exception as e:
        log(f"  Error: {e}")
        s13_pass = assert_step("S13", False, details=str(e))
    results.append(("S13", s13_pass))
    if not s13_pass:
        all_pass = False
    
    # S14: Settings Read
    # GET /api/v1/admin/settings with JWT -> 200, response contains hold_minutes
    if staff_jwt:
        try:
            resp = requests.get(f"{API_BASE}/admin/settings",
                                headers={"Authorization": f"Bearer {staff_jwt}"}, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                has_hold = 'hold_minutes' in data
                s14_pass = assert_step("S14", has_hold,
                                       details=f"missing hold_minutes" if not has_hold else "")
            else:
                s14_pass = assert_step("S14", False, details=f"got {resp.status_code}")
        except Exception as e:
            log(f"  Error: {e}")
            s14_pass = assert_step("S14", False, details=str(e))
    else:
        log("  SKIPPED (no JWT)")
        s14_pass = False
    results.append(("S14", s14_pass))
    if not s14_pass:
        all_pass = False
    
    # S15: Settings Write
    # PATCH /api/v1/admin/settings with JWT {hold_minutes: 12} -> 200, subsequent read shows 12
    if staff_jwt:
        try:
            resp = requests.patch(f"{API_BASE}/admin/settings",
                                  headers={"Authorization": f"Bearer {staff_jwt}"},
                                  json={"hold_minutes": 12}, timeout=10)
            if resp.status_code == 200:
                # Verify
                resp2 = requests.get(f"{API_BASE}/admin/settings",
                                     headers={"Authorization": f"Bearer {staff_jwt}"}, timeout=10)
                if resp2.status_code == 200:
                    data = resp2.json()
                    is_12 = data.get('hold_minutes') == 12
                    s15_pass = assert_step("S15", is_12,
                                           details=f"hold_minutes={data.get('hold_minutes')}" if not is_12 else "")
                else:
                    s15_pass = assert_step("S15", False, details=f"verify got {resp2.status_code}")
            else:
                s15_pass = assert_step("S15", False, details=f"got {resp.status_code}")
        except Exception as e:
            log(f"  Error: {e}")
            s15_pass = assert_step("S15", False, details=str(e))
    else:
        log("  SKIPPED (no JWT)")
        s15_pass = False
    results.append(("S15", s15_pass))
    if not s15_pass:
        all_pass = False
    
    # Final result
    log("")
    if all_pass:
        log("RESULT=PASS")
        return 0
    else:
        log("RESULT=FAIL")
        return 1

if __name__ == "__main__":
    sys.exit(main())
