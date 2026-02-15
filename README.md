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

### Ubuntu Installation & Launch

#### 1. Install System Dependencies

First, ensure your Ubuntu system has the required packages:

```bash
# Update package list
sudo apt update

# Install Python 3.12+ and required system dependencies
sudo apt install -y python3 python3-pip python3-venv git

# Install PyQt6 system dependencies (for GUI)
sudo apt install -y libxcb-xinerama0 libxcb-cursor0 libxkbcommon-x11-0 \
    libegl1 libgl1 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 \
    libxcb-randr0 libxcb-render-util0 libxcb-shape0
```

#### 2. Clone and Setup

```bash
# Clone the repository
git clone https://github.com/eashangallage/MoneyMirror.git
cd MoneyMirror

# (Optional) If you need to checkout a specific branch
# git checkout debian

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -e .
```

#### 3. Launch the Application

After installation, you can launch MoneyMirror in several ways:

**Option 1: Using the installed command (Recommended)**
```bash
# Make sure virtual environment is activated
source venv/bin/activate

# Launch the application
moneymirror
```

**Option 2: Using Python module**
```bash
# Make sure virtual environment is activated
source venv/bin/activate

# Launch via module
python -m moneymirror
```

**Option 3: Direct Python execution**
```bash
# From the MoneyMirror directory
source venv/bin/activate
python src/moneymirror/main.py
```

### Troubleshooting

**Issue: "moneymirror: command not found"**
- Make sure you've activated the virtual environment: `source venv/bin/activate`
- Verify installation: `pip show moneymirror`

**Issue: PyQt6 GUI errors (libEGL.so.1, libGL.so.1, etc.)**
- Install missing Qt/OpenGL dependencies:
  ```bash
  sudo apt install -y libxcb-xinerama0 libxcb-cursor0 libxkbcommon-x11-0 \
      libegl1 libgl1 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 \
      libxcb-randr0 libxcb-render-util0 libxcb-shape0
  ```

**Issue: Google Sheets API credentials not found**
- Make sure you have set up Google Sheets API credentials
- Place your credentials file in the appropriate location as per the application requirements

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
