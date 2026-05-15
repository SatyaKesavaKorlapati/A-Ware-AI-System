import sys
import os
import cv2
import random
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QCheckBox, QScrollArea, QFrame,
                             QComboBox, QFileDialog, QSizePolicy, QTableWidget, QTableWidgetItem, QHeaderView)
from PyQt5.QtGui import QPixmap, QImage, QColor, QFont
from PyQt5.QtCore import Qt, QSize
from ultralytics import YOLO

# --- CONFIGURATION (Keep these paths real) ---
MODEL_PATH = r"D:\RAJU\rs\IssacSim\Python\Models\lar1r.pt"
TEST_IMAGES_DIR = r"D:\RAJU\rs\IssacSim\rockynotes_master_yolo_2640\images\val"

class ClassBadgeWidget(QWidget):
    """A custom widget for the sidebar to show class name, count, and status."""
    def __init__(self, c_id, name, color, parent=None):
        super().__init__(parent)
        self.c_id = c_id
        self.name = name
        self.color = QColor(*color)

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(5, 2, 5, 2)
        self.layout.setSpacing(5)

        # 1. Colored Status Indicator Dot
        self.dot_label = QLabel("●")
        self.dot_label.setFixedWidth(15)
        self.dot_label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.dot_label)

        # 2. Checkbox and Class Name
        self.checkbox = QCheckBox(f"{c_id}: {name}")
        self.checkbox.setChecked(True)
        self.checkbox.setFont(QFont("Arial", 10))
        self.layout.addWidget(self.checkbox)

        # 3. Count Badge
        self.count_label = QLabel("[ 0 ]")
        self.count_label.setFixedWidth(50)
        self.count_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.layout.addWidget(self.count_label)

        self.update_status(0)

    def update_status(self, count):
        count_str = f"[{count:2}]"
        if count > 0:
            self.dot_label.setStyleSheet(f"color: {self.color.name()}; font-size: 14pt;")
            self.checkbox.setStyleSheet("color: #0000BB; font-weight: bold;")
            self.count_label.setStyleSheet("color: #0000BB; font-weight: bold; border-radius: 10px; background-color: #E6EEFF;")
        else:
            self.dot_label.setStyleSheet("color: #999999; font-size: 14pt;")
            self.checkbox.setStyleSheet("color: #999999; font-weight: normal;")
            self.count_label.setStyleSheet("color: #999999; font-weight: normal; background-color: transparent;")
        
        self.count_label.setText(count_str)

    def connect_checkbox(self, callback):
        self.checkbox.stateChanged.connect(lambda state: callback(self.c_id, state == Qt.Checked))

class ImageCard(QLabel):
    """A clean card to display the main image without causing layout jitters."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.setStyleSheet("background-color: white; border: 1px solid #E0E0E0; border-radius: 15px;")
        self._pixmap = None

    def set_image(self, pixmap):
        self._pixmap = pixmap
        self._update_image()

    def _update_image(self):
        if self._pixmap and self.width() > 0 and self.height() > 0:
            scaled = self._pixmap.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            super().setPixmap(scaled)

    def resizeEvent(self, event):
        self._update_image()
        super().resizeEvent(event)

class YoloViewerPro(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RockyNotes YOLO - Intelligent View & Data Logger")
        self.resize(1600, 900)

        # Load Model
        print("Loading YOLO model...")
        self.model = YOLO(MODEL_PATH)
        self.class_names = self.model.names
        
        random.seed(42)
        self.colors = {c_id: (random.randint(50, 255), random.randint(100, 255), random.randint(50, 255)) 
                       for c_id in self.class_names.keys()}

        self.image_pool = []
        self.image_pool_paths = []
        self.custom_img_path = None
        self.active_image_path = None
        self.current_raw_img = None
        self.current_results = None
        self.class_filter_state = {c_id: True for c_id in self.class_names.keys()}
        self.data_panel_visible = False

        self.load_image_pool()
        self.setup_gui()
        
        if self.image_pool:
            self.pool_dropdown.setCurrentIndex(0)

    def load_image_pool(self):
        if not os.path.exists(TEST_IMAGES_DIR):
            print(f"❌ Warning: Image folder not found at {TEST_IMAGES_DIR}")
            return
            
        valid_extensions = ('.png', '.jpg', '.jpeg')
        self.image_pool = [f for f in os.listdir(TEST_IMAGES_DIR) if f.lower().endswith(valid_extensions)]
        self.image_pool_paths = [os.path.join(TEST_IMAGES_DIR, f) for f in self.image_pool]

    def setup_gui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        master_layout = QHBoxLayout(main_widget)
        master_layout.setContentsMargins(10, 10, 10, 10)
        master_layout.setSpacing(10)

        # --- LEFT PANEL (Controls) ---
        control_panel = QFrame()
        control_panel.setFixedWidth(350)
        control_panel.setStyleSheet("background-color: #F8F9FA; border-radius: 15px; border: 1px solid #E0E0E0;")
        control_layout = QVBoxLayout(control_panel)
        control_layout.setContentsMargins(15, 15, 15, 15)
        master_layout.addWidget(control_panel)

        header = QLabel("Frame Manifest")
        header.setFont(QFont("Arial", 16, QFont.Bold))
        control_layout.addWidget(header)

        control_layout.addWidget(QLabel("Image Pool Select:"))
        self.pool_dropdown = QComboBox()
        self.pool_dropdown.addItems(self.image_pool)
        self.pool_dropdown.setStyleSheet("background-color: white; border: 1px solid #CCCCCC; padding: 5px;")
        self.pool_dropdown.currentIndexChanged.connect(self.load_pool_image)
        control_layout.addWidget(self.pool_dropdown)

        control_layout.addWidget(QFrame(frameShape=QFrame.HLine, frameShadow=QFrame.Sunken))

        filter_btn_layout = QHBoxLayout()
        btn_select_all = QPushButton("Select All")
        btn_clear_all = QPushButton("Clear All")
        btn_select_all.clicked.connect(self.select_all_classes)
        btn_clear_all.clicked.connect(self.clear_all_classes)
        filter_btn_layout.addWidget(btn_select_all)
        filter_btn_layout.addWidget(btn_clear_all)
        control_layout.addLayout(filter_btn_layout)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("background-color: transparent; border: none;")
        self.class_manifest_widget = QWidget()
        self.class_manifest_layout = QVBoxLayout(self.class_manifest_widget)
        self.class_manifest_layout.setAlignment(Qt.AlignTop)
        scroll_area.setWidget(self.class_manifest_widget)
        control_layout.addWidget(scroll_area)

        self.manifest_widgets = {}
        for c_id, name in self.class_names.items():
            color = self.colors[c_id]
            badge = ClassBadgeWidget(c_id, name, color)
            badge.connect_checkbox(self.update_class_filter)
            self.class_manifest_layout.addWidget(badge)
            self.manifest_widgets[c_id] = badge

        nav_frame = QWidget()
        nav_layout = QHBoxLayout(nav_frame)
        self.btn_prev = QPushButton("Previous")
        self.btn_prev.clicked.connect(self.prev_image)
        self.btn_next = QPushButton("Next")
        self.btn_next.clicked.connect(self.next_image)
        nav_layout.addWidget(self.btn_prev)
        nav_layout.addWidget(self.btn_next)
        control_layout.addWidget(nav_frame)

        self.btn_upload = QPushButton("Upload Custom Image")
        self.btn_upload.setStyleSheet("background-color: #007BFF; color: white; padding: 8px; border-radius: 8px;")
        self.btn_upload.clicked.connect(self.upload_custom_image)
        control_layout.addWidget(self.btn_upload)

        # --- RIGHT PANEL (Image + Data Table) ---
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)
        master_layout.addWidget(right_panel, stretch=1)

        # The Image
        self.image_card = ImageCard()
        right_layout.addWidget(self.image_card, stretch=1) # Stretch=1 gives image max priority

        # The Data Toggle Button
        self.btn_toggle_data = QPushButton("▼ Show Bounding Box Coordinates Data")
        self.btn_toggle_data.setFont(QFont("Arial", 10, QFont.Bold))
        self.btn_toggle_data.setStyleSheet("background-color: #E0E0E0; padding: 8px; border-radius: 5px;")
        self.btn_toggle_data.clicked.connect(self.toggle_data_panel)
        right_layout.addWidget(self.btn_toggle_data)

        # The Data Table (Hidden by default)
        self.data_table = QTableWidget()
        self.data_table.setColumnCount(6)
        self.data_table.setHorizontalHeaderLabels(["Class Name", "Confidence", "X_Min (px)", "Y_Min (px)", "X_Max (px)", "Y_Max (px)"])
        self.data_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.data_table.setEditTriggers(QTableWidget.NoEditTriggers) # Make it read-only
        self.data_table.setStyleSheet("background-color: white; border: 1px solid #CCCCCC;")
        self.data_table.setFixedHeight(200) # Fix the height so it acts like a console
        self.data_table.hide()
        right_layout.addWidget(self.data_table)

    def toggle_data_panel(self):
        self.data_panel_visible = not self.data_panel_visible
        if self.data_panel_visible:
            self.data_table.show()
            self.btn_toggle_data.setText("▲ Hide Bounding Box Coordinates Data")
        else:
            self.data_table.hide()
            self.btn_toggle_data.setText("▼ Show Bounding Box Coordinates Data")

    def update_image_view(self, path):
        if not path or not os.path.exists(path):
            return

        self.active_image_path = path
        self.current_raw_img = cv2.imread(path)
        self.current_results = self.model(self.current_raw_img, conf=0.25, verbose=False)[0] 
        
        detected_counts = {}
        if self.current_results.boxes is not None:
            for box in self.current_results.boxes:
                c_id = int(box.cls[0])
                detected_counts[c_id] = detected_counts.get(c_id, 0) + 1

        for c_id, badge in self.manifest_widgets.items():
            count = detected_counts.get(c_id, 0)
            badge.update_status(count)

        self.redraw_image()

    def redraw_image(self):
        if self.current_raw_img is None or self.current_results is None:
            return

        display_img = self.current_raw_img.copy()
        
        # Clear the data table before repopulating
        self.data_table.setRowCount(0)
        table_row = 0

        if self.current_results.boxes is not None:
            for box in self.current_results.boxes:
                c_id = int(box.cls[0])
                
                # Check filter
                if not self.class_filter_state[c_id]:
                    continue

                x1, y1, x2, y2 = map(int, box.xyxy[0])
                conf = float(box.conf[0])
                name = self.class_names[c_id]
                color = self.colors.get(c_id, (0, 255, 0))

                # Draw on image
                cv2.rectangle(display_img, (x1, y1), (x2, y2), color, 2)
                label_text = f"{name} {conf:.2f}"
                (text_w, text_h), _ = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                cv2.rectangle(display_img, (x1, y1 - text_h - 5), (x1 + text_w, y1), color, -1)
                cv2.putText(display_img, label_text, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)

                # Add to data table
                self.data_table.insertRow(table_row)
                self.data_table.setItem(table_row, 0, QTableWidgetItem(name))
                self.data_table.setItem(table_row, 1, QTableWidgetItem(f"{conf:.2f}"))
                self.data_table.setItem(table_row, 2, QTableWidgetItem(str(x1)))
                self.data_table.setItem(table_row, 3, QTableWidgetItem(str(y1)))
                self.data_table.setItem(table_row, 4, QTableWidgetItem(str(x2)))
                self.data_table.setItem(table_row, 5, QTableWidgetItem(str(y2)))
                table_row += 1

        # Display Image
        h, w, ch = display_img.shape
        bytes_per_line = ch * w
        display_img_rgb = cv2.cvtColor(display_img, cv2.COLOR_BGR2RGB)
        qimg = QImage(display_img_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg)
        self.image_card.set_image(pixmap)

    # --- ACTIONS ---
    def load_pool_image(self, index):
        if 0 <= index < len(self.image_pool_paths):
            self.update_image_view(self.image_pool_paths[index])
            self.custom_img_path = None 

    def upload_custom_image(self):
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getOpenFileName(self, "Open Custom Image", "", "Images (*.png *.jpg *.jpeg)", options=options)
        if file_path:
            self.custom_img_path = file_path
            self.pool_dropdown.blockSignals(True) 
            self.pool_dropdown.setCurrentIndex(-1)
            self.pool_dropdown.blockSignals(False)
            self.update_image_view(file_path)

    def next_image(self):
        if self.custom_img_path: return
        current_idx = self.pool_dropdown.currentIndex()
        if current_idx < len(self.image_pool) - 1:
            self.pool_dropdown.setCurrentIndex(current_idx + 1)

    def prev_image(self):
        if self.custom_img_path: return
        current_idx = self.pool_dropdown.currentIndex()
        if current_idx > 0:
            self.pool_dropdown.setCurrentIndex(current_idx - 1)

    def update_class_filter(self, c_id, is_active):
        self.class_filter_state[c_id] = is_active
        self.redraw_image()

    def select_all_classes(self):
        for c_id, badge in self.manifest_widgets.items():
            badge.checkbox.blockSignals(True)
            badge.checkbox.setChecked(True)
            self.class_filter_state[c_id] = True
            badge.checkbox.blockSignals(False)
        self.redraw_image()

    def clear_all_classes(self):
        for c_id, badge in self.manifest_widgets.items():
            badge.checkbox.blockSignals(True)
            badge.checkbox.setChecked(False)
            self.class_filter_state[c_id] = False
            badge.checkbox.blockSignals(False)
        self.redraw_image()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    viewer = YoloViewerPro()
    viewer.show()
    sys.exit(app.exec_())