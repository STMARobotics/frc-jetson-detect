import jetson.inference
import jetson.utils
import time
import argparse
import cscore
from cscore import CameraServer
from networktables import NetworkTables
import numpy

parser = argparse.ArgumentParser(description='FRC Object Detection')
# Common arguments
parser.add_argument('--team', '-t', type=int, default=7028,
                    help='Team number of robot to connect to. Not used when --ntip is specified.')

# Less common arguments
parser.add_argument('--ntip', '-ip',
                    help='IP Address of the NetworkTables to connect to. Leave blank to connect to robot.')
parser.add_argument('--camera0-url', '-c0', default="/dev/video0",
                    help='The camera to use for detection. Use `v4l2-ctl --list-devices` to get list of USB cameras')
parser.add_argument('--camera1-url', '-c1', default="/dev/video2",
                    help='The camera to use for detection. Use `v4l2-ctl --list-devices` to get list of USB cameras')
parser.add_argument('--height', type=int, default=180,
                    help='The resolution height to capture images from the cameras. Use `v4l2-ctl --device=/dev/video1 --list-formats-ext` to get modes')
parser.add_argument('--width', type=int, default=320,
                    help='The resolution width to capture images from the cameras.')
parser.add_argument('--rate', type=int, default=20,
                    help="The framerate (FPS) to capture from the cameras.")
parser.add_argument('--stream-compression', type=int, default=20,
                    help='The compression to stream for clients that do not specify it.')
parser.add_argument("--port", "-p", type=int, default=1182,
                    help="CameraServer port")

args = parser.parse_args()
print(args)

# Configure the CameraServer to send images to the Driver Station
cs = CameraServer.getInstance()
cs.enableLogging()

usbCam0 = cscore.UsbCamera("DriverCam0", args.camera0_url)
usbCam0.setResolution(args.width, args.height)
usbCam0.setFPS(args.rate)
usbCam0.setPixelFormat(cscore.VideoMode.PixelFormat.kMJPEG)
usbCam0.setConnectionStrategy(cscore.VideoSource.ConnectionStrategy.kKeepOpen)


usbCam1 = cscore.UsbCamera("DriverCam1", args.camera1_url)
usbCam1.setPixelFormat(cscore.VideoMode.PixelFormat.kMJPEG)
usbCam1.setResolution(args.width, args.height)
usbCam1.setFPS(args.rate)
usbCam1.setConnectionStrategy(cscore.VideoSource.ConnectionStrategy.kKeepOpen)

server = cs.addServer(name="DriverCombined", port=args.port)
# server = cs.addSwitchedCamera("Driver")
server.setSource(usbCam0)

csSource = cscore.CvSource("DriverCombined", cscore.VideoMode.PixelFormat.kMJPEG, args.width, args.height, args.rate)
# server = cs.startAutomaticCapture(camera=csSource, return_server=True)
server.setSource(csSource)
server.setCompression(args.stream_compression)
server.setFPS(args.rate)
server.setResolution(args.width, args.height)

# Configure the NetworkTables to send data to the robot and shuffleboard
if args.ntip is None:
    NetworkTables.startClientTeam(args.team)
else:
    NetworkTables.initialize(args.ntip)

driverCamTable = NetworkTables.getTable('DriverCam')
driverCamTable.putNumber("CameraNum", 0)

cvSource0 = cs.getVideo(camera=usbCam0)
cvSource1 = cs.getVideo(camera=usbCam1)

image = numpy.zeros(shape=(args.height, args.width, 3), dtype=numpy.uint8)
while True:
    if driverCamTable.getNumber("CameraNum", 0) == 0:
        cvSource0.grabFrame(image)
    else:
        cvSource1.grabFrame(image)
        
    csSource.putFrame(image)