import jetson.inference
import jetson.utils
import json
import time
import datetime
import math
import argparse
import cscore
from cscore import CameraServer
from networktables import NetworkTables

def drawCrossHairs(input, x, y, r, g, b, a, size, gapSize, thickness):
    jetson.utils.cudaDrawLine(img, (x, y - size // 2), (x, y - gapSize // 2), (r, g, b, a), thickness)
    jetson.utils.cudaDrawLine(img, (x, y + size // 2), (x, y + gapSize // 2), (r, g, b, a), thickness)

    jetson.utils.cudaDrawLine(img, (x - size // 2, y), (x - gapSize // 2, y), (r, g, b, a), thickness)
    jetson.utils.cudaDrawLine(img, (x + size // 2, y), (x + gapSize // 2, y), (r, g, b, a), thickness)

parser = argparse.ArgumentParser(description='FRC Object Detection')
# Common arguments
parser.add_argument('--model-dir', default="/home/robotics/jetson-inference/python/training/detection/ssd/models/7028-all-1-31",
                    help='The model directory')
parser.add_argument('--model-file', default="ssd-mobilenet.onnx",
                    help='The name of the model file')
parser.add_argument('--threshold', type=float, default=0.5,
                    help='The confidence threshold. Detections with confidence below the threshold are excluded.')
parser.add_argument('--team', '-t', type=int, default=7028,
                    help='Team number of robot to connect to. Not used when --ntip is specified.')

# Less common arguments
parser.add_argument('--ntip', '-ip',
                    help='IP Address of the NetworkTables to connect to. Leave blank to connect to robot.')
parser.add_argument('--display', '-d', action='store_true',
                    help='Show a window on the desktop with detection result. Default: False.')
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
parser.add_argument('--record-folder', default=".",
                    help='Folder where recorded video is stored.')
parser.add_argument('--record-height', type=int, default=360,
                    help='The resolution to record frames.')
parser.add_argument('--record-width', type=int, default=640,
                    help='The resolution to record frames.')

args = parser.parse_args()
print(args)

# Scale of current capture settings vs the baseline of 720p (used to scale things we draw on the image)
captureScale = args.capture_height / 720

# Crosshair location. This is the "origin" for targets - the location where we want targets to be.
crosshairX = args.capture_width // 2
crosshairY = args.capture_height

# Configure the CameraServer to send images to the Driver Station
cs = CameraServer.getInstance()
cs.enableLogging()
csSource = cscore.CvSource("Jetson", cscore.VideoMode.PixelFormat.kMJPEG, args.stream_width, args.stream_height, 24)
server = cs.startAutomaticCapture(camera=csSource, return_server=True)
server.setCompression(args.stream_compression)

# Configure the NetworkTables to send data to the robot and shuffleboard
if args.ntip is None:
    NetworkTables.startClientTeam(args.team)
else:
    NetworkTables.initialize(args.ntip)

jetsonTable = NetworkTables.getTable('JetsonDetect')

# Configure DetectNet for object detection
detectNet = jetson.inference.detectNet(
    argv=[
        "--model=" + args.model_dir + "/" + args.model_file,
        "--class_labels=" + args.model_dir + "/labels.txt",
        "--input-blob=input_0",
        "--output-cvg=scores",
        "--output-bbox=boxes"
    ],
    threshold=args.threshold)

# Load class labels from the model
with open(args.model_dir + "/labels.txt") as file:
    labels = file.read().splitlines()

# Configure the camera
camera = jetson.utils.videoSource(args.camera_url, argv=[
    "--input-width=" + str(args.capture_width),
    "--input-height=" + str(args.capture_height)])
jetsonTable.putString("Camera FPS", camera.GetFrameRate())

display = None
if args.display:
    display = jetson.utils.videoOutput("display://0")

# Define variables to hold tranformed images for streaming
smallImg = None
bgrSmallImg = None

# Define variables used for record video
recordFrameNum = -1
recordImg = None
recordVideo = None

startTime = time.time()
while True:
    if not csSource.isEnabled() and not jetsonTable.getBoolean("Enabled", True):
        jetsonTable.putString("Status", "Sleeping")
        time.sleep(.02)
        continue

    jetsonTable.putString("Status", "Processing")
    # Capture image from the camera
    img = camera.Capture()

    # If "Record" entry is set, save every 20th frame to a video file
    if jetsonTable.getBoolean("Record", False):
        recordFrameNum += 1
        recordInterval = jetsonTable.getNumber("Record Interval", 20)
        if (recordInterval < 1): recordInterval = 1
        if recordFrameNum % recordInterval == 0:
            if recordVideo is None:
                recordVideo = jetson.utils.videoOutput(f"{args.record_folder}/frc-capture-{datetime.datetime.now():%Y-%m-%d-%H%M%S}.mp4", argv=["--headless"])
            if recordImg is None:
                recordImg = jetson.utils.cudaAllocMapped(width=args.record_width, height=args.record_height, format=img.format)
            jetson.utils.cudaResize(img, recordImg)
            recordVideo.Render(recordImg)
            recordFrameNum = 0
    else:
        # Clear the variables so a new file is created every time recording is enabled
        recordVideo = None
        recordImg = None
        recordFrameNum = -1

    # Detect objects from the image. Have DetectNet overlay confidence on image.
    detections = detectNet.Detect(img, overlay='conf')

    cargoColor = jetsonTable.getString("CargoColor", "Both")
    closestDetection = None
    closestDetectionDistance = 10000
    # Loop over detected objects
    ntDetections = []
    for detection in detections:
        # Filter based on selected color - RedCargo, BlueCargo, or Both
        if labels[detection.ClassID] == cargoColor or cargoColor == "Both":
            # Calculate the target's distance from the crosshairs
            targetX = detection.Center[0] - crosshairX
            targetY = crosshairY - detection.Center[1]
            targetDistance = math.sqrt(targetX**2 + targetY**2)

            # Create object we can serialize to the network table.
            ntDetection = {
                "ClassLabel": labels[detection.ClassID],
                "ClassID": detection.ClassID,
                "InstanceID": detection.Instance,
                "Area": detection.Area,
                "Bottom": detection.Bottom,
                "CenterX": detection.Center[0],
                "CenterY": detection.Center[1],
                "Confidence": detection.Confidence,
                "Height": detection.Height,
                "Left": detection.Left,
                "Right": detection.Right,
                "Top": detection.Top,
                "Width": detection.Width,
                "Timestamp": time.time(),
                "TargetX": targetX,
                "TargetY": targetY,
                "TargetDistance": targetDistance
            }
            ntDetections.append(ntDetection)
            
            # Check if this is the closest object encountered so far
            if targetDistance < closestDetectionDistance:
                closestDetection = ntDetection
                closestDetectionDistance = targetDistance
            
            # Draw box over detection. We do this here instead of having DetectNet do it so we can choose the colors.
            if labels[detection.ClassID] == "RedCargo":
                jetson.utils.cudaDrawRect(img, (detection.Left, detection.Top, detection.Right, detection.Bottom), (255, 0, 0, 75))
            else:
                jetson.utils.cudaDrawRect(img, (detection.Left, detection.Top, detection.Right, detection.Bottom), (0, 0, 255, 75))
    
    jetsonTable.putString("Detections", json.dumps(ntDetections))
    jetsonTable.putNumber("Network FPS", detectNet.GetNetworkFPS())

    if (closestDetection is None):
        jetsonTable.putString("Closest Detection", "")
    else:
        jetsonTable.putString("Closest Detection", json.dumps(closestDetection))
        # Draw + in the center of the detection
        drawCrossHairs(img, closestDetection["CenterX"], closestDetection["CenterY"], 
            255, 255, 255, 255,
            30 * captureScale, 12 * captureScale, 3)

    # Draw the origin crosshairs
    drawCrossHairs(img, crosshairX, crosshairY,
        0, 255, 0, 255,
        120 * captureScale, 30 * captureScale, 1)

    if display is not None:
        # Update the the desktop window
        display.Render(img)
        display.SetStatus("Object Detection | Network {:.0f} FPS".format(detectNet.GetNetworkFPS()))

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
    jetsonTable.putNumber("Latency", elapseTime)
    jetsonTable.putNumber("Pipeline FPS", 1000 / elapseTime)

del smallImg
del bgrSmallImg
