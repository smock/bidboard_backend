import math

import asyncio
import random

from app import db

from sklearn.model_selection import train_test_split
import cv2
import numpy as np
from ultralytics import YOLO



async def run_drawing_inference():
  # Load pre-trained model
  model = YOLO('/Users/harish/data/bidboard_training_data/drawing_number_yolov8/inference.pt')
  idx = 0
  async with db.database:
    for unique_image in await db.UniqueImage.objects.select_related('unique_image_annotations').filter(has_architectural_page_number=True).all():
      valid_roi = [anno for anno in unique_image.unique_image_annotations if anno.valid_roi == True]
      if len(valid_roi) > 0:
        continue
      results = model(unique_image.local_filename)
      if len(results[0].boxes.data) == 0:
        print("Couldn't identify annotation for %s" % unique_image.local_filename)
        continue
      for i, _d in enumerate(results[0].boxes.data):
        annotation = db.UniqueImageAnnotation.construct(unique_image_id=unique_image.id)
        annotation.page_number = 'a'
        annotation.page_number_x1 = math.floor(results[0].boxes.xyxy[i][0].item())
        annotation.page_number_x2 = math.floor(results[0].boxes.xyxy[i][2].item())
        annotation.page_number_y1 = math.floor(results[0].boxes.xyxy[i][1].item())
        annotation.page_number_y2 = math.floor(results[0].boxes.xyxy[i][3].item())
        annotation.annotation_source = db.AnnotationSource.YOLO_MODEL_V1.value
        annotation.confidence = results[0].boxes.conf[i].item()
        await annotation.save()
        idx += 1



if __name__ == '__main__':
  import sys

  asyncio.run(run_drawing_inference())

  sys.exit()
