import asyncio

from tensorflow.keras.models import load_model


def preprocess_image(image_path, image_size, augment=False):
  image = tf.io.read_file(image_path)
  image = tf.image.decode_png(image, channels=1)
  image = tf.image.resize(image, image_size[0:2])

  if augment:
    image = tf.image.random_flip_left_right(image)
    image = tf.image.random_flip_up_down(image)

  image = image / 255.0  # Normalize to [0, 1]
  return image

async def flag_drawings():
  model = load_model('best_architectural_drawing_model.keras')
  print(model.input_shape)
  async with db.database:
    for bid_file_image in await db.UniqueImage.objects.filter(has_architectural_page_number=None).all():
      preproccesed = preprocess_image(bid_file_image.local_filename, (512, 512))
      print(preproccesed.shape)
      predictions = model.predict(preprocessed)
      print(predictions)
      return


if __name__ == '__main__':
  import sys

  asyncio.run(flag_drawings())

  sys.exit()