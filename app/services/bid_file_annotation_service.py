import asyncio
import os
import hashlib
import io

from databases import Database
from pdf2image import convert_from_path
from pdf2image.exceptions import PDFPageCountError
from pathlib import Path
import cv2
import numpy as np
import pytesseract
from PIL import Image
import qasync
from PyQt5.QtWidgets import QApplication, QLabel, QWidget, QVBoxLayout
from PyQt5.QtGui import QPixmap, QPainter, QPen
from PyQt5.QtCore import Qt, QPoint, QTimer, QRect

from app import db

Image.MAX_IMAGE_PIXELS = None

class BoundingBoxApp(QWidget):
    def __init__(self, imagePath):
        super().__init__()
        self.imagePath = imagePath
        self.initUI()

    def initUI(self):
        self.setWindowTitle("Bounding Box Drawer")
        self.setGeometry(100, 100, 800, 600)

        self.layout = QVBoxLayout()
        self.imageLabel = QLabel(self)
        self.imageLabel.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.imageLabel)
        self.setLayout(self.layout)
        QTimer.singleShot(100, self.loadImage)  # Load image after everything is initialized

    def loadImage(self):
        self.pixmap = QPixmap(self.imagePath)
        self.scaledPixmap = self.pixmap.scaled(self.imageLabel.size(), Qt.KeepAspectRatio)
        self.imageLabel.setPixmap(self.scaledPixmap)
        self.imageLabel.setContentsMargins(0, 0, 0, 0)  # No margins
        self.imageLabel.setAlignment(Qt.AlignTop | Qt.AlignLeft)  # Align to the top left

        # Initializing drawing state
        self.startPoint = QPoint()
        self.endPoint = QPoint()
        self.drawing = False

        # Connect mouse events
        self.imageLabel.mousePressEvent = self.mousePressEvent
        self.imageLabel.mouseMoveEvent = self.mouseMoveEvent
        self.imageLabel.mouseReleaseEvent = self.mouseReleaseEvent

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drawing = True
            self.startPoint = event.pos()
            self.endPoint = event.pos()  # Initialize endPoint to be the start to ensure proper rectangle drawing

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and self.drawing:
            self.endPoint = event.pos()
            self.updateDrawing()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drawing = False
            self.endPoint = event.pos()
            self.updateDrawing()

    def updateDrawing(self):
        tempPixmap = self.scaledPixmap.copy()
        painter = QPainter(tempPixmap)
        pen = QPen(Qt.red, 2, Qt.SolidLine)
        painter.setPen(pen)
        rect = QRect(self.startPoint, self.endPoint)
        painter.drawRect(rect)
        self.imageLabel.setPixmap(tempPixmap)

class BidFileAnnotationService:
  LOCAL_FILENAME_PATH = '/Users/harish/data/bidboard_images'

  def __init__(self, db: Database):
    self.db = db

  async def upsert_bid_file_image(self, bid_file, page_number, local_filename, md5_hash):
    unique_image = await db.UniqueImage.objects.get_or_none(md5_hash=md5_hash)
    if unique_image is None:
      unique_image = db.UniqueImage.construct(
        md5_hash=md5_hash,
        local_filename=local_filename
      )
      await unique_image.save()
    else:
      print("Found dupe image %s" % md5_hash)
    created = True
    bid_file_image = await db.BCBidFileImage.objects.get_or_none(
      bc_bid_file_id=bid_file.id,
      page_number=page_number
    )
    if bid_file_image is None:
      created = False
      bid_file_image = db.BCBidFileImage.construct(bc_bid_file_id=bid_file.id, page_number=page_number)
    bid_file_image.unique_image_id=unique_image.id
    if created is False:
      await bid_file_image.save()
    else:
      await bid_file_image.update()
    
    return bid_file_image

  async def extract_images(self, bid_file, dpi=300, force=False):
    if bid_file.local_filename is None or bid_file.mime_type != 'application/pdf':
      return

    if bid_file.images_extracted and not force:
      return

    try:
      pages = convert_from_path(bid_file.local_filename, dpi=dpi)
    except PDFPageCountError:
      print("Could not extract pages from %s" % bid_file.id)
      return
    for i, page in enumerate(pages):
      page_number = i + 1

      hasher = hashlib.md5()
      img_byte_arr = io.BytesIO()
      page.save(img_byte_arr, format='PNG')  # You can choose PNG or other formats depending on the image
      img_byte_arr = img_byte_arr.getvalue()
      hasher.update(img_byte_arr)
      md5_hash = hasher.hexdigest()
      image_path = os.path.join(BidFileAnnotationService.LOCAL_FILENAME_PATH, md5_hash)
      page.save(image_path, 'PNG')
      await self.upsert_bid_file_image(bid_file, page_number, image_path, md5_hash)
      print(f"Saved: {image_path}")
    
    bid_file.images_extracted = True
    await bid_file.update()

    return bid_file
  
  async def flag_architectural_page_number(self, bid_file_image):
    image = cv2.imread(bid_file_image.local_filename)
    cv2.imshow('Does this have an architectural page number?', image)
    key = cv2.waitKey(0)
    if key == ord('y'):
      bid_file_image.has_architectural_page_number = True
    elif key == ord('n'):
      bid_file_image.has_architectural_page_number = False
    else:
      bid_file_image.has_architectural_page_number = None
    print("image %s - %s" % (bid_file_image.local_filename, bid_file_image.has_architectural_page_number))
    await bid_file_image.update()
    cv2.destroyAllWindows()

  def extract_coordinates_from_ocr_result(self, ocr_result, idx, border_size):
    return {
      'left': ocr_result['left'][idx] - border_size,
      'top': ocr_result['top'][idx] - border_size,
      'right': ocr_result['left'][idx] - border_size + ocr_result['width'][idx],
      'bottom': ocr_result['top'][idx] - border_size + ocr_result['height'][idx]
    }

  def extract_page_number(self, binary_inverted_image, psm=12, debug=False):
    # Get the dimensions of the image
    _, width = binary_inverted_image.shape[:2]

    kernel = np.ones((3, 3), np.uint8)
    dilation = cv2.dilate(binary_inverted_image, kernel, iterations=1)
    reverted_dilation = cv2.bitwise_not(dilation)

    border_size = width
    bordered_image = cv2.copyMakeBorder(reverted_dilation, border_size, border_size, border_size, border_size, cv2.BORDER_CONSTANT, value=[255, 255, 255])

    page_number_text = None
    page_number_coordinates = None
    # Perform OCR on the cropped image
    custom_config = "--oem 1 --psm %s" % psm
    ocr_result = pytesseract.image_to_data(Image.fromarray(bordered_image), output_type=pytesseract.Output.DICT, config=custom_config)
    
    bordered_height, bordered_width = bordered_image.shape[:2]
    # Initialize variables to track the largest font size and its location
    # Find the Largest Font Sized Text
    if debug:
      print(ocr_result)
      cv2.imshow("page num bordered image", bordered_image)
      cv2.waitKey(0)
      cv2.destroyAllWindows()

    page_number_index = None
    heights = []
    for i in range(len(ocr_result['text'])):
      text = ocr_result['text'][i]
      if len(text.strip()) > 0 and int(ocr_result['conf'][i]) > 0:
        heights.append(ocr_result['height'][i])
    heights = sorted(heights)
    if len(heights) == 0:
      return None, None

    mean = np.mean(heights)
    std_dev = np.std(heights)
    heights = [height for height in heights if height < mean + 3 * std_dev]
    if len(heights) == 0:
      return None, None

    height_cutoff = int(heights[-1] * .75)
    candidates = []
    tops = []
    for i in range(len(ocr_result['text'])):
      text = ocr_result['text'][i]
      top = ocr_result['top'][i]
      height = ocr_result['height'][i]
      if height > height_cutoff and \
        len(text.strip()) > 0 and \
        int(ocr_result['conf'][i]) > 0 and \
        any(char.isdigit() for char in text):
        tops.append(top)
        candidates.append(i)

    if len(candidates) == 1:
      page_number_index = candidates[0]
    elif len(candidates) > 0:
      # going to pick the largest one halfway down the page
      max_size = 0
      print("searching candidates")
      for candidate in candidates:
        top = ocr_result['top'][candidate]
        print(ocr_result['text'][candidate])
        print(str(top) + ' ' + str(bordered_height))
        if top < bordered_height * .5:
          continue
        font_size = ocr_result['height'][candidate]
        if font_size > max_size:
          max_size = font_size
          page_number_index = candidate
      if page_number_index is None:
        # just choose the largest one
        max_size = 0
        for candidate in candidates:
          font_size = ocr_result['height'][candidate]
          if font_size > max_size:
            max_size = font_size
            page_number_index = candidate

    if page_number_index:
      page_number_text = ocr_result['text'][page_number_index]
      page_number_coordinates = self.extract_coordinates_from_ocr_result(
        ocr_result,
        page_number_index, 
        border_size
      )
    return page_number_text, page_number_coordinates


  def display_images_side_by_side(self, image1, title1, image2, title2):
    height1, width1 = image1.shape[:2]
    height2, width2 = image2.shape[:2]
    height_scale_factor = height1/height2
    width_scale_factor = width1/width2
    scale_factor = height_scale_factor if height_scale_factor < width_scale_factor else width_scale_factor
    new_width = int(width2 * scale_factor)
    new_height = int(height2 * scale_factor)
    scaled_image2 = cv2.resize(image2, (new_width, new_height), interpolation=cv2.INTER_LINEAR)

    height2, width2 = scaled_image2.shape[:2]

    top = (height1 - height2) // 2 if height1 > height2 else 0
    bottom = height1 - height2 - top if height1 > height2 else 0
    left = (width1 - width2) // 2 if width1 > width2 else 0
    right = width1 - width2 - left if width1 > width2 else 0

    adjusted_image2 = cv2.copyMakeBorder(scaled_image2, top, bottom, left, right, cv2.BORDER_CONSTANT, value=[0, 0, 0])
    combined = np.hstack((image1, adjusted_image2))
    cv2.imshow(f'{title1} | {title2}', combined)


  def identify_page_number_from_sidepanel(self, cv2_image, panel_coords, debug=False):
    sidepanel = cv2_image[panel_coords['top']:panel_coords['bottom'], panel_coords['left']:panel_coords['right']]

    if debug:
      cv2.imshow('processing sidepanel', sidepanel)
      cv2.waitKey(0)
      cv2.destroyAllWindows()

    height, width = sidepanel.shape[:2]
    # most of the info we want is on the bottom quarter
    cropped_sidepanel = sidepanel[int(3 * height/4):height, 0:width]
    # Convert from BGR (OpenCV default) to gray
    sidepanel_gray = cv2.cvtColor(cropped_sidepanel, cv2.COLOR_BGR2GRAY)
    # Apply a binary threshold to get a binary inverted image
    _, binary_inverted_sidepanel = cv2.threshold(sidepanel_gray, 0, 255, cv2.THRESH_BINARY_INV)

    page_number_text, page_number_coordinates = self.extract_page_number(binary_inverted_sidepanel, debug=debug)
    if page_number_coordinates:
      page_number_coordinates = {
        'left': page_number_coordinates['left'] + panel_coords['left'],
        'right': page_number_coordinates['right'] + panel_coords['left'],
        'top': page_number_coordinates['top'] + panel_coords['top'] + int(3 * height/4),
        'bottom': page_number_coordinates['bottom'] + panel_coords['top'] + int(3 * height/4)
      }
    return page_number_text, page_number_coordinates

  def identify_panels(self, cv2_image, debug=False):
    panels = []
    height, width = cv2_image.shape[:2]

    # Convert to grayscale
    gray = cv2.cvtColor(cv2_image, cv2.COLOR_BGR2GRAY)
    _, binary_image = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV)
    if debug:
      cv2.imshow('binary', binary_image)
      cv2.waitKey(0)
      cv2.destroyAllWindows()

    # Apply dilation to close gaps in the boundaries
    kernel = np.ones((10, 10), np.uint8)
    dilation = cv2.dilate(binary_image, kernel, iterations=1)
    if debug:
      cv2.imshow('dilation', dilation)
      cv2.waitKey(0)
      cv2.destroyAllWindows()

    # crop into the region formed by the top most and bottom most horizontal lines
    lines = cv2.HoughLinesP(dilation, 1, np.pi / 180, threshold=100, minLineLength=int(width * 0.8), maxLineGap=10)
    if lines is None:
      print("could not find horizontal line candidates")
      return panels
    horizontal_lines = []
    for line in lines:
      x1, y1, x2, y2 = line[0]
      if abs(y2 - y1) < 10: # checking if the line is horizontal
        horizontal_lines.append((x1, y1, x2, y2))
    # Sort the horizontal lines by y coordinate
    if len(horizontal_lines) == 0:
      print("Could not extract horizontal lines")
      return panels
    horizontal_lines = sorted(horizontal_lines, key=lambda x: x[1])

    vertically_bounded_dilation = None
    vertically_bounded_roi = None
    top = None
    bottom = None
    for i in range(0, len(horizontal_lines) - 1):
      _, y1, _, _ = horizontal_lines[i]
      _, y2, _, _ = horizontal_lines[i + 1]
      if y2 == y1+1:
        continue
      # Compute region of interest
      roi = cv2_image[y1:y2,:]
      # Check if the region is not mostly empty
      white_pixels = cv2.countNonZero(cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY))
      total_pixels = roi.shape[0] * roi.shape[1]
      if white_pixels < (total_pixels * 0.999):
        if top is None:
          top = y1
          bottom = y2
        else:
          bottom = y2
      if debug:
        print(y1)
        print(y2)
        print(white_pixels)
        print(total_pixels)
        print(top)
        print(bottom)
        cv2.imshow('evaluating dilation', roi)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    if debug:
      print(top)
      print(bottom)

    # extract the region of interest
    vertically_bounded_roi = cv2_image[top:bottom,:]
    kernel = np.ones((10, 10), np.uint8)
    vertically_bounded_dilation = cv2.dilate(binary_image[top:bottom,:], kernel, iterations=1)
    height, width = vertically_bounded_roi.shape[:2]
    if debug:
      print('---')
      print(top)
      print(bottom)
      cv2.imshow('vertically bounded dilation', vertically_bounded_dilation)
      cv2.waitKey(0)
      cv2.destroyAllWindows()

    # Apply edge detection (e.g., Canny)
    edges = cv2.Canny(vertically_bounded_dilation, 50, 150, apertureSize=3)
    if debug:
      cv2.imshow('edges', edges)
      cv2.waitKey(0)
      cv2.destroyAllWindows()

    # Detect lines
    lines = cv2.HoughLinesP(edges, rho=1, theta=np.pi / 180, threshold=int(height * 0.8), minLineLength=100, maxLineGap=10)

    #lines = cv2.HoughLinesP(vertically_bounded_dilation, 1, np.pi / 180, threshold=100, minLineLength=int(height * 0.9), maxLineGap=10)
    if lines is None:
      print("could not find vertical candidate lines")
      return panels

    vertical_lines = []
    # Iterate over the points and draw the largest vertical line on the original image
    for line in lines:
      x1, y1, x2, y2 = line[0]
      if abs(x2 - x1) < 10: # checking if the line is vertical
        vertical_lines.append((x1, y1, x2, y2))
    if len(vertical_lines) == 0:
      if debug:
        print(lines)
      print("could not find vertical lines")
      return panels
    # Sort the vertical lines by the x coordinate
    vertical_lines = sorted(vertical_lines, key=lambda x: x[0])
    if debug:
      print(vertical_lines)
    # Now we'll look for the rightmost region between two vertical lines which isn't mostly empty
    panels = []
    for i in range(0, len(vertical_lines)):
        x1, _, _, _ = vertical_lines[i]
        # special case last line
        if i == len(vertical_lines) - 1:
          x2 = width
        else:
          x2, _, _, _ = vertical_lines[i + 1]
        # ignore small regions ( < 5% of the width)
        if (x2 - x1) < 0.05 * width:
          if debug:
            print("---")
            print("ignoring region")
            print(x1)
            print(x2)
            if x2 > x1 + 1:
              cv2.imshow('ignoring region', vertically_bounded_roi[:, x1:x2])
              cv2.waitKey(0)
              cv2.destroyAllWindows()
              print('--')
          continue
        # Compute region of interest
        roi = vertically_bounded_roi[:, x1:x2]
        white_pixels = cv2.countNonZero(cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY))
        total_pixels = roi.shape[0] * roi.shape[1]
        # Check if the region is not mostly empty
        if white_pixels < (total_pixels * 0.999):
          if debug:
            print(white_pixels)
            print(total_pixels)
            cv2.imshow('qualified vertical region', roi)
            cv2.waitKey(0)
            cv2.destroyAllWindows()
          panels.append({'left': x1, 'right': x2, 'top': top, 'bottom': bottom})
        else:
          if debug:
            cv2.imshow('unqualified vertical region', roi)
            cv2.waitKey(0)
            cv2.destroyAllWindows()

    if debug:
      for panel in panels:
        panel_image = cv2_image[panel['top']:panel['bottom'], panel['left']:panel['right']]
        cv2.imshow('panel', panel_image)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    return panels

  async def annotate_page_number(self, bid_file_image, force=False):
    created = True
    annotation = await db.UniqueImageAnnotation.objects.get_or_none(unique_image_id=bid_file_image.id)
    if annotation is not None and not force:
      return
    if annotation is None:
      created = False
      annotation = db.UniqueImageAnnotation.construct(unique_image_id=bid_file_image.id)

    cv2_image = cv2.imread(bid_file_image.local_filename, cv2.IMREAD_COLOR)
    panels = self.identify_panels(cv2_image)
    if len(panels) < 2:
      print("Could not find sidepanels")
      return None

    sidepanel = panels[-1]
    page_number_text, page_number_coordinates = self.identify_page_number_from_sidepanel(cv2_image, sidepanel)
    if page_number_text:
      annotation.page_number = page_number_text
      annotation.page_number_x1 = page_number_coordinates['left']
      annotation.page_number_x2 = page_number_coordinates['right']
      annotation.page_number_y1 = page_number_coordinates['top']
      annotation.page_number_y2 = page_number_coordinates['bottom']
      if created:
        await annotation.update()
      else:
        await annotation.save()
      return annotation
    elif created:
      if not annotation.valid: # protect valid annotations
        await annotation.destroy()

  async def manually_annotate_page_number(self, bid_file_image, force=False):
    created = True
    annotation = await db.UniqueImageAnnotation.objects.get_or_none(unique_image_id=bid_file_image.id, valid=True)
    if annotation is not None:
      return
    annotation = db.UniqueImageAnnotation.construct(unique_image_id=bid_file_image.id)
    app = QApplication([])
    #loop = qasync.QEventLoop(app)
    #asyncio.set_event_loop(loop)
    viewer = BoundingBoxApp(bid_file_image.local_filename)  # Specify the image path
    viewer.show()
    app.exec_()
    #await loop.run_forever()
    return


    panels = self.identify_panels(cv2_image)
    if len(panels) < 2:
      print("Could not find sidepanels")
      return None

    sidepanel = panels[-1]
    page_number_text, page_number_coordinates = self.identify_page_number_from_sidepanel(cv2_image, sidepanel)
    if page_number_text:
      annotation.page_number = page_number_text
      annotation.page_number_x1 = page_number_coordinates['left']
      annotation.page_number_x2 = page_number_coordinates['right']
      annotation.page_number_y1 = page_number_coordinates['top']
      annotation.page_number_y2 = page_number_coordinates['bottom']
      if created:
        await annotation.update()
      else:
        await annotation.save()
      return annotation
    elif created:
      if not annotation.valid: # protect valid annotations
        await annotation.destroy()

  async def review_annotation(self, annotation, force=False):
    if annotation.valid is not None and not force:
      return

    bid_file_image = await db.UniqueImage.objects.get(id=annotation.unique_image_id)
    cv2_image = cv2.imread(bid_file_image.local_filename, cv2.IMREAD_COLOR)

    page_number_image = cv2_image[annotation.page_number_y1:annotation.page_number_y2, annotation.page_number_x1:annotation.page_number_x2]
    self.display_images_side_by_side(cv2_image, "Original", page_number_image, annotation.page_number)
    key = cv2.waitKey(0)
    cv2.destroyAllWindows()
    if key == ord('y'):
      annotation.valid = True
    elif key == ord('n'):
      annotation.valid = False
    else:
      annotation.valid = None
    await annotation.update()
    return annotation
