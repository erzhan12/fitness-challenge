#!/bin/bash

# Interactive Manual Testing Guide for Feature 0003
# This script guides you through each test scenario step by step

# Don't exit on errors - we want to handle them gracefully
set +e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
BASE_URL="${BASE_URL:-http://localhost:8001}"
API_KEY="${API_KEY:-}"

# Helper functions
print_header() {
    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
}

print_step() {
    echo -e "\n${CYAN}▶ Step $1: $2${NC}"
    echo -e "${YELLOW}─────────────────────────────────────────────────────${NC}"
}

print_info() {
    echo -e "   ℹ️  $1"
}

print_success() {
    echo -e "   ${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "   ${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "   ${RED}❌ $1${NC}"
}

wait_for_user() {
    echo ""
    read -p "Press ENTER to continue..."
}


# Check if response is valid JSON
is_valid_json() {
    local json="$1"
    if command -v jq &> /dev/null; then
        echo "$json" | jq . > /dev/null 2>&1
        return $?
    else
        # Basic check - starts with { or [
        [[ "$json" =~ ^[{\[] ]]
        return $?
    fi
}

# Safe jq wrapper that handles errors
safe_jq_parse() {
    local json="$1"
    local query="$2"
    
    if ! command -v jq &> /dev/null; then
        return 1
    fi
    
    # Check if it's valid JSON first
    if ! echo "$json" | jq . > /dev/null 2>&1; then
        return 1
    fi
    
    # Try to extract value
    local result=$(echo "$json" | jq -r "$query" 2>/dev/null)
    if [ $? -eq 0 ] && [ "$result" != "null" ] && [ -n "$result" ]; then
        echo "$result"
        return 0
    fi
    
    return 1
}

check_prerequisites() {
    print_header "Checking Prerequisites"
    
    # Check if server is running
    if ! curl -s -f "$BASE_URL/" > /dev/null 2>&1; then
        print_error "Cannot connect to $BASE_URL"
        print_info "Please start the server with: uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload"
        exit 1
    fi
    print_success "Server is running at $BASE_URL"
    
    # Check for API key
    if [ -z "$API_KEY" ]; then
        print_warning "API_KEY environment variable is not set"
        print_info "Checking for .env file..."
        
        if [ -f ".env" ]; then
            # Try to extract ADMIN_API_KEY from .env
            if grep -q "ADMIN_API_KEY=" .env; then
                API_KEY=$(grep "ADMIN_API_KEY=" .env | cut -d '=' -f2 | tr -d '"' | tr -d "'")
                if [ -n "$API_KEY" ]; then
                    print_success "Found API key in .env file"
                    export API_KEY="$API_KEY"
                fi
            fi
        fi
        
        if [ -z "$API_KEY" ]; then
            print_error "Please set API_KEY environment variable"
            print_info "You can set it with: export API_KEY='your-api-key'"
            print_info "Or add ADMIN_API_KEY to your .env file"
            exit 1
        fi
    fi
    
    print_success "API key configured: ${API_KEY:0:10}..."
    
    # Check for jq
    if ! command -v jq &> /dev/null; then
        print_warning "jq is not installed (recommended for JSON parsing)"
        print_info "Install with: brew install jq (macOS) or apt-get install jq (Linux)"
        print_info "Continuing without jq..."
    else
        print_success "jq is installed"
    fi
    
    wait_for_user
}

# Scenario 1: Historical Stats
scenario_1() {
    print_header "Scenario 1: Historical Stats with target_date Parameter"
    
    print_info "Goal: Verify that stats endpoints correctly filter by target_date"
    
    # Test 1.1: Create Test Data
    print_step "1.1" "Create Test Data with Past and Future Logs"
    
    print_info "First, let's check if we have an exercise type..."
    EXERCISES=$(curl -s "$BASE_URL/api/v1/exercises?is_active=true")
    
    if command -v jq &> /dev/null; then
        EXERCISE_COUNT=$(echo "$EXERCISES" | jq '. | length')
        print_info "Found $EXERCISE_COUNT active exercise(s)"
        
        if [ "$EXERCISE_COUNT" -eq 0 ]; then
            print_warning "No active exercises found. Creating one..."
            print_info "Creating exercise type: pushups"
            
            CREATE_EXERCISE=$(curl -s -X POST "$BASE_URL/api/v1/exercises" \
                -H "Authorization: Bearer $API_KEY" \
                -H "Content-Type: application/json" \
                -d '{
                    "name": "pushups",
                    "display_name": "Push-ups",
                    "emoji": "💪",
                    "unit": "reps",
                    "aliases": ["pushup", "press-up"]
                }')
            
            if command -v jq &> /dev/null; then
                EXERCISE_ID=$(echo "$CREATE_EXERCISE" | jq -r '.id')
            else
                EXERCISE_ID=$(echo "$CREATE_EXERCISE" | grep -o '"id":[0-9]*' | head -1 | cut -d':' -f2)
            fi
            
            if [ -n "$EXERCISE_ID" ] && [ "$EXERCISE_ID" != "null" ]; then
                print_success "Created exercise with ID: $EXERCISE_ID"
            else
                print_error "Failed to create exercise"
                echo "$CREATE_EXERCISE"
                wait_for_user
                return
            fi
        else
            EXERCISE_ID=$(echo "$EXERCISES" | jq -r '.[0].id')
            EXERCISE_NAME=$(echo "$EXERCISES" | jq -r '.[0].display_name')
            print_info "Using existing exercise: $EXERCISE_NAME (ID: $EXERCISE_ID)"
        fi
    else
        print_warning "jq not available, please manually check exercises at: $BASE_URL/api/v1/exercises"
        read -p "Enter exercise ID to use: " EXERCISE_ID
    fi
    
    wait_for_user
    
    # Check for active challenge
    print_info "Checking for active challenge..."
    CHALLENGES=$(curl -s "$BASE_URL/api/v1/challenges?is_active=true&exercise_type_id=$EXERCISE_ID")
    
    if command -v jq &> /dev/null; then
        CHALLENGE_COUNT=$(echo "$CHALLENGES" | jq '. | length')
        
        if [ "$CHALLENGE_COUNT" -eq 0 ]; then
            print_warning "No active challenge found. Creating one..."
            print_info "Creating 30-day challenge..."
            
            CREATE_CHALLENGE=$(curl -s -X POST "$BASE_URL/api/v1/challenges" \
                -H "Authorization: Bearer $API_KEY" \
                -H "Content-Type: application/json" \
                -d "{
                    \"exercise_type_id\": $EXERCISE_ID,
                    \"challenge_name\": \"30-Day Push-up Challenge\",
                    \"start_date\": \"2025-12-01\",
                    \"end_date\": \"2025-12-30\",
                    \"target_total\": 1000,
                    \"daily_target\": 33
                }")
            
            CHALLENGE_ID=$(echo "$CREATE_CHALLENGE" | jq -r '.id')
            if [ -n "$CHALLENGE_ID" ] && [ "$CHALLENGE_ID" != "null" ]; then
                print_success "Created challenge with ID: $CHALLENGE_ID"
            else
                print_error "Failed to create challenge"
                echo "$CREATE_CHALLENGE"
            fi
        else
            print_info "Using existing challenge"
        fi
    fi
    
    wait_for_user
    
    # Create test logs
    print_info "Creating test logs on different dates..."
    
    echo ""
    print_info "Creating log for Dec 1 (50 reps)..."
    LOG1=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "$BASE_URL/api/v1/logs" \
        -H "Authorization: Bearer $API_KEY" \
        -H "Content-Type: application/json" \
        -d "{
            \"exercise_type_id\": $EXERCISE_ID,
            \"count\": 50,
            \"date\": \"2025-12-01\"
        }" 2>&1)
    
    HTTP_CODE=$(echo "$LOG1" | grep -o "HTTP_CODE:[0-9]*" | cut -d: -f2)
    LOG1_BODY=$(echo "$LOG1" | sed 's/HTTP_CODE:[0-9]*$//')
    
    if [ "$HTTP_CODE" -ge 200 ] && [ "$HTTP_CODE" -lt 300 ]; then
        if is_valid_json "$LOG1_BODY"; then
            LOG1_ID=$(safe_jq_parse "$LOG1_BODY" '.id')
            if [ -n "$LOG1_ID" ]; then
                print_success "Created log ID: $LOG1_ID"
            else
                print_warning "Log created but couldn't parse ID"
                echo "$LOG1_BODY" | head -3
            fi
        else
            print_error "Server returned non-JSON response (HTTP $HTTP_CODE):"
            echo "$LOG1_BODY" | head -5
            print_warning "This might indicate a server error. Check server logs."
        fi
    else
        print_error "Failed to create log (HTTP $HTTP_CODE):"
        echo "$LOG1_BODY" | head -5
        print_warning "Continuing anyway..."
    fi
    
    echo ""
    print_info "Creating log for Dec 5 (40 reps)..."
    LOG2=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "$BASE_URL/api/v1/logs" \
        -H "Authorization: Bearer $API_KEY" \
        -H "Content-Type: application/json" \
        -d "{
            \"exercise_type_id\": $EXERCISE_ID,
            \"count\": 40,
            \"date\": \"2025-12-05\"
        }" 2>&1)
    
    HTTP_CODE=$(echo "$LOG2" | grep -o "HTTP_CODE:[0-9]*" | cut -d: -f2)
    LOG2_BODY=$(echo "$LOG2" | sed 's/HTTP_CODE:[0-9]*$//')
    
    if [ "$HTTP_CODE" -ge 200 ] && [ "$HTTP_CODE" -lt 300 ]; then
        if is_valid_json "$LOG2_BODY"; then
            LOG2_ID=$(safe_jq_parse "$LOG2_BODY" '.id')
            if [ -n "$LOG2_ID" ]; then
                print_success "Created log ID: $LOG2_ID"
            fi
        else
            print_warning "Non-JSON response (HTTP $HTTP_CODE), continuing..."
        fi
    else
        print_warning "Failed to create log (HTTP $HTTP_CODE), continuing..."
    fi
    
    echo ""
    print_info "Creating log for Dec 10 (60 reps)..."
    LOG3=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "$BASE_URL/api/v1/logs" \
        -H "Authorization: Bearer $API_KEY" \
        -H "Content-Type: application/json" \
        -d "{
            \"exercise_type_id\": $EXERCISE_ID,
            \"count\": 60,
            \"date\": \"2025-12-10\"
        }" 2>&1)
    
    HTTP_CODE=$(echo "$LOG3" | grep -o "HTTP_CODE:[0-9]*" | cut -d: -f2)
    LOG3_BODY=$(echo "$LOG3" | sed 's/HTTP_CODE:[0-9]*$//')
    
    if [ "$HTTP_CODE" -ge 200 ] && [ "$HTTP_CODE" -lt 300 ]; then
        if is_valid_json "$LOG3_BODY"; then
            LOG3_ID=$(safe_jq_parse "$LOG3_BODY" '.id')
            if [ -n "$LOG3_ID" ]; then
                print_success "Created log ID: $LOG3_ID"
            fi
        else
            print_warning "Non-JSON response (HTTP $HTTP_CODE), continuing..."
        fi
    else
        print_warning "Failed to create log (HTTP $HTTP_CODE), continuing..."
    fi
    
    echo ""
    print_info "Creating log for Dec 15 (55 reps)..."
    LOG4=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "$BASE_URL/api/v1/logs" \
        -H "Authorization: Bearer $API_KEY" \
        -H "Content-Type: application/json" \
        -d "{
            \"exercise_type_id\": $EXERCISE_ID,
            \"count\": 55,
            \"date\": \"2025-12-15\"
        }" 2>&1)
    
    HTTP_CODE=$(echo "$LOG4" | grep -o "HTTP_CODE:[0-9]*" | cut -d: -f2)
    LOG4_BODY=$(echo "$LOG4" | sed 's/HTTP_CODE:[0-9]*$//')
    
    if [ "$HTTP_CODE" -ge 200 ] && [ "$HTTP_CODE" -lt 300 ]; then
        if is_valid_json "$LOG4_BODY"; then
            LOG4_ID=$(safe_jq_parse "$LOG4_BODY" '.id')
            if [ -n "$LOG4_ID" ]; then
                print_success "Created log ID: $LOG4_ID"
            fi
        else
            print_warning "Non-JSON response (HTTP $HTTP_CODE), continuing..."
        fi
    else
        print_warning "Failed to create log (HTTP $HTTP_CODE), continuing..."
    fi
    
    print_success "Test data created!"
    print_info "Expected totals:"
    print_info "  - Through Dec 1: 50"
    print_info "  - Through Dec 5: 90 (50 + 40)"
    print_info "  - Through Dec 10 (today): 150 (50 + 40 + 60)"
    print_info "  - Through Dec 15 (future): 205 (50 + 40 + 60 + 55)"
    
    wait_for_user
    
    # Test 1.2: Query without target_date
    print_step "1.2" "Query Stats Without target_date (Current State)"
    
    print_info "Querying: GET $BASE_URL/api/v1/stats/exercises/$EXERCISE_ID"
    STATS_RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" "$BASE_URL/api/v1/stats/exercises/$EXERCISE_ID" 2>&1)
    HTTP_CODE=$(echo "$STATS_RESPONSE" | grep -o "HTTP_CODE:[0-9]*" | cut -d: -f2)
    STATS_CURRENT=$(echo "$STATS_RESPONSE" | sed 's/HTTP_CODE:[0-9]*$//')
    
    echo ""
    if [ "$HTTP_CODE" -ge 200 ] && [ "$HTTP_CODE" -lt 300 ]; then
        if is_valid_json "$STATS_CURRENT"; then
            if command -v jq &> /dev/null; then
                echo "$STATS_CURRENT" | jq '.' 2>/dev/null || echo "$STATS_CURRENT"
                CUMULATIVE=$(safe_jq_parse "$STATS_CURRENT" '.cumulative_total')
                DAY_NUM=$(safe_jq_parse "$STATS_CURRENT" '.day_number')
                
                if [ -n "$CUMULATIVE" ]; then
                    print_info "Cumulative total: $CUMULATIVE"
                    if [ "$CUMULATIVE" -eq 150 ] 2>/dev/null; then
                        print_success "✅ Cumulative total is correct (150 - excludes future logs)"
                    else
                        print_warning "⚠️  Expected 150 (today is Dec 10), got $CUMULATIVE"
                    fi
                fi
                
                if [ -n "$DAY_NUM" ]; then
                    print_info "Day number: $DAY_NUM"
                    if [ "$DAY_NUM" -eq 10 ] 2>/dev/null; then
                        print_success "✅ Day number is correct (10 - today is Dec 10)"
                    else
                        print_warning "⚠️  Expected day 10 (today is Dec 10), got $DAY_NUM"
                    fi
                fi
            else
                echo "$STATS_CURRENT"
                print_info "Please verify: cumulative_total should be 150 (today is Dec 10)"
            fi
        else
            print_error "Invalid JSON response (HTTP $HTTP_CODE):"
            echo "$STATS_CURRENT" | head -10
        fi
    else
        print_error "Request failed (HTTP $HTTP_CODE):"
        echo "$STATS_CURRENT" | head -10
    fi
    
    wait_for_user
    
    # Test 1.3: Query with target_date = Dec 5
    print_step "1.3" "Query Stats with target_date = Dec 5"

    print_info "Querying: GET $BASE_URL/api/v1/stats/exercises/$EXERCISE_ID?target_date=2025-12-05"
    STATS_DEC5=$(curl -s "$BASE_URL/api/v1/stats/exercises/$EXERCISE_ID?target_date=2025-12-05")
    
    echo ""
    if command -v jq &> /dev/null; then
        echo "$STATS_DEC5" | jq '.'
        CUMULATIVE_DEC5=$(echo "$STATS_DEC5" | jq -r '.cumulative_total')
        DAY_NUM_DEC5=$(echo "$STATS_DEC5" | jq -r '.day_number')
        TODAY_DEC5=$(echo "$STATS_DEC5" | jq -r '.today_total // 0')
        
        print_info "Cumulative total as of Dec 5: $CUMULATIVE_DEC5"
        print_info "Day number: $DAY_NUM_DEC5"
        print_info "Today total: $TODAY_DEC5"
        
        if [ "$CUMULATIVE_DEC5" -eq 90 ]; then
            print_success "✅ Cumulative total is correct (90)"
        elif [ "$CUMULATIVE_DEC5" -ge 50 ] && [ "$CUMULATIVE_DEC5" -lt 110 ]; then
            print_warning "⚠️  Got $CUMULATIVE_DEC5 (should be 90, but excludes future logs)"
        else
            print_error "❌ Expected ~90, got $CUMULATIVE_DEC5 (may include future logs incorrectly)"
        fi
        
        if [ "$DAY_NUM_DEC5" -eq 5 ]; then
            print_success "✅ Day number is correct (5)"
        else
            print_warning "⚠️  Expected day 5, got $DAY_NUM_DEC5"
        fi
    else
        echo "$STATS_DEC5"
        print_info "Please verify: cumulative_total should be 90, day_number should be 5"
    fi
    
    wait_for_user
    
    # Test 1.4: Query with target_date = Dec 10
    print_step "1.4" "Query Stats with target_date = Dec 10"

    print_info "Querying: GET $BASE_URL/api/v1/stats/exercises/$EXERCISE_ID?target_date=2025-12-10"
    STATS_DEC10=$(curl -s "$BASE_URL/api/v1/stats/exercises/$EXERCISE_ID?target_date=2025-12-10")
    
    echo ""
    if command -v jq &> /dev/null; then
        echo "$STATS_DEC10" | jq '.'
        CUMULATIVE_DEC10=$(echo "$STATS_DEC10" | jq -r '.cumulative_total')
        DAY_NUM_DEC10=$(echo "$STATS_DEC10" | jq -r '.day_number')
        TODAY_DEC10=$(echo "$STATS_DEC10" | jq -r '.today_total // 0')
        
        print_info "Cumulative total as of Dec 10: $CUMULATIVE_DEC10"
        print_info "Day number: $DAY_NUM_DEC10"
        print_info "Today total: $TODAY_DEC10"
        
        if [ "$CUMULATIVE_DEC10" -eq 150 ]; then
            print_success "✅ Cumulative total is correct (150)"
        elif [ "$CUMULATIVE_DEC10" -ge 110 ]; then
            print_warning "⚠️  Got $CUMULATIVE_DEC10 (should be 150, but includes logs through Dec 10)"
        else
            print_error "❌ Expected ~150, got $CUMULATIVE_DEC10"
        fi
        
        if [ "$DAY_NUM_DEC10" -eq 10 ]; then
            print_success "✅ Day number is correct (10)"
        else
            print_warning "⚠️  Expected day 10, got $DAY_NUM_DEC10"
        fi
    else
        echo "$STATS_DEC10"
        print_info "Please verify: cumulative_total should be 150, day_number should be 10"
    fi
    
    wait_for_user
    
    # Test 1.5: Query all exercises
    print_step "1.5" "Query All Exercises Stats with target_date"

    print_info "Querying: GET $BASE_URL/api/v1/stats/exercises?target_date=2025-12-05"
    STATS_ALL=$(curl -s "$BASE_URL/api/v1/stats/exercises?target_date=2025-12-05")
    
    echo ""
    if command -v jq &> /dev/null; then
        echo "$STATS_ALL" | jq '.'
        print_info "Verify all exercises respect the target_date filter"
    else
        echo "$STATS_ALL"
        print_info "Please verify all exercises show correct historical stats"
    fi
    
    print_success "Scenario 1 complete!"
    wait_for_user
}

# Scenario 2: Telegram/REST Consistency
scenario_2() {
    print_header "Scenario 2: Consistent Behavior Between Telegram and REST API"
    
    print_info "Goal: Verify that Telegram bot and REST API return identical stats"
    print_warning "This scenario requires manual Telegram testing"
    
    print_step "2.1" "Compare Stats via REST API"
    
    # Get first exercise
    EXERCISES=$(curl -s "$BASE_URL/api/v1/exercises?is_active=true")
    if command -v jq &> /dev/null; then
        EXERCISE_ID=$(echo "$EXERCISES" | jq -r '.[0].id')
        EXERCISE_NAME=$(echo "$EXERCISES" | jq -r '.[0].display_name')
        print_info "Using exercise: $EXERCISE_NAME (ID: $EXERCISE_ID)"
    else
        read -p "Enter exercise ID: " EXERCISE_ID
    fi
    
    print_info "Creating a test log via REST API..."
    LOG=$(curl -s -X POST "$BASE_URL/api/v1/logs" \
        -H "Authorization: Bearer $API_KEY" \
        -H "Content-Type: application/json" \
        -d "{
            \"exercise_type_id\": $EXERCISE_ID,
            \"count\": 25,
            \"date\": \"2025-12-16\"
        }")
    
    if command -v jq &> /dev/null; then
        LOG_ID=$(echo "$LOG" | jq -r '.id')
        print_success "Created log ID: $LOG_ID"
    fi
    
    print_info "Getting stats via REST API..."
    STATS=$(curl -s "$BASE_URL/api/v1/stats/exercises/$EXERCISE_ID")
    
    echo ""
    if command -v jq &> /dev/null; then
        echo "$STATS" | jq '.'
        CUMULATIVE=$(echo "$STATS" | jq -r '.cumulative_total')
        TODAY=$(echo "$STATS" | jq -r '.today_total // 0')
        STATUS=$(echo "$STATS" | jq -r '.status')
        CATCH_UP=$(echo "$STATS" | jq -r '.catch_up_reps // 0')
        
        print_info "REST API Stats:"
        print_info "  - Cumulative total: $CUMULATIVE"
        print_info "  - Today total: $TODAY"
        print_info "  - Status: $STATUS"
        print_info "  - Catch-up reps: $CATCH_UP"
    else
        echo "$STATS"
    fi
    
    wait_for_user
    
    print_step "2.2" "Compare Stats via Telegram Bot"
    
    print_warning "MANUAL STEP REQUIRED"
    print_info "1. Open Telegram and send a message to your bot:"
    print_info "   25 pushups"
    print_info ""
    print_info "2. Read the response message carefully"
    print_info "3. Compare the values with REST API stats above"
    print_info ""
    print_info "Expected format:"
    print_info "  💪 Push-ups: +25 reps"
    print_info "  Day 16/30 • Today: 25 • Total: XXX/1000"
    print_info "  [████░░░░░░] XX%"
    print_info "  Need X more to catch up!"
    
    wait_for_user
    
    print_step "2.3" "Test with Multiple Exercises"
    
    print_warning "MANUAL STEP REQUIRED"
    print_info "1. Send via Telegram:"
    print_info "   20 pushups and 30 squats"
    print_info ""
    print_info "2. Query both exercises via REST API:"
    print_info "   curl -X GET \"$BASE_URL/api/v1/stats/exercises\""
    print_info ""
    print_info "3. Compare values between Telegram and REST API"
    
    wait_for_user
    
    print_step "2.4" "Test Log Deletion Consistency"
    
    print_info "Getting recent logs..."
    LOGS=$(curl -s "$BASE_URL/api/v1/logs?limit=5")
    
    if command -v jq &> /dev/null; then
        echo "$LOGS" | jq '.data[0:3]'
        LOG_ID=$(echo "$LOGS" | jq -r '.data[0].id // empty')
        
        if [ -n "$LOG_ID" ] && [ "$LOG_ID" != "null" ]; then
            print_info "Found log ID: $LOG_ID"
            read -p "Delete this log? (y/n): " DELETE_CONFIRM
            
            if [ "$DELETE_CONFIRM" = "y" ]; then
                print_info "Deleting log via REST API..."
                DELETE_RESULT=$(curl -s -X DELETE "$BASE_URL/api/v1/logs/$LOG_ID" \
                    -H "Authorization: Bearer $API_KEY")
                print_success "Log deleted"
                
                print_info "Check stats via both REST API and Telegram"
                print_info "Both should show updated cumulative totals"
            fi
        fi
    else
        echo "$LOGS"
        print_info "Please manually delete a log and verify consistency"
    fi
    
    print_success "Scenario 2 complete!"
    wait_for_user
}

# Scenario 3: Parser Fallback
scenario_3() {
    print_header "Scenario 3: Parser Fallback for No Active Challenges"
    
    print_info "Goal: Verify that the workout parser works when no challenges are active"
    
    print_step "3.1" "Setup - Deactivate All Challenges"
    
    print_info "Listing all active challenges..."
    ACTIVE_CHALLENGES=$(curl -s "$BASE_URL/api/v1/challenges?is_active=true")
    
    if command -v jq &> /dev/null; then
        CHALLENGE_IDS=$(echo "$ACTIVE_CHALLENGES" | jq -r '.[].id')
        CHALLENGE_COUNT=$(echo "$ACTIVE_CHALLENGES" | jq '. | length')
        
        print_info "Found $CHALLENGE_COUNT active challenge(s)"
        
        if [ "$CHALLENGE_COUNT" -gt 0 ]; then
            print_warning "Deactivating all challenges..."
            for CHALLENGE_ID in $CHALLENGE_IDS; do
                curl -s -X PATCH "$BASE_URL/api/v1/challenges/$CHALLENGE_ID" \
                    -H "Authorization: Bearer $API_KEY" \
                    -H "Content-Type: application/json" \
                    -d '{"is_active": false}' > /dev/null
                print_info "Deactivated challenge ID: $CHALLENGE_ID"
            done
            
            # Verify
            ACTIVE_COUNT=$(curl -s "$BASE_URL/api/v1/challenges?is_active=true" | jq '. | length')
            if [ "$ACTIVE_COUNT" -eq 0 ]; then
                print_success "All challenges deactivated"
            else
                print_error "Still have $ACTIVE_COUNT active challenges"
            fi
        else
            print_info "No active challenges found"
        fi
    else
        print_warning "jq not available. Please manually deactivate challenges"
        print_info "Visit: $BASE_URL/api/v1/challenges"
    fi
    
    wait_for_user
    
    print_step "3.2" "Test Parser with No Active Challenges"
    
    print_info "Testing parser with: '20 pushups and 30 squats'"
    PARSE_RESULT=$(curl -s -X POST "$BASE_URL/api/v1/workouts/parse" \
        -H "Authorization: Bearer $API_KEY" \
        -H "Content-Type: application/json" \
        -d '{"text": "20 pushups and 30 squats"}')
    
    echo ""
    if command -v jq &> /dev/null; then
        echo "$PARSE_RESULT" | jq '.'
        IS_VALID=$(echo "$PARSE_RESULT" | jq -r '.is_valid')
        ENTRIES_COUNT=$(echo "$PARSE_RESULT" | jq '.entries | length')
        
        if [ "$IS_VALID" = "true" ] && [ "$ENTRIES_COUNT" -gt 0 ]; then
            print_success "✅ Parser works without active challenges (fallback successful)"
        else
            print_error "❌ Parser failed with no active challenges (fallback not working)"
        fi
    else
        echo "$PARSE_RESULT"
        print_info "Please verify: is_valid should be true, entries should not be empty"
    fi
    
    wait_for_user
    
    print_step "3.3" "Test with Various Exercise Types"
    
    print_info "Test 1: Single exercise"
    PARSE1=$(curl -s -X POST "$BASE_URL/api/v1/workouts/parse" \
        -H "Authorization: Bearer $API_KEY" \
        -H "Content-Type: application/json" \
        -d '{"text": "50 pushups"}')
    
    if command -v jq &> /dev/null; then
        IS_VALID1=$(echo "$PARSE1" | jq -r '.is_valid')
        if [ "$IS_VALID1" = "true" ]; then
            print_success "✅ Single exercise parsed"
        else
            print_error "❌ Failed to parse single exercise"
        fi
    fi
    
    echo ""
    print_info "Test 2: Multiple exercises"
    PARSE2=$(curl -s -X POST "$BASE_URL/api/v1/workouts/parse" \
        -H "Authorization: Bearer $API_KEY" \
        -H "Content-Type: application/json" \
        -d '{"text": "20 pushups, 30 squats, and 2 min plank"}')
    
    if command -v jq &> /dev/null; then
        IS_VALID2=$(echo "$PARSE2" | jq -r '.is_valid')
        ENTRIES2=$(echo "$PARSE2" | jq '.entries | length')
        if [ "$IS_VALID2" = "true" ] && [ "$ENTRIES2" -gt 0 ]; then
            print_success "✅ Multiple exercises parsed ($ENTRIES2 entries)"
        else
            print_error "❌ Failed to parse multiple exercises"
        fi
    fi
    
    echo ""
    print_info "Test 3: Natural language"
    PARSE3=$(curl -s -X POST "$BASE_URL/api/v1/workouts/parse" \
        -H "Authorization: Bearer $API_KEY" \
        -H "Content-Type: application/json" \
        -d '{"text": "I did 15 pushups this morning"}')
    
    if command -v jq &> /dev/null; then
        IS_VALID3=$(echo "$PARSE3" | jq -r '.is_valid')
        if [ "$IS_VALID3" = "true" ]; then
            print_success "✅ Natural language parsed"
        else
            print_error "❌ Failed to parse natural language"
        fi
    fi
    
    wait_for_user
    
    print_step "3.4" "Test Telegram Bot with No Challenges"
    
    print_warning "MANUAL STEP REQUIRED"
    print_info "1. Open Telegram"
    print_info "2. Send a workout message:"
    print_info "   25 pushups"
    print_info ""
    print_info "Expected: Bot should respond with stats (even without challenge)"
    print_info "If bot refuses to parse or shows error, fallback is NOT working"
    
    wait_for_user
    
    print_step "3.5" "Reactivate Challenge and Verify"
    
    print_info "Reactivating challenges..."
    if command -v jq &> /dev/null; then
        ALL_CHALLENGES=$(curl -s "$BASE_URL/api/v1/challenges")
        CHALLENGE_IDS=$(echo "$ALL_CHALLENGES" | jq -r '.[].id')
        
        for CHALLENGE_ID in $CHALLENGE_IDS; do
            curl -s -X PATCH "$BASE_URL/api/v1/challenges/$CHALLENGE_ID" \
                -H "Authorization: Bearer $API_KEY" \
                -H "Content-Type: application/json" \
                -d '{"is_active": true}' > /dev/null
        done
        print_success "Challenges reactivated"
    else
        print_info "Please manually reactivate challenges"
    fi
    
    print_info "Testing parser again with active challenges..."
    PARSE_FINAL=$(curl -s -X POST "$BASE_URL/api/v1/workouts/parse" \
        -H "Authorization: Bearer $API_KEY" \
        -H "Content-Type: application/json" \
        -d '{"text": "20 pushups"}')
    
    if command -v jq &> /dev/null; then
        IS_VALID_FINAL=$(echo "$PARSE_FINAL" | jq -r '.is_valid')
        if [ "$IS_VALID_FINAL" = "true" ]; then
            print_success "✅ Parser still works with active challenges"
        else
            print_error "❌ Parser broken after reactivating challenges"
        fi
    fi
    
    print_success "Scenario 3 complete!"
    wait_for_user
}

# Scenario 4: Edge Cases
scenario_4() {
    print_header "Scenario 4: Edge Cases and Error Handling"
    
    # Get exercise ID
    EXERCISES=$(curl -s "$BASE_URL/api/v1/exercises?is_active=true")
    if command -v jq &> /dev/null; then
        EXERCISE_ID=$(echo "$EXERCISES" | jq -r '.[0].id')
    else
        read -p "Enter exercise ID: " EXERCISE_ID
    fi
    
    print_step "4.1" "target_date Before Challenge Start"

    print_info "Querying: GET $BASE_URL/api/v1/stats/exercises/$EXERCISE_ID?target_date=2025-11-25"
    RESULT=$(curl -s "$BASE_URL/api/v1/stats/exercises/$EXERCISE_ID?target_date=2025-11-25")
    
    if command -v jq &> /dev/null; then
        echo "$RESULT" | jq '.'
        CUMULATIVE=$(echo "$RESULT" | jq -r '.cumulative_total')
        if [ "$CUMULATIVE" -eq 0 ]; then
            print_success "✅ Returns 0 for dates before challenge start"
        else
            print_warning "⚠️  Got $CUMULATIVE (expected 0)"
        fi
    else
        echo "$RESULT"
    fi
    
    wait_for_user
    
    print_step "4.2" "target_date After Challenge End"
    
    print_info "Querying: GET $BASE_URL/api/v1/stats/exercises/$EXERCISE_ID?target_date=2025-01-05"
    RESULT=$(curl -s "$BASE_URL/api/v1/stats/exercises/$EXERCISE_ID?target_date=2025-01-05")
    
    if command -v jq &> /dev/null; then
        echo "$RESULT" | jq '.'
        print_info "Verify day_number is clamped to total_days"
    else
        echo "$RESULT"
    fi
    
    wait_for_user
    
    print_step "4.3" "Invalid Date Format"
    
    print_info "Querying with invalid date: GET $BASE_URL/api/v1/stats/exercises/$EXERCISE_ID?target_date=invalid-date"
    RESULT=$(curl -s -w "\nHTTP Status: %{http_code}\n" "$BASE_URL/api/v1/stats/exercises/$EXERCISE_ID?target_date=invalid-date")
    
    echo "$RESULT"
    print_info "Expected: 422 Unprocessable Entity with validation error"
    
    wait_for_user
    
    print_step "4.4" "Parser with Empty Text"
    
    print_info "Testing parser with empty text..."
    RESULT=$(curl -s -X POST "$BASE_URL/api/v1/workouts/parse" \
        -H "Authorization: Bearer $API_KEY" \
        -H "Content-Type: application/json" \
        -d '{"text": ""}')
    
    if command -v jq &> /dev/null; then
        echo "$RESULT" | jq '.'
        print_info "Expected: validation error or is_valid: false"
    else
        echo "$RESULT"
    fi
    
    wait_for_user
    
    print_step "4.5" "Parser with No Recognizable Exercises"
    
    print_info "Testing parser with non-workout text..."
    RESULT=$(curl -s -X POST "$BASE_URL/api/v1/workouts/parse" \
        -H "Authorization: Bearer $API_KEY" \
        -H "Content-Type: application/json" \
        -d '{"text": "Hello world this is not a workout"}')
    
    if command -v jq &> /dev/null; then
        echo "$RESULT" | jq '.'
        IS_VALID=$(echo "$RESULT" | jq -r '.is_valid')
        if [ "$IS_VALID" = "false" ]; then
            print_success "✅ Returns is_valid: false for non-workout text"
        else
            print_warning "⚠️  Expected is_valid: false"
        fi
    else
        echo "$RESULT"
    fi
    
    print_success "Scenario 4 complete!"
    wait_for_user
}

# Scenario 5: Performance
scenario_5() {
    print_header "Scenario 5: Performance and Stress Tests"
    
    EXERCISES=$(curl -s "$BASE_URL/api/v1/exercises?is_active=true")
    if command -v jq &> /dev/null; then
        EXERCISE_ID=$(echo "$EXERCISES" | jq -r '.[0].id')
    else
        read -p "Enter exercise ID: " EXERCISE_ID
    fi
    
    print_step "5.1" "Multiple Rapid Requests"
    
    print_info "Sending 10 rapid requests..."
    START_TIME=$(date +%s)

    for i in {1..10}; do
        curl -s "$BASE_URL/api/v1/stats/exercises/$EXERCISE_ID?target_date=2025-12-10" > /dev/null &
    done
    wait
    
    END_TIME=$(date +%s)
    ELAPSED=$((END_TIME - START_TIME))
    
    print_info "Completed 10 requests in ${ELAPSED} seconds"
    if [ "$ELAPSED" -lt 5 ]; then
        print_success "✅ Performance is good (< 1 second per request)"
    else
        print_warning "⚠️  Requests took longer than expected"
    fi
    
    wait_for_user
    
    print_step "5.2" "Large Date Range Query"
    
    print_info "Querying logs over large date range..."
    START_TIME=$(date +%s)

    RESULT=$(curl -s "$BASE_URL/api/v1/logs?date_from=2025-01-01&date_to=2025-12-31&limit=100")
    
    END_TIME=$(date +%s)
    ELAPSED=$((END_TIME - START_TIME))
    
    if command -v jq &> /dev/null; then
        COUNT=$(echo "$RESULT" | jq '.data | length')
        print_info "Retrieved $COUNT logs in ${ELAPSED} seconds"
    else
        print_info "Query completed in ${ELAPSED} seconds"
    fi
    
    if [ "$ELAPSED" -lt 2 ]; then
        print_success "✅ Query completed quickly"
    else
        print_warning "⚠️  Query took longer than expected"
    fi
    
    print_success "Scenario 5 complete!"
    wait_for_user
}

# Main menu
main() {
    clear
    echo -e "${BLUE}"
    echo "╔═══════════════════════════════════════════════════════╗"
    echo "║     Feature 0003 - Manual Testing Guide              ║"
    echo "║     Step-by-Step Interactive Testing                  ║"
    echo "╚═══════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    
    check_prerequisites
    
    while true; do
        clear
        echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${BLUE}Select a Scenario to Test:${NC}"
        echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo ""
        echo "  1) Scenario 1: Historical Stats with target_date"
        echo "  2) Scenario 2: Telegram/REST Consistency"
        echo "  3) Scenario 3: Parser Fallback (No Active Challenges)"
        echo "  4) Scenario 4: Edge Cases and Error Handling"
        echo "  5) Scenario 5: Performance and Stress Tests"
        echo "  6) Run All Scenarios"
        echo "  0) Exit"
        echo ""
        read -p "Enter choice [0-6]: " choice
        
        case $choice in
            1) scenario_1 ;;
            2) scenario_2 ;;
            3) scenario_3 ;;
            4) scenario_4 ;;
            5) scenario_5 ;;
            6)
                scenario_1
                scenario_2
                scenario_3
                scenario_4
                scenario_5
                ;;
            0)
                print_header "Testing Complete!"
                print_info "Thank you for testing Feature 0003"
                exit 0
                ;;
            *)
                print_error "Invalid choice"
                sleep 1
                ;;
        esac
    done
}

# Run main function
main
