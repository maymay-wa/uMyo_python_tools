
# kinda main

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Add parent directory to Python path to import modules from parent folder
import umyo_parser
import display_mouse
# import mouse
from pynput.mouse import Controller, Button, Listener
from pynput.keyboard import Controller as KeyboardController, Key
import quat_math
import math
# import os
import time
from serial.tools import list_ports
import serial
import sys

# Initialize pynput mouse controller
mouse_controller = Controller()
# Initialize pynput keyboard controller
keyboard_controller = KeyboardController()

# TOGGLE: Set to True for up arrow mode, False for click mode
USE_ARROW_MODE = False
# list

port = list(list_ports.comports())
print("available ports:")
for p in port:
    print(p.device)
    device = p.device
print("===")

# read

ser = serial.Serial(port=device,
                    baudrate=921600,
                    parity=serial.PARITY_NONE,
                    stopbits=1,
                    bytesize=8,
                    timeout=0)

print("conn: " + ser.portstr)
last_data_upd = 0
parse_unproc_cnt = 0
ch0 = 0
ch1 = 0
avg0 = 0
savg0 = 0
savg1 = 0
zero_Q = quat_math.sQ(1, 0, 0, 0)
cur_Q = quat_math.sQ(1, 0, 0, 0)
need_zero_update = 1
rot_X = quat_math.sV(1, 0, 0)
rot_Y = quat_math.sV(0, 1, 0)
rot_Z = quat_math.sV(0, 0, 1)
calibrate_requested = 0
calibrate_stage = 0
calibrate_stage_start = 0
calibrate_progress = 0
prev_dx = 0
prev_dy = 0
prev_dr = 0
relaxed_avg0 = 100
active_avg0 = 500000
relaxed_avg1 = 100
active_avg1 = 500000
mouse_move_active = 0
mouse_click_active = 0
clicked = 0
arrow_pressed = 0  # Track if up arrow key was already pressed

THR0_H = 50000
THR0_L = 50000
THR1_H = 50000
THR1_L = 50000

fix_TH0 = 400
fix_TH1 = 400

# Print initial mode information
print("To switch modes, change USE_ARROW_MODE variable at the top of the script")
print("="*40)

# Joystick movement configuration
JOYSTICK_DEADZONE = 50   # Reduced deadzone for better sensitivity
JOYSTICK_SENSITIVITY = 0.3  # Base movement scaling factor
MAX_DISPLACEMENT = 3000  # Maximum expected displacement value for normalization
MIN_MOVEMENT_THRESHOLD = 0.02  # Minimum normalized movement to register (smoother than hard deadzone)

def print_mode_info():
    """Print current mode information."""
    mode_text = "Up Arrow Mode" if USE_ARROW_MODE else "Click Mode"
    print(f"Current mode: {mode_text}")
    print("Mouse control: JOYSTICK MODE - Distance from center controls movement speed")
    if USE_ARROW_MODE:
        print("EMG activation will press UP ARROW key")
    else:
        print("EMG activation will perform MOUSE CLICK")
    print("="*40)

while (1):
    cnt = ser.in_waiting
    if (cnt > 0):
        cnt_corr = parse_unproc_cnt / 200
        data = ser.read(cnt)
        parse_unproc_cnt = umyo_parser.umyo_parse_preprocessor(data)
        umyos = umyo_parser.umyo_get_list()
        if (len(umyos) < 1):
            continue
        if (need_zero_update > 0):
            zero_Q = quat_math.sQ(umyos[0].Qsg[0], umyos[0].Qsg[1], umyos[0].Qsg[2], umyos[0].Qsg[3])
            zero_Q = quat_math.q_renorm(zero_Q)
            need_zero_update = 0
        cur_Q = quat_math.sQ(umyos[0].Qsg[0], umyos[0].Qsg[1], umyos[0].Qsg[2], umyos[0].Qsg[3])
        cur_Q = quat_math.q_renorm(cur_Q)
        zq_inv = quat_math.q_make_conj(zero_Q)
        diff_Q = quat_math.q_mult(cur_Q, zq_inv)
        qV = quat_math.sV(diff_Q.x, diff_Q.y, diff_Q.z)
        ww = diff_Q.w
        if (diff_Q.w > 1):
            ww = 1
        qA = math.acos(ww)
        dx = qA * quat_math.v_dot(rot_X, qV)
        dy = qA * quat_math.v_dot(rot_Y, qV)
        dr = qA * quat_math.v_dot(rot_Z, qV)
        dx = umyos[0].yaw
        dy = umyos[0].pitch
        dr = umyos[0].roll
        
        # Joystick mode: treat current position as distance from center
        # Normalize the values to treat them as joystick displacement from center
        center_yaw = 0  # Center position for yaw
        center_pitch = 0  # Center position for pitch
        
        # Calculate displacement from center
        yaw_displacement = dx - center_yaw
        pitch_displacement = dy - center_pitch
        
        # Calculate the magnitude of the displacement vector for better diagonal handling
        displacement_magnitude = math.sqrt(yaw_displacement**2 + pitch_displacement**2)
        
        # Apply smooth response curve instead of hard deadzone
        if displacement_magnitude < JOYSTICK_DEADZONE:
            # Use exponential fade-in near center for smoother response
            fade_factor = max(0, (displacement_magnitude - JOYSTICK_DEADZONE/2) / (JOYSTICK_DEADZONE/2))
            yaw_displacement *= fade_factor
            pitch_displacement *= fade_factor
        
        # Normalize displacement to -1 to 1 range
        normalized_yaw = max(-1, min(1, yaw_displacement / MAX_DISPLACEMENT))
        normalized_pitch = max(-1, min(1, pitch_displacement / MAX_DISPLACEMENT))
        
        # Calculate normalized magnitude for scaling
        normalized_magnitude = math.sqrt(normalized_yaw**2 + normalized_pitch**2)
        
        # Apply quadratic scaling for more natural feel (slow near center, fast at edges)
        # This makes small movements more precise and large movements faster
        if normalized_magnitude > MIN_MOVEMENT_THRESHOLD:
            # Use quadratic curve with minimum threshold
            scale_factor = normalized_magnitude * normalized_magnitude
            # Apply directional scaling while preserving magnitude relationship
            if normalized_magnitude > 0:
                direction_scale_yaw = normalized_yaw / normalized_magnitude
                direction_scale_pitch = normalized_pitch / normalized_magnitude
                
                # Calculate final movement with enhanced sensitivity
                ddx = -direction_scale_yaw * scale_factor * JOYSTICK_SENSITIVITY * 150
                ddy = direction_scale_pitch * scale_factor * JOYSTICK_SENSITIVITY * 150
            else:
                ddx = 0
                ddy = 0
        else:
            ddx = 0
            ddy = 0
        
        ddr = 0  # Not using roll for mouse movement
        
        prev_dx = dx
        prev_dy = dy
        prev_dr = dr
        ch0 = ch0 * 0.9 + 0.1 * (umyos[0].device_spectr[2] +
                                 umyos[0].device_spectr[3])
        ch1 = ch1 * 0.9 + 0.1 * (umyos[0].device_spectr[2] +
                                 umyos[0].device_spectr[3])
        savg0 = savg0 * 0.9 + 0.1 * ch0
        savg1 = savg1 * 0.9 + 0.1 * ch1
        act_ch0 = savg0 
        has_click = 0
        
        # Direct EMG control - no sticky states
        mouse_move_active = 1

            
        if (ch1 > fix_TH1):
            mouse_click_active = 1
            mouse_move_active = 0
        else:
            mouse_click_active = 0
            clicked = 0
            arrow_pressed = 0  # Reset arrow pressed state when not active
            
        # print(savg0, mouse_move_active, ch1)
        if (calibrate_requested == 0):
            if (mouse_move_active > 0):
                # Joystick mode: move cursor based on displacement from center
                # Only move if there's actual displacement (deadzone already applied above)
                if abs(ddx) > 0 or abs(ddy) > 0:
                    mouse_controller.move(ddx, -ddy)
                    
            if (mouse_click_active > 0):
                # Click mode: perform mouse click
                if (clicked == 0):
                    mouse_controller.click(Button.left)
                    clicked = 1
                    print("Mouse clicked")
                has_click = 1

        scale = 1
        T = 300
        avg0 = avg0 * 0.999 + 0.001 * ch0