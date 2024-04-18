import sys
from PyQt5.QtWidgets import QApplication, QLabel, QWidget, QVBoxLayout
from PyQt5.QtGui import QPixmap, QPainter, QPen
from PyQt5.QtCore import Qt, QTimer, QPoint, QRect

class ImageViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        #self.loadImage()  # Load image during initialization

    def initUI(self):
        # Set up the user interface
        self.setWindowTitle("PyQt Image Viewer")
        self.setGeometry(100, 100, 800, 600)  # Position and size of the window

        # Layout and widgets
        self.layout = QVBoxLayout()
        self.imageLabel = QLabel(self)
        self.imageLabel.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.imageLabel)
        self.setLayout(self.layout)
        QTimer.singleShot(100, self.loadImage)  # 100 ms after the loop starts

    def loadImage(self):
        # Open file dialog to select an image
        imagePath = '/Users/harish/data/bidboard_images/005c9596560c13d9ea52544b73839f48'
        pixmap = QPixmap(imagePath)
        self.imageLabel.setPixmap(pixmap.scaled(self.imageLabel.size(), Qt.KeepAspectRatio))

    def resizeEvent(self, event):
        # Resize the pixmap when the window is resized
        if self.imageLabel.pixmap():
            self.imageLabel.setPixmap(self.imageLabel.pixmap().scaled(self.imageLabel.size(), Qt.KeepAspectRatio))

class BoundingBoxApp(QWidget):
    def __init__(self):
        super().__init__()
        self.imagePath = '/Users/harish/data/bidboard_images/005c9596560c13d9ea52544b73839f48'
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


if __name__ == '__main__':
    app = QApplication(sys.argv)
    viewer = BoundingBoxApp()  # Specify the image path
    viewer.show()
    sys.exit(app.exec_())
