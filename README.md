# PX4 Multicopter Step Input
A ROS package that executes step inputs of the different PX4 multicopter controllers.

## Pre-requisites

### Install PX4

https://dev.px4.io/en/setup/dev_env_linux_ubuntu.html

### Install ROS and MAVROS

IMPORTANT: If you are using Ubuntu 18.04, you need to install ROS Melodic. If you are using Ubuntu 16.04, you need to install ROS Kinetic.

The below commands are for Ubuntu 18.04 and ROS Melodic. If you are using Ubuntu 16.04, replace all `melodic` commands with `kinetic`.

#### Ubuntu 18.04

- Install ROS (https://wiki.ros.org/melodic/Installation/Ubuntu)
- Install MAVROS
  - `sudo apt-get install ros-melodic-mavros ros-melodic-mavros-extras`
  - `wget https://raw.githubusercontent.com/mavlink/mavros/master/mavros/scripts/install_geographiclib_datasets.sh`
  - `chmod +x install_geographiclib_datasets.sh`
  - `sudo ./install_geographiclib_datasets.sh`
  - `rm -rf install_geographiclib_datasets.sh`
- Install Python libraries
  - `sudo apt-get install python-rosinstall python-wstool python-rosinstall-generator python-catkin-tools -y`
  - `sudo pip install pymavlink`
  
### Create catkin workspace

The official build system of ROS is called catkin. One needs a catkin workspace to build and run ROS packages.

- `mkdir -p catkin_ws/src`
- `cd catkin_ws`
- `catkin init`
- `wstool init src`
- `cd src`
- `git clone https://github.com/18177654/px4_mc_step_input.git`
- `cd ..`
- `catkin build`
- `source devel/setup.bash`

## Run

- Open a terminal, navigate to the PX4 root directory and start PX4 SITL:
  - `make px4_sitl jmavsim`
- Open another terminal and start MAVROS:
  - `roslaunch mavros px4.launch fcu_url:="udp://:14540@127.0.0.1:14557"`
- Open another terminal and run the ROS package px4_mc_step_input in the catkin workspace directory:
  - `rosrun mc_step_input mc_step_input.py -t z -v 10 -d 10` (Step to 10m)
- For help on how to use the ROS node, run the following:
  - `rosrun mc_step_input mc_step_input.py --help` (Commands help)
