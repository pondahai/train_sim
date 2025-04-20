# scene_editor.py
import sys
import os
import time # <--- 新增：用於計算 dt
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QSplitter,
    QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView,
    QVBoxLayout, QSizePolicy, QMenuBar, QAction, QMessageBox, QStatusBar,
    QDockWidget # <--- 新增：用於可停靠視窗
)
from PyQt5.QtCore import Qt, pyqtSignal, QPoint, QTimer # <--- 新增：QTimer
from PyQt5.QtOpenGL import QGLWidget
from PyQt5.QtGui import QFont, QFontMetrics, QCursor # <--- 新增：QCursor
from OpenGL.GL import *
from OpenGL.GLU import *
import pygame
import numpy as math
import numpy as np # <--- 新增：方便使用 np

# --- Import Shared Modules ---
import scene_parser
import renderer
import minimap_renderer
import texture_loader
from scene_parser import Scene
from camera import Camera # <--- 新增：用於 3D 預覽攝影機

# --- Constants (Keep) ---
SCENE_FILE = "scene.txt"
EDITOR_WINDOW_TITLE = "Tram Scene Editor"
INITIAL_WINDOW_WIDTH = 1200 # 稍微加寬以容納更多視窗
INITIAL_WINDOW_HEIGHT = 600 # 稍微加高
EDITOR_COORD_COLOR = (205, 205, 20, 200) # Keep
EDITOR_COORD_FONT_SIZE = 24 # Keep
EDITOR_LABEL_OFFSET_X = 5 # Keep
EDITOR_LABEL_OFFSET_Y = 3 # Keep

# --- 新增：3D 預覽視窗常數 ---
PREVIEW_UPDATE_INTERVAL = 64 # ms (16ms 約 60 FPS)
PREVIEW_MOVE_SPEED = 25.0 # units per second
PREVIEW_MOUSE_SENSITIVITY = 0.15
PREVIEW_ACCEL_FACTOR = 6.0 # <--- 新增：Shift 加速倍率

# --- Minimap OpenGL Widget (No significant changes needed internally) ---
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
                # print(f"Minimap created coordinate display font (size: {EDITOR_COORD_FONT_SIZE}).") # 註解掉重複訊息
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
        if w == 0 or h == 0: return

        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glOrtho(0.0, float(w), 0.0, float(h), -1.0, 1.0)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        glViewport(0, 0, w, h)

        glPushAttrib(GL_ENABLE_BIT | GL_CURRENT_BIT | GL_LINE_BIT | GL_POINT_BIT)
        glDisable(GL_DEPTH_TEST)
        glDisable(GL_LIGHTING)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        try:
            minimap_renderer.draw_editor_preview(
                self._scene_data,
                self._view_center_x,
                self._view_center_z,
                self._view_range,
                w, h
            )
        except Exception as e:
            print(f"Error calling draw_editor_preview: {e}")

        glColor3f(1.0, 0.0, 0.0)
        glLineWidth(1.0)
        widget_cx = w / 2.0
        widget_cy = h / 2.0
        cross_size = 10 # 縮小十字大小
        glBegin(GL_LINES)
        glVertex2f(widget_cx - cross_size, widget_cy); glVertex2f(widget_cx + cross_size, widget_cy)
        glVertex2f(widget_cx, widget_cy - cross_size); glVertex2f(widget_cx, widget_cy + cross_size)
        glEnd()

        if self._coord_font:
            coord_text = f"Center: ({self._view_center_x:.1f}, {self._view_center_z:.1f}) Range: {self._view_range:.1f}"
            try:
                text_surface = self._coord_font.render(coord_text, True, EDITOR_COORD_COLOR)
                text_width = text_surface.get_width()
                text_height = text_surface.get_height()
                draw_x = w - text_width - EDITOR_LABEL_OFFSET_X
                draw_y = h - text_height - EDITOR_LABEL_OFFSET_Y
                renderer._draw_text_texture(text_surface, draw_x, draw_y)
            except Exception as e:
                # print(f"渲染中心座標時出錯: {e}") # 減少訊息輸出
                pass

        glPopAttrib()

    def update_scene(self, scene_object):
        if isinstance(scene_object, Scene) or scene_object is None:
            self._scene_data = scene_object
            self.update()
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
            w = self.width(); h = self.height()
            if w > 0 and h > 0 and self._view_range > 0:
                scale = min(w, h) / self._view_range
                # 保持原始邏輯 - X 軸映射到世界 X，Y 軸(向下)映射到世界 Z(向上)
                world_dx = delta.x() / scale
                world_dz = delta.y() / scale # QPoint Y is down, map Y is Z up
                self._view_center_x += world_dx
                self._view_center_z += world_dz
                self._last_mouse_pos = event.pos()
                self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._is_dragging:
            self._is_dragging = False
            self.setCursor(Qt.ArrowCursor)

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta > 0: factor = 1.0 / self._zoom_factor
        elif delta < 0: factor = self._zoom_factor
        else: return
        new_range = self._view_range * factor
        self._view_range = max(self._min_range, min(self._max_range, new_range))
        self.update()

# --- 新增：3D 預覽 OpenGL Widget ---
class PreviewGLWidget(QGLWidget):
    """用於互動式 3D 場景預覽的 OpenGL Widget"""
    glInitialized = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene_data = None
        self._camera = Camera() # 獨立的攝影機實例
        self._timer = QTimer(self) # 用於更新迴圈
        self._last_update_time = time.time()
        self._keys_pressed = set() # 追蹤按下的按鍵
        self._mouse_locked = False
        self._camera.set_mouse_lock(self._mouse_locked) # <--- 新增：確保 Camera 初始狀態與 Widget 一致
        self._last_mouse_pos = QPoint()

        # 調整攝影機設定用於自由飛行
        self._camera.mouse_sensitivity = PREVIEW_MOUSE_SENSITIVITY
        self._camera.base_position = np.array([10.0, 5.0, 10.0], dtype=float) # 初始位置
        self._camera.yaw = -135.0 # 初始視角
        self._camera.pitch = -20.0

        self.setFocusPolicy(Qt.StrongFocus) # 接收鍵盤焦點
        self.setMouseTracking(True) # 即使沒有按下按鈕也追蹤滑鼠移動

        self.show_ground_flag = False
        
    def initializeGL(self):
        """OpenGL 初始化"""
        # 基本設定 (與 renderer.init_renderer 類似，但不重複載入紋理)
        glClearColor(0.5, 0.7, 1.0, 1.0) # 天藍色背景
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

        # 連接並啟動計時器
        self._timer.timeout.connect(self.update_preview)
        self._timer.start(PREVIEW_UPDATE_INTERVAL)
        self._last_update_time = time.time()

        self.glInitialized.emit()
        print("3D Preview Widget Initialized.")

    def resizeGL(self, w, h):
        """視窗大小調整"""
        if h == 0: h = 1
        glViewport(0, 0, w, h)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        # 設定 3D 投影
        far_clip = renderer.GROUND_SIZE * 4 if hasattr(renderer, 'GROUND_SIZE') else 1000.0 # 增加視距
        gluPerspective(45, float(w) / float(h), 0.1, far_clip)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

    def paintGL(self):
        """繪製 OpenGL 場景"""
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

        # 套用攝影機視角
        # 注意：這裡我們直接使用 Camera 類別的 apply_view，但它的內部實現
        # 可能基於電車。對於自由視角，我們可能需要一個稍微修改的版本
        # 或確保 yaw/pitch 正確更新 look_at 方向。目前 Camera.apply_view
        # 已能基於 yaw/pitch 計算 look_dir，應該可用。
        try:
            self._camera.apply_view()
        except Exception as e:
            print(f"Error applying camera view: {e}")
            # Fallback view if camera fails
            gluLookAt(10, 5, 10, 0, 0, 0, 0, 1, 0)

        # 繪製場景內容 (使用 renderer 中的函數)
        try:
            renderer.draw_ground(self.show_ground_flag) # 始終顯示地面
            if self._scene_data:
                if self._scene_data.track:
                    renderer.draw_track(self._scene_data.track)
                renderer.draw_scene_objects(self._scene_data)
            else:
                # 可以繪製一個提示，表示沒有場景數據
                pass
        except Exception as e:
            print(f"Error drawing scene in preview: {e}")

    def update_preview(self):
        """由 QTimer 觸發的更新迴圈"""
        current_time = time.time()
        dt = current_time - self._last_update_time
        self._last_update_time = current_time
        dt = min(dt, 0.1) # 防止 dt 過大導致跳躍

        # 更新攝影機位置 (基於按鍵)
        self._update_camera_position(dt)

        # 觸發重繪
        self.update() # QGLWidget.update() -> calls paintGL

    def _update_camera_position(self, dt):
        """根據按下的按鍵更新攝影機位置"""
        if not self._keys_pressed:
            return

        # --- 判斷是否加速 ---
        is_accelerating = Qt.Key_Shift in self._keys_pressed # 檢查 Shift 是否按下

        if is_accelerating:
            current_speed = PREVIEW_MOVE_SPEED * PREVIEW_ACCEL_FACTOR # 使用加速後的速度
        else:
            current_speed = PREVIEW_MOVE_SPEED # 使用普通速度
            
        move_vector = np.array([0.0, 0.0, 0.0], dtype=float)

        # --- 計算攝影機的局部方向向量 ---
        # 這部分邏輯類似 camera.apply_view 中計算 look_dir 的部分
        yaw_rad = math.radians(self._camera.yaw)
        pitch_rad = math.radians(self._camera.pitch)
        cos_pitch = math.cos(pitch_rad)

        # Forward vector (考慮 yaw 和 pitch)
        cam_forward = np.array([
            cos_pitch * math.sin(yaw_rad),
            math.sin(pitch_rad),
            cos_pitch * math.cos(yaw_rad)
        ], dtype=float)
        # 確保歸一化 (理論上應該是，但保險起見)
        norm_fwd = np.linalg.norm(cam_forward)
        if norm_fwd > 1e-6: cam_forward /= norm_fwd

        # Right vector (基於 forward 和世界 Y 軸)
        world_up = np.array([0.0, 1.0, 0.0], dtype=float)
        cam_right = np.cross(cam_forward, world_up)
        norm_right = np.linalg.norm(cam_right)
        if norm_right > 1e-6: cam_right /= norm_right
        else: # 如果看向正上方/下方，選擇一個固定的 right (例如 X 軸)
            cam_right = np.array([1.0, 0.0, 0.0], dtype=float)

        # Up vector (使用世界 Y 軸進行上下移動)
        cam_up = world_up # 簡單起見，上下移動總是沿世界 Y 軸

        # --- 根據按鍵計算移動向量 ---
        if Qt.Key_W in self._keys_pressed:
            move_vector += cam_forward
        if Qt.Key_S in self._keys_pressed:
            move_vector -= cam_forward
        if Qt.Key_A in self._keys_pressed:
            move_vector -= cam_right # Strafe left
        if Qt.Key_D in self._keys_pressed:
            move_vector += cam_right # Strafe right
        if Qt.Key_Space in self._keys_pressed:
            move_vector += cam_up # Move up
        if Qt.Key_Q in self._keys_pressed:
            move_vector -= cam_up # Move down

        # --- 歸一化移動向量並應用速度和 dt ---
        norm_move = np.linalg.norm(move_vector)
        if norm_move > 1e-6:
            move_vector /= norm_move
            self._camera.base_position += move_vector * current_speed  * dt

    def update_scene(self, scene_object):
        """接收新的場景數據"""
        if isinstance(scene_object, Scene) or scene_object is None:
            self._scene_data = scene_object
            # 不需要立即呼叫 update()，因為 QTimer 會定期觸發
            # print("Preview widget received scene update.") # 減少訊息
        else:
            print("Editor Preview received invalid scene data type.")

    def keyPressEvent(self, event):
        """處理按鍵按下事件"""
        key = event.key()
        self._keys_pressed.add(key)

        # Tab 鍵用於切換滑鼠鎖定狀態
        if key == Qt.Key_Tab:
            self.toggle_mouse_lock()
        elif key == Qt.Key_G:
            self.show_ground_flag = not self.show_ground_flag
        # Escape 鍵總是解除鎖定
        elif key == Qt.Key_Escape:
            if self._mouse_locked:
                self._release_mouse()

        event.accept() # 表示事件已處理

    def keyReleaseEvent(self, event):
        """處理按鍵釋放事件"""
        if not event.isAutoRepeat(): # 忽略自動重複的釋放事件
            self._keys_pressed.discard(event.key())
        event.accept()

    def mousePressEvent(self, event):
        """處理滑鼠按下事件 - 用於鎖定滑鼠"""
        if event.button() == Qt.LeftButton and not self._mouse_locked:
            self.toggle_mouse_lock() # 按左鍵也鎖定
        event.accept()

    def mouseMoveEvent(self, event):
        """處理滑鼠移動事件 - 用於視角控制"""
        if self._mouse_locked:
            current_pos = event.pos()
            delta = current_pos - self._last_mouse_pos

            # 更新攝影機角度
            self._camera.update_angles(delta.x(), delta.y())

            # 將滑鼠移回中心 (如果需要完美鎖定) - 可能會導致抖動，謹慎使用
            center_pos = QPoint(self.width() // 2, self.height() // 2)
            if current_pos != center_pos:
                QCursor.setPos(self.mapToGlobal(center_pos))
                self._last_mouse_pos = center_pos
            else:
                 self._last_mouse_pos = current_pos

        else:
            self._last_mouse_pos = event.pos() # 更新位置以備下次鎖定

        event.accept()

    def focusOutEvent(self, event):
        """當 Widget 失去焦點時，解除滑鼠鎖定"""
        if self._mouse_locked:
            self._release_mouse()
        self._keys_pressed.clear() # 清除按鍵狀態避免失去焦點後還在移動
        event.accept()

    def _grab_mouse(self):
        """鎖定滑鼠並隱藏指標"""
        if not self._mouse_locked:
            self.grabMouse()
            self.setCursor(Qt.BlankCursor)
            self._mouse_locked = True
            self._camera.set_mouse_lock(True)  # <--- 新增：設定 Camera 實例的鎖定狀態
            center_pos = QPoint(self.width() // 2, self.height() // 2)
            self._last_mouse_pos = center_pos # 重設上次位置到中心
            QCursor.setPos(self.mapToGlobal(center_pos)) # 將系統滑鼠移到中心
            print("Mouse grabbed for 3D preview.")

    def _release_mouse(self):
        """釋放滑鼠並顯示指標"""
        if self._mouse_locked:
            self.releaseMouse()
            self.setCursor(Qt.ArrowCursor)
            self._mouse_locked = False
            self._camera.set_mouse_lock(False) # <--- 新增：設定 Camera 實例的鎖定狀態
            print("Mouse released.")

    def toggle_mouse_lock(self):
        """切換滑鼠鎖定狀態"""
        if self._mouse_locked:
            self._release_mouse()
        else:
            self._grab_mouse()


# --- SceneTableWidget (No changes needed from previous version with header resize) ---
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
        self.currentCellChanged.connect(self._on_current_cell_changed)
        self.itemChanged.connect(self._on_item_changed)
        self.needUpdate = False
        
    def _resize_columns_to_header_labels(self):
        header = self.horizontalHeader()
        header_font = header.font()
        if not header_font: return
        fm = QFontMetrics(header_font)
        for col in range(self.columnCount()):
            if col == 0: continue
            header_item = self.horizontalHeaderItem(col)
            header_text = header_item.text() if header_item else f"P{col}"
            text_width = fm.horizontalAdvance(header_text)
            final_width = max(self.MIN_COLUMN_WIDTH, text_width + self.HEADER_PADDING)
            self.setColumnWidth(col, final_width)

    def load_scene_file(self):
        self.clear()
        self.setRowCount(0); self.setColumnCount(0)
        if not os.path.exists(self._filepath):
            self.insertRow(0); self.setColumnCount(1)
            self.setHorizontalHeaderLabels(["Command"])
            self._resize_columns_to_header_labels()
            return False
        try:
            with open(self._filepath, 'r', encoding='utf-8') as f: lines = f.readlines()
            if not lines:
                self.insertRow(0); self.setColumnCount(1)
                self.setHorizontalHeaderLabels(["Command"])
                self._resize_columns_to_header_labels()
                return True
            max_cols = max((len(line.strip().split()) for line in lines if line.strip()), default=0)
            max_cols = max(1, max_cols)
            self.setColumnCount(max_cols)
            self.setHorizontalHeaderLabels([f"P{i}" for i in range(max_cols)])
            self.setRowCount(len(lines))
            self.blockSignals(True)
            try:
                for row, line in enumerate(lines):
                    self.setVerticalHeaderItem(row, QTableWidgetItem(str(row + 1)))
                    parts = line.strip().split()
                    for col, part in enumerate(parts): self.setItem(row, col, QTableWidgetItem(part))
                    for col in range(len(parts), max_cols): self.setItem(row, col, QTableWidgetItem(""))
            finally: self.blockSignals(False)
            self._data_modified = False
            self._resize_columns_to_header_labels()
            # print(f"Loaded '{self._filepath}' into table.") #減少訊息
            self.sceneDataChanged.emit()
            return True
        except Exception as e:
            print(f"Error loading scene file '{self._filepath}': {e}")
            self.clear(); self.setRowCount(0); self.setColumnCount(0)
            return False

    def get_scene_lines(self):
        lines = []
        for row in range(self.rowCount()):
            row_parts = []
            for col in range(self.columnCount()):
                item = self.item(row, col)
                if item and item.text(): row_parts.append(item.text())
                else: break
            lines.append(" ".join(row_parts))
        return lines

    def is_modified(self): return self._data_modified
    def mark_saved(self): self._data_modified = False

    def is_row_empty(self, row_index):
        if row_index < 0 or row_index >= self.rowCount(): return False
        for col in range(self.columnCount()):
            item = self.item(row_index, col)
            if item is not None and item.text().strip(): return False
        return True

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key_Return, Qt.Key_Enter):
            current_row = self.currentRow()
            if current_row >= 0:
                self.insertRow(current_row + 1)
                self.setVerticalHeaderItem(current_row + 1, QTableWidgetItem(str(current_row + 2)))
                for r in range(current_row + 2, self.rowCount()): self.setVerticalHeaderItem(r, QTableWidgetItem(str(r + 1)))
                self.setCurrentCell(current_row + 1, 0)
                self._data_modified = True
                self.sceneDataChanged.emit()
                event.accept(); return
        elif key == Qt.Key_Up or key == Qt.Key_Down:
            pass
        elif key == Qt.Key_Delete:
             selected_ranges = self.selectedRanges()
             if len(selected_ranges) == 1:
                 selection_range = selected_ranges[0]
                 if selection_range.leftColumn() == 0 and \
                    selection_range.rightColumn() == self.columnCount() - 1 and \
                    selection_range.rowCount() == 1:
                     row_to_delete = selection_range.topRow()
                     if self.is_row_empty(row_to_delete):
                         self.removeRow(row_to_delete)
                         for r in range(row_to_delete, self.rowCount()): self.setVerticalHeaderItem(r, QTableWidgetItem(str(r + 1)))
                         self._data_modified = True
                         self.sceneDataChanged.emit()
                         # print(f"Deleted empty row {row_to_delete + 1}") # 減少訊息
                         event.accept(); return
        super().keyPressEvent(event)

    def _on_current_cell_changed(self, currentRow, currentColumn, previousRow, previousColumn):
        if currentRow != previousRow and self.needUpdate:
            self.sceneDataChanged.emit()
            self.needUpdate = False
            
        if currentRow < 0 or currentRow >= self.rowCount():
             default_headers = [f"__P{c}__" for c in range(self.columnCount())]
             if default_headers or self.columnCount() == 0:
                  if default_headers: self.setHorizontalHeaderLabels(default_headers)
             else:
                  self.setColumnCount(1); self.setHorizontalHeaderLabels(["P0"])
        else:
            command_item = self.item(currentRow, 0)
            command = command_item.text().lower().strip() if command_item else ""
            hints = self._command_hints.get(command, [])
            max_cols = self.columnCount()
            current_headers = [hints[i] if i < len(hints) else f"P{i}" for i in range(max_cols)]
            if current_headers: self.setHorizontalHeaderLabels(current_headers)
            elif max_cols > 0: self.setHorizontalHeaderLabels([f"P{i}" for i in range(max_cols)])
        self._resize_columns_to_header_labels()

    def _on_item_changed(self, item):
        self._data_modified = True
#         self.sceneDataChanged.emit()
        self.needUpdate = True

# --- Main Editor Window ---
class SceneEditorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(EDITOR_WINDOW_TITLE)
        self.setGeometry(100, 100, INITIAL_WINDOW_WIDTH, INITIAL_WINDOW_HEIGHT)

        # --- Pygame/Loader Init (Keep) ---
        pygame.init()
        pygame.font.init()
        try:
            pygame.display.set_mode((64, 64), pygame.RESIZABLE)
            pygame.display.set_caption("Pygame Helper (Editor)")
        except pygame.error as e: print(f"Warning: Could not set Pygame display mode in editor init: {e}")
        scene_parser.set_texture_loader(texture_loader)

        # --- Font setup for Renderer/Minimap (Keep) ---
        try:
            editor_hud_font = pygame.font.SysFont(None, 24)
            renderer.set_hud_font(editor_hud_font)
            if renderer.grid_label_font: minimap_renderer.set_grid_label_font(renderer.grid_label_font)
            # --- 新增：設定座標標籤字體 ---
            if renderer.coord_label_font: minimap_renderer.set_coord_label_font(renderer.coord_label_font)
            else: print("Editor Warning: Grid label font not created by renderer.")
        except Exception as e:
            print(f"Editor Warning: Could not initialize/set fonts: {e}")
            renderer.set_hud_font(None)
            minimap_renderer.set_grid_label_font(None)
            minimap_renderer.set_coord_label_font(None) # <--- 新增

        # --- UI Setup (使用 Dock Widgets) ---
        self._setup_ui_with_docks() # <--- 修改：呼叫新的 UI 設置函數
        self._setup_menu()
        self._setup_status_bar()

        # --- 連接 GL 初始化訊號 ---
        # 需要確保兩個 GL Widget 都初始化完成後再載入場景和更新預覽
        self._minimap_gl_ready = False
        self._preview_gl_ready = False
        self.minimap_widget.glInitialized.connect(self._on_minimap_gl_ready)
        self.preview_widget.glInitialized.connect(self._on_preview_gl_ready)

        print("Scene Editor Initialized.")

    # --- 新增：處理 GL 初始化完成的 Slots ---
    def _check_all_gl_ready(self):
        """檢查所有 GL Widget 是否都已初始化"""
        if self._minimap_gl_ready and self._preview_gl_ready:
            print("All OpenGL Widgets Initialized. Loading initial scene...")
            self.load_initial_scene()

    def _on_minimap_gl_ready(self):
        self._minimap_gl_ready = True
        self._check_all_gl_ready()

    def _on_preview_gl_ready(self):
        self._preview_gl_ready = True
        self._check_all_gl_ready()
    # ---

    # --- 修改：使用 Dock Widgets 設定 UI ---
    def _setup_ui_with_docks(self):
        """使用 QDockWidget 設定 UI 佈局"""
        self.setDockOptions(QMainWindow.AllowNestedDocks | QMainWindow.AllowTabbedDocks | QMainWindow.AnimatedDocks)

        # 創建 Table Widget Dock
        self.table_dock = QDockWidget("Scene Editor", self)
        self.table_widget = SceneTableWidget(self.table_dock)
        self.table_dock.setWidget(self.table_widget)
        self.table_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.table_dock)

        # 創建 Minimap Widget Dock
        self.minimap_dock = QDockWidget("Minimap", self)
        self.minimap_widget = MinimapGLWidget(self.minimap_dock)
        self.minimap_dock.setWidget(self.minimap_widget)
        self.minimap_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea | Qt.BottomDockWidgetArea)
        self.addDockWidget(Qt.RightDockWidgetArea, self.minimap_dock)

        # 創建 3D Preview Widget Dock
        self.preview_dock = QDockWidget("3D Preview", self)
        self.preview_widget = PreviewGLWidget(self.preview_dock) # <--- 新增：實例化預覽 Widget
        self.preview_dock.setWidget(self.preview_widget)
        self.preview_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea | Qt.BottomDockWidgetArea)
        # 將 3D 預覽放在小地圖下方作為初始佈局
        self.splitDockWidget(self.minimap_dock, self.preview_dock, Qt.Vertical)

        # 調整初始大小比例 (可選)
        self.resizeDocks([self.table_dock], [int(self.width() * 0.4)], Qt.Horizontal)
        self.resizeDocks([self.minimap_dock, self.preview_dock], [int(self.height() * 0.5), int(self.height()*0.5)], Qt.Vertical)


        # 連接表格變更訊號到更新函數
        self.table_widget.sceneDataChanged.connect(self.update_previews) # <--- 修改：連接到新的更新函數


    # --- 保留原始的 _setup_ui，以備不時之需或比較 ---
    def _setup_ui_original(self):
        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        self.layout = QHBoxLayout(self.central_widget)
        self.splitter = QSplitter(Qt.Horizontal)
        self.layout.addWidget(self.splitter)
        self.table_widget = SceneTableWidget(self)
        self.splitter.addWidget(self.table_widget)
        self.minimap_widget = MinimapGLWidget(self)
        self.splitter.addWidget(self.minimap_widget)
        self.splitter.setSizes([int(self.width() * 0.4), int(self.width() * 0.6)])
        self.table_widget.sceneDataChanged.connect(self.update_previews) # 修改：連接到 update_previews

    def _setup_menu(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu('&File')
        save_action = QAction('&Save', self); save_action.setShortcut('Ctrl+S'); save_action.setStatusTip('Save scene file'); save_action.triggered.connect(self.save_scene_file); file_menu.addAction(save_action)
        reload_action = QAction('&Reload', self); reload_action.setShortcut('Ctrl+R'); reload_action.setStatusTip('Reload scene file from disk'); reload_action.triggered.connect(self.ask_reload_scene); file_menu.addAction(reload_action)
        exit_action = QAction('&Exit', self); exit_action.setShortcut('Ctrl+Q'); exit_action.setStatusTip('Exit application'); exit_action.triggered.connect(self.close); file_menu.addAction(exit_action)

        # --- 新增：View 選單，用於控制 Dock Widgets 的顯示/隱藏 ---
        view_menu = menubar.addMenu('&View')
        view_menu.addAction(self.table_dock.toggleViewAction())
        view_menu.addAction(self.minimap_dock.toggleViewAction())
        view_menu.addAction(self.preview_dock.toggleViewAction())


    def _setup_status_bar(self):
         self.statusBar = QStatusBar()
         self.setStatusBar(self.statusBar)
         self.statusBar.showMessage("Ready", 3000)

    def load_initial_scene(self):
        """載入場景檔案並觸發所有預覽更新"""
        # print("Loading initial scene for editor...") # 減少訊息
        if self.table_widget.load_scene_file(): # 這會觸發 sceneDataChanged
            self.statusBar.showMessage(f"Loaded '{SCENE_FILE}'", 5000)
            # sceneDataChanged 信號會自動調用 update_previews
        else:
            self.statusBar.showMessage(f"Failed to load '{SCENE_FILE}'", 5000)
            self.update_previews() # 即使載入失敗也要確保預覽被清空

    def save_scene_file(self):
        lines = self.table_widget.get_scene_lines()
        try:
            content_to_write = "\n".join(lines)
            if content_to_write and not content_to_write.endswith('\n'): content_to_write += '\n'
            with open(SCENE_FILE, 'w', encoding='utf-8') as f: f.write(content_to_write)
            self.table_widget.mark_saved()
            self.statusBar.showMessage(f"Saved '{SCENE_FILE}'", 3000)
            return True
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Could not save file '{SCENE_FILE}':\n{e}")
            self.statusBar.showMessage("Save failed", 5000)
            return False

    # --- 修改：更新所有預覽視窗 ---
    def update_previews(self):
        """解析表格數據，更新小地圖和 3D 預覽"""
        # print("Updating editor previews...") # 減少訊息
        lines = self.table_widget.get_scene_lines()

        # 解析場景 (不載入紋理，因為 renderer 會處理)
        # 注意：如果 renderer 需要紋理 ID，可能需要在解析時就載入一次
        # 保持 load_textures=False 看是否可行，如果 3D 預覽缺少紋理，再改為 True
        parsed_scene = scene_parser.parse_scene_from_lines(lines, load_textures=True) # <--- 修改為 True，確保 3D 預覽有紋理

        # --- 更新小地圖 ---
        # 小地圖需要烘焙，但在編輯器中我們使用動態繪製
        # bake_static_map_elements 通常在主模擬器中使用
        # 這裡直接將解析後的場景傳遞給 minimap widget
        try:
            self.minimap_widget.update_scene(parsed_scene)
        except Exception as e:
            print(f"Error updating minimap widget: {e}")

        # --- 更新 3D 預覽 ---
        try:
            # 3D 預覽也需要最新的場景數據來渲染
            # 需要創建軌道緩衝區，因為 renderer.draw_track 依賴它們
            if parsed_scene and parsed_scene.track:
                try:
                    # print("  Creating track buffers for preview...") # 減少訊息
                    parsed_scene.track.create_all_segment_buffers()
                except Exception as e:
                    print(f"  Error creating track buffers for preview: {e}")
            self.preview_widget.update_scene(parsed_scene)
        except Exception as e:
            print(f"Error updating 3D preview widget: {e}")


    def ask_reload_scene(self):
        if self.table_widget.is_modified():
            reply = QMessageBox.question(self, 'Reload Scene',
                                         "Discard current changes and reload from disk?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.No: return
        self.load_initial_scene()


    def closeEvent(self, event):
        if self.table_widget.is_modified():
            reply = QMessageBox.question(self, 'Exit Editor',
                                         "You have unsaved changes. Save before exiting?",
                                         QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                                         QMessageBox.Cancel)
            if reply == QMessageBox.Save:
                if not self.save_scene_file(): event.ignore(); return
            elif reply == QMessageBox.Discard: pass
            else: event.ignore(); return

        print("Cleaning up editor resources...")
        # --- 新增：停止 3D 預覽的計時器 ---
        if hasattr(self, 'preview_widget') and self.preview_widget._timer.isActive():
            self.preview_widget._timer.stop()
            print("Stopped preview timer.")

        minimap_renderer.cleanup_minimap_renderer() # 清理小地圖資源
        last_scene = scene_parser.get_current_scene()
        if last_scene and last_scene.track: last_scene.track.clear()

        # --- 清理 Pygame 資源 ---
        if pygame.font.get_init(): pygame.font.quit()
        if pygame.display.get_init(): pygame.display.quit()
        if pygame.get_init(): pygame.quit()
        print("Editor cleanup complete.")
        event.accept()


# --- Main Application Execution (Keep) ---
if __name__ == '__main__':
    try:
        os.chdir(os.path.dirname(os.path.abspath(__file__)))
        print(f"工作目錄設定為: {os.getcwd()}")
    except Exception as e:
        print(f"無法更改工作目錄: {e}")

    app = QApplication(sys.argv)
    editor = SceneEditorWindow()
    editor.show()
    sys.exit(app.exec_())