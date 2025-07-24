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
        for sheet in meta.get('sheets', []):
            title = sheet['properties']['title']
            if title == 'Template':
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
    
    def get_header_indices(self):
        return list(self.HEADER_IDX.keys())

    def get_all_load_nos(self):
        # Build from in-memory rows
        ids = set()
        for info in self._memory_cache.values():
            for row in info['rows']:
                if len(row) > self.HEADER_IDX['load_no']-1:
                    ids.add(row[self.HEADER_IDX['load_no']-1])
        lst = sorted(filter(lambda x: x and x != "Other", ids))
        return lst

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

    def _duplicate_template(self, new_title):
        # Find the source 'Template' sheet ID
        source_id = next(
            s['properties']['sheetId']
            for s in self.spreadsheet_metadata['sheets']
            if s['properties']['title'] == 'Template'
        )

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
        for title, row_num in self._index.get(load_no, []):
            # 1) Propagate driver/truck/from/to if passed
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

    def append_entry(
        self, date, load_no, driver_id, truck_id, from_state, to_state,
        transaction, delivery_status, payment_status,
        credit_amt, debit_amt, details
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
        # Build row in updated column order A:J
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
        # Propagate statuses for this load_no across all existing entries
        if load_no:
            # Propagate status + any changed driver/truck/from/to values
            self._propagate_status(
                load_no, delivery_status, payment_status,
                driver_id, truck_id, from_state, to_state
            )
            # Also keep the new row in our in-memory cache + index
            title = month_title
            entry_rows = self._memory_cache.setdefault(title, {'rows': [], 'start_row': 3})['rows']
            entry_rows.append(row)
            new_row_num = self._memory_cache[title]['start_row'] + len(entry_rows) - 1
            self._index.setdefault(load_no, []).append((title, new_row_num))

    def generate_detailed_report(
        self, from_date, to_date, load_no=None, transaction=None
    ):
        rows = []
        # index for load_no column
        ln_idx = self.HEADER_IDX['load_no'] - 1
        # Read entirely from in-memory cache
        for title, info in self._memory_cache.items():
            for row in info['rows']:
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
                rows.append(row)
        return rows

    def export_detailed_csv(self, rows, path):
        with open(path, 'w', newline='') as f:
            writer = csv.writer(f)
            headers = self.get_header_indices()
            writer.writerow(headers)
            writer.writerows(rows)

    def generate_summary_report(
        self, from_date, to_date, load_no=None, transaction=None
    ):
        rows = self.generate_detailed_report(from_date, to_date, load_no, transaction)
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

    def export_summary_pdf(self, summary, path):
        c = canvas.Canvas(path, pagesize=letter)
        width, height = letter
        logo_path = resource_path('resources/logo.png')
        if logo_path.exists():
            img = ImageReader(str(logo_path))
            iw, ih = img.getSize()
            aspect = ih / iw
            w = 300
            h = w * aspect
            c.drawImage(img, (width - w) / 2, height - h - 50, w, h)
        text_y = height - (h + 80)
        c.setFont('Helvetica', 12)
        c.drawString(100, text_y, f'Time Period: {summary["time_period"]}')
        c.drawString(100, text_y - 20, f'Total Credit: {summary["total_credit"]}')
        c.drawString(100, text_y - 40, f'Total Debit: {summary["total_debit"]}')
        c.drawString(100, text_y - 60, f'Net: {summary["net"]}')
        c.showPage()
        c.save()

        
