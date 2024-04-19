import asyncio

from app import db

import tensorflow as tf
from tensorflow.keras.models import Model
from tensorflow.keras.layers import Input, Conv2D, MaxPooling2D, Flatten, Dense, BatchNormalization, SpatialDropout2D, LeakyReLU
from sklearn.model_selection import train_test_split
import cv2
import numpy as np
from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint

def load_east_model(checkpoint_path):
  input_images = tf.placeholder(tf.float32, shape=[None, None, None, 3], name='input_images')
  is_training = tf.placeholder(tf.bool, name='is_training')
  f_score, f_geometry = east_model(input_images, is_training=is_training)
  saver = tf.train.Saver()
  sess = tf.Session()
  model_path = tf.train.latest_checkpoint(checkpoint_path)
  saver.restore(sess, model_path)
  return sess, input_images, f_score, f_geometry, is_training

def create_model(input_shape):
  inputs = Input(shape=input_shape)

  x = Conv2D(16, (3, 3), padding='same')(inputs)
  x = LeakyReLU(alpha=0.1)(x)
  x = BatchNormalization()(x)
  x = MaxPooling2D((2, 2))(x)
  x = SpatialDropout2D(0.25)(x)  # Add dropout after pooling

  x = Conv2D(32, (3, 3), padding='same')(x)
  x = LeakyReLU(alpha=0.1)(x)
  x = BatchNormalization()(x)
  x = MaxPooling2D((2, 2))(x)
  x = SpatialDropout2D(0.25)(x)  # Add dropout after pooling

  x = Conv2D(64, (3, 3), padding='same')(x)
  x = LeakyReLU(alpha=0.1)(x)
  x = BatchNormalization()(x)
  x = MaxPooling2D((2, 2))(x)
  x = SpatialDropout2D(0.25)(x)  # Add dropout after pooling

  x = Flatten()(x)
  x = Dense(128, activation='relu')(x)
  outputs = Dense(4, activation='sigmoid')(x)  # Outputs normalized coordinates

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
  train_images = np.array(train_images, dtype=np.float32)
  train_boxes = np.array(train_boxes, dtype=np.float32)
  val_images = np.array(val_images, dtype=np.float32)
  val_boxes = np.array(val_boxes, dtype=np.float32)

  east_model = load_east_model('/Users/harish/Downloads/east_icdar2015_resnet_v1_50_rbox/checkpoint')

  callbacks = [
      EarlyStopping(monitor='val_loss', patience=5, verbose=1),
      ModelCheckpoint('drawing_number_identifier.keras', monitor='val_loss', save_best_only=True)
  ]
  model = create_model(normalized_image_shape)
  model.fit(train_images, train_boxes, epochs=30, validation_data=(val_images, val_boxes), callbacks=callbacks)


if __name__ == '__main__':
  import sys

  pb_path = '/Users/harish/Downloads/frozen_east_text_detection.pb'
  model = tf.saved_model.load(pb_path)
  sys.exit()
  #sess, input_images, f_score, f_geometry


  asyncio.run(train_model())

  sys.exit()
