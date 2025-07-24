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
from PyQt6.QtCore import pyqtSignal, QDate, Qt
from PyQt6.QtGui import QFont

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

        self.custom_load_edit = QLineEdit()
        self.custom_load_edit.setPlaceholderText("Other")
        self.custom_load_edit.setEnabled(False)
        self.custom_load_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        # GroupBox to visually connect options
        load_box = QGroupBox("Load No.")
        grid = QGridLayout(load_box)

        # Add radio buttons and inputs in grid columns 0 and 1 respectively
        grid.addWidget(self.existing_load_radio, 0, 0, alignment=Qt.AlignmentFlag.AlignLeft)
        grid.addWidget(self.load_no_combo, 0, 1)
        grid.addWidget(self.custom_load_radio, 1, 0, alignment=Qt.AlignmentFlag.AlignLeft)
        grid.addWidget(self.custom_load_edit, 1, 1)

        # Optional: set column minimum width and stretch to improve appearance
        grid.setColumnMinimumWidth(0, 160)  # adjust to fit radio buttons nicely
        grid.setColumnStretch(1, 1)         # input widgets expand to fill space

        layout.addRow(load_box)

        # Toggle behavior
        self.existing_load_radio.toggled.connect(self._on_load_radio_toggled)
        # ─────────────────────────────────────────────────────────────────────────

        # Driver ID
        self.driver_id_combo = QComboBox()
        self.driver_id_combo.setEditable(True)
        layout.addRow("Driver ID:", self.driver_id_combo)

        # Truck ID
        self.truck_id_combo = QComboBox()
        self.truck_id_combo.setEditable(True)
        layout.addRow("Truck ID:", self.truck_id_combo)
    
        # From State
        self.from_state_combo = QComboBox()
        self.from_state_combo.setEditable(True)
        layout.addRow("From State:", self.from_state_combo)

        # To State
        self.to_state_combo = QComboBox()
        self.to_state_combo.setEditable(True)
        layout.addRow("To State:", self.to_state_combo)

        # Transaction
        self.transaction_combo = QComboBox()
        layout.addRow("Transaction:", self.transaction_combo)

        # Delivery Status
        self.delivery_combo = QComboBox()
        layout.addRow("Delivery Status:", self.delivery_combo)

        # Payment Status
        self.payment_combo = QComboBox()
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
        self.submit_button = QPushButton("Submit Entry")
        self.reset_button = QPushButton("Reset Form")
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

        if not checked: # custom load selected
            self.custom_load_edit.setText("Other")
        else:
            self.custom_load_edit.clear()



class ReportsTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        filter_layout = QHBoxLayout()

        # Date filters
        self.from_date = QDateEdit()
        self.from_date.setCalendarPopup(True)
        self.from_date.setDate(QDate.currentDate().addMonths(-1))
        filter_layout.addWidget(QLabel("From:"))
        filter_layout.addWidget(self.from_date)

        self.to_date = QDateEdit()
        self.to_date.setCalendarPopup(True)
        self.to_date.setDate(QDate.currentDate())
        filter_layout.addWidget(QLabel("To:"))
        filter_layout.addWidget(self.to_date)

        # Load No. filter
        self.load_no_filter_combo = QComboBox()
        filter_layout.addWidget(QLabel("Load No.:"))
        filter_layout.addWidget(self.load_no_filter_combo)

        # Transaction filter
        self.transaction_filter_combo = QComboBox()
        filter_layout.addWidget(QLabel("Transaction:"))
        filter_layout.addWidget(self.transaction_filter_combo)

        layout.addLayout(filter_layout)

        # Buttons
        self.detailed_button = QPushButton("Generate Detailed Report")
        self.summary_button = QPushButton("Generate Summary Report")
        layout.addWidget(self.detailed_button)
        layout.addWidget(self.summary_button)

        # Detailed table and CSV download
        self.detailed_table = QTableWidget()
        layout.addWidget(self.detailed_table)
        self.csv_download_button = QPushButton("Download CSV")
        layout.addWidget(self.csv_download_button)

        # Summary text and PDF download
        self.summary_text = QTextEdit()
        layout.addWidget(self.summary_text)
        self.pdf_download_button = QPushButton("Download PDF")
        layout.addWidget(self.pdf_download_button)

        self.setLayout(layout)

    def populate_detailed_table(self, rows, column_headers):
        self.detailed_table.clear()
        self.detailed_table.setColumnCount(len(column_headers))
        self.detailed_table.setHorizontalHeaderLabels(column_headers)
        self.detailed_table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, val in enumerate(row):
                item = QTableWidgetItem(str(val))
                self.detailed_table.setItem(i, j, item)

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

    def populate_summary(self, summary):
        text = (
            f"Time Period: {summary['time_period']}\n"
            f"Total Credit: {summary['total_credit']}\n"
            f"Total Debit: {summary['total_debit']}\n"
            f"Net: {summary['net']}\n"
        )
        self.summary_text.setPlainText(text)

    def enable_pdf_download(self, export_func, summary):
        self.pdf_download_button.setEnabled(True)
        try:
            self.pdf_download_button.clicked.disconnect()
        except Exception:
            pass
        def save_pdf():
            path, _ = QFileDialog.getSaveFileName(self, "Save PDF", "", "PDF Files (*.pdf)")
            if path:
                export_func(summary, path)
        self.pdf_download_button.clicked.connect(save_pdf)

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
