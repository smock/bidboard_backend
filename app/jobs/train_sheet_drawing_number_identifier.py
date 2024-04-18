import asyncio
import os

from app import db

import tensorflow as tf
from tensorflow.keras.models import Model
from tensorflow.keras.layers import Input, Conv2D, MaxPooling2D, Flatten, Dense
from sklearn.model_selection import train_test_split
import cv2
import numpy as np

def create_model(input_shape):
    inputs = Input(shape=input_shape)

    # Simple Convolutional Base
    x = Conv2D(16, (3, 3), activation='relu', padding='same')(inputs)
    x = MaxPooling2D((2, 2))(x)
    x = Conv2D(32, (3, 3), activation='relu', padding='same')(x)
    x = MaxPooling2D((2, 2))(x)
    x = Conv2D(64, (3, 3), activation='relu', padding='same')(x)
    x = MaxPooling2D((2, 2))(x)

    # Dense layers for prediction
    x = Flatten()(x)
    x = Dense(128, activation='relu')(x)
    outputs = Dense(4, activation='sigmoid')(x)  # Predicting 4 coordinates

    model = Model(inputs=inputs, outputs=outputs)
    model.compile(optimizer='adam', loss='mse')
    
    return model

async def load_image_and_boxes(normalized_image_shape):
  image_filenames = []
  boxes = []
  images = []
  scaled_boxes = []
  async with db.database:
    for unique_image_annotation in await db.UniqueImageAnnotation.objects.select_related('unique_image_id').filter(valid=True).all():
      image_filenames.append(unique_image_annotation.unique_image_id.local_filename)
      boxes.append([
        unique_image_annotation.page_number_x1,
        unique_image_annotation.page_number_y1,
        unique_image_annotation.page_number_x2,
        unique_image_annotation.page_number_y2,
      ])

  for i, image_filename in enumerate(image_filenames):
    image = cv2.imread(image_filename, cv2.IMREAD_GRAYSCALE)
    height, width = image.shape[:2]
    image = cv2.resize(image, (normalized_image_shape[1], normalized_image_shape[0]))  # Resize the image
    image = image / 255.0  # Normalize to range [0, 1]
    image = np.expand_dims(image, axis=-1)  # Add channel dimension
    images.append(image)

    scaled_boxes.append([
        boxes[i][0] / width,
        boxes[i][1] / height,
        boxes[i][2] / width,
        boxes[i][3] / height
    ])

  return images, scaled_boxes

async def train_model():
  normalized_image_shape = (512, 512, 1)
  images, boxes = await load_image_and_boxes(normalized_image_shape)
  train_images, val_images, train_boxes, val_boxes = train_test_split(images, boxes, test_size=0.2, random_state=42)

  # Create and train the model
  model = create_model(normalized_image_shape)
  model.fit(train_images, train_boxes, epochs=10, validation_data=(val_images, val_boxes))


if __name__ == '__main__':
  import sys

  asyncio.run(train_model())

  sys.exit()
