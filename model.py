import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from PyQt6.QtCore import Qt, QAbstractTableModel, QSize
from PyQt6.QtGui import QFont, QPainter, QPageSize, QImage
from PyQt6.QtPrintSupport import QPrinter
import os
from PyQt6.QtGui import QPageSize  # Import QPageSize


# class CheckError:
#     @classmethod
#     def main(self, var, func, *args):
   

# Singleton pattern ensures that only one instance of a class exists
class ConnectAPI:
    _instance = None  # Private class variable to hold the instance
    """child class for find spreadsheets"""

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        if hasattr(self, 'client'): return #prevents reintialization

        self.client = None
        self.scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
            ]
        self.credentials = Credentials.from_service_account_file("creds/MoneyMirrorCreds.json", scopes=self.scopes)
        self.spreadsheet_list = []

    def main(self):
        self._connect_google_worksheets()

    def _connect_google_worksheets(self):
        try:
            self.client = gspread.authorize(self.credentials)
        except gspread.exceptions.SpreadsheetNotFound as e:
            raise gspread.exceptions.SpreadsheetNotFound(f"Spreadsheet not found: {e}")
        except gspread.exceptions.APIError as e:
            print(f"Google Sheets API Error: {e}")
            # Check the error code for more specific handling if needed
            if e.response.status_code == 401:  # Unauthorized
                print("Authentication failed. Check your credentials.")
            elif e.response.status_code == 403: #Forbidden
                print("You do not have permission to access this resource")
            elif e.response.status_code == 429:
                print("Too many requests. Please wait before retrying.")
            elif e.response.status_code == 500: #Internal Server Error
                print("Google's server encountered an error. Please try again later.")
            elif e.response.status_code == 503: #Service Unavailable
                print("The service is currently unavailable. Please try again later.")
        except Exception as e: # Catch other gspread or general exceptions
            raise Exception(f"An unexpected error occurred during authorization: {e}")
    
    # List all accessible spreadsheets
    def get_spreadsheet_list(self):
        """
        Prints the titles and IDs of all spreadsheets the credentials have access to.
        """
        try:
            self.spreadsheets_meta_data = self.client.list_spreadsheet_files()
            if not self.spreadsheets_meta_data:
                print("No spreadsheets found with these credentials.")
            else:
                print("Accessible Spreadsheets:")
                for sheet in self.spreadsheets_meta_data:
                    print(f"Title: {sheet['name']}, ID: {sheet['id']}")
                    self.spreadsheet_list.append(sheet['name'])
        except gspread.exceptions.APIError as e:
            print(f"Google Sheets API Error: {e}")
            # Check the error code for more specific handling if needed
            if e.response.status_code == 401:  # Unauthorized
                print("Authentication failed. Check your credentials.")
            elif e.response.status_code == 403: #Forbidden
                print("You do not have permission to access this resource")
            elif e.response.status_code == 429:
                print("Too many requests. Please wait before retrying.")
            elif e.response.status_code == 500: #Internal Server Error
                print("Google's server encountered an error. Please try again later.")
            elif e.response.status_code == 503: #Service Unavailable
                print("The service is currently unavailable. Please try again later.")
            return None
        except gspread.exceptions.SpreadsheetNotFound as e:
            print(f"Spreadsheet not found: {e}")
            return None
        except gspread.exceptions.WorksheetNotFound as e:
            print(f"Worksheet not found: {e}")
            return None
        except gspread.exceptions.IncorrectCellLabel as e:
            print(f"Incorrect Cell label: {e}")
            return None
        except Exception as e:  # Catch other potential exceptions (network issues, etc.)
            print(f"An unexpected error occurred: {e}")
            return None
        
        return self.spreadsheet_list


class FilterData:
    def __init__(self, df, selection_info):
        self.dfMain = df
        self.selection_info = selection_info
        self.filtered_df = pd.DataFrame()
        self.start() 
    
    def start(self):
        for key, value in self.selection_info.items():
            if value:
                self._filter_data(key)

        return self.filtered_df

    def _filter_data(self, key):
        """Filters the DataFrame by the selected key."""
        _pattern = "|".join(self.selection_info[key])  # Create the regex pattern from the selected key
        print(_pattern)

        if self.filtered_df.empty:  # Check if the DataFrame is empty (no parentheses needed)
            self.filtered_df = self.dfMain[self.dfMain[key].str.contains(_pattern, case=False, na=False)]
        else:
            self.filtered_df = self.filtered_df[self.filtered_df[key].str.contains(_pattern, case=False, na=False)]


class SaveAsModel:
    @staticmethod
    def start(model, file_path):
        """
        Saves the PandasModel data to a CSV file.

        :param model: Instance of PandasModel containing the DataFrame
        :param file_path: Path to save the CSV file
        """
        if not isinstance(model, PandasModel):
            print("Error: Provided model is not an instance of PandasModel.")
            return

        try:
            # Extract the DataFrame from PandasModel
            df = model._data.copy()

            # Remove the totals row and empty row before saving (assuming last two rows)
            # if model.bold_row_index is not None and model.bold_row_index < len(df):
            #     df = df.iloc[:model.bold_row_index]  # Remove totals row and empty row

            # Save to CSV
            df.to_csv(file_path, index=False)
            print(f"File saved successfully at: {file_path}")

        except Exception as e:
            print(f"An error occurred while saving CSV: {e}")


from PyQt6.QtPrintSupport import QPrinter
from PyQt6.QtGui import QPainter, QPageSize, QImage
from PyQt6.QtCore import Qt, QRect
import os

class PrintModel:
    @staticmethod
    def save_as_pdf(table_view, file_path):
        """
        Saves the full QTableView (including scrolled-off parts) as a multi-page PDF.
        """

        if not file_path.lower().endswith(".pdf"):
            file_path += ".pdf"

        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        # Ensure the entire table is captured, not just the visible part
        full_size = table_view.viewport().sizeHint()
        table_width, table_height = full_size.width(), full_size.height()

        # Create an off-screen image with full dimensions
        table_image = QImage(table_width, table_height, QImage.Format.Format_RGB32)
        table_image.fill(Qt.GlobalColor.white)

        # Render full table to the image
        painter = QPainter(table_image)
        table_view.render(painter)
        painter.end()

        # Setup printer for high-quality PDF
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(file_path)
        printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))

        # Get PDF page dimensions
        page_rect = printer.pageLayout().paintRectPixels(printer.resolution())
        page_width, page_height = page_rect.width(), page_rect.height()

        # Initialize printer and painter
        painter = QPainter(printer)
        current_y = 0  # Track the vertical position for multi-page rendering

        while current_y < table_height:
            # Create a cropped image for the current page
            cropped_image = table_image.copy(QRect(0, current_y, table_width, page_height))

            # Scale the image to fit the page width while maintaining aspect ratio
            scaled_image = cropped_image.scaledToWidth(page_width, Qt.TransformationMode.SmoothTransformation)

            # Center the scaled image vertically
            y_offset = (page_height - scaled_image.height()) // 2 if scaled_image.height() < page_height else 0

            # Draw the image on the printer
            painter.drawImage(0, y_offset, scaled_image)

            # Move to the next page
            current_y += page_height
            if current_y < table_height:
                printer.newPage()  # Start a new page

        painter.end()
        print(f"✅ Multi-page PDF saved successfully at: {file_path}")



class PandasModel(QAbstractTableModel):
    def __init__(self, data):
        super().__init__()
        self._data = data
        self.bold_row_index = None
        self.calculate_totals()

    def calculate_totals(self):
        try:
            # Identify numeric columns and calculate totals
            totals = {
                col: f"{self._data[col].sum(skipna=True):.2f}" 
                if col in self._data else 0 
                for col in Model.numeric_columns
                }

            # Create an empty row
            empty_row = {col: '' for col in self._data.columns}
            
            # Create a totals row with calculated totals
            totals_row = {col: totals.get(col, '') for col in self._data.columns}
            totals_row['Trip'] = 'Total'  # Add a label for the totals row
            
            # Append the empty row and totals row to the DataFrame
            self._data = pd.concat([self._data, pd.DataFrame([empty_row]), pd.DataFrame([totals_row])], ignore_index=True)
            
            # Save the index of the totals row for styling
            self.bold_row_index = len(self._data) - 1
        except Exception as e:
            print(f"An error occurred during total calculation: {e}")

    def data(self, index, role):
        row = index.row()
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if 0 <= row < len(self._data) and 0 <= col < len(self._data.columns):
                return str(self._data.iloc[row, col])

        if role == Qt.ItemDataRole.FontRole and row == self.bold_row_index:
            font = QFont()
            font.setBold(True)
            font.setPointSize(12)  # Increase the font size for the totals row
            return font

        return None

    def rowCount(self, parent=None):
        return len(self._data)

    def columnCount(self, parent=None):
        return len(self._data.columns)

    def headerData(self, section, orientation, role):
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                return str(self._data.columns[section])
            elif orientation == Qt.Orientation.Vertical:
                # Add an index on the left side of the table
                return str(section + 1)
        return None


class Model:

    numeric_columns = ['Trip Amount','Miscellaneous Income','Dispatch 9%','Dispatch 8%' ,'Fuel','Expenses','Total','Amount Received']
    _months = {"January": "Jan","February": "Feb","March": "Mar","April": "Apr","May": "May",  "June": "Jun",
                "July": "Jul","August": "Aug","September": "Sep","October": "Oct","November": "Nov","December": "Dec"}
    _month_reverse = {value: key for key, value in _months.items()}
    _other_expenses = ["Fuel","Insurance","Lumper","Advance","Lay Over"]
    _states = {'Alabama': 'AL', 'Alaska': 'AK', 'Arizona': 'AZ', 'Arkansas': 'AR', 'California': 'CA', 'Colorado': 'CO', 'Connecticut': 'CT', 
            'Delaware': 'DE', 'Florida': 'FL', 'Georgia': 'GA', 'Hawaii': 'HI', 'Idaho': 'ID', 'Illinois': 'IL', 'Indiana': 'IN', 'Iowa': 'IA', 
            'Kansas': 'KS', 'Kentucky': 'KY', 'Louisiana': 'LA', 'Maine': 'ME', 'Maryland': 'MD', 'Massachusetts': 'MA', 'Michigan': 'MI', 
            'Minnesota': 'MN', 'Mississippi': 'MS', 'Missouri': 'MO', 'Montana': 'MT', 'Nebraska': 'NE', 'Nevada': 'NV', 'New Hampshire': 'NH', 
            'New Jersey': 'NJ', 'New Mexico': 'NM', 'New York': 'NY', 'North Carolina': 'NC', 'North Dakota': 'ND', 'Ohio': 'OH', 'Oklahoma': 'OK', 
            'Oregon': 'OR', 'Pennsylvania': 'PA', 'Rhode Island': 'RI', 'South Carolina': 'SC', 'South Dakota': 'SD', 'Tennessee': 'TN', 'Texas': 'TX', 
            'Utah': 'UT', 'Vermont': 'VT', 'Virginia': 'VA', 'Washington': 'WA', 'West Virginia': 'WV', 'Wisconsin': 'WI', 'Wyoming': 'WY'}
    _trip_pattern = r"^[A-Z]{2}-[A-Z]{2}$"  # Matches pattern like "PA-TX", "AB-CD"
    _expense_descriptions = {
        "fuel": "Fuel",
        "lumper": "Lumper",
        "lay over": "Lay Over",
        "layover": "Lay Over",
        "insurance": "Insurance",
        "tolls": "Toll",
        "maintenance": "Maintenance",
        "advance": "Advance",
        "cash advance": "Advance",
    }
    
    def __init__(self, spreadsheet, id):
        self.client = ConnectAPI().client  # Access the singleton instance's client
        self.id = id
        self.spreadsheet = spreadsheet
        self.dfMain = pd.DataFrame()
        self.available_months = []
        self.available_expenses = []
    
    
    def _get_worksheetsheet_list(self):

        try:
            worksheets = self.client.open(self.spreadsheet)
            self.worksheets = worksheets.worksheets()
        except gspread.SpreadsheetNotFound:
            print(f"Spreadsheet '{self.spreadsheet}' not found. Check the name and sharing permissions.")


    def is_empty_row(self, row) -> bool:
        """Checks if a row is effectively empty (handles strings, whitespace, None, NaN, and 0.0)."""
        return all(
            (isinstance(cell, str) and not cell.strip()) or "$0.0" in cell
            for cell in row
        )
    

    def _get_data_with_header(self, worksheet):

        all_values = worksheet.get_all_values()
        if not all_values:
            print("Sheet is empty.")
            return None

        for i, row in enumerate(all_values):
            if row and str(row[0]).strip().startswith("Date"):
                header_row_index = i
                break
        else:  # No 'Date' row found
            print("No header row found with 'Date' in the first column.")
            return None

        header = all_values[header_row_index][:11]
        data = []

        for row in all_values[header_row_index + 1:]:
            row = [str(cell).strip() if isinstance(cell, (str, int, float)) else cell for cell in row[:11]]
            if self.is_empty_row(row):
                break
            data.append(row)

        if not data:
            print("No valid data rows found.")
            return None

        df = pd.DataFrame(data, columns=header)
        df.columns = df.columns.str.strip()  # Clean column names
        return df
    
    def _filter_data(self, df, worksheet_title):

        df_filtered = df.copy()

        for column in df.columns:
            if column in Model.numeric_columns:
                df_filtered[column] = df_filtered[column].astype(str).str.replace(r'[$,]', '', regex=True) # Remove $ and ,

                # Convert to numeric (this will handle the negative signs correctly)
                df_filtered[column] = pd.to_numeric(df_filtered[column], errors='coerce')
                # print(df_filtered['Total'])
            # else:
            #     df_filtered[column] = df_filtered[column].mask(df_filtered[column] == '').ffill()

        # df_filtered['Date'] = df_filtered['Date'].mask(df_filtered['Date'] == '').ffill()

        month_abr = next((_month for _month in set(Model._months.values()) if _month in worksheet_title), None)
        # self.available_months[Model._month_reverse[month_abr]] = month_abr

        self.available_months.append(Model._month_reverse[month_abr])
        # Replace whitespace or empty strings with "Mar"
        df_filtered['Date'] = df_filtered['Date'].replace(r'^\s*$', month_abr, regex=True)

        # Add the "Month" column and fill with "month"
        df_filtered['Month'] = Model._month_reverse[month_abr]  # This is the most efficient way

        return df_filtered


    def _add_expense_column(self): 
        # Define the patterns and mappings

        # Update the Expense column based on both "Trip" and "Load" columns
        def get_expense(row):
            # Check if either "Trip" or "Load" matches the trip pattern
            if pd.Series(row["Trip"]).str.match(Model._trip_pattern).any():
                return "Trip"
            # Otherwise, match with known expense descriptions
            return Model._expense_descriptions.get(row["Trip"].lower(), Model._expense_descriptions.get(row["Load"].lower(), "Other"))

        # Apply the function to each row
        self.dfMain["Expense"] = self.dfMain.apply(get_expense, axis=1)
        # self.available_expenses = list(set(self.dfMain["Expense"]))
        self.available_expenses = sorted(set(self.dfMain["Expense"]))

    
    def main(self):

        self._get_worksheetsheet_list()

        for worksheet in self.worksheets:
            if (worksheet.title == "Jan 2024") or (worksheet.title == "Feb 2024") or ("Template" in worksheet.title) :
                continue
            print(f"Sheet '{worksheet.title}' selected successfully!")

            dfRaw = self._get_data_with_header(worksheet)
            if dfRaw is not None:
                dfFiltered = self._filter_data(dfRaw, worksheet.title)
                # Concatenate vertically (append rows)
                self.dfMain = pd.concat([self.dfMain, dfFiltered], ignore_index=True)  # ignore_index resets the index

        self._add_expense_column()

        _return_dict = {"Year": ["2024","2025"], "Month": self.available_months, "Expense": self.available_expenses}

        return _return_dict

