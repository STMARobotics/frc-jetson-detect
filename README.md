This repo is for Object Detection on the Jetson

# Background
The first thing to know is that we are trying to do Object Detection (not Image Classification.)

This doc just lists some helpful information and is not a complete reference. Please look at the [jetson-inference](https://github.com/dusty-nv/jetson-inference) repo on GitHub. There are links at the bottom to YouTube videos.

## Setup
To get started from scratch, the Jetson needs to be set up.
1) Install Jetpack
1) [Clone and build the jetson-inference project](https://github.com/dusty-nv/jetson-inference/blob/master/docs/building-repo-2.md)

## Object Detection
Information about object detection can be found here:
- [Object Detection YouTube video](https://www.youtube.com/watch?v=obt60r8ZeB0&list=PL5B692fm6--uQRRDTPsJDp4o0xbzkoyf8&index=12)
- [Object detection documentation](
  https://github.com/dusty-nv/jetson-inference/blob/master/docs/detectnet-console-2.md#detecting-objects-from-the-command-line)

# Training a model
## Labeling data sets

https://cvat.org/

NOTE: After export, need to add labels.txt with each label on its own line(without trailing new-line)

## Training background
Information about training your own model can be found here:
1) [Training object detection models YouTube video](https://www.youtube.com/watch?v=2XMkPW_sIGg&list=PL5B692fm6--uQRRDTPsJDp4o0xbzkoyf8&index=13)
1) [Documentation for training a model with Pytorch](https://github.com/dusty-nv/jetson-inference/blob/master/docs/pytorch-collect-detection.md)

## Training
Example command for training
```bash
python3 train_ssd.py --dataset-type=voc --data=data/cargo --model-dir=/models/cargo --batch-size=4 --workers=2
```

Convert to ONNX format:
```
python3 onnx_export.py --model-dir=models/cargo
```

## Testing a model
Run detection on a bunch of images:
```
detectnet --model=models/cargo/ssd-mobilenet.onnx --labels=models/cargo/labels.txt --input-blob=input_0 --output-cvg=scores --output-bbox=boxes "test-images/*.jpg" --threshold=20 output_%i.jpg
```

# Integration with FRC robot
Integration with an FRC robot uses [RobotPy](https://robotpy.readthedocs.io/en/stable/) CScore, and pynetworktables

## Setup
Install pip
```
sudo apt update
sudo apt install python3-pip
```

Install pynetworktables. Unfortunately, WPILib 2023 requires Ubunty 22.04, but Jetson runs 18.04. You must use older
python libraries. `pynetworktables` is still compatible, the newer `pyntcore` is not.
[See docs for details](https://robotpy.readthedocs.io/en/stable/install/pynetworktables.html#install-via-pip-on-macos-linux)
```
python3 -m pip install pynetworktables
```


Install cscore.
Warning: If you follow the docs to install with `apt` you may get an old version. Using pip will build from source, so it takes a few minutes, but you'll get the correct version. 2023+ requires Ubuntu 22.04, so use version 2022.0.3.
```
export CPPFLAGS=-I/usr/include/opencv4
python3 -m pip install robotpy-cscore===2022.0.3
```

# NetworkTables
The Jetson communicate with the robot and driver station through the NetworkTables. This is pretty simple, so just [look at the docs](https://robotpy.readthedocs.io/projects/pynetworktables/en/stable/api.html).

```python
from networktables import NetworkTables

NetworkTables.initialize()
sd = NetworkTables.getTable("SmartDashboard")
sd.putNumber("MyNumber", 1234)
```

# CameraServer (CSCore)
The CameraServer is for streaming video. This is used to stream images after to the driver station for debugging.

There are two places to look for documentation, [RobotPy CameraServer docs](https://robotpy.readthedocs.io/projects/cscore/en/stable/api.html) and [WPILib CameraServer docs](https://docs.wpilib.org/en/stable/docs/software/vision-processing/introduction/cameraserver-class.html)

# Misc
## Finding cameras
Command to list cameras:
```
v4l2-ctl --list-devices
```
NOTE: This command requires v4l-utils. If it is not installed, run this command:
```
sudo apt install v4l-utils
```

### Pick the right camera
If there are multiple cameras you will need to do additional work to find a way to identify them between boots. FRC's
cscore supports identifying cameras by path or ID, jetson-inference appears to only support device IDs like /dev/video0.

Once you have identified your camera with `v4l2-ctl --list-devices`, run this to get camera's alternate paths:
```
sudo udevadm info --query=all --name=/dev/video3
```

From here, there are a few ways you may be able to uniquely identify the camera. You may be able to identify it by
model, serial number, or USB port. In our case, two of our cameras have the same model and serial number, so we need
to identify them by USB port. From the command above, at least one of the entries will have a path that includes the
USB port:
```
/dev/v4l/by-path/platform-70090000.xusb-usb-0:2:1.0-video-index0
                                              ^
                                              port
```                                              
On the Jetson, the USB 3.0 port appears to be port `2`. The bottom USB 2.0 port appears to be port `3.1` and the top
USB 2.0 port appears to be port `3.2`. If a USB hub is connected it will be appended, for example a two port hub in
port `3.1` will have ports `3.1.1` and `3.1.2`.

Our H.264 cameras identify as two devices: video-index0 appears to be MJPEG/YUYV whereas video-index1 appears to be
H.264.

Our H.264 cameras don't seem to be distinguishable, there is no serial number, etc. However, the HD camera seems to
consistently have this ID, regardless of port: `v4l/by-id/usb-HD_USB_Camera_HD_USB_Camera-video-index0`

Once you have identified the camera, you need to pass it to the python script. The `frc-driver-cam.py` script will
accept a variety of camera IDs, so you can probably choose any of them from `udevadm` and they will work.
Unfortunately, the `frc-detect.py` script does not. You can use bash commands to locate the camera when you
execute the script. For example, this command will find the camera on usb port 2.1:
```
python3 frc-detect.py -c `v4l2-ctl --list-devices | grep -A 1 usb-2.1 | grep video`
```

There are a number of solutions to use this in the systemd service (see below), but a simple option is to use bash.
The ExecStart entry would be something like this:
```
ExecStart=/bin/bash -c "/usr/bin/python3 /home/robotics/frc-jetson-detect/frc-detect.py -c `v4l2-ctl --list-devices | grep -A 1 'usb-2.1' | grep video`"
```

### Scheduling at startup
Schedule this project to run on startup with systemd.

Create a file with the below contents in the folder `/etc/systemd/system`.

```bash
sudo nano /etc/systemd/system/frc-detect.service
```

Add contents like this to the file and save:
```
[Unit]
Description=FRC Object Detection
After=network-online.target
Wants=network-online.target systemd-networkd-wait-online.service
[Service]
Restart=on-failure
RestartSec=1s
User=robotics
Type=simple
WorkingDirectory=/home/robotics/frc-jetson-detect
ExecStart=/usr/bin/python3 /home/robotics/frc-jetson-detect/frc-detect.py --record-folder /media/robotics/Robotics-USB
[Install]
WantedBy=multi-user.target
```

Start the service and then check that it starts up with these comands:
```bash
sudo systemctl start frc-detect
journalctl -f -u frc-detect
```

If the service was successful, enable it so it will start automatically when the computer boots up:
```bash
sudo systemctl enable frc-detect.service
```

### Recording to USB
When a USB drive is inserted it will mount to /media/robotics/<VolumeName>. You can pass this path with the 
`--record-folder` parameter. We named our USB drives `Robotics-USB` so you will see in the service above we pass
`--record-folder /media/robotics/Robotics-USB`.

WARNING: Be sure to eject the USB drive or power down or your data most likely will not be saved. Use `mount` to find
the device, it will be something like `/dev/sda1`. Then run `sudo eject /dev/<DeviceID>`.

### Running headless
Like a Raspberry Pi, you can configure the Jetson to boot to the command-line instead of loading the window manager and
desktop. This will reduce resource utilization, especially memory.

```bash
sudo init 3     # stop the desktop
sudo init 5     # restart the desktop
```

If you wish to make this persistent across reboots, you can use the follow commands to change the boot-up behavior:

```bash
sudo systemctl set-default multi-user.target     # disable desktop on boot
sudo systemctl set-default graphical.target      # enable desktop on boot
```
Then after you reboot, the desktop will remain disabled or enabled (whichever default you set).
