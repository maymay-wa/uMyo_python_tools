"""uMyo Bluetooth Connection Module

Provides direct Bluetooth Low Energy connectivity for uMyo devices,
maintaining compatibility with the existing umyo_parser pipeline.

Features:
    - Direct BLE connection (no USB dongle required)
    - Automatic device discovery and connection
    - Real-time data streaming with automatic reconnection
    - Full compatibility with existing umyo_parser

Requirements:
    - Python 3.7+
    - bleak library
    - uMyo device with Bluetooth enabled

Usage:
    ```python
    manager = uMyoBluetoothManager()
    await manager.discover_and_connect()
    await manager.start_streaming()
    
    # Process data using existing parser
    devices = umyo_parser.umyo_get_list()
    ```

Author: uMyo Development Team
Version: 1.1
"""

import asyncio
import time
from typing import Optional, List, Callable, Dict
import logging
from dataclasses import dataclass

try:
    from bleak import BleakScanner, BleakClient
    from bleak.backends.characteristic import BleakGATTCharacteristic
except ImportError:
    raise ImportError("bleak library required. Install with: pip install bleak")

import umyo_parser


@dataclass
class BLEConfig:
    """Configuration constants for uMyo BLE communication."""
    # Nordic UART Service UUIDs
    SERVICE_UUID = "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"
    TX_CHAR_UUID = "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"
    RX_CHAR_UUID = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"
    
    # Custom uMyo service UUIDs
    EMG_SERVICE_UUID = "12345678-1234-5678-9ABC-DEF012345678"
    EMG_DATA_CHAR_UUID = "12345679-1234-5678-9ABC-DEF012345678"
    IMU_DATA_CHAR_UUID = "1234567A-1234-5678-9ABC-DEF012345678"
    DEVICE_INFO_CHAR_UUID = "1234567B-1234-5678-9ABC-DEF012345678"
    
    # Standard service UUIDs
    BATTERY_SERVICE_UUID = "0000180f-0000-1000-8000-00805f9b34fb"
    DEVICE_INFO_SERVICE_UUID = "0000180a-0000-1000-8000-00805f9b34fb"
    
    # Device identification
    MANUFACTURER_ID = 0x0059  # Nordic Semiconductor
    DEVICE_NAME_PATTERNS = ["uMyo", "EMG_", "URF_"]
    
    # Connection parameters
    SCAN_TIMEOUT = 15.0
    CONNECTION_TIMEOUT = 10.0
    MTU_SIZE = 244
    
    # Commands
    START_COMMAND = b'\x01\x00\x01'
    STOP_COMMAND = b'\x01\x00\x00'


@dataclass
class DeviceInfo:
    """Container for device information."""
    name: str = "Unknown"
    manufacturer: str = "Unknown"
    firmware: str = "Unknown"
    hardware: str = "Unknown"
    battery_percent: Optional[int] = None


class uMyoBluetoothManager:
    """Simplified Bluetooth manager for uMyo devices.
    
    Handles device discovery, connection, and data streaming with automatic
    reconnection and integration with the existing uMyo parser.
    """
    
    def __init__(self, auto_reconnect: bool = True, max_reconnect_attempts: int = 5):
        """Initialize the Bluetooth manager."""
        self.client: Optional[BleakClient] = None
        self.device_address: Optional[str] = None
        self.is_connected: bool = False
        self.is_streaming: bool = False
        self.auto_reconnect: bool = auto_reconnect
        self.reconnect_attempts: int = 0
        self.max_reconnect_attempts: int = max_reconnect_attempts
        self.data_callback: Optional[Callable] = None
        self.last_data_time: float = 0
        self._stats = {'total_bytes': 0, 'total_packets': 0, 'start_time': time.time()}
        
        # Setup logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
    
    async def discover_devices(self, timeout: float = 15.0) -> List[str]:
        """Discover uMyo devices via Bluetooth scanning."""
        self.logger.info(f"Scanning for uMyo devices (timeout: {timeout}s)...")
        
        devices = await BleakScanner.discover(timeout=timeout, return_adv=True)
        umyo_devices = []
        
        for address, (device, adv_data) in devices.items():
            if self._is_umyo_device(device, adv_data):
                umyo_devices.append(address)
                self.logger.info(f"Found uMyo device: {device.name or 'Unknown'} ({address})")
        
        if not umyo_devices:
            self.logger.warning("No uMyo devices found. Check device power and pairing mode.")
        
        return umyo_devices
    
    def _is_umyo_device(self, device, adv_data) -> bool:
        """Check if a device is a uMyo device using multiple criteria."""
        # Check device name patterns
        if device.name:
            for pattern in BLEConfig.DEVICE_NAME_PATTERNS:
                if pattern.lower() in device.name.lower():
                    return True
        
        # Check manufacturer data
        if adv_data.manufacturer_data and BLEConfig.MANUFACTURER_ID in adv_data.manufacturer_data:
            return True
        
        # Check advertised services
        if adv_data.service_uuids:
            target_services = {
                BLEConfig.SERVICE_UUID.lower(),
                BLEConfig.EMG_SERVICE_UUID.lower(),
                BLEConfig.BATTERY_SERVICE_UUID.lower(),
                BLEConfig.DEVICE_INFO_SERVICE_UUID.lower()
            }
            service_uuids = {uuid.lower() for uuid in adv_data.service_uuids}
            return bool(target_services & service_uuids)
        
        return False
    
    async def connect_to_device(self, device_address: str) -> bool:
        """Connect to a specific uMyo device."""
        try:
            self.logger.info(f"Connecting to device: {device_address}")
            
            self.client = BleakClient(device_address, disconnected_callback=self._on_disconnect)
            await self.client.connect(timeout=BLEConfig.CONNECTION_TIMEOUT)
            
            if self.client.is_connected:
                self.device_address = device_address
                self.is_connected = True
                self.reconnect_attempts = 0
                
                self.logger.info(f"Connected to {device_address}")
                await self._setup_connection()
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Connection error: {e}")
            return False
    
    async def _setup_connection(self):
        """Setup connection parameters and discover services."""
        if not self.client:
            return
        
        # Set MTU for better performance
        try:
            await self.client.request_mtu(BLEConfig.MTU_SIZE)
        except Exception:
            pass  # MTU setting is optional
        
        # Log available services
        services = self.client.services
        self.logger.debug(f"Found {len(services)} services")
    
    async def discover_and_connect(self, timeout: float = 15.0) -> bool:
        """Discover and connect to the first available uMyo device."""
        devices = await self.discover_devices(timeout)
        return bool(devices) and await self.connect_to_device(devices[0])
    
    async def start_streaming(self) -> bool:
        """Start receiving data from the connected device."""
        if not self.is_connected or not self.client:
            self.logger.error("Device not connected")
            return False
        
        try:
            # Start notifications on available characteristics
            characteristics = [
                (BLEConfig.RX_CHAR_UUID, "UART RX"),
                (BLEConfig.EMG_DATA_CHAR_UUID, "EMG data"),
                (BLEConfig.IMU_DATA_CHAR_UUID, "IMU data"),
                (BLEConfig.DEVICE_INFO_CHAR_UUID, "Device info")
            ]
            
            notifications_started = 0
            for char_uuid, name in characteristics:
                try:
                    await self.client.start_notify(char_uuid, self._data_handler)
                    self.logger.debug(f"Started {name} notifications")
                    notifications_started += 1
                except Exception:
                    continue  # Characteristic not available
            
            if notifications_started > 0:
                self.is_streaming = True
                await self._send_command(BLEConfig.START_COMMAND)
                self.logger.info(f"Streaming started ({notifications_started} characteristics)")
                return True
            
            self.logger.error("No notification characteristics available")
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to start streaming: {e}")
            return False
    
    async def stop_streaming(self) -> bool:
        """Stop receiving data from the connected device."""
        if not self.is_connected or not self.client:
            return False
        
        try:
            await self._send_command(BLEConfig.STOP_COMMAND)
            
            # Stop notifications on all characteristics
            characteristics = [
                BLEConfig.RX_CHAR_UUID,
                BLEConfig.EMG_DATA_CHAR_UUID,
                BLEConfig.IMU_DATA_CHAR_UUID,
                BLEConfig.DEVICE_INFO_CHAR_UUID
            ]
            
            for char_uuid in characteristics:
                try:
                    await self.client.stop_notify(char_uuid)
                except Exception:
                    continue  # Characteristic may not be active
            
            self.is_streaming = False
            self.logger.info("Streaming stopped")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to stop streaming: {e}")
            return False
    
    async def _send_command(self, command: bytes):
        """Send command to the device."""
        try:
            await self.client.write_gatt_char(BLEConfig.TX_CHAR_UUID, command)
        except Exception as e:
            self.logger.debug(f"Command send failed: {e}")
    
    def _data_handler(self, characteristic: BleakGATTCharacteristic, data: bytearray):
        """Handle incoming data from any characteristic."""
        self.last_data_time = time.time()
        
        try:
            # Process data based on characteristic type
            char_uuid = characteristic.uuid.lower()
            
            if char_uuid == BLEConfig.DEVICE_INFO_CHAR_UUID.lower():
                self._process_device_info(data)
            else:
                # Process as sensor data
                payload = self._extract_payload(data)
                umyo_parser.umyo_parse_preprocessor(payload)
                
                # Update statistics
                self._update_stats(len(data))
                
                # Call custom callback if set
                if self.data_callback:
                    self.data_callback(data)
                    
        except Exception as e:
            self.logger.error(f"Data processing error: {e}")
    
    def _extract_payload(self, data: bytearray) -> bytearray:
        """Extract payload from structured BLE packet."""
        if len(data) > 2 and data[0] in [0x01, 0x02, 0x03]:
            return data[1:]  # Skip packet type byte
        return data  # Use raw data
    
    def _process_device_info(self, data: bytearray):
        """Process device information data."""
        if len(data) >= 4:
            try:
                battery = (data[1] << 8) | data[0]
                firmware = f"{data[2]}.{data[3]}"
                self.logger.debug(f"Battery: {battery}mV, Firmware: {firmware}")
            except Exception:
                pass
    
    def _update_stats(self, bytes_received: int):
        """Update data reception statistics."""
        self._stats['total_bytes'] += bytes_received
        self._stats['total_packets'] += 1
        
        # Log stats every 100 packets
        if self._stats['total_packets'] % 100 == 0:
            elapsed = time.time() - self._stats['start_time']
            if elapsed > 0:
                rate = self._stats['total_bytes'] / elapsed
                self.logger.debug(f"Data rate: {rate:.1f} B/s")
    
    def _on_disconnect(self, client: BleakClient):
        """Handle device disconnection."""
        self.logger.warning("Device disconnected")
        self.is_connected = False
        self.is_streaming = False
        
        if self.auto_reconnect and self.reconnect_attempts < self.max_reconnect_attempts:
            self.logger.info(f"Attempting reconnection ({self.reconnect_attempts + 1}/{self.max_reconnect_attempts})")
            asyncio.create_task(self._reconnect())
    
    async def _reconnect(self):
        """Attempt to reconnect to the device."""
        self.reconnect_attempts += 1
        await asyncio.sleep(2.0)  # Wait before reconnecting
        
        if self.device_address:
            success = await self.connect_to_device(self.device_address)
            if success:
                await self.start_streaming()
    
    async def disconnect(self):
        """Disconnect from the current device."""
        if self.client and self.is_connected:
            try:
                if self.is_streaming:
                    await self.stop_streaming()
                await self.client.disconnect()
                self.logger.info("Disconnected from device")
            except Exception as e:
                self.logger.error(f"Disconnect error: {e}")
            finally:
                self.client = None
                self.device_address = None
                self.is_connected = False
                self.is_streaming = False
    
    async def read_device_info(self) -> DeviceInfo:
        """Read device information from connected device."""
        if not self.is_connected or not self.client:
            return DeviceInfo()
        
        device_info = DeviceInfo()
        
        # Standard characteristics to read
        info_chars = {
            "00002a00-0000-1000-8000-00805f9b34fb": "device_name",
            "00002a29-0000-1000-8000-00805f9b34fb": "manufacturer", 
            "00002a26-0000-1000-8000-00805f9b34fb": "firmware",
            "00002a27-0000-1000-8000-00805f9b34fb": "hardware",
            "00002a19-0000-1000-8000-00805f9b34fb": "battery_percent"
        }
        
        for char_uuid, attr_name in info_chars.items():
            try:
                data = await self.client.read_gatt_char(char_uuid)
                if attr_name == "battery_percent":
                    setattr(device_info, attr_name, data[0] if data else None)
                else:
                    setattr(device_info, attr_name, data.decode('utf-8').strip('\x00'))
            except Exception:
                continue  # Characteristic not available
        
        return device_info
    
    def set_data_callback(self, callback: Callable):
        """Set custom callback for received data."""
        self.data_callback = callback
    
    def get_connection_info(self) -> Dict:
        """Get current connection information."""
        return {
            "connected": self.is_connected,
            "device_address": self.device_address,
            "streaming": self.is_streaming,
            "reconnect_attempts": self.reconnect_attempts,
            "last_data_time": self.last_data_time,
            "stats": self._stats
        }


# Utility functions for easier usage
async def quick_connect() -> Optional[uMyoBluetoothManager]:
    """Quick connection helper function.
    
    Returns:
        Connected uMyoBluetoothManager instance or None if failed
    """
    manager = uMyoBluetoothManager()
    success = await manager.discover_and_connect()
    if success:
        await manager.start_streaming()
        return manager
    return None


def create_manager(**kwargs) -> uMyoBluetoothManager:
    """Create a new Bluetooth manager with optional parameters.
    
    Args:
        **kwargs: Arguments passed to uMyoBluetoothManager constructor
        
    Returns:
        New uMyoBluetoothManager instance
    """
    return uMyoBluetoothManager(**kwargs)


# Example usage function
async def example_usage():
    """Example of how to use the uMyo Bluetooth module."""
    print("🔗 uMyo Bluetooth Example")
    
    # Method 1: Quick connection
    manager = await quick_connect()
    if manager:
        print("✅ Quick connection successful!")
        
        # Monitor data for 10 seconds
        start_time = time.time()
        while time.time() - start_time < 10:
            devices = umyo_parser.umyo_get_list()
            if devices:
                device = devices[0]
                print(f"EMG: {device.data_array[-1] if device.data_array else 0}")
            await asyncio.sleep(1)
        
        await manager.disconnect()
    
    # Method 2: Manual connection
    manager = create_manager(auto_reconnect=True)
    devices = await manager.discover_devices()
    if devices:
        await manager.connect_to_device(devices[0])
        await manager.start_streaming()
        # ... use the connection
        await manager.disconnect()


async def test_bluetooth_connection():
    """Test Bluetooth connection functionality."""
    print("🔋 uMyo Bluetooth Connection Test")
    print("=" * 40)
    
    manager = uMyoBluetoothManager(auto_reconnect=True)
    
    try:
        # Phase 1: Discovery and Connection
        print("🔍 Discovering and connecting to uMyo device...")
        connected = await manager.discover_and_connect(timeout=15.0)
        
        if not connected:
            print("❌ No devices found or connection failed")
            print("\n💡 Troubleshooting:")
            print("   • Ensure device is powered on and in pairing mode")
            print("   • Check Bluetooth is enabled")
            print("   • Move closer to device")
            return
        
        print("✅ Connected successfully!")
        
        # Phase 2: Device Information
        print("\n📋 Reading device information...")
        device_info = await manager.read_device_info()
        for key, value in device_info.__dict__.items():
            if value:
                print(f"   {key.replace('_', ' ').title()}: {value}")
        
        # Phase 3: Data Streaming Test
        print("\n📡 Starting data streaming...")
        streaming = await manager.start_streaming()
        
        if not streaming:
            print("❌ Failed to start streaming")
            return
        
        print("✅ Streaming started successfully!")
        
        # Phase 4: Monitor data for 30 seconds
        print("\n📊 Monitoring data (30 seconds)...")
        print("Time | Device ID | EMG | Battery | RSSI")
        print("-" * 40)
        
        start_time = time.time()
        data_count = 0
        
        while time.time() - start_time < 30.0:
            devices = umyo_parser.umyo_get_list()
            
            if devices:
                device = devices[0]
                elapsed = int(time.time() - start_time)
                emg = device.data_array[-1] if device.data_array else 0
                print(f"{elapsed:2d}s  | {device.unit_id:08X} | {emg:4d} | {device.batt:4d}mV | {device.rssi:4d}")
                data_count += 1
            
            await asyncio.sleep(1.0)
        
        print("-" * 40)
        
        # Results
        if data_count > 0:
            print(f"✅ Test PASSED - Received data for {data_count} seconds")
            print(f"   Data rate: {data_count/30*100:.1f}%")
        else:
            print("⚠️  Connection OK but no data received")
        
    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test error: {e}")
    finally:
        print("\n🧹 Cleaning up...")
        await manager.disconnect()
        print("✅ Test complete!")


if __name__ == "__main__":
    """Run the Bluetooth connection test."""
    print("🔋 uMyo Bluetooth Module")
    print("Direct BLE connectivity for uMyo devices")
    print()
    print("Requirements:")
    print("  • uMyo device with Bluetooth enabled")
    print("  • Device in pairing mode")
    print("  • Bluetooth enabled on computer")
    print("  • 'bleak' library installed")
    print()
    input("Press Enter to start test...")
    
    asyncio.run(test_bluetooth_connection())
