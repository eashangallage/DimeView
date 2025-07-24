# MoneyMirror

MoneyMirror is a desktop application for managing and visualizing your personal finances.

## Features

* Connects to Google Sheets to fetch income and expense data
* Local processing and analysis of financial transactions
* Exports reports and visual charts

## Prerequisites

* Python 3.12 or higher
* [pyinstaller](https://www.pyinstaller.org/) (for building the standalone executable)

## Installation

1. **Clone the repository and select the `debian` branch**

   ```bash
   git clone git@github.com:eashangallage/MoneyMirror.git
   cd MoneyMirror
   git fetch origin
   git checkout debian
   ```

2. **Create and activate a virtual environment**

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install the package in editable mode**

   ```bash
   pip install -e .
   ```

## Running from Source

Once installed in your environment, you can start MoneyMirror directly:

```bash
moneymirror
```

*(You no longer need to prefix with `python -m`.)*

## Building a Standalone Executable

To package MoneyMirror into a standalone application, run:

```bash
pyinstaller --name moneymirror --onedir --windowed --add-data "src/moneymirror/resources:." src/moneymirror/main.py
```

After the build completes, you'll find the executable in the `dist/moneymirror/` directory.

## Testing

```bash
pytest
```

## Contributing

Contributions, issues, and feature requests are welcome!

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
