import argparse
import cscore
import time
from networktables import NetworkTables

parser = argparse.ArgumentParser(description='FRC Object Detection')
# Common arguments
parser.add_argument('--team', '-t', type=int, default=7028,
                    help='Team number of robot to connect to. Not used when --ntip is specified.')

# Less common arguments
parser.add_argument('--ntip', '-ip',
                    help='IP Address of the NetworkTables to connect to. Leave blank to connect to robot.')
parser.add_argument('--front-camera', '-cf', default="/dev/video3",
                    help='The camera to use for detection. Use `v4l2-ctl --list-devices` to get list of USB cameras')
parser.add_argument('--rear-camera', '-cr', default="/dev/video1",
                    help='The camera to use for detection. Use `v4l2-ctl --list-devices` to get list of USB cameras')
parser.add_argument('--height', type=int, default=180,
                    help='The resolution height to capture images from the cameras. Use `v4l2-ctl --device=/dev/video1 --list-formats-ext` to get modes')
parser.add_argument('--width', type=int, default=320,
                    help='The resolution width to capture images from the cameras.')
parser.add_argument('--rate', type=int, default=20,
                    help="The framerate (FPS) to capture from the cameras.")
parser.add_argument('--stream-compression', type=int, default=20,
                    help='The compression to stream for clients that do not specify it.')
parser.add_argument("--port", "-p", type=int, default=1181,
                    help="MjpgServer port for streaming")

args = parser.parse_args()
print(args)

frontCam = cscore.UsbCamera("DriverCam0", args.front_camera)
frontCam.setPixelFormat(cscore.VideoMode.PixelFormat.kMJPEG)
frontCam.setResolution(args.width, args.height)
frontCam.setFPS(args.rate)
frontCam.setConnectionStrategy(cscore.VideoSource.ConnectionStrategy.kKeepOpen)

rearCam = cscore.UsbCamera("DriverCam1", args.rear_camera)
rearCam.setPixelFormat(cscore.VideoMode.PixelFormat.kMJPEG)
rearCam.setResolution(args.width, args.height)
rearCam.setFPS(args.rate)
rearCam.setConnectionStrategy(cscore.VideoSource.ConnectionStrategy.kKeepOpen)

server = cscore.MjpegServer(name="Driver", port=args.port)
server.setCompression(args.stream_compression)
server.setFPS(args.rate)
server.setResolution(args.width, args.height)

# Configure the NetworkTables to send data to the robot and shuffleboard
if args.ntip is None:
    NetworkTables.startClientTeam(args.team)
else:
    NetworkTables.initialize(args.ntip)


# Set up the entry that is used to select front or rear camera
driverCamTable = NetworkTables.getTable('DriverCam')
driverCamTable.putBoolean("Front", driverCamTable.getBoolean("Front", True))

# Loop forever switching the source to front or back
startTime = time.time()
while True:
    if driverCamTable.getBoolean("Front", True):
        server.setSource(frontCam)
    else:
        server.setSource(rearCam)

    # Republish the camera every 5 seconds in case the IP changes
    if ((time.time() - startTime) % 5):
        # Publish the stream to the CameraPublisher table so it can be added to shuffleboard
        streamAddresses = []
        for addr in cscore.getNetworkInterfaces():
            if addr == "127.0.0.1":
                continue  # ignore localhost
            streamAddresses.append("mjpg:http://%s:%d/?action=stream" % (addr, args.port))
        NetworkTables.getTable("CameraPublisher").getSubTable("Driver").putStringArray("streams", streamAddresses)