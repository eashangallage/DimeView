#!/usr/bin/env python3
"""
model.py

Model component for MoneyMirror application.
Handles Google Sheets API integration, offline cache, and data operations.
"""
import json
import csv
import time
from pathlib import Path
from datetime import datetime, date
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import sys
import re

from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

from pdfrw import PdfReader
from pdfrw.buildxobj import pagexobj
from pdfrw.toreportlab import makerl


def _parse_amount(s: str) -> float:
    """
    Turn a string like '$1,274.00' or '1274.00' into a float.
    Treat empty or malformed values as 0.0.
    """
    if not s:
        return 0.0
    clean = s.replace('$', '').replace(',', '').strip()
    try:
        return float(clean)
    except ValueError:
        return 0.0
    

def resource_path(relative_path):
    """
    Return a path to a resource located relative to the executable/script.
    Ignores PyInstaller internal temp folder (sys._MEIPASS).
    """

    if getattr(sys, 'frozen', False):
        # Running as PyInstaller executable
        base_path = Path(sys.executable).parent
    else:
        # Running as script
        base_path = Path(__file__).parent

    return base_path / relative_path


class GoogleQuotaExceededError(Exception):
    """Custom exception for Google Sheets API quota exceeded errors."""
    pass


class MoneyMirrorModel:
    """Handles data logic: Google Sheets API and offline cache."""

    SCOPES = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://spreadsheets.google.com/feeds',
        'https://www.googleapis.com/auth/drive'
    ]

    CREDS_PATH = resource_path('config/MoneyMirrorCreds.json')
    CACHE_PATH = resource_path('cache/offline_cache.json')

    # Column indexes based on updated sheet layout (1-based)
    HEADER_IDX = {
        'date': 1,
        'load_no': 2,
        'driver_id': 3,
        'truck_id': 4,
        'from_state': 5,
        'to_state': 6,
        'transaction': 7,
        'delivery_status': 8,
        'payment_status': 9,
        'credit': 10,
        'debit': 11,
        'details': 12
    }

    TRANSACTION_TYPES = [
        'Fuel', 'Dispatch', 'Miscellaneous Income', 'Cash Advance',
        'Maintenance', 'LayOver', 'Toll', 'Lumper', 'Insurance',
        'Partial Payment', 'Full Payment', 'Balance Carried', 'Other'
    ]

    # List of US state abbreviations and names for dropdowns
    US_STATES = [
        'AL: Alabama', 'AK: Alaska', 'AZ: Arizona', 'AR: Arkansas', 'CA: California',
        'CO: Colorado', 'CT: Connecticut', 'DE: Delaware', 'FL: Florida', 'GA: Georgia',
        'HI: Hawaii', 'ID: Idaho', 'IL: Illinois', 'IN: Indiana', 'IA: Iowa',
        'KS: Kansas', 'KY: Kentucky', 'LA: Louisiana', 'ME: Maine', 'MD: Maryland',
        'MA: Massachusetts', 'MI: Michigan', 'MN: Minnesota', 'MS: Mississippi', 'MO: Missouri',
        'MT: Montana', 'NE: Nebraska', 'NV: Nevada', 'NH: New Hampshire', 'NJ: New Jersey',
        'NM: New Mexico', 'NY: New York', 'NC: North Carolina', 'ND: North Dakota', 'OH: Ohio',
        'OK: Oklahoma', 'OR: Oregon', 'PA: Pennsylvania', 'RI: Rhode Island', 'SC: South Carolina',
        'SD: South Dakota', 'TN: Tennessee', 'TX: Texas', 'UT: Utah', 'VT: Vermont',
        'VA: Virginia', 'WA: Washington', 'WV: West Virginia', 'WI: Wisconsin', 'WY: Wyoming'
    ]

    DELIVERY_STATUS_OPTIONS = ['Upcoming', 'In Progress', 'Completed']
    PAYMENT_STATUS_OPTIONS = ['Incomplete', 'Complete']

    def __init__(self):
        self.CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        creds = self._load_credentials()
        self.sheets_service = build('sheets', 'v4', credentials=creds)
        self.drive_service = build('drive', 'v3', credentials=creds)
        self.spreadsheet_id = None
        self.spreadsheet_metadata = None
        self.cache = self._load_cache()
        # In-memory, ephemeral cache (cleared on app close)
        self._memory_cache = {}   # { sheet_title: { 'rows': [...], 'start_row': 3 } }
        self._index = {}          # { load_no: [ (sheet_title, row_num), ... ] }

    def _load_credentials(self):
        if not self.CREDS_PATH.exists():
            raise FileNotFoundError(f"Credentials file not found at {self.CREDS_PATH}")
        return Credentials.from_service_account_file(
            str(self.CREDS_PATH), scopes=self.SCOPES
        )

    def _load_cache(self):
        if self.CACHE_PATH.exists():
            with open(self.CACHE_PATH, 'r') as f:
                return json.load(f)
        return {'sheets': {}, 'last_sync': None}

    def _save_cache(self):
        with open(self.CACHE_PATH, 'w') as f:
            json.dump(self.cache, f, indent=2, default=str)

    def _execute_with_retry(self, func, max_retries=3, base_delay=1):
        """
        Execute a Google API call function with retry on quota errors.
        func: callable that runs the API call and returns result.
        """
        for attempt in range(max_retries):
            try:
                return func()
            except HttpError as e:
                if e.resp.status == 429:
                    wait = base_delay * (2 ** attempt)
                    # print(f"Quota exceeded. Waiting {wait}s before retry...")
                    time.sleep(wait)
                else:
                    raise
        # After retries exhausted
        raise GoogleQuotaExceededError("Google Sheets API quota exceeded. Please wait a moment and try again.")

    def list_spreadsheets(self):
        query = "mimeType='application/vnd.google-apps.spreadsheet'"
        resp = self._execute_with_retry(lambda: self.drive_service.files().list(
            q=query, fields='files(id,name)', pageSize=100
        ).execute())
        return [{'id': f['id'], 'name': f['name']} for f in resp.get('files', [])]

    def select_spreadsheet(self, spreadsheet_id):
        self.spreadsheet_id = spreadsheet_id
        meta = self._execute_with_retry(lambda: self.sheets_service.spreadsheets().get(
            spreadsheetId=spreadsheet_id,
            includeGridData=False
        ).execute())
        self.spreadsheet_metadata = meta
        # Build in-memory cache + index of every load_no → (sheet, row)
        self._memory_cache.clear()
        self._index.clear()
        
        # Regex for 'Mmm YYYY' format (e.g. 'Jan 2026', 'Dec 2025')
        sheet_pattern = re.compile(r'^[A-Z][a-z]{2}\s\d{4}$')
        
        for sheet in meta.get('sheets', []):
            title = sheet['properties']['title']
            
            # Skip if not a valid month/year sheet
            if not sheet_pattern.match(title):
                continue
                
            resp = self._execute_with_retry(lambda: 
                self.sheets_service.spreadsheets().values().get(
                    spreadsheetId=spreadsheet_id,
                    range=f"'{title}'!A3:L"
                ).execute()
            )
            rows = resp.get('values', [])
            self._memory_cache[title] = {'rows': rows, 'start_row': 3}
            # index by load_no
            for i, row in enumerate(rows):
                if len(row) > self.HEADER_IDX['load_no'] - 1:
                    ln = row[self.HEADER_IDX['load_no'] - 1]
                    if ln:
                        real_row = 3 + i
                        self._index.setdefault(ln, []).append((title, real_row))

    def get_client_email(self) -> str:
        with open(self.CREDS_PATH, 'r') as f:
            creds = json.load(f)
            return creds.get('client_email')

    def get_transaction_types(self):
        return self.TRANSACTION_TYPES.copy()

    def get_delivery_status_options(self):
        return self.DELIVERY_STATUS_OPTIONS.copy()

    def get_payment_status_options(self):
        return self.PAYMENT_STATUS_OPTIONS.copy()

    def get_us_states(self):
        return self.US_STATES.copy()
    
    def format_state_input(self, state_input: str) -> str:
        """
        Convert user input (abbreviation or partial name) to full format.
        Examples:
            'AL' -> 'AL: Alabama'
            'CA' -> 'CA: California'
            'california' -> 'CA: California'
        Returns the formatted state string if found, otherwise returns input unchanged.
        """
        state_input = state_input.strip().upper()
        if not state_input:
            return ''
        
        # Try to find by exact abbreviation match first (e.g., 'AL')
        for state in self.US_STATES:
            abbr = state.split(':')[0].strip()
            if abbr == state_input:
                return state
        
        # Try to find by state name (case-insensitive)
        for state in self.US_STATES:
            parts = state.split(':')
            abbr = parts[0].strip()
            name = parts[1].strip().upper()
            if name.startswith(state_input) or state_input in name:
                return state
        
        # If not found, return original input (will be caught by validation)
        return state_input.title() if state_input else ''
    
    def get_header_indices(self):
        return list(self.HEADER_IDX.keys())

    def get_all_load_nos(self):
        # Build from in-memory rows
        ids = set()
        for info in self._memory_cache.values():
            for row in info['rows']:
                if len(row) > self.HEADER_IDX['load_no']-1:
                    ids.add(row[self.HEADER_IDX['load_no']-1])
        # Filter out empty and "Other", then sort by numeric value
        filtered_ids = [x for x in ids if x and x != "Other"]
        # Sort by numeric value (convert to int for proper ordering)
        sorted_ids = sorted(filtered_ids, key=lambda x: int(x) if x.isdigit() else float('inf'))
        return sorted_ids

    def get_all_driver_ids(self):
        # Build from in-memory rows
        ids = set()
        for info in self._memory_cache.values():
            for row in info['rows']:
                if len(row) > self.HEADER_IDX['driver_id']-1:
                    ids.add(row[self.HEADER_IDX['driver_id']-1])
        lst = sorted(filter(None, ids))
        return lst

    def get_all_truck_ids(self):
        # Build from in-memory rows
        ids = set()
        for info in self._memory_cache.values():
            for row in info['rows']:
                if len(row) > self.HEADER_IDX['truck_id']-1:
                    ids.add(row[self.HEADER_IDX['truck_id']-1])
        lst = sorted(filter(None, ids))
        lst.append('Other')
        return lst

    def _ensure_trash_sheet(self):
        """Ensures a 'Trash' sheet exists, creating it from Template if missing."""
        has_trash = any(s['properties']['title'] == 'Trash' for s in self.spreadsheet_metadata['sheets'])
        if not has_trash:
            self._duplicate_template('Trash')

    def delete_entry(self, sheet_name, row_num, row_data):
        """
        Soft-delete an entry:
        1. Move to 'Trash' sheet.
        2. Delete from original sheet.
        3. Recalculate fractions if needed.
        """
        # 1. Archive to Trash
        self._ensure_trash_sheet()
        
        # We need to clean the row data to ensure it matches the 12 columns + extra
        # row_data might have metadata columns at the end, so slice to header length
        cleaned_row = list(row_data[:12])
        
        # Ensure it has 12 columns padded
        while len(cleaned_row) < 12:
            cleaned_row.append('')
            
        trash_range = "Trash!A3"
        self._execute_with_retry(lambda: self.sheets_service.spreadsheets().values().append(
            spreadsheetId=self.spreadsheet_id,
            range=trash_range,
            valueInputOption='USER_ENTERED',
            insertDataOption='OVERWRITE',
            body={'values': [cleaned_row]}
        ).execute())
        
        # 2. Delete from original sheet
        # Find sheetId for the sheet_name
        sheet_id = next(
            s['properties']['sheetId']
            for s in self.spreadsheet_metadata['sheets']
            if s['properties']['title'] == sheet_name
        )
        
        # Rows are 0-indexed in batchUpdate deleteDimension
        # row_num is 1-based (from Sheets UI / our cache logic)
        delete_idx = row_num - 1
        
        self._execute_with_retry(lambda: self.sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=self.spreadsheet_id,
            body={'requests': [
                {'deleteDimension': {
                    'range': {
                        'sheetId': sheet_id,
                        'dimension': 'ROWS',
                        'startIndex': delete_idx,
                        'endIndex': delete_idx + 1
                    }
                }}
            ]}
        ).execute())
        
        # 3. Update Cache (Invalidate/Reload is safest)
        # But for performance and consistency we should try to update it.
        # Actually, simpler to just force a full reload of that month's cache next time
        # or remove it now.
        if sheet_name in self._memory_cache:
            # We simply remove the specific row from the list
            rows = self._memory_cache[sheet_name]['rows']
            start_row = self._memory_cache[sheet_name]['start_row']
            
            # The index in the list is:
            list_idx = row_num - start_row
            
            if 0 <= list_idx < len(rows):
                del rows[list_idx]
                
                # IMPORTANT: Since we deleted a row, all rows AFTER this one
                # in the sheet have shifted up by 1.
                # Our metadata (start_row) remains same, so subsequent calculations
                # for row indices (start_row + i) work fine for the *new* list state.
                # However, if we had other cached indices (like self._index), they are now wrong.
                
                # So we must rebuild the index for this load_no
                # Or easier: just clear the main index and rebuild lazily or now.
                self._index = {}
        
        # 4. Handle Fraction Recalculation
        ln_idx = self.HEADER_IDX['load_no'] - 1
        transaction_idx = self.HEADER_IDX['transaction'] - 1
        
        load_no = cleaned_row[ln_idx] if len(cleaned_row) > ln_idx else None
        transaction = cleaned_row[transaction_idx] if len(cleaned_row) > transaction_idx else ''
        
        # If we deleted a credit entry (income) for a load, we must update the fraction
        if load_no and transaction != 'Fraction':
            self._recalculate_fraction(load_no)
                     
    def _recalculate_fraction(self, load_no):
        """
        Recalculate and update the Fraction entry for a given Load No.
        This is the single source of truth for fraction logic.
        """
        if not load_no or load_no == 'Other':
            return

        # 1. Find existing fraction entry and its location
        # Scan all months in cache
        fraction_loc = None  # (sheet_name, row_idx_in_list, row_data)
        
        ln_idx = self.HEADER_IDX['load_no'] - 1
        transaction_idx = self.HEADER_IDX['transaction'] - 1
        
        for m_title, m_info in self._memory_cache.items():
            rows = m_info['rows']
            for i, r in enumerate(rows):
                if (len(r) > transaction_idx and r[transaction_idx] == 'Fraction' and
                    len(r) > ln_idx and str(r[ln_idx]) == str(load_no)):
                    fraction_loc = (m_title, i, r)
                    break
            if fraction_loc:
                break
        
        if not fraction_loc:
            # If no fraction entry exists, we can't update it.
            # (Creation logic is handled in append_entry for new entries)
            return

        sheet_name_frac, list_idx_frac, fraction_row = fraction_loc
        
        # 2. Determine the Fraction Percentage to use
        # We try to extract it from the 'Details' column of the fraction row (e.g. "Fraction 3.5%...")
        details_idx = self.HEADER_IDX['details'] - 1
        details_text = fraction_row[details_idx] if len(fraction_row) > details_idx else ""
        
        fraction_percent = 3.5 # Default

        match = re.search(r'Fraction\s+(\d+(?:\.\d+)?)%', details_text)
        if match:
            fraction_percent = float(match.group(1))
        
        # 3. Calculate Total Credit for this Load No across ALL sheets
        total_credit = 0.0
        credit_idx = self.HEADER_IDX['credit'] - 1
        
        for m_title, m_info in self._memory_cache.items():
            for r in m_info['rows']:
                # Skip the fraction row itself to avoid circular math (though it should have 0 credit)
                if (len(r) > transaction_idx and r[transaction_idx] == 'Fraction'):
                    continue
                
                if (len(r) > ln_idx and str(r[ln_idx]) == str(load_no)):
                    if len(r) > credit_idx:
                        total_credit += _parse_amount(str(r[credit_idx]))

        # 4. Calculate New Debit Amount
        # new_debit = total_credit * (fraction_percent / 100.0)
        new_debit = round(total_credit * (fraction_percent / 100.0), 2)

        
        # 5. Update the Fraction Row in local cache
        debit_idx = self.HEADER_IDX['debit'] - 1
        
        # Ensure row is long enough
        while len(fraction_row) < 12:
            fraction_row.append('')
            
        fraction_row[debit_idx] = str(new_debit)
        
        # Update cache reference
        self._memory_cache[sheet_name_frac]['rows'][list_idx_frac] = fraction_row
        
        # 6. Push Update to Google Sheet
        # Calculate actual row number
        actual_row_num = self._memory_cache[sheet_name_frac]['start_row'] + list_idx_frac
        range_name = f"'{sheet_name_frac}'!A{actual_row_num}:L{actual_row_num}"
        
        # We send the whole row update
        self._execute_with_retry(lambda: self.sheets_service.spreadsheets().values().update(
            spreadsheetId=self.spreadsheet_id,
            range=range_name,
            valueInputOption='USER_ENTERED',
            body={'values': [fraction_row]}
        ).execute())

    def _create_template_sheet(self):
        """Creates the Template sheet if it's missing."""
        # Add new sheet properties
        requests = [
            {'addSheet': {'properties': {'title': 'Template'}}}
        ]
        
        response = self._execute_with_retry(lambda: self.sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=self.spreadsheet_id,
            body={'requests': requests}
        ).execute())
        
        new_sheet_id = response['replies'][0]['addSheet']['properties']['sheetId']

        # Configure formatting and content
        headers = [
            'Date', 'Load No.', 'Driver ID', 'Truck ID', 'From State', 'To State',
            'Transaction', 'Delivery Status', 'Payment Status', 'Credit', 'Debit', 'More Details'
        ]
        
        update_requests = []
        
        # 1. Merge A1:L1
        update_requests.append({
            'mergeCells': {
                'range': {
                    'sheetId': new_sheet_id,
                    'startRowIndex': 0, 'endRowIndex': 1,
                    'startColumnIndex': 0, 'endColumnIndex': 12
                },
                'mergeType': 'MERGE_ALL'
            }
        })
        
        # 2. Main Table Headers and Title
        rows_data = []
        # Row 1 (A1: Merged Title)
        rows_data.append({
            'values': [{'userEnteredValue': {'stringValue': 'Monthly Revenue Sheet'}}]
        })
        # Row 2 (Headers)
        header_cells = [{'userEnteredValue': {'stringValue': h}} for h in headers]
        rows_data.append({'values': header_cells})

        update_requests.append({
            'updateCells': {
                'start': {'sheetId': new_sheet_id, 'rowIndex': 0, 'columnIndex': 0},
                'rows': rows_data,
                'fields': 'userEnteredValue'
            }
        })
        
        # 3. Summary Section Values and Formulas (N1:P2)
        summary_rows = [
            {'values': [
                {'userEnteredValue': {'stringValue': 'Total Income'}},
                {'userEnteredValue': {'stringValue': 'Total Expense'}},
                {'userEnteredValue': {'stringValue': 'Net'}}
            ]},
            {'values': [
                {'userEnteredValue': {'formulaValue': '=SUM(INDIRECT("J3:J200"))'}},
                {'userEnteredValue': {'formulaValue': '=SUM(INDIRECT("K3:K200"))'}},
                {'userEnteredValue': {'formulaValue': '=N2-O2'}}
            ]}
        ]
        
        update_requests.append({
            'updateCells': {
                'start': {'sheetId': new_sheet_id, 'rowIndex': 0, 'columnIndex': 13}, # Col N is index 13
                'rows': summary_rows,
                'fields': 'userEnteredValue'
            }
        })

        # 4. Formatting - Background Color for Summary (Light Yellow 3)
        light_yellow = {'red': 1.0, 'green': 0.949, 'blue': 0.8}
        borders = {
             "top": {"style": "SOLID"},
             "bottom": {"style": "SOLID"},
             "left": {"style": "SOLID"},
             "right": {"style": "SOLID"}
        }

        update_requests.append({
            'repeatCell': {
                'range': {
                    'sheetId': new_sheet_id,
                    'startRowIndex': 0, 'endRowIndex': 2,
                    'startColumnIndex': 13, 'endColumnIndex': 16
                },
                'cell': {'userEnteredFormat': {'backgroundColor': light_yellow, "borders": borders}},
                'fields': 'userEnteredFormat(backgroundColor,borders)'
            }
        })

        # 5. Borders and Layout for Data Table (A1:L200)
        # Apply borders to data rows (A2:L200)
        update_requests.append({
            'repeatCell': {
                'range': {
                    'sheetId': new_sheet_id,
                    'startRowIndex': 1, 'endRowIndex': 200,
                    'startColumnIndex': 0, 'endColumnIndex': 12
                },
                'cell': {'userEnteredFormat': {"borders": borders}},
                'fields': 'userEnteredFormat(borders)'
            }
        })
        
        # Style Title (A1)
        update_requests.append({
             'repeatCell': {
                'range': {
                    'sheetId': new_sheet_id,
                    'startRowIndex': 0, 'endRowIndex': 1,
                    'startColumnIndex': 0, 'endColumnIndex': 1
                },
                'cell': {
                    'userEnteredFormat': {
                        'horizontalAlignment': 'CENTER',
                        'textFormat': {'bold': True, 'fontSize': 12},
                        "borders": borders
                    }
                },
                'fields': 'userEnteredFormat(horizontalAlignment,textFormat,borders)'
            }
        })
        
        # Bold Headers (Row 2)
        update_requests.append({
             'repeatCell': {
                'range': {
                    'sheetId': new_sheet_id,
                    'startRowIndex': 1, 'endRowIndex': 2,
                    'startColumnIndex': 0, 'endColumnIndex': 12
                },
                'cell': {
                    'userEnteredFormat': {
                        'textFormat': {'bold': True},
                         "borders": borders
                    }
                },
                'fields': 'userEnteredFormat(textFormat,borders)'
            }
        })

        self._execute_with_retry(lambda: self.sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=self.spreadsheet_id,
            body={'requests': update_requests}
        ).execute())

    def _duplicate_template(self, new_title):
        # Check if 'Template' exists
        source_sheet = next(
            (s for s in self.spreadsheet_metadata['sheets'] if s['properties']['title'] == 'Template'),
            None
        )

        if not source_sheet:
            self._create_template_sheet()
            # Refresh metadata to get the new 'Template' sheet info
            meta = self._execute_with_retry(lambda: self.sheets_service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id,
                includeGridData=False
            ).execute())
            self.spreadsheet_metadata = meta
            source_sheet = next(
                s for s in self.spreadsheet_metadata['sheets']
                if s['properties']['title'] == 'Template'
            )
        
        source_id = source_sheet['properties']['sheetId']

        # Step 1: Duplicate the Template sheet. The correct formulas are already on it.
        self._execute_with_retry(lambda: self.sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=self.spreadsheet_id,
            body={'requests': [
                {'duplicateSheet': {'sourceSheetId': source_id, 'newSheetName': new_title}}
            ]}
        ).execute())

        # Step 2: Refresh metadata (the formulas are already correct from the duplication)
        meta = self._execute_with_retry(lambda: self.sheets_service.spreadsheets().get(
            spreadsheetId=self.spreadsheet_id,
            includeGridData=False
        ).execute())
        self.spreadsheet_metadata = meta

    def _propagate_status(
        self, load_no, delivery_status, payment_status,
        driver_id=None, truck_id=None, from_state=None, to_state=None
    ):
        updates = []
        
        # We need to scan all loaded data because _index might not cover all cases
        # or might be slightly out of sync if we relied solely on it.
        # But for performance _index is preferred.
        # Let's ensure _index is robust or fallback to scan if needed.
        # Actually, let's just make sure we check `_index` is being populated correctly.
        # It is populated on `select_spreadsheet` (initial load) and `append_entry`.
        
        occurrences = self._index.get(load_no, [])

        # If _index is empty but we have load_no, it might be that validation failed earlier
        # OR we just added the very first entry (which is in the index now via append_entry).
        
        for title, row_num in occurrences:
            # Check if this row actually exists in cache before queuing update to avoid errors
            # (e.g. if row was deleted but index not fully cleared, though delete_entry clears index)
            if title not in self._memory_cache: continue
            
            # 1) Propagate driver/truck/from/to if passed
            # We must be careful not to overwrite with empty strings if the user didn't Intent to change them.
            # However, the controller passes current values from the form.
            # If the user leaves them blank in the form, they ARE blank.
            
            # The issue might be that batchUpdate (values().batchUpdate) expects 'data' list.
            
            # Let's also update the in-memory cache to keep it in sync!
            # Otherwise subsequent operations in this session will see old data.
            
            cache_row_idx = row_num - self._memory_cache[title]['start_row']
            if 0 <= cache_row_idx < len(self._memory_cache[title]['rows']):
                 row = self._memory_cache[title]['rows'][cache_row_idx]
                 
                 # Update memory first
                 if driver_id is not None: row[self.HEADER_IDX['driver_id']-1] = driver_id
                 if truck_id is not None: row[self.HEADER_IDX['truck_id']-1] = truck_id
                 if from_state is not None: row[self.HEADER_IDX['from_state']-1] = from_state
                 if to_state is not None: row[self.HEADER_IDX['to_state']-1] = to_state
                 
                 row[self.HEADER_IDX['delivery_status']-1] = delivery_status
                 row[self.HEADER_IDX['payment_status']-1] = payment_status
                 
                 self._memory_cache[title]['rows'][cache_row_idx] = row

            if any([driver_id, truck_id, from_state, to_state]):
                vals = [
                    driver_id or '',
                    truck_id or '',
                    from_state or '',
                    to_state or ''
                ]
                updates.append({
                    'range': f"'{title}'!C{row_num}:F{row_num}",
                    'values': [vals]
                })
            # 2) Propagate delivery/payment
            updates.append({
                'range': f"'{title}'!H{row_num}:I{row_num}",
                'values': [[delivery_status, payment_status]]
            })
            
        if updates:
            body = {'valueInputOption': 'USER_ENTERED', 'data': updates}
            self._execute_with_retry(lambda: 
                self.sheets_service.spreadsheets().values()
                    .batchUpdate(spreadsheetId=self.spreadsheet_id, body=body)
                    .execute()
            )

    def _delete_fraction_entries(self, load_no, month_title):
        """Delete all Fraction entries for a load in the given month."""
        try:
            # Get all rows for this sheet
            rows = self._memory_cache.get(month_title, {}).get('rows', [])
            if not rows:
                return
            
            # Find rows to delete (those with Transaction='Fraction' and matching load_no)
            rows_to_delete = []
            ln_idx = self.HEADER_IDX['load_no'] - 1
            transaction_idx = self.HEADER_IDX['transaction'] - 1
            
            for i, row in enumerate(rows):
                if (len(row) > ln_idx and len(row) > transaction_idx and
                    row[ln_idx] == load_no and row[transaction_idx] == 'Fraction'):
                    actual_row_num = self._memory_cache[month_title]['start_row'] + i
                    rows_to_delete.append(actual_row_num)
            
            # Delete rows in reverse order to maintain correct row numbers
            for row_num in sorted(rows_to_delete, reverse=True):
                self._execute_with_retry(lambda rn=row_num: 
                    self.sheets_service.spreadsheets().batchUpdate(
                        spreadsheetId=self.spreadsheet_id,
                        body={'requests': [
                            {'deleteDimension': {
                                'range': {
                                    'sheetId': self._get_sheet_id(month_title),
                                    'dimension': 'ROWS',
                                    'startIndex': rn - 1,
                                    'endIndex': rn
                                }
                            }}
                        ]}
                    ).execute()
                )
        except Exception:
            # Silently fail - if deletion fails, we'll just create duplicate
            pass

    def _get_sheet_id(self, sheet_title):
        """Get the sheet ID for a given sheet title."""
        if self.spreadsheet_metadata:
            for sheet in self.spreadsheet_metadata.get('sheets', []):
                if sheet['properties']['title'] == sheet_title:
                    return sheet['properties']['sheetId']
        return None
    
    def _find_fraction_entry_row(self, load_no, month_title):
        """Find the row number of an existing Fraction entry for a load in the given month."""
        try:
            rows = self._memory_cache.get(month_title, {}).get('rows', [])
            if not rows:
                return None
            
            ln_idx = self.HEADER_IDX['load_no'] - 1
            transaction_idx = self.HEADER_IDX['transaction'] - 1
            
            for i, row in enumerate(rows):
                if (len(row) > ln_idx and len(row) > transaction_idx and
                    row[ln_idx] == load_no and row[transaction_idx] == 'Fraction'):
                    actual_row_num = self._memory_cache[month_title]['start_row'] + i
                    return actual_row_num
            
            return None
        except Exception:
            return None
    
    def _get_load_total_credit(self, load_no, month_title):
        """Calculate total credit amount for a load across all months."""
        total_credit = 0.0
        try:
            # Use the index to find all occurrences of this load across all sheets
            occurrences = self._index.get(load_no, [])
            
            # If no index entry (e.g. new load), fall back to checking current month only
            if not occurrences:
                rows = self._memory_cache.get(month_title, {}).get('rows', [])
                occurrences = [(month_title, self._memory_cache[month_title]['start_row'] + i) 
                               for i, _ in enumerate(rows)]

            ln_idx = self.HEADER_IDX['load_no'] - 1
            credit_idx = self.HEADER_IDX['credit'] - 1
            trans_idx = self.HEADER_IDX['transaction'] - 1
            
            for sheet_title, row_num in occurrences:
                # Get the row from cache
                cache_entry = self._memory_cache.get(sheet_title)
                if not cache_entry:
                    continue
                    
                rows = cache_entry['rows']
                start_row = cache_entry['start_row']
                idx = row_num - start_row
                
                if 0 <= idx < len(rows):
                    row = rows[idx]
                    
                    # Verify load no matches (should match if coming from index)
                    if len(row) > ln_idx and str(row[ln_idx]) == str(load_no):
                        # Skip Fraction entries to avoid double counting or circular logic
                        if len(row) > trans_idx and row[trans_idx] == 'Fraction':
                            continue
                            
                        if len(row) > credit_idx:
                            total_credit += _parse_amount(str(row[credit_idx]))
        except Exception:
            pass
        return total_credit

    def _update_fraction_entry(self, load_no, month_title, date_val, driver_id, truck_id, 
                               from_state, to_state, delivery_status, payment_status, 
                               fraction_percent, details):
        """Update existing Fraction entry or return False if not found."""
        row_num = self._find_fraction_entry_row(load_no, month_title)
        if row_num is None:
            return False
        
        try:
            # Calculate new total debit based on total credits for this load
            total_credit = self._get_load_total_credit(load_no, month_title)
            new_total_debit = total_credit * (fraction_percent / 100.0)

            # Build the updated fraction row
            load_cell = load_no if load_no else ''
            fraction_row = [
                date_val.strftime('%Y/%m/%d'),
                load_cell,
                driver_id or '',
                truck_id or '',
                from_state or '',
                to_state or '',
                'Fraction',
                delivery_status,
                payment_status,
                '',  # No credit for fraction
                str(new_total_debit) if new_total_debit else '',  # Debit column
                details or ''
            ]
            
            # Update the row in Google Sheets
            sheet_name = month_title
            range_name = f"{sheet_name}!A{row_num}:L{row_num}"
            
            self._execute_with_retry(lambda: self.sheets_service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range=range_name,
                valueInputOption='USER_ENTERED',
                body={'values': [fraction_row]}
            ).execute())
            
            # Update memory cache
            rows = self._memory_cache[month_title]['rows']
            cache_idx = row_num - self._memory_cache[month_title]['start_row']
            if 0 <= cache_idx < len(rows):
                rows[cache_idx] = fraction_row
            
            return True
        except Exception:
            return False

    def append_entry(
        self, date, load_no, driver_id, truck_id, from_state, to_state,
        transaction, delivery_status, payment_status,
        credit_amt, debit_amt, details, fraction_percent=3.5
    ):
        # Adjust for two-digit year entries (e.g. '25' -> 2025)
        if date.year < 100:
            date = date.replace(year=date.year + 2000)
        if credit_amt and debit_amt:
            raise ValueError(
                'Provide only one of Credit or Debit for Balance Carried.'
            )
        # Validation for Balance Carried
        if transaction == 'Balance Carried':
            if not credit_amt and not debit_amt:
                raise ValueError(
                    'For Balance Carried, provide either Credit or Debit amount.'
                )
        # Automatic payment status for Full Payment
        if transaction == 'Full Payment':
            payment_status = 'Complete'
        # Determine sheet name (e.g. 'Dec 2025')
        month_title = date.strftime('%b %Y')
        if month_title not in [
            s['properties']['title'] for s in self.spreadsheet_metadata['sheets']
        ]:
            self._duplicate_template(month_title)
        # Prefix Load No. with apostrophe so Sheets treats it as text
        load_cell = f"{load_no}" if load_no else ''
        # Build row in updated column order A:L
        row = [
            date.strftime('%Y/%m/%d'),
            load_cell,
            driver_id or '',
            truck_id or '',
            from_state or '',
            to_state or '',
            transaction,
            delivery_status,
            payment_status,
            str(credit_amt) if credit_amt else '',
            str(debit_amt) if debit_amt else '',
            details or ''
        ]
        rng = f"'{month_title}'!A3"
        # Append new entry
        result = self._execute_with_retry(lambda: self.sheets_service.spreadsheets().values().append(
            spreadsheetId=self.spreadsheet_id,
            range=rng,
            valueInputOption='USER_ENTERED',  # keep currency formatting
            insertDataOption='OVERWRITE', # This prevents copying formatting from the row above
            body={'values': [row]}
        ).execute())
        
        # Update cache with new row immediately so fraction calculation can see it
        title = month_title
        entry_rows = self._memory_cache.setdefault(title, {'rows': [], 'start_row': 3})['rows']
        entry_rows.append(row)
        new_row_num = self._memory_cache[title]['start_row'] + len(entry_rows) - 1
        if load_no:
            self._index.setdefault(load_no, []).append((title, new_row_num))
        
        fraction_created = False
        # If there's a credit amount and we have a load_no, ensure a Fraction entry exists
        if load_no and credit_amt and transaction not in ['Fraction'] and fraction_percent is not None:
            
            # Check if Fraction entry exists for this load in ANY loaded sheet
            fraction_exists = False
            fraction_loc = None
            ln_idx = self.HEADER_IDX['load_no'] - 1
            tr_idx = self.HEADER_IDX['transaction'] - 1
            
            for m_title, info in self._memory_cache.items():
                for i, r in enumerate(info['rows']):
                    if (len(r) > tr_idx and r[tr_idx] == 'Fraction' and 
                        len(r) > ln_idx and str(r[ln_idx]) == str(load_no)):
                            fraction_exists = True
                            fraction_loc = (m_title, i, r)
                            break
                if fraction_exists: break

            if not fraction_exists:
                # Create a placeholder Fraction row
                # _recalculate_fraction will fill in the Debit amount
                
                # Format details strictly so _recalculate scans it correctly
                frac_details = f"Fraction {fraction_percent}%"
                
                fraction_row = [
                    date.strftime('%Y/%m/%d'),
                    load_cell,
                    driver_id or '',
                    truck_id or '',
                    from_state or '',
                    to_state or '',
                    'Fraction',
                    delivery_status,
                    payment_status,
                    '',  # Credit
                    '',  # Debit - to be filled by recalc
                    frac_details
                ]
                
                # Use same range as the append above (it just appends to bottom)
                self._execute_with_retry(lambda: self.sheets_service.spreadsheets().values().append(
                    spreadsheetId=self.spreadsheet_id,
                    range=rng,
                    valueInputOption='USER_ENTERED',
                    insertDataOption='OVERWRITE',
                    body={'values': [fraction_row]}
                ).execute())
                
                # Add to local cache manually so Recalc finds it immediately
                entry_rows.append(fraction_row)
                fraction_created = True
            
            elif fraction_loc:
                # Check provided fraction_percent matches existing one
                # If changed, we update the Fraction row details so recalculate picks it up
                m_title, list_idx, f_row = fraction_loc
                details_idx = self.HEADER_IDX['details'] - 1
                curr_details = f_row[details_idx] if len(f_row) > details_idx else ""
                
                # Extract current percent
                curr_percent = 3.5

                match = re.search(r'Fraction\s+(\d+(?:\.\d+)?)%', curr_details)
                if match:
                    curr_percent = float(match.group(1))
                    
                if abs(curr_percent - fraction_percent) > 0.001:
                     # Update details column to reflect new percentage
                     new_details = f"Fraction {fraction_percent}%"
                     
                     while len(f_row) < 12: f_row.append('')
                     f_row[details_idx] = new_details
                     
                     # Update cache
                     self._memory_cache[m_title]['rows'][list_idx] = f_row
                     
                     # Update Sheet (Details column is 'L')
                     actual_row_num = self._memory_cache[m_title]['start_row'] + list_idx
                     u_range = f"'{m_title}'!L{actual_row_num}"
                     
                     self._execute_with_retry(lambda: self.sheets_service.spreadsheets().values().update(
                        spreadsheetId=self.spreadsheet_id,
                        range=u_range,
                        valueInputOption='USER_ENTERED',
                        body={'values': [[new_details]]}
                    ).execute())

            # Use the single source of truth to calculate value
            self._recalculate_fraction(load_no)
        
        # Propagate statuses for this load_no across all existing entries
        if load_no:
            # Propagate status + any changed driver/truck/from/to values
            self._propagate_status(
                load_no, delivery_status, payment_status,
                driver_id, truck_id, from_state, to_state
            )
            
            # Also add fraction row to cache index if created
            if fraction_created:
                # entry_rows was appended to above
                # Re-calculate index
                frac_row_num = self._memory_cache[title]['start_row'] + len(entry_rows) - 1
                self._index.setdefault(load_no, []).append((title, frac_row_num))

    def generate_detailed_report(
        self, from_date, to_date, load_no=None, transaction=None, driver=None, truck=None, from_state=None, to_state=None
    ):
        rows = []
        # index for load_no column
        ln_idx = self.HEADER_IDX['load_no'] - 1
        driver_idx = self.HEADER_IDX['driver_id'] - 1
        truck_idx = self.HEADER_IDX['truck_id'] - 1
        from_state_idx = self.HEADER_IDX['from_state'] - 1
        to_state_idx = self.HEADER_IDX['to_state'] - 1
        # Read entirely from in-memory cache
        for title, info in self._memory_cache.items():
            for i, row in enumerate(info['rows']):
                # pad to full width
                if len(row) < len(self.HEADER_IDX):
                    row += [''] * (len(self.HEADER_IDX) - len(row))
                try:
                    d = datetime.strptime(row[0], '%Y/%m/%d').date()
                except Exception:
                    continue
                if from_date and d < from_date:    continue
                if to_date   and d > to_date:      continue
                if load_no   and row[ln_idx] != load_no:      continue
                if transaction and row[self.HEADER_IDX['transaction']-1] != transaction: continue
                if driver and row[driver_idx] != driver: continue
                if truck and row[truck_idx] != truck: continue
                if from_state and row[from_state_idx] != from_state: continue
                if to_state and row[to_state_idx] != to_state: continue
                
                # Create a copy and append metadata (sheet_name, row_num)
                # row_num = start_row + index
                actual_row_num = info['start_row'] + i
                row_with_meta = list(row) + [title, actual_row_num]
                rows.append(row_with_meta)
        return rows

    def get_latest_entry(self, rows):
        """Extract the latest entry from a list of rows by date."""
        if not rows:
            return None
        
        latest = None
        latest_date = None
        for row in rows:
            try:
                d = datetime.strptime(row[0], '%Y/%m/%d').date()
            except Exception:
                continue
            if latest_date is None or d > latest_date:
                latest_date, latest = d, row
        
        return latest

    def get_latest_fraction(self, load_no):
        """
        Get the latest fraction percentage for a load.
        Extracts directly from the details column of the Fraction row.
        """
        if not load_no:
            return 3.5  # Default
        
        try:
            # Get all fraction entries for this load
            rows = self.generate_detailed_report(None, None, load_no=load_no, transaction='Fraction')
            if rows:
                latest = self.get_latest_entry(rows)
                if latest:
                    # Extract from Details column
                    details_idx = self.HEADER_IDX['details'] - 1
                    details_text = latest[details_idx] if len(latest) > details_idx else ""
                    
                    match = re.search(r'Fraction\s+(\d+(?:\.\d+)?)%', details_text)
                    if match:
                        return float(match.group(1))
        except Exception:
            pass
        
        return 3.5  # Default

    def detect_field_changes(self, latest_entry, driver_id, truck_id, from_state, to_state, delivery_status, payment_status, fraction_percent=None):
        """
        Detect field changes between the latest entry and new values.
        Returns a list of change descriptions.
        """
        changes = []
        if not latest_entry or len(latest_entry) < 9:
            return changes
        
        # Extract old values from entry
        # Row format: [date, load_no, driver_id, truck_id, from_state, to_state,
        #              transaction, delivery_status, payment_status, credit, debit, fraction, details]
        old_driver = latest_entry[2] if len(latest_entry) > 2 else ''
        old_truck = latest_entry[3] if len(latest_entry) > 3 else ''
        old_from = latest_entry[4] if len(latest_entry) > 4 else ''
        old_to = latest_entry[5] if len(latest_entry) > 5 else ''
        old_delivery = latest_entry[7] if len(latest_entry) > 7 else ''
        old_payment = latest_entry[8] if len(latest_entry) > 8 else ''
        old_fraction = latest_entry[11] if len(latest_entry) > 11 else ''
        
        # Detect changes
        if driver_id and driver_id != old_driver:
            changes.append(f"Driver ID: {old_driver} → {driver_id}")
        if truck_id and truck_id != old_truck:
            changes.append(f"Truck ID: {old_truck} → {truck_id}")
        if from_state and from_state != old_from:
            changes.append(f"From State: {old_from} → {from_state}")
        if to_state and to_state != old_to:
            changes.append(f"To State: {old_to} → {to_state}")
        if delivery_status and delivery_status != old_delivery:
            changes.append(f"Delivery Status: {old_delivery} → {delivery_status}")
        if payment_status and payment_status != old_payment:
            changes.append(f"Payment Status: {old_payment} → {payment_status}")
        
        if fraction_percent is not None:
            # Extract existing fraction percentage from details
            old_frac_float = 3.5 # Default
            match = re.search(r'Fraction\s+(\d+(?:\.\d+)?)%', old_fraction)
            if match:
                old_frac_float = float(match.group(1))
            
            # Compare with epsilon
            if abs(fraction_percent - old_frac_float) > 0.001:
                changes.append(f"Fraction: {old_frac_float}% → {fraction_percent}%")
        
        return changes

    def export_detailed_csv(self, rows, path):
        with open(path, 'w', newline='') as f:
            writer = csv.writer(f)
            headers = self.get_header_indices()
            writer.writerow(headers)
            writer.writerows(rows)

    def generate_summary_report(
        self, from_date, to_date, load_no=None, transaction=None, driver=None, truck=None, from_state=None, to_state=None
    ):
        rows = self.generate_detailed_report(from_date, to_date, load_no, transaction, driver, truck, from_state, to_state)
        credit_col = self.HEADER_IDX['credit'] - 1
        debit_col = self.HEADER_IDX['debit'] - 1
        total_credit = sum(_parse_amount(r[credit_col]) for r in rows)
        total_debit = sum(_parse_amount(r[debit_col]) for r in rows)
        return {
            'time_period': f"{from_date} to {to_date}",
            'total_credit': f"${total_credit:,.2f}",
            'total_debit': f"${total_debit:,.2f}",
            'net': f"${total_credit - total_debit:,.2f}"
        }

    def export_summary_pdf(self, summary, path, rows=None):

        def on_first_page(canvas, doc):
            canvas.saveState()
            try:
                template_path = resource_path('resources/REDACTED_Letterhead.pdf')
                if template_path.exists():
                    template = PdfReader(str(template_path)).pages[0]
                    template_xobj = pagexobj(template)
                    canvas.doForm(makerl(canvas, template_xobj))
            except Exception as e:
                print(f"Error loading letterhead: {e}")
            canvas.restoreState()

        def on_later_pages(canvas, doc):
            canvas.saveState()
            try:
                # Try the footer file name provided by user, fallback to the one found in directory
                template_path = resource_path('resources/REDACTED_Footer.pdf')
                if not template_path.exists():
                    template_path = resource_path('resources/REDACTED_Letterhead_Footer.pdf')
                
                if template_path.exists():
                    template = PdfReader(str(template_path)).pages[0]
                    template_xobj = pagexobj(template)
                    canvas.doForm(makerl(canvas, template_xobj))
            except Exception as e:
                print(f"Error loading footer: {e}")
            canvas.restoreState()
        
        # Create PDF with Platypus for better table handling
        # Top margin 1 inch for later pages. Bottom margin 1.5 inch for footer.
        doc = SimpleDocTemplate(path, pagesize=letter, topMargin=1.0*inch, bottomMargin=1.5*inch,
                               leftMargin=0.5*inch, rightMargin=0.5*inch)
        
        story = []
        styles = getSampleStyleSheet()
        
        # Spacer to clear the letterhead on the first page
        # Letterhead is approx 2 inches. Top margin is 1 inch. Need ~1.5 inch spacer.
        story.append(Spacer(1, 1.5*inch))

        # Add creation date
        date_style = ParagraphStyle(
            'DateStyle',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.gray,
            alignment=2  # RIGHT
        )
        creation_date = datetime.now().strftime('%B %d, %Y')
        story.append(Paragraph(f"Report Generated: {creation_date}", date_style))
        story.append(Spacer(1, 0.2*inch))
        
        # Add summary title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#1a73e8'),
            spaceAfter=0.2*inch,
            alignment=1  # CENTER
        )
        story.append(Paragraph("Financial Summary Report", title_style))
        story.append(Spacer(1, 0.2*inch))
        
        # Add summary statistics
        summary_style = ParagraphStyle(
            'Summary',
            parent=styles['Normal'],
            fontSize=11,
            spaceAfter=0.1*inch
        )
        story.append(Paragraph(f"<b>Time Period:</b> {summary['time_period']}", summary_style))
        story.append(Paragraph(f"<b>Total Credit:</b> {summary['total_credit']}", summary_style))
        story.append(Paragraph(f"<b>Total Debit:</b> {summary['total_debit']}", summary_style))
        story.append(Paragraph(f"<b>Net:</b> {summary['net']}", summary_style))
        story.append(Spacer(1, 0.3*inch))
        
        # Add detailed table if rows are provided
        if rows:
            story.append(Paragraph("Detailed Transactions", title_style))
            story.append(Spacer(1, 0.2*inch))
            
            # Prepare table data with custom columns for PDF
            # We'll exclude delivery_status and payment_status, and merge from_state/to_state into Trip
            headers = self.get_header_indices()
            
            # Column indices (0-based)
            date_idx = self.HEADER_IDX['date'] - 1
            load_no_idx = self.HEADER_IDX['load_no'] - 1
            driver_id_idx = self.HEADER_IDX['driver_id'] - 1
            truck_id_idx = self.HEADER_IDX['truck_id'] - 1
            from_state_idx = self.HEADER_IDX['from_state'] - 1
            to_state_idx = self.HEADER_IDX['to_state'] - 1
            transaction_idx = self.HEADER_IDX['transaction'] - 1
            credit_idx = self.HEADER_IDX['credit'] - 1
            debit_idx = self.HEADER_IDX['debit'] - 1
            
            # Define the columns to display in PDF (excluding delivery_status, payment_status, and details)
            pdf_headers = ['Date', 'Load No.', 'Driver ID', 'Truck ID', 'Trip', 'Transaction', 'Credit', 'Debit']
            
            # Build table data
            table_data = []
            raw_data = [pdf_headers]  # Store raw data for width calculation
            
            for row in rows:
                # Safely extract values, ensuring we don't get corrupted data
                date_val = str(row[date_idx]).strip() if date_idx < len(row) else ""
                load_no_val = str(row[load_no_idx]).strip() if load_no_idx < len(row) else ""
                driver_id_val = str(row[driver_id_idx]).strip() if driver_id_idx < len(row) else ""
                truck_id_val = str(row[truck_id_idx]).strip() if truck_id_idx < len(row) else ""
                
                # Extract state values
                from_state = str(row[from_state_idx]).strip() if from_state_idx < len(row) else ""
                to_state = str(row[to_state_idx]).strip() if to_state_idx < len(row) else ""
                
                # Extract just the abbreviation (first 2 characters before ':')
                from_abbr = from_state.split(':')[0].strip() if from_state else ""
                to_abbr = to_state.split(':')[0].strip() if to_state else ""
                
                # Create Trip column in format "AL-NY"
                trip = f"{from_abbr}-{to_abbr}" if from_abbr or to_abbr else ""
                
                # Extract transaction type - must be a valid transaction type
                transaction_raw = str(row[transaction_idx]).strip() if transaction_idx < len(row) else ""
                # Take only the first valid transaction type word
                for valid_trans in self.TRANSACTION_TYPES:
                    if valid_trans.lower() in transaction_raw.lower():
                        transaction_clean = valid_trans
                        break
                else:
                    # If no valid transaction found, take first word only
                    transaction_clean = transaction_raw.split()[0] if transaction_raw else ""
                
                # Extract credit and debit using helper function
                credit_val = _parse_amount(str(row[credit_idx])) if credit_idx < len(row) else 0.0
                debit_val = _parse_amount(str(row[debit_idx])) if debit_idx < len(row) else 0.0

                # Clean and convert to float, then round to 2 decimal places, then back to string
                credit_val = str(round(credit_val, 2))
                debit_val = str(round(debit_val, 2))
                
                # Build row with selected columns - clean data
                pdf_row = [
                    date_val,
                    load_no_val,
                    driver_id_val,
                    truck_id_val,
                    trip,
                    transaction_clean,
                    credit_val,
                    debit_val,
                ]
                raw_data.append(pdf_row)
            
            # Calculate the maximum width for Load No. column
            max_load_no_width = len(pdf_headers[1])  # Header "Load No."
            for row_idx in range(1, len(raw_data)):
                load_no_text = str(raw_data[row_idx][1]) if 1 < len(raw_data[row_idx]) else ""
                max_load_no_width = max(max_load_no_width, len(load_no_text))
            
            # Set fixed column widths (in characters) - INCREASED for better spacing
            # 0=Date, 1=Load No., 2=Driver ID, 3=Truck ID, 4=Trip, 5=Transaction, 6=Credit, 7=Debit
            column_char_widths = [13, max_load_no_width, 10, 10, 9, 25, 12, 12]
            
            # Convert character widths to inches using 0.07 inches per character (wider spacing)
            col_widths = [width * 0.07 * inch for width in column_char_widths]
            
            # Add padding spaces to the actual cell content
            table_data = []
            for row_idx, row in enumerate(raw_data):
                padded_row = []
                for col_idx, cell_text in enumerate(row):
                    # Add one space prefix and one space suffix to each cell
                    padded_cell = f" {cell_text} "
                    padded_row.append(padded_cell)
                table_data.append(padded_row)
            
            # Create table with calculated column widths
            table = Table(table_data, colWidths=col_widths, repeatRows=1)
            table.setStyle(TableStyle([
                # Header styling
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4CAF50')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                ('TOPPADDING', (0, 0), (-1, 0), 6),
                
                # Body styling
                ('ALIGN', (0, 1), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f0f0')]),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('LEFTPADDING', (0, 0), (-1, -1), 2),
                ('RIGHTPADDING', (0, 0), (-1, -1), 2),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('WORDWRAP', (0, 0), (-1, -1), False),
            ]))
            
            story.append(table)
        
        # Build PDF
        doc.build(story, onFirstPage=on_first_page, onLaterPages=on_later_pages)

        
