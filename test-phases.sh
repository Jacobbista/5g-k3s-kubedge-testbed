#!/bin/bash

# 5G Kubernetes Testbed - Phase Testing Script
# 
# This script validates the phased deployment structure and provides utilities
# to inspect individual phases without running the full deployment.
#
# Usage: ./test-phases.sh [option]
#
# Options:
#   validate     - Validate the complete phase structure
#   list         - List all available phases
#   [phase]      - Show information about a specific phase
#   help         - Show this help message
#
# Examples:
#   ./test-phases.sh validate
#   ./test-phases.sh list
#   ./test-phases.sh 01-infrastructure
#   ./test-phases.sh 02-kubernetes

set -e

echo "🚀 5G KUBERNETES TESTBED - PHASE TESTING"
echo "========================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions for colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Verify we're in the correct directory
if [ ! -f "Vagrantfile" ]; then
    print_error "Vagrantfile not found. Run this script from the project root."
    exit 1
fi

# Verify the phased structure exists
if [ ! -d "ansible/phases" ]; then
    print_error "Phased structure not found. Run the reorganization first."
    exit 1
fi

print_status "Phased structure found ✅"

# Function to inspect a specific phase
run_phase() {
    local phase=$1
    local phase_dir="ansible/phases/$phase"
    
    if [ ! -d "$phase_dir" ]; then
        print_error "Phase $phase not found in $phase_dir"
        exit 1
    fi
    
    print_status "Inspecting phase: $phase"
    print_status "Directory: $phase_dir"
    
    # Verify the playbook exists
    if [ ! -f "$phase_dir/playbook.yml" ]; then
        print_error "Playbook not found: $phase_dir/playbook.yml"
        exit 1
    fi
    
    print_success "Playbook found: $phase_dir/playbook.yml"
    
    # Show playbook content
    echo ""
    print_status "Playbook content:"
    echo "----------------------------------------"
    head -20 "$phase_dir/playbook.yml"
    echo "----------------------------------------"
    echo ""
}

# Function to show all available phases
show_phases() {
    print_status "Available phases:"
    echo ""
    for phase_dir in ansible/phases/*/; do
        if [ -d "$phase_dir" ]; then
            phase_name=$(basename "$phase_dir")
            if [ -f "$phase_dir/playbook.yml" ]; then
                echo "  ✅ $phase_name"
            else
                echo "  ❌ $phase_name (missing playbook)"
            fi
        fi
    done
    echo ""
}

# Function to validate the structure
validate_structure() {
    print_status "Validating phased structure..."
    
    local errors=0
    
    # Check required phases
    local required_phases=("01-infrastructure" "02-kubernetes" "03-kubeedge" "04-overlay-network" "05-5g-core" "06-ueransim-mec")
    
    for phase in "${required_phases[@]}"; do
        if [ ! -d "ansible/phases/$phase" ]; then
            print_error "Required phase missing: $phase"
            ((errors++))
        elif [ ! -f "ansible/phases/$phase/playbook.yml" ]; then
            print_error "Missing playbook for phase: $phase"
            ((errors++))
        else
            print_success "Phase $phase: OK"
        fi
    done
    
    # Check main playbook
    if [ ! -f "ansible/phases/00-main-playbook.yml" ]; then
        print_error "Main playbook missing: 00-main-playbook.yml"
        ((errors++))
    else
        print_success "Main playbook: OK"
    fi
    
    # Check main documentation
    if [ ! -f "docs/handbook.md" ]; then
        print_warning "Handbook missing: docs/handbook.md"
    else
        print_success "Handbook: OK"
    fi
    
    if [ $errors -eq 0 ]; then
        print_success "Phased structure is valid ✅"
        return 0
    else
        print_error "Phased structure has $errors errors ❌"
        return 1
    fi
}

# Function to show help
show_help() {
    echo "Usage: $0 [option]"
    echo ""
    echo "Options:"
    echo "  validate     - Validate the phased structure"
    echo "  list         - Show all available phases"
    echo "  [phase]      - Show information about a specific phase"
    echo "  help         - Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 validate"
    echo "  $0 list"
    echo "  $0 01-infrastructure"
    echo "  $0 02-kubernetes"
    echo ""
}

# Main logic
case "${1:-help}" in
    "validate")
        validate_structure
        ;;
    "list")
        show_phases
        ;;
    "help"|"-h"|"--help")
        show_help
        ;;
    *)
        if [[ "$1" =~ ^[0-9][0-9]- ]]; then
            run_phase "$1"
        else
            print_error "Unrecognized option: $1"
            echo ""
            show_help
            exit 1
        fi
        ;;
esac

print_success "Script completed ✅"
