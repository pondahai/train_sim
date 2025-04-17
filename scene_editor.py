import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QSplitter,
    QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView,
    QVBoxLayout, QSizePolicy, QMenuBar, QAction, QMessageBox, QStatusBar
)
from PyQt5.QtCore import Qt, pyqtSignal, QPoint
from PyQt5.QtOpenGL import QGLWidget # Using QGLWidget
from PyQt5.QtGui import QFont # Keep if needed for alternative text
from OpenGL.GL import *
from OpenGL.GLU import *
import pygame # Still needed for font init and maybe text rendering helper
import numpy as math # Keep consistent

# --- Import Shared Modules ---
import scene_parser
import renderer           # Keep for shared utilities (_draw_text_texture, colors?)
import minimap_renderer # *** NEW: Import minimap module ***
import texture_loader # Keep, needed by scene_parser
from scene_parser import Scene # Import Scene class

# --- Constants (Keep) ---
SCENE_FILE = "scene.txt"
EDITOR_WINDOW_TITLE = "Tram Scene Editor"
INITIAL_WINDOW_WIDTH = 1200
INITIAL_WINDOW_HEIGHT = 600
EDITOR_COORD_COLOR = (205, 205, 20, 200) # Keep
EDITOR_COORD_FONT_SIZE = 24 # Make consistent or use separate constant
EDITOR_LABEL_OFFSET_X = 5 # Keep
EDITOR_LABEL_OFFSET_Y = 3 # Keep


# --- Minimap OpenGL Widget ---
class MinimapGLWidget(QGLWidget):
    """Custom OpenGL Widget for rendering the scene preview."""

    glInitialized = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene_data = None  # Holds the parsed Scene object (used for overlay info)
        # View control state (Keep)
        self._view_center_x = 0.0
        self._view_center_z = 0.0
        self._view_range = minimap_renderer.DEFAULT_MINIMAP_RANGE # Use constant from minimap_renderer
        self._min_range = minimap_renderer.MINIMAP_MIN_RANGE
        self._max_range = minimap_renderer.MINIMAP_MAX_RANGE
        self._zoom_factor = minimap_renderer.MINIMAP_ZOOM_FACTOR

        self._is_dragging = False
        self._last_mouse_pos = QPoint()

        self.setFocusPolicy(Qt.StrongFocus) # For wheel events

        # --- REMOVED: Background Image State ---
        # _show_background_image, _bg_texture_id, etc. removed

        # Font for coordinate display (Keep, relies on renderer._draw_text_texture)
        self._coord_font = None
        try:
            if pygame.font.get_init():
                self._coord_font = pygame.font.SysFont(None, EDITOR_COORD_FONT_SIZE)
                print(f"Minimap created coordinate display font (size: {EDITOR_COORD_FONT_SIZE}).")
        except Exception as e:
            print(f"Minimap Warning: Failed to create coordinate font: {e}")

        # Grid label font is now managed/set via minimap_renderer

    def initializeGL(self):
        """Called once upon OpenGL initialization."""
        # Use the editor's fallback background color for glClear
        # Note: The actual visible background will be the baked texture or its fallback
        r, g, b, a = minimap_renderer.EDITOR_BG_COLOR # Use constant from minimap_renderer
        glClearColor(r, g, b, a)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        # No 3D setup needed here
        self.glInitialized.emit() # Signal GL readiness

    def resizeGL(self, w, h):
        """Called upon widget resize."""
        # Viewport is set dynamically in paintGL
        pass

    def paintGL(self):
        """Called whenever the widget needs to be painted."""
        glClear(GL_COLOR_BUFFER_BIT) # Clear with fallback color
        w = self.width()
        h = self.height()
        if w == 0 or h == 0: return

        # --- Setup 2D Ortho Projection (Keep) ---
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glOrtho(0.0, float(w), 0.0, float(h), -1.0, 1.0) # Y increases upwards
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        glViewport(0, 0, w, h)

        # --- Disable 3D states (Keep) ---
        glPushAttrib(GL_ENABLE_BIT | GL_CURRENT_BIT | GL_LINE_BIT | GL_POINT_BIT) # Save state
        glDisable(GL_DEPTH_TEST)
        glDisable(GL_LIGHTING)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        # --- Draw Minimap Content using minimap_renderer ---
        try:
            # Call the dedicated editor preview function
            minimap_renderer.draw_editor_preview(
                self._scene_data, # Pass scene data (needed for track overlay)
                self._view_center_x,
                self._view_center_z,
                self._view_range,
                w, h
            )
        except Exception as e:
            print(f"Error calling draw_editor_preview: {e}")
            # Optionally draw an error message overlay

        # --- Draw Editor Specific Overlays (Crosshair, Center Coords) ---
        # --- Draw Center Marker (Keep) ---
        glColor3f(1.0, 0.0, 0.0) # Red crosshair
        glLineWidth(1.0)
        widget_cx = w / 2.0
        widget_cy = h / 2.0
        cross_size = 30
        glBegin(GL_LINES)
        glVertex2f(widget_cx - cross_size, widget_cy); glVertex2f(widget_cx + cross_size, widget_cy)
        glVertex2f(widget_cx, widget_cy - cross_size); glVertex2f(widget_cx, widget_cy + cross_size)
        glEnd()

        # --- Draw Center Coordinate Label (Keep) ---
        if self._coord_font:
            coord_text = f"Center: ({self._view_center_x:.1f}, {self._view_center_z:.1f}) Range: {self._view_range:.1f}"
            try:
                # Use color constant from this file
                text_surface = self._coord_font.render(coord_text, True, EDITOR_COORD_COLOR)
                text_width = text_surface.get_width()
                text_height = text_surface.get_height()
                # Position at top-right corner
                draw_x = w - text_width - EDITOR_LABEL_OFFSET_X
                draw_y = h - text_height - EDITOR_LABEL_OFFSET_Y # Offset from top
                # Use the text drawing utility from renderer
                renderer._draw_text_texture(text_surface, draw_x, draw_y)
            except Exception as e:
                print(f"渲染中心座標時出錯: {e}")

        glPopAttrib() # Restore state

    # --- REMOVED: keyPressEvent (handling 'M' key) ---

    # --- REMOVED: _update_background_texture method ---

    def update_scene(self, scene_object):
        """
        Slot to receive updated scene data (parsed, but not yet baked).
        Stores the reference and triggers a repaint. Baking happens externally.
        """
        # Only store the scene data reference. The draw function will use it
        # to potentially draw overlays like the track.
        if isinstance(scene_object, Scene):
            self._scene_data = scene_object
            self.update() # Trigger repaint
        elif scene_object is None:
            self._scene_data = None
            self.update() # Trigger repaint with empty scene reference
            print("Editor Minimap scene data cleared.")
        else:
            print("Editor Minimap received invalid scene data type.")

    # --- Keep Interaction Methods (mousePress, mouseMove, mouseRelease, wheelEvent) ---
    # These methods control the view parameters (_view_center_x/z, _view_range)
    # which are used by draw_editor_preview. Their logic remains the same.
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
                # Convert screen delta to world delta (Keep logic)
                scale = min(w, h) / self._view_range
                world_dx = delta.x() / scale # Screen X maps to World X (but flipped in coords func?) -> Check consistency
                world_dz = -delta.y() / scale # Screen Y (down) maps to World Z (up) -> Needs negative?

                # Adjust view center based on drag (Keep logic)
                # If _world_to_map_coords flips X, dragging needs inverse? Let's test original first.
                # Original logic assumed non-flipped X:
                # world_dx = -delta.x() / scale
                # world_dz = delta.y() / scale # QPoint Y is down, map Y is Z up
                # Let's try keeping the original logic, as the flip happens in coordinate conversion
                world_dx = delta.x() / scale
                world_dz = delta.y() / scale # Flip Y delta

                self._view_center_x += world_dx
                self._view_center_z += world_dz

                self._last_mouse_pos = event.pos()
                self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._is_dragging:
            self._is_dragging = False
            self.setCursor(Qt.ArrowCursor)

    def wheelEvent(self, event):
        """Handles mouse wheel scrolling for zooming."""
        delta = event.angleDelta().y()
        if delta > 0: factor = 1.0 / self._zoom_factor # Zoom in
        elif delta < 0: factor = self._zoom_factor    # Zoom out
        else: return

        new_range = self._view_range * factor
        self._view_range = max(self._min_range, min(self._max_range, new_range))
        self.update()

# --- SceneTableWidget (No changes needed) ---
class SceneTableWidget(QTableWidget):
    """Custom Table Widget for editing scene file content."""
    # --- KEEPING ALL LOGIC IDENTICAL ---
    sceneDataChanged = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data_modified = False
        self._filepath = SCENE_FILE
        self._command_hints = scene_parser.COMMAND_HINTS

        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.verticalHeader().setVisible(True)

        self.currentCellChanged.connect(self._on_current_cell_changed)
        self.itemChanged.connect(self._on_item_changed)
        # Connect itemChanged slightly differently to trigger save maybe?
        # self.itemChanged.connect(self._handle_item_change_and_maybe_save)

    # def _handle_item_change_and_maybe_save(self, item):
    #     self._on_item_changed(item)
    #     # Trigger auto-save? Debatable. Let's keep explicit save for now.
    #     # if self.parent() and hasattr(self.parent(), 'save_scene_file'):
    #     #     self.parent().save_scene_file() # Trigger save on edit


    def load_scene_file(self):
        """Loads content from the scene file into the table."""
        self.clear()
        self.setRowCount(0)
        self.setColumnCount(0)

        if not os.path.exists(self._filepath):
            print(f"Scene file '{self._filepath}' not found. Creating empty table.")
            self.insertRow(0)
            self.setColumnCount(1)
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

            max_cols = 0
            for line in lines:
                parts = line.strip().split()
                max_cols = max(max_cols, len(parts))
            max_cols = max(1, max_cols)
            self.setColumnCount(max_cols)
            self.setHorizontalHeaderLabels([f"P{i}" for i in range(max_cols)])

            self.setRowCount(len(lines))
            self.blockSignals(True) # Block during population
            try:
                for row, line in enumerate(lines):
                    self.setVerticalHeaderItem(row, QTableWidgetItem(str(row + 1)))
                    parts = line.strip().split()
                    for col, part in enumerate(parts):
                        item = QTableWidgetItem(part)
                        self.setItem(row, col, item)
                    for col in range(len(parts), max_cols):
                         self.setItem(row, col, QTableWidgetItem(""))
            finally:
                self.blockSignals(False) # Unblock

            self._data_modified = False
            self.resizeColumnsToContents()
            print(f"Loaded '{self._filepath}' into table.")
            self.sceneDataChanged.emit() # Emit AFTER loading
            return True

        except Exception as e:
            print(f"Error loading scene file '{self._filepath}': {e}")
            self.clear(); self.setRowCount(0); self.setColumnCount(0)
            return False

    def get_scene_lines(self):
        """Gets the current content of the table as a list of strings."""
        lines = []
        for row in range(self.rowCount()):
            row_parts = []
            for col in range(self.columnCount()):
                item = self.item(row, col)
                if item and item.text():
                    row_parts.append(item.text())
                elif item is None or not item.text():
                     break
            lines.append(" ".join(row_parts))
        return lines

    def is_modified(self):
        return self._data_modified

    def mark_saved(self):
        self._data_modified = False

    def is_row_empty(self, row_index):
        """Checks if all cells in the given row are empty or contain only whitespace."""
        if row_index < 0 or row_index >= self.rowCount(): return False
        for col in range(self.columnCount()):
            item = self.item(row_index, col)
            if item is not None and item.text().strip(): return False
        return True

    def keyPressEvent(self, event):
        """Handles Enter for inserting rows and Delete for removing empty rows."""
        key = event.key()
        if key in (Qt.Key_Return, Qt.Key_Enter):
            current_row = self.currentRow()
            if current_row >= 0:
                self.insertRow(current_row + 1)
                self.setVerticalHeaderItem(current_row + 1, QTableWidgetItem(str(current_row + 2)))
                for r in range(current_row + 2, self.rowCount()):
                     self.setVerticalHeaderItem(r, QTableWidgetItem(str(r + 1)))
                self.setCurrentCell(current_row + 1, 0)
                self._data_modified = True
                self.sceneDataChanged.emit() # Notify change
                event.accept()
                return
        elif key == Qt.Key_Delete:
            selected_ranges = self.selectedRanges()
            if len(selected_ranges) == 1:
                selection_range = selected_ranges[0]
                if selection_range.leftColumn() == 0 and \
                   selection_range.rightColumn() == self.columnCount() - 1 and \
                   selection_range.rowCount() == 1:
                    row_to_delete = selection_range.topRow()
                    if self.is_row_empty(row_to_delete):
                        # No confirmation for empty row deletion
                        self.removeRow(row_to_delete)
                        for r in range(row_to_delete, self.rowCount()):
                            self.setVerticalHeaderItem(r, QTableWidgetItem(str(r + 1)))
                        self._data_modified = True
                        self.sceneDataChanged.emit()
                        print(f"Deleted empty row {row_to_delete + 1}")
                        event.accept()
                        return # Consume event
        super().keyPressEvent(event) # Default handling for other keys

    def _on_current_cell_changed(self, currentRow, currentColumn, previousRow, previousColumn):
        """Updates column headers with hints."""
        if currentRow < 0 or currentRow >= self.rowCount():
             for c in range(self.columnCount()): self.setHorizontalHeaderItem(c, QTableWidgetItem(f"P{c}"))
             return
        command_item = self.item(currentRow, 0)
        command = command_item.text().lower().strip() if command_item else ""
        hints = self._command_hints.get(command, [])
        max_cols = self.columnCount()
        current_headers = []
        for i, hint in enumerate(hints):
            if i < max_cols: current_headers.append(hint)
        for i in range(len(hints), max_cols): current_headers.append(f"P{i}")
        self.setHorizontalHeaderLabels(current_headers)

    def _on_item_changed(self, item):
        """Flags data as modified when a cell changes."""
        self._data_modified = True
        # Emit signal immediately on item change? Can be noisy.
        # Emitting ensures preview updates live.
        self.sceneDataChanged.emit()

# --- Main Editor Window ---
class SceneEditorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(EDITOR_WINDOW_TITLE)
        self.setGeometry(100, 100, INITIAL_WINDOW_WIDTH, INITIAL_WINDOW_HEIGHT)

        # --- Pygame/Loader Init (Keep) ---
        # Need pygame for font/image used by helpers potentially
        pygame.init()
        pygame.font.init()
        try: # Minimal display init for pygame helpers
            pygame.display.set_mode((64, 64), pygame.RESIZABLE)
            pygame.display.set_caption("Pygame Helper (Editor)")
        except pygame.error as e: print(f"Warning: Could not set Pygame display mode in editor init: {e}")
        scene_parser.set_texture_loader(texture_loader)

        # --- Font setup for Renderer/Minimap ---
        # Create editor font and pass to relevant modules
        try:
            editor_hud_font = pygame.font.SysFont(None, 24) # Main HUD font size
            renderer.set_hud_font(editor_hud_font) # Pass to renderer (for coord display in editor)
            # Pass the generated grid font to minimap_renderer
            if renderer.grid_label_font:
                minimap_renderer.set_grid_label_font(renderer.grid_label_font)
            else:
                print("Editor Warning: Grid label font not created by renderer.")
        except Exception as e:
            print(f"Editor Warning: Could not initialize/set fonts: {e}")
            renderer.set_hud_font(None) # Ensure renderer knows font failed
            minimap_renderer.set_grid_label_font(None) # Ensure minimap knows

        # --- UI Setup (Keep) ---
        self._setup_ui()
        self.minimap_widget.glInitialized.connect(self.on_gl_initialized)
        self._setup_menu()
        self._setup_status_bar()
        # Don't load file here, wait for glInitialized

        print("Scene Editor Initialized.")

    def on_gl_initialized(self):
        """Called after the OpenGL context is ready."""
        print("OpenGL Initialized. Loading initial scene and baking minimap.")
        # Now it's safe to load scene, create buffers, and bake
        self.load_initial_scene() # This now includes baking

    def _setup_ui(self):
        """Sets up the splitter and widgets."""
        # --- KEEPING UI SETUP IDENTICAL ---
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
        # Connect table changes to the main update function
        self.table_widget.sceneDataChanged.connect(self.update_minimap_preview)

    def _setup_menu(self):
        """Sets up the main menu bar."""
        # --- KEEPING MENU SETUP IDENTICAL ---
        menubar = self.menuBar()
        file_menu = menubar.addMenu('&File')
        save_action = QAction('&Save', self); save_action.setShortcut('Ctrl+S'); save_action.setStatusTip('Save scene file'); save_action.triggered.connect(self.save_scene_file); file_menu.addAction(save_action)
        reload_action = QAction('&Reload', self); reload_action.setShortcut('Ctrl+R'); reload_action.setStatusTip('Reload scene file from disk'); reload_action.triggered.connect(self.ask_reload_scene); file_menu.addAction(reload_action)
        exit_action = QAction('&Exit', self); exit_action.setShortcut('Ctrl+Q'); exit_action.setStatusTip('Exit application'); exit_action.triggered.connect(self.close); file_menu.addAction(exit_action)

    def _setup_status_bar(self):
         # --- KEEPING STATUS BAR SETUP IDENTICAL ---
         self.statusBar = QStatusBar()
         self.setStatusBar(self.statusBar)
         self.statusBar.showMessage("Ready", 3000)

    def load_initial_scene(self):
        """Loads the scene file and triggers buffer creation and minimap baking."""
        print("Loading initial scene for editor...")
        if self.table_widget.load_scene_file(): # Loads text into table
            self.statusBar.showMessage(f"Loaded '{SCENE_FILE}'", 5000)
            # Now trigger parse, buffer creation, bake, and widget update
            self.update_minimap_preview()
        else:
            self.statusBar.showMessage(f"Failed to load '{SCENE_FILE}'", 5000)
            self.update_minimap_preview() # Update with empty data


    def save_scene_file(self):
        """Saves the current table content back to the scene file."""
        # --- KEEPING SAVE LOGIC IDENTICAL ---
        lines = self.table_widget.get_scene_lines()
        try:
            # Add newline at the end if last line isn't empty? Optional.
            content_to_write = "\n".join(lines)
            if content_to_write and not content_to_write.endswith('\n'):
                content_to_write += '\n' # Ensure trailing newline

            with open(SCENE_FILE, 'w', encoding='utf-8') as f:
                f.write(content_to_write)
            self.table_widget.mark_saved()
            self.statusBar.showMessage(f"Saved '{SCENE_FILE}'", 3000)
            return True
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Could not save file '{SCENE_FILE}':\n{e}")
            self.statusBar.showMessage("Save failed", 5000)
            return False

    def update_minimap_preview(self):
        """Parses table data, creates buffers, bakes minimap, updates widget."""
        print("Updating editor preview (Parse -> Buffers -> Bake -> Update Widget)...")
        lines = self.table_widget.get_scene_lines()

        # --- 1. Parse Scene Data (No texture loading needed for bake logic) ---
        # Pass load_textures=False as bake uses absolute coords, not object textures.
        # However, parser might still load common textures via texture_loader if called.
        # Let's parse *without* loading object textures specifically for the bake trigger.
        # If the 3D view needed update, we'd parse with load_textures=True.
        parsed_scene = scene_parser.parse_scene_from_lines(lines, load_textures=False)

        if parsed_scene:
            # --- 2. Create Track Buffers (If needed for overlay) ---
            # The minimap overlay draws track lines, which might need buffer data
            # if we optimize track drawing later. For now, it uses points directly.
            # Let's create buffers anyway for consistency.
            try:
                if parsed_scene.track:
                    print("  Creating track buffers...")
                    parsed_scene.track.create_all_segment_buffers()
            except Exception as e:
                print(f"  Error creating track buffers: {e}")
                # Continue even if buffer creation fails? Preview might lack track.

            # --- 3. Bake Minimap ---
            try:
                print("  Baking minimap...")
                minimap_renderer.bake_static_map_elements(parsed_scene)
            except Exception as e:
                print(f"  Error baking minimap elements: {e}")
                # Should probably clear the baked texture state
                minimap_renderer.cleanup_minimap_renderer() # Ensure clean state

            # --- 4. Update Minimap Widget ---
            # Pass the parsed scene data (needed for track overlay info)
            print("  Updating minimap widget...")
            self.minimap_widget.update_scene(parsed_scene)

        else:
            # Parsing failed
            print("  Parsing failed, clearing minimap preview.")
            minimap_renderer.cleanup_minimap_renderer() # Clear baked texture
            self.minimap_widget.update_scene(None) # Clear widget data

    def ask_reload_scene(self):
        """Asks the user if they want to reload, discarding changes."""
        # --- KEEPING RELOAD LOGIC IDENTICAL ---
        if self.table_widget.is_modified():
            reply = QMessageBox.question(self, 'Reload Scene',
                                         "Discard current changes and reload from disk?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.No: return
        # Proceed with reloading (which includes parsing, baking, update)
        self.load_initial_scene()


    def closeEvent(self, event):
        """Handles the window close event."""
        # --- KEEPING CLOSE LOGIC IDENTICAL ---
        if self.table_widget.is_modified():
            reply = QMessageBox.question(self, 'Exit Editor',
                                         "You have unsaved changes. Save before exiting?",
                                         QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                                         QMessageBox.Cancel)
            if reply == QMessageBox.Save:
                if not self.save_scene_file(): event.ignore(); return
            elif reply == QMessageBox.Discard: pass
            else: event.ignore(); return

        # --- Add Cleanup ---
        print("Cleaning up editor resources...")
        minimap_renderer.cleanup_minimap_renderer()
        # Clean up track buffers of the last scene?
        last_scene = scene_parser.get_current_scene() # Get whatever was last parsed
        if last_scene and last_scene.track:
            last_scene.track.clear()
        # Quit pygame?
        pygame.quit()
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