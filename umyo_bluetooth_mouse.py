"""uMyo Bluetooth Mouse Control

This script provides gesture-based mouse control using uMyo devices connected
via Bluetooth instead of the USB dongle. It maintains the same functionality
as umyo_mouse.py but uses direct Bluetooth connectivity.

Features:
    - Direct Bluetooth connection to uMyo devices
    - EMG-based mouse clicking
    - 3D orientation-based cursor movement
    - Scroll control via wrist rotation
    - Calibration system for personalized control
    - Real-time visual feedback

Requirements:
    pip install bleak pygame pyautogui

Usage:
    python umyo_bluetooth_mouse.py

Controls:
    - Move arm to control cursor position
    - Contract muscle to click
    - Rotate wrist to scroll
    - Press 'ESC' to exit
    - Press 'C' to recalibrate

Author: uMyo Development Team
"""

import asyncio
import pygame
import pyautogui
import math
import time
from typing import Optional

import umyo_parser
import quat_math
import display_mouse
from umyo_bluetooth import uMyoBluetoothManager


class uMyoBluetoothMouse:
    """Bluetooth-enabled mouse control using uMyo sensors."""
    
    def __init__(self):
        """Initialize the Bluetooth mouse controller."""
        self.bluetooth_manager = uMyoBluetoothManager()
        self.running = False
        self.calibrated = False
        
        # Mouse control parameters
        self.center_quat = [1, 0, 0, 0]  # Neutral orientation
        self.sensitivity = 2.0
        self.click_threshold = 100
        self.scroll_sensitivity = 0.1
        
        # Calibration data
        self.x_axis_quat = [1, 0, 0, 0]
        self.y_axis_quat = [1, 0, 0, 0]
        self.z_axis_quat = [1, 0, 0, 0]
        
        # Screen dimensions
        self.screen_width, self.screen_height = pyautogui.size()
        
        # Display initialization
        pygame.init()
        self.display_width = 250
        self.display_height = 200
        self.screen = pygame.display.set_mode((self.display_width, self.display_height))
        pygame.display.set_caption("uMyo Bluetooth Mouse Control")
        
        # Disable pygame mouse failsafe (optional)
        pyautogui.FAILSAFE = False
        
        print("🔋 uMyo Bluetooth Mouse Control Initialized")
    
    async def connect_device(self) -> bool:
        """Connect to uMyo device via Bluetooth.
        
        Returns:
            bool: True if connection successful
        """
        print("🔍 Searching for uMyo devices...")
        connected = await self.bluetooth_manager.discover_and_connect(timeout=15.0)
        
        if connected:
            print("✅ Connected to uMyo device")
            streaming = await self.bluetooth_manager.start_streaming()
            if streaming:
                print("📡 Data streaming started")
                return True
            else:
                print("❌ Failed to start data streaming")
                return False
        else:
            print("❌ Failed to connect to uMyo device")
            return False
    
    async def calibrate(self):
        """Perform mouse control calibration."""
        print("\n🎯 Starting calibration process...")
        print("Follow the on-screen instructions")
        
        stages = [
            {"name": "Center Position", "instruction": "Hold arm in neutral position", "duration": 3},
            {"name": "X-Axis (Right)", "instruction": "Move arm to the right", "duration": 3},
            {"name": "Y-Axis (Up)", "instruction": "Move arm upward", "duration": 3},
            {"name": "Z-Axis (Twist)", "instruction": "Rotate wrist clockwise", "duration": 3},
            {"name": "Click Test", "instruction": "Contract muscle to test clicking", "duration": 3}
        ]
        
        for i, stage in enumerate(stages):
            print(f"\n📍 Stage {i+1}/5: {stage['name']}")
            print(f"   {stage['instruction']}")
            
            # Wait for stage completion
            start_time = time.time()
            while time.time() - start_time < stage['duration']:
                # Update display
                progress = (time.time() - start_time) / stage['duration']
                display_mouse.draw_calibration_stage(
                    self.screen, stage['name'], stage['instruction'], progress
                )
                pygame.display.flip()
                
                # Process events
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        return False
                
                await asyncio.sleep(0.1)
            
            # Capture calibration data
            devices = umyo_parser.umyo_get_list()
            if devices:
                device = devices[0]
                
                if i == 0:  # Center position
                    self.center_quat = device.Qsg.copy()
                elif i == 1:  # X-axis
                    self.x_axis_quat = device.Qsg.copy()
                elif i == 2:  # Y-axis
                    self.y_axis_quat = device.Qsg.copy()
                elif i == 3:  # Z-axis (scroll)
                    self.z_axis_quat = device.Qsg.copy()
                elif i == 4:  # Click threshold
                    if device.data_array:
                        self.click_threshold = max(50, device.data_array[-1] * 0.7)
                
                print(f"   ✅ Captured: {stage['name']}")
            else:
                print(f"   ⚠️  No data available for {stage['name']}")
        
        self.calibrated = True
        print("\n🎉 Calibration complete!")
        print(f"   Click threshold: {self.click_threshold}")
        print("   You can now use mouse control")
        return True
    
    def process_mouse_control(self):
        """Process current sensor data for mouse control."""
        devices = umyo_parser.umyo_get_list()
        if not devices or not self.calibrated:
            return
        
        device = devices[0]
        
        # Calculate cursor movement based on orientation
        if device.Qsg != [0, 0, 0, 0]:
            # Calculate relative rotation from center position
            center_conj = quat_math.q_make_conj(quat_math.sQ(*self.center_quat))
            current_quat = quat_math.sQ(*device.Qsg)
            relative_quat = quat_math.q_mult(current_quat, center_conj)
            
            # Map quaternion to screen coordinates
            # This is a simplified mapping - you may need to adjust based on your device orientation
            mouse_x = self.screen_width / 2 + (relative_quat.y * self.sensitivity * self.screen_width)
            mouse_y = self.screen_height / 2 - (relative_quat.z * self.sensitivity * self.screen_height)
            
            # Constrain to screen bounds
            mouse_x = max(0, min(self.screen_width - 1, mouse_x))
            mouse_y = max(0, min(self.screen_height - 1, mouse_y))
            
            # Move mouse cursor
            pyautogui.moveTo(mouse_x, mouse_y)
            
            # Handle clicking based on EMG signal
            if device.data_array:
                emg_value = device.data_array[-1]
                if emg_value > self.click_threshold:
                    pyautogui.click()
                    time.sleep(0.2)  # Prevent multiple clicks
            
            # Handle scrolling based on wrist rotation (simplified)
            scroll_amount = relative_quat.x * self.scroll_sensitivity
            if abs(scroll_amount) > 0.1:
                pyautogui.scroll(int(scroll_amount * 10))
    
    async def run(self):
        """Main control loop."""
        print("\n🎮 Starting mouse control...")
        print("Controls:")
        print("  - Move arm to control cursor")
        print("  - Contract muscle to click")
        print("  - Rotate wrist to scroll")
        print("  - Press 'C' to recalibrate")
        print("  - Press 'ESC' to exit")
        
        self.running = True
        clock = pygame.time.Clock()
        
        while self.running:
            # Handle pygame events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.running = False
                    elif event.key == pygame.K_c:
                        await self.calibrate()
            
            # Process mouse control
            self.process_mouse_control()
            
            # Update display
            devices = umyo_parser.umyo_get_list()
            if devices:
                device = devices[0]
                display_mouse.draw_mouse_control_status(
                    self.screen,
                    device,
                    self.calibrated,
                    self.click_threshold
                )
            else:
                # Draw "waiting for data" message
                self.screen.fill((0, 0, 0))
                font = pygame.font.Font(None, 24)
                text = font.render("Waiting for data...", True, (255, 255, 255))
                text_rect = text.get_rect(center=(self.display_width//2, self.display_height//2))
                self.screen.blit(text, text_rect)
            
            pygame.display.flip()
            clock.tick(60)  # 60 FPS
            await asyncio.sleep(0.01)  # Small async delay
    
    async def cleanup(self):
        """Clean up resources."""
        print("\n🧹 Cleaning up...")
        await self.bluetooth_manager.disconnect()
        pygame.quit()
        print("👋 Goodbye!")


async def main():
    """Main function."""
    print("🔋 uMyo Bluetooth Mouse Control")
    print("=" * 40)
    print("Make sure your uMyo device is in pairing mode!")
    print()
    
    mouse_controller = uMyoBluetoothMouse()
    
    try:
        # Connect to device
        connected = await mouse_controller.connect_device()
        if not connected:
            print("❌ Failed to connect to uMyo device")
            return
        
        # Wait a moment for data to start flowing
        print("⏳ Waiting for initial data...")
        await asyncio.sleep(2)
        
        # Perform calibration
        calibrated = await mouse_controller.calibrate()
        if not calibrated:
            print("❌ Calibration failed or cancelled")
            return
        
        # Start mouse control
        await mouse_controller.run()
    
    except KeyboardInterrupt:
        print("\n⏹️  Interrupted by user")
    
    except Exception as e:
        print(f"❌ Error: {e}")
    
    finally:
        await mouse_controller.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
