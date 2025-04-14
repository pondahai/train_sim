import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QSplitter,
    QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView,
    QVBoxLayout, QSizePolicy, QMenuBar, QAction, QMessageBox, QStatusBar
)
from PyQt5.QtCore import Qt, pyqtSignal, QPoint
from PyQt5.QtOpenGL import QGLWidget # Using QGLWidget for simplicity here
from PyQt5.QtGui import QFont # Import QFont for native Qt text rendering (Alternative)
from OpenGL.GL import *
from OpenGL.GLU import *
import pygame # Still needed for font rendering in renderer
import numpy as math

# --- Import Shared Modules ---
# Assuming they are in the same directory or accessible via sys.path
import scene_parser
import renderer
import texture_loader # Needed by scene_parser
from scene_parser import Scene # Import Scene class for type hinting/checking

# --- Constants ---
SCENE_FILE = "scene.txt"
EDITOR_WINDOW_TITLE = "Tram Scene Editor"
INITIAL_WINDOW_WIDTH = 1400
INITIAL_WINDOW_HEIGHT = 800

# --- Constants ---
# ... (Keep existing constants)
EDITOR_COORD_COLOR = (205, 205, 20, 200) # Yellowish color for coords
EDITOR_COORD_FONT_SIZE = 32
EDITOR_LABEL_OFFSET_X = 5 # Offset for labels from edge
EDITOR_LABEL_OFFSET_Y = 3

# --- Minimap OpenGL Widget ---
class MinimapGLWidget(QGLWidget):
    """Custom OpenGL Widget for rendering the scene preview."""
    
    glInitialized = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene_data = None  # Holds the parsed Scene object
        self._view_center_x = 0.0
        self._view_center_z = 0.0
        # Use view_range consistent with renderer's minimap logic
        self._view_range = renderer.DEFAULT_MINIMAP_RANGE
        self._min_range = renderer.MINIMAP_MIN_RANGE
        self._max_range = renderer.MINIMAP_MAX_RANGE
        self._zoom_factor = renderer.MINIMAP_ZOOM_FACTOR

        self._is_dragging = False
        self._last_mouse_pos = QPoint()

        # Enable mouse tracking even when button not pressed (optional)
        # self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus) # Ensure it can receive wheel events

        self._grid_label_font = None # Font for grid labels
        self._coord_font = None      # Font for center coordinates
        
        # --- NEW: Background Image State ---
        self._show_background_image = True # Default to showing background
        self._bg_texture_id = None
        self._bg_image_width_px = 0
        self._bg_image_height_px = 0
        self._map_filename = None
        self._map_world_cx = 0.0
        self._map_world_cz = 0.0
        self._map_world_scale = 1.0
        # --- End Background Image State ---        
        
        # Attempt to use the font initialized by the renderer
        if renderer.grid_label_font:
            self._grid_label_font = renderer.grid_label_font
            print("Minimap using pre-initialized grid label font.")
        else:
            # Fallback: Try to create font here (requires pygame.font initialized)
            try:
                if pygame.font.get_init(): # Check if initialized
                    self._grid_label_font = pygame.font.SysFont(None, renderer.MINIMAP_GRID_LABEL_FONT_SIZE)
                    print(f"Minimap created its own grid label font (size: {renderer.MINIMAP_GRID_LABEL_FONT_SIZE}).")
            except Exception as e:
                print(f"Minimap Warning: Failed to create grid label font: {e}")

        # Create font for coordinate display
        try:
            if pygame.font.get_init():
                self._coord_font = pygame.font.SysFont(None, EDITOR_COORD_FONT_SIZE)
                print(f"Minimap created coordinate display font (size: {EDITOR_COORD_FONT_SIZE}).")
        except Exception as e:
            print(f"Minimap Warning: Failed to create coordinate font: {e}")

        self.setFocusPolicy(Qt.StrongFocus) # Ensure it can receive key events
        
    def initializeGL(self):
        """Called once upon OpenGL initialization."""
        # Use the editor's background color
        r, g, b, a = renderer.EDITOR_BG_COLOR
        glClearColor(r, g, b, a)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        # No 3D lighting or depth test needed for 2D minimap
        # *** Signal that GL is ready ***
        self.glInitialized.emit()

    def resizeGL(self, w, h):
        """Called upon widget resize."""
        # Viewport is set in paintGL based on current size
        pass

    def paintGL(self):
        """Called whenever the widget needs to be painted."""
        glClear(GL_COLOR_BUFFER_BIT)
        w = self.width()
        h = self.height()
        if w == 0 or h == 0: return

        # --- Setup 2D Ortho Projection for this widget ---
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        # Match screen coordinates (0,0 at top-left) for easier mouse mapping?
        # Or standard GL (0,0 at bottom-left)? Let's use standard GL ortho.
        glOrtho(0.0, float(w), 0.0, float(h), -1.0, 1.0) # Y increases upwards
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

        glViewport(0, 0, w, h)

        # --- Disable 3D states ---
        glPushAttrib(GL_ENABLE_BIT | GL_CURRENT_BIT) # Save current enable/color state
        glDisable(GL_DEPTH_TEST)
        glDisable(GL_LIGHTING)
        glEnable(GL_BLEND) # Keep blend enabled for text potentially
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glDisable(GL_TEXTURE_2D) # Start with texture off

        widget_rect = (0, 0, w, h) # Draw in the entire widget area
        background_drawn = False # Flag to track if we drew a background

        # --- Step 1: Draw Background (Texture or Solid) ---
        # Inside paintGL, before if can_draw_texture:
#         print(f"DEBUG can_draw_texture Check:")
        _cond1 = self._show_background_image
        _cond2 = self._bg_texture_id is not None
        _cond3 = self._bg_image_width_px > 0
        _cond4 = self._bg_image_height_px > 0
        _cond5 = self._map_filename is not None
        _cond6 = abs(self._map_world_scale) > 1e-6
#         print(f"  _show_background_image: {_cond1}")
#         print(f"  _bg_texture_id is not None: {_cond2}")
#         print(f"  _bg_image_width_px > 0: {_cond3}")
#         print(f"  _bg_image_height_px > 0: {_cond4}")
#         print(f"  _map_filename is not None: {_cond5}")
#         print(f"  abs(_map_world_scale) > 1e-6: {_cond6}")

        # *** CHECK THIS LINE CAREFULLY ***
        can_draw_texture = (_cond1 and _cond2 and _cond3 and _cond4 and _cond5 and _cond6)
        # Ensure only 'and' operators are used and variable names are correct

#         print(f"  Result (can_draw_texture): {can_draw_texture}") # Should now print True or False

        if can_draw_texture:
            try:
                glEnable(GL_TEXTURE_2D)
                glBindTexture(GL_TEXTURE_2D, self._bg_texture_id)
                glColor4f(1.0, 1.0, 1.0, 1.0) # White base for texture

                view_center_x = self._view_center_x
                view_center_z = self._view_center_z
                view_range = self._view_range
                map_world_scale = self._map_world_scale # Use stored scale
                map_world_center_x = self._map_world_cx
                map_world_center_z = self._map_world_cz
                image_width_px = self._bg_image_width_px
                image_height_px = self._bg_image_height_px
                # Calculate world boundaries visible in the widget (using potentially non-square aspect)
                if view_range <= 0: view_range = renderer.MINIMAP_MIN_RANGE
                # Calculate scale based on widget dimensions and desired range
                scale_x = w / view_range # Scale for X might differ from Z if widget not square
                scale_z = h / view_range # We might need separate scales or adjust view range differently

                # For UV calculation, assume we want to show 'view_range' world units across the SHORTER widget dimension
                # This ensures the intended range is always visible.
                effective_scale = min(w, h) / view_range
                view_half_w_world = (w / effective_scale) / 2.0 # World half-width shown
                view_half_h_world = (h / effective_scale) / 2.0 # World half-height shown

                # World coordinates visible at the edges of the widget
                view_l = view_center_x - view_half_w_world
                view_r = view_center_x + view_half_w_world
                view_b = view_center_z - view_half_h_world # Bottom Z
                view_t = view_center_z + view_half_h_world # Top Z
                
                # Image world boundaries
                image_world_width = image_width_px * map_world_scale
                image_world_height = image_height_px * map_world_scale
                img_world_x_max = map_world_center_x + image_world_width / 2.0
                img_world_z_max = map_world_center_z + image_world_height / 2.0
                img_world_x_min = map_world_center_x - image_world_width / 2.0
                img_world_z_min = map_world_center_z - image_world_height / 2.0
                
                # Calculate UVs based on the visible world coords and image world coords
                if abs(image_world_width) < 1e-6 or abs(image_world_height) < 1e-6:
                    u_min, u_max, v_min, v_max = 0.0, 1.0, 0.0, 1.0
                    print("Warning: Calculated image world width/height is near zero.")
                else:
                    # 以下兩行是修改過的 改成 +img_world_x_max 因為要讓圖片跟著同方向移動
                    u_min = (-view_l + img_world_x_max) / image_world_width
                    u_max = (-view_r + img_world_x_max) / image_world_width
                    v_min = (view_b - img_world_z_min) / image_world_height # V=0 at Z_min
                    v_max = (view_t - img_world_z_min) / image_world_height # V=1 at Z_max
                    # print(f"DEBUG UVs: u=({u_min:.3f}, {u_max:.3f}), v=({v_min:.3f}, {v_max:.3f})") # Debug UV values

                # Inside if can_draw_texture, after UV calculation:
#                 print(f"DEBUG UVs: u=({u_min:.4f}, {u_max:.4f}), v=({v_min:.4f}, {v_max:.4f})")
#                 print(f"  Used view_l={view_l:.2f}, view_r={view_r:.2f}, view_b={view_b:.2f}, view_t={view_t:.2f}")
#                 print(f"  Used img_x_min={img_world_x_min:.2f}, img_z_min={img_world_z_min:.2f}, img_w={image_world_width:.2f}, img_h={image_world_height:.2f}")
                
                # Draw the textured Quad covering the widget
                # 修改以下 glTexCoord2f 內的u_max u_min  因為要把圖片左右相反
                glBegin(GL_QUADS)
                glTexCoord2f(u_max, v_min); glVertex2f(0, 0) # Bottom Left Vertex maps to (u_min, v_min) Tex Coord
                glTexCoord2f(u_min, v_min); glVertex2f(w, 0) # Bottom Right Vertex maps to (u_max, v_min) Tex Coord
                glTexCoord2f(u_min, v_max); glVertex2f(w, h) # Top Right Vertex maps to (u_max, v_max) Tex Coord
                glTexCoord2f(u_max, v_max); glVertex2f(0, h) # Top Left Vertex maps to (u_min, v_max) Tex Coord
                glEnd()

                glBindTexture(GL_TEXTURE_2D, 0)
                glDisable(GL_TEXTURE_2D)
                background_drawn = True
            except Exception as e:
                print(f"Error drawing background texture: {e}")
                if glIsEnabled(GL_TEXTURE_2D): glDisable(GL_TEXTURE_2D)

        # If texture wasn't drawn (or shouldn't be shown), draw solid color
        if not background_drawn:
            r, g, b, a = renderer.EDITOR_BG_COLOR
            glColor4f(r, g, b, a)
            glBegin(GL_QUADS)
            glVertex2f(0, 0); glVertex2f(w, 0); glVertex2f(w, h); glVertex2f(0, h)
            glEnd()
            background_drawn = True # Mark solid background as drawn

        # --- Step 2: Draw Scene Content using _render_map_view (WITHOUT its background) ---
        if self._scene_data:
            try:
                # Call the shared rendering function from renderer.py
                renderer._render_map_view(
                    self._scene_data,
                    self._view_center_x,
                    self._view_center_z,
                    self._view_range,
                    widget_rect,
                    draw_grid_labels=False, # Enable labels in editor?
                    background_color=None # Pass editor BG
                )
#                 # --- Draw Center Marker (Optional) ---
#                 glColor3f(1.0, 0.0, 0.0) # Red crosshair
#                 glLineWidth(1.0)
#                 widget_cx = w / 2.0
#                 widget_cy = h / 2.0
#                 cross_size = 10
#                 glBegin(GL_LINES)
#                 glVertex2f(widget_cx - cross_size, widget_cy)
#                 glVertex2f(widget_cx + cross_size, widget_cy)
#                 glVertex2f(widget_cx, widget_cy - cross_size)
#                 glVertex2f(widget_cx, widget_cy + cross_size)
#                 glEnd()
                pass
            except Exception as e:
                print(f"Error during _render_map_view call: {e}")
                # Optionally draw an error message on the widget itself
        else:
            # Draw only background if no scene data
            r, g, b, a = renderer.EDITOR_BG_COLOR
            glColor4f(r,g,b,a)
            glBegin(GL_QUADS)
            glVertex2f(0, 0); glVertex2f(w, 0); glVertex2f(w, h); glVertex2f(0, h)
            glEnd()

        # --- Step 3: Draw Editor Specific Overlays (Crosshair, Labels, Coords) ---
        # --- Draw Center Marker ---
        glColor3f(1.0, 0.0, 0.0) # Red crosshair
        glLineWidth(1.0)
        widget_cx = w / 2.0
        widget_cy = h / 2.0
        cross_size = 10
        glBegin(GL_LINES)
        glVertex2f(widget_cx - cross_size, widget_cy); glVertex2f(widget_cx + cross_size, widget_cy)
        glVertex2f(widget_cx, widget_cy - cross_size); glVertex2f(widget_cx, widget_cy + cross_size)
        glEnd()

        # --- Draw Grid Labels (outside _render_map_view) ---
        show_labels = self._grid_label_font and self._view_range < renderer.DEFAULT_MINIMAP_RANGE * 1.5
        if show_labels:
            # Calculate world boundaries and scale again (needed for label placement)
            if self._view_range <= 0: self._view_range = renderer.MINIMAP_MIN_RANGE
            scale = min(w, h) / self._view_range
            world_half_range_x = (w / scale) / 2.0
            world_half_range_z = (h / scale) / 2.0
            world_view_left = self._view_center_x - world_half_range_x
            world_view_right = self._view_center_x + world_half_range_x
            world_view_bottom_z = self._view_center_z - world_half_range_z
            world_view_top_z = self._view_center_z + world_half_range_z
            grid_scale = renderer.MINIMAP_GRID_SCALE

            start_grid_x = math.floor(world_view_left / grid_scale) * grid_scale
            start_grid_z = math.floor(world_view_bottom_z / grid_scale) * grid_scale

            # Draw X labels (at the bottom edge)
            current_grid_x = start_grid_x
            while current_grid_x <= world_view_right:
                map_x, _ = renderer._world_to_map_coords_adapted(current_grid_x, self._view_center_z, self._view_center_x, self._view_center_z, widget_cx, widget_cy, scale)
                # Check if the label position is within the widget width
                if 0 <= map_x <= w:
                    label_text = f"{current_grid_x:.0f}"
                    try:
                        text_surface = self._grid_label_font.render(label_text, True, renderer.MINIMAP_GRID_LABEL_COLOR)
                        draw_label_x = map_x - text_surface.get_width() / 2
                        draw_label_y = EDITOR_LABEL_OFFSET_Y # Offset from bottom
                        renderer._draw_text_texture(text_surface, draw_label_x, draw_label_y)
                    except Exception as e: print(f"渲染 X 標籤時出錯: {e}")
                current_grid_x += grid_scale

            # Draw Z labels (at the left edge)
            current_grid_z = start_grid_z
            while current_grid_z <= world_view_top_z:
                 _, map_y = renderer._world_to_map_coords_adapted(self._view_center_x, current_grid_z, self._view_center_x, self._view_center_z, widget_cx, widget_cy, scale)
                 # Check if the label position is within the widget height
                 if 0 <= map_y <= h:
                    label_text = f"{current_grid_z:.0f}"
                    try:
                        text_surface = self._grid_label_font.render(label_text, True, renderer.MINIMAP_GRID_LABEL_COLOR)
                        draw_label_x = EDITOR_LABEL_OFFSET_X # Offset from left
                        draw_label_y = map_y - text_surface.get_height() / 2
                        renderer._draw_text_texture(text_surface, draw_label_x, draw_label_y)
                    except Exception as e: print(f"渲染 Z 標籤時出錯: {e}")
                 current_grid_z += grid_scale

        # --- Draw Center Coordinate Label ---
        if self._coord_font:
            coord_text = f"Center: ({self._view_center_x:.1f}, {self._view_center_z:.1f}) Range: {self._view_range:.1f}"
            try:
                text_surface = self._coord_font.render(coord_text, True, EDITOR_COORD_COLOR)
                text_width = text_surface.get_width()
                text_height = text_surface.get_height()
                # Position at top-right corner
                draw_x = w - text_width - EDITOR_LABEL_OFFSET_X
                draw_y = h - text_height - EDITOR_LABEL_OFFSET_Y # Offset from top
                renderer._draw_text_texture(text_surface, draw_x, draw_y)
            except Exception as e:
                print(f"渲染中心座標時出錯: {e}")

        glPopAttrib() # Restore enable/color state

    # --- NEW: Keyboard Event Handler ---
    def keyPressEvent(self, event):
        """Handles key presses for the minimap widget."""
        key = event.key()
        if key == Qt.Key_M:
            self._show_background_image = not self._show_background_image
            print(f"Minimap background image {'shown' if self._show_background_image else 'hidden'}.")
            self.update() # Trigger repaint to reflect change
            event.accept()
        else:
            # Pass other keys to the base class (or ignore)
            event.ignore() # Important for focus handling in parent widgets

    # --- NEW: Method to load/unload background texture ---
    def _update_background_texture(self, filename):
        """Loads the specified image file as the background texture."""
        # --- Cleanup previous texture ---
        if self._bg_texture_id is not None:
            # Check if context is current before deleting? Usually is here.
            # Need to make context current if called from wrong thread, but likely okay.
            try:
                 # It's important to make the context current before GL calls
                 # if this is called from a non-paintGL context, though
                 # update_scene should be called from the main thread where context is likely current.
                 # self.makeCurrent() # Make sure context is current
                 if glIsTexture(self._bg_texture_id):
                      glDeleteTextures(1, [self._bg_texture_id])
                 # self.doneCurrent()
            except Exception as e:
                 print(f"Warning: Error deleting old background texture: {e}")
            self._bg_texture_id = None
            self._bg_image_width_px = 0
            self._bg_image_height_px = 0

        self._map_filename = filename # Store the new filename regardless of success

        if filename is None:
            self.update() # Trigger repaint to show solid color
            return # No texture to load

        filepath = os.path.join("textures", filename)
        if not os.path.exists(filepath):
            print(f"Editor Warning: Background image '{filepath}' not found.")
            self.update()
            return

        print(f"Editor: Loading background texture '{filepath}'...")
        # Use texture_loader logic (or replicate parts)
        # For simplicity, replicating relevant parts here:
        try:
            # self.makeCurrent() # Ensure context is current before GL calls
            surface = pygame.image.load(filepath).convert_alpha() # Use convert_alpha
            texture_data = pygame.image.tostring(surface, "RGBA", True)
            w_px, h_px = surface.get_width(), surface.get_height()

            if w_px <= 0 or h_px <= 0:
                print(f"Editor Warning: Background image '{filepath}' has invalid dimensions.")
                # self.doneCurrent()
                return

            self._bg_image_width_px = w_px
            self._bg_image_height_px = h_px

            tex_id = glGenTextures(1)
            glBindTexture(GL_TEXTURE_2D, tex_id)
            # Use CLAMP_TO_EDGE for background maps usually
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR) # Use linear for zooming
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, w_px, h_px, 0, GL_RGBA, GL_UNSIGNED_BYTE, texture_data)
            glBindTexture(GL_TEXTURE_2D, 0)

            self._bg_texture_id = tex_id
            print(f"Editor: Background texture loaded (ID: {tex_id}, {w_px}x{h_px}px).")
            # self.doneCurrent()
        except Exception as e:
            print(f"Editor Error: Failed to load background texture '{filepath}': {e}")
            self._bg_texture_id = None
            self._bg_image_width_px = 0
            self._bg_image_height_px = 0
            # if self.isValid(): self.doneCurrent() # Check if context was made current

        self.update() # Trigger repaint

    def update_scene(self, scene_object):
        """Slot to receive updated scene data."""
        if isinstance(scene_object, Scene):
            new_map_filename = scene_object.map_filename
            # Check if background map needs updating
            if new_map_filename != self._map_filename:
                 print(f"Editor: Map filename changed from '{self._map_filename}' to '{new_map_filename}'. Updating texture...")
                 self._update_background_texture(new_map_filename) # Load/unload texture

            # Store scene data and map parameters
            self._scene_data = scene_object
            self._map_filename = new_map_filename # Ensure consistency
            self._map_world_cx = scene_object.map_world_center_x
            self._map_world_cz = scene_object.map_world_center_z
            self._map_world_scale = scene_object.map_world_scale if scene_object.map_world_scale > 1e-6 else 1.0

            self.update()            
        elif scene_object is None:
            # Clear scene and potentially unload texture
            if self._map_filename is not None:
                 self._update_background_texture(None) # Unload texture
            self._scene_data = None
            self.update() # Trigger repaint with empty scene
            print("Minimap cleared.")
        else:
            print("Minimap received invalid scene data type.")


    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._is_dragging = True
            self._last_mouse_pos = event.pos()
            self.setCursor(Qt.ClosedHandCursor) # Change cursor during drag

    def mouseMoveEvent(self, event):
        if self._is_dragging:
            delta = event.pos() - self._last_mouse_pos
            w = self.width()
            h = self.height()
            if w > 0 and h > 0 and self._view_range > 0:
                # Convert screen pixel delta to world coordinate delta
                # Using average scale for simplicity if widget not square
                scale = min(w, h) / self._view_range
                # Note: QPoint y increases downwards, OpenGL y increases upwards in our ortho
                world_dx = -delta.x() / scale
                world_dz = -delta.y() / scale # Invert Y delta for Z

                self._view_center_x -= world_dx
                self._view_center_z -= world_dz

                self._last_mouse_pos = event.pos()
                self.update() # Trigger repaint

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._is_dragging:
            self._is_dragging = False
            self.setCursor(Qt.ArrowCursor) # Restore cursor

    def wheelEvent(self, event):
        """Handles mouse wheel scrolling for zooming."""
        delta = event.angleDelta().y() # Typically +/- 120
        if delta > 0: # Scroll up -> Zoom in
            factor = 1.0 / self._zoom_factor
        elif delta < 0: # Scroll down -> Zoom out
            factor = self._zoom_factor
        else:
            return

        new_range = self._view_range * factor
        # Clamp zoom level
        self._view_range = max(self._min_range, min(self._max_range, new_range))
        # print(f"Minimap view range: {self._view_range:.1f}")
        self.update() # Trigger repaint

# --- Table Widget for Scene Data ---
class SceneTableWidget(QTableWidget):
    """Custom Table Widget for editing scene file content."""
    # Signal emitted when data changes significantly (edit, insert row)
    sceneDataChanged = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data_modified = False
        self._filepath = SCENE_FILE # Store the path
        self._command_hints = scene_parser.COMMAND_HINTS # Get hints

        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection) # Select one row at a time
        self.verticalHeader().setVisible(True) # Show line numbers

        # Connect signals
        self.currentCellChanged.connect(self._on_current_cell_changed)
        self.itemChanged.connect(self._on_item_changed)

    def load_scene_file(self):
        """Loads content from the scene file into the table."""
        self.clear() # Clear previous headers and content
        self.setRowCount(0)
        self.setColumnCount(0) # Reset columns

        if not os.path.exists(self._filepath):
            print(f"Scene file '{self._filepath}' not found. Creating empty table.")
            # Maybe add one empty row?
            self.insertRow(0)
            self.setColumnCount(1) # Need at least one column
            self.setHorizontalHeaderLabels(["Command"])
            return False

        try:
            with open(self._filepath, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            if not lines:
                self.insertRow(0)
                self.setColumnCount(1)
                self.setHorizontalHeaderLabels(["Command"])
                return True

            # First pass: find max columns needed
            max_cols = 0
            for line in lines:
                parts = line.strip().split()
                max_cols = max(max_cols, len(parts))
            max_cols = max(1, max_cols) # Ensure at least one column
            self.setColumnCount(max_cols)
            self.setHorizontalHeaderLabels([f"P{i}" for i in range(max_cols)]) # Default headers

            # Second pass: populate table
            self.setRowCount(len(lines))
            self.blockSignals(True) # <--- Block signals
            try:
                for row, line in enumerate(lines):
                    self.setVerticalHeaderItem(row, QTableWidgetItem(str(row + 1))) # Line number
                    parts = line.strip().split()
                    for col, part in enumerate(parts):
                        item = QTableWidgetItem(part)
                        # Comments are usually not editable, but here we allow it
                        # if line.strip().startswith('#'):
                        #     item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                        self.setItem(row, col, item)
                    # Fill remaining columns in the row with empty items if needed
                    for col in range(len(parts), max_cols):
                         self.setItem(row, col, QTableWidgetItem(""))
            finally:
                # Ensure signals are unblocked even if error occurs
                self.blockSignals(False) # <--- Unblock signals


            self._data_modified = False
            self.resizeColumnsToContents()
            print(f"Loaded '{self._filepath}' into table.")
            # Emit signal AFTER loading is complete
            self.sceneDataChanged.emit()
            return True

        except Exception as e:
            print(f"Error loading scene file '{self._filepath}': {e}")
            self.clear()
            self.setRowCount(0)
            self.setColumnCount(0)
            return False

    def get_scene_lines(self):
        """Gets the current content of the table as a list of strings."""
        lines = []
        for row in range(self.rowCount()):
            row_parts = []
            for col in range(self.columnCount()):
                item = self.item(row, col)
                if item and item.text(): # Only include non-empty cells
                    row_parts.append(item.text())
                elif item is None or not item.text():
                    # Stop processing columns for this row if an empty cell is found?
                    # Or include based on expected command length? Simpler to just take existing.
                    # Let's break to avoid trailing spaces from empty columns
                     break
            lines.append(" ".join(row_parts))
        return lines

    def is_modified(self):
        """Checks if the table data has been modified since last load/save."""
        return self._data_modified

    def mark_saved(self):
        """Resets the modified flag."""
        self._data_modified = False

    def is_row_empty(self, row_index):
        """Checks if all cells in the given row are empty or contain only whitespace."""
        if row_index < 0 or row_index >= self.rowCount():
            return False # Invalid row index
        for col in range(self.columnCount()):
            item = self.item(row_index, col)
            # Consider a cell empty if it's None or its text is empty/whitespace
            if item is not None and item.text().strip():
                return False # Found non-empty cell
        return True # All cells are empty or None

    # --- Event Handlers ---
    def keyPressEvent(self, event):
        """Handles key presses, specifically Enter for inserting rows."""
        key = event.key()
        if key in (Qt.Key_Return, Qt.Key_Enter):
            current_row = self.currentRow()
            if current_row >= 0:
                self.insertRow(current_row + 1)
                # Set vertical header for the new row
                self.setVerticalHeaderItem(current_row + 1, QTableWidgetItem(str(current_row + 2)))
                # Adjust subsequent vertical headers (optional, but good practice)
                for r in range(current_row + 2, self.rowCount()):
                     self.setVerticalHeaderItem(r, QTableWidgetItem(str(r + 1)))

                self.setCurrentCell(current_row + 1, 0) # Focus new row
                self._data_modified = True
                self.sceneDataChanged.emit() # Notify change
                # Trigger auto-save via main window
#                 if self.parent() and hasattr(self.parent(), 'save_scene_file'):
#                     self.parent().save_scene_file() # Assumes parent has this method
                event.accept() # Consume the event
                return # Prevent default behavior
        elif key == Qt.Key_Delete:
            # Check if a full row is selected
            selected_ranges = self.selectedRanges()
            # A full row selection usually results in one range spanning all columns for that row
            if len(selected_ranges) == 1:
                selection_range = selected_ranges[0]
                # Check if the selection spans the entire row width and only one row vertically
                if selection_range.leftColumn() == 0 and \
                   selection_range.rightColumn() == self.columnCount() - 1 and \
                   selection_range.rowCount() == 1:

                    row_to_delete = selection_range.topRow()

                    # Check if the selected row is empty
                    if self.is_row_empty(row_to_delete):
                        # Optional confirmation dialog
                        # reply = QMessageBox.question(self, 'Delete Row',
                        #                              f"Delete empty row {row_to_delete + 1}?",
                        #                              QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                        # if reply == QMessageBox.No:
                        #     event.accept() # Consume event even if not deleted
                        #     return

                        # Proceed with deletion
                        self.removeRow(row_to_delete)
                        # Adjust subsequent vertical headers
                        for r in range(row_to_delete, self.rowCount()):
                            self.setVerticalHeaderItem(r, QTableWidgetItem(str(r + 1)))

                        self._data_modified = True
                        self.sceneDataChanged.emit() # Notify change
                        # Trigger auto-save maybe? Or let user save manually?
                        # Let's trigger save for consistency with Enter
                        if self.parent() and hasattr(self.parent(), 'save_scene_file'):
                             self.parent().save_scene_file()

                        print(f"Deleted empty row {row_to_delete + 1}")
                        event.accept() # Consume the delete event
                        return # Prevent default delete behavior (like clearing cell content)

            # If not deleting a full empty row, let the default behavior handle cell clearing etc.
            # Or explicitly ignore here if you ONLY want Delete for full empty rows
            # event.ignore()
        # Call base class implementation for other keys
        super().keyPressEvent(event)

    def _on_current_cell_changed(self, currentRow, currentColumn, previousRow, previousColumn):
        """Updates column headers with hints when the selected row changes."""
        if currentRow < 0 or currentRow >= self.rowCount():
             # Reset headers if selection is invalid
             for c in range(self.columnCount()):
                 self.setHorizontalHeaderItem(c, QTableWidgetItem(f"P{c}"))
             return

        command_item = self.item(currentRow, 0)
        command = command_item.text().lower().strip() if command_item else ""

        hints = self._command_hints.get(command, [])

        max_cols = self.columnCount()
        current_headers = []
        # Set headers based on hints
        for i, hint in enumerate(hints):
            if i < max_cols:
                current_headers.append(hint)
            else: # Need more columns for hints? (Shouldn't happen if table is wide enough)
                 pass
        # Fill remaining headers with default names
        for i in range(len(hints), max_cols):
            current_headers.append(f"P{i}")

        self.setHorizontalHeaderLabels(current_headers)

    def _on_item_changed(self, item):
        """Called when a cell's content is changed by the user."""
        # Avoid triggering during initial load if possible (tricky)
        # A simple flag might be needed during load_scene_file
        self._data_modified = True
        # Don't emit signal on every character typed, usually triggers on focus lost/enter.
        # But itemChanged *does* fire on programmatic changes too.
        # Maybe emit only if the change wasn't programmatic?
        # For now, emitting here is simplest.
        self.sceneDataChanged.emit()

# --- Main Editor Window ---
class SceneEditorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(EDITOR_WINDOW_TITLE)
        self.setGeometry(100, 100, INITIAL_WINDOW_WIDTH, INITIAL_WINDOW_HEIGHT) # x, y, w, h

        # --- Crucial: Set texture loader for scene_parser ---
        # We might need pygame initialized for texture_loader itself
        pygame.init() # Initialize pygame just for font/image loading
        pygame.font.init() # Needed if renderer uses pygame fonts
        try:
            # Try setting display mode after Qt app exists but before heavy use
            pygame.display.set_mode((64, 64), pygame.RESIZABLE)
            pygame.display.set_caption("Pygame Helper (Editor)")
            print("Pygame display mode set inside Editor init.")
        except pygame.error as e:
             print(f"Warning: Could not set Pygame display mode in init: {e}")
        # Initialize our simple texture loader
        scene_parser.set_texture_loader(texture_loader)
        # Initialize renderer (loads common textures, sets font)
        # Need to pass a font object if renderer uses it
        try:
            editor_font = pygame.font.SysFont(None, 24) # Example font
            renderer.set_hud_font(editor_font)
        except Exception as e:
            print(f"Warning: Could not initialize font for renderer: {e}")
            renderer.set_hud_font(None)
        # No need to call renderer.init_renderer() fully unless editor needs 3D setup

        self._setup_ui()
        self.minimap_widget.glInitialized.connect(self.on_gl_initialized) # Connect signal
        self._setup_menu()
        self._setup_status_bar()
        self.table_widget.load_scene_file()

        print("Scene Editor Initialized.")
        
    def on_gl_initialized(self):
        """Called after the OpenGL context is ready."""
        print("OpenGL Initialized. Performing initial minimap update.")
        # Now it's safe to parse and update the minimap which might create GL objects
        self.update_minimap_preview()
        # Maybe load common renderer textures here too if needed?
        # renderer.init_renderer() # If renderer init needs GL context

    def _setup_ui(self):
        """Sets up the splitter and widgets."""
        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        self.layout = QHBoxLayout(self.central_widget)

        self.splitter = QSplitter(Qt.Horizontal)
        self.layout.addWidget(self.splitter)

        # Left Panel: Table
        self.table_widget = SceneTableWidget(self) # Pass self as parent for save trigger
        self.splitter.addWidget(self.table_widget)

        # Right Panel: Minimap
        self.minimap_widget = MinimapGLWidget(self)
        self.splitter.addWidget(self.minimap_widget)

        # Set initial size ratio (optional)
        self.splitter.setSizes([int(self.width() * 0.4), int(self.width() * 0.6)])

        # Connect table changes to minimap update
        self.table_widget.sceneDataChanged.connect(self.update_minimap_preview)

    def _setup_menu(self):
        """Sets up the main menu bar."""
        menubar = self.menuBar()
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

        exit_action = QAction('&Exit', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.setStatusTip('Exit application')
        exit_action.triggered.connect(self.close) # Use default close event
        file_menu.addAction(exit_action)

    def _setup_status_bar(self):
         self.statusBar = QStatusBar()
         self.setStatusBar(self.statusBar)
         self.statusBar.showMessage("Ready", 3000)

    def load_initial_scene(self):
        if self.table_widget.load_scene_file():
            self.statusBar.showMessage(f"Loaded '{SCENE_FILE}'", 5000)
            # Don't call update_minimap_preview here, wait for glInitialized signal
        else:
            self.statusBar.showMessage(f"Failed to load '{SCENE_FILE}'", 5000)
            # self.minimap_widget.update_scene(None) # Can clear here if needed


    def save_scene_file(self):
        """Saves the current table content back to the scene file."""
        lines = self.table_widget.get_scene_lines()
        try:
            with open(SCENE_FILE, 'w', encoding='utf-8') as f:
                f.write("\n".join(lines)) # Write lines joined by newline
            self.table_widget.mark_saved() # Reset modified flag
            self.statusBar.showMessage(f"Saved '{SCENE_FILE}'", 3000)
            # print(f"Saved {len(lines)} lines to '{SCENE_FILE}'")
            
            return True
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Could not save file '{SCENE_FILE}':\n{e}")
            self.statusBar.showMessage("Save failed", 5000)
            return False

    def update_minimap_preview(self):
        # This function now assumes GL context is valid when called
        print("Updating minimap preview...")
        lines = self.table_widget.get_scene_lines()
        parsed_scene = scene_parser.parse_scene_from_lines(lines, load_textures=False) # Parses data

        if parsed_scene:
            # *** Create GL objects AFTER parsing and BEFORE passing to minimap ***
            # Now it's safe to create VBOs and load textures via parser
            try:
                # Create Track VBOs
                if parsed_scene.track:
                    parsed_scene.track.create_all_segment_buffers()

                # Ensure textures are loaded (scene_parser now does this, assuming GL context)
                # No extra texture loading step needed here if parser calls load_texture

                # Pass the fully prepared scene to the minimap
                self.minimap_widget.update_scene(parsed_scene)
            except Exception as e:
                 print(f"Error creating GL objects for scene: {e}")
                 self.minimap_widget.update_scene(None) # Clear minimap on error
        else:
            print("Parsing failed, clearing minimap.")
            self.minimap_widget.update_scene(None)
        
    def ask_reload_scene(self):
        """Asks the user if they want to reload, discarding changes."""
        if self.table_widget.is_modified():
            reply = QMessageBox.question(self, 'Reload Scene',
                                         "Discard current changes and reload from disk?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.No:
                return
        # Proceed with reloading
        self.load_initial_scene()


    def closeEvent(self, event):
        """Handles the window close event."""
        if self.table_widget.is_modified():
            reply = QMessageBox.question(self, 'Exit Editor',
                                         "You have unsaved changes. Save before exiting?",
                                         QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                                         QMessageBox.Cancel) # Default to Cancel

            if reply == QMessageBox.Save:
                if not self.save_scene_file():
                    event.ignore() # Prevent closing if save failed
                else:
                    event.accept() # Saved successfully, allow closing
            elif reply == QMessageBox.Discard:
                event.accept() # Discard changes, allow closing
            else: # Cancel
                event.ignore() # Prevent closing
        else:
            event.accept() # No changes, allow closing

# --- Main Application Execution ---
if __name__ == '__main__':
    # Ensure running from script's directory for relative paths
    try:
        os.chdir(os.path.dirname(os.path.abspath(__file__)))
        print(f"工作目錄設定為: {os.getcwd()}")
    except Exception as e:
        print(f"無法更改工作目錄: {e}")

    app = QApplication(sys.argv)
    editor = SceneEditorWindow()
    editor.show()
    sys.exit(app.exec_())