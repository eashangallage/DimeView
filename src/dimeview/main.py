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
    
    # Fix Windows taskbar icon grouping
    if sys.platform.startswith('win'):
        import ctypes
        myappid = 'eashangallage.dimeview.app.1'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    
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

    # set the "global" window icon here
    if getattr(sys, 'frozen', False):
         # Running as compiled executable
         import os
         base_path = Path(sys._MEIPASS)
         icon_path = base_path / "resources" / icon_name
    else:
         # Running from source
         # dimeview.resources package must exist
         icon_path = (resources.files("dimeview").joinpath("resources").joinpath(icon_name))
    
    # DEBUG
    print(f"DEBUG: Icon path = {icon_path}")
    print(f"DEBUG: Icon exists? {Path(icon_path).exists()}")
    
    icon = QIcon(str(icon_path))
    
    # DEBUG - check after creating icon
    print(f"DEBUG: Icon is null? {icon.isNull()}")
    print(f"DEBUG: Available sizes: {icon.availableSizes()}")
    
    app.setWindowIcon(icon)

    # Initialize model and controller (which sets up the views)
    model = DimeViewModel()
    controller = DimeViewController(model)

    # Run the application event loop
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
