#!/usr/bin/env python
# ROS python API
import rospy

# import needed geometry messages
from geometry_msgs.msg import Point, Vector3, Quaternion, PoseStamped, TwistStamped
# import all mavros messages and services
from mavros_msgs.msg import *
from mavros_msgs.srv import *

# import quat and eul transformation
from tf.transformations import quaternion_from_euler, euler_from_quaternion

# import for script argument parsing
import argparse

# import other system/utils
import time, sys, math

# Constants
ALL_STEP_TYPES = ["pitch_rate", "roll_rate", "yaw_rate", "pitch", "roll", "yaw", "vx", "vy", "vz", "x", "y", "z"]
INDEX_PITCH_RATE = 0
INDEX_ROLL_RATE = 1
INDEX_YAW_RATE = 2
INDEX_PITCH = 3
INDEX_ROLL = 4
INDEX_YAW = 5
INDEX_VX = 6
INDEX_VY = 7
INDEX_VZ = 8
INDEX_X = 9
INDEX_Y = 10
INDEX_Z = 11
INDICES_ATTITUDE = [INDEX_PITCH_RATE, INDEX_ROLL_RATE, INDEX_YAW_RATE, INDEX_PITCH, INDEX_ROLL, INDEX_YAW]
INDICES_POSITION = [INDEX_VX, INDEX_VY, INDEX_VZ, INDEX_X, INDEX_Y, INDEX_Z]

# Global variables

# Flight modes class
# Flight modes are activated using ROS services
class FlightModes:
    def __init__(self):
        pass

    def setArm(self):
        rospy.wait_for_service('mavros/cmd/arming')
        try:
            armService = rospy.ServiceProxy('mavros/cmd/arming', mavros_msgs.srv.CommandBool)
            armService(True)
        except rospy.ServiceException, e:
            print "Service arming call failed: %s"%e

    def setOffboardMode(self):
        rospy.wait_for_service('mavros/set_mode')
        try:
            flightModeService = rospy.ServiceProxy('mavros/set_mode', mavros_msgs.srv.SetMode)
            flightModeService(custom_mode='OFFBOARD')
        except rospy.ServiceException, e:
            print "service set_mode call failed: %s. Offboard Mode could not be set."%e

# Flight parameters class
# Flight parameters are activated using ROS services
class FlightParams:
    def getTakeoffHeight(self):
        rospy.wait_for_service('mavros/param/get')
        try:
            paramService = rospy.ServiceProxy('mavros/param/get', mavros_msgs.srv.ParamGet)
            height = paramService('MIS_TAKEOFF_ALT')
            return height.value.real
        except rospy.ServiceException, e:
               print "service param_get call failed: %s. Could not retrieve parameter."%e

    def getHoverThrust(self):
        rospy.wait_for_service('mavros/param/get')
        try:
            paramService = rospy.ServiceProxy('mavros/param/get', mavros_msgs.srv.ParamGet)
            hover = paramService('MPC_THR_HOVER')
            return hover.value.real
        except rospy.ServiceException, e:
               print "service param_get call failed: %s. Could not retrieve parameter."%e

# Offboard controller for sending setpoints
class Controller:
    def __init__(self):
        # Drone state
        self.state = State()

        # A Message for the current local position of the drone
        self.local_pos = Point(0.0, 0.0, 0.0)

        # A Message for the current linear velocity of the drone
        self.local_vel = Vector3(0.0, 0.0, 0.0)

        # A Message for the current attitude of the drone
        self.quat = Quaternion(0.0, 0.0, 0.0, 1.0)

        # A Message for the current angular rate of the drone
        self.ang_rate = Vector3(0.0, 0.0, 0.0)

        # Instantiate the position setpoint message
        self.pos_sp = PositionTarget()
        # set the flag to control height
        self.pos_sp.type_mask = int('110111111000', 2)
        # LOCAL_NED
        self.pos_sp.coordinate_frame = 1
        # initial values for setpoints
        self.pos_sp.position.x = 0.0
        self.pos_sp.position.y = 0.0
        self.pos_sp.position.z = 0.0

        # Instantiate the attitude setpoint message
        self.att_sp = AttitudeTarget()
        # set the default flag
        self.att_sp.type_mask = int('11000111', 2)
        # initial values for setpoints
        self.att_sp.orientation.w = 1.0
        self.att_sp.orientation.x = 0.0
        self.att_sp.orientation.y = 0.0
        self.att_sp.orientation.z = 0.0

        # Obtain flight parameters
        params = FlightParams()
        self.takeoffHeight = params.getTakeoffHeight()
        self.hoverThrust = params.getHoverThrust()

        # Set initial yaw angle to unknown
        self.init_yaw = None

    # Update setpoint message
    def updateSp(self, step_type, step_val):
        # Set default values
        self.pos_sp.position.x = self.local_pos.x
        self.pos_sp.position.y = self.local_pos.y
        self.pos_sp.position.z = self.local_pos.z

        self.pos_sp.velocity.x = self.local_vel.x
        self.pos_sp.velocity.y = self.local_vel.y
        self.pos_sp.velocity.z = self.local_vel.z

        self.att_sp.orientation.w = self.quat.w
        self.att_sp.orientation.x = self.quat.x
        self.att_sp.orientation.y = self.quat.y
        self.att_sp.orientation.z = self.quat.z

        self.att_sp.body_rate.x = self.ang_rate.x
        self.att_sp.body_rate.y = self.ang_rate.y
        self.att_sp.body_rate.z = self.ang_rate.z

        self.att_sp.thrust = self.hoverThrust

        # Set step value
        if ALL_STEP_TYPES.index(step_type) == INDEX_VX:
            self.pos_sp.velocity.x = step_val
        elif ALL_STEP_TYPES.index(step_type) == INDEX_VY:
            self.pos_sp.velocity.y = step_val
        elif ALL_STEP_TYPES.index(step_type) == INDEX_VZ:
            self.pos_sp.velocity.z = step_val
        elif ALL_STEP_TYPES.index(step_type) == INDEX_X:
            self.pos_sp.position.x = step_val
        elif ALL_STEP_TYPES.index(step_type) == INDEX_Y:
            self.pos_sp.position.y = step_val
        elif ALL_STEP_TYPES.index(step_type) == INDEX_Z:
            self.pos_sp.position.z = step_val
        elif ALL_STEP_TYPES.index(step_type) == INDEX_ROLL_RATE:
            self.att_sp.body_rate.x = math.radians(step_val)
        elif ALL_STEP_TYPES.index(step_type) == INDEX_PITCH_RATE:
            self.att_sp.body_rate.y = math.radians(step_val)
        elif ALL_STEP_TYPES.index(step_type) == INDEX_YAW_RATE:
            self.att_sp.body_rate.z = math.radians(step_val)
        elif ALL_STEP_TYPES.index(step_type) == INDEX_ROLL:
            self.att_sp.orientation = Quaternion(*quaternion_from_euler(math.radians(step_val), 0.0, math.radians(self.init_yaw)))
        elif ALL_STEP_TYPES.index(step_type) == INDEX_PITCH:
            self.att_sp.orientation = Quaternion(*quaternion_from_euler(0.0, math.radians(step_val), math.radians(self.init_yaw)))
        elif ALL_STEP_TYPES.index(step_type) == INDEX_YAW:
            self.att_sp.orientation = Quaternion(*quaternion_from_euler(0.0, 0.0, math.radians(step_val)))

        # Set mask
        if ALL_STEP_TYPES.index(step_type) in [INDEX_VX, INDEX_VY, INDEX_VZ]:
            self.pos_sp.type_mask = int('110111000111', 2)
        elif ALL_STEP_TYPES.index(step_type) in [INDEX_X, INDEX_Y, INDEX_Z]:
            self.pos_sp.type_mask = int('110111111000', 2) 
        elif ALL_STEP_TYPES.index(step_type) in [INDEX_PITCH_RATE, INDEX_ROLL_RATE, INDEX_YAW_RATE]:
            self.att_sp.type_mask = int('10111000', 2)
        elif ALL_STEP_TYPES.index(step_type) in [INDEX_PITCH, INDEX_ROLL, INDEX_YAW]:
            self.att_sp.type_mask = int('00111111', 2)           

    # Callbacks.

    ## Drone State callback
    def stateCb(self, msg):
        self.state = msg

    ## Drone local position callback
    def posCb(self, msg):
        self.local_pos.x = msg.pose.position.x
        self.local_pos.y = msg.pose.position.y
        self.local_pos.z = msg.pose.position.z

        self.quat.w = msg.pose.orientation.w
        self.quat.x = msg.pose.orientation.x
        self.quat.y = msg.pose.orientation.y
        self.quat.z = msg.pose.orientation.z

        # Set initial yaw angle
        if self.init_yaw is None:
            self.init_yaw = math.degrees(euler_from_quaternion([self.quat.x, self.quat.y, self.quat.z, self.quat.w])[2])

    ## Drone linear velocity callback
    def velCb(self, msg):
        self.local_vel.x = msg.twist.linear.x
        self.local_vel.y = msg.twist.linear.y
        self.local_vel.z = msg.twist.linear.z

        self.ang_rate.x = msg.twist.angular.x
        self.ang_rate.y = msg.twist.angular.y
        self.ang_rate.z = msg.twist.angular.z

def publish_setpoint(cnt, step_type, pub_pos, pub_att):
    if ALL_STEP_TYPES.index(step_type) in [INDEX_VX, INDEX_VY, INDEX_VZ, INDEX_X, INDEX_Y, INDEX_Z]:
        pub_pos.publish(cnt.pos_sp)
    elif ALL_STEP_TYPES.index(step_type) in [INDEX_PITCH_RATE, INDEX_ROLL_RATE, INDEX_YAW_RATE, INDEX_PITCH, INDEX_ROLL, INDEX_YAW]:
        pub_att.publish(cnt.att_sp)

def run(argv):
    # Parse arguments
    parser = argparse.ArgumentParser()

    parser.add_argument("-t", "--type", help="step input type, should be one of the following: [pitch|roll|yaw]_rate, pitch, roll, yaw, v[x|y|z], x, y, z", type=str, nargs=1)
    parser.add_argument("-v", "--value", help="the step input final value in degrees[per second] or meters[per second], depending on the type", type=float, nargs=1)
    parser.add_argument("-d", "--duration", help="the duration of the step input in seconds, if not provided the duration is infinity", type=float, nargs="?")

    args = parser.parse_args()
    if args.type != None and args.value != None:
        step_type = str(args.type[0])
        value = args.value[0]
    else:
        print("Please provide a step type and a step final value")
        sys.exit(2)
    duration = float("inf")

    # Validate arguments
    if args.duration != None:
        duration = args.duration
    elif step_type == None or value == None:
        print("Please provide a step type and a step final value")
        sys.exit(2)
    elif step_type not in ALL_STEP_TYPES:
        print("Please provide a valid step type")
        sys.exit(2)

    # initiate node
    rospy.init_node('setpoint_node', anonymous=True)

    # flight mode object
    modes = FlightModes()

    # controller object
    cnt = Controller()

    # ROS loop rate
    rate = rospy.Rate(20.0)

    # Subscribe to drone state
    rospy.Subscriber('mavros/state', State, cnt.stateCb)

    # Subscribe to drone's local position
    rospy.Subscriber('mavros/local_position/pose', PoseStamped, cnt.posCb)

    # Subscribe to drone's linear velocity
    rospy.Subscriber('mavros/local_position/velocity', TwistStamped, cnt.velCb)

    # Setpoint publishers   
    sp_pos_pub = rospy.Publisher('mavros/setpoint_raw/local', PositionTarget, queue_size=1)
    sp_att_pub = rospy.Publisher('mavros/setpoint_raw/attitude', AttitudeTarget, queue_size=1)

    # Make sure the drone is armed
    print("Arming")
    while not (cnt.state.armed or rospy.is_shutdown()):
        modes.setArm()
        rate.sleep()
    print("Armed\n")

    # activate OFFBOARD mode
    print("Activate OFFBOARD mode")
    while not (cnt.state.mode == "OFFBOARD" or rospy.is_shutdown()):
        # We need to send few setpoint messages, then activate OFFBOARD mode, to take effect
        k=0
        while k<10:
            sp_pos_pub.publish(cnt.pos_sp)
            rate.sleep()
            k = k + 1

        modes.setOffboardMode()
        rate.sleep()
    print("OFFBOARD mode activated\n")

    # Takeoff
    print("Taking off")
    while not (abs(cnt.local_pos.z - cnt.takeoffHeight) < 0.2 or rospy.is_shutdown()):
        cnt.updateSp("z", cnt.takeoffHeight)
        sp_pos_pub.publish(cnt.pos_sp)
        rate.sleep()
    print("Reached takeoff height")

    # ROS main loop
    start = time.time()
    while not ((time.time() - start >= duration) or rospy.is_shutdown()):
        cnt.updateSp(step_type, value)
        publish_setpoint(cnt, step_type, sp_pos_pub, sp_att_pub)
        rate.sleep()

    # Time exceeded - step down to 0. Well, really close to 0...
    final_val = 1e-6
    if ALL_STEP_TYPES.index(step_type) == INDEX_Z:
        final_val = cnt.takeoffHeight
    elif ALL_STEP_TYPES.index(step_type) == INDEX_YAW:
        final_val = cnt.init_yaw

    # Step down for the same duration
    start = time.time()
    while not ((time.time() - start >= duration) or rospy.is_shutdown()):
        cnt.updateSp(step_type, final_val)
        publish_setpoint(cnt, step_type, sp_pos_pub, sp_att_pub)
        rate.sleep()

def main(argv):
    try:
		run(argv)
    except rospy.ROSInterruptException:
        pass
    print("Terminated.\n")

if __name__ == "__main__":
    main(sys.argv[1:])