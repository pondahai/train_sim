# scene_editor.py
import sys
import os
import time # 用於計算 dt
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QSplitter,
    QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView,
    QVBoxLayout, QSizePolicy, QMenuBar, QAction, QMessageBox, QStatusBar,
    QDockWidget # 用於可停靠視窗
)
from PyQt5.QtCore import Qt, pyqtSignal, QPoint, QTimer # QTimer 用於預覽更新
from PyQt5.QtOpenGL import QGLWidget
from PyQt5.QtGui import QFont, QFontMetrics, QCursor # QCursor 用於滑鼠鎖定
from OpenGL.GL import *
from OpenGL.GLU import *
import pygame
import numpy as math # 保持一致性
import numpy as np # 方便使用 np

# --- Import Shared Modules ---
# (確保這些模組存在且路徑正確)
import scene_parser
import renderer
import minimap_renderer
import texture_loader
from scene_parser import Scene
from camera import Camera # 用於 3D 預覽攝影機

# --- Constants ---
SCENE_FILE = "scene.txt"
EDITOR_WINDOW_TITLE = "Tram Scene Editor"
INITIAL_WINDOW_WIDTH = 1200
INITIAL_WINDOW_HEIGHT = 600
EDITOR_COORD_COLOR = (205, 205, 20, 200)
EDITOR_COORD_FONT_SIZE = 24
EDITOR_LABEL_OFFSET_X = 5
EDITOR_LABEL_OFFSET_Y = 3

# --- 3D 預覽視窗常數 ---
PREVIEW_UPDATE_INTERVAL = 16 # ms (接近 60 FPS)
PREVIEW_MOVE_SPEED = 25.0 # units per second
PREVIEW_MOUSE_SENSITIVITY = 0.15
PREVIEW_ACCEL_FACTOR = 6.0 # Shift 加速倍率

# --- Minimap OpenGL Widget ---
class MinimapGLWidget(QGLWidget):
    """Custom OpenGL Widget for rendering the scene preview."""
    glInitialized = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene_data = None
        self._view_center_x = 0.0
        self._view_center_z = 0.0
        self._view_range = minimap_renderer.DEFAULT_MINIMAP_RANGE
        self._min_range = minimap_renderer.MINIMAP_MIN_RANGE
        self._max_range = minimap_renderer.MINIMAP_MAX_RANGE
        self._zoom_factor = minimap_renderer.MINIMAP_ZOOM_FACTOR
        self._is_dragging = False
        self._last_mouse_pos = QPoint()
        self.setFocusPolicy(Qt.StrongFocus)
        self._coord_font = None
        try:
            if pygame.font.get_init():
                self._coord_font = pygame.font.SysFont(None, EDITOR_COORD_FONT_SIZE)
        except Exception as e:
            print(f"Minimap Warning: Failed to create coordinate font: {e}")

    def initializeGL(self):
        r, g, b, a = minimap_renderer.EDITOR_BG_COLOR
        glClearColor(r, g, b, a)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        self.glInitialized.emit()

    def resizeGL(self, w, h):
        pass # Viewport set in paintGL

    def paintGL(self):
        glClear(GL_COLOR_BUFFER_BIT)
        w = self.width()
        h = self.height()
        if w == 0 or h == 0:
            return

        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glOrtho(0.0, float(w), 0.0, float(h), -1.0, 1.0) # Y=0 is bottom in Ortho
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        glViewport(0, 0, w, h)

        # 保存並設定狀態
        glPushAttrib(GL_ENABLE_BIT | GL_CURRENT_BIT | GL_LINE_BIT | GL_POINT_BIT | GL_COLOR_BUFFER_BIT)
        glDisable(GL_DEPTH_TEST)
        glDisable(GL_LIGHTING)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        try:
            # 調用 minimap_renderer 進行動態繪製
            minimap_renderer.draw_editor_preview(
                self._scene_data,
                self._view_center_x,
                self._view_center_z,
                self._view_range,
                w, h
            )
        except Exception as e:
            print(f"Error calling draw_editor_preview: {e}")

        # 繪製中心十字
        glColor3f(1.0, 0.0, 0.0) # 紅色
        glLineWidth(1.0)
        widget_cx = w / 2.0
        widget_cy = h / 2.0
        cross_size = 10
        glBegin(GL_LINES)
        glVertex2f(widget_cx - cross_size, widget_cy)
        glVertex2f(widget_cx + cross_size, widget_cy)
        glVertex2f(widget_cx, widget_cy - cross_size)
        glVertex2f(widget_cx, widget_cy + cross_size)
        glEnd()

        # 繪製座標文字
        if self._coord_font:
            coord_text = f"Center: ({self._view_center_x:.1f}, {self._view_center_z:.1f}) Range: {self._view_range:.1f}"
            try:
                text_surface = self._coord_font.render(coord_text, True, EDITOR_COORD_COLOR)
                text_width = text_surface.get_width()
                text_height = text_surface.get_height()
                # Ortho Y=0 is bottom, so position near top edge
                draw_x = w - text_width - EDITOR_LABEL_OFFSET_X
                draw_y = h - text_height - EDITOR_LABEL_OFFSET_Y
                # Use the shared renderer text drawing function
                renderer._draw_text_texture(text_surface, draw_x, draw_y)
            except Exception as e:
                # print(f"渲染中心座標時出錯: {e}") # 減少訊息輸出
                pass

        # 恢復狀態
        glPopAttrib()

    def update_scene(self, scene_object):
        if isinstance(scene_object, Scene) or scene_object is None:
            self._scene_data = scene_object
            self.update() # Trigger repaint
        else:
            print("Editor Minimap received invalid scene data type.")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._is_dragging = True
            self._last_mouse_pos = event.pos()
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        if self._is_dragging:
            delta = event.pos() - self._last_mouse_pos
            w = self.width()
            h = self.height()
            if w > 0 and h > 0 and self._view_range > 0:
                # Calculate scale based on the smaller dimension to avoid distortion
                scale = min(w, h) / self._view_range
                # world_dx corresponds to change in screen X
                # world_dz corresponds to change in screen Y (flipped because screen Y down, world Z up)
                world_dx = delta.x() / scale
                world_dz = delta.y() / scale # 
                self._view_center_x += world_dx
                self._view_center_z += world_dz
                self._last_mouse_pos = event.pos()
                self.update() # Trigger repaint

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._is_dragging:
            self._is_dragging = False
            self.setCursor(Qt.ArrowCursor)

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        factor = 1.0
        if delta > 0:
            factor = 1.0 / self._zoom_factor # Zoom in
        elif delta < 0:
            factor = self._zoom_factor    # Zoom out

        if factor != 1.0:
            new_range = self._view_range * factor
            # Clamp range
            self._view_range = max(self._min_range, min(self._max_range, new_range))
            self.update() # Trigger repaint

# --- PreviewGLWidget ---
class PreviewGLWidget(QGLWidget):
    """用於互動式 3D 場景預覽的 OpenGL Widget"""
    glInitialized = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene_data = None
        self._camera = Camera()
        self._timer = QTimer(self)
        self._last_update_time = time.time()
        self._keys_pressed = set()
        self._mouse_locked = False
        self._camera.set_mouse_lock(self._mouse_locked)
        self._last_mouse_pos = QPoint()

        # 攝影機初始狀態
        self._camera.mouse_sensitivity = PREVIEW_MOUSE_SENSITIVITY
        self._camera.base_position = np.array([10.0, 5.0, 10.0], dtype=float)
        self._camera.yaw = -135.0
        self._camera.pitch = -20.0

        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)

        self._current_background_info = None
        self.show_ground_flag = False # Default to not showing ground in preview

    def initializeGL(self):
        """OpenGL 初始化"""
        glClearColor(0.5, 0.7, 1.0, 1.0) # Default sky blue
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_TEXTURE_2D)
        glEnable(GL_LIGHTING)
        glEnable(GL_LIGHT0)
        glEnable(GL_COLOR_MATERIAL)
        glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)
        glLightfv(GL_LIGHT0, GL_AMBIENT, [0.3, 0.3, 0.3, 1.0])
        glLightfv(GL_LIGHT0, GL_DIFFUSE, [0.8, 0.8, 0.8, 1.0])
        glLightfv(GL_LIGHT0, GL_SPECULAR, [0.5, 0.5, 0.5, 1.0])
        glLightfv(GL_LIGHT0, GL_POSITION, [100.0, 150.0, 100.0, 1.0])
        glEnable(GL_NORMALIZE)

        self._timer.timeout.connect(self.update_preview)
        self._timer.start(PREVIEW_UPDATE_INTERVAL)
        self._last_update_time = time.time()
        self.glInitialized.emit()
        print("3D Preview Widget Initialized.")

    def resizeGL(self, w, h):
        """視窗大小調整"""
        if h == 0:
            h = 1
        glViewport(0, 0, w, h)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        far_clip = renderer.GROUND_SIZE * 4 if hasattr(renderer, 'GROUND_SIZE') else 1000.0
        gluPerspective(45, float(w) / float(h), 0.1, far_clip)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

    def paintGL(self):
        """繪製 OpenGL 場景"""
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

#         camera_pos_for_background = self._camera.base_position
        try:
            self._camera.apply_view()
        except Exception as e:
            print(f"Error applying camera view: {e}")
            gluLookAt(10, 5, 10, 0, 0, 0, 0, 1, 0) # Fallback view

        # --- 繪製背景 (Skybox/Skydome) ---
        original_depth_mask = glGetBooleanv(GL_DEPTH_WRITEMASK) # 保存原始深度遮罩狀態
        try:
            if self._current_background_info:
                # --- >>> DEBUG <<< ---
#                 print(f"DEBUG: Calling draw_background with: {self._current_background_info}")
                # --- >>> END DEBUG <<< ---
                # draw_background 內部會處理深度測試和光照禁用
                renderer.draw_background(self._current_background_info, self._camera)
                # --- >>> DEBUG <<< ---
#                 print("DEBUG: draw_background call finished.")
                # --- >>> END DEBUG <<< ---
        except Exception as e:
            print(f"Error drawing background in preview: {e}")
        finally:
             # 確保恢復深度遮罩，即使背景繪製出錯
             # 如果 draw_background 內部禁用了深度測試而不是深度遮罩，這裡可能需要 glEnable(GL_DEPTH_TEST)
             if not original_depth_mask:
                 # print("Warning: Depth mask was already false before drawing background?") # Debug
                 pass
             # 假設 draw_background 會正確恢復它修改的狀態，或者在這裡強制恢復
             glDepthMask(GL_TRUE) # 確保主場景可以寫入深度緩衝
             glEnable(GL_DEPTH_TEST) # 確保深度測試啟用
             glEnable(GL_LIGHTING)   # 確保光照啟用 (如果 draw_background 關閉了它)


        # --- 繪製場景內容 ---
        try:
            renderer.draw_ground(self.show_ground_flag)
            if self._scene_data:
                if self._scene_data.track:
                    renderer.draw_track(self._scene_data.track)
                renderer.draw_scene_objects(self._scene_data)
        except Exception as e:
            print(f"Error drawing scene contents in preview: {e}")

    def update_preview(self):
        """由 QTimer 觸發的更新迴圈"""
        current_time = time.time()
        dt = current_time - self._last_update_time
        self._last_update_time = current_time
        dt = min(dt, 0.1) # Clamp dt
        self._update_camera_position(dt)
        self.update() # Request repaint

    def _update_camera_position(self, dt):
        """根據按下的按鍵更新攝影機位置"""
        if not self._keys_pressed:
            return

        is_accelerating = Qt.Key_Shift in self._keys_pressed
        current_speed = PREVIEW_MOVE_SPEED * PREVIEW_ACCEL_FACTOR if is_accelerating else PREVIEW_MOVE_SPEED

        move_vector = np.array([0.0, 0.0, 0.0], dtype=float)
        yaw_rad = math.radians(self._camera.yaw)
        pitch_rad = math.radians(self._camera.pitch)
        cos_pitch = math.cos(pitch_rad)

        cam_forward = np.array([cos_pitch * math.sin(yaw_rad), math.sin(pitch_rad), cos_pitch * math.cos(yaw_rad)], dtype=float)
        norm_fwd = np.linalg.norm(cam_forward)
        if norm_fwd > 1e-6:
            cam_forward /= norm_fwd

        world_up = np.array([0.0, 1.0, 0.0], dtype=float)
        cam_right = np.cross(cam_forward, world_up)
        norm_right = np.linalg.norm(cam_right)
        if norm_right > 1e-6:
            cam_right /= norm_right
        else:
            cam_right = np.array([1.0, 0.0, 0.0], dtype=float) # Fallback if looking straight up/down

        cam_up = world_up # Movement uses world up

        if Qt.Key_W in self._keys_pressed: move_vector += cam_forward
        if Qt.Key_S in self._keys_pressed: move_vector -= cam_forward
        if Qt.Key_A in self._keys_pressed: move_vector -= cam_right
        if Qt.Key_D in self._keys_pressed: move_vector += cam_right
        if Qt.Key_Space in self._keys_pressed: move_vector += cam_up
        if Qt.Key_Q in self._keys_pressed: move_vector -= cam_up

        norm_move = np.linalg.norm(move_vector)
        if norm_move > 1e-6:
            move_vector /= norm_move
            self._camera.base_position += move_vector * current_speed * dt

    def update_scene(self, scene_object, background_info=None):
        """接收新的場景數據和對應的背景資訊"""
        if isinstance(scene_object, Scene) or scene_object is None:
            self._scene_data = scene_object
            self._current_background_info = background_info
            # Don't call self.update() here, let the timer handle repaints
        else:
            print("Editor Preview received invalid scene data type.")

    def keyPressEvent(self, event):
        key = event.key()
        self._keys_pressed.add(key)
        if key == Qt.Key_Tab:
            self.toggle_mouse_lock()
        elif key == Qt.Key_G:
            self.show_ground_flag = not self.show_ground_flag
            self.update() # Trigger immediate repaint to reflect ground change
        elif key == Qt.Key_Escape:
            if self._mouse_locked:
                self._release_mouse()
        event.accept()

    def keyReleaseEvent(self, event):
        if not event.isAutoRepeat():
            self._keys_pressed.discard(event.key())
        event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and not self._mouse_locked:
            self.toggle_mouse_lock()
        event.accept()

    def mouseMoveEvent(self, event):
        if self._mouse_locked:
            current_pos = event.pos()
            delta = current_pos - self._last_mouse_pos
            self._camera.update_angles(delta.x(), delta.y())
            # Center cursor (optional, can cause jitter)
            center_pos = QPoint(self.width() // 2, self.height() // 2)
            if current_pos != center_pos:
                QCursor.setPos(self.mapToGlobal(center_pos))
                self._last_mouse_pos = center_pos
            else:
                self._last_mouse_pos = current_pos
        else:
            self._last_mouse_pos = event.pos() # Update last pos even when not locked
        event.accept()

    def focusOutEvent(self, event):
        if self._mouse_locked:
            self._release_mouse()
        self._keys_pressed.clear() # Clear keys when losing focus
        event.accept()

    def _grab_mouse(self):
        if not self._mouse_locked:
            self.grabMouse()
            self.setCursor(Qt.BlankCursor)
            self._mouse_locked = True
            self._camera.set_mouse_lock(True)
            center_pos = QPoint(self.width() // 2, self.height() // 2)
            self._last_mouse_pos = center_pos
            QCursor.setPos(self.mapToGlobal(center_pos)) # Move cursor to center

    def _release_mouse(self):
        if self._mouse_locked:
            self.releaseMouse()
            self.setCursor(Qt.ArrowCursor)
            self._mouse_locked = False
            self._camera.set_mouse_lock(False)

    def toggle_mouse_lock(self):
        if self._mouse_locked:
            self._release_mouse()
        else:
            self._grab_mouse()

# --- SceneTableWidget ---
class SceneTableWidget(QTableWidget):
    sceneDataChanged = pyqtSignal()
    HEADER_PADDING = 20
    MIN_COLUMN_WIDTH = 40

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data_modified = False
        self._filepath = SCENE_FILE
        self._command_hints = scene_parser.COMMAND_HINTS
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.verticalHeader().setVisible(True)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        # Connections
        self.currentCellChanged.connect(self._on_current_cell_changed)
        self.itemChanged.connect(self._on_item_changed)
        self.needUpdate = False
        self._last_active_row = -1

    def _resize_columns_to_header_labels(self):
        header = self.horizontalHeader()
        header_font = header.font()
        if not header_font:
            return
        fm = QFontMetrics(header_font)
        for col in range(self.columnCount()):
            # Give command column a reasonable width
            if col == 0:
                # Use width of a longer command like 'building' for estimate
                width = fm.horizontalAdvance("building") + self.HEADER_PADDING
                self.setColumnWidth(col, max(self.MIN_COLUMN_WIDTH * 2, width)) # Ensure min width
                continue
            # Resize other columns based on header text
            header_item = self.horizontalHeaderItem(col)
            header_text = header_item.text() if header_item else f"P{col}"
            text_width = fm.horizontalAdvance(header_text)
            final_width = max(self.MIN_COLUMN_WIDTH, text_width + self.HEADER_PADDING)
            self.setColumnWidth(col, final_width)

    def load_scene_file(self):
        remember_row = self._last_active_row # Remember last active row before clearing
        self.clear()
        self.setRowCount(0)
        self.setColumnCount(0)

        if not os.path.exists(self._filepath):
            self.insertRow(0)
            self.setColumnCount(1)
            self.setHorizontalHeaderLabels(["Command"])
            self._resize_columns_to_header_labels()
            return False

        try:
            with open(self._filepath, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            if not lines: # Handle empty file
                self.insertRow(0)
                self.setColumnCount(1)
                self.setHorizontalHeaderLabels(["Command"])
                self._resize_columns_to_header_labels()
                return True

            # Determine max columns needed
            max_cols = 0
            for line in lines:
                stripped_line = line.strip()
                if stripped_line and not stripped_line.startswith('#'):
                    max_cols = max(max_cols, len(stripped_line.split()))
            max_cols = max(1, max_cols) # Ensure at least one column

            self.setColumnCount(max_cols)
            self.setHorizontalHeaderLabels([f"P{i}" for i in range(max_cols)]) # Initial generic headers
            self.setRowCount(len(lines))

            self.blockSignals(True) # Block signals during population
            try:
                for row, line in enumerate(lines):
                    self.setVerticalHeaderItem(row, QTableWidgetItem(str(row + 1)))
                    parts = line.strip().split()
                    for col, part in enumerate(parts):
                        self.setItem(row, col, QTableWidgetItem(part))
                    # Fill remaining cells in the row with empty items
                    for col in range(len(parts), max_cols):
                        self.setItem(row, col, QTableWidgetItem(""))
            finally:
                self.blockSignals(False)

            self._data_modified = False
            self._resize_columns_to_header_labels() # Resize after populating
            self.sceneDataChanged.emit() # Notify that data has changed

            # Restore selection/scroll position
            new_row_count = self.rowCount()
            if 0 <= remember_row < new_row_count:
                item_to_scroll = self.item(remember_row, 0) # Check if item exists
                if item_to_scroll:
                    self.setCurrentCell(remember_row, 0)
                    self.scrollToItem(item_to_scroll, QAbstractItemView.PositionAtCenter)
                    self._last_active_row = remember_row # Restore remembered row
                    # print(f"跳轉到行: {remember_row + 1}")
            else:
                self._last_active_row = -1 # Reset if row is invalid

            return True

        except Exception as e:
            print(f"Error loading scene file '{self._filepath}': {e}")
            self.clear()
            self.setRowCount(0)
            self.setColumnCount(0)
            self._last_active_row = -1 # Reset on error
            return False

    def get_scene_lines(self):
        lines = []
        for row in range(self.rowCount()):
            row_parts = []
            for col in range(self.columnCount()):
                item = self.item(row, col)
                # Append part if item exists and has text
                if item and item.text():
                    row_parts.append(item.text())
                else:
                    # Stop appending parts for this row if an empty cell is encountered
                    # (unless you want to preserve trailing empty strings)
                    break
            # Only add non-empty lines (lines with at least one part)
            if row_parts:
                lines.append(" ".join(row_parts))
            # else:
            #     lines.append("") # Add this line if you want to preserve blank lines from the table
        return lines

    def is_modified(self):
        return self._data_modified

    def mark_saved(self):
        self._data_modified = False

    def is_row_empty(self, row_index):
        if not (0 <= row_index < self.rowCount()):
            return False
        for col in range(self.columnCount()):
            item = self.item(row_index, col)
            if item is not None and item.text().strip():
                return False # Found non-empty cell
        return True # All cells are empty or whitespace

    def keyPressEvent(self, event):
        key = event.key()
        modifiers = event.modifiers()

        if key in (Qt.Key_Return, Qt.Key_Enter) and not modifiers: # Enter/Return without modifiers
            current_row = self.currentRow()
            if current_row >= 0:
                self.insertRow(current_row + 1)
                # Renumber vertical headers
                for r in range(current_row + 1, self.rowCount()):
                    self.setVerticalHeaderItem(r, QTableWidgetItem(str(r + 1)))
                self.setCurrentCell(current_row + 1, 0) # Move cursor to new row
                self._data_modified = True
                self.sceneDataChanged.emit() # Notify change
                event.accept()
                return
        elif key == Qt.Key_Delete and not modifiers: # Delete without modifiers
            selected_ranges = self.selectedRanges()
            # Check if exactly one row is selected
            if len(selected_ranges) == 1:
                selection_range = selected_ranges[0]
                if selection_range.leftColumn() == 0 and \
                   selection_range.rightColumn() == self.columnCount() - 1 and \
                   selection_range.rowCount() == 1:
                    row_to_delete = selection_range.topRow()
                    # Only delete if the row is completely empty
                    if self.is_row_empty(row_to_delete):
                        self.removeRow(row_to_delete)
                        # Renumber vertical headers
                        for r in range(row_to_delete, self.rowCount()):
                            self.setVerticalHeaderItem(r, QTableWidgetItem(str(r + 1)))
                        self._data_modified = True
                        self.sceneDataChanged.emit() # Notify change
                        # print(f"Deleted empty row {row_to_delete + 1}")
                        event.accept()
                        return
        # Let the base class handle other key presses (like navigation)
        super().keyPressEvent(event)

    def _on_current_cell_changed(self, currentRow, currentColumn, previousRow, previousColumn):
        # Update last active row when selection changes
        if currentRow >= 0:
            self._last_active_row = currentRow

        # Emit scene changed signal only when the *row* changes,
        # and if an update is actually needed (item was edited).
        if currentRow != previousRow and self.needUpdate:
            if currentRow >= 0: # Ensure the new row is valid
                self.sceneDataChanged.emit()
            self.needUpdate = False # Reset update flag

        # Update horizontal header hints based on the command in the first column
        if 0 <= currentRow < self.rowCount():
            command_item = self.item(currentRow, 0)
            command = command_item.text().lower().strip() if command_item else ""
            hints = self._command_hints.get(command, [])
            max_cols = self.columnCount()

            # Prepare new headers
            new_headers = []
            if not hints: # If command not found or has no hints
                 new_headers = [f"P{i}" for i in range(max_cols)]
            else:
                 new_headers = [hints[i] if i < len(hints) else f"P{i}" for i in range(max_cols)]

             # Only set headers if they actually changed to avoid unnecessary updates
            current_actual_headers = [self.horizontalHeaderItem(c).text() if self.horizontalHeaderItem(c) else f"P{c}" for c in range(max_cols)]
            if new_headers != current_actual_headers:
                self.setHorizontalHeaderLabels(new_headers)
                self._resize_columns_to_header_labels() # Resize only when headers change
        else:
            # If no row is selected or row is invalid, show generic headers
            self.setHorizontalHeaderLabels([f"P{c}" for c in range(self.columnCount())])
            # Don't resize if no row is selected


    def _on_item_changed(self, item):
        # Mark data as modified and flag that an update is needed
        # The actual sceneDataChanged signal is emitted when the row changes (_on_current_cell_changed)
        self._data_modified = True
        self.needUpdate = True

# --- Main Editor Window ---
class SceneEditorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(EDITOR_WINDOW_TITLE)
        self.setGeometry(100, 100, INITIAL_WINDOW_WIDTH, INITIAL_WINDOW_HEIGHT)

        # Pygame/Loader Init
        pygame.init()
        pygame.font.init()
        try:
            pygame.display.set_mode((64, 64), pygame.OPENGL | pygame.DOUBLEBUF, vsync=0)
            pygame.display.set_caption("Pygame Helper (Editor)")
        except pygame.error as e:
            print(f"Warning: Could not set Pygame display mode: {e}")
        scene_parser.set_texture_loader(texture_loader) # Pass loader to parser

        # Font setup
        try:
            editor_hud_font = pygame.font.SysFont(None, 24)
            renderer.set_hud_font(editor_hud_font)
            if renderer.grid_label_font:
                minimap_renderer.set_grid_label_font(renderer.grid_label_font)
            if renderer.coord_label_font:
                minimap_renderer.set_coord_label_font(renderer.coord_label_font)
        except Exception as e:
            print(f"Editor Warning: Could not initialize/set fonts: {e}")
            renderer.set_hud_font(None)
            minimap_renderer.set_grid_label_font(None)
            minimap_renderer.set_coord_label_font(None)

        # UI Setup
        self._setup_ui_with_docks()
        self._setup_menu()
        self._setup_status_bar()

        # GL Init Signals
        self._minimap_gl_ready = False
        self._preview_gl_ready = False
        self.minimap_widget.glInitialized.connect(self._on_minimap_gl_ready)
        self.preview_widget.glInitialized.connect(self._on_preview_gl_ready)

        print("Scene Editor Initialized.")

    def _check_all_gl_ready(self):
        if self._minimap_gl_ready and self._preview_gl_ready:
            print("All OpenGL Widgets Initialized. Loading initial scene...")
            self.load_initial_scene()

    def _on_minimap_gl_ready(self):
        self._minimap_gl_ready = True
        self._check_all_gl_ready()

    def _on_preview_gl_ready(self):
        self._preview_gl_ready = True
        self._check_all_gl_ready()

    def _setup_ui_with_docks(self):
        self.setDockOptions(QMainWindow.AllowNestedDocks | QMainWindow.AllowTabbedDocks | QMainWindow.AnimatedDocks)

        # Table Dock
        self.table_dock = QDockWidget("Scene Editor", self)
        self.table_widget = SceneTableWidget(self.table_dock)
        self.table_dock.setWidget(self.table_widget)
        self.table_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.table_dock)

        # Minimap Dock
        self.minimap_dock = QDockWidget("Minimap", self)
        self.minimap_widget = MinimapGLWidget(self.minimap_dock)
        self.minimap_dock.setWidget(self.minimap_widget)
        self.minimap_dock.setAllowedAreas(Qt.AllDockWidgetAreas) # Allow more flexibility
        self.addDockWidget(Qt.RightDockWidgetArea, self.minimap_dock)

        # 3D Preview Dock
        self.preview_dock = QDockWidget("3D Preview", self)
        self.preview_widget = PreviewGLWidget(self.preview_dock)
        self.preview_dock.setWidget(self.preview_widget)
        self.preview_dock.setAllowedAreas(Qt.AllDockWidgetAreas)
        # Stack preview below minimap initially
        self.splitDockWidget(self.minimap_dock, self.preview_dock, Qt.Vertical)

        # Set initial sizes (adjust ratios as needed)
        self.resizeDocks([self.table_dock], [int(self.width() * 0.4)], Qt.Horizontal)
        self.resizeDocks([self.minimap_dock, self.preview_dock], [int(self.height() * 0.5), int(self.height() * 0.5)], Qt.Vertical)

        # Connect table changes to update previews
        self.table_widget.sceneDataChanged.connect(self.update_previews)

    def _setup_menu(self):
        menubar = self.menuBar()
        # File Menu
        file_menu = menubar.addMenu('&File')
        save_action = QAction('&Save', self)
        save_action.setShortcut('Ctrl+S')
        save_action.setStatusTip('Save scene file')
        save_action.triggered.connect(self.save_scene_file)
        file_menu.addAction(save_action)

        reload_action = QAction('&Reload', self)
        reload_action.setShortcut('Ctrl+R')
        reload_action.setStatusTip('Reload scene file from disk')
        reload_action.triggered.connect(self.ask_reload_scene)
        file_menu.addAction(reload_action)

        file_menu.addSeparator()

        exit_action = QAction('&Exit', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.setStatusTip('Exit application')
        exit_action.triggered.connect(self.close) # Connect to QMainWindow.close
        file_menu.addAction(exit_action)

        # View Menu (for toggling docks)
        view_menu = menubar.addMenu('&View')
        view_menu.addAction(self.table_dock.toggleViewAction())
        view_menu.addAction(self.minimap_dock.toggleViewAction())
        view_menu.addAction(self.preview_dock.toggleViewAction())

    def _setup_status_bar(self):
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("Ready", 3000) # Initial message

    def load_initial_scene(self):
        """Loads the scene file and triggers preview updates."""
        if self.table_widget.load_scene_file():
            self.statusBar.showMessage(f"Loaded '{SCENE_FILE}'", 5000)
        else:
            self.statusBar.showMessage(f"Failed to load '{SCENE_FILE}'", 5000)
            self.update_previews() # Ensure previews are cleared/updated even on fail

    def save_scene_file(self):
        lines = self.table_widget.get_scene_lines()
        try:
            content_to_write = "\n".join(lines)
            # Ensure trailing newline unless empty
            if content_to_write and not content_to_write.endswith('\n'):
                content_to_write += '\n'
            with open(SCENE_FILE, 'w', encoding='utf-8') as f:
                f.write(content_to_write)
            self.table_widget.mark_saved() # Reset modified flag
            self.statusBar.showMessage(f"Saved '{SCENE_FILE}'", 3000)
            return True
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Could not save file '{SCENE_FILE}':\n{e}")
            self.statusBar.showMessage("Save failed", 5000)
            return False

    def update_previews(self):
        """解析表格數據，更新小地圖和 3D 預覽 (包含背景)"""
        # print("Updating editor previews...") # 可選的調試信息

        # 1. 從表格獲取當前所有行的文本內容 (這個函數本身是沒問題的)
        # lines = self.table_widget.get_scene_lines() # 我們可以直接讀取表格內容

        # 2. 獲取當前表格中選中的行號
        current_row = self.table_widget.currentRow()

        # 3. 使用 scene_parser 解析當前表格的 *完整* 內容
        #    我們先獲取一次完整的 lines 列表用於解析 Scene 物件
        current_table_lines = self.table_widget.get_scene_lines()
        parsed_scene = scene_parser.parse_scene_from_lines(current_table_lines, load_textures=True)

        # --- 4. 決定 3D 預覽窗口應該顯示哪個背景 ---
        background_info_for_preview = None # 初始化為 None (無特定背景)

        # 只有在場景成功解析後才繼續判斷背景
        if parsed_scene:
            # 預設情況下，使用場景的初始背景（如果有的話）
            background_info_for_preview = parsed_scene.initial_background_info

            # 如果使用者在表格中選中了一個有效的行 (current_row >= 0)
            if current_row >= 0:
                # 從當前選中的行開始，向上查找最近定義的 skybox 或 skydome 指令
                last_bg_info_found_upwards = None
                table_widget_ref = self.table_widget
                for i in range(current_row, -1, -1): # 從 current_row 倒序迭代到 0
                    # --- >>> 修正點：獲取整行文本來解析 <<< ---
                    row_text = ""
                    row_parts = []
                    if i < table_widget_ref.rowCount():
                        for j in range(table_widget_ref.columnCount()): # 遍歷該行的所有列
                            item = table_widget_ref.item(i, j)
                            if item and item.text():
                                row_parts.append(item.text().strip()) # 獲取單元格文本
                            else:
                                break # 遇到空單元格停止，假設後面都是空的
                        row_text = " ".join(row_parts) # 組合該行文本
                    # --- >>> END 修正點 <<< ---

                    if row_text: # 確保行不為空
                        parts = row_text.split() # 這裡 parts 才包含參數
                        cmd = parts[0].lower() if parts else ""

                        if cmd in ["skybox", "skydome"]:
                            # 找到了背景指令，重建其資訊字典
                            if cmd == "skybox" and len(parts) > 1:
                                # Skybox 信息只包含類型和基礎名稱
                                last_bg_info_found_upwards = {'type': 'skybox', 'base_name': parts[1]}
                            elif cmd == "skydome" and len(parts) > 1:
                                # Skydome 信息包含類型、檔名，並嘗試查找已載入的 ID
                                tex_file_to_find = parts[1] # 現在可以正確獲取檔名
                                found_id = None
                                # 檢查初始背景是否匹配
                                if parsed_scene.initial_background_info and \
                                   parsed_scene.initial_background_info.get('type') == 'skydome' and \
                                   parsed_scene.initial_background_info.get('file') == tex_file_to_find:
                                    found_id = parsed_scene.initial_background_info.get('id')
                                # 如果初始沒找到，檢查觸發器列表
                                if found_id is None:
                                    for _, info_dict in parsed_scene.background_triggers:
                                         if info_dict.get('type') == 'skydome' and info_dict.get('file') == tex_file_to_find:
                                             found_id = info_dict.get('id')
                                             if found_id: break # 找到 ID 就停止
                                # 構建 Skydome 的信息字典
                                last_bg_info_found_upwards = {'type': 'skydome', 'file': tex_file_to_find, 'id': found_id}

                            # 找到第一個（最近的）背景指令後就停止向上搜索
                            break # 退出 for 循環

                # 如果向上搜索找到了背景指令，則使用它作為預覽背景
                if last_bg_info_found_upwards is not None:
                    background_info_for_preview = last_bg_info_found_upwards
                # 否則，維持使用上面設定的 initial_background_info

        # --- 5. 更新小地圖預覽 ---
        try:
            # 傳遞我們為解析 Scene 而獲取的 parsed_scene
            self.minimap_widget.update_scene(parsed_scene)
        except Exception as e:
            print(f"Error updating minimap widget: {e}")

        # --- 6. 更新 3D 預覽窗口 ---
        try:
            # 為新解析的場景創建軌道渲染所需的緩衝區
            if parsed_scene and parsed_scene.track:
                try:
                    parsed_scene.track.create_all_segment_buffers()
                except Exception as e:
                    print(f"  Error creating track buffers for preview: {e}")
            # 將解析後的場景數據 和 決定好的預覽背景信息 傳遞給 3D 預覽窗口
            self.preview_widget.update_scene(parsed_scene, background_info_for_preview)
        except Exception as e:
            print(f"Error updating 3D preview widget: {e}")

    def ask_reload_scene(self):
        if self.table_widget.is_modified():
            reply = QMessageBox.question(self, 'Reload Scene',
                                         "Discard current changes and reload from disk?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.No:
                return
        # Proceed with reload
        self.load_initial_scene()

    def closeEvent(self, event):
        # Check for unsaved changes before closing
        if self.table_widget.is_modified():
            reply = QMessageBox.question(self, 'Exit Editor',
                                         "You have unsaved changes. Save before exiting?",
                                         QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                                         QMessageBox.Cancel) # Default to Cancel

            if reply == QMessageBox.Save:
                if not self.save_scene_file():
                    event.ignore() # Prevent closing if save failed
                    return
            elif reply == QMessageBox.Discard:
                pass # Proceed with closing
            else: # Cancel
                event.ignore() # Prevent closing
                return

        # Cleanup resources
        print("Cleaning up editor resources...")
        if hasattr(self, 'preview_widget') and self.preview_widget._timer.isActive():
            self.preview_widget._timer.stop()
            print("Stopped preview timer.")

        # Cleanup renderer resources (minimap FBO, dynamic textures)
        minimap_renderer.cleanup_minimap_renderer()
        # Cleanup track buffers from the last parsed scene in the editor
        last_scene_in_editor = self.preview_widget._scene_data # Get scene from preview
        if last_scene_in_editor and last_scene_in_editor.track:
            last_scene_in_editor.track.clear()
            print("Cleaned up track buffers from editor's last scene.")
        # Clear global texture caches (important!)
        if texture_loader:
            texture_loader.clear_texture_cache()
        if hasattr(renderer, 'skybox_texture_cache'):
             for tex_id in renderer.skybox_texture_cache.values():
                 try:
                     if glIsTexture(tex_id): glDeleteTextures(1, [tex_id])
                 except Exception as cleanup_error: print(f"Error cleaning up skybox texture {tex_id}: {cleanup_error}")
             renderer.skybox_texture_cache.clear()
             print("Skybox texture cache cleared.")


        # Quit Pygame subsystems if initialized
        if pygame.font.get_init():
            pygame.font.quit()
        if pygame.display.get_init():
            pygame.display.quit()
        # pygame.quit() # Call this last if needed, might interfere with Qt event loop if called too early

        print("Editor cleanup complete.")
        event.accept() # Allow window to close


# --- Main Application Execution ---
if __name__ == '__main__':
    try:
        # Set working directory to script's location
        os.chdir(os.path.dirname(os.path.abspath(__file__)))
        print(f"工作目錄設定為: {os.getcwd()}")
    except Exception as e:
        print(f"無法更改工作目錄: {e}")

    # Ensure Pygame display is initialized *before* QGLWidget instances are created
    # This can sometimes help with OpenGL context sharing issues, although not guaranteed.
    # try:
    #     pygame.init()
    #     pygame.display.set_mode((1, 1), pygame.OPENGL) # Minimal Pygame GL context
    # except pygame.error as e:
    #     print(f"Warning: Minimal Pygame init failed: {e}")


    app = QApplication(sys.argv)
    editor = SceneEditorWindow()
    editor.show()
    exit_code = app.exec_()

    # Optional: Final pygame quit after Qt loop finishes
    if pygame.get_init():
        pygame.quit()

    sys.exit(exit_code)