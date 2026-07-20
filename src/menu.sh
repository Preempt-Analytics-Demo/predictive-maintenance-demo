#!/usr/bin/env bash
# menu.sh — Simple ASCII terminal menu for Predictive Maintenance Demo
# Uses only basic ASCII characters safe for all Docker terminals

# Clear screen
clear

# Display menu
show_menu() {
    echo ""
    echo "========================================"
    echo "  Predictive Maintenance Demo"
    echo "========================================"
    echo ""
    echo "  1. Smoke Test — Verify API is running"
    echo "  2. Full Retraining Loop — Trigger drift detection"
    echo ""
    read -p "  Choose an option (1-2): " choice
    echo
}

# Run smoke test
run_smoke_test() {
    echo ""
    echo "Running smoke test..."
    echo "  Testing API connectivity and basic functionality..."
    echo ""
    docker compose run --rm simulator --mode normal --n-readings 500 --pause
    echo ""
    echo "Smoke test complete!"
}

# Run full retraining loop
run_retraining_loop() {
    echo ""
    echo "Running full retraining loop..."
    echo "  This will take 1-5 minutes. Don't close this window."
    echo ""
    docker compose run --rm simulator --mode sudden-spike --n-readings 1000 --demo && ./open_results.sh
    echo ""
    echo "Retraining loop complete!"
}

# Main menu loop
main_menu() {
    while true; do
        show_menu
        
        case "$choice" in
            1)
                run_smoke_test
                ;;
            2)
                run_retraining_loop
                ;;
            *)
                echo ""
                echo "Invalid option. Please choose 1 or 2."
                echo ""
                ;;
        esac
    done
}

# Run the main menu
main_menu