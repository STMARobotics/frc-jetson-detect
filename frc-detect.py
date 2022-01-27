import jetson.inference
import jetson.utils
import json
from cscore import CameraServer
from networktables import NetworkTables

# Directory where the model is stored
MODEL_DIR = "/home/robotics/jetson-inference/python/training/detection/ssd/models/7028-vid-1-26"
MODEL_FILE_NAME = "ssd-mobilenet.onnx"

# Detection confidence thresold in percent. Confidence less than this will not be returned
CONFIDENCE_THRESHOLD = 0.5

# Camera URL
# '/dev/video1' for USB (use `v4l2-ctl --list-devices` to get list of USB cameras)
CAMERA_URL = "/dev/video1"
# 'csi://0' for CSI (PiCam)
# CAMERA_URL = "csi://0"

# Capture dimensions and rate
CAP_HEIGHT = 720
CAP_WIDTH = 1280
CAP_RATE = 60

# CameraServer dimensions
STREAM_HEIGHT = 180
STREAM_WIDTH = 320

# Configure the CameraServer to send images to the Driver Station
cs = CameraServer.getInstance()
cs.enableLogging()
csSource = cs.putVideo("Jetson", STREAM_WIDTH, STREAM_HEIGHT)

# Configure the NetworkTables to send data to the robot and Driver Station
# NetworkTables.initialize("192.168.1.214")
NetworkTables.startClientTeam(7028)
jetsonTable = NetworkTables.getTable('JetsonDetect')

# Configure DetectNet for object detection
detectNet = jetson.inference.detectNet(
    argv=[
        "--model=" + MODEL_DIR + "/" + MODEL_FILE_NAME,
        "--class_labels=" + MODEL_DIR + "/labels.txt",
        "--input-blob=input_0",
        "--output-cvg=scores",
        "--output-bbox=boxes"
    ],
    threshold=CONFIDENCE_THRESHOLD)

# Load class labels from the model
with open(MODEL_DIR + "/labels.txt") as file:
    labels = file.read().splitlines()

# Configure the camera
camera = jetson.utils.videoSource(CAMERA_URL, argv=[
    "--input-width=" + str(CAP_WIDTH),
    "--input-height=" + str(CAP_HEIGHT),
    "--input-rate=" + str(CAP_RATE)])

# display = jetson.utils.videoOutput("display://0") # 'my_video.mp4' for file

while True:
    # Capture image from the camera
    img = camera.Capture()

    # Detect objects from the image
    detections = detectNet.Detect(img)

    # Put detection info on the NetworkTable
    ntDetections = []
    for detection in detections:
        ntDetections.append({
            "Class": labels[detection.ClassID],
            "ClassID": detection.ClassID,
            "Instance": detection.Instance,
            "Area": detection.Area,
            "Bottom": detection.Bottom,
            "Center": detection.Center,
            "Confidence": detection.Confidence,
            "Height": detection.Height,
            "Left": detection.Left,
            "Right": detection.Right,
            "Top": detection.Top,
            "Width": detection.Width,
        })

    jetsonTable.putString("Detections", json.dumps(ntDetections))
    jetsonTable.putNumber("Network FPS", detectNet.GetNetworkFPS())

    # display.Render(img)
    # display.SetStatus("Object Detection | Network {:.0f} FPS".format(net.GetNetworkFPS()))

    # Resize the image on the GPU to lower resolution for more efficient streaming
    smallImg = jetson.utils.cudaAllocMapped(width=STREAM_WIDTH, height=STREAM_HEIGHT, format=img.format)
    jetson.utils.cudaResize(img, smallImg)
    del img

    # Convert color from rgb8 to bgr8 - CUDA uses rgb but OpenCV/CameraServer use bgr
    # Without this step, red and blue are inverted in the streamed image
    bgrSmallImg = jetson.utils.cudaAllocMapped(width=STREAM_WIDTH, height=STREAM_HEIGHT, format="bgr8")
    jetson.utils.cudaConvertColor(smallImg, bgrSmallImg)
    del smallImg

    # Synchronize so changes from GPU are available on CPU
    jetson.utils.cudaDeviceSynchronize()

    # Convert to from CUDA to Numpy/OpenGL 
    # https://github.com/dusty-nv/jetson-inference/blob/master/docs/aux-image.md#converting-to-numpy-arrays
    numpyImg = jetson.utils.cudaToNumpy(bgrSmallImg, STREAM_WIDTH, STREAM_HEIGHT, 4)

    # Send the image to the CameraServer
    csSource.putFrame(numpyImg)
    del numpyImg