import shutil

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

  async with db.database:
    for unique_image in await db.UniqueImage.objects.select_related('unique_image_annotations').filter(has_architectural_page_number=True).all():
      if len(unique_image.unique_image_annotations) > 0:
        continue
      results = model(unique_image.local_filename)
      print(results)
      results[0].show()
      return



if __name__ == '__main__':
  import sys

  asyncio.run(run_drawing_inference())

  sys.exit()
