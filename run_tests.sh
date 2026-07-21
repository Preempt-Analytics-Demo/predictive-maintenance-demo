#!/usr/bin/env bash
# run_tests.sh — Menu-driven test runner for Predictive Maintenance Demo

# ANSI color codes for better visual feedback
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Check if Docker is running
check_docker() {
    if ! docker ps > /dev/null 2>&1; then
        echo -e "${RED}❌ Docker is not running. Please start Docker Desktop first.${NC}"
        echo "   Visit: https://www.docker.com/products/docker-desktop/"
        exit 1
    fi
}

# Check if services are running
check_services() {
    if ! docker ps | grep -q "api"; then
        echo -e "${YELLOW}⚠️  Services are not running.${NC}"
        echo -e "${YELLOW}   Starting services...${NC}"
        docker compose up -d
        sleep 2
    fi
}

# Display menu
show_menu() {
    echo ""
    echo "========================================"
    echo -e "${CYAN}  Predictive Maintenance Demo${NC}"
    echo "========================================"
    echo ""
    echo -e "${GREEN}  1${NC}  Smoke Test — Verify API is running"
    echo -e "${GREEN}  2${NC}  Full Retraining Loop — Trigger drift detection"
    echo ""
    read -p -r -n 1 -p "  Choose an option (1-2): " choice
    echo
}

# Run smoke test
run_smoke_test() {
    echo ""
    echo -e "${GREEN}→ Running smoke test...${NC}"
    echo -e "${YELLOW}   Testing API connectivity and basic functionality...${NC}"
    echo ""
    docker compose run --rm simulator --mode normal --n-readings 500 --pause
    echo ""
    echo -e "${GREEN}✓ Smoke test complete!${NC}"
}

# Run full retraining loop
run_retraining_loop() {
    echo ""
    echo -e "${GREEN}→ Running full retraining loop...${NC}"
    echo -e "${YELLOW}   This will take 1-5 minutes. Don't close this window.${NC}"
    echo ""
    docker compose run --rm simulator --mode sudden-spike --n-readings 1000 --demo && ./open_results.sh
    echo ""
    echo -e "${GREEN}✓ Retraining loop complete!${NC}"
}

# Main menu loop
main_menu() {
    while true; do
        show_menu
        
        case "$choice" in
            1)
                check_docker
                run_smoke_test
                ;;
            2)
                check_docker
                check_services
                run_retraining_loop
                ;;
            *)
                echo ""
                echo -e "${RED}❌ Invalid option. Please run ./run_tests.sh and choose 1 or 2.${NC}"
                echo ""
                ;;
        esac
    done
}

# Check if we're on a TTY (interactive terminal)
if [ ! -t 0 ]; then
    echo -e "${YELLOW}⚠️  This script requires an interactive terminal.${NC}"
    echo "   Please run it from your terminal (not piped or redirected)."
    exit 1
fi

# Run the main menu
main_menu