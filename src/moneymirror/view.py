#!/usr/bin/env python3
"""
view.py

View component for MoneyMirror application.
Defines PyQt6 GUI: StartupWindow for spreadsheet selection, Data Entry and Reports tabs.
"""
from PyQt6.QtWidgets import (
    QWidget, QMainWindow, QVBoxLayout, QLabel, QComboBox,
    QPushButton, QTabWidget, QFormLayout, QLineEdit, QDateEdit,
    QTextEdit, QTableWidget, QTableWidgetItem, QFileDialog,
    QDialog, QHBoxLayout, QRadioButton, QButtonGroup, QGroupBox,
    QSizePolicy,QGridLayout, QMessageBox,QApplication
)
from PyQt6.QtCore import pyqtSignal, QDate, Qt, QObject, QEvent
from PyQt6.QtGui import QFont

def configure_combobox_height(combo_box, max_items=10):
    """Configure a QComboBox to show max items before scrolling."""
    # Set the maximum height to show approximately 10 items
    combo_box.setMaxVisibleItems(max_items)
    # Ensure the view height is constrained
    combo_box.view().setMinimumHeight(max_items * 20)  # ~20 pixels per item

class LoadingDialog(QDialog):
    def __init__(self, message="Loading... Please wait."):
        super().__init__()
        self.setWindowTitle("Please wait")
        self.setModal(True)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowCloseButtonHint)
        layout = QVBoxLayout(self)
        label = QLabel(message)
        layout.addWidget(label)
        self.setFixedSize(310, 80)

class SharingInstructionsDialog(QDialog):
    """A dialog that instructs the user on how to share their spreadsheet."""
    def __init__(self, client_email, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sharing Instructions")
        self.setModal(True)

        layout = QVBoxLayout(self)

        # Instructional Text
        instructions_text = (
            "<h3>Your spreadsheet isn't showing up?</h3>"
            "<p>Please share your Google Sheet with the app's service account:</p>"
            "<ol>"
            "<li>Open your spreadsheet in Google Sheets.</li>"
            "<li>Click the <b>Share</b> button in the top-right corner.</li>"
            "<li>In the 'Add people and groups' field, paste the email address below.</li>"
            "<li>Make sure <b>Editor</b> is selected as the role.</li>"
            "<li>Click <b>Send</b> to grant access.</li>"
            "<li>Click <b>Close</b> and <b>Refresh 🔄</b> button on the MoneyMirror application.</li>"
            "</ol>"
        )
        layout.addWidget(QLabel(instructions_text))

        # Email and Copy Button
        email_layout = QHBoxLayout()
        self.email_field = QLineEdit(client_email)
        self.email_field.setReadOnly(True)
        email_layout.addWidget(self.email_field)

        copy_btn = QPushButton("Copy")
        copy_btn.clicked.connect(self._copy_email_to_clipboard)
        email_layout.addWidget(copy_btn)
        layout.addLayout(email_layout)

        # Close Button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    def _copy_email_to_clipboard(self):
        QApplication.clipboard().setText(self.email_field.text())
        QMessageBox.information(self, "Copied", "Client email has been copied to the clipboard.")


class StartupWindow(QWidget):
    """Initial window prompting user to select a spreadsheet."""
    # now emits both the spreadsheet ID and its human‐readable name
    spreadsheet_selected = pyqtSignal(str, str)
    show_sharing_instructions = pyqtSignal()
    refresh_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("MoneyMirror")
        self.setMinimumWidth(350) # Set a minimum width for better spacing

        main_layout = QVBoxLayout(self)

        # 1. Add a prominent, centered application title
        title_label = QLabel("MoneyMirror")
        font = QFont()
        font.setPointSize(24)
        font.setBold(True)
        title_label.setFont(font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)
        
        main_layout.addSpacing(15)

        # Dropdown for spreadsheet selection
        main_layout.addWidget(QLabel("Choose Google Spreadsheet:"))
        self.combo = QComboBox()
        main_layout.addWidget(self.combo)

        # 2. Select button on its own line
        self.select_btn = QPushButton("Select")
        self.select_btn.clicked.connect(self._on_select)
        main_layout.addWidget(self.select_btn)

        main_layout.addSpacing(20)

        # 3. Reorder the help and refresh buttons
        self.help_btn = QPushButton("Spreadsheet not listed?")
        self.help_btn.clicked.connect(self.show_sharing_instructions.emit)
        main_layout.addWidget(self.help_btn)
        
        self.refresh_btn = QPushButton("Refresh 🔄")
        self.refresh_btn.clicked.connect(self.refresh_requested.emit)
        main_layout.addWidget(self.refresh_btn)


    def set_spreadsheets(self, sheets):
        """Populate dropdown with list of {'id', 'name'}."""
        self.combo.clear()
        for sheet in sheets:
            self.combo.addItem(sheet['name'], sheet['id'])

    def _on_select(self):
        sheet_name = self.combo.currentText()
        sheet_id = self.combo.currentData()
        if sheet_id:
            # emit both ID and name
            self.spreadsheet_selected.emit(sheet_id, sheet_name)

class DataEntryTab(QWidget):
    """Tab for entering new transaction entries."""
    def __init__(self):
        super().__init__()
        layout = QFormLayout(self)

        # Date
        self.date_edit = QDateEdit(calendarPopup=True)
        layout.addRow("Date:", self.date_edit)

        # ─── Load No. selection group ──────────────────────────────────────────────
        self.load_group = QButtonGroup(self)
        self.existing_load_radio = QRadioButton("Use Load No.")
        self.custom_load_radio   = QRadioButton("No Load Number / Other")
        self.load_group.addButton(self.existing_load_radio)
        self.load_group.addButton(self.custom_load_radio)
        self.existing_load_radio.setChecked(True)

        # Widgets for each option
        self.load_no_combo = QComboBox()
        self.load_no_combo.setEditable(True)
        self.load_no_combo.lineEdit().setPlaceholderText("e.g., 100")
        self.load_no_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        configure_combobox_height(self.load_no_combo, 10)

        self.custom_load_edit = QLineEdit()
        self.custom_load_edit.setPlaceholderText("Other")
        self.custom_load_edit.setEnabled(False)
        self.custom_load_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        # Fraction input widget
        self.fraction_edit = QLineEdit()
        self.fraction_edit.setPlaceholderText("e.g., 3.5")
        self.fraction_edit.setText("3.5")
        self.fraction_edit.setEnabled(False)
        self.fraction_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        # GroupBox to visually connect options
        load_box = QGroupBox("📦 Load No.")
        grid = QGridLayout(load_box)

        # Add radio buttons and inputs in grid columns 0 and 1 respectively
        grid.addWidget(self.existing_load_radio, 0, 0, alignment=Qt.AlignmentFlag.AlignLeft)
        grid.addWidget(self.load_no_combo, 0, 1)
        
        # Add Fraction label and input below "Use Load No." (indented with spacing)
        fraction_label = QLabel("    Fraction (%):")
        grid.addWidget(fraction_label, 1, 0, alignment=Qt.AlignmentFlag.AlignLeft)
        grid.addWidget(self.fraction_edit, 1, 1)
        
        grid.addWidget(self.custom_load_radio, 2, 0, alignment=Qt.AlignmentFlag.AlignLeft)
        grid.addWidget(self.custom_load_edit, 2, 1)

        # Optional: set column minimum width and stretch to improve appearance
        grid.setColumnMinimumWidth(0, 160)  # adjust to fit radio buttons nicely
        grid.setColumnStretch(1, 1)         # input widgets expand to fill space
        
        # Apply stylesheet for better visibility
        load_box.setStyleSheet("""
            QGroupBox {
                border: 2px solid #2196F3;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        grid.setColumnStretch(1, 1)         # input widgets expand to fill space

        layout.addRow(load_box)

        # Toggle behavior
        self.existing_load_radio.toggled.connect(self._on_load_radio_toggled)
        # ─────────────────────────────────────────────────────────────────────────

        # Driver ID
        self.driver_id_combo = QComboBox()
        self.driver_id_combo.setEditable(True)
        configure_combobox_height(self.driver_id_combo, 10)
        layout.addRow("Driver ID:", self.driver_id_combo)

        # Truck ID
        self.truck_id_combo = QComboBox()
        self.truck_id_combo.setEditable(True)
        configure_combobox_height(self.truck_id_combo, 10)
        layout.addRow("Truck ID:", self.truck_id_combo)
    
        # From State
        self.from_state_combo = QComboBox()
        self.from_state_combo.setEditable(True)
        configure_combobox_height(self.from_state_combo, 10)
        layout.addRow("From State:", self.from_state_combo)

        # To State
        self.to_state_combo = QComboBox()
        self.to_state_combo.setEditable(True)
        configure_combobox_height(self.to_state_combo, 10)
        layout.addRow("To State:", self.to_state_combo)

        # Transaction
        self.transaction_combo = QComboBox()
        configure_combobox_height(self.transaction_combo, 10)
        layout.addRow("Transaction:", self.transaction_combo)

        # Delivery Status
        self.delivery_combo = QComboBox()
        configure_combobox_height(self.delivery_combo, 10)
        layout.addRow("Delivery Status:", self.delivery_combo)

        # Payment Status
        self.payment_combo = QComboBox()
        configure_combobox_height(self.payment_combo, 10)
        layout.addRow("Payment Status:", self.payment_combo)

        # Credit
        self.credit_edit = QLineEdit()
        self.credit_edit.setPlaceholderText("Enter amount received (e.g., 123.45)")
        layout.addRow("Credit:", self.credit_edit)

        # Debit
        self.debit_edit = QLineEdit()
        self.debit_edit.setPlaceholderText("Enter payment amount made (e.g., 123.45)")
        layout.addRow("Debit:", self.debit_edit)

        # More Details
        self.details_edit = QTextEdit()
        self.details_edit.setPlaceholderText("Enter optional notes or comments (e.g., payment details, trip notes)")
        layout.addRow("More Details:", self.details_edit)

        # Submit and Reset buttons
        btn_layout = QHBoxLayout()
        self.submit_button = QPushButton("✅ Submit Entry")
        self.reset_button = QPushButton("🗘 Reset Form")
        btn_layout.addWidget(self.submit_button)
        btn_layout.addWidget(self.reset_button)
        layout.addRow(btn_layout)

        # Connect reset
        self.reset_button.clicked.connect(self.reset_form)

        # Initialize form state
        self.reset_form()

    def reset_form(self):
        """Clear all fields and restore defaults."""
        self.existing_load_radio.setChecked(True)
        self.custom_load_edit.clear()

        self.date_edit.setDate(QDate.currentDate())
        self.load_no_combo.clearEditText()
        self.fraction_edit.setText("3.5")
        self.fraction_edit.setEnabled(True)  # Enable since Use Load No. is checked
        self.driver_id_combo.setCurrentIndex(-1)
        self.truck_id_combo.setCurrentIndex(-1)
        self.from_state_combo.setCurrentIndex(-1)
        self.to_state_combo.setCurrentIndex(-1)
        self.transaction_combo.setCurrentIndex(-1)
        self.delivery_combo.setCurrentIndex(-1)
        self.payment_combo.setCurrentIndex(-1)
        self.credit_edit.clear()
        self.debit_edit.clear()
        self.details_edit.clear()

    def _on_load_radio_toggled(self, checked: bool):
        """Enable combo when existing is checked; else enable custom edit."""
        self.load_no_combo.setEnabled(checked)
        self.custom_load_edit.setEnabled(not checked)
        # Enable fraction input only when "Use Load No." is selected
        self.fraction_edit.setEnabled(checked)
        if not checked: # custom load selected
            self.custom_load_edit.setText("Other")
        else:
            self.custom_load_edit.clear()

    def populate_from_entry(self, entry_row):
        """
        Populate form fields from a data row.
        Row format: [date, load_no, driver_id, truck_id, from_state, to_state,
                     transaction, delivery_status, payment_status, credit, debit, details]
        """
        if not entry_row or len(entry_row) < 9:
            return

        # [0]=Date, [1]=Load, [2]=Driver, [3]=Truck, [4]=From, [5]=To,
        # [6]=Transaction, [7]=Delivery, [8]=Payment
        self.driver_id_combo.setCurrentText(entry_row[2])
        self.truck_id_combo.setCurrentText(entry_row[3])
        self.from_state_combo.setCurrentText(entry_row[4])
        self.to_state_combo.setCurrentText(entry_row[5])
        self.delivery_combo.setCurrentText(entry_row[7])
        self.payment_combo.setCurrentText(entry_row[8])

    def setup_state_auto_format(self, model):
        """
        Connect state combo boxes to auto-format input when focus is lost.
        Call this from the controller after the view is initialized.
        """
        # Create event filters for the state combo boxes
        state_formatter_from = StateAutoFormatter(model, self.from_state_combo)
        state_formatter_to = StateAutoFormatter(model, self.to_state_combo)
        
        self.from_state_combo.lineEdit().installEventFilter(state_formatter_from)
        self.to_state_combo.lineEdit().installEventFilter(state_formatter_to)


class StateAutoFormatter(QObject):
    """Event filter to auto-format state input when focus is lost."""
    
    def __init__(self, model, combo_box):
        super().__init__()
        self.model = model
        self.combo_box = combo_box
    
    def eventFilter(self, obj, event):
        """Handle focus out event to auto-format state input."""
        if event.type() == QEvent.Type.FocusOut:
            current_text = obj.text().strip()
            if current_text:
                # Format the input using the model
                formatted = self.model.format_state_input(current_text)
                
                # Simply set the text on the line edit
                # This works because the combo box is editable
                obj.setText(formatted)
        
        return super().eventFilter(obj, event)



class ReportsTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        
        # === FILTERS SECTION ===
        filters_section = QVBoxLayout()
        
        # Row 1: Date filters (vertical)
        date_layout = QVBoxLayout()
        from_date_layout = QHBoxLayout()
        from_date_layout.addWidget(QLabel("From Date:"))
        self.from_date = QDateEdit()
        self.from_date.setCalendarPopup(True)
        self.from_date.setDate(QDate.currentDate().addMonths(-1))
        from_date_layout.addWidget(self.from_date)
        date_layout.addLayout(from_date_layout)
        
        to_date_layout = QHBoxLayout()
        to_date_layout.addWidget(QLabel("To Date:"))
        self.to_date = QDateEdit()
        self.to_date.setCalendarPopup(True)
        self.to_date.setDate(QDate.currentDate())
        to_date_layout.addWidget(self.to_date)
        date_layout.addLayout(to_date_layout)
        filters_section.addLayout(date_layout)
        
        # Row 2: Transaction, Load No, Driver
        row2_layout = QHBoxLayout()
        
        # Transaction filter (moved to second position)
        trans_layout = QVBoxLayout()
        trans_layout.addWidget(QLabel("Transaction:"))
        self.transaction_filter_combo = QComboBox()
        configure_combobox_height(self.transaction_filter_combo, 10)
        trans_layout.addWidget(self.transaction_filter_combo)
        row2_layout.addLayout(trans_layout)
        
        # Load No. filter
        load_layout = QVBoxLayout()
        load_layout.addWidget(QLabel("Load No.:"))
        self.load_no_filter_combo = QComboBox()
        self.load_no_filter_combo.setEditable(True)
        configure_combobox_height(self.load_no_filter_combo, 10)
        load_layout.addWidget(self.load_no_filter_combo)
        row2_layout.addLayout(load_layout)
        
        # Driver filter
        driver_layout = QVBoxLayout()
        driver_layout.addWidget(QLabel("Driver:"))
        self.driver_filter_combo = QComboBox()
        self.driver_filter_combo.setEditable(True)
        configure_combobox_height(self.driver_filter_combo, 10)
        driver_layout.addWidget(self.driver_filter_combo)
        row2_layout.addLayout(driver_layout)

        # Truck filter
        truck_layout = QVBoxLayout()
        truck_layout.addWidget(QLabel("Truck:"))
        self.truck_filter_combo = QComboBox()
        self.truck_filter_combo.setEditable(True)
        configure_combobox_height(self.truck_filter_combo, 10)
        truck_layout.addWidget(self.truck_filter_combo)
        row2_layout.addLayout(truck_layout)
        
        filters_section.addLayout(row2_layout)
        
        # Row 3: State filters (vertical)
        state_layout = QVBoxLayout()
        from_state_row = QHBoxLayout()
        from_state_row.addWidget(QLabel("From State:"))
        self.from_state_filter_combo = QComboBox()
        self.from_state_filter_combo.setEditable(True)
        configure_combobox_height(self.from_state_filter_combo, 10)
        from_state_row.addWidget(self.from_state_filter_combo)
        state_layout.addLayout(from_state_row)
        
        to_state_row = QHBoxLayout()
        to_state_row.addWidget(QLabel("To State:"))
        self.to_state_filter_combo = QComboBox()
        self.to_state_filter_combo.setEditable(True)
        configure_combobox_height(self.to_state_filter_combo, 10)
        to_state_row.addWidget(self.to_state_filter_combo)
        state_layout.addLayout(to_state_row)
        filters_section.addLayout(state_layout)
        
        # Create a QGroupBox with the filters layout for visual outline
        filters_group = QGroupBox("📋 Report Filters")
        filters_group.setLayout(filters_section)
        # Apply stylesheet for better visibility
        filters_group.setStyleSheet("""
            QGroupBox {
                border: 2px solid #4CAF50;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        layout.addWidget(filters_group)
        
        # === REPORT GENERATION BUTTON ===
        self.generate_button = QPushButton("📝 Generate Report")
        layout.addWidget(self.generate_button)

        # === DETAILED TABLE ===
        self.detailed_table = QTableWidget()
        layout.addWidget(self.detailed_table)

        # === SUMMARY TEXT ===
        self.summary_text = QTextEdit()
        layout.addWidget(self.summary_text)
        
        # === DOWNLOAD BUTTONS (Vertical, at bottom above Reset) ===
        download_layout = QVBoxLayout()
        self.csv_download_button = QPushButton("⬇️ Download Detailed Report as CSV")
        self.pdf_download_button = QPushButton("⬇️ Download Summary Report as PDF")
        download_layout.addWidget(self.csv_download_button)
        download_layout.addWidget(self.pdf_download_button)
        layout.addLayout(download_layout)
        
        # === RESET BUTTON (at bottom) ===
        self.reset_button = QPushButton("🗘 Reset Filters")
        layout.addWidget(self.reset_button)

        self.setLayout(layout)

    def populate_detailed_table(self, rows, column_headers):
        # Map coding names to human-readable names
        header_mapping = {
            'date': 'Date',
            'load_no': 'Load No.',
            'driver_id': 'Driver ID',
            'truck_id': 'Truck ID',
            'trip': 'Trip',  # New combined column
            'transaction': 'Transaction',
            'delivery_status': 'Delivery Status',
            'payment_status': 'Payment Status',
            'credit': 'Credit',
            'debit': 'Debit',
            'fraction': 'Fraction %',
            'details': 'Details'
        }
        
        # Identify indices for From/To state to combine them
        try:
            from_idx = column_headers.index('from_state')
            to_idx = column_headers.index('to_state')
        except ValueError:
            from_idx = -1
            to_idx = -1

        # Build new headers list
        new_headers = []
        trip_col_index = -1
        
        for i, h in enumerate(column_headers):
            if h == 'from_state':
                new_headers.append('trip')
                trip_col_index = len(new_headers) - 1
            elif h == 'to_state':
                continue # Skip, already handled by 'trip'
            else:
                new_headers.append(h)

        # Convert headers to readable names
        readable_headers = [header_mapping.get(h, h) for h in new_headers]
        
        self.detailed_table.clear()
        self.detailed_table.setColumnCount(len(readable_headers))
        self.detailed_table.setHorizontalHeaderLabels(readable_headers)
        self.detailed_table.setRowCount(len(rows))
        
        for i, row in enumerate(rows):
            new_row = []
            from_val = ""
            to_val = ""
            
            # Reconstruct row with combined Trip column
            for j, val in enumerate(row):
                # Assuming column_headers matches row structure
                if j < len(column_headers):
                    col_name = column_headers[j]
                    if col_name == 'from_state':
                        from_val = str(val)
                    elif col_name == 'to_state':
                        to_val = str(val)
                    else:
                        new_row.append(val)
            
            # Insert Trip value at the correct position
            if trip_col_index != -1:
                trip_val = f"{from_val}-{to_val}" if from_val or to_val else ""
                # We need to insert it where 'from_state' was (which is now 'trip')
                # But since we appended non-state columns to new_row, we need to be careful.
                # Actually, let's rebuild the row strictly following new_headers order
                
                final_row = []
                for h in new_headers:
                    if h == 'trip':
                        final_row.append(f"{from_val}-{to_val}" if from_val or to_val else "")
                    else:
                        # Find index in original headers
                        orig_idx = column_headers.index(h)
                        if orig_idx < len(row):
                            final_row.append(row[orig_idx])
                        else:
                            final_row.append("")
                
                for j, val in enumerate(final_row):
                    item = QTableWidgetItem(str(val))
                    self.detailed_table.setItem(i, j, item)
            else:
                # Fallback if states not found
                for j, val in enumerate(row):
                    item = QTableWidgetItem(str(val))
                    self.detailed_table.setItem(i, j, item)

        # Set column widths based on character counts from PDF export logic
        # 1 char approx 10 pixels
        char_widths = {
            'date': 13,
            'load_no': 10, # Default
            'driver_id': 10,
            'truck_id': 10,
            'trip': 9,
            'transaction': 25,
            'delivery_status': 15,
            'payment_status': 15,
            'credit': 12,
            'debit': 12,
            'fraction': 10,
            'details': 30
        }

        # Calculate dynamic max width for Load No. if present
        if 'load_no' in column_headers:
            ln_idx = column_headers.index('load_no')
            max_len = 8 # "Load No."
            for row in rows:
                if ln_idx < len(row):
                    max_len = max(max_len, len(str(row[ln_idx])))
            char_widths['load_no'] = max_len

        # Apply widths
        for col_idx, header_key in enumerate(new_headers):
            if header_key in char_widths:
                # Use 10px per character as a rough approximation
                # Add a little padding (e.g. +10px)
                pixel_width = (char_widths[header_key] * 10) + 10
                self.detailed_table.setColumnWidth(col_idx, pixel_width)

    def enable_csv_download(self, export_func, rows):
        self.csv_download_button.setEnabled(True)
        try:
            self.csv_download_button.clicked.disconnect()
        except Exception:
            pass
        def save_csv():
            path, _ = QFileDialog.getSaveFileName(self, "Save CSV", "", "CSV Files (*.csv)")
            if path:
                export_func(rows, path)
        self.csv_download_button.clicked.connect(save_csv)

    def enable_pdf_download(self, export_func, summary, rows=None):
        self.pdf_download_button.setEnabled(True)
        try:
            self.pdf_download_button.clicked.disconnect()
        except Exception:
            pass
        def save_pdf():
            path, _ = QFileDialog.getSaveFileName(self, "Save PDF", "", "PDF Files (*.pdf)")
            if path:
                # Pass both summary and rows if available
                if rows is not None:
                    export_func(summary, path, rows)
                else:
                    export_func(summary, path)
        self.pdf_download_button.clicked.connect(save_pdf)

    def populate_summary(self, summary):
        text = (
            f"Time Period: {summary['time_period']}\n"
            f"Total Credit: {summary['total_credit']}\n"
            f"Total Debit: {summary['total_debit']}\n"
            f"Net: {summary['net']}\n"
        )
        self.summary_text.setPlainText(text)

    def reset_filters(self):
        """Reset all filter selections to defaults."""
        self.from_date.setDate(QDate.currentDate().addMonths(-1))
        self.to_date.setDate(QDate.currentDate())
        self.load_no_filter_combo.setCurrentIndex(0)  # Select 'All'
        self.driver_filter_combo.setCurrentIndex(0)   # Select 'All'
        self.truck_filter_combo.setCurrentIndex(0)    # Select 'All'
        self.from_state_filter_combo.setCurrentIndex(0)  # Select blank
        self.to_state_filter_combo.setCurrentIndex(0)    # Select blank
        self.transaction_filter_combo.setCurrentIndex(0) # Select 'All'
        self.detailed_table.clear()
        self.summary_text.clear()

class MainWindow(QMainWindow):
    """Main application window containing tabs."""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MoneyMirror")
        tabs = QTabWidget()
        self.data_entry_tab = DataEntryTab()
        self.reports_tab    = ReportsTab()
        tabs.addTab(self.data_entry_tab, "Data Entry")
        tabs.addTab(self.reports_tab,    "Reports")
        self.setCentralWidget(tabs)
