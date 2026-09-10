# TableQueue — API Examples

Version: 0.1.0
Last updated: 2026-09-10

All examples assume:
- Backend running at `http://localhost:8000`
- JWT token stored in `$TOKEN` after login

---

## Public

### Get public branch info
```bash
curl http://localhost:8000/api/v1/public/branches/{branch_id}
```

### Get public board data
```bash
curl http://localhost:8000/api/v1/public/branches/{branch_id}/board
```

### Join the waitlist
```bash
curl -X POST http://localhost:8000/api/v1/branches/{branch_id}/waitlist \
  -H "Content-Type: application/json" \
  -d '{
    "name": "John Smith",
    "phone": "0900-000-001",
    "party_size": 4,
    "note": "Window seat"
  }'
```

### Get waitlist status
```bash
curl http://localhost:8000/api/v1/waitlist/{queue_number}
```

### Cancel waitlist entry
```bash
curl -X POST http://localhost:8000/api/v1/waitlist/{queue_number}/cancel \
  -H "Content-Type: application/json" \
  -d '{"token": "abc123def456"}'
```

## Auth

### Staff login
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"pin": "1234"}'
```

### Change staff PIN
```bash
curl -X POST http://localhost:8000/api/v1/auth/change-pin \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "current_pin": "1234",
    "new_pin": "5678",
    "confirm_new_pin": "5678"
  }'
```

## Staff

### List waitlist entries
```bash
curl http://localhost:8000/api/v1/staff/waitlist \
  -H "Authorization: Bearer $TOKEN"
```

### Call a waitlist entry
```bash
curl -X POST http://localhost:8000/api/v1/staff/waitlist/{id}/call \
  -H "Authorization: Bearer $TOKEN"
```

### Seat a waitlist entry
```bash
curl -X POST http://localhost:8000/api/v1/staff/waitlist/{id}/seat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"table_id": "9c1b2d3e-4f5a-6b7c-8d9e-0f1a2b3c4d5e"}'
```

### Mark no-show
```bash
curl -X POST http://localhost:8000/api/v1/staff/waitlist/{id}/no-show \
  -H "Authorization: Bearer $TOKEN"
```

### Restore no-show entry
```bash
curl -X POST http://localhost:8000/api/v1/staff/waitlist/{id}/restore \
  -H "Authorization: Bearer $TOKEN"
```

### Revert called entry
```bash
curl -X POST http://localhost:8000/api/v1/staff/waitlist/{id}/revert \
  -H "Authorization: Bearer $TOKEN"
```

### Cancel waitlist entry (staff)
```bash
curl -X POST http://localhost:8000/api/v1/staff/waitlist/{id}/cancel \
  -H "Authorization: Bearer $TOKEN"
```

### Edit party size or note
```bash
curl -X POST http://localhost:8000/api/v1/staff/waitlist/{id}/edit \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"party_size": 5, "note": "Needs high chair"}'
```

### Reorder waitlist entries
```bash
curl -X POST http://localhost:8000/api/v1/staff/waitlist/reorder \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"ordered_ids": ["5f7c1a9e-9a7b-4f1e-8e1a-1b2c3d4e5f60", "6a8d2b0f-1b8c-5e2f-9f2b-2c3d4e5f6a71"]}'
```

### List tables
```bash
curl http://localhost:8000/api/v1/staff/tables \
  -H "Authorization: Bearer $TOKEN"
```

### Update table status
```bash
curl -X PATCH http://localhost:8000/api/v1/staff/tables/{id} \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status": "CLEANING"}'
```

### Release table
```bash
curl -X POST http://localhost:8000/api/v1/staff/tables/{id}/release \
  -H "Authorization: Bearer $TOKEN"
```

### Get dashboard stats
```bash
curl http://localhost:8000/api/v1/staff/dashboard \
  -H "Authorization: Bearer $TOKEN"
```

## Admin

### Get settings
```bash
curl http://localhost:8000/api/v1/admin/settings \
  -H "Authorization: Bearer $TOKEN"
```

### Update settings
```bash
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
```

### List all tables
```bash
curl http://localhost:8000/api/v1/admin/tables \
  -H "Authorization: Bearer $TOKEN"
```

### Create table
```bash
curl -X POST http://localhost:8000/api/v1/admin/tables \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "label": "A5",
    "capacity": 2,
    "section": "Patio",
    "sort_order": 5000
  }'
```

### Update table
```bash
curl -X PATCH http://localhost:8000/api/v1/admin/tables/{id} \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "label": "A5",
    "capacity": 4,
    "section": "Patio",
    "is_active": true
  }'
```

### Delete table (soft)
```bash
curl -X DELETE http://localhost:8000/api/v1/admin/tables/{id} \
  -H "Authorization: Bearer $TOKEN"
```

### Reset all data (development only)
```bash
curl -X POST http://localhost:8000/api/v1/admin/reset \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"confirm": "RESET"}'
```

## Health

### Health check
```bash
curl http://localhost:8000/health
```

## Error Examples

Error responses follow this JSON shape:
```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable message",
    "details": {}
  }
}
```

### VALIDATION_ERROR (422)
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Validation failed",
    "details": {
      "fields": { "phone": "Invalid format" }
    }
  }
}
```

### WAITLIST_DUPLICATE_PHONE (409)
```json
{
  "error": {
    "code": "WAITLIST_DUPLICATE_PHONE",
    "message": "Phone already on waitlist",
    "details": { "queue_number": "A001" }
  }
}
```

### WAITLIST_NOT_FOUND (404)
```json
{
  "error": {
    "code": "WAITLIST_NOT_FOUND",
    "message": "Waitlist entry not found",
    "details": {}
  }
}
```

### WAITLIST_INVALID_STATUS (409)
```json
{
  "error": {
    "code": "WAITLIST_INVALID_STATUS",
    "message": "Invalid status for this action",
    "details": {}
  }
}
```

### WAITLIST_CLOSED (409)
```json
{
  "error": {
    "code": "WAITLIST_CLOSED",
    "message": "Waitlist is currently closed",
    "details": {}
  }
}
```

### AUTH_INVALID_PIN (401)
```json
{
  "error": {
    "code": "AUTH_INVALID_PIN",
    "message": "Invalid PIN",
    "details": {}
  }
}
```

### AUTH_TOKEN_EXPIRED (401)
```json
{
  "error": {
    "code": "AUTH_TOKEN_EXPIRED",
    "message": "Session expired. Please log in again.",
    "details": {}
  }
}
```

### TABLE_NOT_FOUND (404)
```json
{
  "error": {
    "code": "TABLE_NOT_FOUND",
    "message": "Table not found",
    "details": {}
  }
}
```

### TABLE_NOT_AVAILABLE (409)
```json
{
  "error": {
    "code": "TABLE_NOT_AVAILABLE",
    "message": "Table is not available",
    "details": {}
  }
}
```

### CONFLICT (409)
```json
{
  "error": {
    "code": "CONFLICT",
    "message": "Conflict with another change",
    "details": {}
  }
}
```

### RATE_LIMITED (429)
```json
{
  "error": {
    "code": "RATE_LIMITED",
    "message": "Too many requests",
    "details": {}
  }
}
```

### INTERNAL_ERROR (500)
```json
{
  "error": {
    "code": "INTERNAL_ERROR",
    "message": "Unhandled error",
    "details": {}
  }
}
```

### BRANCH_NOT_FOUND (404)
```json
{
  "error": {
    "code": "BRANCH_NOT_FOUND",
    "message": "Branch not found",
    "details": {}
  }
}
```
