# MoneyMirror v2.0.0

A desktop application for tracking and reporting on personal finances using Google Sheets integration.

## New in v2.0.0
- **Fraction Logic Overhaul**: Implemented "Single Source of Truth" for fraction calculations. Deleting or modifying entries now automatically recalculates the Fraction % debit, correcting prior inconsistencies.
- **Soft Delete**: Deleting an entry now moves it to a "Trash" sheet instead of permanent deletion.
- **Improved UI**: 
  - Added "Delete Selected" button in Reports tab.
  - Credit/Debit columns now formatted to 2 decimal places.
  - "Fraction" entries are protected from direct deletion (must delete the source income entry).
  - Status updates (Driver, Payment, etc.) now propagate instantly to all related entries without restart.
- **Bug Fixes**: 
  - Fixed "Template already exists" error.
  - Fixed persistent pop-ups when Fraction % wasn't actually changed.

## Quick Start

### Prerequisites
- Python 3.12+
- Google Sheets API credentials

### Setup

```bash
# Clone and setup
git clone git@github.com:eashangallage/MoneyMirror.git
cd MoneyMirror
git checkout debian

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -e .
```

### Run

```bash
moneymirror
```

Or via module:
```bash
python -m moneymirror
```

## Build Standalone Executable

```bash
pyinstaller moneymirror.spec
```

Output: `dist/moneymirror/`

## Test

```bash
pytest
```

## Features

- Google Sheets integration for data sync
- Detailed transaction reports with filtering
- PDF/CSV export functionality
- Summary reports with credit/debit calculations
- Multi-month data management

## License

MIT
