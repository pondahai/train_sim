# scene_editor.py
import sys
import os
import time # 用於計算 dt
import json # <--- 新增导入
# --- 新增：導入剪貼簿 ---
from PyQt5 import QtWidgets
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QSplitter,
    QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView,
    QVBoxLayout, QSizePolicy, QMenuBar, QAction, QMessageBox, QStatusBar,
    QDockWidget, QFileDialog  # 用於可停靠視窗
)
# --- 新增：導入 KeySequence ---
from PyQt5.QtCore import Qt, pyqtSignal, QPoint, QTimer, QStandardPaths, pyqtSlot # QTimer 用於預覽更新
from PyQt5.QtOpenGL import QGLWidget
# --- 新增：導入 Clipboard 和 KeySequence ---
from PyQt5.QtGui import QFont, QFontMetrics, QCursor, QKeySequence, QClipboard # QCursor 用於滑鼠鎖定
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

# ## Keep profiler if used
# import cProfile
# import pstats
# profiler = cProfile.Profile()
# profiler.enable()

# --- Constants ---
SCENE_FILE = "scene.txt"
EDITOR_WINDOW_TITLE = "Tram Scene Editor"
INITIAL_WINDOW_WIDTH = 1200
INITIAL_WINDOW_HEIGHT = 600
EDITOR_COORD_COLOR = (205, 205, 20, 200)
EDITOR_COORD_FONT_SIZE = 18
EDITOR_LABEL_OFFSET_X = 5
EDITOR_LABEL_OFFSET_Y = 3

# --- 3D 預覽視窗常數 ---
PREVIEW_UPDATE_INTERVAL = 100 # ms 
PREVIEW_MOVE_SPEED = 25.0 # units per second
PREVIEW_MOUSE_SENSITIVITY = 0.15
PREVIEW_ACCEL_FACTOR = 6.0 # Shift 加速倍率

# --- Minimap OpenGL Widget ---
class MinimapGLWidget(QGLWidget):
    """Custom OpenGL Widget for rendering the scene preview."""
    glInitialized = pyqtSignal()
    # scene_editor.py -> class MinimapGLWidget
    center3DPreviewAt = pyqtSignal(float, float)

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
        self._highlight_line_numbers = set() # 使用集合
        try:
            if pygame.font.get_init():
                self._coord_font = pygame.font.SysFont(None, EDITOR_COORD_FONT_SIZE)
        except Exception as e:
            print(f"Minimap Warning: Failed to create coordinate font: {e}")
            
        self._line_to_focus_on = -1 # 新增状态：存储请求定位的行号
        self._trigger_focus_on_paint = False # 新增状态：标记是否需要在下次绘制时执行定位
        self.zoom_end_timer = QTimer(self)
        self.zoom_end_timer.setSingleShot(True) # 確保是單次觸發
        self.zoom_end_timer.timeout.connect(self.endZooming)
        
        self._potential_drag_start_pos = None # 新增：记录潜在拖拽的起始位置
        self.DRAG_START_THRESHOLD = 5 # 移动多少像素才算开始拖拽 (可调整)

    def request_focus_on_line(self, line_number: int):
        """当表格请求小地图定位到场景文件中的某一行时调用此方法。"""
#         print(f"MinimapGLWidget: Received request to focus on line {line_number}") # Debug
        self._line_to_focus_on = line_number
        self._trigger_focus_on_paint = True # 标记在下次绘制时执行聚焦
        self.set_highlight_targets({line_number}) # 同时也设置高亮
        # 如果 self.set_highlight_targets 内部没有调用 self.update()，则需要在这里调用
        # 假设 set_highlight_targets 已经处理了 update()
        self.update()
    
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

        line_to_pass_for_focus = -1
        if self._trigger_focus_on_paint and self._line_to_focus_on > 0: # 确保行号有效
            line_to_pass_for_focus = self._line_to_focus_on
        
        returned_new_cx, returned_new_cz = None, None # 初始化
    
        try:
            # 調用 minimap_renderer 進行動態繪製
            returned_new_cx, returned_new_cz = minimap_renderer.draw_editor_preview(
                self._scene_data,
                self._view_center_x,
                self._view_center_z,
                self._view_range,
                w, h,
                self._is_dragging,
                highlight_line_nums=self._highlight_line_numbers, # 傳遞集合
                line_to_focus_on=line_to_pass_for_focus                
            )
        except Exception as e:
            print(f"Error calling draw_editor_preview: {e}")

        # 处理定位结果
        focus_action_taken = False
        if returned_new_cx is not None and returned_new_cz is not None and self._trigger_focus_on_paint:
#             print(f"{returned_new_cx} {returned_new_cz}")
            focus_action_taken = True
            center_changed = not (math.isclose(self._view_center_x, returned_new_cx) and \
                                  math.isclose(self._view_center_z, returned_new_cz))
            
            self._view_center_x = returned_new_cx
            self._view_center_z = returned_new_cz
            
            if center_changed:
                # print(f"Minimap focused: New center ({self._view_center_x:.1f}, {self._view_center_z:.1f}) for line {self._line_to_focus_on}") # Debug
                QTimer.singleShot(0, self.update) # 使用新中心重绘
            else:
                # print(f"Minimap focus requested for line {self._line_to_focus_on}, but center did not change.") # Debug
                pass # 中心未变，不需要再次 update
            
        elif self._trigger_focus_on_paint and line_to_pass_for_focus > 0:
            # 如果请求了聚焦，但没有返回有效坐标
            focus_action_taken = True # 尝试过聚焦
            # print(f"Minimap: Could not find locatable element for line {line_to_pass_for_focus} to focus.") # Debug

        if focus_action_taken: # 无论是否成功定位，只要尝试过聚焦，就重置状态
            self._trigger_focus_on_paint = False
            self._line_to_focus_on = -1

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

    def _map_to_world_coords(self, screen_x_in_widget, screen_y_in_widget_gl_style):
        # ... (代码如前一个回复所示) ...
        widget_w = self.width()
        widget_h = self.height()
        if widget_w <= 0 or widget_h <= 0 or abs(self._view_range) < 1e-6:
            return self._view_center_x, self._view_center_z

        scale = min(widget_w, widget_h) / self._view_range

        map_x_gl = screen_x_in_widget
        map_y_gl = screen_y_in_widget_gl_style

        delta_screen_x = map_x_gl - (widget_w / 2.0)
        delta_screen_y = map_y_gl - (widget_h / 2.0)

        world_dx_from_center = -delta_screen_x / scale
        world_dz_from_center =  delta_screen_y / scale

        target_world_x = self._view_center_x + world_dx_from_center
        target_world_z = self._view_center_z + world_dz_from_center
        return target_world_x, target_world_z

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._potential_drag_start_pos = event.pos() # 记录按下的位置
            # 不要在这里设置 _is_dragging 或改变光标，也不要 accept
        super().mousePressEvent(event) # 确保事件能被用于双击判断
        
    def mouseMoveEvent(self, event):
        if self._potential_drag_start_pos is not None and (event.buttons() & Qt.LeftButton): # 左键被按下且有拖拽可能
            if not self._is_dragging: # 如果还没开始拖拽
                # 计算移动距离
                delta = event.pos() - self._potential_drag_start_pos
                if delta.manhattanLength() > self.DRAG_START_THRESHOLD: # 超过阈值才开始拖拽
                    self._is_dragging = True
                    self._last_mouse_pos = self._potential_drag_start_pos # 或者 event.pos()，取决于你希望从哪开始算delta
                                                                      # 使用 _potential_drag_start_pos 更准确
                    self.setCursor(Qt.ClosedHandCursor)
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
                if not self.zoom_end_timer.isActive(): # 避免在快速缩放时也因为微小移动而调用
                    self.update() # Trigger repaint
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self._is_dragging:
                self._is_dragging = False
                self.setCursor(Qt.ArrowCursor)
                if not self.zoom_end_timer.isActive(): # 避免缩放刚结束时的release也触发update
                    self.update() # 更新一次以显示最终状态和普通光标
            self._potential_drag_start_pos = None # 重置
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event): # 这个方法保持不变
        if event.button() == Qt.LeftButton:
#             print(f"MinimapGLWidget: Left Button Double Clicked at {event.pos()}")
            screen_y_gl = self.height() - event.pos().y()
            world_x, world_z = self._map_to_world_coords(event.pos().x(), screen_y_gl)
#             print(f"MinimapGLWidget: Calculated world coords ({world_x:.1f}, {world_z:.1f})")
            self.center3DPreviewAt.emit(world_x, world_z)
#             print(f"MinimapGLWidget: Emitted center3DPreviewAt")
            event.accept() # 双击事件我们确实处理了
        else:
            super().mouseDoubleClickEvent(event)
            
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
            self._is_dragging = True
            self.update() # Trigger repaint

            # 啟動一個短定時器，在延遲後恢復文字顯示
            # 延遲時間可以調整，例如 100-250 毫秒
            self.zoom_end_timer.start(350) # 150ms 延遲

    def endZooming(self):
        """縮放操作結束後調用，用於恢復文字顯示"""
        self._is_dragging = False
        self.update() # 再次觸發繪製，此時文字會顯示

    def set_highlight_targets(self, line_numbers: set):
        """Sets the line numbers to be highlighted."""
        # 只在集合內容變化時才觸發更新
        if self._highlight_line_numbers != line_numbers:
            self._highlight_line_numbers = line_numbers.copy()
            self.update() # Trigger repaint

    def clear_highlight_targets(self):
        """Clears all highlighting."""
        if self._highlight_line_numbers: # 只在確實有高亮時才清除並更新
            self._highlight_line_numbers.clear()
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

    @pyqtSlot(float, float)
    def set_camera_xz_position(self, world_x, world_z):
        # print(f"PreviewGLWidget: Setting camera XZ to ({world_x:.1f}, {world_z:.1f})") # Debug
        self._camera.base_position[0] = world_x
        self._camera.base_position[2] = world_z
        self.update()
    
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
        """由 QTimer 触发的更新循环，主要处理键盘移动导致的位置变化"""
        current_time = time.time()
        dt = current_time - self._last_update_time
        self._last_update_time = current_time
        dt = min(dt, 0.1) # Clamp dt

        # --- 记录位置变化 ---
        position_changed = False
        old_pos = np.copy(self._camera.base_position)

        # 处理键盘移动
        self._update_camera_position(dt)

        # 检查位置是否变化
        if not np.allclose(old_pos, self._camera.base_position, atol=1e-6):
            position_changed = True

        # --- 仅在位置改变时请求重绘 ---
        # 角度变化现在由 mouseMoveEvent 立即触发更新
        if position_changed:
            self.update() # Request repaint ONLY if camera moved via keyboard

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
        should_update = False
        if isinstance(scene_object, Scene) or scene_object is None:
            # 检查场景对象本身或背景信息是否真的改变了
            if self._scene_data is not scene_object or self._current_background_info != background_info:
                 self._scene_data = scene_object
                 self._current_background_info = background_info
                 should_update = True
            # Don't call self.update() here automatically, let external changes trigger it
        else:
            print("Editor Preview received invalid scene data type.")

        # --- 如果数据确实更新了，触发一次重绘 ---
        if should_update:
            # print("Scene data updated, requesting repaint.") # Debug
            self.update() # Explicitly request repaint for scene changes

    def keyPressEvent(self, event):
        key = event.key()
        self._keys_pressed.add(key)
        should_update = False # Flag to check if we need an immediate update

        if key == Qt.Key_Tab:
            self.toggle_mouse_lock()
            should_update = True # Update to show/hide cursor immediately
        elif key == Qt.Key_G:
            self.show_ground_flag = not self.show_ground_flag
            should_update = True # Update to show/hide ground immediately
            print(f"3D Preview Ground: {'ON' if self.show_ground_flag else 'OFF'}") # Feedback
        elif key == Qt.Key_Escape:
            if self._mouse_locked:
                self._release_mouse()
                should_update = True # Update to show cursor immediately

        # 如果是移动键，不需要立即更新，让 timer loop 在下一帧检测变化
        # if key in [Qt.Key_W, Qt.Key_S, Qt.Key_A, Qt.Key_D, Qt.Key_Space, Qt.Key_Q]:
        #    pass # Let the timer handle updates for movement

        if should_update:
            self.update() # Trigger immediate repaint if needed

        event.accept()
        
    def keyReleaseEvent(self, event):
        if not event.isAutoRepeat():
            self._keys_pressed.discard(event.key())
        event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and not self._mouse_locked:
            self.toggle_mouse_lock()
            # toggle_mouse_lock 内部会调用 update()
        event.accept()

    def mouseMoveEvent(self, event):
        if self._mouse_locked:
            current_pos = event.pos()
            delta = current_pos - self._last_mouse_pos

            # --- 记录更新前的角度 ---
            old_yaw = self._camera.yaw
            old_pitch = self._camera.pitch

            # --- 更新相机角度 ---
            self._camera.update_angles(delta.x(), delta.y())

            # --- 检查角度是否真的改变了 ---
            # 这可以防止因微小的、未改变角度的 delta (可能由光标居中引起) 触发不必要的更新
            angles_changed = (old_yaw != self._camera.yaw or old_pitch != self._camera.pitch)

            # --- 居中光标 (保持不变) ---
            center_pos = QPoint(self.width() // 2, self.height() // 2)
            # 仅当光标实际移出中心且角度已改变时才重置光标位置
            if current_pos != center_pos and angles_changed:
                QCursor.setPos(self.mapToGlobal(center_pos))
                self._last_mouse_pos = center_pos
            else:
                 # 否则，只更新最后的位置，不重置光标（避免在中心点时的抖动）
                self._last_mouse_pos = current_pos


            # --- 如果角度改变了，立即触发重绘 ---
            if angles_changed:
                self.update() # <--- !! 添加这一行 !!

        else:
            # 鼠标未锁定时，仍然更新 last_mouse_pos，但不触发更新
            self._last_mouse_pos = event.pos()

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
            self.update() # Update to reflect cursor change

    def _release_mouse(self):
        if self._mouse_locked:
            self.releaseMouse()
            self.setCursor(Qt.ArrowCursor)
            self._mouse_locked = False
            self._camera.set_mouse_lock(False)
            self.update() # Update to reflect cursor change

    def toggle_mouse_lock(self):
        # 这个函数本身调用 _grab_mouse 或 _release_mouse，
        # 而这两个函数内部已经调用了 self.update()，所以这里不需要再调用
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
        self._filepath = None 
        self._command_hints = scene_parser.COMMAND_HINTS
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        # --- 修改：啟用擴展選擇模式 ---
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        # ---------------------------
        self.verticalHeader().setVisible(True)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        # Connections
        self.currentCellChanged.connect(self._on_current_cell_changed)
        self.itemChanged.connect(self._on_item_changed)
        self.needUpdate = False
        self._last_active_row = -1
        
        
        self.header_update_timer = QTimer(self)
        self.header_update_timer.setSingleShot(True)
        self.header_update_timer.timeout.connect(self._perform_header_update)
        self._pending_header_update_row = -1 # 記錄需要更新表頭的行

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

    def load_scene_file(self, filepath_to_load):
        remember_row = self._last_active_row 
        self.clear()
        self.setRowCount(0)
        self.setColumnCount(0)
        self._filepath = None # Reset filepath initially

        if not filepath_to_load or not os.path.exists(filepath_to_load): # Check if path is valid
            # If no path or path doesn't exist, set to empty state
            self.insertRow(0)
            self.setColumnCount(1)
            self.setHorizontalHeaderLabels(["Command"])
            self._resize_columns_to_header_labels()
            self._data_modified = False # No data loaded, so not modified from this "empty" state
            return False # Indicate failure to load specified file

        try:
            with open(filepath_to_load, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            self._filepath = filepath_to_load # <--- 更新：成功打開檔案後設定路徑

            if not lines: 
                self.insertRow(0)
                self.setColumnCount(1)
                self.setHorizontalHeaderLabels(["Command"])
                self._resize_columns_to_header_labels()
                self._data_modified = False # Empty file, not modified from this state
                # self.sceneDataChanged.emit() # Emit even for empty, so previews clear
                return True # Empty file is still a "successful" load of that file

            max_cols = 0
            for line in lines:
                stripped_line = line.strip()
                if stripped_line and not stripped_line.startswith('#'):
                    max_cols = max(max_cols, len(stripped_line.split()))
            max_cols = max(1, max_cols) 

            self.setColumnCount(max_cols + 8) # Add some buffer columns
            self.setRowCount(len(lines))

            self.blockSignals(True) 
            try:
                for row, line in enumerate(lines):
                    self.setVerticalHeaderItem(row, QTableWidgetItem(str(row + 1)))
                    parts = line.strip().split()
                    for col, part in enumerate(parts):
                        item = QTableWidgetItem(part)
                        self.setItem(row, col, item)
                    for col in range(len(parts), self.columnCount()): # Fill to actual column count
                        item = QTableWidgetItem("")
                        self.setItem(row, col, item)
            finally:
                self.blockSignals(False)

            self._data_modified = False
            if self.rowCount() > 0:
                self._on_current_cell_changed(0, 0, -1, -1) 
            else: 
                self.setHorizontalHeaderLabels(["Command"] + [f"P{i+1}" for i in range(max_cols-1 if max_cols > 0 else 0)])
                self._resize_columns_to_header_labels()
            # self.sceneDataChanged.emit() # Moved to SceneEditorWindow after this returns

            new_row_count = self.rowCount()
            if 0 <= remember_row < new_row_count:
                item_to_scroll = self.item(remember_row, 0) 
                if item_to_scroll:
                    self.setCurrentCell(remember_row, 0)
                    self.scrollToItem(item_to_scroll, QAbstractItemView.PositionAtCenter)
                    self._last_active_row = remember_row 
            else:
                self._last_active_row = -1 
            return True

        except Exception as e:
            print(f"Error loading scene file '{filepath_to_load}': {e}")
            self.clear()
            self.setRowCount(0)
            self.setColumnCount(0)
            self._filepath = None # <--- 更新：載入失敗，路徑無效
            self._last_active_row = -1 
            return False

    def get_current_filepath(self):
        """Returns the path of the currently loaded file."""
        return self._filepath

    def set_current_filepath(self, filepath):
        """Sets the internal filepath. Called by the main window after save as."""
        self._filepath = filepath
        
    def get_scene_lines(self):
        lines = []
        # 設定一個合理的單行最大參數檢查數量，以防表格列數異常大但實際無數據
        # 這個值應該大於你所有指令中可能有的最大參數個數
        MAX_PARAMS_PER_LINE_CHECK = 30 # 例如， building 指令有約17個參數

        for r in range(self.rowCount()):
            row_parts = []
            # 從第一列開始，逐列檢查是否有內容
            # 我們遍歷到 MAX_PARAMS_PER_LINE_CHECK 或者 self.columnCount() 中較小者，
            # 再額外檢查幾列以捕獲超出 columnCount 但用戶已輸入的內容。
            # 一個更簡單的方法是，直接迭代到 MAX_PARAMS_PER_LINE_CHECK，然後清理。
            
            # 實際有效的列數，我們應該考慮表格本身的 columnCount
            # 但也允許探測超出 columnCount 的、用戶可能剛輸入的單元格
            # 我們可以迭代到 max(self.columnCount(), REASONABLE_USER_INPUT_LIMIT)
            # 或者簡單地迭代到一個較大的固定數，然後清理尾部空值。

            potential_max_cols = max(self.columnCount(), MAX_PARAMS_PER_LINE_CHECK) # 看哪個更大
            # 但如果 columnCount 本身就很大了，就不需要 MAX_PARAMS_PER_LINE_CHECK
            # 應該是：檢查到 self.columnCount()，然後再往後探測幾列
            # 或者，直接用一個足夠大的數，然後清理。
            # 為了簡單和捕獲用戶輸入，我們用 MAX_PARAMS_PER_LINE_CHECK

            for c in range(MAX_PARAMS_PER_LINE_CHECK):
                item = self.item(r, c) # self.item(r,c) 在 c >= columnCount() 時會返回 None
                
                if item and item.text().strip(): # 有 item 且文本不為空
                    row_parts.append(item.text().strip())
                elif c < self.columnCount(): 
                    # 在 columnCount 範圍內，即使是空 item 或空文本，也先用空字符串佔位
                    # 以保持參數順序，後續會清理尾部空字符串
                    row_parts.append("") 
                else:
                    # 超出了 columnCount，並且 item 為 None 或文本為空，說明後面沒有數據了
                    break 
            
            # 清理尾部的空字符串 (這些是因為 columnCount 範圍內但單元格為空而添加的)
            while row_parts and row_parts[-1] == "":
                row_parts.pop()

            if row_parts: # 只有當行真的有內容（或至少有一個非空字串的參數）時才添加
                lines.append(" ".join(row_parts))
            else:
                # 如果想保留表格中的視覺空行作為場景文件中的空行
                lines.append("")
        
        # 在函數末尾打印，用於調試
        # print(f"DEBUG: get_scene_lines() returning: {lines}")
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

    # --- 新增：重新編號垂直表頭 ---
    def renumber_vertical_headers(self):
        """Updates the vertical header numbers after row insertion/deletion."""
        for r in range(self.rowCount()):
            self.setVerticalHeaderItem(r, QTableWidgetItem(str(r + 1)))
    # -----------------------------

    # --- 新增：複製選中行 ---
    def copy_selected_rows(self):
        """Copies the content of selected rows to the clipboard."""
        selected_indexes = self.selectionModel().selectedRows()
        if not selected_indexes:
            return

        # Sort selected rows by index
        rows_to_copy = sorted([index.row() for index in selected_indexes])

        clipboard_text = ""
        for row in rows_to_copy:
            row_data = []
            # --- MODIFICATION: Iterate only up to actual content for copying ---
            has_content = False
            temp_row_parts = []
            for col in range(self.columnCount()):
                item = self.item(row, col)
                cell_text = item.text() if item else ""
                temp_row_parts.append(cell_text)
                if cell_text: has_content = True
            # Trim trailing empty cells from the copied line, but only if there was content
            if has_content:
                while temp_row_parts and not temp_row_parts[-1]:
                    temp_row_parts.pop()
            row_data = temp_row_parts
            # --- END OF MODIFICATION ---
            clipboard_text += "\t".join(row_data) + "\n"

        if clipboard_text:
            clipboard = QApplication.clipboard()
            clipboard.setText(clipboard_text)
            # print(f"Copied {len(rows_to_copy)} rows to clipboard.") # Debug
    # ------------------------

    # --- 新增：貼上行 (插入模式) ---
    def paste_rows(self):
        """Pastes rows from the clipboard, inserting them below the current selection."""
        clipboard = QApplication.clipboard()
        clipboard_text = clipboard.text()
        if not clipboard_text:
            return

        # Determine insertion point
        current_row = self.currentRow() # Gets the row of the cell with focus
        selected_indexes = self.selectionModel().selectedRows()

        insert_row_index = -1
        if selected_indexes:
             # Insert below the last selected row
             insert_row_index = max(index.row() for index in selected_indexes) + 1
        elif current_row >= 0:
             # Insert below the current row if no full rows are selected
             insert_row_index = current_row + 1
        else:
             # Insert at the end if nothing is selected
             insert_row_index = self.rowCount()

        # Parse clipboard text into rows and columns
        lines = clipboard_text.strip('\n').split('\n')
        pasted_data = [line.split('\t') for line in lines]
        if not pasted_data: return

        self.blockSignals(True) 
        try:
            # --- MODIFICATION: Ensure table has enough columns for pasted data ---
            max_pasted_cols = 0
            for row_parts in pasted_data:
                max_pasted_cols = max(max_pasted_cols, len(row_parts))
            
            current_col_count = self.columnCount()
            if max_pasted_cols > current_col_count:
                self.setColumnCount(max_pasted_cols)
                # Update headers for new columns if necessary (though _on_current_cell_changed will do it)
                # for c_idx in range(current_col_count, max_pasted_cols):
                #     self.setHorizontalHeaderItem(c_idx, QTableWidgetItem(f"P{c_idx}"))
            col_count_to_use = self.columnCount() # Use updated column count
            # --- END OF MODIFICATION ---

            num_pasted = 0
            for i, row_parts in enumerate(pasted_data):
                actual_insert_pos = insert_row_index + i
                self.insertRow(actual_insert_pos)
                for col, part in enumerate(row_parts):
                    if col < col_count_to_use: 
                        item = QTableWidgetItem(part)
                        # --- 確保貼上的 Item 也是可編輯的 ---
                        # 假設原始的可編輯性是期望的，如果需要強制，則取消註解
                        # flags = item.flags() | Qt.ItemIsEditable
                        # item.setFlags(flags)
                        # ---------------------------------
                        self.setItem(actual_insert_pos, col, item)
                for col in range(len(row_parts), col_count_to_use):
                     item = QTableWidgetItem("")
                     # flags = item.flags() | Qt.ItemIsEditable
                     # item.setFlags(flags)
                     self.setItem(actual_insert_pos, col, item)
                num_pasted += 1
        finally:
            self.blockSignals(False)

        if num_pasted > 0:
            self.renumber_vertical_headers() # Update row numbers
            self._data_modified = True
            self.sceneDataChanged.emit() # Trigger preview update after paste
            # print(f"Pasted {num_pasted} rows at index {insert_row_index}.") # Debug
            # Optionally, select the newly pasted rows
            self.clearSelection()
            selection_range = QtWidgets.QTableWidgetSelectionRange(insert_row_index, 0, insert_row_index + num_pasted - 1, self.columnCount() - 1)
            self.setRangeSelected(selection_range, True)
            item_to_scroll = self.item(insert_row_index, 0)
            if item_to_scroll:
                self.scrollToItem(item_to_scroll, QAbstractItemView.PositionAtCenter)
    # --------------------------

    def keyPressEvent(self, event):
        key = event.key()
        modifiers = event.modifiers()

        # --- 修改：處理複製、貼上、刪除 ---
        if event.matches(QKeySequence.Copy):
            self.copy_selected_rows()
            event.accept()
            return
        elif event.matches(QKeySequence.Paste):
            self.paste_rows()
            event.accept()
            return
        elif key in (Qt.Key_Return, Qt.Key_Enter) and not modifiers: # Enter/Return without modifiers
            current_row = self.currentRow()
            if current_row >= 0:
                self.insertRow(current_row + 1)
                self.renumber_vertical_headers() # 更新行號
                self.setCurrentCell(current_row + 1, 0) # Move cursor to new row
                self._data_modified = True
                self.sceneDataChanged.emit() # Trigger preview update
                event.accept()
                return
        elif key == Qt.Key_Delete and not modifiers: # Delete without modifiers
            selected_ranges = self.selectedRanges()
            rows_to_delete = set()
            # Check if whole rows are selected
            for r in selected_ranges:
                if r.leftColumn() == 0 and r.rightColumn() == self.columnCount() - 1:
                    for i in range(r.topRow(), r.bottomRow() + 1):
                        rows_to_delete.add(i)

            if rows_to_delete:
                # Sort rows in descending order to delete from bottom up
                sorted_rows = sorted(list(rows_to_delete), reverse=True)
                self.blockSignals(True)
                try:
                    num_deleted = 0
                    for row_index in sorted_rows:
                        # --- MODIFICATION: Allow deleting non-empty rows as well ---
#                         if self.is_row_empty(row_index): 
                        self.removeRow(row_index)
                        num_deleted += 1
                        # --- END OF MODIFICATION ---
                        
                finally: self.blockSignals(False)
                if num_deleted > 0:
                    self.renumber_vertical_headers() # Update row numbers
                    self._data_modified = True
                    self.sceneDataChanged.emit() # Trigger preview update after delete
                    # print(f"Deleted {num_deleted} rows.") # Debug
                event.accept()
                return
        # ------------------------------------

        # Let the base class handle other key presses (like navigation)
        super().keyPressEvent(event)

    def mousePressEvent(self, event):
#         if event.button() == Qt.MiddleButton: # (这是功能二：表格定位小地图)
#             row_index = self.rowAt(event.pos().y())
#             if row_index >= 0:
#                 file_line_number = row_index + 1
#                 main_editor_window = self.window() # 获取父窗口 SceneEditorWindow
#                 if hasattr(main_editor_window, 'minimap_widget') and \
#                    hasattr(main_editor_window.minimap_widget, 'request_focus_on_line'):
#                     main_editor_window.minimap_widget.request_focus_on_line(file_line_number)
#                 event.accept()
#                 return # 中键点击已处理
        super().mousePressEvent(event) # 调用基类方法处理其他事件 (如左键选择)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton: # 确保是左键双击
            index = self.indexAt(event.pos()) # 获取双击位置的 QModelIndex
            if index.isValid(): # 确保点击在有效的单元格上
                row_index = index.row()
                file_line_number = row_index + 1 # 表格行是0-based, 文件行号是1-based
                
                main_editor_window = self.window() # 获取父窗口 SceneEditorWindow
                if hasattr(main_editor_window, 'minimap_widget') and \
                   hasattr(main_editor_window.minimap_widget, 'request_focus_on_line'):
                    main_editor_window.minimap_widget.request_focus_on_line(file_line_number)
                    print(f"Table double-clicked on row {row_index}: Requesting focus on line {file_line_number}") # Debug
                event.accept()
            else: # 如果点击在表格的空白区域
                super().mouseDoubleClickEvent(event)
        else:
            super().mouseDoubleClickEvent(event)
            
    def _on_current_cell_changed(self, currentRow, currentColumn, previousRow, previousColumn):
        if currentRow >= 0:
            self._last_active_row = currentRow

        # ---  ---
        if currentRow != previousRow and self.needUpdate:
            # 只有當選中的行確實改變了，並且在之前的行上有數據被修改過 (needUpdate is True)
            # 才觸發場景數據變更的信號，進而更新預覽。
            if currentRow >= 0: # 確保新行是有效的（雖然 currentRow != previousRow 暗示了這一點）
                print(f"DEBUG: SceneTableWidget._on_current_cell_changed - Row changed from {previousRow} to {currentRow} AND needUpdate is True. Emitting sceneDataChanged.")
                self.sceneDataChanged.emit()
            
            self.needUpdate = False # 重置 needUpdate 標誌，因為更新已經被觸發（或即將被觸發）
        # -------------------------

        # 觸發延遲的表頭更新
        self._pending_header_update_row = currentRow 
        self.header_update_timer.start(150) # 150ms 延遲，可以調整

    def _perform_header_update(self):
        currentRow = self._pending_header_update_row
        if currentRow < 0 or currentRow >= self.rowCount():
            # 處理表格清空後或無效行時的表頭 (例如，在 load_scene_file 後)
            if self.rowCount() == 0: # 如果表格是空的
                if self.columnCount() < 1: self.setColumnCount(1)
                self.setHorizontalHeaderLabels(["Command"] + [f"P{i+1}" for i in range(self.columnCount() - 1)])
                self._resize_columns_to_header_labels()
            return

        # --- 正常的行選擇邏輯 ---
        command_item = self.item(currentRow, 0)
        command = ""
        if command_item:
            command_text = command_item.text()
            if command_text:
                command = command_text.lower().strip()
        
        hints = self._command_hints.get(command, [])
        current_col_count = self.columnCount()

        # 決定新表頭的內容和長度
        # 期望的列數至少是 hints 的長度，或者對於無 command/hints 的情況，至少是1
        num_cols_for_new_header = len(hints) if command and hints else 1
        if not (command and hints) and current_col_count > 1 : # 無命令或無提示，但表格本身有多列
            num_cols_for_new_header = max(num_cols_for_new_header, current_col_count)


        new_headers = []
        if not command: # 空指令行
            new_headers = ["Command"] + [f"P{i}" for i in range(1, num_cols_for_new_header)]
        elif not hints: # 有指令但無提示
            new_headers = ["Command"] + [f"P{i}" for i in range(1, num_cols_for_new_header)]
        else: # 有指令且有提示
            new_headers = [hints[i] if i < len(hints) else f"P{i}" for i in range(num_cols_for_new_header)]
        
        # 確保第一個是 "Command" (如果 new_headers 為空或第一個不對)
        if not new_headers and num_cols_for_new_header > 0: new_headers.append("Command")
        elif new_headers and new_headers[0].strip().lower() != "command" and hints and hints[0].strip().lower() != "cmd" :
            if new_headers[0].strip() == "": new_headers[0] = "Command" # 如果是空則替換
            # 否則，如果hints[0]不是cmd，則可能 new_headers[0] 已經是參數了，這時應該在前面插入 "Command"
            # 但COMMAND_HINTS 的設計是第一個總是 " cmd "，所以這種情況理論上不該發生
        elif new_headers and new_headers[0].strip().lower() != "command" and not (hints and hints[0].strip().lower() == "cmd"):
             new_headers[0] = "Command" # 強制第一個為 Command

        # --- 更新列數和表頭 ---
        # 1. 列數只增不減：新的列數是當前列數和新表頭要求列數中的較大者。
        final_col_count = max(current_col_count, len(new_headers))
        
        if final_col_count > current_col_count:
            self.setColumnCount(final_col_count)
            # print(f"DEBUG: Increased column count to {final_col_count}")

        # 2. 準備最終的表頭標籤列表，長度必須與 final_col_count 匹配
        final_header_labels = []
        for i in range(final_col_count):
            if i < len(new_headers):
                final_header_labels.append(new_headers[i])
            else: # 如果 final_col_count > len(new_headers)，用 Px 填充
                final_header_labels.append(f"P{i}") 
        
        # 3. 比較並設置表頭
        current_header_texts_for_compare = [self.horizontalHeaderItem(c).text() if self.horizontalHeaderItem(c) else "" for c in range(self.columnCount())]
        if final_header_labels != current_header_texts_for_compare:
            self.setHorizontalHeaderLabels(final_header_labels)
            self._resize_columns_to_header_labels()
            # print(f"DEBUG: Headers updated. Count: {self.columnCount()}, Labels: {final_header_labels}")

    def _on_item_changed(self, item):
        # Mark data as modified and flag that an update is needed
        # The actual sceneDataChanged signal is emitted when the row changes (_on_current_cell_changed)
        self._data_modified = True
        self.needUpdate = True # Mark that an update *should* happen when row changes
#         print(f"DEBUG: Table item changed at row {item.row()}, col {item.column()}, text: '{item.text()}'")
#         self.sceneDataChanged.emit() # <--- 確保這裡發射信號

# --- Main Editor Window ---
class SceneEditorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(EDITOR_WINDOW_TITLE)
        self.setGeometry(100, 100, INITIAL_WINDOW_WIDTH, INITIAL_WINDOW_HEIGHT)
        self.settings_filepath = "editor_settings.json" # <--- 新增属性
        self._current_scene_filepath = None
        
        # Pygame/Loader Init
        pygame.init()
        pygame.font.init()
        # --- 新增：為編輯器設置一個最小的 Pygame 顯示模式 ---
        try:
            # 創建一個1x1像素的不可見窗口，僅用於初始化顯示子系統
            # 這對於需要 video mode 的 Pygame Surface 操作（如 convert_alpha）是必要的
            # 在 Qt 環境中，這個 Pygame 窗口實際上不會被看到或使用
            pygame.display.set_mode((1, 1), pygame.NOFRAME | pygame.HIDDEN) 
            # 或者，如果上面的組合不起作用，可以嘗試僅用 OPENGL，但QGLWidget應該處理GL上下文
            # pygame.display.set_mode((1, 1), pygame.OPENGL | pygame.HIDDEN)
            print("Scene Editor: Pygame display mode set (1x1 hidden) for surface operations.")
        except pygame.error as e:
            print(f"Scene Editor Warning: Could not set minimal Pygame display mode: {e}")
            print("                 Surface operations like convert_alpha() might fail in texture_loader.")
        # ----------------------------------------------------
        
        try:
            # print("Pygame font/mixer initialized for editor (no display mode set).") #R
            pass
        except pygame.error as e:
            print(f"Warning: Could not initialize Pygame subsystems: {e}")
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

    def _update_window_title(self):
        """Updates the window title based on the current file and modified state."""
        base_title = EDITOR_WINDOW_TITLE
        filename_part = "Untitled"
        if self._current_scene_filepath:
            filename_part = os.path.basename(self._current_scene_filepath)
        
        modified_indicator = "*" if self.table_widget.is_modified() else ""
        
        self.setWindowTitle(f"{base_title} - {filename_part}{modified_indicator}")
        
    def _save_settings(self):
        """Saves the current editor operational parameters to a JSON file."""
        settings = {}
        try:
            # 1. Minimap settings
            settings['minimap'] = {
                'center_x': self.minimap_widget._view_center_x,
                'center_z': self.minimap_widget._view_center_z,
                'range': self.minimap_widget._view_range
            }

            # 2. 3D Preview settings
            cam = self.preview_widget._camera
            settings['preview_camera'] = {
                'position': list(cam.base_position), # Convert numpy array to list for JSON
                'yaw': cam.yaw,
                'pitch': cam.pitch
            }

            # 3. Table settings
            settings['table'] = {
                'last_active_row': self.table_widget._last_active_row
            }

            # --- 新增：保存最後開啟的檔案 ---
            if self._current_scene_filepath: # 只在有有效路徑時保存
                settings['last_scene_file'] = self._current_scene_filepath
            elif 'last_scene_file' in settings: # 如果之前有但現在沒有了，可以選擇移除或保留
                pass # 或者 del settings['last_scene_file']
            # -----------------------------

            with open(self.settings_filepath, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=4)
            self.statusBar.showMessage("Editor settings saved.", 2000)
            # print(f"Editor settings saved to {self.settings_filepath}") # Debug
            return True
        except Exception as e:
            print(f"Error saving editor settings to '{self.settings_filepath}': {e}")
            self.statusBar.showMessage("Failed to save editor settings.", 3000)
            return False
        
    def _load_settings(self):
        """Loads editor operational parameters from a JSON file if it exists."""
        if not os.path.exists(self.settings_filepath):
            self.statusBar.showMessage("No editor settings file found, using defaults.", 2000)
            return False

        try:
            with open(self.settings_filepath, 'r', encoding='utf-8') as f:
                settings = json.load(f)

            # Apply Minimap settings
            if 'minimap' in settings:
                mm_settings = settings['minimap']
                self.minimap_widget._view_center_x = mm_settings.get('center_x', 0.0)
                self.minimap_widget._view_center_z = mm_settings.get('center_z', 0.0)
                self.minimap_widget._view_range = mm_settings.get('range', minimap_renderer.DEFAULT_MINIMAP_RANGE)
                self.minimap_widget.update() # Trigger repaint

            # Apply 3D Preview settings
            if 'preview_camera' in settings:
                cam_settings = settings['preview_camera']
                cam = self.preview_widget._camera
                cam.base_position = np.array(cam_settings.get('position', [10.0, 5.0, 10.0]), dtype=float)
                cam.yaw = cam_settings.get('yaw', -135.0)
                cam.pitch = cam_settings.get('pitch', -20.0)
                self.preview_widget.update() # Trigger repaint

            # Apply Table settings
            if 'table' in settings and self.table_widget.rowCount() > 0:
                tbl_settings = settings['table']
                last_row = tbl_settings.get('last_active_row', -1)
                if 0 <= last_row < self.table_widget.rowCount():
                    self.table_widget.setCurrentCell(last_row, 0)
                    self.table_widget._last_active_row = last_row # Explicitly set it
                    item_to_scroll = self.table_widget.item(last_row, 0)
                    if item_to_scroll:
                        self.table_widget.scrollToItem(item_to_scroll, QAbstractItemView.PositionAtCenter)
                else:
                    self.table_widget._last_active_row = -1 # Reset if invalid

            # --- 新增：載入並設定最後開啟的檔案路徑 ---
            if 'last_scene_file' in settings:
                self._current_scene_filepath = settings.get('last_scene_file')
                print(f"Editor settings: last_scene_file set to '{self._current_scene_filepath}'") # Debug
            else:
                self._current_scene_filepath = None # 確保如果設定中沒有，則為 None
            # ---------------------------------------

            self.statusBar.showMessage("Editor settings loaded.", 2000)
            # print(f"Editor settings loaded from {self.settings_filepath}") # Debug
            return True
        except Exception as e:
            print(f"Error loading editor settings from '{self.settings_filepath}': {e}")
            self.statusBar.showMessage("Failed to load editor settings.", 3000)
            return False
        
    def _check_all_gl_ready(self):
        if self._minimap_gl_ready and self._preview_gl_ready:
            print("All OpenGL Widgets Initialized. Loading initial scene...")
            # --- 修改：先載入設定檔 ---
            self._load_settings()  # 這會嘗試設定 self._current_scene_filepath
            # -----------------------
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
        
        # 確保有這條連接，用於觸發高亮和參數提示更新
        self.table_widget.currentCellChanged.connect(self._on_table_selection_changed)

        self.minimap_widget.center3DPreviewAt.connect(self.preview_widget.set_camera_xz_position)
        
        # --- 新增：連接 itemChanged 用於標題更新 ---
        self.table_widget.itemChanged.connect(self._on_table_item_changed_for_title)
        # -----------------------------------------

    def _on_table_item_changed_for_title(self, item):
        """Called when a table item is changed, updates the window title if modified."""
        if self.table_widget.is_modified(): # is_modified 應該由 table_widget._on_item_changed 設置
            self._update_window_title()
            
    def _setup_menu(self):
        menubar = self.menuBar()
        # File Menu
        file_menu = menubar.addMenu('&File')

        # --- 新增：Open Action ---
        open_action = QAction('&Open...', self)
        open_action.setShortcut(QKeySequence.Open)
        open_action.setStatusTip('Open scene file')
        open_action.triggered.connect(self.open_scene_file_dialog)
        file_menu.addAction(open_action)
        # ------------------------

        # --- 修改：Save Action ---
        save_action = QAction('&Save', self)
        save_action.setShortcut(QKeySequence.Save)
        save_action.setStatusTip('Save current scene file')
        save_action.triggered.connect(self.save_current_scene_file) # 改為調用新方法
        file_menu.addAction(save_action)
        # -----------------------

        # --- 新增：Save As Action ---
        save_as_action = QAction('Save &As...', self)
        save_as_action.setShortcut(QKeySequence.SaveAs)
        save_as_action.setStatusTip('Save current scene to a new file')
        save_as_action.triggered.connect(self.save_scene_file_as_dialog)
        file_menu.addAction(save_as_action)
        # -------------------------

        # --- 修改：Reload Action ---
        reload_action = QAction('&Reload', self)
        reload_action.setShortcut(QKeySequence.Refresh)
        reload_action.setStatusTip('Reload current scene file from disk')
        reload_action.triggered.connect(self.ask_reload_current_scene) # 改為調用新方法
        file_menu.addAction(reload_action)
        # ------------------------

        file_menu.addSeparator()

        exit_action = QAction('&Exit', self)
        exit_action.setShortcut(QKeySequence.Quit) # Use standard shortcut (Ctrl+Q)
        exit_action.setStatusTip('Exit application')
        exit_action.triggered.connect(self.close) # Connect to QMainWindow.close
        file_menu.addAction(exit_action)

        # --- 新增：Edit Menu (用於複製貼上) ---
        edit_menu = menubar.addMenu('&Edit')
        copy_action = QAction('&Copy Rows', self)
        copy_action.setShortcut(QKeySequence.Copy)
        copy_action.setStatusTip('Copy selected rows')
        copy_action.triggered.connect(self.table_widget.copy_selected_rows) # Connect to table method
        edit_menu.addAction(copy_action)

        paste_action = QAction('&Paste Rows (Insert)', self)
        paste_action.setShortcut(QKeySequence.Paste)
        paste_action.setStatusTip('Paste rows from clipboard, inserting below selection')
        paste_action.triggered.connect(self.table_widget.paste_rows) # Connect to table method
        edit_menu.addAction(paste_action)
        # ------------------------------------

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
        """Loads the scene file and triggers preview updates.
        Uses _current_scene_filepath if set, otherwise defaults to SCENE_FILE.
        """
        filepath_to_load = self._current_scene_filepath if self._current_scene_filepath and os.path.exists(self._current_scene_filepath) else SCENE_FILE
        
        if not os.path.exists(filepath_to_load) and filepath_to_load == self._current_scene_filepath:
            # If the last_scene_file from settings doesn't exist, try SCENE_FILE
            print(f"Initial file '{filepath_to_load}' not found, trying default '{SCENE_FILE}'.")
            filepath_to_load = SCENE_FILE

        if self.table_widget.load_scene_file(filepath_to_load):
            # load_scene_file in table_widget now sets its internal _filepath
            self._current_scene_filepath = self.table_widget.get_current_filepath() # Get the actual loaded path
            if self._current_scene_filepath:
                self.statusBar.showMessage(f"Loaded '{os.path.basename(self._current_scene_filepath)}'", 5000)
            else: # Should not happen if load_scene_file returned True
                self.statusBar.showMessage(f"Loaded '{filepath_to_load}', but path tracking issue.", 5000)
        else:
            # If the primary or default SCENE_FILE fails
            self.statusBar.showMessage(f"Failed to load '{filepath_to_load}'. Editor may be empty.", 5000)
            self._current_scene_filepath = None # Ensure it's None if no file is loaded
            # Ensure table is cleared and shows "Untitled"
            self.table_widget.clear()
            self.table_widget.setRowCount(0)
            self.table_widget.setColumnCount(1) # Minimal one column for "Command"
            self.table_widget.setHorizontalHeaderLabels(["Command"])

        self.update_previews()
        self._update_window_title()
        
    def _save_to_filepath(self, filepath_to_save):
        """Saves the current table content to the specified filepath."""
        if not filepath_to_save: # Should not happen if called by save_current or save_as
            QMessageBox.warning(self, "Save Error", "No filepath specified for saving.")
            return False

        lines = self.table_widget.get_scene_lines()
        try:
            content_to_write = "\n".join(lines)
            if content_to_write and not content_to_write.endswith('\n'):
                content_to_write += '\n'
            elif not content_to_write: # Handle empty file save
                content_to_write = '\n' # Save at least a newline for an empty file

            with open(filepath_to_save, 'w', encoding='utf-8') as f:
                f.write(content_to_write)
            
            self.table_widget.mark_saved()
            self._current_scene_filepath = filepath_to_save # Update current path
            self.table_widget.set_current_filepath(filepath_to_save) # Inform table widget too
            self._update_window_title()
            self.statusBar.showMessage(f"Saved '{os.path.basename(filepath_to_save)}'", 3000)
            self._save_settings() # Save editor settings (including new last_scene_file)
            return True
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Could not save file '{filepath_to_save}':\n{e}")
            self.statusBar.showMessage(f"Save failed for '{os.path.basename(filepath_to_save)}'", 5000)
            return False

    def save_current_scene_file(self):
        """Saves the scene to the current filepath, or prompts for Save As if no path."""
        if self._current_scene_filepath:
            return self._save_to_filepath(self._current_scene_filepath)
        else:
            return self.save_scene_file_as_dialog()

    def save_scene_file_as_dialog(self):
        """Opens a Save As dialog and saves the scene to the chosen file."""
        initial_dir = os.getcwd()
        if self._current_scene_filepath:
            initial_dir = os.path.dirname(self._current_scene_filepath)
        
        # 使用 QStandardPaths 獲取推薦的初始目錄，例如文件目錄
        # default_dir = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
        # initial_path = os.path.join(default_dir, os.path.basename(self._current_scene_filepath or "untitled.txt"))

        filePath, _ = QFileDialog.getSaveFileName(
            self,
            "Save Scene As",
            self._current_scene_filepath or os.path.join(initial_dir, "untitled.txt"), # Start in current dir or last file's dir
            "Text Files (*.txt);;All Files (*)"
        )
        if filePath:
            return self._save_to_filepath(filePath)
        return False # Dialog cancelled

    def open_scene_file_dialog(self):
        """Opens a file dialog to choose a scene file to load."""
        if self.table_widget.is_modified():
            reply = QMessageBox.question(self, 'Open File',
                                         "Discard current changes and open a new file?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.No:
                return

        initial_dir = os.getcwd()
        if self._current_scene_filepath:
            initial_dir = os.path.dirname(self._current_scene_filepath)

        filePath, _ = QFileDialog.getOpenFileName(
            self,
            "Open Scene File",
            initial_dir, # Start in current dir or last file's dir
            "Text Files (*.txt);;All Files (*)"
        )
        if filePath:
            if self.table_widget.load_scene_file(filePath):
                self._current_scene_filepath = filePath
                self.table_widget.set_current_filepath(filePath) # Inform table
                self._update_window_title()
                self.update_previews()
                self.statusBar.showMessage(f"Opened '{os.path.basename(filePath)}'", 3000)
                self._save_settings() # Save new last_scene_file to settings
            else:
                QMessageBox.critical(self, "Open Error", f"Could not load file '{filePath}'.")
                # Keep current state or clear? For now, keep.
                self._update_window_title() # Reflect that the file didn't change

    def update_previews(self): # 這是新的 update_previews，作為槽函數
        """
        Schedules the actual preview update logic to run in the next event loop iteration.
        This helps ensure that any pending Qt item model updates are completed before
        reading data from the table.
        """
#         print("DEBUG: SceneEditorWindow.update_previews() CALLED, scheduling _perform_preview_update_logic.")
        QTimer.singleShot(0, self._perform_preview_update_logic) # 延遲 0ms 執行
        
    def _perform_preview_update_logic(self):
        self.preview_widget.makeCurrent()
        """解析表格數據，更新小地圖和 3D 預覽 (包含背景)"""
        print("Updating editor previews...") # 可選的調試信息

        # 1. 從表格獲取當前所有行的文本內容 (這個函數本身是沒問題的)
        # lines = self.table_widget.get_scene_lines() # 我們可以直接讀取表格內容
        current_table_lines = self.table_widget.get_scene_lines()
#         print(f"DEBUG: update_previews - current_table_lines (around suspected tree): {current_table_lines[28]}") # 需要知道行號

#         if self.table_widget.is_modified(): # 只要表格被修改過
#             texture_loader.clear_texture_cache()
#             time.sleep(1)

        # --- 在這裡添加你之前的調試打印 ---
        # 假設你知道被修改的行是第28行 (0-based index for list)
#         MODIFIED_ROW_INDEX_FOR_DEBUG = 28 
#         if MODIFIED_ROW_INDEX_FOR_DEBUG < len(current_table_lines):
#             print(f"DEBUG: _perform_preview_update_logic - Line {MODIFIED_ROW_INDEX_FOR_DEBUG + 1} from table: '{current_table_lines[MODIFIED_ROW_INDEX_FOR_DEBUG]}'")
#         else:
#             print(f"DEBUG: _perform_preview_update_logic - Row index {MODIFIED_ROW_INDEX_FOR_DEBUG} is out of bounds for current_table_lines (len: {len(current_table_lines)}).")
        # ---------------------------------

        # 2. 獲取當前表格中選中的行號
        base_directory_for_imports = os.getcwd() # 預設為當前工作目錄
        current_filename_for_display = "Untitled" # 預設顯示的檔名

        if self._current_scene_filepath and os.path.exists(self._current_scene_filepath):
            base_directory_for_imports = os.path.dirname(self._current_scene_filepath)
            current_filename_for_display = os.path.basename(self._current_scene_filepath)
        elif self.table_widget.get_current_filepath(): # 如果表格知道自己的路徑（例如剛另存過）
            # 這種情況較少見，通常 _current_scene_filepath 會被優先更新
            temp_path = self.table_widget.get_current_filepath()
            base_directory_for_imports = os.path.dirname(temp_path)
            current_filename_for_display = os.path.basename(temp_path)


        # --- 確保 texture_loader 可用 ---
        if scene_parser.texture_loader is None:
            scene_parser.set_texture_loader(texture_loader)
        # ------------------------------

        # 3. 使用 scene_parser 解析當前表格的 *完整* 內容
        #    我們先獲取一次完整的 lines 列表用於解析 Scene 物件        
        parsed_scene = scene_parser.parse_scene_from_lines(current_table_lines, 
                                                            base_dir_for_import=base_directory_for_imports,
            filename_for_display=current_filename_for_display, load_textures=True)

        # --- 4. 決定 3D 預覽窗口應該顯示哪個背景 ---
        background_info_for_preview = None 
        current_row_in_table = self.table_widget.currentRow() # 獲取表格中當前選中的行

        if parsed_scene: # 只有在場景成功解析後才繼續判斷背景
            background_info_for_preview = parsed_scene.initial_background_info # 預設使用場景的初始背景

            if current_row_in_table >= 0 and current_row_in_table < len(current_table_lines):
                # 從當前選中的行開始，向上查找最近定義的 skybox 或 skydome 指令
                # 注意：這裡的 current_table_lines 是原始的、未經 import 展開的表格行
                # 我們需要解析的是這些原始行，而不是 parsed_scene 中的 background_triggers (那是基於軌道距離的)
                
                last_bg_info_found_upwards = None
                for i in range(current_row_in_table, -1, -1):
                    line_text = current_table_lines[i].strip()
                    if line_text and not line_text.startswith('#'):
                        parts = line_text.split()
                        cmd = parts[0].lower() if parts else ""
                        
                        if cmd == "skybox" and len(parts) > 1:
                            # 為了預覽，我們只需要類型和基本名稱
                            last_bg_info_found_upwards = {'type': 'skybox', 'base_name': parts[1]}
                            break 
                        elif cmd == "skydome" and len(parts) > 1:
                            # 為了預覽，我們需要類型、檔案名，並嘗試獲取已載入的紋理ID
                            skydome_file = parts[1]
                            skydome_tex_id = None
                            # 嘗試從 parsed_scene 中找到這個 skydome 的紋理 ID (如果它被定義為初始背景或觸發器)
                            if parsed_scene.initial_background_info and \
                               parsed_scene.initial_background_info.get('type') == 'skydome' and \
                               parsed_scene.initial_background_info.get('file') == skydome_file:
                                skydome_tex_id = parsed_scene.initial_background_info.get('id')
                            
                            if skydome_tex_id is None and parsed_scene.background_triggers:
                                for _, bg_info_dict in parsed_scene.background_triggers:
                                    if bg_info_dict.get('type') == 'skydome' and bg_info_dict.get('file') == skydome_file:
                                        skydome_tex_id = bg_info_dict.get('id')
                                        if skydome_tex_id: break
                            
                            # 如果在 parsed_scene 中找不到，並且 texture_loader 存在，可以嘗試即時載入 (通常不推薦在更新循環中)
                            # 或者依賴 parsed_scene 中已有的ID
                            if skydome_tex_id is None and texture_loader:
                                # print(f"Preview: Attempting to dynamically load skydome texture '{skydome_file}' for preview.")
                                skydome_tex_id = texture_loader.load_texture(skydome_file)


                            last_bg_info_found_upwards = {'type': 'skydome', 'file': skydome_file, 'id': skydome_tex_id}
                            break
                
                if last_bg_info_found_upwards is not None:
                    background_info_for_preview = last_bg_info_found_upwards

        # --- 5. 更新小地圖預覽 ---
        try:
            # 小地圖只需要解析後的 Scene 物件
            self.minimap_widget.update_scene(parsed_scene)
        except Exception as e:
            print(f"Error updating minimap widget: {e}")

        # --- 6. 更新 3D 預覽窗口 ---
        try:
            # 為新解析的場景創建軌道渲染所需的緩衝區
            if parsed_scene and parsed_scene.track:
                try:
                    self.preview_widget.makeCurrent() # 確保OpenGL上下文正確
                    parsed_scene.track.create_all_segment_buffers() # 創建主軌道和vbranch的緩衝區
                except Exception as e:
                    print(f"  Error creating track buffers for preview: {e}")
            
            # 將解析後的場景數據 和 決定好的預覽背景信息 傳遞給 3D 預覽窗口
            self.preview_widget.update_scene(parsed_scene, background_info_for_preview)
        except Exception as e:
            print(f"Error updating 3D preview widget: {e}")
            import traceback
            traceback.print_exc() # 打印更詳細的錯誤信息


    def ask_reload_current_scene(self):
        """Asks to reload the current scene file from disk."""
        if not self._current_scene_filepath or not os.path.exists(self._current_scene_filepath):
            QMessageBox.information(self, "Reload Scene", "No current file to reload or file does not exist.")
            return

        if self.table_widget.is_modified():
            reply = QMessageBox.question(self, 'Reload Scene',
                                         f"Discard current changes and reload '{os.path.basename(self._current_scene_filepath)}' from disk?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.No:
                return
        
        # Proceed with reload for the _current_scene_filepath
        if self.table_widget.load_scene_file(self._current_scene_filepath):
            self._update_window_title()
            self.update_previews()
            self.statusBar.showMessage(f"Reloaded '{os.path.basename(self._current_scene_filepath)}'", 3000)
        else:
            QMessageBox.critical(self, "Reload Error", f"Could not reload file '{self._current_scene_filepath}'.")

    def closeEvent(self, event):
        settings_saved_on_exit = self._save_settings() 
        if not settings_saved_on_exit:
             pass
            
        if self.table_widget.is_modified():
            reply = QMessageBox.question(self, 'Exit Editor',
                                         "You have unsaved changes. Save before exiting?",
                                         QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                                         QMessageBox.Cancel) 

            if reply == QMessageBox.Save:
                # --- 修改：調用 save_current_scene_file ---
                if not self.save_current_scene_file(): # This handles if _current_scene_filepath is None
                # ----------------------------------------
                    event.ignore() 
                    return
            elif reply == QMessageBox.Discard:
                pass 
            else: 
                event.ignore() 
                return

        # ... (其餘 cleanup 邏輯保持不變) ...
        print("Cleaning up editor resources...")
        if hasattr(self, 'preview_widget') and self.preview_widget._timer.isActive():
            self.preview_widget._timer.stop()
            print("Stopped preview timer.")

        minimap_renderer.cleanup_minimap_renderer()
        last_scene_in_editor = self.preview_widget._scene_data 
        if last_scene_in_editor and last_scene_in_editor.track:
            last_scene_in_editor.track.clear()
            print("Cleaned up track buffers from editor's last scene.")
        if texture_loader:
            texture_loader.clear_texture_cache()
        if hasattr(renderer, 'skybox_texture_cache'):
             for tex_id in renderer.skybox_texture_cache.values():
                 try:
                     glDeleteTextures(1, [tex_id])
                 except Exception as cleanup_error: print(f"Warn: Error cleaning up skybox texture {tex_id}: {cleanup_error}")
             renderer.skybox_texture_cache.clear()
             print("Skybox texture cache cleared.")

        if pygame.font.get_init():
            pygame.font.quit()
        print("Editor cleanup complete.")
        event.accept()

    def _on_table_selection_changed(self, current_row, current_column, previous_row, previous_column):
        # --- 高亮邏輯 ---
        if current_row >= 0:
            # 當選中有效行時，設置高亮目標為當前物理行號 (表格行索引+1)
            # 使用集合形式以保持擴展性
            self.minimap_widget.set_highlight_targets({current_row + 1})
        else:
            # 如果沒有選中任何行 (例如表格清空後)
            self.minimap_widget.clear_highlight_targets()
        
        # --- START OF MODIFICATION: Use self.table_widget._command_hints ---
        # This ensures we are using the same hint source as the table widget itself if it's directly populated.
        # Or, if the table widget gets hints from scene_parser, then scene_parser.COMMAND_HINTS is fine.
        # For consistency, let's assume the table_widget holds the definitive list it uses.
        # command_hints_source = self.table_widget._command_hints # Accessing "private" member, better if there's a getter
        command_hints_source = scene_parser.COMMAND_HINTS # Assuming this is the canonical source
        # --- END OF MODIFICATION ---

        # --- 更新參數提示 (這部分邏輯從 SceneTableWidget 移過來或保持獨立) ---
        # 建議將參數提示的更新邏輯也放在這裡，與高亮同步觸發
        if current_row >= 0:
            command_item = self.table_widget.item(current_row, 0)
            command = command_item.text().lower().strip() if command_item else ""
            hints = command_hints_source.get(command, []) 
            max_cols = self.table_widget.columnCount() # Use current table column count
            
            # Determine how many headers to generate based on hints or existing columns
            num_headers_needed = max(len(hints), max_cols if max_cols > 0 else 1)
            if command and not hints and max_cols > 0: # Command typed, but no hints, use Px for all
                num_headers_needed = max_cols
            elif not command and max_cols > 0: # Empty row, use Px
                 num_headers_needed = max_cols


            new_headers = []
            if not command and current_row >=0: # Empty or invalid command line
                new_headers = ["Command"] + [f"P{i}" for i in range(1, num_headers_needed if num_headers_needed >0 else 1)]
            elif not hints: # Command has no hints defined
                 new_headers = ["Command"] + [f"P{i}" for i in range(1, num_headers_needed if num_headers_needed >0 else 1)]
            else: # Command has hints
                 new_headers = [hints[i] if i < len(hints) else f"P{i}" for i in range(num_headers_needed)]

            current_actual_headers = []
            for c_idx in range(self.table_widget.columnCount()):
                header_item = self.table_widget.horizontalHeaderItem(c_idx)
                current_actual_headers.append(header_item.text() if header_item else "")
            
            # Only update if headers are different to prevent unnecessary resizing/flicker
            if new_headers != current_actual_headers:
                 # --- MODIFICATION: Ensure table has enough columns for all hints ---
                 if len(new_headers) > self.table_widget.columnCount():
                     self.table_widget.setColumnCount(len(new_headers))
                 # --- END OF MODIFICATION ---
                 self.table_widget.setHorizontalHeaderLabels(new_headers)
                 self.table_widget._resize_columns_to_header_labels() 
        else: # No row selected
            default_cols = self.table_widget.columnCount() if self.table_widget.columnCount() > 0 else 1
            self.table_widget.setHorizontalHeaderLabels(["Command"] + [f"P{i+1}" for i in range(default_cols -1)])
            self.table_widget._resize_columns_to_header_labels()
    
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
    # --- 修改：只退出已初始化的部分 ---
    if pygame.get_init():
        pygame.quit()
    if pygame.font.get_init():
        pygame.font.quit()
    # ----------------------------------

    sys.exit(exit_code)
