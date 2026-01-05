#!/usr/bin/env python3
"""
kismap - WiFi Heatmap Generator for Kismet SQLite databases

A modern replacement for kismapping that works with the new .kismet SQLite format.
Generates interactive HTML heatmaps using Folium/Leaflet (no Google API key required).

Usage:
    python3 kismap.py -i capture.kismet [options]

Examples:
    # Generate heatmap for all APs
    python3 kismap.py -i wardrive.kismet -o heatmap.html

    # Filter by specific SSID
    python3 kismap.py -i wardrive.kismet -e "MyNetwork" -o mynetwork.html

    # Show only 5GHz band
    python3 kismap.py -i wardrive.kismet -b 5 -o 5ghz_heatmap.html

    # Export to CSV as well
    python3 kismap.py -i wardrive.kismet --export-csv -v

Author: Liz4rd04 - inspired by inguardians/kismapping
License: GPLv2
"""

import sqlite3
import argparse
import json
import sys
import os
from collections import defaultdict

try:
    import folium
    from folium.plugins import HeatMap, MarkerCluster
    FOLIUM_AVAILABLE = True
except ImportError:
    FOLIUM_AVAILABLE = False

def get_band(frequency):
    """Determine WiFi band from frequency (handles Hz, kHz, or MHz)"""
    if frequency <= 0:
        return "unknown"
    
    # Kismet stores frequency in kHz (e.g., 2412000 for 2412 MHz)
    # Convert to MHz for easier comparison
    if frequency > 100000:  # It's in kHz
        freq_mhz = frequency / 1000
    elif frequency > 100:  # It's already in MHz
        freq_mhz = frequency
    else:  # It's in GHz
        freq_mhz = frequency * 1000
    
    if 2400 <= freq_mhz <= 2500:
        return "2.4"
    elif 5150 <= freq_mhz <= 5895:
        return "5"
    elif 5925 <= freq_mhz <= 7125:
        return "6"
    return "unknown"

def signal_to_weight(signal_dbm):
    """Convert signal strength to heatmap weight (0-1)"""
    min_signal = -95
    max_signal = -30
    normalized = (signal_dbm - min_signal) / (max_signal - min_signal)
    return max(0.1, min(1, normalized))

def load_kismet_data(db_path, args):
    """Load and filter data from Kismet SQLite database"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get device info (for SSIDs and device types)
    devices = {}
    cursor.execute("""
        SELECT devmac, type, strongest_signal, avg_lat, avg_lon, device 
        FROM devices 
        WHERE avg_lat != 0 AND avg_lon != 0
    """)
    for row in cursor.fetchall():
        mac = row['devmac']
        devices[mac] = {
            'type': row['type'],
            'strongest_signal': row['strongest_signal'],
            'avg_lat': row['avg_lat'],
            'avg_lon': row['avg_lon'],
            'ssid': None
        }
        # Try to extract SSID from device blob
        if row['device']:
            try:
                device_json = json.loads(row['device'])
                dot11 = device_json.get('dot11.device', {})
                if dot11:
                    ssid_record = dot11.get('dot11.device.last_beaconed_ssid_record', {})
                    if ssid_record:
                        ssid = ssid_record.get('dot11.advertisedssid.ssid', '')
                        if ssid:
                            devices[mac]['ssid'] = ssid
            except (json.JSONDecodeError, TypeError):
                pass
    
    # Get packet data with GPS coordinates
    cursor.execute("""
        SELECT lat, lon, signal, frequency, sourcemac, destmac, ts_sec
        FROM packets 
        WHERE lat != 0 AND lon != 0 AND signal != 0
        ORDER BY ts_sec
    """)
    
    packets = []
    for row in cursor.fetchall():
        band = get_band(row['frequency'])
        packet = {
            'lat': row['lat'],
            'lon': row['lon'],
            'signal': row['signal'],
            'frequency': row['frequency'],
            'mac': row['sourcemac'],
            'timestamp': row['ts_sec'],
            'band': band
        }
        
        # Add device info if available
        if packet['mac'] in devices:
            packet['ssid'] = devices[packet['mac']].get('ssid')
            packet['type'] = devices[packet['mac']].get('type')
        else:
            packet['ssid'] = None
            packet['type'] = None
        
        # Apply filters
        if args.band and packet['band'] not in args.band:
            continue
        if args.min_signal and packet['signal'] < args.min_signal:
            continue
        if args.type and packet['type'] not in args.type:
            continue
        if args.essid and packet['ssid'] not in args.essid:
            continue
        if args.mac and packet['mac'] not in args.mac:
            continue
        if not args.all_devices and packet['type'] and 'AP' not in packet['type']:
            continue
            
        packets.append(packet)
    
    conn.close()
    return packets, devices

def generate_heatmap(packets, devices, args):
    """Generate Folium heatmap HTML"""
    if not packets:
        print("No packets match the filter criteria!")
        return None
    
    # Calculate map center
    lats = [p['lat'] for p in packets]
    lons = [p['lon'] for p in packets]
    center_lat = sum(lats) / len(lats)
    center_lon = sum(lons) / len(lons)
    
    # Create map
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=18,
        tiles='OpenStreetMap'
    )
    
    # Add tile layers
    folium.TileLayer('cartodbdark_matter', name='Dark Mode').add_to(m)
    folium.TileLayer('cartodbpositron', name='Light Mode').add_to(m)
    
    if not args.no_heatmap:
        # Prepare heatmap data by band
        heat_data_by_band = defaultdict(list)
        for p in packets:
            weight = signal_to_weight(p['signal'])
            heat_data_by_band[p['band']].append([p['lat'], p['lon'], weight])
        
        # Add heatmap layers for each band
        band_colors = {'2.4': 'blue', '5': 'green', '6': 'purple', 'unknown': 'gray'}
        for band, heat_data in heat_data_by_band.items():
            if heat_data:
                HeatMap(
                    heat_data,
                    name=f'Heatmap {band} GHz ({len(heat_data)} pts)',
                    radius=20,
                    blur=15,
                    min_opacity=0.4
                ).add_to(m)
    
    # Add markers for unique APs
    ap_cluster = MarkerCluster(name='Access Points').add_to(m)
    seen_macs = set()
    
    for mac, dev in devices.items():
        if mac in seen_macs:
            continue
        if dev['avg_lat'] == 0 or dev['avg_lon'] == 0:
            continue
        if dev['type'] and 'AP' not in dev['type']:
            continue
            
        seen_macs.add(mac)
        ssid = dev.get('ssid') or 'Hidden'
        signal = dev.get('strongest_signal', 'N/A')
        
        popup_html = f"""
        <b>SSID:</b> {ssid}<br>
        <b>MAC:</b> {mac}<br>
        <b>Signal:</b> {signal} dBm<br>
        <b>Type:</b> {dev.get('type', 'Unknown')}
        """
        
        folium.Marker(
            location=[dev['avg_lat'], dev['avg_lon']],
            popup=folium.Popup(popup_html, max_width=300),
            icon=folium.Icon(color='blue', icon='wifi', prefix='fa'),
            tooltip=ssid
        ).add_to(ap_cluster)
    
    # Add layer control
    folium.LayerControl().add_to(m)
    
    # Add legend
    legend_html = '''
    <div style="position: fixed; bottom: 50px; left: 50px; z-index: 1000; 
                background-color: white; padding: 10px; border-radius: 5px;
                border: 2px solid gray; font-family: Arial; font-size: 12px;">
        <b>WiFi Signal Heatmap</b><br>
        <span style="color: red;">■</span> Excellent (>-40 dBm)<br>
        <span style="color: orange;">■</span> Good (-40 to -60 dBm)<br>
        <span style="color: yellow;">■</span> Fair (-60 to -75 dBm)<br>
        <span style="color: green;">■</span> Weak (-75 to -85 dBm)<br>
        <span style="color: blue;">■</span> Poor (<-85 dBm)<br>
        <hr style="margin: 5px 0;">
        <small>Generated by kismap</small>
    </div>
    '''
    m.get_root().html.add_child(folium.Element(legend_html))
    
    return m

def export_csv(packets, output_path):
    """Export packet data to CSV"""
    csv_path = output_path.replace('.html', '.csv')
    with open(csv_path, 'w') as f:
        f.write("timestamp,lat,lon,signal,frequency_khz,band,mac,ssid,type\n")
        for p in packets:
            ssid = (p.get('ssid') or '').replace(',', ';').replace('"', "'")
            f.write(f"{p['timestamp']},{p['lat']},{p['lon']},{p['signal']},"
                    f"{p['frequency']},{p['band']},{p['mac']},\"{ssid}\",{p.get('type','')}\n")
    return csv_path

def main():
    parser = argparse.ArgumentParser(
        description='Generate WiFi heatmaps from Kismet .kismet files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  kismap.py -i capture.kismet                    # Basic heatmap
  kismap.py -i capture.kismet -b 5 -b 6          # 5GHz and 6GHz only
  kismap.py -i capture.kismet -e "MyWiFi"        # Specific SSID
  kismap.py -i capture.kismet --export-csv -v    # Verbose + CSV export
        """
    )
    parser.add_argument('-i', '--input', required=True, help='Input .kismet file')
    parser.add_argument('-o', '--output', default='kismet_heatmap.html', help='Output HTML file')
    parser.add_argument('-e', '--essid', action='append', help='Filter by ESSID (can repeat)')
    parser.add_argument('-m', '--mac', action='append', help='Filter by MAC (can repeat)')
    parser.add_argument('-t', '--type', action='append', help='Filter by device type')
    parser.add_argument('-b', '--band', action='append', choices=['2.4', '5', '6'], 
                        help='Filter by band: 2.4, 5, or 6 GHz (can repeat)')
    parser.add_argument('--min-signal', type=int, default=-100, help='Min signal in dBm')
    parser.add_argument('--all-devices', action='store_true', help='Show all devices, not just APs')
    parser.add_argument('--no-heatmap', action='store_true', help='Disable heatmap layer')
    parser.add_argument('--export-csv', action='store_true', help='Also export to CSV')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    if not FOLIUM_AVAILABLE:
        print("Error: folium is required.")
        print("Install with: sudo apt install python3-folium")
        sys.exit(1)
    
    if not os.path.exists(args.input):
        print(f"Error: Input file not found: {args.input}")
        sys.exit(1)
    
    print(f"Loading data from {args.input}...")
    packets, devices = load_kismet_data(args.input, args)
    
    print(f"Found {len(packets)} packets and {len(devices)} devices")
    
    if args.verbose:
        bands = defaultdict(int)
        types = defaultdict(int)
        ssids = defaultdict(int)
        for p in packets:
            bands[p['band']] += 1
            if p.get('type'):
                types[p['type']] += 1
            if p.get('ssid'):
                ssids[p['ssid']] += 1
        
        print("\nPackets by band:")
        for band, count in sorted(bands.items()):
            print(f"  {band} GHz: {count:,}")
        
        print("\nPackets by device type:")
        for dtype, count in sorted(types.items(), key=lambda x: -x[1])[:10]:
            print(f"  {dtype}: {count:,}")
        
        print("\nTop 10 SSIDs:")
        for ssid, count in sorted(ssids.items(), key=lambda x: -x[1])[:10]:
            print(f"  {ssid}: {count:,}")
    
    print(f"\nGenerating heatmap...")
    heatmap = generate_heatmap(packets, devices, args)
    
    if heatmap:
        heatmap.save(args.output)
        print(f"✓ Heatmap saved to: {args.output}")
        
        if args.export_csv:
            csv_path = export_csv(packets, args.output)
            print(f"✓ CSV exported to: {csv_path}")
        
        print(f"\nOpen {args.output} in a web browser to view the heatmap!")
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
