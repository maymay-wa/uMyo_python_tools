"""Simple uMyo Bluetooth Connection Example

This script demonstrates how to connect to a uMyo device via Bluetooth
and receive real-time EMG data without using the USB dongle.

Requirements:
    pip install bleak

Usage:
    python umyo_bluetooth_example.py

Make sure your uMyo device is in pairing/discoverable mode before running.
"""

import asyncio
import time
import umyo_parser
from umyo_bluetooth import uMyoBluetoothManager, quick_connect


async def simple_demo():
    """Simple connection demo using quick_connect."""
    print("🔋 Simple uMyo Bluetooth Demo")
    print("=" * 35)
    
    # Quick connection
    print("🔍 Connecting to uMyo device...")
    manager = await quick_connect()
    
    if not manager:
        print("❌ Connection failed")
        return
    
    print("✅ Connected and streaming!")
    print("\n📊 EMG Data (15 seconds):")
    
    # Monitor data
    start_time = time.time()
    while time.time() - start_time < 15:
        devices = umyo_parser.umyo_get_list()
        if devices:
            device = devices[0]
            elapsed = int(time.time() - start_time)
            emg = device.data_array[-1] if device.data_array else 0
            print(f"{elapsed:2d}s: EMG = {emg:4d}")
        await asyncio.sleep(1)
    
    await manager.disconnect()
    print("✅ Demo complete!")


async def main():
    """Main function demonstrating Bluetooth connectivity."""
    
    print("🔋 uMyo Bluetooth Connection Example")
    print("=" * 50)
    print("Make sure your uMyo device is in pairing mode!")
    print()
    
    # Create Bluetooth manager
    manager = uMyoBluetoothManager(auto_reconnect=True)
    
    try:
        # Discover and connect
        print("🔍 Searching for uMyo devices...")
        connected = await manager.discover_and_connect(timeout=15.0)
        
        if not connected:
            print("❌ Failed to find or connect to uMyo device")
            print("   - Ensure device is powered on")
            print("   - Ensure device is in pairing mode") 
            print("   - Check Bluetooth is enabled on your computer")
            return
        
        print("✅ Successfully connected to uMyo device!")
        
        # Read device info
        print("\n📋 Device Information:")
        device_info = await manager.read_device_info()
        print(f"   Name: {device_info.name}")
        print(f"   Manufacturer: {device_info.manufacturer}")
        print(f"   Firmware: {device_info.firmware}")
        if device_info.battery_percent:
            print(f"   Battery: {device_info.battery_percent}%")
        
        # Start receiving data
        print("\n📡 Starting data stream...")
        streaming = await manager.start_streaming()
        
        if not streaming:
            print("❌ Failed to start data streaming")
            print("   Device may not support streaming or wrong firmware")
            return
        
        print("✅ Data streaming started!")
        print()
        
        # Monitor real-time EMG data for 30 seconds
        print("📊 Real-time EMG Data (30 seconds):")
        print("Time | Device ID | EMG   | Battery | RSSI | Quaternion")
        print("-" * 60)
        
        start_time = time.time()
        data_count = 0
        
        while time.time() - start_time < 30.0:
            # Get parsed device data
            devices = umyo_parser.umyo_get_list()
            
            if devices:
                device = devices[0]
                elapsed = int(time.time() - start_time)
                emg_value = device.data_array[-1] if device.data_array else 0
                quat = f"({device.Qsg[0]:.2f},{device.Qsg[1]:.2f},{device.Qsg[2]:.2f},{device.Qsg[3]:.2f})"
                
                print(f"{elapsed:2d}s  | {device.unit_id:08X} | {emg_value:5d} | "
                      f"{device.batt:4d}mV | {device.rssi:4d} | {quat}")
                data_count += 1
            else:
                elapsed = int(time.time() - start_time)
                print(f"{elapsed:2d}s  | Waiting for data...")
            
            await asyncio.sleep(1.0)
        
        print("-" * 60)
        
        # Show results
        print(f"\n📈 Results:")
        if data_count > 0:
            print(f"✅ Successfully received data for {data_count} seconds")
            print(f"   Data reception rate: {data_count/30*100:.1f}%")
            print("   Bluetooth connection is working properly!")
            
            # Show connection statistics
            conn_info = manager.get_connection_info()
            stats = conn_info.get('stats', {})
            if stats:
                print(f"   Total packets: {stats.get('total_packets', 0)}")
                print(f"   Total bytes: {stats.get('total_bytes', 0)}")
        else:
            print("⚠️  Connected but no data received")
            print("   Device may need different firmware or configuration")
    
    except KeyboardInterrupt:
        print("\n⏹️  Demo interrupted by user")
    
    except Exception as e:
        print(f"\n❌ Error occurred: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Clean up
        print("\n🧹 Disconnecting from device...")
        await manager.disconnect()
        print("✅ Disconnected successfully!")
        print("\n🎯 Demo complete! Thank you for testing uMyo Bluetooth.")


if __name__ == "__main__":
    """Run the demo."""
    print("Choose demo mode:")
    print("1. Simple demo (quick connect)")
    print("2. Full demo (detailed)")
    
    try:
        choice = input("Enter choice (1 or 2): ").strip()
        if choice == "1":
            asyncio.run(simple_demo())
        else:
            asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️  Interrupted by user")
    except Exception as e:
        print(f"❌ Demo error: {e}")
