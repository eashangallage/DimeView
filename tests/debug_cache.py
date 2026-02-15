#!/usr/bin/env python3
"""
Debug script to test data loading from Google Sheets
and inspect the actual row structure for June data.

USAGE:
    python tests/debug_cache.py <spreadsheet_id>

Example:
    python tests/debug_cache.py 1ftX8D9wEJ_-tFPRdw8Pz_kR7G0E
"""

import sys
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from dimeview.model import DimeViewModel

def debug_june_data():
    """Load data from spreadsheet and inspect June rows."""
    
    print("=" * 80)
    print("DimeView Debug: Inspecting Cache and Row Data")
    print("=" * 80)
    
    # Get spreadsheet ID from command line
    if len(sys.argv) < 2:
        print("\nERROR: Spreadsheet ID required!")
        print("USAGE: python tests/debug_cache.py <spreadsheet_id>")
        print("\nFind your spreadsheet ID from the Google Sheets URL:")
        print("  https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit")
        return
    
    spreadsheet_id = sys.argv[1]
    
    # Initialize model
    model = DimeViewModel()
    
    # Load data from test worksheet
    print(f"\n[1] Loading data from spreadsheet: {spreadsheet_id}")
    try:
        model.select_spreadsheet(spreadsheet_id)
    except Exception as e:
        print(f"✗ Error loading data: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("✓ Data loaded successfully\n")
    
    # Inspect memory cache
    print("[2] Cache Structure:")
    print(f"Number of sheets in cache: {len(model._memory_cache)}")
    for sheet_title, info in model._memory_cache.items():
        print(f"  - Sheet: '{sheet_title}', Rows: {len(info['rows'])}, Start Row: {info['start_row']}")
    
    # Analyze June data
    print("\n[3] Analyzing June (2025-06) Data:")
    print("-" * 80)
    
    june_rows = []
    for sheet_title, info in model._memory_cache.items():
        for row_idx, row in enumerate(info['rows']):
            if len(row) > 0:
                date_str = row[0] if len(row) > 0 else ""
                if isinstance(date_str, str) and date_str.startswith('2025/06'):
                    june_rows.append((sheet_title, row_idx + 3, row))  # row_idx + 3 because data starts at row 3
    
    print(f"Found {len(june_rows)} June entries\n")
    
    if june_rows:
        # Show first few June rows in detail
        print("First 10 June rows (COLUMN BREAKDOWN):")
        print("-" * 80)
        for idx, (sheet_title, real_row_num, row) in enumerate(june_rows[:10]):
            print(f"\n[Row {real_row_num} in sheet '{sheet_title}'] Total columns: {len(row)}")
            print(f"  Col[0] Date:            '{row[0] if len(row) > 0 else ''}'")
            print(f"  Col[1] Load No:         '{row[1] if len(row) > 1 else ''}'")
            print(f"  Col[2] Driver ID:       '{row[2] if len(row) > 2 else ''}'")
            print(f"  Col[3] Truck ID:        '{row[3] if len(row) > 3 else ''}'")
            print(f"  Col[4] From State:      '{row[4] if len(row) > 4 else ''}'")
            print(f"  Col[5] To State:        '{row[5] if len(row) > 5 else ''}'")
            print(f"  Col[6] Transaction:     '{row[6] if len(row) > 6 else ''}'")
            print(f"  Col[7] Delivery Status: '{row[7] if len(row) > 7 else ''}'")
            print(f"  Col[8] Payment Status:  '{row[8] if len(row) > 8 else ''}'")
            print(f"  Col[9] Credit:          '{row[9] if len(row) > 9 else ''}'")
            print(f"  Col[10] Debit:          '{row[10] if len(row) > 10 else ''}'")
            print(f"  Col[11] Details:        '{row[11] if len(row) > 11 else ''}'")
            
            # Show any extra columns
            if len(row) > 12:
                print(f"  ⚠️  WARNING: Extra columns detected! ({len(row) - 12} extra columns)")
                for i in range(12, min(len(row), 20)):  # Show up to 20 to avoid spam
                    print(f"      Col[{i}] EXTRA: '{row[i]}'")
    
    # Check for data contamination in Transaction field
    print("\n\n[4] CHECKING FOR TRANSACTION FIELD CONTAMINATION:")
    print("-" * 80)
    
    contaminated_rows = []
    for sheet_title, real_row_num, row in june_rows:
        if len(row) > 6:
            trans = str(row[6]).lower()
            # Check if transaction field contains words that should be in other columns
            if any(word in trans for word in ['complete', 'gross', 'dispatch', 'delivered', 'delivered']):
                contaminated_rows.append((real_row_num, row[6]))
    
    if contaminated_rows:
        print(f"✗ Found {len(contaminated_rows)} rows with contaminated Transaction field:\n")
        for real_row_num, trans_value in contaminated_rows[:5]:
            print(f"  Row {real_row_num}: '{trans_value}'")
            print(f"    ^ This should be JUST a transaction type like 'Full Payment', 'Fuel', etc.")
        if len(contaminated_rows) > 5:
            print(f"  ... and {len(contaminated_rows) - 5} more contaminated rows")
    else:
        print("✓ No data contamination detected in Transaction field")
    
    # Test generate_detailed_report
    print("\n\n[5] Testing generate_detailed_report for June 2025:")
    print("-" * 80)
    
    from_date = datetime(2025, 6, 1).date()
    to_date = datetime(2025, 6, 30).date()
    
    report_rows = model.generate_detailed_report(from_date, to_date)
    print(f"Generated report with {len(report_rows)} rows\n")
    
    if report_rows:
        print("Showing first 5 report rows (Transaction field only):")
        for i, row in enumerate(report_rows[:5]):
            load_no = row[1] if len(row) > 1 else ''
            trans = row[6] if len(row) > 6 else ''
            credit = row[9] if len(row) > 9 else ''
            print(f"  Row {i+1} (Load #{load_no}): Trans='{trans}' Credit='{credit}'")
    
    print("\n" + "=" * 80)
    print("Debug complete! Check the output above for issues.")
    print("=" * 80)

if __name__ == '__main__':
    debug_june_data()
