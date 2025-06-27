import sys
import re
import os
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
                             QWidget, QPushButton, QFileDialog, QCheckBox, QLabel,
                             QMessageBox, QGroupBox, QGridLayout, QSplitter,
                             QComboBox, QScrollArea)
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
        """Parse klippy.log file and extract all available performance metrics"""
        timestamps = []
        metrics_data = {}

        # Initialize all possible metrics
        all_metrics = [
            'mcu_load', 'bandwidth', 'host_buffer', 'awake_time',
            'mcu_bytes_write', 'mcu_bytes_read', 'mcu_bytes_retransmit',
            'mcu_send_seq', 'mcu_receive_seq', 'mcu_srtt', 'mcu_rttvar', 'mcu_rto',
            'toolhead0_load', 'toolhead0_bandwidth', 'toolhead0_awake',
            'toolhead0_bytes_write', 'toolhead0_bytes_read', 'toolhead0_freq',
            'toolhead1_load', 'toolhead1_bandwidth', 'toolhead1_awake',
            'toolhead1_bytes_write', 'toolhead1_bytes_read', 'toolhead1_freq',
            'heater_bed_target', 'heater_bed_temp', 'heater_bed_pwm',
            'extruder_target', 'extruder_temp', 'extruder_pwm',
            'extruder1_target', 'extruder1_temp', 'extruder1_pwm',
            'sysload', 'cputime', 'memavail', 'print_time', 'print_stall'
        ]

        for metric in all_metrics:
            metrics_data[metric] = []

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
                    timestamps.append(timestamp)

                    # Extract all metrics from the line
                    self.extract_all_metrics(line, metrics_data)

        # Convert to numpy arrays and ensure all have same length
        result = {'timestamps': np.array(timestamps)}

        if len(timestamps) > 0:
            for metric in all_metrics:
                # Pad shorter arrays to match timestamp length
                while len(metrics_data[metric]) < len(timestamps):
                    metrics_data[metric].append(0.0)
                # Truncate longer arrays
                metrics_data[metric] = metrics_data[metric][:len(timestamps)]
                result[metric] = np.array(metrics_data[metric])
        else:
            for metric in all_metrics:
                result[metric] = np.array([])

        return result

    def extract_all_metrics(self, line, metrics_data):
        """Extract all available metrics from a stats line"""

        # MCU main metrics
        mcu_pattern = r'mcu: mcu_awake=(\d+\.\d+) mcu_task_avg=(\d+\.\d+) mcu_task_stddev=(\d+\.\d+) bytes_write=(\d+) bytes_read=(\d+) bytes_retransmit=(\d+).*?send_seq=(\d+) receive_seq=(\d+).*?srtt=(\d+\.\d+) rttvar=(\d+\.\d+) rto=(\d+\.\d+)'
        mcu_match = re.search(mcu_pattern, line)

        if mcu_match:
            awake = float(mcu_match.group(1))
            task_avg = float(mcu_match.group(2))
            bytes_write = int(mcu_match.group(4))
            bytes_read = int(mcu_match.group(5))
            bytes_retransmit = int(mcu_match.group(6))
            send_seq = int(mcu_match.group(7))
            receive_seq = int(mcu_match.group(8))
            srtt = float(mcu_match.group(9))
            rttvar = float(mcu_match.group(10))
            rto = float(mcu_match.group(11))

            metrics_data['mcu_load'].append(task_avg * 100000)  # Convert to percentage and scale
            metrics_data['bandwidth'].append((bytes_write + bytes_read) / 1024)  # Convert to KB
            metrics_data['awake_time'].append(awake * 100)  # Convert to percentage
            metrics_data['mcu_bytes_write'].append(bytes_write)
            metrics_data['mcu_bytes_read'].append(bytes_read)
            metrics_data['mcu_bytes_retransmit'].append(bytes_retransmit)
            metrics_data['mcu_send_seq'].append(send_seq)
            metrics_data['mcu_receive_seq'].append(receive_seq)
            metrics_data['mcu_srtt'].append(srtt * 1000)  # Convert to ms
            metrics_data['mcu_rttvar'].append(rttvar * 1000)  # Convert to ms
            metrics_data['mcu_rto'].append(rto * 1000)  # Convert to ms
        else:
            # Add zeros if no MCU data found
            for metric in ['mcu_load', 'bandwidth', 'awake_time', 'mcu_bytes_write',
                           'mcu_bytes_read', 'mcu_bytes_retransmit', 'mcu_send_seq',
                           'mcu_receive_seq', 'mcu_srtt', 'mcu_rttvar', 'mcu_rto']:
                metrics_data[metric].append(0.0)

        # Toolhead metrics
        for toolhead_num in [0, 1]:
            toolhead_pattern = f'toolhead{toolhead_num}: mcu_awake=(\d+\.\d+) mcu_task_avg=(\d+\.\d+).*?bytes_write=(\d+) bytes_read=(\d+).*?freq=(\d+)'
            toolhead_match = re.search(toolhead_pattern, line)

            if toolhead_match:
                awake = float(toolhead_match.group(1))
                task_avg = float(toolhead_match.group(2))
                bytes_write = int(toolhead_match.group(3))
                bytes_read = int(toolhead_match.group(4))
                freq = int(toolhead_match.group(5))

                metrics_data[f'toolhead{toolhead_num}_load'].append(task_avg * 100000)
                metrics_data[f'toolhead{toolhead_num}_bandwidth'].append((bytes_write + bytes_read) / 1024)
                metrics_data[f'toolhead{toolhead_num}_awake'].append(awake * 100)
                metrics_data[f'toolhead{toolhead_num}_bytes_write'].append(bytes_write)
                metrics_data[f'toolhead{toolhead_num}_bytes_read'].append(bytes_read)
                metrics_data[f'toolhead{toolhead_num}_freq'].append(freq / 1000000)  # Convert to MHz
            else:
                for metric in [f'toolhead{toolhead_num}_load', f'toolhead{toolhead_num}_bandwidth',
                               f'toolhead{toolhead_num}_awake', f'toolhead{toolhead_num}_bytes_write',
                               f'toolhead{toolhead_num}_bytes_read', f'toolhead{toolhead_num}_freq']:
                    metrics_data[metric].append(0.0)

        # Heater bed metrics
        heater_bed_pattern = r'heater_bed: target=(\d+(?:\.\d+)?) temp=(\d+\.\d+) pwm=(\d+\.\d+)'
        heater_bed_match = re.search(heater_bed_pattern, line)
        if heater_bed_match:
            metrics_data['heater_bed_target'].append(float(heater_bed_match.group(1)))
            metrics_data['heater_bed_temp'].append(float(heater_bed_match.group(2)))
            metrics_data['heater_bed_pwm'].append(float(heater_bed_match.group(3)) * 100)  # Convert to percentage
        else:
            for metric in ['heater_bed_target', 'heater_bed_temp', 'heater_bed_pwm']:
                metrics_data[metric].append(0.0)

        # Extruder metrics
        for extruder_name in ['extruder', 'extruder1']:
            extruder_pattern = f'{extruder_name}: target=(\d+(?:\.\d+)?) temp=(\d+\.\d+) pwm=(\d+\.\d+)'
            extruder_match = re.search(extruder_pattern, line)

            if extruder_match:
                metrics_data[f'{extruder_name}_target'].append(float(extruder_match.group(1)))
                metrics_data[f'{extruder_name}_temp'].append(float(extruder_match.group(2)))
                metrics_data[f'{extruder_name}_pwm'].append(float(extruder_match.group(3)) * 100)
            else:
                for suffix in ['_target', '_temp', '_pwm']:
                    metrics_data[f'{extruder_name}{suffix}'].append(0.0)

        # System metrics
        system_metrics = {
            'sysload': r'sysload=(\d+\.\d+)',
            'cputime': r'cputime=(\d+\.\d+)',
            'memavail': r'memavail=(\d+)',
            'print_time': r'print_time=(\d+\.\d+)',
            'print_stall': r'print_stall=(\d+)'
        }

        for metric, pattern in system_metrics.items():
            match = re.search(pattern, line)
            if match:
                value = float(match.group(1))
                if metric == 'memavail':
                    value = value / 1024  # Convert to MB
                metrics_data[metric].append(value)
            else:
                metrics_data[metric].append(0.0)

        # Extract buffer time
        buffer_match = re.search(r'buffer_time=(\d+\.\d+)', line)
        if buffer_match:
            metrics_data['host_buffer'].append(float(buffer_match.group(1)))
        else:
            metrics_data['host_buffer'].append(0.0)


class KlippyLogAnalyzer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.data = None
        self.plots = {}
        self.metric_checkboxes = {}
        self.available_metrics = []
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle('Klippy Log Performance Analyzer')
        self.setGeometry(100, 100, 1400, 900)

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
        splitter.setSizes([300, 1100])

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
        """Create controls panel with metric selection"""
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)

        # Metric selection dropdown section
        selection_group = QGroupBox("Metric Selection")
        selection_layout = QVBoxLayout(selection_group)

        # Dropdown for adding metrics
        dropdown_layout = QHBoxLayout()
        dropdown_layout.addWidget(QLabel("Add Metric:"))

        self.metric_dropdown = QComboBox()
        self.metric_dropdown.currentTextChanged.connect(self.on_metric_selected)
        dropdown_layout.addWidget(self.metric_dropdown)

        selection_layout.addLayout(dropdown_layout)

        # Info label
        self.info_label = QLabel("Select up to 4 metrics to display")
        self.info_label.setStyleSheet("QLabel { color: #666; font-style: italic; }")
        selection_layout.addWidget(self.info_label)

        main_layout.addWidget(selection_group)

        # Active metrics section with scroll area
        active_group = QGroupBox("Active Metrics (Max 4)")
        active_layout = QVBoxLayout(active_group)

        # Create scroll area for checkboxes
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setMaximumHeight(200)

        self.checkbox_widget = QWidget()
        self.checkbox_layout = QVBoxLayout(self.checkbox_widget)
        scroll_area.setWidget(self.checkbox_widget)

        active_layout.addWidget(scroll_area)
        main_layout.addWidget(active_group)

        # Initialize with default metrics
        self.setup_default_metrics()

        main_layout.addStretch()

        # Initially disable controls
        self.set_controls_enabled(False)

        return main_widget

    def setup_default_metrics(self):
        """Setup default metrics (the original 4)"""
        default_metrics = [
            ('mcu_load', 'MCU Load', '#D32F2F'),
            ('bandwidth', 'Bandwidth', '#FF9800'),
            ('host_buffer', 'Host Buffer', '#4CAF50'),
            ('awake_time', 'Awake Time', '#2196F3')
        ]

        for metric_key, display_name, color in default_metrics:
            self.add_metric_checkbox(metric_key, display_name, color, checked=True)

    def get_all_available_metrics(self):
        """Get all available metrics with their display names and colors"""
        return [
            # Original 4 (default)
            ('mcu_load', 'MCU Load', '#D32F2F'),
            ('bandwidth', 'Bandwidth (KB)', '#FF9800'),
            ('host_buffer', 'Host Buffer', '#4CAF50'),
            ('awake_time', 'Awake Time', '#2196F3'),

            # MCU extended metrics
            ('mcu_bytes_write', 'MCU Bytes Write', '#8E24AA'),
            ('mcu_bytes_read', 'MCU Bytes Read', '#00ACC1'),
            ('mcu_bytes_retransmit', 'MCU Bytes Retransmit', '#D84315'),
            ('mcu_send_seq', 'MCU Send Sequence', '#388E3C'),
            ('mcu_receive_seq', 'MCU Receive Sequence', '#1976D2'),
            ('mcu_srtt', 'MCU SRTT (ms)', '#7B1FA2'),
            ('mcu_rttvar', 'MCU RTT Variance (ms)', '#0288D1'),
            ('mcu_rto', 'MCU RTO (ms)', '#5D4037'),

            # Toolhead metrics
            ('toolhead0_load', 'Toolhead0 Load', '#E91E63'),
            ('toolhead0_bandwidth', 'Toolhead0 Bandwidth (KB)', '#9C27B0'),
            ('toolhead0_awake', 'Toolhead0 Awake', '#673AB7'),
            ('toolhead0_bytes_write', 'Toolhead0 Bytes Write', '#3F51B5'),
            ('toolhead0_bytes_read', 'Toolhead0 Bytes Read', '#2196F3'),
            ('toolhead0_freq', 'Toolhead0 Frequency (MHz)', '#03A9F4'),

            ('toolhead1_load', 'Toolhead1 Load', '#00BCD4'),
            ('toolhead1_bandwidth', 'Toolhead1 Bandwidth (KB)', '#009688'),
            ('toolhead1_awake', 'Toolhead1 Awake', '#4CAF50'),
            ('toolhead1_bytes_write', 'Toolhead1 Bytes Write', '#8BC34A'),
            ('toolhead1_bytes_read', 'Toolhead1 Bytes Read', '#CDDC39'),
            ('toolhead1_freq', 'Toolhead1 Frequency (MHz)', '#FFC107'),

            # Temperature metrics
            ('heater_bed_target', 'Bed Target Temp', '#FF9800'),
            ('heater_bed_temp', 'Bed Temperature', '#FF5722'),
            ('heater_bed_pwm', 'Bed PWM %', '#795548'),
            ('extruder_target', 'Extruder Target Temp', '#9E9E9E'),
            ('extruder_temp', 'Extruder Temperature', '#607D8B'),
            ('extruder_pwm', 'Extruder PWM %', '#F44336'),
            ('extruder1_target', 'Extruder1 Target Temp', '#E91E63'),
            ('extruder1_temp', 'Extruder1 Temperature', '#9C27B0'),
            ('extruder1_pwm', 'Extruder1 PWM %', '#673AB7'),

            # System metrics
            ('sysload', 'System Load', '#3F51B5'),
            ('cputime', 'CPU Time', '#2196F3'),
            ('memavail', 'Memory Available (MB)', '#03A9F4'),
            ('print_time', 'Print Time', '#00BCD4'),
            ('print_stall', 'Print Stall', '#009688')
        ]

    def add_metric_checkbox(self, metric_key, display_name, color, checked=False):
        """Add a new metric checkbox"""
        if len(self.metric_checkboxes) >= 4:
            return False

        checkbox = QCheckBox(display_name)
        checkbox.setStyleSheet(f"QCheckBox {{ color: {color}; font-weight: bold; }}")
        checkbox.setChecked(checked)
        checkbox.stateChanged.connect(self.update_plot)

        # Add remove button
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(checkbox)

        remove_btn = QPushButton("×")
        remove_btn.setMaximumWidth(30)
        remove_btn.setStyleSheet("QPushButton { color: red; font-weight: bold; }")
        remove_btn.clicked.connect(lambda: self.remove_metric_checkbox(metric_key))
        layout.addWidget(remove_btn)

        self.checkbox_layout.addWidget(container)

        self.metric_checkboxes[metric_key] = {
            'checkbox': checkbox,
            'container': container,
            'color': color
        }

        self.update_dropdown()
        return True

    def remove_metric_checkbox(self, metric_key):
        """Remove a metric checkbox"""
        if metric_key in self.metric_checkboxes:
            container = self.metric_checkboxes[metric_key]['container']
            self.checkbox_layout.removeWidget(container)
            container.deleteLater()
            del self.metric_checkboxes[metric_key]

            self.update_dropdown()
            self.update_plot()

    def update_dropdown(self):
        """Update dropdown with available metrics"""
        self.metric_dropdown.clear()
        self.metric_dropdown.addItem("-- Select Metric --")

        all_metrics = self.get_all_available_metrics()
        available = [m for m in all_metrics if m[0] not in self.metric_checkboxes]

        for metric_key, display_name, _ in available:
            self.metric_dropdown.addItem(display_name, metric_key)

        # Update info
        count = len(self.metric_checkboxes)
        self.info_label.setText(f"Active metrics: {count}/4")
        if count >= 4:
            self.info_label.setStyleSheet("QLabel { color: #ff6b6b; font-style: italic; }")
        else:
            self.info_label.setStyleSheet("QLabel { color: #666; font-style: italic; }")

    def on_metric_selected(self, display_name):
        """Handle metric selection from dropdown"""
        if display_name == "-- Select Metric --":
            return

        metric_key = self.metric_dropdown.currentData()
        if metric_key and len(self.metric_checkboxes) < 4:
            # Find the color for this metric
            all_metrics = self.get_all_available_metrics()
            color = '#000000'  # default
            for key, name, clr in all_metrics:
                if key == metric_key:
                    color = clr
                    break

            if self.add_metric_checkbox(metric_key, display_name, color, checked=True):
                self.update_plot()

        # Reset dropdown
        self.metric_dropdown.setCurrentIndex(0)

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
        for metric_data in self.metric_checkboxes.values():
            metric_data['checkbox'].setEnabled(enabled)
        self.metric_dropdown.setEnabled(enabled)

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

        # Plot each selected metric
        for metric_key, metric_data in self.metric_checkboxes.items():
            checkbox = metric_data['checkbox']
            color = metric_data['color']

            if checkbox.isChecked() and metric_key in self.data:
                pen = pg.mkPen(color=color, width=2)
                self.plots[metric_key] = self.graph_widget.plot(
                    time_minutes, self.data[metric_key],
                    pen=pen, name=checkbox.text()
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
