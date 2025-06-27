# KlipperLogAnalyzer

A powerful performance monitoring tool for Klipper 3D printers that analyzes klippy.log files and provides real-time visualization of system metrics.

## 📊 Features

- **Real-time Performance Monitoring**: Analyze MCU load, bandwidth, buffer times, and more
- **25+ Metrics Available**: Choose from comprehensive printer performance indicators
- **Flexible Display**: Select any 4 metrics to display simultaneously
- **Interactive Graphs**: Zoom, pan, and explore your printer's performance over time
- **Easy to Use**: Simple drag-and-drop interface for log files
- **Standalone Application**: No Python installation required

1. **Download the latest release**:
   - Go to [Releases](../../releases)
   - Download `Klippy.Log.Analyzer.zip` from the latest release
   - No installation required - just run the executable!

2. **Alternative: Build from Source**
   ```bash
   git clone https://github.com/yourusername/klippy-log-analyzer.git
   cd klippy-log-analyzer
   pip install -r requirements.txt
   python klippy_analyzer.py
   ```
   
### Development Setup
```bash
git clone https://github.com/yourusername/klippy-log-analyzer.git
cd klippy-log-analyzer
pip install -r requirements.txt
python klippy_analyzer.py
```

### Building Executable
```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name "Klippy Log Analyzer" klippy_analyzer.py
```