import asyncio
import os

from app import db

import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Conv2D, MaxPooling2D, Flatten, Dense


def preprocess_image(image_path, image_size=(256, 256)):
    """Load the specified image and resize it to the target size."""
    image = tf.io.read_file(image_path)
    image = tf.image.decode_jpeg(image, channels=1)  # Use decode_png if your images are in PNG format
    image = tf.image.resize(image, image_size)
    image = image / 255.0  # Normalize to [0, 1]
    return image

async def load_dataset(image_size=(256, 256)):
  image_paths = []
  image_labels = []

  async with db.database:
    for unique_image in await db.UniqueImage.objects.all():
      if unique_image.has_architectural_page_number is None:
        continue
      image_paths.append(unique_image.local_filename)
      image_labels.append(unique_image.has_architectural_page_number)
    
  image_dataset = tf.data.Dataset.from_tensor_slices((image_paths, image_labels))
  image_dataset = image_dataset.map(lambda image_path, label: (preprocess_image(image_path, image_size), label))
  return image_dataset

def prepare_datasets(dataset, train_size=0.8, shuffle_buffer_size=1000, batch_size=32):
  """Shuffle and split the dataset into training and validation datasets."""
  dataset = dataset.shuffle(shuffle_buffer_size)
  train_dataset_size = int(len(dataset) * train_size)
  
  train_dataset = dataset.take(train_dataset_size)
  val_dataset = dataset.skip(train_dataset_size)
  
  return train_dataset.batch(batch_size), val_dataset.batch(batch_size)

async def train_drawing_detector():
  dataset = await load_dataset()
  train_dataset, val_dataset = prepare_datasets(dataset)

  # Build the CNN model
  model = Sequential([
      Conv2D(32, (3, 3), activation='relu', input_shape=(256, 256, 1)),
      MaxPooling2D(2, 2),
      Conv2D(64, (3, 3), activation='relu'),
      MaxPooling2D(2, 2),
      Flatten(),
      Dense(128, activation='relu'),
      Dense(2, activation='softmax')  # 2 classes: drawing or not
  ])

  # Compile the model
  model.compile(optimizer='adam', loss='sparse_categorical_crossentropy', metrics=['accuracy'])

  # Now you can use train_dataset in your model training
  model.fit(train_dataset, epochs=10, validation_data=val_dataset)


if __name__ == '__main__':
  import sys

  asyncio.run(train_drawing_detector())

  sys.exit()
