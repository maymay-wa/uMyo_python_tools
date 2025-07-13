# uMyo Python Tools - Optimization Analysis

This document outlines optimization opportunities across the uMyo Python tools repository, categorizing improvements by complexity and potential impact.

## Executive Summary

The codebase shows several patterns that could benefit from optimization, ranging from algorithmic improvements (Big O complexity reductions) to Python-specific optimizations and code quality improvements. Key areas include:

- **Critical Performance Issues**: Inefficient data structure operations in real-time loops
- **Memory Management**: Suboptimal buffer management and memory allocation
- **Code Duplication**: Repeated serial port discovery patterns
- **Python-Specific Improvements**: Non-Pythonic code patterns and missing optimizations

## 🔴 Critical Performance Issues (Big O Improvements)

### 1. Linear Search in Device Management (`umyo_parser.py`)

**Location**: `id2idx()` function, lines ~150-180
**Current Complexity**: O(n) for each device lookup
**Issue**: Linear search through active devices for every packet

```python
# Current inefficient approach
for u in range(cnt):
    if (umyo_list[u].unit_id == uid):
        return u
```

**Optimization**: Use dictionary/hash map for O(1) device lookups
```python
# Proposed optimization
device_id_to_index = {}  # Global lookup table
def id2idx(uid):
    if uid in device_id_to_index:
        return device_id_to_index[uid]
    # Create new device logic here
```

**Impact**: High - This function is called for every incoming data packet in real-time

### 2. Inefficient Buffer Trimming (`display_stuff.py`)

**Location**: `plot_prepare()` function, lines 570-578
**Current Complexity**: O(n) list slicing operations in real-time loop
**Issue**: Multiple list slicing operations per device per frame

```python
# Current inefficient approach
plot_emg[d] = plot_emg[d][-plot_len:]
plot_spg[d] = plot_spg[d][-spg_len * 4:]
# ... more slicing operations
```

**Optimization**: Use circular buffers or deque with maxlen
```python
from collections import deque
# During initialization
plot_emg[d] = deque(maxlen=plot_len)
plot_spg[d] = deque(maxlen=spg_len * 4)
# Automatic trimming, O(1) append operations
```

**Impact**: High - Called continuously in real-time display loop

### 3. Redundant Device Cleanup Loop (`umyo_parser.py`)

**Location**: `id2idx()` function, device cleanup section
**Current Complexity**: O(n²) in worst case due to deletion during iteration
**Issue**: Deleting from list while iterating requires reindexing

```python
# Current problematic approach
while (u < cnt):
    if (unseen_cnt[u] > 1000 and umyo_list[u].unit_id != uid):
        del umyo_list[u]
        del unseen_cnt[u]
        cnt -= 1
    else:
        u += 1
```

**Optimization**: Build new lists or mark for deletion
```python
# Proposed optimization
active_devices = []
active_counts = []
for i, device in enumerate(umyo_list):
    if unseen_cnt[i] <= 1000 or device.unit_id == uid:
        active_devices.append(device)
        active_counts.append(unseen_cnt[i])
umyo_list = active_devices
unseen_cnt = active_counts
```

**Impact**: Medium - Cleanup runs less frequently but blocks processing

## 🟡 Memory Management Issues

### 4. Excessive List Growth (`parse_plot_data.py`)

**Location**: `plot_prepare()` function, line 145
**Issue**: Unbounded list growth before trimming

```python
plot_ys.append(val)  # Grows indefinitely
# ... later
plot_ys = plot_ys[-1000:]  # Expensive slice operation
```

**Optimization**: Use circular buffer from start
```python
from collections import deque
plot_ys = deque(maxlen=1000)  # Fixed size, automatic cleanup
```

### 5. Inefficient Color Mapping (`display_stuff.py`)

**Location**: Multiple functions using repeated if-elif chains
**Issue**: O(n) lookup for device colors

```python
# Current approach - O(n) lookup
def num_to_color(n):
    if (n == 0): return 0, 200, 0
    if (n == 1): return 0, 100, 200
    # ... many more conditions
```

**Optimization**: Use lookup table
```python
# O(1) lookup
DEVICE_COLORS = {
    0: (0, 200, 0),
    1: (0, 100, 200),
    2: (150, 150, 0),
    # ... etc
}
def num_to_color(n):
    return DEVICE_COLORS.get(n, (100, 100, 100))
```

### 6. Multiple Data Structure Appends (`display_stuff.py`)

**Location**: `plot_prepare()` function, quaternion handling
**Issue**: Four separate append operations for quaternion data

```python
# Current approach - 4 separate appends
plot_Q[d].append(devices[d].Qsg[0])
plot_Q[d].append(devices[d].Qsg[1])
plot_Q[d].append(devices[d].Qsg[2])
plot_Q[d].append(devices[d].Qsg[3])
```

**Optimization**: Single extend operation
```python
plot_Q[d].extend(devices[d].Qsg)  # Single operation
```

## 🟠 Code Duplication and Maintenance Issues

### 7. Repeated Serial Port Discovery Pattern

**Locations**: Multiple files (serial_test.py, parse_plot_data.py, umyo_3ch_detector.py, etc.)
**Issue**: Same serial port discovery code repeated across 8+ files

**Current Pattern**:
```python
from serial.tools import list_ports
port = list(list_ports.comports())
print("available ports:")
for p in port:
    print(p.device)
    device = p.device
```

**Optimization**: Create shared utility function
```python
# In utils.py or umyo_serial.py
def discover_serial_port():
    """Discover and return the first available serial port."""
    ports = list_ports.comports()
    if not ports:
        raise RuntimeError("No serial ports found")
    
    print("Available ports:")
    for port in ports:
        print(f"  {port.device}")
    
    return ports[0].device

# Usage in all files
from umyo_serial import discover_serial_port
device = discover_serial_port()
```

### 8. Redundant Serial Configuration

**Issue**: Same serial configuration repeated across files

**Optimization**: Centralized configuration
```python
# In umyo_serial.py
def create_umyo_serial(port):
    """Create standardized uMyo serial connection."""
    return serial.Serial(
        port=port,
        baudrate=921600,
        parity=serial.PARITY_NONE,
        stopbits=1,
        bytesize=8,
        timeout=0
    )
```

## 🔵 Python-Specific Optimizations

### 9. Non-Pythonic Loop Patterns

**Location**: Multiple files using C-style loops
**Issue**: Using `while(1):` instead of Python conventions

```python
# Current C-style
while (1):
    # processing
```

**Optimization**: Python conventions
```python
# More Pythonic
while True:
    # processing
```

### 10. Inefficient String Concatenation

**Location**: Various print statements and logging
**Issue**: Using `+` for string concatenation

```python
# Current approach
print("conn: " + ser.portstr)
```

**Optimization**: Use f-strings (Python 3.6+)
```python
# More efficient and readable
print(f"conn: {ser.portstr}")
```

### 11. Manual Index Management

**Location**: Multiple files using manual range/len combinations
**Issue**: Verbose iteration patterns

```python
# Current verbose approach
for x in range(devices[0].data_count):
    val = devices[0].data_array[x]
```

**Optimization**: Direct iteration or enumerate
```python
# More Pythonic
for val in devices[0].data_array[:devices[0].data_count]:
    # process val
```

## 🟢 Code Quality and Maintainability

### 12. Magic Numbers

**Issue**: Hard-coded values throughout codebase
**Examples**:
- Baud rate: 921600 (repeated 10+ times)
- Buffer sizes: 1000, 2000, 200
- Thresholds: 1000 for device cleanup

**Optimization**: Define constants
```python
# config.py
UMYO_BAUD_RATE = 921600
PLOT_BUFFER_SIZE = 2000
DEVICE_CLEANUP_THRESHOLD = 1000
```

### 13. Error Handling

**Issue**: Limited error handling in serial operations
**Current**: Direct operations without try/catch

**Optimization**: Add proper error handling
```python
try:
    ser = serial.Serial(port=device, baudrate=UMYO_BAUD_RATE, ...)
except serial.SerialException as e:
    logger.error(f"Failed to open serial port {device}: {e}")
    sys.exit(1)
```

### 14. Resource Management

**Issue**: Serial ports and pygame resources not properly closed
**Optimization**: Use context managers

```python
# Proper resource management
with serial.Serial(port=device, ...) as ser:
    # processing
    pass  # Automatically closed
```

## 🟪 Performance Monitoring Opportunities

### 15. Add Profiling Capabilities

**Optimization**: Add optional performance monitoring
```python
import cProfile
import time

class PerformanceMonitor:
    def __init__(self, enabled=False):
        self.enabled = enabled
        self.timings = {}
    
    def time_function(self, func_name):
        if not self.enabled:
            return lambda f: f
        
        def decorator(func):
            def wrapper(*args, **kwargs):
                start = time.perf_counter()
                result = func(*args, **kwargs)
                end = time.perf_counter()
                self.timings[func_name] = end - start
                return result
            return wrapper
        return decorator
```

## EMG Mouse Control Specific Optimizations (`umyo_mouse.py`)

### 16. Redundant Quaternion Operations in Real-time Loop

**Location**: Main processing loop, lines ~175-195
**Current Complexity**: O(1) but computationally expensive operations repeated unnecessarily
**Issue**: Quaternion creation and normalization happening every loop iteration

```python
# Current inefficient approach - multiple quaternion operations per frame
zero_Q = quat_math.sQ(umyos[0].Qsg[0], umyos[0].Qsg[1], umyos[0].Qsg[2], umyos[0].Qsg[3])
zero_Q = quat_math.q_renorm(zero_Q)
cur_Q = quat_math.sQ(umyos[0].Qsg[0], umyos[0].Qsg[1], umyos[0].Qsg[2], umyos[0].Qsg[3])
cur_Q = quat_math.q_renorm(cur_Q)
zq_inv = quat_math.q_make_conj(zero_Q)
diff_Q = quat_math.q_mult(cur_Q, zq_inv)
```

**Optimization**: Cache quaternion operations and use direct data access
```python
# More efficient approach
if need_zero_update:
    zero_Q = quat_math.q_renorm(quat_math.sQ(*umyos[0].Qsg))
    zero_Q_inv = quat_math.q_make_conj(zero_Q)  # Cache inverse
    need_zero_update = False

cur_Q = quat_math.q_renorm(quat_math.sQ(*umyos[0].Qsg))
diff_Q = quat_math.q_mult(cur_Q, zero_Q_inv)  # Use cached inverse
```

**Impact**: Medium - Reduces computational overhead in real-time mouse control

### 17. Wasteful Quaternion-to-Euler Conversion

**Location**: Lines ~200-210
**Issue**: Computing complex quaternion rotations then discarding them for direct Euler angles

```python
# Current wasteful approach - complex quaternion math then overwritten
qV = quat_math.sV(diff_Q.x, diff_Q.y, diff_Q.z)
ww = diff_Q.w
if (diff_Q.w > 1):
    ww = 1
qA = math.acos(ww)
dx = qA * quat_math.v_dot(rot_X, qV)
dy = qA * quat_math.v_dot(rot_Y, qV)
dr = qA * quat_math.v_dot(rot_Z, qV)
# Then immediately overwritten:
dx = umyos[0].yaw
dy = umyos[0].pitch
dr = umyos[0].roll
```

**Optimization**: Use Euler angles directly, remove unused quaternion calculations
```python
# Direct approach - use what's actually needed
dx = umyos[0].yaw
dy = umyos[0].pitch
dr = umyos[0].roll
# Remove all the unused quaternion calculations above
```

**Impact**: High - Eliminates ~15 lines of complex math operations per frame

### 18. Inefficient Calibration Range Checking

**Location**: Calibration logic, lines ~290-320
**Issue**: Multiple nested if statements with repeated range calculations

```python
# Current approach - repeated range checking
if (calibrate_stage == 0 and calibrate_progress > 60 and calibrate_progress < 70):
    need_zero_update = 1
if (calibrate_stage == 1 and calibrate_progress > 80 and calibrate_progress < 90):
    rot_X = quat_math.v_renorm(qV)
# ... many more similar patterns
```

**Optimization**: Use lookup table or state machine
```python
# More efficient approach
CALIBRATION_ACTIONS = {
    (0, 60, 70): lambda: setattr(sys.modules[__name__], 'need_zero_update', 1),
    (1, 80, 90): lambda: setattr(sys.modules[__name__], 'rot_X', quat_math.v_renorm(qV)),
    (3, 80, 90): lambda: setattr(sys.modules[__name__], 'rot_Y', quat_math.v_renorm(qV)),
    # ... etc
}

for (stage, min_prog, max_prog), action in CALIBRATION_ACTIONS.items():
    if calibrate_stage == stage and min_prog < calibrate_progress < max_prog:
        action()
        break
```

**Impact**: Medium - Improves calibration responsiveness and code maintainability

### 19. Excessive Print Statements in Real-time Loop

**Location**: Lines ~235, 262
**Issue**: Print statements in real-time control loop causing I/O blocking

```python
# Current approach - prints in real-time loop
print(savg0, ch1)
print(savg0, mouse_sticky_move, mouse_sticky_state)
```

**Optimization**: Use conditional logging or remove debug prints
```python
# Better approach with conditional debugging
DEBUG_MOUSE = False  # Configuration flag

if DEBUG_MOUSE:
    print(f"EMG: {savg0:.1f}, CH1: {ch1:.1f}")
    print(f"Move: {mouse_sticky_move}, State: {mouse_sticky_state}")
```

**Impact**: Medium - Reduces I/O overhead in real-time processing

### 20. Magic Number Proliferation

**Location**: Throughout the file
**Issue**: Many hard-coded thresholds and scaling factors

```python
# Current approach - magic numbers everywhere
ch0 = ch0 * 0.9 + 0.1 * (umyos[0].device_spectr[2] + umyos[0].device_spectr[3])
savg0 = savg0 * 0.9 + 0.1 * ch0
d_scale = 0.1
ddx = -ddx * d_scale * 8
ddy = ddy * d_scale * 8
```

**Optimization**: Define named constants
```python
# Better approach with named constants
EMG_SMOOTHING_FACTOR = 0.9
EMG_NEW_DATA_WEIGHT = 0.1
MOUSE_SCALE_FACTOR = 0.1
MOUSE_SENSITIVITY_X = 8
MOUSE_SENSITIVITY_Y = 8

ch0 = ch0 * EMG_SMOOTHING_FACTOR + EMG_NEW_DATA_WEIGHT * (
    umyos[0].device_spectr[2] + umyos[0].device_spectr[3])
savg0 = savg0 * EMG_SMOOTHING_FACTOR + EMG_NEW_DATA_WEIGHT * ch0
ddx = -ddx * MOUSE_SCALE_FACTOR * MOUSE_SENSITIVITY_X
ddy = ddy * MOUSE_SCALE_FACTOR * MOUSE_SENSITIVITY_Y
```

### 21. Commented Dead Code

**Location**: Multiple locations throughout file
**Issue**: Large blocks of commented code cluttering the implementation

```python
# Dead code taking up space and reducing readability
#        mouse.is_pressed("left")
#        print(zero_Q.w, zero_Q.x, zero_Q.y, zero_Q.z)
#        if(act_ch0 > THR0_H): mouse_move_active = 1
#        if(act_ch0 > THR0_H * 1.2): mouse_scroll_active = 1
#                mouse.wheel(round(ddr))
#                mouse.move(ddx*math.sqrt(math.fabs(ddx)), -ddy*math.sqrt(math.fabs(ddy)), False)
#                pyautogui.mouseDown()
#                mouse.click("left")
```

**Optimization**: Remove commented code, use version control for history
```python
# Clean implementation without dead code
# If alternative implementations needed, use feature flags or separate functions
```

**Impact**: Low computational, High maintainability - Improves code readability

### 22. Inefficient Movement Threshold Checking

**Location**: Lines ~270-280
**Issue**: Repeated threshold calculations and complex conditional logic

```python
# Current approach - repeated calculations
if (mouse_scroll_active > 0 and (ddr > 1 or ddr < -1)):
    pyautogui.scroll(round(-ddr))
if (mouse_move_active > 0 and (ddx > 1 or ddx < -1 or ddy > 1 or ddy < -1)):
    pyautogui.move(ddx, -ddy)
```

**Optimization**: Pre-calculate thresholds and combine conditions
```python
# More efficient approach
MOVEMENT_THRESHOLD = 1
SCROLL_THRESHOLD = 1

movement_magnitude = abs(ddx) + abs(ddy)  # Manhattan distance
scroll_magnitude = abs(ddr)

if mouse_scroll_active and scroll_magnitude > SCROLL_THRESHOLD:
    pyautogui.scroll(round(-ddr))
    
if mouse_move_active and movement_magnitude > MOVEMENT_THRESHOLD:
    pyautogui.move(ddx, -ddy)
```

## Performance Monitoring Opportunities

### Summary of Mouse Control Optimizations

The `umyo_mouse.py` file represents a critical real-time control system where performance optimizations have direct impact on user experience, especially for accessibility applications. Key findings:

**🔴 Critical Issues**:
- **Wasteful quaternion calculations**: Complex math operations computed then immediately discarded
- **Redundant quaternion operations**: Creating and normalizing quaternions every frame unnecessarily

**🟡 Medium Impact Issues**:
- **Debug prints in real-time loop**: I/O operations blocking time-critical mouse control
- **Inefficient calibration logic**: Nested conditionals with repeated range checking
- **Magic number proliferation**: Hard-coded values making the system difficult to tune

**🟢 Code Quality Issues**:
- **Dead code**: Extensive commented-out code reducing readability
- **Movement threshold inefficiency**: Repeated calculations for movement detection

**Performance Impact for Mouse Control**:
- **Latency Critical**: Mouse control requires <10ms response time for smooth operation
- **Accessibility Important**: For users with motor impairments, any lag significantly impacts usability
- **Real-time Requirements**: EMG signals must be processed and translated to mouse movements instantly

**Recommended Priority for Mouse Optimizations**:
1. Remove wasteful quaternion calculations (highest impact)
2. Cache quaternion operations and eliminate redundancy
3. Remove debug prints from real-time loop
4. Simplify calibration range checking
5. Define constants for all magic numbers
6. Clean up dead code
