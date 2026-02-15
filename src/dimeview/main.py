#!/usr/bin/env python3
"""
main.py
Entry point for DimeView application.
Initializes the application, model, view, and controller.
"""
import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon

from dimeview.model import DimeViewModel
from dimeview.controller import DimeViewController

from importlib import resources

def main():
    """Start the DimeView application."""
    # Create Qt application
    app = QApplication(sys.argv)

    app.setDesktopFileName("DimeView")

    # figure out which icon to use
    if sys.platform.startswith("win"):
        icon_name = "icon.ico"
    elif sys.platform.startswith("linux") and Path("/etc/debian_version").exists():
        # running on a Debian‐based Linux
        icon_name = "icon.png"
    else:
        # any other UNIX‐like OS; fall back to PNG
        icon_name = "icon.png"

    # set the “global” window icon here
    icon_path = (resources.files("dimeview").joinpath("resources").joinpath(icon_name))
    icon = QIcon(str(icon_path))
    app.setWindowIcon(icon)

    # Initialize model and controller (which sets up the views)
    model = DimeViewModel()
    controller = DimeViewController(model)

    # Run the application event loop
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
