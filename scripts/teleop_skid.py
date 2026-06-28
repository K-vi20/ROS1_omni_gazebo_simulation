#!/usr/bin/env python3
"""
Holonomic teleop สำหรับ gazebo_ros_planar_move
ควบคุมด้วย keyboard: x / y / yaw
"""
import sys
import tty
import termios
import rospy
from geometry_msgs.msg import Twist

BANNER = """
╔══════════════════════════════════╗
║   Holonomic Robot Teleop         ║
╠══════════════════════════════════╣
║  w / s  : หน้า / หลัง           ║
║  a / d  : ซ้าย / ขวา (lateral)  ║
║  q / e  : หมุนซ้าย / ขวา        ║
║  Space  : หยุด                   ║
║  Ctrl+C : ออก                    ║
╚══════════════════════════════════╝
"""

LIN_SPEED = 0.3   # m/s
ANG_SPEED = 0.8   # rad/s

KEY_MAP = {
    'w': ( LIN_SPEED,  0.0,        0.0),
    's': (-LIN_SPEED,  0.0,        0.0),
    'a': ( 0.0,        LIN_SPEED,  0.0),
    'd': ( 0.0,       -LIN_SPEED,  0.0),
    'q': ( 0.0,        0.0,        ANG_SPEED),
    'e': ( 0.0,        0.0,       -ANG_SPEED),
    ' ': ( 0.0,        0.0,        0.0),
}

def get_key():
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        return sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)

def main():
    rospy.init_node('teleop_skid')
    pub = rospy.Publisher('/cmd_vel', Twist, queue_size=1)
    rate = rospy.Rate(20)

    print(BANNER)
    cmd = Twist()

    while not rospy.is_shutdown():
        key = get_key()
        if key == '\x03':   # Ctrl+C
            break

        if key in KEY_MAP:
            vx, vy, wz = KEY_MAP[key]
            cmd.linear.x  = vx
            cmd.linear.y  = vy
            cmd.angular.z = wz
        else:
            cmd.linear.x  = 0.0
            cmd.linear.y  = 0.0
            cmd.angular.z = 0.0

        pub.publish(cmd)
        rate.sleep()

    # หยุด robot ก่อนออก
    pub.publish(Twist())

if __name__ == '__main__':
    main()
