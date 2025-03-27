"""
Created: 2025.01.20

Author: Eashan Polwatta Gallage
Email: eashanpol@gmail.com
"""

"""
1. only have 1 csv window"""

import sys
from queue import Queue
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QThread, pyqtSignal, QObject

from model import Model, ConnectAPI, FilterData, PandasModel, SaveAsModel, PrintModel
from view import LoadingScreen, StartWindow, MainWindow, CSVWindow

class Worker(QObject):
    """
    Worker class for running tasks in a separate thread.
    """
    finished = pyqtSignal()  # Signal emitted when the task is complete
    result_ready = pyqtSignal(object)  # Signal emitted with task results

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def run(self):
        """
        Execute the task and emit signals upon completion.
        """
        try:
            result = self.func(*self.args, **self.kwargs)
            self.result_ready.emit(result)  # Emit the result
        except Exception as e:
            print(f"Error in worker thread: {e}")
            self.result_ready.emit(None)
        finally:
            self.finished.emit()  # Emit the finished signal


class Controller:
    """
    The main controller that drives the application logic.
    """
    def __init__(self):
        # self.model = Model()
        self.connectapi = ConnectAPI()
        self.loading_screen = LoadingScreen()
        self.save_as_model = SaveAsModel()
        self.main_windows = {}
        self.models = {}
        self.csv_windows = {}
        self.main_window_counter = 0  # Counter for unique IDs
        self.csv_window_counter = 0  # Counter for unique IDs
        self.temp_df = None

    def main(self):
        """
        Main entry point of the application.
        """
        self._start_app()

    def _start_app(self):
        """
        Start the application with `self.model.main` followed by `self.model.get_spreadsheet_list`.
        """
        self.loading_screen.show()

        # Step 1: Run `self.model.main` in the first QThread
        self.thread1 = QThread()
        self.worker1 = Worker(self.connectapi.main)
        self.worker1.moveToThread(self.thread1)

        # Step 2: Run `self.model.get_spreadsheet_list` in the second QThread after the first one completes
        self.thread2 = QThread()
        self.worker2 = Worker(self.connectapi.get_spreadsheet_list)
        self.worker2.moveToThread(self.thread2)

        # Connect signals for worker1 (self.model.main)
        self.thread1.started.connect(self.worker1.run)
        self.worker1.finished.connect(self.thread1.quit)
        self.worker1.finished.connect(self.thread1.deleteLater)
        
        # Start `self.thread2` only after `self.worker1` finishes
        self.worker1.finished.connect(self.thread2.start)

        # Connect signals for worker2 (self.model.get_spreadsheet_list)
        self.thread2.started.connect(self.worker2.run)
        self.worker2.result_ready.connect(self.handle_spreadsheets_result)
        self.worker2.finished.connect(self.thread2.quit)
        self.worker2.finished.connect(self.thread2.deleteLater)
        self.worker2.finished.connect(self.loading_screen.close)

        # Start the first thread
        self.thread1.start()

    def handle_spreadsheets_result(self, spreadsheets):
        """
        Handle the result of fetching spreadsheets.
        """
        self.spreadsheets = spreadsheets
        if self.spreadsheets:
            print("Spreadsheets Found:", self.spreadsheets)
            self.start_window = StartWindow(self, self.spreadsheets)
            # self.start_window.update_spreadsheets(result)
        else:
            print("No spreadsheets found or an error occurred.")
        self.start_window.show()

    def submit_spreadsheet(self, spreadsheet):
        """
        Show the loading screen, create a new MainWindow, and run the `get_data` method in a separate thread.
        """
        """TODO: keyboard shortcuts to open new ES and SS to view
        TODO: make it familiar, dropdown menu"""
        # Optional limit to the number of open windows
        if len(self.main_windows) > 2:
            print("Too many windows open. Exiting submit_spreadsheet.")  # Optional message
            return  # Exit the function
        
        self.loading_screen.show()
        
        # Increment the counter to assign a new unique ID
        self.main_window_counter += 1
        unique_id = self.main_window_counter

        # Create a new instance of MainWindow and Model, then add it to the list
        new_model = Model(spreadsheet, unique_id)
        new_main_window = MainWindow(self, spreadsheet, unique_id)

        # self.models.append(new_model)
        # self.main_windows.append(new_main_window)
        self.models[unique_id] = new_model
        self.main_windows[unique_id] = new_main_window

        # Connect the MainWindow's close event to a cleanup function
        new_main_window.aboutToClose.connect(lambda: self.cleanup_main_window(unique_id))

        # Create a QThread and worker for fetching data
        self.thread3 = QThread()
        self.worker3 = Worker(new_model.main)
        self.worker3.moveToThread(self.thread3)

        # Connect signals
        self.thread3.started.connect(self.worker3.run)
        self.worker3.finished.connect(self.loading_screen.close)
        self.worker3.result_ready.connect(new_main_window.main)
        self.worker3.finished.connect(new_main_window.show)
        self.worker3.finished.connect(self.thread3.quit)
        self.worker3.finished.connect(self.thread3.deleteLater)


        # Start the thread
        self.thread3.start()

    def cleanup_main_window(self, unique_id):
        """
        Cleanup method to remove the MainWindow and its corresponding Model.
        """
        del self.models[unique_id]
        del self.main_windows[unique_id]
        print(f"Cleaned up main window: {unique_id}")

    def submit_show_details(self, selected_buttons, unique_id):
        """TODO:only have 1 window
        TODO: CHECK COMMENTING"""
        print(unique_id, selected_buttons)
        self.temp_unique_id = unique_id

        filter_data_model = FilterData(self.models[unique_id].dfMain, selected_buttons) 

        self.loading_screen.show()

        # Create a QThread and worker for fetching the filtered data (thread4)
        self.thread4 = QThread()
        self.worker4 = Worker(filter_data_model.start)
        self.worker4.moveToThread(self.thread4)

        # Connect signals for thread4
        self.thread4.started.connect(self.worker4.run)
        self.worker4.result_ready.connect(self.handle_filtered_data)
        self.worker4.finished.connect(self.thread4.quit)
        self.worker4.finished.connect(self.thread4.deleteLater)

        # Create a QThread and worker for processing formatted data (thread5)
        self.thread5 = QThread()
        self.worker5 = Worker(PandasModel, None)  # Initially pass None, updated later
        self.worker5.moveToThread(self.thread5)

        # Connect signals for thread5
        self.thread5.started.connect(self.worker5.run)
        self.worker5.result_ready.connect(self.handle_formatted_df)
        self.thread5.started.connect(self.loading_screen.close)
        self.worker5.finished.connect(self.thread5.quit)
        self.worker5.finished.connect(self.thread5.deleteLater)

        # Start thread5 only after thread4 finishes
        self.worker4.finished.connect(self.start_thread5)

        # Start thread4
        self.thread4.start()

    def start_thread5(self):
        """
        Start thread5 after thread4 is complete and self.temp_df is populated.
        """
        # Update worker5's arguments with the new DataFrame
        self.worker5.args = (self.temp_df,)
        self.thread5.start()

    def handle_filtered_data(self, temp_df):
        """
        Handle the filtered data from worker4.
        """
        self.temp_df = temp_df

    def handle_formatted_df(self, formatted_df):
        """
        Handle the formatted data from worker5.
        """
        self.csv_window_counter += 1
        key = f"{self.temp_unique_id}.{self.csv_window_counter}"
        csv_window = CSVWindow(formatted_df, key, self)
        self.csv_windows[key] = csv_window

        # Connect the MainWindow's close event to a cleanup function
        csv_window.aboutToClose.connect(lambda: self.cleanup_csv_window(key))
        csv_window.show()
    
    def save_data(self, csv_window_key, file_path, option):

        print(type(self.csv_windows[csv_window_key].model))

        # self.loading_screen.show()

        # Create a QThread and worker for fetching the filtered data (thread4)
        self.thread6 = QThread()
        if option == "Save As":
            self.worker6 = Worker(self.save_as_model.start, self.csv_windows[csv_window_key].model, file_path)
        else: 
            # self.worker6 = Worker(PrintModel.save_as_pdf, self.csv_windows[csv_window_key], file_path)
            self.worker6 = Worker(PrintModel.generate_pdf_from_table, self.csv_windows[csv_window_key].model, file_path)  # Use the static method
        self.worker6.moveToThread(self.thread6)

        # Connect signals for thread4
        self.thread6.started.connect(self.worker6.run)
        self.worker6.finished.connect(self.loading_screen.close)
        self.worker6.finished.connect(self.thread6.quit)
        self.worker6.finished.connect(self.thread6.deleteLater)

        self.thread6.start()
    
    def cleanup_csv_window(self, unique_id):
        """
        Cleanup method to remove the MainWindow and its corresponding Model.
        """
        del self.csv_windows[unique_id]
        print(f"Cleaned up CSV window: {unique_id}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    controller = Controller()
    controller.main()
    sys.exit(app.exec())
