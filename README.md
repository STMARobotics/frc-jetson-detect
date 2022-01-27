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
curl -o get-pip.py https://bootstrap.pypa.io/get-pip.py
python3 get-pip.py
rm get-pip.py
```

Add to pip `~/.bashrc` by adding this line to the end of the file
```
export PATH=$PATH:/home/robotics/.local/bin
```

Install pynetworktables. [See docs for details](https://robotpy.readthedocs.io/en/stable/install/pynetworktables.html#install-via-pip-on-macos-linux)
```
pip install pynetworktables
```


Install cscore. [See docs for details](https://software.opensuse.org/download.html?project=home%3Aauscompgeek%3Arobotpy&package=python3-cscore)
```
echo 'deb http://download.opensuse.org/repositories/home:/auscompgeek:/robotpy/xUbuntu_18.04/ /' | sudo tee /etc/apt/sources.list.d/home:auscompgeek:robotpy.list
curl -fsSL https://download.opensuse.org/repositories/home:auscompgeek:robotpy/xUbuntu_18.04/Release.key | gpg --dearmor | sudo tee /etc/apt/trusted.gpg.d/home_auscompgeek_robotpy.gpg > /dev/null
sudo apt update
sudo apt install python3-cscore
```

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