
# EMG-Controlled Click Interface - Main Implementation
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import umyo_parser
from pynput.mouse import Controller, Button
import time
from serial.tools import list_ports
import serial
import sys

# Initialize pynput mouse controller
mouse_controller = Controller()

# EMG signal processing variables
ch0 = 0
ch1 = 0
savg0 = 0
savg1 = 0

# Click control variables
clicked = 0
mouse_click_active = 0

# Configurable thresholds
CLICK_THRESHOLD = 400  # EMG activation threshold for clicking
SMOOTHING_FACTOR = 0.9  # Exponential smoothing factor (0-1, higher = more smoothing)

print("EMG Click Controller Starting...")
print("This system will detect EMG activation and trigger left mouse clicks")
print("="*50)

# Serial port setup
port = list(list_ports.comports())
print("Available ports:")
for p in port:
    print(p.device)
    device = p.device
print("="*30)

# Initialize serial connection
ser = serial.Serial(port=device,
                    baudrate=921600,
                    parity=serial.PARITY_NONE,
                    stopbits=1,
                    bytesize=8,
                    timeout=0)

print("Connected to: " + ser.portstr)
print("EMG Click Controller Ready!")
print("Activate EMG to trigger left mouse clicks")
print("="*50)

# Main processing loop
parse_unproc_cnt = 0

while True:
    try:
        cnt = ser.in_waiting
        if cnt > 0:
            # Read and parse data from uMyo device
            data = ser.read(cnt)
            parse_unproc_cnt = umyo_parser.umyo_parse_preprocessor(data)
            umyos = umyo_parser.umyo_get_list()
            
            if len(umyos) < 1:
                continue
            
            # Process EMG signals with exponential smoothing
            # Using device_spectr channels 2 and 3 for EMG data
            raw_emg = umyos[0].device_spectr[2] + umyos[0].device_spectr[3]
            
            # Apply exponential smoothing to reduce noise
            ch0 = ch0 * SMOOTHING_FACTOR + (1 - SMOOTHING_FACTOR) * raw_emg
            savg0 = savg0 * SMOOTHING_FACTOR + (1 - SMOOTHING_FACTOR) * ch0
            
            # Click detection logic
            if ch0 > CLICK_THRESHOLD:
                mouse_click_active = 1
            else:
                mouse_click_active = 0
                clicked = 0  # Reset click state when EMG falls below threshold
            
            # Execute click when EMG is active and we haven't already clicked
            if mouse_click_active > 0 and clicked == 0:
                mouse_controller.click(Button.left)
                clicked = 1
                print(f"Click! EMG level: {ch0:.1f}")
            
            # Optional: Print EMG levels for debugging (uncomment next line)
            # print(f"EMG: {ch0:.1f}, Threshold: {CLICK_THRESHOLD}, Active: {mouse_click_active}")
            
    except KeyboardInterrupt:
        print("\nShutting down EMG Click Controller...")
        ser.close()
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}")
        continue