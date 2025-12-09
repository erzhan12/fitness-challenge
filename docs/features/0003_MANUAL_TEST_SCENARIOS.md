# Feature 0003: Manual Test Scenarios

**Date:** 2025-12-02  
**Purpose:** Manual verification of REST API fixes

---

## Prerequisites

### Environment Setup
1. Application running locally or on test server
2. API accessible at base URL (e.g., `http://localhost:8000`)
3. Valid API key for authenticated endpoints
4. Tool for API testing (curl, Postman, HTTPie, or similar)
5. Database with test data (or ability to create it)

### Required Test Data
You'll need:
- At least 1 active exercise type (e.g., "pushups")
- At least 1 active challenge with a date range
- Several log entries with different dates
- At least 1 exercise type without an active challenge

### Environment Variables
```bash
export API_KEY="your-api-key-here"
export BASE_URL="http://localhost:8000"
```

---

## Scenario 1: Historical Stats with `target_date` Parameter

**Goal:** Verify that stats endpoints correctly filter by target_date and exclude future logs

### Test 1.1: Create Test Data with Past and Future Logs

**Steps:**
1. Create an exercise type:
```bash
curl -X POST "$BASE_URL/api/v1/exercises" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "pushups",
    "display_name": "Push-ups",
    "emoji": "💪",
    "unit": "reps",
    "aliases": ["pushup", "press-up"]
  }'
```

2. Create a 30-day challenge:
```bash
curl -X POST "$BASE_URL/api/v1/challenges" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "exercise_type_id": 1,
    "challenge_name": "30-Day Push-up Challenge",
    "start_date": "2024-12-01",
    "end_date": "2024-12-30",
    "target_total": 1000,
    "daily_target": 33
  }'
```

3. Create logs on different dates:
```bash
# Day 1 (Dec 1) - 50 pushups
curl -X POST "$BASE_URL/api/v1/logs" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "exercise_type_id": 1,
    "count": 50,
    "date": "2024-12-01"
  }'

# Day 5 (Dec 5) - 40 pushups
curl -X POST "$BASE_URL/api/v1/logs" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "exercise_type_id": 1,
    "count": 40,
    "date": "2024-12-05"
  }'

# Day 10 (Dec 10) - 60 pushups
curl -X POST "$BASE_URL/api/v1/logs" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "exercise_type_id": 1,
    "count": 60,
    "date": "2024-12-10"
  }'

# Day 15 (Dec 15) - 55 pushups
curl -X POST "$BASE_URL/api/v1/logs" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "exercise_type_id": 1,
    "count": 55,
    "date": "2024-12-15"
  }'
```

**Total logs:** 
- Through Dec 5: 90 pushups (50 + 40)
- Through Dec 10: 150 pushups (50 + 40 + 60)
- Through Dec 15: 205 pushups (50 + 40 + 60 + 55)

### Test 1.2: Query Stats Without target_date (Current State)

**Steps:**
```bash
curl -X GET "$BASE_URL/api/v1/stats/exercises/1" \
  -H "Content-Type: application/json"
```

**Expected Result:**
```json
{
  "exercise_type_id": 1,
  "exercise_type_name": "Push-ups",
  "cumulative_total": 205,
  "day_number": 15,
  "target_total": 1000,
  "status": "behind",
  ...
}
```

**Verification:**
- ✅ `cumulative_total` should be 205 (all logs)
- ✅ Shows current day number based on today's date

### Test 1.3: Query Stats with target_date = Dec 5

**Steps:**
```bash
curl -X GET "$BASE_URL/api/v1/stats/exercises/1?target_date=2024-12-05" \
  -H "Content-Type: application/json"
```

**Expected Result:**
```json
{
  "exercise_type_id": 1,
  "exercise_type_name": "Push-ups",
  "cumulative_total": 90,
  "day_number": 5,
  "target_total": 1000,
  "today_total": 40,
  ...
}
```

**Verification:**
- ✅ `cumulative_total` should be 90 (excludes Dec 10 and Dec 15 logs)
- ✅ `day_number` should be 5
- ✅ `today_total` should be 40 (the log from Dec 5)
- ❌ If you see 205, the fix is NOT working

### Test 1.4: Query Stats with target_date = Dec 10

**Steps:**
```bash
curl -X GET "$BASE_URL/api/v1/stats/exercises/1?target_date=2024-12-10" \
  -H "Content-Type: application/json"
```

**Expected Result:**
```json
{
  "cumulative_total": 150,
  "day_number": 10,
  "today_total": 60,
  ...
}
```

**Verification:**
- ✅ `cumulative_total` should be 150 (excludes Dec 15 log)
- ✅ `day_number` should be 10
- ✅ `today_total` should be 60

### Test 1.5: Query All Exercises Stats with target_date

**Steps:**
```bash
curl -X GET "$BASE_URL/api/v1/stats/exercises?target_date=2024-12-05" \
  -H "Content-Type: application/json"
```

**Expected Result:**
```json
[
  {
    "exercise_type_id": 1,
    "cumulative_total": 90,
    "day_number": 5,
    ...
  }
]
```

**Verification:**
- ✅ All exercises should respect the target_date filter
- ✅ Historical snapshot is accurate

---

## Scenario 2: Consistent Behavior Between Telegram and REST API

**Goal:** Verify that Telegram bot and REST API return identical stats for the same data

### Test 2.1: Compare Stats via REST API

**Steps:**
```bash
# Create a log via REST API
curl -X POST "$BASE_URL/api/v1/logs" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "exercise_type_id": 1,
    "count": 25,
    "date": "2024-12-16"
  }'

# Get stats via REST API
curl -X GET "$BASE_URL/api/v1/stats/exercises/1" \
  -H "Content-Type: application/json"
```

**Note the values:**
- `cumulative_total`: _______
- `today_total`: _______
- `status`: _______
- `catch_up_reps`: _______

### Test 2.2: Compare Stats via Telegram Bot

**Steps:**
1. Open Telegram and send a message to your bot:
   ```
   25 pushups
   ```

2. Read the response message carefully

**Expected Response Format:**
```
💪 Push-ups: +25 reps
Day 16/30 • Today: 25 • Total: 230/1000
[████░░░░░░] 23%
Need X more to catch up!
```

**Verification:**
- ✅ Day number matches REST API
- ✅ Today's total matches REST API
- ✅ Cumulative total matches REST API
- ✅ Progress percentage matches REST API
- ✅ Catch-up reps match REST API (if behind)
- ❌ If values differ, shared logic is NOT working

### Test 2.3: Test with Multiple Exercises

**Steps:**

1. Create another exercise and challenge
2. Send via Telegram:
   ```
   20 pushups and 30 squats
   ```

3. Query both exercises via REST API:
```bash
curl -X GET "$BASE_URL/api/v1/stats/exercises" \
  -H "Content-Type: application/json"
```

**Verification:**
- ✅ Both exercises show in Telegram response
- ✅ Both exercises show in REST API response
- ✅ All stats match between Telegram and REST API

### Test 2.4: Test Log Deletion Consistency

**Steps:**

1. Get recent logs via Telegram:
   ```
   /recent
   ```

2. Note a log ID from the response

3. Delete via REST API:
```bash
curl -X DELETE "$BASE_URL/api/v1/logs/{LOG_ID}" \
  -H "Authorization: Bearer $API_KEY"
```

4. Check stats via both:
```bash
# REST API
curl -X GET "$BASE_URL/api/v1/stats/exercises/1"

# Telegram
Send any message like "25 pushups" and observe stats
```

**Verification:**
- ✅ Cumulative total decreased by the deleted count
- ✅ Stats match between Telegram and REST API
- ✅ Status recalculated correctly in both

---

## Scenario 3: Parser Fallback for No Active Challenges

**Goal:** Verify that the workout parser works when no challenges are active

### Test 3.1: Setup - Deactivate All Challenges

**Steps:**

1. List all challenges:
```bash
curl -X GET "$BASE_URL/api/v1/challenges" \
  -H "Content-Type: application/json"
```

2. Deactivate each challenge:
```bash
curl -X PATCH "$BASE_URL/api/v1/challenges/{CHALLENGE_ID}" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"is_active": false}'
```

3. Verify no active challenges:
```bash
curl -X GET "$BASE_URL/api/v1/challenges?is_active=true" \
  -H "Content-Type: application/json"
```

**Expected Result:**
```json
[]
```

### Test 3.2: Test Parser with No Active Challenges

**Steps:**
```bash
curl -X POST "$BASE_URL/api/v1/workouts/parse" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "20 pushups and 30 squats"
  }'
```

**Expected Result:**
```json
{
  "entries": [
    {
      "exercise_type_name": "pushups",
      "count": 20,
      "duration_seconds": null,
      "notes": null,
      "confidence": 0.95
    },
    {
      "exercise_type_name": "squats",
      "count": 30,
      "duration_seconds": null,
      "notes": null,
      "confidence": 0.92
    }
  ],
  "is_valid": true,
  "error_reason": null
}
```

**Verification:**
- ✅ Parser successfully recognizes exercises
- ✅ `is_valid` is true
- ✅ Both exercises are parsed correctly
- ❌ If you get an empty entries array or error, fallback is NOT working

### Test 3.3: Test with Various Exercise Types

**Steps:**
```bash
# Test 1: Single exercise
curl -X POST "$BASE_URL/api/v1/workouts/parse" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"text": "50 pushups"}'

# Test 2: Multiple exercises
curl -X POST "$BASE_URL/api/v1/workouts/parse" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"text": "20 pushups, 30 squats, and 2 min plank"}'

# Test 3: Natural language
curl -X POST "$BASE_URL/api/v1/workouts/parse" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"text": "I did 15 pushups this morning"}'
```

**Verification:**
- ✅ All parse requests succeed
- ✅ All return `is_valid: true`
- ✅ Exercises are correctly identified

### Test 3.4: Test Telegram Bot with No Challenges

**Steps:**

1. Open Telegram
2. Send a workout message:
   ```
   25 pushups
   ```

**Expected Behavior:**
- ✅ Bot responds with stats (even without challenge)
- ✅ Shows basic stats (may use defaults)
- ✅ Logs the workout successfully
- ❌ If bot refuses to parse or shows error, fallback is NOT working

### Test 3.5: Reactivate Challenge and Verify

**Steps:**

1. Reactivate a challenge:
```bash
curl -X PATCH "$BASE_URL/api/v1/challenges/{CHALLENGE_ID}" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"is_active": true}'
```

2. Test parser again:
```bash
curl -X POST "$BASE_URL/api/v1/workouts/parse" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"text": "20 pushups"}'
```

**Verification:**
- ✅ Parser still works with active challenges
- ✅ Stats now include challenge context
- ✅ No regression in functionality

---

## Scenario 4: Edge Cases and Error Handling

### Test 4.1: target_date Before Challenge Start

**Steps:**
```bash
# Challenge starts 2024-12-01
curl -X GET "$BASE_URL/api/v1/stats/exercises/1?target_date=2024-11-25" \
  -H "Content-Type: application/json"
```

**Expected Behavior:**
- ✅ Returns stats (may show day_number = 0 or 1)
- ✅ `cumulative_total` should be 0 (no logs before challenge)
- ✅ No server error

### Test 4.2: target_date After Challenge End

**Steps:**
```bash
# Challenge ends 2024-12-30
curl -X GET "$BASE_URL/api/v1/stats/exercises/1?target_date=2025-01-05" \
  -H "Content-Type: application/json"
```

**Expected Behavior:**
- ✅ Returns stats
- ✅ `day_number` clamped to total_days (30)
- ✅ Shows all logs through challenge end

### Test 4.3: Invalid Date Format

**Steps:**
```bash
curl -X GET "$BASE_URL/api/v1/stats/exercises/1?target_date=invalid-date" \
  -H "Content-Type: application/json"
```

**Expected Behavior:**
- ✅ Returns 422 Unprocessable Entity with validation error
- ✅ Clear error message about date format

### Test 4.4: Parser with Empty Text

**Steps:**
```bash
curl -X POST "$BASE_URL/api/v1/workouts/parse" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"text": ""}'
```

**Expected Behavior:**
- ✅ Returns validation error or `is_valid: false`
- ✅ No server crash

### Test 4.5: Parser with No Recognizable Exercises

**Steps:**
```bash
curl -X POST "$BASE_URL/api/v1/workouts/parse" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello world this is not a workout"}'
```

**Expected Behavior:**
- ✅ Returns `is_valid: false`
- ✅ Includes `error_reason` explaining why
- ✅ No server crash

---

## Scenario 5: Performance and Stress Tests

### Test 5.1: Multiple Rapid Requests

**Steps:**
```bash
# Send 10 rapid requests
for i in {1..10}; do
  curl -X GET "$BASE_URL/api/v1/stats/exercises/1?target_date=2024-12-10" &
done
wait
```

**Expected Behavior:**
- ✅ All requests succeed
- ✅ All return consistent data
- ✅ Response time < 1 second per request

### Test 5.2: Large Date Range Query

**Steps:**
```bash
# Query logs over a large date range
curl -X GET "$BASE_URL/api/v1/logs?date_from=2024-01-01&date_to=2024-12-31&limit=100" \
  -H "Content-Type: application/json"
```

**Expected Behavior:**
- ✅ Query completes successfully
- ✅ Returns paginated results
- ✅ Response time reasonable (< 2 seconds)

---

## Test Results Template

Use this template to document your test results:

```markdown
## Test Execution Report

**Date:** ___________
**Tester:** ___________
**Environment:** ___________

### Scenario 1: Historical Stats
- [ ] Test 1.1: Test data created
- [ ] Test 1.2: Current stats correct
- [ ] Test 1.3: target_date=Dec 5 correct (cumulative=90)
- [ ] Test 1.4: target_date=Dec 10 correct (cumulative=150)
- [ ] Test 1.5: All exercises respect target_date

**Issues Found:** ___________

### Scenario 2: Telegram/REST Consistency
- [ ] Test 2.1: REST API stats recorded
- [ ] Test 2.2: Telegram stats match REST
- [ ] Test 2.3: Multiple exercises consistent
- [ ] Test 2.4: Deletion updates consistently

**Issues Found:** ___________

### Scenario 3: Parser Fallback
- [ ] Test 3.1: All challenges deactivated
- [ ] Test 3.2: Parser works with no challenges
- [ ] Test 3.3: Various exercise types parsed
- [ ] Test 3.4: Telegram bot works without challenges
- [ ] Test 3.5: Works after reactivating challenges

**Issues Found:** ___________

### Scenario 4: Edge Cases
- [ ] Test 4.1: Date before challenge start
- [ ] Test 4.2: Date after challenge end
- [ ] Test 4.3: Invalid date format
- [ ] Test 4.4: Parser with empty text
- [ ] Test 4.5: Parser with non-workout text

**Issues Found:** ___________

### Scenario 5: Performance
- [ ] Test 5.1: Multiple rapid requests
- [ ] Test 5.2: Large date range query

**Issues Found:** ___________

### Overall Result
- [ ] ✅ ALL TESTS PASSED - Ready for production
- [ ] ⚠️ MINOR ISSUES - Document and decide
- [ ] ❌ MAJOR ISSUES - Fix before deployment

**Sign-off:** ___________
```

---

## Cleanup

After testing, clean up test data:

```bash
# Delete test logs (if needed)
curl -X DELETE "$BASE_URL/api/v1/logs/{LOG_ID}" \
  -H "Authorization: Bearer $API_KEY"

# Deactivate test challenges (if needed)
curl -X PATCH "$BASE_URL/api/v1/challenges/{CHALLENGE_ID}" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"is_active": false}'
```

---

## Notes for Testers

1. **Use a test database** - Don't run these tests on production data
2. **Document everything** - Screenshot unexpected results
3. **Test both Telegram and REST** - Consistency is key
4. **Check logs** - Review server logs for errors during testing
5. **Reset between scenarios** - Ensure clean state for each test

**Questions?** Contact the development team.


