# MoneyMirror

A desktop application for tracking and reporting on personal finances using Google Sheets integration.

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
