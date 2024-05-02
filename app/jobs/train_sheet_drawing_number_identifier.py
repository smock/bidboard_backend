import asyncio
import random

from app import db

from sklearn.model_selection import train_test_split
import cv2
import numpy as np
from ultralytics import YOLO


async def load_image_and_boxes(path):
  idx = 0
  async with db.database:
    for anno in await db.UniqueImageAnnotation.objects.select_related('unique_image_id').filter(valid_roi=True).all():
      train_val = 'train' if random.random() < 0.7 else 'val'
      data_path = "%s/%s" % (path, train_val)

      image = cv2.imread(anno.unique_image_id.local_filename, cv2.IMREAD_GRAYSCALE)
      height, width = image.shape[:2]
      image = np.expand_dims(image, axis=-1)  # Add channel dimension

      x_center = (anno.page_number_x1 + anno.page_number_x2) * 0.5
      y_center = (anno.page_number_y1 + anno.page_number_y2) * 0.5
      box_width = anno.page_number_x2 - anno.page_number_x1
      box_height = anno.page_number_y2 - anno.page_number_y1

      image_path = "%s/images/image_%s.jpg" % (data_path, idx)
      cv2.imwrite(image_path, image)
      label_path = "%s/labels/image_%s.txt" % (data_path, idx)
      with open(label_path, 'w') as file:
        file.write(f'0 {x_center / width} {y_center / height} {box_width / width} {box_height / height}')
        file.write("\n")
      idx+=1


async def train_model():
  #await load_image_and_boxes('/Users/harish/data/bidboard_training_data/drawing_number_yolov8')
  # Load pre-trained model
  model = YOLO('/Users/harish/data/bidboard_training_data/drawing_number_yolov8/yolov8n.pt')

  # Fine-tuning
  results = model.train(data='/Users/harish/data/bidboard_training_data/drawing_number_yolov8/sheet_drawing_yolov8.yaml',
                        imgsz=2560,
                        epochs=200,
                        device='mps',
                        single_cls=True)



if __name__ == '__main__':
  import sys

  asyncio.run(train_model())

  sys.exit()
