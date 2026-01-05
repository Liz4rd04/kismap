# kismap

A modern WiFi heatmap generator for Kismet's `.kismet` SQLite database files.

**kismap** is a Python tool that reads Kismet capture files and generates interactive HTML heatmaps using Folium/Leaflet. No Google API key required!

This tool was created as a modern replacement for [kismapping](https://github.com/inguardians/kismapping), which only supports the legacy `.gpsxml` format that Kismet no longer produces.

## Features

- ✅ Works with modern `.kismet` SQLite files
- ✅ Interactive HTML output with multiple map layers (OpenStreetMap, Dark Mode, Light Mode)
- ✅ Filter by WiFi band (2.4 GHz, 5 GHz, 6 GHz)
- ✅ Filter by SSID, MAC address, or device type
- ✅ Clustered AP markers with popup info (SSID, MAC, signal strength)
- ✅ CSV export for further analysis
- ✅ No API keys required - uses OpenStreetMap tiles
- ✅ Signal strength legend
- ✅ Layer controls to toggle heatmap/markers

## Screenshot

![kismap heatmap example](https://user-images.githubusercontent.com/placeholder/kismap-example.png)

## Installation

### Dependencies

```bash
# Debian/Ubuntu/Raspberry Pi OS
sudo apt install python3-folium

# Or using pip
pip3 install folium --break-system-packages
```

### Install kismap

```bash
git clone https://github.com/Liz4rd04/kismap.git
cd kismap
chmod +x kismap.py
```

Optionally, copy to your PATH:
```bash
sudo cp kismap.py /usr/local/bin/kismap
```

## Usage

### Basic Usage

```bash
# Generate heatmap from Kismet capture
python3 kismap.py -i wardrive.kismet -o heatmap.html

# Open in browser
firefox heatmap.html
```

### Filter by Band

```bash
# 5 GHz only
python3 kismap.py -i capture.kismet -b 5 -o 5ghz_map.html

# 5 GHz and 6 GHz (WiFi 6E)
python3 kismap.py -i capture.kismet -b 5 -b 6 -o wifi6_map.html
```

### Filter by SSID

```bash
# Single SSID
python3 kismap.py -i capture.kismet -e "MyNetwork" -o mynetwork.html

# Multiple SSIDs
python3 kismap.py -i capture.kismet -e "Network1" -e "Network2" -o networks.html
```

### Export to CSV

```bash
python3 kismap.py -i capture.kismet --export-csv -v
```

### All Options

```
usage: kismap.py [-h] -i INPUT [-o OUTPUT] [-e ESSID] [-m MAC] [-t TYPE]
                 [-b {2.4,5,6}] [--min-signal MIN_SIGNAL] [--all-devices]
                 [--no-heatmap] [--export-csv] [-v]

Options:
  -i, --input         Input .kismet file (required)
  -o, --output        Output HTML file (default: kismet_heatmap.html)
  -e, --essid         Filter by ESSID (can be used multiple times)
  -m, --mac           Filter by MAC address (can be used multiple times)
  -t, --type          Filter by device type (e.g., "Wi-Fi AP")
  -b, --band          Filter by band: 2.4, 5, or 6 GHz (can repeat)
  --min-signal        Minimum signal strength in dBm (default: -100)
  --all-devices       Show all devices, not just APs
  --no-heatmap        Disable heatmap layer, show only markers
  --export-csv        Also export data to CSV file
  -v, --verbose       Verbose output with statistics
```

## Example Output

With verbose mode (`-v`), you'll see statistics like:

```
Loading data from wardrive.kismet...
Found 92,354 packets and 394 devices

Packets by band:
  2.4 GHz: 14,805
  5 GHz: 77,480
  6 GHz: 69

Top 10 SSIDs:
  Medcurity Main: 38,832
  xfinitywifi: 5,500
  BANet4-5GHz: 1,660
  ...

Generating heatmap...
✓ Heatmap saved to: wifi_heatmap.html
✓ CSV exported to: wifi_heatmap.csv
```

## Requirements

- Python 3.6+
- folium (`sudo apt install python3-folium` or `pip3 install folium`)
- A `.kismet` file from Kismet (2019+ versions that use SQLite format)

## How It Works

1. Reads the SQLite `.kismet` database
2. Extracts GPS coordinates, signal strength, frequency, and device info from the `packets` and `devices` tables
3. Filters data based on user criteria
4. Generates an interactive Folium map with:
   - Heatmap layer showing signal strength (red=strong, blue=weak)
   - Clustered markers for each Access Point
   - Multiple tile layers (street map, dark mode, light mode)
   - Layer controls to toggle visibility

## License

GPLv2 - Inspired by [inguardians/kismapping](https://github.com/inguardians/kismapping)

## Credits

- Original kismapping concept by [InGuardians](https://github.com/inguardians/kismapping) and Tom Liston
- [Kismet](https://www.kismetwireless.net/) by Mike Kershaw
- [Folium](https://python-visualization.github.io/folium/) for map generation

## Contributing

Pull requests welcome! Ideas for improvements:
- [ ] KML/KMZ export for Google Earth
- [ ] Time-based animation of captures
- [ ] Signal interpolation for smoother heatmaps
- [ ] Multiple capture file merging
