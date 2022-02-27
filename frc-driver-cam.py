import jetson.inference
import jetson.utils
import time
import argparse
import cscore
from cscore import CameraServer
from networktables import NetworkTables

parser = argparse.ArgumentParser(description='FRC Object Detection')
# Common arguments
parser.add_argument('--team', '-t', type=int, default=7028,
                    help='Team number of robot to connect to. Not used when --ntip is specified.')

# Less common arguments
parser.add_argument('--ntip', '-ip',
                    help='IP Address of the NetworkTables to connect to. Leave blank to connect to robot.')
parser.add_argument('--camera-url', '-c', default="/dev/video0",
                    help='The camera to use for detection. Use `v4l2-ctl --list-devices` to get list of USB cameras')
parser.add_argument('--capture-height', type=int, default=720,
                    help='The resolution height to capture images from the camera. Use `v4l2-ctl --device=/dev/video1 --list-formats-ext` to get modes')
parser.add_argument('--capture-width', type=int, default=1280,
                    help='The resolution width to capture images from the camera.')
parser.add_argument('--stream-height', type=int, default=180,
                    help='The resolution to stream to the CameraServer.')
parser.add_argument('--stream-width', type=int, default=320,
                    help='The resolution to stream to the CameraServer.')
parser.add_argument('--stream-compression', type=int, default=20,
                    help='The compression to stream for clients that do not specify it.')

args = parser.parse_args()
print(args)

# Configure the CameraServer to send images to the Driver Station
cs = CameraServer.getInstance()
cs.enableLogging()
csSource = cscore.CvSource("Driver", cscore.VideoMode.PixelFormat.kMJPEG, args.stream_width, args.stream_height, 24)
server = cs.startAutomaticCapture(camera=csSource, return_server=True)
server.setCompression(args.stream_compression)

# Configure the NetworkTables to send data to the robot and shuffleboard
if args.ntip is None:
    NetworkTables.startClientTeam(args.team)
else:
    NetworkTables.initialize(args.ntip)

driverCamTable = NetworkTables.getTable('DriverCam')

# Configure the camera
camera = jetson.utils.videoSource(args.camera_url, argv=[
    "--input-width=" + str(args.capture_width),
    "--input-height=" + str(args.capture_height)])
driverCamTable.putString("Camera FPS", camera.GetFrameRate())

# Define variables to hold tranformed images for streaming
smallImg = None
bgrSmallImg = None

startTime = time.time()
while True:
    if not csSource.isEnabled():
        continue

    # Capture image from the camera
    img = camera.Capture()

    # Stream to CameraServer, if anyone is watching
    if csSource.isEnabled():
        # Resize the image on the GPU to lower resolution for more efficient streaming
        if smallImg is None:
            smallImg = jetson.utils.cudaAllocMapped(width=args.stream_width, height=args.stream_height, format=img.format)
        jetson.utils.cudaResize(img, smallImg)
        del img

        # Convert color from rgb8 to bgr8 - CUDA uses rgb but OpenCV/CameraServer use bgr
        # Without this step, red and blue are inverted in the streamed image
        if bgrSmallImg is None:
            bgrSmallImg = jetson.utils.cudaAllocMapped(width=args.stream_width, height=args.stream_height, format="bgr8")
        jetson.utils.cudaConvertColor(smallImg, bgrSmallImg)

        # Synchronize so changes from GPU are available on CPU
        jetson.utils.cudaDeviceSynchronize()

        # Convert to from CUDA to Numpy/OpenGL 
        # https://github.com/dusty-nv/jetson-inference/blob/master/docs/aux-image.md#converting-to-numpy-arrays
        numpyImg = jetson.utils.cudaToNumpy(bgrSmallImg, args.stream_width, args.stream_height, 4)

        # Send the image to the CameraServer
        csSource.putFrame(numpyImg)
        del numpyImg

    # Calculate timing statistics
    endTime = time.time()
    elapseTime = (endTime - startTime) * 1000
    startTime = endTime
    driverCamTable.putNumber("Latency", elapseTime)
    driverCamTable.putNumber("Pipeline FPS", 1000 / elapseTime)

del smallImg
del bgrSmallImg
