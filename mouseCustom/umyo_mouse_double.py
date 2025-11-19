
import sys
import os
# kinda main
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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

# Mouse movement deadzone configuration
MOVEMENT_DEADZONE = 1  # Minimum movement required to trigger cursor movement
MOVEMENT_SENSITIVITY = 1.0  # Movement scaling factor

def print_mode_info():
    """Print current mode information."""
    mode_text = "Up Arrow Mode" if USE_ARROW_MODE else "Click Mode"
    print(f"Current mode: {mode_text}")
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
        ddx = dx - prev_dx
        ddy = dy - prev_dy
        ddr = dr - prev_dr
        if (dy > 2000 and prev_dy < -2000):
            ddy = 0
        if (dy < -2000 and prev_dy > 2000):
            ddy = 0
        prev_dx = dx
        prev_dy = dy
        prev_dr = dr
        d_scale = 0.1
        ddx = -ddx * d_scale * 8
        ddy = ddy * d_scale * 8
        ddr = ddr * d_scale
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
                # Calculate movement magnitude for deadzone check
                movement_magnitude = math.sqrt(ddx * ddx + ddy * ddy)
                
                # Apply deadzone: only move if movement exceeds threshold
                if movement_magnitude > MOVEMENT_DEADZONE:
                    # Scale movement by sensitivity factor
                    scaled_ddx = ddx * MOVEMENT_SENSITIVITY
                    scaled_ddy = ddy * MOVEMENT_SENSITIVITY
                    mouse_controller.move(scaled_ddx, -scaled_ddy)
                    
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