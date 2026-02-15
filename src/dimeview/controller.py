#!/usr/bin/env python3
"""
controller.py

Controller component for DimeView application.
Connects the model and views, handling user interactions and orchestrating data flow.
"""
import sys
from datetime import datetime
from PyQt6.QtWidgets import QApplication, QMessageBox, QCompleter
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject
from dimeview.view import StartupWindow, MainWindow, LoadingDialog, SharingInstructionsDialog
from dimeview.model import DimeViewModel, GoogleQuotaExceededError
from googleapiclient.errors import HttpError


# --- Worker classes ---

class SpreadsheetLoader(QObject):
    finished = pyqtSignal(object)  # error or None

    def __init__(self, model, spreadsheet_id):
        super().__init__()
        self.model = model
        self.spreadsheet_id = spreadsheet_id

    def run(self):
        try:
            self.model.select_spreadsheet(self.spreadsheet_id)
            self.finished.emit(None)
        except Exception as e:
            self.finished.emit(e)


class DetailedReportGenerator(QObject):
    finished = pyqtSignal(object, object)  # data or None, error or None

    def __init__(self, model, from_date, to_date, load_no, transaction, driver=None, truck=None, from_state=None, to_state=None):
        super().__init__()
        self.model = model
        self.from_date = from_date
        self.to_date = to_date
        self.load_no = load_no
        self.transaction = transaction
        self.driver = driver
        self.truck = truck
        self.from_state = from_state
        self.to_state = to_state

    def run(self):
        try:
            rows = self.model.generate_detailed_report(
                self.from_date, self.to_date, self.load_no, self.transaction, self.driver, self.truck,
                self.from_state, self.to_state
            )
            self.finished.emit(rows, None)
        except Exception as e:
            self.finished.emit(None, e)


class SummaryReportGenerator(QObject):
    finished = pyqtSignal(object, object)  # summary or None, error or None

    def __init__(self, model, from_date, to_date, load_no, transaction, driver=None, from_state=None, to_state=None):
        super().__init__()
        self.model = model
        self.from_date = from_date
        self.to_date = to_date
        self.load_no = load_no
        self.transaction = transaction
        self.driver = driver
        self.from_state = from_state
        self.to_state = to_state

    def run(self):
        try:
            summary = self.model.generate_summary_report(
                self.from_date, self.to_date, self.load_no, self.transaction, self.driver,
                self.from_state, self.to_state
            )
            self.finished.emit(summary, None)
        except Exception as e:
            self.finished.emit(None, e)


class EntrySubmitter(QObject):
    finished = pyqtSignal(object)  # error or None

    def __init__(self, model, *args, **kwargs):
        super().__init__()
        self.model = model
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            self.model.append_entry(*self.args, **self.kwargs)
            self.finished.emit(None)
        except Exception as e:
            self.finished.emit(e)


# --- Controller class ---
class DimeViewController:
    """Orchestrates interactions between the model and view."""
    def __init__(self, model):
        self.model = model

        try:
            sheets = self.model.list_spreadsheets()
        except GoogleQuotaExceededError:
            QMessageBox.warning(None, "Quota Exceeded",
                "Google Sheets API quota exceeded while listing spreadsheets. Please wait and restart the app.")
            sys.exit(1)
        except HttpError as e:
            QMessageBox.critical(None, "Google API Error",
                f"Google API error while listing spreadsheets:\n{e}")
            sys.exit(1)

        self.startup_window = StartupWindow()
        self.startup_window.set_spreadsheets(sheets)
        self.startup_window.spreadsheet_selected.connect(self.handle_spreadsheet_selection)
        self.startup_window.show_sharing_instructions.connect(self.show_sharing_help)
        
        # Connect the new signal for the refresh button
        self.startup_window.refresh_requested.connect(self.handle_refresh_spreadsheets)
        
        self.startup_window.show()

    def handle_refresh_spreadsheets(self):
        """Fetches the latest list of spreadsheets and updates the dropdown."""
        try:
            # Disable the button to prevent multiple clicks while refreshing
            self.startup_window.refresh_btn.setEnabled(False)
            
            # Re-fetch the list from the model
            sheets = self.model.list_spreadsheets()
            
            # Update the view with the new list
            self.startup_window.set_spreadsheets(sheets)
            QMessageBox.information(self.startup_window, "Success", "Spreadsheet list has been updated.")
            
        except GoogleQuotaExceededError:
            QMessageBox.warning(self.startup_window, "Quota Exceeded",
                "Google Sheets API quota exceeded. Please wait and try again.")
        except HttpError as e:
            QMessageBox.critical(self.startup_window, "Google API Error",
                f"An error occurred while refreshing:\n{e}")
        finally:
            # Always re-enable the button, even if an error occurred
            self.startup_window.refresh_btn.setEnabled(True)

    def show_sharing_help(self):
        """
        Retrieves the client email and shows the sharing instructions dialog.
        """
        try:
            client_email = self.model.get_client_email()
            dialog = SharingInstructionsDialog(client_email, self.startup_window)
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(None, "Error", f"Could not retrieve client email: {e}")


    def handle_spreadsheet_selection(self, spreadsheet_id, spreadsheet_name):
        # Close the old window FIRST for immediate feedback.
        self.startup_window.close() 

        self.spreadsheet_name = spreadsheet_name

        # Now show the loading dialog. It won't be tied to the startup window.
        self.loading_dialog = LoadingDialog("Loading spreadsheet, please wait...")
        self.loading_dialog.show()

        self.loader_thread = QThread()
        self.loader_worker = SpreadsheetLoader(self.model, spreadsheet_id)
        # ... rest of the function is the same
        self.loader_worker.moveToThread(self.loader_thread)
        self.loader_thread.started.connect(self.loader_worker.run)
        self.loader_worker.finished.connect(self._on_spreadsheet_loaded)
        self.loader_worker.finished.connect(self.loader_thread.quit)
        self.loader_worker.finished.connect(self.loader_worker.deleteLater)
        self.loader_thread.finished.connect(self.loader_thread.deleteLater)
        self.loader_thread.start()

    def _on_spreadsheet_loaded(self, error):
        # DO NOT close the loading dialog here.
        if error:
            self.loading_dialog.close() # Close it only if there's an error.
            QMessageBox.critical(None, "Error", f"Failed to load spreadsheet: {error}")
            return
        # If successful, proceed to setup the main window.
        self.setup_main_window()

    def setup_main_window(self):
        # DO NOT close the startup_window here, it's already closed.
        self.main_window = MainWindow()
        # Update the main window title to include the selected spreadsheet ID
        self.main_window.setWindowTitle(f"MoneyMirror: {self.spreadsheet_name}")
        self.setup_data_entry_tab()
        self.setup_reports_tab()
        # DO NOT show the main_window here. It will be shown when all data is loaded.


    def setup_data_entry_tab(self):
        data_tab = self.main_window.data_entry_tab
        self.us_states = self.model.get_us_states()

        # From / To state dropdowns
        data_tab.from_state_combo.clear()
        data_tab.from_state_combo.addItems(self.us_states)
        completer_from = QCompleter(self.us_states)
        completer_from.setFilterMode(Qt.MatchFlag.MatchContains)
        completer_from.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        data_tab.from_state_combo.setCompleter(completer_from)

        data_tab.to_state_combo.clear()
        data_tab.to_state_combo.addItems(self.us_states)
        completer_to = QCompleter(self.us_states)
        completer_to.setFilterMode(Qt.MatchFlag.MatchContains)
        completer_to.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        data_tab.to_state_combo.setCompleter(completer_to)

        # Load Nos
        try:
            load_nos = self.model.get_all_load_nos()
        except GoogleQuotaExceededError:
            QMessageBox.warning(None, "Quota Exceeded",
                "Google Sheets API quota exceeded while fetching Load Nos. Please wait and try again.")
            load_nos = []
        except HttpError as e:
            QMessageBox.critical(None, "Google API Error",
                f"Google API error while fetching Load Nos.:\n{e}")
            load_nos = []

        # Driver / Truck IDs
        try:
            driver_ids = self.model.get_all_driver_ids()
        except GoogleQuotaExceededError:
            QMessageBox.warning(None, "Quota Exceeded",
                "Google Sheets API quota exceeded while fetching Driver IDs. Please wait and try again.")
            driver_ids = []

        try:
            truck_ids = self.model.get_all_truck_ids()
        except GoogleQuotaExceededError:
            QMessageBox.warning(None, "Quota Exceeded",
                "Google Sheets API quota exceeded while fetching Truck IDs. Please wait and try again.")
            truck_ids = []

        # Populate combos
        data_tab.load_no_combo.clear()
        data_tab.load_no_combo.setEditable(True)
        data_tab.load_no_combo.addItems(load_nos)
        # Disable auto-completion for load_no to prevent partial matching
        data_tab.load_no_combo.setCompleter(None)

        data_tab.driver_id_combo.clear()
        data_tab.driver_id_combo.setEditable(True)
        data_tab.driver_id_combo.addItems(driver_ids)

        data_tab.truck_id_combo.clear()
        data_tab.truck_id_combo.setEditable(True)
        data_tab.truck_id_combo.addItems(truck_ids)

        data_tab.transaction_combo.clear()
        data_tab.transaction_combo.addItems(self.model.get_transaction_types())

        data_tab.delivery_combo.clear()
        delivery_opts = [''] + self.model.get_delivery_status_options()
        data_tab.delivery_combo.addItems(delivery_opts)

        data_tab.payment_combo.clear()
        data_tab.payment_combo.addItems(self.model.get_payment_status_options())

        # —— dynamic behavior wiring —— 
        # Auto-set Payment Status to 'Complete' when 'Full Payment' is selected
        data_tab.transaction_combo.currentTextChanged.connect(self.on_transaction_changed)
        # → Auto-populate fields when Load No. changes
        data_tab.load_no_combo.currentTextChanged.connect(self.on_load_no_changed)

        # Submit / Reset
        data_tab.submit_button.clicked.connect(self.handle_data_entry_submit)
        data_tab.reset_form()

    def on_transaction_changed(self, transaction_text: str):
        """
        If user picks Full Payment, auto-set Payment Status to Complete.
        """
        if transaction_text == 'Full Payment':
            # Auto-set Payment Status only when the user explicitly selects 'Full Payment'
            tab = self.main_window.data_entry_tab
            tab.payment_combo.setCurrentText('Complete')

    def on_load_no_changed(self, load_no):
        """Fetch latest entry for a load_no and populate form fields."""
        if not load_no or load_no == 'Other':
            return

        try:
            # Pull all rows for this load (no date filters)
            rows = self.model.generate_detailed_report(None, None, load_no=load_no)
            latest_entry = self.model.get_latest_entry(rows)

            if not latest_entry:
                return

            # Update the view with the latest entry data
            tab = self.main_window.data_entry_tab
            tab.populate_from_entry(latest_entry)
            
            # Also fetch and set the latest fraction value
            latest_fraction = self.model.get_latest_fraction(load_no)
            tab.fraction_edit.setText(str(latest_fraction))
            tab.fraction_edit.setEnabled(True)
            
            # Clear transaction-specific fields for fresh entry
            tab.transaction_combo.setCurrentIndex(-1)
            tab.credit_edit.clear()
            tab.debit_edit.clear()
            tab.details_edit.clear()
        except (GoogleQuotaExceededError, HttpError) as e:
            # Silently fail on auto-populate (non-blocking operation)
            pass

    def handle_data_entry_submit(self):
        data_tab = self.main_window.data_entry_tab

        date_val = data_tab.date_edit.date().toPyDate()
        if data_tab.existing_load_radio.isChecked():
            load_no = data_tab.load_no_combo.currentText().strip()
            if not load_no:
                QMessageBox.critical(None, "Error", "Please enter or select a Load No.")
                return
        else:
            load_raw = data_tab.custom_load_edit.text().strip()
            load_no = load_raw if load_raw else "Other"
        # New fields
        driver_id = data_tab.driver_id_combo.currentText().strip()
        truck_id  = data_tab.truck_id_combo.currentText().strip()
        transaction = data_tab.transaction_combo.currentText()
        delivery_status = data_tab.delivery_combo.currentText()
        payment_status = data_tab.payment_combo.currentText()
        credit_text = data_tab.credit_edit.text().strip()
        debit_text = data_tab.debit_edit.text().strip()
        fraction_text = data_tab.fraction_edit.text().strip()
        user_details = data_tab.details_edit.toPlainText().strip()

        if not credit_text and not debit_text:
             QMessageBox.critical(None, "Error", "Please input either Credit or Debit amount.")
             return

        try:
            credit_amt = float(credit_text) if credit_text else 0.0
        except ValueError:
            QMessageBox.critical(None, "Error", f"Invalid credit amount: '{credit_text}'")
            return

        try:
            debit_amt = float(debit_text) if debit_text else 0.0
        except ValueError:
            QMessageBox.critical(None, "Error", f"Invalid debit amount: '{debit_text}'")
            return

        fraction_percent = None
        details = user_details

        if data_tab.existing_load_radio.isChecked():
            try:
                fraction_percent = float(fraction_text) if fraction_text else 3.5
            except ValueError:
                QMessageBox.critical(None, "Error", f"Invalid fraction percentage: '{fraction_text}'")
                return
            
            # Build details with fraction info
            fraction_info = f"Fraction {fraction_percent}%"
            details = f"{fraction_info}" if not user_details else f"{fraction_info} - {user_details}"
        
        def validate_and_format_state(state_text, field_name, valid_states, model):
            """Validate state and convert abbreviations to full format. Empty values are allowed."""
            state_text = state_text.strip()
            if not state_text:
                return ""  # Allow empty states
            
            # If already in full format (contains ':'), use as-is
            if ':' in state_text:
                if state_text in valid_states:
                    return state_text
                else:
                    QMessageBox.critical(None, "Error", f"Invalid {field_name} entry: '{state_text}'")
                    return None
            
            # If abbreviation (2 letters), convert to full format
            if len(state_text) == 2:
                formatted = model.format_state_input(state_text)
                if formatted in valid_states:
                    return formatted
                else:
                    QMessageBox.critical(None, "Error", f"'{state_text}' is not a valid state abbreviation for {field_name}")
                    return None
            
            # Try partial name match
            formatted = model.format_state_input(state_text)
            if formatted in valid_states:
                return formatted
            
            QMessageBox.critical(None, "Error", f"Invalid {field_name} entry: '{state_text}'")
            return None

        from_text = data_tab.from_state_combo.currentText()
        to_text = data_tab.to_state_combo.currentText()
        
        from_text = validate_and_format_state(from_text, "From State", self.us_states, self.model)
        if from_text is None:
            return
        
        to_text = validate_and_format_state(to_text, "To State", self.us_states, self.model)
        if to_text is None:
            return

        from_state = from_text.split(':')[0].strip() if from_text else ""
        to_state = to_text.split(':')[0].strip() if to_text else ""

        # Pre-submission status & field change check (sync with model)
        try:
            if load_no and load_no != "Other":
                prev_rows = self.model.generate_detailed_report(None, date_val, load_no, None)
                latest_prev = self.model.get_latest_entry(prev_rows)
                if latest_prev:
                    # Get changes from model (including fraction changes)
                    changes = self.model.detect_field_changes(
                        latest_prev, driver_id, truck_id, from_state, to_state,
                        delivery_status, payment_status, fraction_percent
                    )
                    if changes:
                        msg = (
                            f"This submission will update the following fields for all previous entries of Load No. {load_no}:\n  " +
                            "\n  ".join(changes) +
                            "\nProceed?"
                        )
                        reply = QMessageBox.question(
                            None, "Confirm updates", msg,
                            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                        )
                        if reply != QMessageBox.StandardButton.Yes:
                            return
        except GoogleQuotaExceededError:
            QMessageBox.warning(None, "Quota Exceeded",
                                "Google Sheets API quota exceeded while generating detailed report. Please wait and try again.")
            return
        except HttpError as e:
            QMessageBox.critical(None, "Google API Error",
                                 f"Google API error while generating detailed report:\n{e}")
            return
        except Exception as e:
            QMessageBox.critical(None, "Error", f"Error during pre-submission check: {e}")
            return

        # Show loading dialog and submit entry in background
        self.loading_dialog = LoadingDialog("Uploading entry, please wait...")
        self.loading_dialog.show()

        self.submit_thread = QThread()
        self.submit_worker = EntrySubmitter(
           self.model,
           date_val, load_no, driver_id, truck_id,
           from_state, to_state,
           transaction, delivery_status, payment_status,
           credit_amt, debit_amt, details, fraction_percent
        )
        self.submit_worker.moveToThread(self.submit_thread)
        self.submit_thread.started.connect(self.submit_worker.run)
        self.submit_worker.finished.connect(self._on_entry_submitted)
        self.submit_worker.finished.connect(self.submit_thread.quit)
        self.submit_worker.finished.connect(self.submit_worker.deleteLater)
        self.submit_thread.finished.connect(self.submit_thread.deleteLater)
        self.submit_thread.start()

    def _on_entry_submitted(self, error):
        self.loading_dialog.close()
        if error:
            if isinstance(error, GoogleQuotaExceededError):
                QMessageBox.warning(None, "Quota Exceeded",
                                    "Google Sheets API quota exceeded while adding entry. Please wait and try again.")
            elif isinstance(error, HttpError):
                QMessageBox.critical(None, "Google API Error",
                                     f"Google API error while adding entry:\n{error}")
            else:
                QMessageBox.critical(None, "Error", f"Failed to add entry: {error}")
            return
        QMessageBox.information(None, "Success", "Entry added successfully.")

        # ── Refresh the Load No. dropdown to include the new entry ──
        data_tab = self.main_window.data_entry_tab

        # Refresh Load Nos
        load_nos = self.model.get_all_load_nos()
        data_tab.load_no_combo.clear()
        data_tab.load_no_combo.addItems(load_nos)

        # Refresh Driver IDs
        driver_ids = self.model.get_all_driver_ids()
        data_tab.driver_id_combo.clear()
        data_tab.driver_id_combo.addItems(driver_ids)

        # Refresh Truck IDs
        truck_ids = self.model.get_all_truck_ids()
        data_tab.truck_id_combo.clear()
        data_tab.truck_id_combo.addItems(truck_ids)

        self.main_window.data_entry_tab.reset_form()

    def setup_reports_tab(self):
        reports_tab = self.main_window.reports_tab

        # DO NOT create a new loading dialog here.
        
        self.loadnos_thread = QThread()
        self.loadnos_worker = LoadNosFetcher(self.model)
        self.loadnos_worker.moveToThread(self.loadnos_thread)
        self.loadnos_thread.started.connect(self.loadnos_worker.run)
        self.loadnos_worker.finished.connect(self._on_load_nos_fetched)
        self.loadnos_worker.finished.connect(self.loadnos_thread.quit)
        self.loadnos_worker.finished.connect(self.loadnos_worker.deleteLater)
        self.loadnos_thread.finished.connect(self.loadnos_thread.deleteLater)
        self.loadnos_thread.start()

        # Populate transaction filter immediately (no async needed)
        # Add "Fraction" to the filter options as requested
        trans_opts = ["All"] + self.model.get_transaction_types() + ["Fraction"]
        reports_tab.transaction_filter_combo.clear()
        reports_tab.transaction_filter_combo.addItems(trans_opts)

        # Populate driver filter immediately (no async needed)
        driver_opts = ["All"] + self.model.get_all_driver_ids()
        reports_tab.driver_filter_combo.clear()
        reports_tab.driver_filter_combo.addItems(driver_opts)

        # Populate truck filter immediately (no async needed)
        truck_opts = ["All"] + self.model.get_all_truck_ids()
        reports_tab.truck_filter_combo.clear()
        reports_tab.truck_filter_combo.addItems(truck_opts)

        # Populate state filters with blank as default + all states
        state_opts = [""] + self.model.get_us_states()
        reports_tab.from_state_filter_combo.clear()
        reports_tab.from_state_filter_combo.addItems(state_opts)
        reports_tab.to_state_filter_combo.clear()
        reports_tab.to_state_filter_combo.addItems(state_opts)

        # Connect report buttons and reset button
        reports_tab.generate_button.clicked.connect(self.handle_generate_report)
        reports_tab.reset_button.clicked.connect(reports_tab.reset_filters)

        # Connect Delete Button
        reports_tab.delete_btn.clicked.connect(self.handle_delete_entry)


    def _on_load_nos_fetched(self, result):
        # This is now the last step in the loading process.
        reports_tab = self.main_window.reports_tab
        # ... (all your existing error handling and data population logic)
        
        # --- Your existing logic to populate the combo box ---
        error = None
        load_nos = []
        if isinstance(result, Exception):
            error = result
        else:
            load_nos = ["All"] + result
        if error:
            if isinstance(error, GoogleQuotaExceededError):
                QMessageBox.warning(None, "Quota Exceeded",
                                    "Google Sheets API quota exceeded while fetching Load Nos. for reports. Please wait and try again.")
            elif isinstance(error, HttpError):
                QMessageBox.critical(None, "Google API Error",
                                     f"Google API error while fetching Load Nos. for reports:\n{error}")
            else:
                QMessageBox.critical(None, "Error", f"Error while fetching Load Nos. for reports: {error}")
            load_nos = ["All"]
            
        reports_tab.load_no_filter_combo.clear()
        reports_tab.load_no_filter_combo.addItems(load_nos)
        # --- End of existing logic ---
        
        # FINALLY, close the single loading dialog and show the ready main window.
        self.loading_dialog.close()
        self.main_window.show()

    def handle_delete_entry(self):
        reports_tab = self.main_window.reports_tab
        selected_rows = reports_tab.detailed_table.selectionModel().selectedRows()
        
        if not selected_rows:
            return

        # We only support single row deletion for safety/simplicity initially, 
        # though logic can handle multiple.
        # Let's start with the first selected row.
        row_idx = selected_rows[0].row()
        
        # Retrieve metadata from the first column item
        item = reports_tab.detailed_table.item(row_idx, 0)
        user_data = item.data(Qt.ItemDataRole.UserRole)
        
        if not user_data:
            QMessageBox.warning(None, "Error", "Could not identify the selected entry. Please try refreshing the report.")
            return
            
        sheet_name = user_data['sheet_name']
        row_num = user_data['row_num']
        original_row = user_data['original_row']
        
        # Check if trying to delete a Fraction entry
        trans_idx = self.model.HEADER_IDX['transaction'] - 1
        ln_idx = self.model.HEADER_IDX['load_no'] - 1
        
        if len(original_row) > trans_idx and original_row[trans_idx] == 'Fraction':
            load_no = original_row[ln_idx] if len(original_row) > ln_idx else ''
            
            # Check if there are any credit entries for this load_no
            has_credit = False
            if load_no:
                # Get all rows for this load from model
                related_rows = self.model.generate_detailed_report(None, None, load_no=load_no)
                credit_col = self.model.HEADER_IDX['credit'] - 1
                trans_col = self.model.HEADER_IDX['transaction'] - 1
                
                for r in related_rows:
                    # Skip Fraction rows
                    current_trans = r[trans_col] if len(r) > trans_col else ''
                    if current_trans == 'Fraction':
                        continue
                        
                    # Check for credit amount
                    if len(r) > credit_col:
                        val_str = str(r[credit_col]).replace('$', '').replace(',', '').strip()
                        if val_str:
                            try:
                                if float(val_str) > 0:
                                    has_credit = True
                                    break
                            except ValueError:
                                pass

            if has_credit:
                QMessageBox.warning(None, "Action Denied", 
                    f"You cannot delete this 'Fraction' entry directly because Load No '{load_no}' has associated Income (Credit).\n\n"
                    "Please delete the corresponding Credit entry first, "
                    "and the Fraction entry will be updated or removed automatically."
                )
                return

        # Confirm Deletion
        confirm_msg = (
            f"Are you sure you want to delete this entry?\n\n"
            f"Sheet: {sheet_name}\n"
            f"Row: {row_num}\n\n"
            f"The entry will be moved to the 'Trash' sheet."
        )
        
        reply = QMessageBox.question(
            None, "Confirm Delete", confirm_msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Show loading dialog
            self.loading = LoadingDialog("Deleting entry...")
            self.loading.show()
            QApplication.processEvents()
            
            try:
                self.model.delete_entry(sheet_name, row_num, original_row)
                self.loading.accept()
                QMessageBox.information(None, "Success", "Entry deleted successfully.")
                
                # Refresh the report automatically
                self.handle_generate_report()
                
            except Exception as e:
                self.loading.accept()
                QMessageBox.critical(None, "Error", f"Failed to delete entry:\n{str(e)}")

    def handle_generate_report(self):
        """Generate both detailed and summary reports."""
        reports_tab = self.main_window.reports_tab
        from_date = reports_tab.from_date.date().toPyDate()
        to_date = reports_tab.to_date.date().toPyDate()
        load_no = reports_tab.load_no_filter_combo.currentText().strip()
        driver = reports_tab.driver_filter_combo.currentText()
        truck = reports_tab.truck_filter_combo.currentText()
        from_state = reports_tab.from_state_filter_combo.currentText().strip()
        to_state = reports_tab.to_state_filter_combo.currentText().strip()
        transaction = reports_tab.transaction_filter_combo.currentText()
        
        # Validate Load No if entered
        if load_no and load_no != "All":
            valid_load_nos = self.model.get_all_load_nos()
            if load_no not in valid_load_nos:
                QMessageBox.critical(None, "Error", f"Invalid Load No: '{load_no}'. Please select from the dropdown or enter a valid load number.")
                return
        else:
            load_no = None
        
        if driver == "All":
            driver = None
        if truck == "All":
            truck = None
        if transaction == "All":
            transaction = None
        
        # Extract abbreviations from state filters (e.g., "AL: Alabama" -> "AL")
        from_state = from_state.split(':')[0].strip() if from_state else None
        to_state = to_state.split(':')[0].strip() if to_state else None

        self.loading_dialog = LoadingDialog("Generating report, please wait...")
        self.loading_dialog.show()

        # Store filter parameters for later use
        self.current_filters = {
            'from_date': from_date,
            'to_date': to_date,
            'load_no': load_no,
            'transaction': transaction,
            'driver': driver,
            'truck': truck,
            'from_state': from_state,
            'to_state': to_state
        }

        self.detailed_thread = QThread()
        self.detailed_worker = DetailedReportGenerator(
            self.model, from_date, to_date, load_no, transaction, driver, truck, from_state, to_state
        )
        self.detailed_worker.moveToThread(self.detailed_thread)
        self.detailed_thread.started.connect(self.detailed_worker.run)
        self.detailed_worker.finished.connect(self._on_report_generated)
        self.detailed_worker.finished.connect(self.detailed_thread.quit)
        self.detailed_worker.finished.connect(self.detailed_worker.deleteLater)
        self.detailed_thread.finished.connect(self.detailed_thread.deleteLater)
        self.detailed_thread.start()

    def _on_report_generated(self, rows, error):
        self.loading_dialog.close()
        if error:
            if isinstance(error, GoogleQuotaExceededError):
                QMessageBox.warning(None, "Quota Exceeded",
                                    "Google Sheets API quota exceeded while generating report. Please wait and try again.")
            elif isinstance(error, HttpError):
                QMessageBox.critical(None, "Google API Error",
                                     f"Google API error while generating report:\n{error}")
            else:
                QMessageBox.critical(None, "Error", f"Error generating report: {error}")
            return
        
        # Sort rows: Ascending Load No, with "Other" or non-numeric at the bottom
        def sort_key(row):
            # Load No is at index 1 (based on HEADER_IDX in model.py)
            # HEADER_IDX = {'date': 1, 'load_no': 2, ...} -> index 1 in 0-indexed list
            try:
                load_val = row[1]
                if not load_val:
                    return (float('inf'), "")
                # Try to convert to int for numeric sorting
                return (int(load_val), "")
            except (ValueError, TypeError):
                # Non-numeric strings go to bottom
                return (float('inf'), str(row[1]))

        rows.sort(key=sort_key)

        # Store detailed rows for later PDF export
        self.current_detailed_rows = rows
        
        # Populate detailed table
        column_headers = self.model.get_header_indices()
        reports_tab = self.main_window.reports_tab
        reports_tab.populate_detailed_table(rows, column_headers)
        reports_tab.enable_csv_download(self.model.export_detailed_csv, rows)
        
        # Generate and display summary
        filters = self.current_filters
        summary = self.model.generate_summary_report(
            filters['from_date'], filters['to_date'], filters['load_no'], filters['transaction'],
            filters['driver'], filters['truck'], filters['from_state'], filters['to_state']
        )
        reports_tab.populate_summary(summary)
        reports_tab.enable_pdf_download(self.model.export_summary_pdf, summary, rows)

    def handle_generate_detailed_report(self):
        reports_tab = self.main_window.reports_tab
        from_date = reports_tab.from_date.date().toPyDate()
        to_date = reports_tab.to_date.date().toPyDate()
        load_no = reports_tab.load_no_filter_combo.currentText().strip()
        driver = reports_tab.driver_filter_combo.currentText()
        from_state = reports_tab.from_state_filter_combo.currentText().strip()
        to_state = reports_tab.to_state_filter_combo.currentText().strip()
        transaction = reports_tab.transaction_filter_combo.currentText()
        
        # Validate Load No if entered
        if load_no and load_no != "All":
            valid_load_nos = self.model.get_all_load_nos()
            if load_no not in valid_load_nos:
                QMessageBox.critical(None, "Error", f"Invalid Load No: '{load_no}'. Please select from the dropdown or enter a valid load number.")
                return
        else:
            load_no = None
        
        if driver == "All":
            driver = None
        if transaction == "All":
            transaction = None
        
        # Extract abbreviations from state filters (e.g., "AL: Alabama" -> "AL")
        from_state = from_state.split(':')[0].strip() if from_state else None
        to_state = to_state.split(':')[0].strip() if to_state else None

        self.loading_dialog = LoadingDialog("Generating detailed report, please wait...")
        self.loading_dialog.show()

        self.detailed_thread = QThread()
        self.detailed_worker = DetailedReportGenerator(
            self.model, from_date, to_date, load_no, transaction, driver, from_state, to_state
        )
        self.detailed_worker.moveToThread(self.detailed_thread)
        self.detailed_thread.started.connect(self.detailed_worker.run)
        self.detailed_worker.finished.connect(self._on_detailed_report_generated)
        self.detailed_worker.finished.connect(self.detailed_thread.quit)
        self.detailed_worker.finished.connect(self.detailed_worker.deleteLater)
        self.detailed_thread.finished.connect(self.detailed_thread.deleteLater)
        self.detailed_thread.start()

    def _on_detailed_report_generated(self, rows, error):
        self.loading_dialog.close()
        if error:
            if isinstance(error, GoogleQuotaExceededError):
                QMessageBox.warning(None, "Quota Exceeded",
                                    "Google Sheets API quota exceeded while generating detailed report. Please wait and try again.")
            elif isinstance(error, HttpError):
                QMessageBox.critical(None, "Google API Error",
                                     f"Google API error while generating detailed report:\n{error}")
            else:
                QMessageBox.critical(None, "Error", f"Error generating detailed report: {error}")
            return
        
        column_headers = self.model.get_header_indices()
        reports_tab = self.main_window.reports_tab
        reports_tab.populate_detailed_table(rows, column_headers)
        reports_tab.enable_csv_download(self.model.export_detailed_csv, rows)

    def handle_generate_summary_report(self):
        reports_tab = self.main_window.reports_tab
        from_date = reports_tab.from_date.date().toPyDate()
        to_date = reports_tab.to_date.date().toPyDate()
        load_no = reports_tab.load_no_filter_combo.currentText().strip()
        driver = reports_tab.driver_filter_combo.currentText()
        from_state = reports_tab.from_state_filter_combo.currentText().strip()
        to_state = reports_tab.to_state_filter_combo.currentText().strip()
        transaction = reports_tab.transaction_filter_combo.currentText()
        
        # Validate Load No if entered
        if load_no and load_no != "All":
            valid_load_nos = self.model.get_all_load_nos()
            if load_no not in valid_load_nos:
                QMessageBox.critical(None, "Error", f"Invalid Load No: '{load_no}'. Please select from the dropdown or enter a valid load number.")
                return
        else:
            load_no = None
        
        if driver == "All":
            driver = None
        if transaction == "All":
            transaction = None
        
        # Extract abbreviations from state filters (e.g., "AL: Alabama" -> "AL")
        from_state = from_state.split(':')[0].strip() if from_state else None
        to_state = to_state.split(':')[0].strip() if to_state else None

        self.loading_dialog = LoadingDialog("Generating summary report, please wait...")
        self.loading_dialog.show()

        self.summary_thread = QThread()
        self.summary_worker = SummaryReportGenerator(
            self.model, from_date, to_date, load_no, transaction, driver, from_state, to_state
        )
        self.summary_worker.moveToThread(self.summary_thread)
        self.summary_thread.started.connect(self.summary_worker.run)
        self.summary_worker.finished.connect(self._on_summary_report_generated)
        self.summary_worker.finished.connect(self.summary_thread.quit)
        self.summary_worker.finished.connect(self.summary_worker.deleteLater)
        self.summary_thread.finished.connect(self.summary_thread.deleteLater)
        self.summary_thread.start()

    def _on_summary_report_generated(self, summary, error):
        self.loading_dialog.close()
        if error:
            if isinstance(error, GoogleQuotaExceededError):
                QMessageBox.warning(None, "Quota Exceeded",
                                    "Google Sheets API quota exceeded while generating summary report. Please wait and try again.")
            elif isinstance(error, HttpError):
                QMessageBox.critical(None, "Google API Error",
                                     f"Google API error while generating summary report:\n{error}")
            else:
                QMessageBox.critical(None, "Error", f"Error generating summary report: {error}")
            return
        reports_tab = self.main_window.reports_tab
        reports_tab.populate_summary(summary)
        reports_tab.enable_pdf_download(self.model.export_summary_pdf, summary)


# Helper worker to fetch Load Nos asynchronously
class LoadNosFetcher(QObject):
    finished = pyqtSignal(object)  # list or Exception

    def __init__(self, model):
        super().__init__()
        self.model = model

    def run(self):
        try:
            load_nos = self.model.get_all_load_nos()
            self.finished.emit(load_nos)
        except Exception as e:
            self.finished.emit(e)


if __name__ == '__main__':
    model = MoneyMirrorModel()
    app = QApplication(sys.argv)
    controller = MoneyMirrorController(model)
    sys.exit(app.exec())
