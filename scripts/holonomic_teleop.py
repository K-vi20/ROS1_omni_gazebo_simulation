#!/usr/bin/env python3
"""
Advanced Holonomic Teleop for Mecanum/Omni Wheel Robots
รองรับ 8 ทิศทาง, ปรับความเร็วได้, มีระบบ Safety Timeout
"""
import sys
import tty
import termios
import select
import time
import math
import rospy
from geometry_msgs.msg import Twist

# ═══════════════════════════════════════════════════════════
# CONFIGURATION & SAFETY LIMITS
# ═══════════════════════════════════════════════════════════
MAX_LIN_SPEED = 1.5   # m/s (Hard limit for safety)
MIN_LIN_SPEED = 0.1   # m/s
MAX_ANG_SPEED = 2.0   # rad/s
MIN_ANG_SPEED = 0.2   # rad/s
SPEED_STEP = 0.1      # Increment/Decrement step

LIN_SPEED = 0.3       # Initial linear speed (m/s)
ANG_SPEED = 0.8       # Initial angular speed (rad/s)

KEY_TIMEOUT = 0.15    # Seconds before a key is considered "released" (Safety)
UPDATE_RATE = 20      # Hz (Control loop frequency)

# ═══════════════════════════════════════════════════════════
# UI BANNER
# ═══════════════════════════════════════════════════════════
BANNER = """
╔══════════════════════════════════════════════════════════╗
║       Advanced Holonomic Teleop (Mecanum/Omni)         ║
╠══════════════════════════════════════════════════════════╣
║  Movement (8-Dir) :  Rotation :  Speed Adjust :        ║
║    w   q   e          j (CCW)     r / f (Linear)       ║
║  a       d            l (CW)      t / g (Angular)      ║
║    z   c                                               ║
║  [Space] : Emergency Stop   |   [Ctrl+C] : Exit        ║
╚══════════════════════════════════════════════════════════╝
"""

def get_key_nonblocking():
    """อ่านค่าปุ่มแบบ Non-blocking โดยใช้ select"""
    dr, _, _ = select.select([sys.stdin], [], [], 0)
    if dr:
        return sys.stdin.read(1)
    return None

def clamp(value, min_val, max_val):
    return max(min_val, min(value, max_val))

def main():
    global LIN_SPEED, ANG_SPEED
    
    # ตรวจสอบว่ารันใน Terminal จริงหรือไม่
    if not sys.stdin.isatty():
        rospy.logerr("Error: This script must be run in an interactive terminal.")
        return

    # ตั้งค่า Terminal แบบ Raw (ไม่รอ Enter, ไม่ echo ตัวอักษร)
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        
        rospy.init_node('holonomic_teleop_advanced')
        pub = rospy.Publisher('/cmd_vel', Twist, queue_size=1)
        rate = rospy.Rate(UPDATE_RATE)

        print(BANNER)
        cmd = Twist()
        key_states = {}  # เก็บสถานะปุ่มและเวลาที่กดล่าสุด

        while not rospy.is_shutdown():
            current_time = time.time()
            
            # 1. อ่านค่าปุ่มที่กด (Non-blocking)
            key = get_key_nonblocking()
            if key:
                if key == '\x03':  # Ctrl+C
                    break
                if key == ' ':     # Emergency Stop
                    key_states.clear()
                else:
                    key_states[key] = current_time  # อัปเดตเวลา按压ล่าสุด
            
            # 2. คัดกรองปุ่มที่ยังถือว่า "ถูกกดอยู่" (ยังไม่ Timeout)
            active_keys = [k for k, t in key_states.items() if current_time - t < KEY_TIMEOUT]
            
            # 3. ปรับความเร็ว (Speed Adjustment)
            if 'r' in active_keys and LIN_SPEED < MAX_LIN_SPEED:
                LIN_SPEED = clamp(LIN_SPEED + SPEED_STEP, MIN_LIN_SPEED, MAX_LIN_SPEED)
                key_states.pop('r', None) # ป้องกันการรัว
            if 'f' in active_keys and LIN_SPEED > MIN_LIN_SPEED:
                LIN_SPEED = clamp(LIN_SPEED - SPEED_STEP, MIN_LIN_SPEED, MAX_LIN_SPEED)
                key_states.pop('f', None)
            if 't' in active_keys and ANG_SPEED < MAX_ANG_SPEED:
                ANG_SPEED = clamp(ANG_SPEED + SPEED_STEP, MIN_ANG_SPEED, MAX_ANG_SPEED)
                key_states.pop('t', None)
            if 'g' in active_keys and ANG_SPEED > MIN_ANG_SPEED:
                ANG_SPEED = clamp(ANG_SPEED - SPEED_STEP, MIN_ANG_SPEED, MAX_ANG_SPEED)
                key_states.pop('g', None)

            # 4. คำนวณเวกเตอร์การเคลื่อนที่ (Kinematics)
            dir_x, dir_y, dir_w = 0.0, 0.0, 0.0
            
            # 4 ทิศทางหลัก
            if 'w' in active_keys: dir_x += 1.0
            if 's' in active_keys: dir_x -= 1.0
            if 'a' in active_keys: dir_y += 1.0
            if 'd' in active_keys: dir_y -= 1.0
            
            # 4 ทิศทางแนวทแยง (Diagonal)
            if 'q' in active_keys: dir_x += 1.0; dir_y += 1.0
            if 'e' in active_keys: dir_x += 1.0; dir_y -= 1.0
            if 'z' in active_keys: dir_x -= 1.0; dir_y += 1.0
            if 'c' in active_keys: dir_x -= 1.0; dir_y -= 1.0
            
            # การหมุน (Yaw)
            if 'j' in active_keys: dir_w += 1.0
            if 'l' in active_keys: dir_w -= 1.0

            # 5. Vector Normalization (สำคัญมากสำหรับ Control Stability)
            # ทำให้ Resultant Velocity เท่ากันทุกทิศทาง ป้องกันล้อสลิป
            lin_mag = math.hypot(dir_x, dir_y)
            if lin_mag > 1.0:
                dir_x /= lin_mag
                dir_y /= lin_mag

            # 6. สั่งงาน Motor
            cmd.linear.x  = dir_x * LIN_SPEED
            cmd.linear.y  = dir_y * LIN_SPEED
            cmd.angular.z = dir_w * ANG_SPEED
            pub.publish(cmd)

            # 7. แสดงสถานะแบบ Real-time (ใช้ \r เพื่อเขียนทับบรรทัดเดิม)
            status = (f"\r[ LIN: {LIN_SPEED:.2f} m/s | ANG: {ANG_SPEED:.2f} rad/s | "
                      f"Active: {active_keys if active_keys else 'None'} ]   ")
            sys.stdout.write(status)
            sys.stdout.flush()

            rate.sleep()

    except Exception as e:
        rospy.logerr(f"Teleop Error: {e}")
    finally:
        # 8. Safety Failsafe: คืนค่า Terminal และสั่งหยุดหุ่นยนต์เสมอ
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        pub.publish(Twist()) # ส่งค่า 0 เพื่อหยุดมอเตอร์
        sys.stdout.write("\n[ System Stopped & Motors Disabled ]\n")
        sys.stdout.flush()

if __name__ == '__main__':
    try:
        main()
    except rospy.ROSInterruptException:
        pass
