from utils import get_template_bubble_centers, print_image, draw_contours
import cv2
import numpy as np
from sklearn.neighbors import NearestNeighbors

def match_and_estimate_affine(detected_pts, template_pts, max_distance=50.0):
    det = np.array(detected_pts, dtype=np.float32)
    tmp = np.array(template_pts, dtype=np.float32)
    
    if len(det) < 2 or len(tmp) < 2:
        return None, None
    
    # 1. Fit NN model on template points
    nn = NearestNeighbors(n_neighbors=1, algorithm='kd_tree').fit(tmp)
    
    # 2. Find closest template point for every detected point
    distances, indices = nn.kneighbors(det)
    
    # 3. Filter out points that are too far away (outliers)
    valid_mask = distances.flatten() < max_distance
    
    matched_src = det[valid_mask]
    matched_dst = tmp[indices.flatten()[valid_mask]]
    
    # 4. Check if we have enough points left
    if len(matched_src) < 2:
        print("Error: Not enough matching points found.")
        return None, None
        
    matrix, inliers = cv2.estimateAffinePartial2D(matched_dst, matched_src, method=cv2.RANSAC)
    
    return matrix, inliers

def scan(img, final_w=2480, final_h=3508):
    img = cv2.resize(img, (final_w, final_h))
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5,5), 0)
    thresh = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel) 
    
    contours, _ = cv2.findContours(cleaned, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    
    contours_mask = np.zeros_like(gray)
    external_contours_mask = contours_mask.copy()
    
    filtered = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < 50 or area > 1000:
            continue
            
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.02*peri, True)
        
        # OPTIMIZATION: Compute bounding box once and cache it
        x, y, w, h = cv2.boundingRect(cnt)
        ar = w / h

        if len(approx) != 4 or ar < 0.7 or ar > 4:
            continue
        
        filtered.append(cnt)
        
    cv2.drawContours(contours_mask, filtered, -1, (255,255,255), 2)
    
    # Keeping your exact double-pass logic intact as requested
    external_contours, _ = cv2.findContours(contours_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(external_contours_mask, external_contours, -1, (255,255,255), 2)
    # print_image(external_contours_mask)
    
    # OPTIMIZATION: Extract bounding boxes directly without a redundant secondary loop computation
    rectangles = []
    for cnt in external_contours:
        x, y, w, h = cv2.boundingRect(cnt)
        rectangles.append((x + w // 2, y + h // 2))
        
    return np.array(rectangles, dtype=np.float32)

def get_bubble_coordinates(img, template_path):     
    template_pts = get_template_bubble_centers(template_path)
    detected_pts = scan(img)
         
    if len(detected_pts) > 0:
        matrix, _ = match_and_estimate_affine(detected_pts, template_pts)
        if matrix is not None:
            template_pts_3d = template_pts.reshape(-1, 1, 2)
            projected_pts_2d = cv2.transform(template_pts_3d, matrix).reshape(-1, 2)    
            
            return projected_pts_2d
        
    print("Error: Cannot get bubble coordinates.")
    return
         
if __name__ == "__main__":
    template_path = "./templates/CMS_mc_template.json"
    img_path = "./samples/scans/2B_11.png"
    
    img = cv2.imread(img_path)
    print(get_bubble_coordinates(img, template_path))