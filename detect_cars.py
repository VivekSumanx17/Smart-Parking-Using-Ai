from ultralytics import YOLO
import cv2
import json
import numpy as np
from shapely.geometry import Polygon, box

# -----------------------------
# PATHS
# -----------------------------
IMAGE_PATH = r"D:\minor project\testing\images\overlap3.png"

ANNOTATION_PATH = r"D:\minor project\testing\annotations\parking_slots.json"

# -----------------------------
# LOAD IMAGE
# -----------------------------
image = cv2.imread(IMAGE_PATH)

if image is None:
    print("ERROR: Image could not be loaded!")
    exit()

# -----------------------------
# LOAD PARKING SLOT ANNOTATIONS
# -----------------------------
with open(ANNOTATION_PATH, "r") as f:
    data = json.load(f)

slots = data["slots"]

# -----------------------------
# LOAD YOLO
# -----------------------------
model = YOLO("yolo11n.pt")

# Detect only cars
results = model(image, classes=[2])

# -----------------------------
# STORE CAR BOXES
# -----------------------------
car_boxes = []

for result in results:

    for detected_box in result.boxes:

        confidence = float(detected_box.conf[0])

        x1, y1, x2, y2 = map(
            int,
            detected_box.xyxy[0]
        )

        car_boxes.append(
            (x1, y1, x2, y2, confidence)
        )

# -----------------------------
# CHECK EACH PARKING SLOT
# -----------------------------
occupied_slots = []
empty_slots = []

for slot in slots:

    slot_id = slot["id"]
    points = slot["polygon"]

    # Create parking polygon
    parking_polygon = Polygon(points)

    occupied = False

    for x1, y1, x2, y2, confidence in car_boxes:

        # Create car bounding box
        car_box = box(x1, y1, x2, y2)

        # Calculate intersection
        intersection = parking_polygon.intersection(car_box)

        # Calculate how much of the parking slot is covered
        overlap = intersection.area / parking_polygon.area

        # Threshold
        if overlap > 0.50:
            occupied = True
            break

    # -----------------------------
    # DRAW RESULT
    # -----------------------------

    polygon_np = np.array(points, np.int32)

    if occupied:

        occupied_slots.append(slot_id)

        # Red polygon
        cv2.polylines(
            image,
            [polygon_np],
            True,
            (0, 0, 255),
            3
        )

        status = "OCCUPIED"

    else:

        empty_slots.append(slot_id)

        # Green polygon
        cv2.polylines(
            image,
            [polygon_np],
            True,
            (0, 255, 0),
            3
        )

        status = "EMPTY"

    # -----------------------------
    # SLOT NUMBER
    # -----------------------------

    center_x = int(
        sum(p[0] for p in points) / len(points)
    )

    center_y = int(
        sum(p[1] for p in points) / len(points)
    )

    cv2.putText(
        image,
        f"Slot {slot_id}",
        (center_x - 30, center_y - 10),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (255, 255, 255),
        2
    )

    cv2.putText(
        image,
        status,
        (center_x - 40, center_y + 15),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.45,
        (255, 255, 255),
        2
    )

# -----------------------------
# DRAW CAR BOXES
# -----------------------------

for x1, y1, x2, y2, confidence in car_boxes:

    cv2.rectangle(
        image,
        (x1, y1),
        (x2, y2),
        (255, 0, 0),
        2
    )

# -----------------------------
# SUMMARY
# -----------------------------

occupied_count = len(occupied_slots)
empty_count = len(empty_slots)

print("\n==============================")
print("      SMART PARKING RESULT")
print("==============================")

print(f"Total Slots : {len(slots)}")

print(f"Occupied    : {occupied_count}")
print(f"Empty       : {empty_count}")

print("\nOccupied Slots:")
print(occupied_slots)

print("\nEmpty Slots:")
print(empty_slots)

print("==============================")

# -----------------------------
# SHOW IMAGE
# -----------------------------

cv2.imshow("Smart Parking", image)

cv2.waitKey(0)
cv2.destroyAllWindows()