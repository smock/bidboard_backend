import os

from databases import Database
from pdf2image import convert_from_path
from pathlib import Path
import cv2
import numpy as np
import pytesseract
from PIL import Image


from app import db

Image.MAX_IMAGE_PIXELS = None

class BidFileAnnotationService:
  def __init__(self, db: Database):
    self.db = db

  async def annotate_bid_file(self, bid_file):
    print(bid_file.name)
    if bid_file.local_filename is None:
      print("Not cached")
      return
    if bid_file.mime_type != 'application/pdf':
      print(bid_file.mime_type)
      print("Not a pdf")
      return
    if not bid_file.images_extracted:
      await self.extract_images(bid_file)
    
    for bid_file_image in await db.BCBidFileImage.objects.filter(bc_bid_file_id=bid_file.id).all():
      if bid_file_image.has_architectural_page_number is None:
        await self.flag_architectural_page_number(bid_file_image)
      if bid_file_image.has_architectural_page_number:
        await self.annotate_page_number(bid_file_image)

  async def upsert_bid_file_image(self, bid_file, page_number, local_filename):
    created = True
    bid_file_image = await db.BCBidFileImage.objects.get_or_none(
      bc_bid_file_id=bid_file.id,
      page_number=page_number
    )
    if bid_file_image is None:
      created = False
      bid_file_image = db.BCBidFileImage.construct(bc_bid_file_id=bid_file.id, page_number=page_number)
    bid_file_image.local_filename=local_filename
    if created is False:
      await bid_file_image.save()
    else:
      await bid_file_image.update()
    
    return bid_file_image

  async def extract_images(self, bid_file, dpi=300, force=False):
    if bid_file.images_extracted and not force:
      return

    output_folder = os.path.join(os.path.dirname(bid_file.local_filename), 'images')
    Path(output_folder).mkdir(parents=True, exist_ok=True)

    pages = convert_from_path(bid_file.local_filename, dpi=dpi)
    for i, page in enumerate(pages):
      page_number = i + 1
      image_path = os.path.join(output_folder, f'page_{page_number}.png')
      page.save(image_path, 'PNG')
      bid_file_image = await self.upsert_bid_file_image(bid_file, page_number, image_path)
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
    else:
      bid_file_image.has_architectural_page_number = False
    print("image %s - %s" % (bid_file_image.local_filename, bid_file_image.has_architectural_page_number))
    await bid_file_image.update()
    cv2.destroyAllWindows()

  def extract_coordinates_from_ocr_result(self, ocr_result, idx, border_size):
    return {
      'left': ocr_result['left'][idx] - border_size,
      'top': ocr_result['top'][idx] - border_size,
      'width': ocr_result['width'][idx],
      'height': ocr_result['height'][idx]
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
    mean = np.mean(heights)
    std_dev = np.std(heights)
    heights = [height for height in heights if height < mean + 3 * std_dev]
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

  def display_images_side_by_side(image1, image2, step):
    title1 = "%s - Before" % step
    title2 = "%s - After" % step
    combined = np.hstack((image1, image2))
    cv2.imshow(f'{title1} | {title2}', combined)
    cv2.waitKey(0)
    cv2.destroyAllWindows()


  def extract_edges(image, debug=False):
    # grayscale the image
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, binary_image = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY)
    if debug:
      display_images_side_by_side(gray, binary_image, "Thresholding")

    # Define a kernel for dilation; you might need to adjust the size and shape
    kernel = np.ones((30, 30), np.uint8)  # A 3x3 square kernel

    # Apply dilation to connect dashed line segments
    dilated_image = cv2.dilate(binary_image, kernel, iterations=1)
    if debug:
      display_images_side_by_side(binary_image, dilated_image, "Dilation")

    contours, _ = cv2.findContours(dilated_image.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Create a mask to draw the open-ended line segments (initially all ones - include everything)
    mask = np.ones_like(dilated_image)

    # Analyze each contour
    for cnt in contours:
      # Approximate the contour to reduce the number of points
      epsilon = 0.01 * cv2.arcLength(cnt, True)
      approx = cv2.approxPolyDP(cnt, epsilon, True)

      # Check if the contour is closed (if it's convex or if approximated contour has same length as the perimeter)
      if cv2.isContourConvex(approx) or len(approx) == int(cv2.arcLength(cnt, True)):
        # If closed, draw it on the mask with 0 (exclude it)
        cv2.drawContours(mask, [cnt], -1, 0, thickness=cv2.FILLED)

    # Apply the mask to the dilated image
    filtered_image = cv2.bitwise_and(dilated_image, dilated_image, mask=mask)
    if debug:
      display_images_side_by_side(dilated_image, filtered_image, "Contour Mask")

    filtered_original_image = cv2.bitwise_and(image, image, mask=mask)
    if debug:
      display_images_side_by_side(image, filtered_original_image, "Applied Contour Mask")
    return filtered_original_image


  def extract_lines(image, debug=False):
    # Apply Canny Edge Detector
    edges = cv2.Canny(image, 50, 150)
    # Detect lines using Hough Transform
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=50, minLineLength=10, maxLineGap=250)
    if lines is None:
      return None, None

    endpoints = []
    if lines is not None:
      for line in lines:
        x1, y1, x2, y2 = line[0]
        endpoints.append(((x1, y1), (x2, y2)))

    # Now `endpoints` contains tuples of line endpoints: ((x1, y1), (x2, y2))
    blank_image = np.zeros(image.shape[:3], dtype=np.uint8)
    for line in lines:
      x1, y1, x2, y2 = line[0]
      cv2.line(blank_image, (x1, y1), (x2, y2), (255, 255, 255), 2)

    if debug:
      display_images_side_by_side(image, blank_image, "Line detection")

    return lines, blank_image


  def show_image_with_coordinates(self, image, coordinates, label):
    if coordinates:
      cropped_image = image[
        coordinates['top']:coordinates['top'] + coordinates['height'],
        coordinates['left']:coordinates['left'] + coordinates['width']
      ]
      cv2.imshow(label, cropped_image)
    else:
      cv2.imshow(label, image)
    cv2.waitKey(0)
    cv2.destroyAllWindows()


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
    if page_number_coordinates and debug:
      self.show_image_with_coordinates(cropped_sidepanel, page_number_coordinates, page_number_text)
    #else:
    #  extract_page_number(binary_inverted_sidepanel, debug=True)

  def identify_panels(self, cv2_image, debug=False):
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
      return
    horizontal_lines = []
    for line in lines:
      x1, y1, x2, y2 = line[0]
      if abs(y2 - y1) < 10: # checking if the line is horizontal
        horizontal_lines.append((x1, y1, x2, y2))
    # Sort the horizontal lines by y coordinate
    if len(horizontal_lines) == 0:
      print("Could not extract horizontal lines")
      return
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
      return

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
      return
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

  async def annotate_page_number(self, bid_file_image):
    cv2_image = cv2.imread(bid_file_image.local_filename, cv2.IMREAD_COLOR)
    panels = self.identify_panels(cv2_image)
    if len(panels) < 2:
      print("Could not find sidepanels")
      return
    sidepanel = panels[-1]
    self.identify_page_number_from_sidepanel(cv2_image, sidepanel, debug=True)
