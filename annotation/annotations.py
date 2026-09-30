import cv2
import json

IMAGE_PATH = "../images/img1.png"
OUTPUT_PATH = r"D:\minor project\testing\annotations\parking_slots.json"

image = cv2.imread(IMAGE_PATH)

points = []
slots = []
current_slot = 1


def mouse_callback(event, x, y, flags, param):
    global points

    if event == cv2.EVENT_LBUTTONDOWN:

        points.append([x, y])

        print(f"Point {len(points)}: ({x}, {y})")

        cv2.circle(image, (x, y), 5, (0, 255, 0), -1)

        if len(points) > 1:
            cv2.line(
                image,
                tuple(points[-2]),
                tuple(points[-1]),
                (0, 255, 0),
                2
            )

        cv2.imshow("Parking Slot Annotation", image)


cv2.namedWindow("Parking Slot Annotation")
cv2.setMouseCallback("Parking Slot Annotation", mouse_callback)

print("Click 4 corners for each parking slot.")
print("After 4 points, press ENTER to save the slot.")
print("Press ESC to finish.")

while True:

    cv2.imshow("Parking Slot Annotation", image)

    key = cv2.waitKey(1) & 0xFF

    # ENTER → save current slot
    if key == 13:

        if len(points) == 4:

            slots.append({
                "id": current_slot,
                "polygon": points.copy()
            })

            print(f"Slot {current_slot} saved!")

            current_slot += 1
            points = []

        else:
            print("You must select exactly 4 points.")

    # ESC → finish
    elif key == 27:
        break


cv2.destroyAllWindows()

# Create annotation data
data = {
    "image": "image1.jpg",
    "image_width": int(cv2.imread(IMAGE_PATH).shape[1]),
    "image_height": int(cv2.imread(IMAGE_PATH).shape[0]),
    "slots": slots
}

# Save JSON
with open(OUTPUT_PATH, "w") as f:
    json.dump(data, f, indent=4)

print("\nAnnotation saved!")
print(OUTPUT_PATH)