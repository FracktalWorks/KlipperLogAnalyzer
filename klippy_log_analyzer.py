import sys
import re
import os
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
                             QWidget, QPushButton, QFileDialog, QCheckBox, QLabel,
                             QMessageBox, QGroupBox, QGridLayout, QSplitter)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont
import pyqtgraph as pg
import numpy as np


class LogParser(QThread):
    """Thread for parsing log file without blocking UI"""
    dataReady = pyqtSignal(dict)
    errorOccurred = pyqtSignal(str)

    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path

    def run(self):
        try:
            data = self.parse_klippy_log(self.file_path)
            self.dataReady.emit(data)
        except Exception as e:
            self.errorOccurred.emit(str(e))

    def parse_klippy_log(self, file_path):
        """Parse klippy.log file and extract performance metrics"""
        timestamps = []
        mcu_load = []
        bandwidth = []
        host_buffer = []
        awake_time = []

        with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
            for line in file:
                # Skip empty lines
                if not line.strip():
                    continue

                # Look for Stats lines
                if line.startswith('Stats '):
                    # Extract timestamp
                    timestamp_match = re.search(r'Stats (\d+\.\d+):', line)
                    if not timestamp_match:
                        continue

                    timestamp = float(timestamp_match.group(1))

                    # Extract MCU data (look for main mcu first, then any mcu)
                    mcu_data = self.extract_mcu_data(line)
                    if mcu_data:
                        timestamps.append(timestamp)
                        mcu_load.append(mcu_data['task_avg'] * 100000)  # Convert to percentage and scale
                        bandwidth.append(mcu_data['bandwidth'] / 1024)  # Convert to KB
                        awake_time.append(mcu_data['awake'] * 100)  # Convert to percentage

                    # Extract buffer time
                    buffer_match = re.search(r'buffer_time=(\d+\.\d+)', line)
                    if buffer_match:
                        buffer_time = float(buffer_match.group(1))
                        if len(host_buffer) < len(timestamps):
                            host_buffer.append(buffer_time)

        # Ensure all arrays have the same length
        min_length = min(len(timestamps), len(mcu_load), len(bandwidth), len(awake_time)) if timestamps else 0

        if min_length == 0:
            # Return empty arrays if no data found
            return {
                'timestamps': np.array([]),
                'mcu_load': np.array([]),
                'bandwidth': np.array([]),
                'host_buffer': np.array([]),
                'awake_time': np.array([])
            }

        # Pad host_buffer if needed
        while len(host_buffer) < min_length:
            host_buffer.append(0.0)

        return {
            'timestamps': np.array(timestamps[:min_length]),
            'mcu_load': np.array(mcu_load[:min_length]),
            'bandwidth': np.array(bandwidth[:min_length]),
            'host_buffer': np.array(host_buffer[:min_length]),
            'awake_time': np.array(awake_time[:min_length])
        }

    def extract_mcu_data(self, line):
        """Extract MCU data from a stats line, prioritizing main mcu"""
        # Look for main mcu first
        mcu_pattern = r'mcu: mcu_awake=(\d+\.\d+) mcu_task_avg=(\d+\.\d+) mcu_task_stddev=(\d+\.\d+) bytes_write=(\d+) bytes_read=(\d+)'
        mcu_match = re.search(mcu_pattern, line)

        if mcu_match:
            awake = float(mcu_match.group(1))
            task_avg = float(mcu_match.group(2))
            bytes_write = int(mcu_match.group(4))
            bytes_read = int(mcu_match.group(5))

            return {
                'awake': awake,
                'task_avg': task_avg,
                'bandwidth': bytes_write + bytes_read
            }

        # If no main mcu found, look for any mcu (toolhead0, toolhead1, etc.)
        toolhead_pattern = r'(\w+): mcu_awake=(\d+\.\d+) mcu_task_avg=(\d+\.\d+) mcu_task_stddev=(\d+\.\d+) bytes_write=(\d+) bytes_read=(\d+)'
        toolhead_matches = re.findall(toolhead_pattern, line)

        if toolhead_matches:
            # Use the first toolhead found
            match = toolhead_matches[0]
            awake = float(match[1])
            task_avg = float(match[2])
            bytes_write = int(match[4])
            bytes_read = int(match[5])

            return {
                'awake': awake,
                'task_avg': task_avg,
                'bandwidth': bytes_write + bytes_read
            }

        return None


class KlippyLogAnalyzer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.data = None
        self.plots = {}
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle('Klippy Log Performance Analyzer')
        self.setGeometry(100, 100, 1200, 800)

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QVBoxLayout(central_widget)

        # File selection section
        file_section = self.create_file_section()
        main_layout.addWidget(file_section)

        # Splitter for controls and graph
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)

        # Controls panel
        controls_panel = self.create_controls_panel()
        splitter.addWidget(controls_panel)

        # Graph widget
        self.graph_widget = self.create_graph_widget()
        splitter.addWidget(self.graph_widget)

        # Set splitter proportions
        splitter.setSizes([200, 1000])

    def create_file_section(self):
        """Create file selection section"""
        group = QGroupBox("Log File Selection")
        layout = QHBoxLayout(group)

        self.file_label = QLabel("No file selected")
        self.file_label.setStyleSheet("QLabel { color: gray; }")

        self.browse_button = QPushButton("Browse klippy.log")
        self.browse_button.clicked.connect(self.browse_file)

        layout.addWidget(self.file_label)
        layout.addStretch()
        layout.addWidget(self.browse_button)

        return group

    def create_controls_panel(self):
        """Create controls panel with checkboxes"""
        group = QGroupBox("Performance Metrics")
        layout = QVBoxLayout(group)

        # Checkboxes for different metrics
        self.mcu_load_cb = QCheckBox("MCU Load")
        self.mcu_load_cb.setStyleSheet("QCheckBox { color: #D32F2F; font-weight: bold; }")
        self.mcu_load_cb.setChecked(True)
        self.mcu_load_cb.stateChanged.connect(self.update_plot)

        self.bandwidth_cb = QCheckBox("Bandwidth")
        self.bandwidth_cb.setStyleSheet("QCheckBox { color: #FF9800; font-weight: bold; }")
        self.bandwidth_cb.setChecked(True)
        self.bandwidth_cb.stateChanged.connect(self.update_plot)

        self.host_buffer_cb = QCheckBox("Host Buffer")
        self.host_buffer_cb.setStyleSheet("QCheckBox { color: #4CAF50; font-weight: bold; }")
        self.host_buffer_cb.setChecked(True)
        self.host_buffer_cb.stateChanged.connect(self.update_plot)

        self.awake_time_cb = QCheckBox("Awake Time")
        self.awake_time_cb.setStyleSheet("QCheckBox { color: #2196F3; font-weight: bold; }")
        self.awake_time_cb.setChecked(True)
        self.awake_time_cb.stateChanged.connect(self.update_plot)

        layout.addWidget(self.mcu_load_cb)
        layout.addWidget(self.bandwidth_cb)
        layout.addWidget(self.host_buffer_cb)
        layout.addWidget(self.awake_time_cb)
        layout.addStretch()

        # Initially disable checkboxes
        self.set_controls_enabled(False)

        return group

    def create_graph_widget(self):
        """Create the main graph widget"""
        # Create plot widget
        plot_widget = pg.PlotWidget()
        plot_widget.setBackground('white')
        plot_widget.setLabel('left', 'Value')
        plot_widget.setLabel('bottom', 'Time')
        plot_widget.setTitle('Klippy Performance Graph')
        plot_widget.showGrid(x=True, y=True, alpha=0.3)

        # Add legend
        plot_widget.addLegend()

        # Configure time axis
        axis = plot_widget.getAxis('bottom')
        axis.setStyle(tickTextOffset=10)

        return plot_widget

    def set_controls_enabled(self, enabled):
        """Enable/disable control checkboxes"""
        self.mcu_load_cb.setEnabled(enabled)
        self.bandwidth_cb.setEnabled(enabled)
        self.host_buffer_cb.setEnabled(enabled)
        self.awake_time_cb.setEnabled(enabled)

    def browse_file(self):
        """Open file browser to select klippy.log file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select klippy.log file",
            "",
            "Log files (*.log);;All files (*.*)"
        )

        if file_path:
            self.load_log_file(file_path)

    def load_log_file(self, file_path):
        """Load and parse the selected log file"""
        self.file_label.setText(f"Loading: {os.path.basename(file_path)}")
        self.file_label.setStyleSheet("QLabel { color: blue; }")
        self.browse_button.setEnabled(False)
        self.set_controls_enabled(False)

        # Create and start parser thread
        self.parser_thread = LogParser(file_path)
        self.parser_thread.dataReady.connect(self.on_data_ready)
        self.parser_thread.errorOccurred.connect(self.on_error)
        self.parser_thread.start()

    def on_data_ready(self, data):
        """Handle parsed data"""
        self.data = data
        self.file_label.setText(f"Loaded: {len(data['timestamps'])} data points")
        self.file_label.setStyleSheet("QLabel { color: green; }")
        self.browse_button.setEnabled(True)
        self.set_controls_enabled(True)
        self.update_plot()

    def on_error(self, error_msg):
        """Handle parsing error"""
        self.file_label.setText("Error loading file")
        self.file_label.setStyleSheet("QLabel { color: red; }")
        self.browse_button.setEnabled(True)
        QMessageBox.critical(self, "Error", f"Failed to parse log file:\n{error_msg}")

    def update_plot(self):
        """Update the plot based on selected checkboxes"""
        if self.data is None:
            return

        # Clear existing plots
        self.graph_widget.clear()
        self.plots = {}

        timestamps = self.data['timestamps']
        if len(timestamps) == 0:
            return

        # Convert timestamps to time format (MM:SS)
        start_time = timestamps[0]
        time_minutes = (timestamps - start_time) / 60.0  # Convert to minutes

        # Create custom time axis labels
        self.setup_time_axis(time_minutes)

        # Plot MCU Load
        if self.mcu_load_cb.isChecked():
            pen = pg.mkPen(color='#D32F2F', width=2)
            self.plots['mcu_load'] = self.graph_widget.plot(
                time_minutes, self.data['mcu_load'],
                pen=pen, name='MCU Load'
            )

        # Plot Bandwidth
        if self.bandwidth_cb.isChecked():
            pen = pg.mkPen(color='#FF9800', width=2)
            self.plots['bandwidth'] = self.graph_widget.plot(
                time_minutes, self.data['bandwidth'],
                pen=pen, name='Bandwidth'
            )

        # Plot Host Buffer
        if self.host_buffer_cb.isChecked():
            pen = pg.mkPen(color='#4CAF50', width=2)
            self.plots['host_buffer'] = self.graph_widget.plot(
                time_minutes, self.data['host_buffer'],
                pen=pen, name='Host Buffer'
            )

        # Plot Awake Time
        if self.awake_time_cb.isChecked():
            pen = pg.mkPen(color='#2196F3', width=2)
            self.plots['awake_time'] = self.graph_widget.plot(
                time_minutes, self.data['awake_time'],
                pen=pen, name='Awake Time'
            )

        # Auto-range the plot
        self.graph_widget.autoRange()

    def setup_time_axis(self, time_minutes):
        """Setup time axis with MM:SS format"""
        axis = self.graph_widget.getAxis('bottom')

        # Create custom tick spacing based on data duration
        max_minutes = time_minutes[-1] if len(time_minutes) > 0 else 30

        if max_minutes <= 5:
            # For short logs, show every 30 seconds
            tick_spacing = 0.5  # 30 seconds
        elif max_minutes <= 30:
            # For medium logs, show every 5 minutes
            tick_spacing = 5
        else:
            # For long logs, show every 10 minutes
            tick_spacing = 10

        # Generate tick positions and labels
        tick_positions = []
        tick_labels = []

        current_tick = 0
        while current_tick <= max_minutes:
            tick_positions.append(current_tick)

            # Format as MM:SS
            minutes = int(current_tick)
            seconds = int((current_tick - minutes) * 60)
            if minutes >= 60:
                hours = minutes // 60
                minutes = minutes % 60
                tick_labels.append(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
            else:
                tick_labels.append(f"{minutes:02d}:{seconds:02d}")

            current_tick += tick_spacing

        # Set custom ticks
        ticks = [list(zip(tick_positions, tick_labels))]
        axis.setTicks(ticks)


def main():
    app = QApplication(sys.argv)

    # Set application style
    app.setStyle('Fusion')

    # Create and show main window
    analyzer = KlippyLogAnalyzer()
    analyzer.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()