# Inserito il codice completo del BatchLabelProcessor
# (copia integrale dalla tua ultima versione)

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import os
from pathlib import Path
import argparse
import zipfile
import time
from tqdm import tqdm

class BatchLabelProcessor:
    def __init__(self, output_dir="output_crops"):
        self.edge_threshold = 195
        self.min_size = 100
        self.max_aspect_ratio = 5.0
        self.overlap_threshold = 0.1
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.supported_formats = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif'}
    def log(self, message):
        timestamp = time.strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")
    def sobel_edge_detection(self, gray_image):
        blurred = cv2.GaussianBlur(gray_image, (3, 3), 0)
        sobelx = cv2.Sobel(blurred, cv2.CV_64F, 1, 0, ksize=3)
        sobely = cv2.Sobel(blurred, cv2.CV_64F, 0, 1, ksize=3)
        magnitude = np.sqrt(sobelx**2 + sobely**2)
        edges = np.zeros_like(magnitude, dtype=np.uint8)
        edges[magnitude > self.edge_threshold] = 255
        return edges
    def find_connected_components(self, binary_image):
        contours, _ = cv2.findContours(binary_image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        rectangles = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            area = w * h
            if area < self.min_size * self.min_size: continue
            if w < self.min_size or h < self.min_size: continue
            aspect_ratio = max(w, h) / min(w, h)
            if aspect_ratio > self.max_aspect_ratio: continue
            contour_area = cv2.contourArea(contour)
            density = contour_area / area if area > 0 else 0
            if density < 0.1: continue
            rectangles.append({'x': x, 'y': y, 'width': w, 'height': h})
        return rectangles
    def remove_overlapping_rectangles(self, rectangles):
        if not rectangles: return rectangles
        rectangles.sort(key=lambda r: r['width'] * r['height'], reverse=True)
        filtered = []
        for current in rectangles:
            is_duplicate = False
            for existing in filtered:
                overlap = self.calculate_overlap(current, existing)
                if overlap > self.overlap_threshold:
                    is_duplicate = True; break
                if self.is_contained(current, existing) or self.is_contained(existing, current):
                    is_duplicate = True; break
            if not is_duplicate: filtered.append(current)
        return filtered
    def calculate_overlap(self, rect1, rect2):
        x1 = max(rect1['x'], rect2['x']); y1 = max(rect1['y'], rect2['y'])
        x2 = min(rect1['x'] + rect1['width'], rect2['x'] + rect2['width'])
        y2 = min(rect1['y'] + rect1['height'], rect2['y'] + rect2['height'])
        if x2 <= x1 or y2 <= y1: return 0.0
        intersection = (x2 - x1) * (y2 - y1)
        area1 = rect1['width'] * rect1['height']; area2 = rect2['width'] * rect2['height']
        return intersection / min(area1, area2)
    def is_contained(self, rect1, rect2):
        return (rect1['x'] >= rect2['x'] and rect1['y'] >= rect2['y'] and
                rect1['x'] + rect1['width'] <= rect2['x'] + rect2['width'] and
                rect1['y'] + rect1['height'] <= rect2['y'] + rect2['height'])
    def sort_rectangles(self, rectangles):
        if not rectangles: return rectangles
        rectangles.sort(key=lambda r: r['y'])
        if not rectangles: return rectangles
        rows, current_row = [], [rectangles[0]]
        row_tolerance = rectangles[0]['height'] * 0.3
        for rect in rectangles[1:]:
            if abs(rect['y'] - current_row[0]['y']) <= row_tolerance:
                current_row.append(rect)
            else:
                current_row.sort(key=lambda r: r['x']); rows.append(current_row); current_row = [rect]
        if current_row: current_row.sort(key=lambda r: r['x']); rows.append(current_row)
        result = []; [result.extend(row) for row in rows]
        return result
    def add_label_to_crop(self, crop_image, filename):
        if len(crop_image.shape) == 3:
            pil_image = Image.fromarray(cv2.cvtColor(crop_image, cv2.COLOR_BGR2RGB))
        else:
            pil_image = Image.fromarray(crop_image)
        draw = ImageDraw.Draw(pil_image)
        font_size = max(12, min(crop_image.shape[1] // 20, 18))
        try: font = ImageFont.truetype("arial.ttf", font_size)
        except: 
            try: font = ImageFont.load_default()
            except: font = None
        text = filename
        if font:
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]; text_height = bbox[3] - bbox[1]
        else:
            text_width, text_height = len(text) * 8, 16
        margin = 8
        label_x = margin; label_y = crop_image.shape[0] - text_height - margin - 8
        label_width = min(text_width + 16, crop_image.shape[1] - 2 * margin)
        label_height = text_height + 12
        draw.rectangle([label_x, label_y, label_x + label_width, label_y + label_height], fill='white', outline='black', width=1)
        text_x = label_x + 8; text_y = label_y + 6
        draw.text((text_x, text_y), text, fill='black', font=font)
        return cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
    def process_single_image(self, image_path, filename_stem):
        try:
            image = cv2.imread(str(image_path))
            if image is None: return []
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            edges = self.sobel_edge_detection(gray)
            kernel = np.ones((2, 2), np.uint8)
            edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
            edges = cv2.morphologyEx(edges, cv2.MORPH_DILATE, kernel, iterations=1)
            rectangles = self.find_connected_components(edges)
            if not rectangles: return []
            rectangles = self.remove_overlapping_rectangles(rectangles)
            rectangles = self.sort_rectangles(rectangles)
            crops_saved = []
            for i, rect in enumerate(rectangles):
                margin = 5
                x1 = max(0, rect['x'] - margin); y1 = max(0, rect['y'] - margin)
                x2 = min(image.shape[1], rect['x'] + rect['width'] + margin)
                y2 = min(image.shape[0], rect['y'] + rect['height'] + margin)
                crop = image[y1:y2, x1:x2]
                if crop.size == 0: continue
                labeled_crop = self.add_label_to_crop(crop, filename_stem)
                crop_filename = f"{filename_stem}_crop_{i+1:02d}.jpg"
                crop_path = self.output_dir / crop_filename
                cv2.imwrite(str(crop_path), labeled_crop, [cv2.IMWRITE_JPEG_QUALITY, 95])
                crops_saved.append(crop_path)
            return crops_saved
        except Exception as e:
            self.log(f"Errore elaborando {image_path}: {e}")
            return []
