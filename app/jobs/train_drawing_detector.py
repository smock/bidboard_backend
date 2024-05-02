import asyncio
import cv2

from app import db
from app.services.bid_file_annotation_service import BidFileAnnotationService

import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import GlobalAveragePooling2D, Dense, Input, Dropout, Layer
from tensorflow.keras.applications import ResNet50
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.models import load_model
import keras_tuner as kt
import numpy as np


def preprocess_image(image_path, image_size, augment=False):
  image = tf.io.read_file(image_path)
  image = tf.image.decode_png(image, channels=1)
  image = tf.image.resize(image, image_size[0:2])

  if augment:
    image = tf.image.random_flip_left_right(image)
    image = tf.image.random_flip_up_down(image)

  image = image / 255.0  # Normalize to [0, 1]
  return image

async def load_dataset(image_size=(512, 512, 1), augment=False):
  image_paths = []
  image_labels = []

  async with db.database:
    for unique_image in await db.UniqueImage.objects.all():
      if unique_image.has_architectural_page_number is None:
        continue
      image_paths.append(unique_image.local_filename)
      image_labels.append(unique_image.has_architectural_page_number)

  dataset = tf.data.Dataset.from_tensor_slices((image_paths, image_labels))
  dataset = dataset.map(lambda x, y: (preprocess_image(x, image_size, augment), y))
  if augment:
    dataset = dataset.map(lambda x, y: (tf.image.random_brightness(x, max_delta=0.1), y))
  return dataset

def prepare_datasets(dataset, batch_size, train_size=0.8, shuffle_buffer_size=1000):
  """Shuffle and split the dataset into training and validation datasets."""
  dataset = dataset.shuffle(shuffle_buffer_size)
  train_dataset_size = int(len(dataset) * train_size)
  
  train_dataset = dataset.take(train_dataset_size)
  val_dataset = dataset.skip(train_dataset_size)
  
  return train_dataset.batch(batch_size), val_dataset.batch(batch_size)

@tf.keras.utils.register_keras_serializable()
class GrayscaleToRGB(Layer):
    """Custom layer to convert grayscale images to RGB by replicating the channels."""
    def __init__(self, **kwargs):
        super(GrayscaleToRGB, self).__init__(**kwargs)
    
    def call(self, inputs):
        return tf.image.grayscale_to_rgb(inputs)

    def get_config(self):
        # Return the base config so that TensorFlow can handle the serialization and deserialization
        return super().get_config()

def build_model(hp):
    base_model = ResNet50(include_top=False, weights='imagenet', input_shape=(512, 512, 3))
    base_model.trainable = False
    model = Sequential([
        Input(shape=(512, 512, 1)),
        GrayscaleToRGB(),
        base_model,
        GlobalAveragePooling2D(),
        Dropout(rate=hp.Float('dropout_rate', min_value=0.0, max_value=0.5, step=0.1)),  # Narrowed range for dropout
        Dense(hp.Int('units', min_value=128, max_value=1024, step=128), activation='relu'),  # Fixed units
        Dense(2, activation='softmax')
    ])

    hp_learning_rate = hp.Float('learning_rate', min_value=1e-5, max_value=1e-2, sampling='log')  # Wider range for learning rate
    model.compile(optimizer=Adam(learning_rate=hp_learning_rate),
                  loss='sparse_categorical_crossentropy',
                  metrics=['accuracy'])
    return model

def tune_model(train_ds, val_ds):
    tuner = kt.Hyperband(build_model,
                         objective='val_accuracy',
                         max_epochs=10,
                         factor=3,
                         directory='/Users/harish/data/bidboard_models/model_tuning',
                         project_name='arch_draw_tuning_expanded_search')
    tuner.reload()  # This reloads the tuner from the saved directory
    best_model = tuner.get_best_models(num_models=1)[0]
    return best_model
    tuner.search(train_ds, validation_data=val_ds, epochs=10)
    best_model = tuner.get_best_models(num_models=1)[0]
    return best_model

def build_fixed_model():
  # Base model, not trainable
  base_model = ResNet50(include_top=False, weights='imagenet', input_shape=(512, 512, 3))
  base_model.trainable = False

  # Complete model architecture
  model = Sequential([
      Input(shape=(512, 512, 1)),
      tf.keras.layers.Lambda(lambda x: tf.image.grayscale_to_rgb(x)),  # Convert grayscale to RGB
      base_model,
      GlobalAveragePooling2D(),
      Dropout(rate=0.05),  # Fixed dropout rate
      Dense(512, activation='relu'),  # Fixed number of units in the Dense layer
      Dense(2, activation='softmax')  # Output layer
  ])

  # Fixed learning rate
  learning_rate = 0.001
  model.compile(optimizer=Adam(learning_rate=learning_rate),
                loss='sparse_categorical_crossentropy',
                metrics=['accuracy'])
  
  return model

def train_fixed_model(train_ds, val_ds):
    # Build the model
    model = build_fixed_model()
        
    # Train the model
    history = model.fit(train_ds, validation_data=val_ds, epochs=10)
    return model


async def train_drawing_detector(batch_size, augment):
  dataset = await load_dataset(augment=augment)
  train_dataset, val_dataset = prepare_datasets(dataset, batch_size)

  best_model = tune_model(train_dataset, val_dataset)
  best_model.save('/Users/harish/data/bidboard_models/dropout_tuned_drawing_model_optimized.keras')
  #best_model = train_fixed_model(train_dataset, val_dataset)
  #best_model.save('/Users/harish/data/bidboard_models/dropout_tuned_drawing_model_optimized.keras')


async def flag_drawings():
  #print(build_fixed_model().summary())
  #model = load_model('/Users/harish/data/bidboard_models/dropout_tuned_drawing_model_optimized.keras', custom_objects={'GrayscaleToRGB': GrayscaleToRGB})
  model = tune_model([], [])
  #print(model.summary())
  #bfas = BidFileAnnotationService(db.database)  
  async with db.database:
    for bid_file_image in await db.UniqueImage.objects.all():
      preproccesed = preprocess_image(bid_file_image.local_filename, (512, 512))
      [[no_drawing, yes_drawing]] = model.predict(np.expand_dims(preproccesed, axis=0))
      bid_file_image.architectural_page_number_probability = yes_drawing
      await bid_file_image.update()
      if yes_drawing <= no_drawing:
         continue
      #await bfas.flag_architectural_page_number(bid_file_image)


if __name__ == '__main__':
  import sys

  #asyncio.run(train_drawing_detector(32, False))
  asyncio.run(flag_drawings())

  sys.exit()