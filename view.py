from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QRadioButton, QLabel, QButtonGroup, QFrame, QHBoxLayout, QScrollArea, QPushButton,
    QLineEdit, QGridLayout, QComboBox, QTableView, QFileDialog, QCompleter
)
from PyQt6.QtGui import QPainter, QColor, QScreen
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QRectF, QSize
from PyQt6.QtPrintSupport import QPrinter, QPrintDialog
import math

class RotatingCircleWidget(QWidget):
    """
    A custom widget that shows a rotating loading circle.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.angle = 0  # Initial angle for the rotation
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_rotation)
        self.timer.start(30)  # Update every 30 ms for smooth animation

    def update_rotation(self):
        """
        Increment the rotation angle and trigger a repaint.
        """
        self.angle = (self.angle + 5) % 360  # Keep the angle between 0-359
        self.update()  # Trigger a repaint

    def paintEvent(self, event):
        """
        Render the rotating circle.
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Center of the widget
        center_x = self.width() / 2
        center_y = self.height() / 2
        radius = min(self.width(), self.height()) / 3

        # Draw the rotating circle
        for i in range(12):  # 12 segments for the loading circle
            alpha = 255 - (i * 20)  # Decrease opacity for trailing effect
            color = QColor(0, 122, 204, alpha)  # Blue color with varying opacity
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)

            # Calculate position of each segment
            angle = math.radians(self.angle + (i * 30))  # 30 degrees apart
            x = center_x + radius * math.cos(angle)
            y = center_y + radius * math.sin(angle)

            # Draw a small circle for each segment
            painter.drawEllipse(QRectF(x - 5, y - 5, 10, 10))


class LoadingScreen(QMainWindow):
    """
    A loading screen with a rotating circle.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Loading Screen")
        self.setFixedSize(400, 400)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)

        # Central widget and layout
        central_widget = QWidget()
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        central_widget.setLayout(layout)

        # Loading circle widget
        self.loading_circle = RotatingCircleWidget()
        self.loading_circle.setFixedSize(200, 200)
        layout.addWidget(self.loading_circle)

        # Loading text
        self.loading_label = QLabel("Loading...")
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.loading_label)

        self.setCentralWidget(central_widget)


class ExpenseReportGUI(QWidget):
    def __init__(self):
        super().__init__()
        layout = QGridLayout()
        layout.addWidget(QLabel("Expense Date:"), 0, 0)
        layout.addWidget(QLineEdit(), 0, 1)
        layout.addWidget(QLabel("Amount:"), 1, 0)
        layout.addWidget(QLineEdit(), 1, 1)
        self.setLayout(layout)
        self.setWindowTitle("Expense Report")


class DetailsGUI(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Details will be shown here."))
        self.setLayout(layout)
        self.setWindowTitle("Details")


class InvoiceGUI(QWidget):
    def __init__(self):
        super().__init__()
        layout = QGridLayout()
        layout.addWidget(QLabel("Invoice Number:"), 0, 0)
        layout.addWidget(QLineEdit(), 0, 1)
        layout.addWidget(QLabel("Client:"), 1, 0)
        layout.addWidget(QLineEdit(), 1, 1)
        self.setLayout(layout)
        self.setWindowTitle("Invoice Entry")


class CSVWindow(QMainWindow):
    aboutToClose = pyqtSignal()

    def __init__(self, model, key, controller):
        super().__init__()
        self.model = model
        self.key = key
        self.controller = controller
        self.setWindowTitle("CSV Viewer: " + key)

        self.table_view = QTableView()
        self.table_view.setModel(model)

        self.resize_window()

        # Create buttons
        self.save_button = QPushButton("Save As")
        self.save_button.setFixedSize(150, 25)

        # Connect button signals
        self.save_button.clicked.connect(self.save_as)

        # Create layout for buttons
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.save_button)

        # Create a main widget and set the layout
        central_widget = QWidget()
        main_layout = QVBoxLayout()
        main_layout.addWidget(self.table_view)
        main_layout.addLayout(button_layout)
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

    def resize_window(self):
        """Resizes the window based on table content or screen height."""
        # Calculate height based on table content
        row_height = self.table_view.rowHeight(0) if self.table_view.model() and self.table_view.model().rowCount() > 0 else 20
        table_height = (self.table_view.model().rowCount() + 1) * row_height  # Add 1 row for the header

        # Get screen height
        screen = QScreen.availableGeometry(QApplication.primaryScreen())
        screen_height = screen.height()

        # Choose the smaller of the two heights
        window_height = min(table_height, int(screen_height * 0.75))  # 3/4 of screen height

        # Set the window size
        self.resize(QSize(self.width(), window_height))

    def save_as(self):
        """
        Allows the user to save the file as either CSV or PDF.
        """
        file_path, file_type = QFileDialog.getSaveFileName(
            self, "Save File", "", "CSV Files (*.csv)"
        )

        if file_type == "CSV Files (*.csv)":
            self.controller.save_data(self.key, file_path, "Save As")

    def closeEvent(self, event):
        self.aboutToClose.emit()
        super().closeEvent(event)


class EnterInvoice(QWidget):
    
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Invoice Input")
        self.setGeometry(100, 100, 400, 300)

        self.inputs_dict = {}
        self.textboxes = []

        # Main Layout
        layout = QVBoxLayout()

        # Add labels and text boxes to layout
        for i in range(1, 6):
            h_layout = QHBoxLayout()
            label = QLabel(f"Textbox{i}")
            textbox = QLineEdit()
            textbox.textChanged.connect(lambda text, i=i: self.save_input(i, text))
            self.textboxes.append(textbox)  # Store textbox references
            h_layout.addWidget(label)
            h_layout.addWidget(textbox)
            layout.addLayout(h_layout)
        
        # Submit Button
        self.submit_button = QPushButton("Submit")
        self.submit_button.clicked.connect(self.print_inputs)
        layout.addWidget(self.submit_button)

        self.setLayout(layout)

    def save_input(self, i, text):
        self.inputs_dict[f"Textbox{i}"] = text

    def print_inputs(self):
        print(self.inputs_dict)
        self.close()  # Close the EnterInvoice window after submit

    def closeEvent(self, event):
        # Reset the text in all text boxes and clear the dictionary when the window is closed
        for textbox in self.textboxes:
            textbox.clear()  # Clear the text in the input boxes
        self.inputs_dict.clear()  # Clear the dictionary storing inputs
        super().closeEvent(event)  # Call the base class closeEvent


class MainWindow(QMainWindow):
    aboutToClose = pyqtSignal()  # Signal emitted when the window is about to close

    def __init__(self, controller, title, id):
        super().__init__()
        self.controller = controller
        self.title = title
        self.id = id
        self.setWindowTitle(f"{self.title} Analyser ID: {self.id}")

    def main(self, info_dict):
        self.info_dict = info_dict
        self.radio_buttons = {}
        self.selected_buttons = {}
        
        # Main Widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main Layout
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)

        # Sections Layout
        sections_layout = QHBoxLayout()
        main_layout.addLayout(sections_layout)

        for key, value in self.info_dict.items():
            _frame = self.create_section(key, value)
            sections_layout.addWidget(_frame)

        self.expense_gui = ExpenseReportGUI()
        self.details_gui = DetailsGUI()
        self.invoice_gui = EnterInvoice()

        # Buttons Layout
        buttons_layout = QHBoxLayout()
        main_layout.addLayout(buttons_layout)
        guis = [self.expense_gui, self.details_gui, self.invoice_gui]

        # Buttons
        button_names = ["Create Expense Report", "Show Details", "Enter Invoice"]

        for i, name in enumerate(button_names):
            button = QPushButton(name)
            button.setFixedSize(150, 25)
            # button.clicked.connect(lambda checked, gui=guis[i]: self.show_gui(gui))
            if name != "Enter Invoice": 
                button.clicked.connect(lambda checked, name=name: self.read_buttons(name))  # Pass name as default argument
            else: 
                button.clicked.connect(lambda checked: self.invoice_gui.show())  # Connect to the function to show the invoice UI
            buttons_layout.addWidget(button)

    def read_buttons(self, name):
        self.selected_buttons = {}
        for title, key_values in self.radio_buttons.items():
            self.selected_buttons[title] = []
            for item_key, value in key_values.items():
                if self.radio_buttons[title][item_key].isChecked():
                    self.selected_buttons[title].append(item_key)

        if name == "Show Details": 
            self.controller.submit_show_details(self.selected_buttons, self.id)

    def show_gui(self, gui):
        gui.show()

    def create_section(self, title, items):
        # Scroll Area for Section
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)

        # Frame for Section
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.Box)
        frame.setFrameShadow(QFrame.Shadow.Plain)

        # Layout for Section
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)  # Align items to the top
        frame.setLayout(layout)

        # Title Label
        label = QLabel(title)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)

        # Button Group
        button_group = QButtonGroup()
        button_group.setExclusive(False)  # Allow deselecting "Select All"

        # "Select All" Square Radio Button
        select_all_button = QRadioButton("Select All")
        select_all_button.setStyleSheet("QRadioButton::indicator { width: 16px; height: 16px; }")
        select_all_button.clicked.connect(lambda: self.toggle_all_buttons(select_all_button, button_group))
        layout.addWidget(select_all_button)
        button_group.addButton(select_all_button)

        self.radio_buttons[title] = {}
        # Individual Circular Radio Buttons
        for item in items:
            radio_button = QRadioButton(item)
            layout.addWidget(radio_button)
            button_group.addButton(radio_button)
            self.radio_buttons[title][item] = radio_button

        # Set the frame as the widget for the scroll area
        scroll_area.setWidget(frame)

        return scroll_area

    def toggle_all_buttons(self, select_all_button, button_group):
        for button in button_group.buttons():
            if button != select_all_button:
                button.setChecked(select_all_button.isChecked())

    def closeEvent(self, event):
        """
        Override the close event to emit a signal before closing.
        """
        self.aboutToClose.emit()
        super().closeEvent(event)


class StartWindow(QMainWindow):
    def __init__(self, controller, spreadsheets):
        super().__init__()

        self.controller = controller

        self.setWindowTitle("Start Application")
        self.resize(400, 250)

        # Central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)  # Center everything
        central_widget.setLayout(layout)

        # Label on top
        self.label = QLabel("Select a spreadsheets:")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setContentsMargins(0, 25, 0, 25)  # Add 50px top & bottom padding
        layout.addWidget(self.label, alignment=Qt.AlignmentFlag.AlignCenter)

        # Dropdown menu
        self.dropdown = QComboBox()
        self.dropdown.setEditable(True)  # Allow typing
        self.dropdown.setFixedWidth(200)  # Set width for better appearance
        
        # Sample items for the dropdown
        self.items = spreadsheets
        self.dropdown.addItems(self.items)

        # Enable filtering with a QCompleter
        self.completer = QCompleter(self.items, self)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)  # Case insensitive
        self.completer.setFilterMode(Qt.MatchFlag.MatchContains)  # Filter items starting with input
        self.dropdown.setCompleter(self.completer)

        layout.addWidget(self.dropdown, alignment=Qt.AlignmentFlag.AlignCenter)

        # Submit button
        self.submit_button = QPushButton("Submit")
        self.submit_button.setFixedSize(150, 25)  # Set fixed size (150x25 px)
        self.submit_button.clicked.connect(self.on_submit)
        layout.addWidget(self.submit_button, alignment=Qt.AlignmentFlag.AlignCenter)

    def on_submit(self):
        """Handles the submit button click event."""
        selected_item = self.dropdown.currentText()
        print(f"Selected Spreadsheet: {selected_item}")
        self.controller.submit_spreadsheet(selected_item)