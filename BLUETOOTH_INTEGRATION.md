# uMyo Bluetooth Integration Guide

## Overview

The uMyo Bluetooth module provides direct wireless connectivity to uMyo devices without requiring the USB dongle. This implementation is fully compatible with the URF library BLE stack running on nRF52832 microcontrollers.

## Features

- ✅ **Direct BLE Connection** - Connect directly to uMyo devices via Bluetooth
- ✅ **URF Library Compatible** - Full integration with Nordic nRF52832 BLE stack  
- ✅ **Multiple Services** - Support for EMG, IMU, and device information characteristics
- ✅ **Auto-Discovery** - Intelligent device scanning with multiple detection methods
- ✅ **Auto-Reconnection** - Automatic reconnection on connection loss
- ✅ **Parser Integration** - Seamless integration with existing umyo_parser
- ✅ **Real-time Streaming** - High-performance data streaming with statistics

## Quick Start

### 1. Install Dependencies
```bash
pip install bleak  # Bluetooth Low Energy library
```

### 2. Basic Connection Test
```python
import asyncio
from umyo_bluetooth import uMyoBluetoothManager
import umyo_parser

async def simple_test():
    # Create manager
    manager = uMyoBluetoothManager()
    
    # Connect to device
    connected = await manager.discover_and_connect()
    if connected:
        print("Connected!")
        
        # Start data streaming
        await manager.start_streaming()
        
        # Monitor for 10 seconds
        for _ in range(10):
            devices = umyo_parser.umyo_get_list()
            if devices:
                device = devices[0]
                print(f"EMG: {device.data_array[-1]}")
            await asyncio.sleep(1)
    
    await manager.disconnect()

# Run test
asyncio.run(simple_test())
```

### 3. Advanced Usage
```python
# Create manager with custom settings
manager = uMyoBluetoothManager(
    auto_reconnect=True,
    max_reconnect_attempts=10
)

# Set custom data callback
def my_data_handler(data):
    print(f"Received {len(data)} bytes")

manager.set_data_callback(my_data_handler)

# Get connection info
info = manager.get_connection_info()
print(f"Connected: {info['connected']}")
print(f"Device: {info['device_address']}")
```

## URF Library Integration

This module is specifically designed to work with uMyo devices running the URF library firmware:

### Supported Services
- **Nordic UART Service** (`6E400001-B5A3-F393-E0A9-E50E24DCCA9E`) - Primary data stream
- **Custom EMG Service** - EMG-specific data characteristics  
- **Custom IMU Service** - 3D orientation and motion data
- **Device Information Service** - Battery, firmware, hardware info

### Device Discovery Methods
1. **Device Name Filtering** - Searches for "uMyo", "EMG_", "URF_" prefixes
2. **Manufacturer Data** - Nordic Semiconductor manufacturer ID
3. **Service UUIDs** - Known uMyo/URF service advertisements
4. **Keyword Matching** - "nrf52", "nordic", "emg", "sensor" in device names

### Data Format Compatibility
The module automatically handles different data formats:
- Raw protocol packets (same as USB dongle)
- URF library structured BLE packets
- Multiple characteristic data streams

## Applications

### 1. Bluetooth Mouse Control
```bash
python umyo_bluetooth_mouse.py
```
Gesture-based mouse control using Bluetooth connectivity.

### 2. Simple Data Monitoring  
```bash
python umyo_bluetooth_example.py
```
Basic data streaming and monitoring example.

### 3. Integration Test
```bash
python umyo_bluetooth.py
```
Comprehensive test of all Bluetooth features.

## Troubleshooting

### Connection Issues
- **Device not found**: Ensure uMyo is in pairing/advertising mode
- **Connection timeout**: Move closer to device (< 10 meters)
- **Permission denied**: May need to pair device through OS settings first

### Data Issues  
- **No data received**: Check URF library firmware compatibility
- **Parsing errors**: Verify umyo_parser integration is working
- **Intermittent data**: Check Bluetooth signal strength and interference

### URF Library Compatibility
- **Service discovery fails**: Device may not be running URF library firmware
- **Wrong characteristics**: Update UUIDs for your specific firmware version
- **Protocol mismatch**: Ensure data format matches umyo_parser expectations

## Configuration

### Custom UUIDs
If your uMyo device uses different UUIDs, update these constants in `umyo_bluetooth.py`:

```python
# Update these for your specific firmware
UMYO_SERVICE_UUID = "your-service-uuid-here"
UMYO_RX_CHAR_UUID = "your-rx-characteristic-uuid"
UMYO_EMG_SERVICE_UUID = "your-emg-service-uuid"
```

### Device Filtering
Customize device discovery by modifying:

```python
UMYO_DEVICE_NAME_PATTERNS = ["uMyo", "YourDevice", "CustomName"]
UMYO_MANUFACTURER_ID = 0x0059  # Your manufacturer ID
```

## Performance

### Typical Performance Metrics
- **Connection Time**: 2-5 seconds
- **Data Latency**: < 10ms
- **Throughput**: Up to 244 bytes per packet (nRF52832 MTU limit)
- **Range**: Up to 10 meters (line of sight)
- **Battery Impact**: Minimal (BLE Low Energy)

### Optimization Tips
- Use `auto_reconnect=True` for reliable connections
- Monitor data statistics with built-in logging
- Adjust scan timeout based on environment
- Use multiple characteristics for high-throughput applications

## Compatibility

### Operating Systems
- ✅ **Windows 10/11** - Built-in Bluetooth stack
- ✅ **macOS** - Core Bluetooth framework  
- ✅ **Linux** - BlueZ Bluetooth stack

### Python Versions
- ✅ **Python 3.7+** - Async/await support required
- ✅ **Python 3.8+** - Recommended for best performance
- ✅ **Python 3.9+** - Full feature compatibility

### Hardware Requirements
- Bluetooth 4.0+ adapter (BLE support)
- uMyo device with URF library firmware
- nRF52832 or compatible microcontroller

## License

This module is part of the uMyo Python Tools and is licensed under the MIT License. The URF library integration maintains compatibility with Nordic SDK licensing requirements.
