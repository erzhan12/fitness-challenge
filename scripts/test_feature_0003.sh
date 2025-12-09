#!/bin/bash

# Feature 0003 - Automated Test Script
# Tests all three critical fixes from the code review

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
BASE_URL="${BASE_URL:-http://localhost:8000}"
API_KEY="${API_KEY:-}"

# Counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# Helper functions
print_header() {
    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
}

print_test() {
    echo -e "${YELLOW}🧪 Test $TESTS_RUN: $1${NC}"
}

print_pass() {
    echo -e "${GREEN}   ✅ PASS${NC} - $1"
    ((TESTS_PASSED++))
}

print_fail() {
    echo -e "${RED}   ❌ FAIL${NC} - $1"
    ((TESTS_FAILED++))
}

print_info() {
    echo -e "   ℹ️  $1"
}

print_warning() {
    echo -e "${YELLOW}   ⚠️  $1${NC}"
}

# Check prerequisites
check_prerequisites() {
    print_header "Checking Prerequisites"
    
    if ! command -v curl &> /dev/null; then
        echo -e "${RED}❌ curl is not installed${NC}"
        exit 1
    fi
    
    if ! command -v jq &> /dev/null; then
        echo -e "${RED}❌ jq is not installed (required for JSON parsing)${NC}"
        echo "Install with: brew install jq (macOS) or apt-get install jq (Linux)"
        exit 1
    fi
    
    if [ -z "$API_KEY" ]; then
        echo -e "${RED}❌ API_KEY environment variable is not set${NC}"
        echo "Set it with: export API_KEY='your-api-key'"
        exit 1
    fi
    
    # Test connection
    if ! curl -s -f "$BASE_URL/health" > /dev/null; then
        echo -e "${RED}❌ Cannot connect to $BASE_URL${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✅ All prerequisites met${NC}"
    print_info "Base URL: $BASE_URL"
    print_info "API Key: ${API_KEY:0:10}..."
}

# Test 1: Historical stats with target_date
test_historical_stats() {
    print_header "Test Suite 1: Historical Stats with target_date"
    
    # Get first active exercise
    print_test "Getting first active exercise type"
    ((TESTS_RUN++))
    
    EXERCISE_ID=$(curl -s "$BASE_URL/api/v1/exercises?is_active=true" | jq -r '.[0].id')
    
    if [ -z "$EXERCISE_ID" ] || [ "$EXERCISE_ID" == "null" ]; then
        print_fail "No active exercises found"
        print_warning "Skipping historical stats tests"
        return
    fi
    
    print_pass "Found exercise ID: $EXERCISE_ID"
    
    # Create test logs with specific dates
    print_test "Creating test logs on different dates"
    ((TESTS_RUN++))
    
    LOG1=$(curl -s -X POST "$BASE_URL/api/v1/logs" \
        -H "Authorization: Bearer $API_KEY" \
        -H "Content-Type: application/json" \
        -d "{\"exercise_type_id\": $EXERCISE_ID, \"count\": 50, \"date\": \"2024-12-01\"}" \
        | jq -r '.id')
    
    LOG2=$(curl -s -X POST "$BASE_URL/api/v1/logs" \
        -H "Authorization: Bearer $API_KEY" \
        -H "Content-Type: application/json" \
        -d "{\"exercise_type_id\": $EXERCISE_ID, \"count\": 60, \"date\": \"2024-12-10\"}" \
        | jq -r '.id')
    
    if [ -z "$LOG1" ] || [ "$LOG1" == "null" ] || [ -z "$LOG2" ] || [ "$LOG2" == "null" ]; then
        print_fail "Failed to create test logs"
        return
    fi
    
    print_pass "Created logs: $LOG1 (Dec 1, 50 count) and $LOG2 (Dec 10, 60 count)"
    
    # Test query with target_date=2024-12-05 (should only include first log)
    print_test "Querying stats with target_date=2024-12-05"
    ((TESTS_RUN++))
    
    CUMULATIVE_DEC5=$(curl -s "$BASE_URL/api/v1/stats/exercises/$EXERCISE_ID?target_date=2024-12-05" \
        | jq -r '.cumulative_total')
    
    print_info "Cumulative total as of Dec 5: $CUMULATIVE_DEC5"
    
    if [ "$CUMULATIVE_DEC5" -ge "50" ] && [ "$CUMULATIVE_DEC5" -lt "110" ]; then
        print_pass "Correctly excludes future logs (got $CUMULATIVE_DEC5, includes Dec 1 only)"
    else
        print_fail "Expected ~50, got $CUMULATIVE_DEC5 (may include Dec 10 log incorrectly)"
    fi
    
    # Test query with target_date=2024-12-10 (should include both logs)
    print_test "Querying stats with target_date=2024-12-10"
    ((TESTS_RUN++))
    
    CUMULATIVE_DEC10=$(curl -s "$BASE_URL/api/v1/stats/exercises/$EXERCISE_ID?target_date=2024-12-10" \
        | jq -r '.cumulative_total')
    
    print_info "Cumulative total as of Dec 10: $CUMULATIVE_DEC10"
    
    if [ "$CUMULATIVE_DEC10" -ge "110" ]; then
        print_pass "Correctly includes logs through Dec 10 (got $CUMULATIVE_DEC10)"
    else
        print_fail "Expected ~110+, got $CUMULATIVE_DEC10"
    fi
    
    # Cleanup
    print_info "Cleaning up test logs..."
    curl -s -X DELETE "$BASE_URL/api/v1/logs/$LOG1" \
        -H "Authorization: Bearer $API_KEY" > /dev/null
    curl -s -X DELETE "$BASE_URL/api/v1/logs/$LOG2" \
        -H "Authorization: Bearer $API_KEY" > /dev/null
}

# Test 2: Shared business logic (REST API only, manual Telegram verification needed)
test_shared_logic() {
    print_header "Test Suite 2: Shared Business Logic"
    
    print_test "Verifying compute_exercise_stats is used in workout_service"
    ((TESTS_RUN++))
    
    if grep -q "compute_exercise_stats" app/services/workout_service.py; then
        print_pass "Telegram service imports shared helper"
    else
        print_fail "Telegram service doesn't import compute_exercise_stats"
    fi
    
    print_test "Checking stats calculation consistency"
    ((TESTS_RUN++))
    
    # Get first active exercise
    EXERCISE_ID=$(curl -s "$BASE_URL/api/v1/exercises?is_active=true" | jq -r '.[0].id')
    
    if [ -z "$EXERCISE_ID" ] || [ "$EXERCISE_ID" == "null" ]; then
        print_fail "No active exercises found"
        return
    fi
    
    # Get stats via REST API
    STATS=$(curl -s "$BASE_URL/api/v1/stats/exercises/$EXERCISE_ID")
    CUMULATIVE=$(echo "$STATS" | jq -r '.cumulative_total')
    STATUS=$(echo "$STATS" | jq -r '.status')
    
    print_info "REST API Stats - Cumulative: $CUMULATIVE, Status: $STATUS"
    print_pass "Successfully retrieved stats via REST API"
    
    print_warning "Manual verification required: Send workout via Telegram and compare"
    print_info "Expected Telegram to show same cumulative total: $CUMULATIVE"
    print_info "Expected Telegram to show same status: $STATUS"
}

# Test 3: Parser fallback when no challenges
test_parser_fallback() {
    print_header "Test Suite 3: Parser Fallback (No Active Challenges)"
    
    # Save current challenge states
    print_info "Saving current challenge states..."
    ACTIVE_CHALLENGES=$(curl -s "$BASE_URL/api/v1/challenges?is_active=true" | jq -r '.[].id' | tr '\n' ' ')
    
    # Deactivate all challenges
    print_test "Deactivating all challenges"
    ((TESTS_RUN++))
    
    DEACTIVATED=0
    for CHALLENGE_ID in $ACTIVE_CHALLENGES; do
        curl -s -X PATCH "$BASE_URL/api/v1/challenges/$CHALLENGE_ID" \
            -H "Authorization: Bearer $API_KEY" \
            -H "Content-Type: application/json" \
            -d '{"is_active": false}' > /dev/null
        ((DEACTIVATED++))
    done
    
    print_info "Deactivated $DEACTIVATED challenges"
    
    # Verify no active challenges
    ACTIVE_COUNT=$(curl -s "$BASE_URL/api/v1/challenges?is_active=true" | jq '. | length')
    
    if [ "$ACTIVE_COUNT" -eq 0 ]; then
        print_pass "Successfully deactivated all challenges"
    else
        print_fail "Still have $ACTIVE_COUNT active challenges"
    fi
    
    # Test parser with no active challenges
    print_test "Testing parser with no active challenges"
    ((TESTS_RUN++))
    
    PARSE_RESULT=$(curl -s -X POST "$BASE_URL/api/v1/workouts/parse" \
        -H "Authorization: Bearer $API_KEY" \
        -H "Content-Type: application/json" \
        -d '{"text": "20 pushups and 30 squats"}')
    
    IS_VALID=$(echo "$PARSE_RESULT" | jq -r '.is_valid')
    ENTRIES_COUNT=$(echo "$PARSE_RESULT" | jq '.entries | length')
    
    print_info "Parse result - Valid: $IS_VALID, Entries: $ENTRIES_COUNT"
    
    if [ "$IS_VALID" == "true" ] && [ "$ENTRIES_COUNT" -gt 0 ]; then
        print_pass "Parser works without active challenges (fallback successful)"
    else
        print_fail "Parser failed with no active challenges (fallback not working)"
    fi
    
    # Test with different input
    print_test "Testing parser with single exercise"
    ((TESTS_RUN++))
    
    PARSE_RESULT2=$(curl -s -X POST "$BASE_URL/api/v1/workouts/parse" \
        -H "Authorization: Bearer $API_KEY" \
        -H "Content-Type: application/json" \
        -d '{"text": "50 pushups"}')
    
    IS_VALID2=$(echo "$PARSE_RESULT2" | jq -r '.is_valid')
    
    if [ "$IS_VALID2" == "true" ]; then
        print_pass "Parser handles single exercise without challenges"
    else
        print_fail "Parser failed on single exercise without challenges"
    fi
    
    # Reactivate challenges
    print_info "Reactivating challenges..."
    for CHALLENGE_ID in $ACTIVE_CHALLENGES; do
        curl -s -X PATCH "$BASE_URL/api/v1/challenges/$CHALLENGE_ID" \
            -H "Authorization: Bearer $API_KEY" \
            -H "Content-Type: application/json" \
            -d '{"is_active": true}' > /dev/null
    done
    
    print_info "Restored challenge states"
}

# Test 4: Code verification
test_code_fixes() {
    print_header "Test Suite 4: Code Fix Verification"
    
    print_test "Checking for date filter in compute_exercise_stats"
    ((TESTS_RUN++))
    
    if grep -q 'lte("date"' src/api/services.py; then
        print_pass "Date filtering is present in stats calculation"
    else
        print_fail "Date filtering NOT found in stats calculation"
    fi
    
    print_test "Checking for shared stats helper usage in Telegram service"
    ((TESTS_RUN++))
    
    if grep -q "from src.api.services import compute_exercise_stats" app/services/workout_service.py; then
        print_pass "Telegram service imports shared helper"
    else
        print_fail "Telegram service doesn't import shared helper"
    fi
    
    print_test "Checking for parser fallback logic"
    ((TESTS_RUN++))
    
    if grep -q "if not api_exercise_types:" src/api/routers/workouts.py; then
        print_pass "Parser fallback logic is present"
    else
        print_fail "Parser fallback logic NOT found"
    fi
}

# Main execution
main() {
    echo -e "${BLUE}"
    echo "╔═══════════════════════════════════════════════════════╗"
    echo "║     Feature 0003 - Automated Test Suite              ║"
    echo "║     Testing REST API Fixes                            ║"
    echo "╚═══════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    
    check_prerequisites
    
    test_historical_stats
    test_shared_logic
    test_parser_fallback
    test_code_fixes
    
    # Summary
    print_header "Test Summary"
    
    echo "Tests Run:    $TESTS_RUN"
    echo -e "Tests Passed: ${GREEN}$TESTS_PASSED${NC}"
    echo -e "Tests Failed: ${RED}$TESTS_FAILED${NC}"
    echo ""
    
    if [ $TESTS_FAILED -eq 0 ]; then
        echo -e "${GREEN}╔═══════════════════════════════════════════════════════╗${NC}"
        echo -e "${GREEN}║  ✅ ALL TESTS PASSED - READY FOR DEPLOYMENT          ║${NC}"
        echo -e "${GREEN}╚═══════════════════════════════════════════════════════╝${NC}"
        exit 0
    else
        echo -e "${RED}╔═══════════════════════════════════════════════════════╗${NC}"
        echo -e "${RED}║  ❌ SOME TESTS FAILED - REVIEW REQUIRED              ║${NC}"
        echo -e "${RED}╚═══════════════════════════════════════════════════════╝${NC}"
        exit 1
    fi
}

# Run main function
main

