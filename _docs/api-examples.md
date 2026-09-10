# TableQueue — API Examples

Version: 0.1.0
Last updated: 2026-09-10

All examples assume:
- Backend running at `http://localhost:8000`
- Branch ID `1`
- Staff PIN `1234`

---

## Public

### Get public branch info
```bash
curl http://localhost:8000/api/v1/public/branches/1


Get public board
bash
curl http://localhost:8000/api/v1/public/branches/1/board

Join waitlist
bash
curl -X POST http://localhost:8000/api/v1/branches/1/waitlist \
  -H "Content-Type: application/json" \
  -d '{
    "name": "John Smith",
    "phone": "0900-000-001",
    "party_size": 4,
    "note": "Window seat"
  }'
Get waitlist status (with token)
bash
curl "http://localhost:8000/api/v1/waitlist/A001?token=abc123def456"
Get waitlist status (with last 3 digits)
bash
curl "http://localhost:8000/api/v1/waitlist/A001?phone_last3=001"
Cancel waitlist (guest)
bash
curl -X POST http://localhost:8000/api/v1/waitlist/A001/cancel \
  -H "Content-Type: application/json" \
  -d '{"token": "abc123def456"}'
Auth
Login
bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"pin": "1234"}'
Change PIN
bash
curl -X POST http://localhost:8000/api/v1/auth/change-pin \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "current_pin": "1234",
    "new_pin": "5678",
    "confirm_new_pin": "5678"
  }'
Staff — Waitlist
List waitlist (active)
bash
curl http://localhost:8000/api/v1/staff/waitlist?status=ACTIVE \
  -H "Authorization: Bearer $TOKEN"
List waitlist (closed)
bash
curl "http://localhost:8000/api/v1/staff/waitlist?status=CLOSED" \
  -H "Authorization: Bearer $TOKEN"
Search by name
bash
curl "http://localhost:8000/api/v1/staff/waitlist?search=John" \
  -H "Authorization: Bearer $TOKEN"
Search by phone last 3
bash
curl "http://localhost:8000/api/v1/staff/waitlist?search=001" \
  -H "Authorization: Bearer $TOKEN"
Call an entry
bash
curl -X POST http://localhost:8000/api/v1/staff/waitlist/$ID/call \
  -H "Authorization: Bearer $TOKEN"
Seat an entry
bash
curl -X POST http://localhost:8000/api/v1/staff/waitlist/$ID/seat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"table_id": "'$TABLE_ID'"}'
Mark no-show
bash
curl -X POST http://localhost:8000/api/v1/staff/waitlist/$ID/no-show \
  -H "Authorization: Bearer $TOKEN"
Restore no-show
bash
curl -X POST http://localhost:8000/api/v1/staff/waitlist/$ID/restore \
  -H "Authorization: Bearer $TOKEN"
Revert call
bash
curl -X POST http://localhost:8000/api/v1/staff/waitlist/$ID/revert \
  -H "Authorization: Bearer $TOKEN"
Cancel (staff)
bash
curl -X POST http://localhost:8000/api/v1/staff/waitlist/$ID/cancel \
  -H "Authorization: Bearer $TOKEN"
Edit party size or note
bash
curl -X POST http://localhost:8000/api/v1/staff/waitlist/$ID/edit \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"party_size": 5, "note": "Needs high chair"}'
Reorder
bash
curl -X POST http://localhost:8000/api/v1/staff/waitlist/reorder \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"ordered_ids": ["'$ID1'", "'$ID2'", "'$ID3'"]}'
Staff — Tables
List tables
bash
curl http://localhost:8000/api/v1/staff/tables \
  -H "Authorization: Bearer $TOKEN"
Update table status
bash
curl -X PATCH http://localhost:8000/api/v1/staff/tables/$ID \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status": "CLEANING"}'
Release table
bash
curl -X POST http://localhost:8000/api/v1/staff/tables/$ID/release \
  -H "Authorization: Bearer $TOKEN"
Staff — Dashboard
bash
curl http://localhost:8000/api/v1/staff/dashboard \
  -H "Authorization: Bearer $TOKEN"
Admin — Settings
Get settings
bash
curl http://localhost:8000/api/v1/admin/settings \
  -H "Authorization: Bearer $TOKEN"
Update settings
bash
curl -X PATCH http://localhost:8000/api/v1/admin/settings \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "hold_minutes": 12,
    "avg_seat_minutes": 20,
    "queue_prefix": "B",
    "is_waitlist_open": false,
    "sound_enabled_default": false
  }'
Admin — Tables
List all tables
bash
curl "http://localhost:8000/api/v1/admin/tables?include_inactive=true" \
  -H "Authorization: Bearer $TOKEN"
Create table
bash
curl -X POST http://localhost:8000/api/v1/admin/tables \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "label": "A5",
    "capacity": 2,
    "section": "Patio",
    "sort_order": 5000
  }'
Update table
bash
curl -X PATCH http://localhost:8000/api/v1/admin/tables/$ID \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "label": "A5",
    "capacity": 4,
    "section": "Patio",
    "is_active": true
  }'
Delete table (soft)
bash
curl -X DELETE http://localhost:8000/api/v1/admin/tables/$ID \
  -H "Authorization: Bearer $TOKEN"
Admin — Reset
bash
curl -X POST http://localhost:8000/api/v1/admin/reset \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"confirm": "RESET"}'
Health
bash
curl http://localhost:8000/health
Error Examples
Duplicate phone
json
{
  "error": {
    "code": "WAITLIST_DUPLICATE_PHONE",
    "message": "Phone already on waitlist",
    "details": { "queue_number": "A001" }
  }
}
Invalid status
json
{
  "error": {
    "code": "WAITLIST_INVALID_STATUS",
    "message": "Invalid status for this action",
    "details": {}
  }
}
Table not available
json
{
  "error": {
    "code": "TABLE_NOT_AVAILABLE",
    "message": "Table is not available",
    "details": {}
  }
}
Validation error
json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Validation failed",
    "details": {
      "fields": { "phone": "Invalid format" }
    }
  }
}
Unauthorized
json
{
  "error": {
    "code": "AUTH_TOKEN_EXPIRED",
    "message": "Session expired. Please log in again.",
    "details": {}
  }
}