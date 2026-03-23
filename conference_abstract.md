# Conference Abstract

## A Dual-Camera Driver Assistance System Designed for Indian Road Conditions

---

**Abstract**

Driving in India is very different from driving in Western countries. Indian roads are full of cars, auto-rickshaws, two-wheelers, and pedestrians sharing the same space, often with faded lane markings and constant stop-and-go traffic. Most available ADAS systems are built for well-organized roads and fail to work reliably here. This paper presents a camera-only driver assistance system designed from the ground up for Indian traffic. It uses two cameras — a front dashcam for collision warning and lane detection, and a rear camera for blind spot detection and lane change guidance. The system does not need LiDAR or radar, making it affordable and easy to deploy.

The front camera detects vehicles in real time using the YOLOv8n object detection model. It then tracks each vehicle and estimates how quickly it is approaching by measuring how fast its bounding box is growing in the frame. A Time-to-Collision value is calculated using a simple pinhole camera model. To avoid unnecessary alerts in heavy traffic, the system raises or lowers its warning thresholds based on how many vehicles are around — so it stays quiet in a traffic jam but reacts sharply on an open highway. Lane boundaries are detected using a bird's-eye-view transform combined with sliding window search and Hough line detection, with smoothing over time to handle missing or unclear markings. The rear camera detects vehicles in the driver's blind spots by mapping them into 3D zones beside the lane boundaries and issues lane change advisories when the driver begins to drift. A separate module also watches for emergency vehicles by detecting flashing light patterns. All decisions use clear, rule-based logic instead of black-box classifiers, making the system easy to understand and trust. Tests on recorded Indian traffic videos show that the system runs in real time and produces far fewer false alarms than simple distance-based approaches.

**Keywords:** ADAS, Forward Collision Warning, Blind Spot Detection, Indian Traffic, Dual-Camera, YOLOv8, Lane Detection, Edge Computing
