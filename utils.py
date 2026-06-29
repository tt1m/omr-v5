import imutils
import cv2
import numpy as np
import json

def print_image(img):
    resized = imutils.resize(img, height=750)
    cv2.imshow("image", resized)
    cv2.waitKey(0)

def draw_contours(img, contours):
    cloned = img.copy()
    cv2.drawContours(cloned, contours, -1, (0,255,0), 2)
    return cloned

def auto_resize(image, target_width, target_height):
    orig_h, orig_w = image.shape[:2]
    
    # If either target dimension is smaller than the original, we are downscaling
    if target_width < orig_w or target_height < orig_h:
        # INTER_AREA is mathematically superior for shrinking (prevents moiré/aliasing)
        interpolation = cv2.INTER_AREA
    else:
        # INTER_CUBIC is slower but creates smoother edges when enlarging
        interpolation = cv2.INTER_CUBIC
        
    return cv2.resize(image, (target_width, target_height), interpolation=interpolation)


def fix_coords(coordinates):
    coordinates = np.array(coordinates, dtype=np.float32)
    fixed_coordinates = np.zeros((4, 2), dtype=np.float32)

    s = coordinates.sum(axis=1)
    fixed_coordinates[0] = coordinates[np.argmin(s)]  # top-left  (min x+y)
    fixed_coordinates[2] = coordinates[np.argmax(s)]  # bottom-right (max x+y)

    diff = np.diff(coordinates, axis=1).ravel()  # y - x
    fixed_coordinates[1] = coordinates[np.argmin(diff)]  # top-right (min y-x)
    fixed_coordinates[3] = coordinates[np.argmax(diff)]  # bottom-left (max y-x)

    return fixed_coordinates

def draw_template(img, template_path):
    with open(template_path, 'r', encoding="utf-8") as file:
      template = json.load(file)

    fields = template["fields"]
    for field in fields:
        bubble_config = field["bubble"]
        bubble_shape = bubble_config["shape"]
        bubble_width = bubble_config["width"]
        bubble_height = bubble_config["height"]
        
        entries = field["entries"]
        for entry in entries:
            bubbles = entry["bubbles"]
            if bubble_shape == "rectangle":
                for bubble in bubbles:
                    x = bubble["x"]
                    y = bubble["y"]
                    point_top_left = (x, y)
                    point_bottom_right = (x + bubble_width, y + bubble_height)
                    cv2.rectangle(img, point_top_left, point_bottom_right, (255,255,0), 3)
                    
    print_image(img)
    
def get_template_bubble_centers(template_path):
    bubble_centers = []

    with open(template_path, 'r', encoding="utf-8") as file:
      template = json.load(file)

    fields = template["fields"]
    for field in fields:
        bubble_config = field["bubble"]
        bubble_shape = bubble_config["shape"]
        bubble_width = bubble_config["width"]
        bubble_height = bubble_config["height"]
        
        entries = field["entries"]
        for entry in entries:
            bubbles = entry["bubbles"]
            if bubble_shape == "rectangle":
                for bubble in bubbles:
                    x = bubble["x"]
                    y = bubble["y"]
                    bubble_centers.append((x + bubble_width // 2, y + bubble_height // 2)) 
    
    return np.array(bubble_centers, dtype=np.float32)