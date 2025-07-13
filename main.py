import sys
import pandas as pd
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton, QLabel, QFileDialog,
    QComboBox, QSpinBox, QHBoxLayout, QMessageBox, QLineEdit,
    QTableWidget, QTableWidgetItem, QRadioButton, QButtonGroup,
    QGroupBox, QHeaderView
)
from PySide6.QtCore import Qt
from logic import (
    hex_to_32bit_bin, detect_bit_length, slice_bits_custom,
    parse_bit_assignments, generate_column_names, is_likely_binary
)

class HexSlicerApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Advanced Hex/Binary Column Slicer")
        self.resize(600, 500)
        self.df = None
        self.selected_column = None
        self.result_df = None
        self.binary_columns = set()  # Track columns that are known binary

        layout = QVBoxLayout()

        self.load_btn = QPushButton("Load Excel File")
        self.load_btn.clicked.connect(self.load_file)
        self.file_label = QLabel("No file loaded.")
        layout.addWidget(self.load_btn)
        layout.addWidget(self.file_label)

        self.column_dropdown = QComboBox()
        self.column_dropdown.setEnabled(False)
        self.column_dropdown.currentTextChanged.connect(self.on_column_changed)
        layout.addWidget(QLabel("Select Column:"))
        layout.addWidget(self.column_dropdown)

        self.bit_length_label = QLabel("Detected bit length: -")
        layout.addWidget(self.bit_length_label)

        mode_group = QGroupBox("Slicing Mode")
        mode_layout = QVBoxLayout()

        self.uniform_radio = QRadioButton("Uniform slicing")
        self.custom_radio = QRadioButton("Custom bit assignments")
        self.uniform_radio.setChecked(True)

        self.mode_group = QButtonGroup()
        self.mode_group.addButton(self.uniform_radio)
        self.mode_group.addButton(self.custom_radio)
        self.mode_group.buttonClicked.connect(self.on_mode_changed)

        mode_layout.addWidget(self.uniform_radio)
        mode_layout.addWidget(self.custom_radio)
        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)

        self.uniform_container = QWidget()
        uniform_layout = QHBoxLayout()
        uniform_layout.setContentsMargins(0, 0, 0, 0)
        uniform_layout.addWidget(QLabel("Slice Size (bits):"))
        self.slice_spin = QSpinBox()
        self.slice_spin.setRange(1, 32)
        self.slice_spin.setValue(4)
        uniform_layout.addWidget(self.slice_spin)
        uniform_layout.addStretch()
        self.uniform_container.setLayout(uniform_layout)
        layout.addWidget(self.uniform_container)

        self.custom_container = QWidget()
        custom_layout = QVBoxLayout()
        custom_layout.setContentsMargins(0, 0, 0, 0)
        custom_layout.addWidget(QLabel("Bit assignments (comma-separated):"))
        self.bit_assignments_input = QLineEdit()
        self.bit_assignments_input.setPlaceholderText("e.g., 12,12,8 or 1,1,1,1,1,1,1,1,1,1,2")
        custom_layout.addWidget(self.bit_assignments_input)
        self.custom_container.setLayout(custom_layout)
        self.custom_container.setVisible(False)
        layout.addWidget(self.custom_container)

        self.preview_btn = QPushButton("Preview Column Names")
        self.preview_btn.setEnabled(False)
        self.preview_btn.clicked.connect(self.preview_columns)
        layout.addWidget(self.preview_btn)

        layout.addWidget(QLabel("Column Names (editable):"))
        self.names_table = QTableWidget()
        self.names_table.setColumnCount(2)
        self.names_table.setHorizontalHeaderLabels(["Bits", "Column Name"])
        self.names_table.horizontalHeader().setStretchLastSection(True)
        self.names_table.setMaximumHeight(200)
        layout.addWidget(self.names_table)

        btn_row = QHBoxLayout()
        self.process_btn = QPushButton("Process")
        self.process_btn.setEnabled(False)
        self.process_btn.clicked.connect(self.process_column)
        btn_row.addWidget(self.process_btn)

        self.save_btn = QPushButton("Save Output")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self.save_output)
        btn_row.addWidget(self.save_btn)

        layout.addLayout(btn_row)
        self.setLayout(layout)

    def load_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open Excel File", "", "Excel Files (*.xlsx *.xls)")
        if not file_path:
            return

        try:
            df = pd.read_excel(file_path, engine="openpyxl", header=0, dtype=str)
            if not all(isinstance(c, str) for c in df.columns):
                raise Exception("Header contains non-strings")
        except:
            df = pd.read_excel(file_path, engine="openpyxl", header=None, dtype=str)
            df.columns = [f"Column_{i}" for i in range(len(df.columns))]

        self.df = df
        self.binary_columns = {col for col in df.columns if "_b" in col and "_bit" in col}
        self.file_label.setText(file_path.split("/")[-1])
        self.column_dropdown.clear()
        self.column_dropdown.addItems(df.columns)
        self.column_dropdown.setEnabled(True)
        self.preview_btn.setEnabled(True)

    def on_column_changed(self):
        if self.df is None or not self.column_dropdown.currentText():
            return

        col_name = self.column_dropdown.currentText()
        bit_length = 32  # Default
        
        for val in self.df[col_name]:
            if pd.notna(val):
                val_str = str(val).strip()
                if col_name in self.binary_columns:
                    # Column name indicates it's binary - trust the stored length
                    bit_length = len(val_str)
                elif is_likely_binary(val_str):
                    # String looks like binary
                    bit_length = len(val_str)
                else:
                    # It's hex - always 32 bits
                    bit_length = 32
                break

        self.bit_length_label.setText(f"Detected bit length: {bit_length}")
        self.slice_spin.setMaximum(max(bit_length - 1, 1))

    def on_mode_changed(self):
        is_custom = self.custom_radio.isChecked()
        self.uniform_container.setVisible(not is_custom)
        self.custom_container.setVisible(is_custom)

    def get_bit_assignments(self):
        if self.uniform_radio.isChecked():
            slice_size = self.slice_spin.value()
            bit_length = self.get_current_bit_length()
            assignments = []
            for i in range(0, bit_length, slice_size):
                remaining = bit_length - i
                assignments.append(min(slice_size, remaining))
            return assignments
        else:
            try:
                return parse_bit_assignments(self.bit_assignments_input.text())
            except ValueError as e:
                QMessageBox.warning(self, "Invalid Input", str(e))
                return None

    def get_current_bit_length(self):
        if self.df is None or not self.column_dropdown.currentText():
            return 32
            
        col_name = self.column_dropdown.currentText()
        for val in self.df[col_name]:
            if pd.notna(val):
                val_str = str(val).strip()
                if col_name in self.binary_columns:
                    return len(val_str)
                elif is_likely_binary(val_str):
                    return len(val_str)
                else:
                    # Hex is always 32-bit
                    return 32
        return 32

    def preview_columns(self):
        bit_assignments = self.get_bit_assignments()
        if not bit_assignments:
            return

        total_bits = sum(bit_assignments)
        expected_bits = self.get_current_bit_length()

        if total_bits != expected_bits:
            QMessageBox.warning(self, "Bit Count Mismatch", f"Total bits ({total_bits}) does not match column bit length ({expected_bits})")
            return

        col_name = self.column_dropdown.currentText()
        default_names = generate_column_names(col_name, bit_assignments)

        self.names_table.setRowCount(len(bit_assignments))
        for i, (bits, name) in enumerate(zip(bit_assignments, default_names)):
            bits_item = QTableWidgetItem(str(bits))
            bits_item.setFlags(bits_item.flags() & ~Qt.ItemIsEditable)
            self.names_table.setItem(i, 0, bits_item)
            name_item = QTableWidgetItem(name)
            self.names_table.setItem(i, 1, name_item)

        self.process_btn.setEnabled(True)

    def get_column_names_from_table(self):
        names = []
        for i in range(self.names_table.rowCount()):
            name_item = self.names_table.item(i, 1)
            if name_item:
                names.append(name_item.text())
        return names

    def process_column(self):
        if self.df is None:
            return

        self.selected_column = self.column_dropdown.currentText()
        self.df[self.selected_column] = self.df[self.selected_column].astype(str)

        bit_assignments = self.get_bit_assignments()
        if not bit_assignments:
            return

        total_bits = sum(bit_assignments)
        expected_bits = self.get_current_bit_length()

        if total_bits != expected_bits:
            QMessageBox.warning(self, "Bit Count Mismatch", f"Total bits ({total_bits}) does not match column bit length ({expected_bits})")
            return

        column_names = self.get_column_names_from_table()
        if len(column_names) != len(bit_assignments):
            QMessageBox.warning(self, "Error", "Column names count mismatch")
            return

        new_rows = []
        debug_first = True
        
        for val in self.df[self.selected_column]:
            if pd.notna(val):
                val_str = str(val).strip()
                
                if self.selected_column in self.binary_columns:
                    # Already binary from a previous slice
                    bin_str = val_str.zfill(expected_bits)
                elif is_likely_binary(val_str):
                    # Binary string
                    bin_str = val_str.zfill(expected_bits)
                else:
                    # Hex value - use the standard conversion
                    bin_str = hex_to_32bit_bin(val_str)
                
                if debug_first:
                    print(f"Debug - Processing value: '{val_str}'")
                    print(f"  Column: {self.selected_column}")
                    print(f"  Is binary column: {self.selected_column in self.binary_columns}")
                    print(f"  is_likely_binary: {is_likely_binary(val_str)}")
                    print(f"  Binary result: '{bin_str}'")
                    print(f"  Binary length: {len(bin_str)}")
                    debug_first = False
                
                sliced = slice_bits_custom(bin_str, bit_assignments)
                new_rows.append(sliced)
            else:
                new_rows.append([''] * len(bit_assignments))

        self.result_df = pd.DataFrame(new_rows, columns=column_names, dtype=object)
        self.binary_columns.update(column_names)
        
        QMessageBox.information(self, "Done", f"Processed {len(self.result_df)} rows into {len(column_names)} columns.")
        self.save_btn.setEnabled(True)

    def save_output(self):
        save_path, _ = QFileDialog.getSaveFileName(self, "Save File", "", "Excel (*.xlsx)")
        if save_path:
            try:
                string_df = self.result_df.copy()
                for col in string_df.columns:
                    string_df[col] = string_df[col].astype(str)

                with pd.ExcelWriter(save_path, engine='openpyxl') as writer:
                    string_df.to_excel(writer, index=False, sheet_name='Sheet1')
                    workbook = writer.book
                    worksheet = writer.sheets['Sheet1']
                    for row in range(2, len(string_df) + 2):
                        for col in range(1, len(string_df.columns) + 1):
                            cell = worksheet.cell(row=row, column=col)
                            cell.number_format = '@'

                csv_path = save_path.replace('.xlsx', '.csv')
                string_df.to_csv(csv_path, index=False)
                QMessageBox.information(self, "Saved", f"Files saved:\n{save_path}\n{csv_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = HexSlicerApp()
    win.show()
    sys.exit(app.exec())