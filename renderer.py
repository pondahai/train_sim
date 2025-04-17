# renderer.py
from OpenGL.GL import *
from OpenGL.GLU import *
import numpy as np
import numpy as math # Keep consistent with other files for now
# import math # Original math import removed for consistency
from track import TRACK_WIDTH, BALLAST_WIDTH, BALLAST_HEIGHT  # Keep track constants if used by draw_track
import texture_loader # Keep for loading general textures
import pygame # Keep for font loading and potentially _draw_text_texture
import os

from numba import jit, njit # Keep numba imports

# --- Drawing Parameters (General) ---
GROUND_SIZE = 200.0
TREE_TRUNK_RADIUS = 0.2
TREE_LEAVES_RADIUS = 1.5
RAIL_COLOR = (0.4, 0.4, 0.5) # Keep
BALLAST_COLOR = (0.6, 0.55, 0.5) # Keep
CAB_COLOR = (0.2, 0.3, 0.7) # Keep
DASHBOARD_COLOR = (0.8, 0.8, 0.85) # Keep
LEVER_COLOR = (0.8, 0.1, 0.1) # Keep
NEEDLE_COLOR = (0.0, 0.0, 0.0) # Keep
CYLINDER_SLICES = 16 # Keep (maybe reduce default slightly?)

# --- Minimap Parameters REMOVED ---
# MINIMAP_SIZE, MINIMAP_PADDING, DEFAULT_MINIMAP_RANGE, etc. REMOVED
# MINIMAP_BG_FALLBACK_COLOR, EDITOR_BG_COLOR REMOVED (now in minimap_renderer)
# MINIMAP_TRACK_COLOR, PLAYER_COLOR, BUILDING_COLOR etc. REMOVED
# MINIMAP_GRID_SCALE, GRID_COLOR, LABEL_COLOR etc. REMOVED

# --- REMOVED Globals for managing the current map texture ---
# current_map_filename_rendered, minimap_bg_texture_id, etc. REMOVED

# --- Global HUD Font ---
hud_display_font = None
# --- Grid Label Font (Still created here, passed to minimap_renderer) ---
grid_label_font = None
coord_label_font = None
# Grid label font size constant (can be moved to minimap_renderer if preferred)
MINIMAP_GRID_LABEL_FONT_SIZE = 24 # Keep here or move? Let's keep for now.
MINIMAP_COORD_LABEL_FONT_SIZE = 16
# --- Coordinate Display Parameters (Keep) ---
COORD_PADDING_X = 10
COORD_PADDING_Y = 10
COORD_TEXT_COLOR = (255, 255, 255, 255)

# --- Texture ID Cache (Keep for general textures) ---
grass_tex = None
tree_bark_tex = None
tree_leaves_tex = None
cab_metal_tex = None

# --- REMOVED: Current minimap range variable ---
# current_minimap_range REMOVED
EDITOR_LABEL_OFFSET_X = 5 # Keep
EDITOR_LABEL_OFFSET_Y = 3 # Keep

# --- REMOVED: zoom_minimap function ---

# --- Keep set_hud_font ---
def set_hud_font(font):
    """
    From main.py receives the Pygame font object for HUD display.
    Also attempts to create the grid label font.
    """
    global hud_display_font, grid_label_font, coord_label_font
    hud_display_font = font

    # Reset grid_label_font
    grid_label_font = None
    coord_label_font = None
    # For grid labels, create a smaller font.
    if hud_display_font: # Check if main font loaded
        # init grid label font
        try:
            # Use the constant defined above
            grid_label_font = pygame.font.SysFont(None, MINIMAP_GRID_LABEL_FONT_SIZE)
            print(f"網格標籤字體已創建 (大小: {MINIMAP_GRID_LABEL_FONT_SIZE}).")
            # *** ADDED: Pass the font to minimap_renderer ***
            try:
                import minimap_renderer
                minimap_renderer.set_grid_label_font(grid_label_font)
            except ImportError:
                print("警告: 無法導入 minimap_renderer 來設置網格字體。")
            except AttributeError:
                 print("警告: minimap_renderer 中未找到 set_grid_label_font。")

        except Exception as e:
            print(f"警告: 無法加載系統默認字體作為網格標籤字體 (大小: {MINIMAP_GRID_LABEL_FONT_SIZE}): {e}")
            grid_label_font = None
        # init coord label font
        try:
            # Use the constant defined above
            coord_label_font = pygame.font.SysFont(None, MINIMAP_COORD_LABEL_FONT_SIZE)
            print(f"網格標籤字體已創建 (大小: {MINIMAP_COORD_LABEL_FONT_SIZE}).")
            # *** ADDED: Pass the font to minimap_renderer ***
            try:
                import minimap_renderer
                minimap_renderer.set_coord_label_font(coord_label_font)
            except ImportError:
                print("警告: 無法導入 minimap_renderer 來設置網格字體。")
            except AttributeError:
                 print("警告: minimap_renderer 中未找到 set_coord_label_font。")

        except Exception as e:
            print(f"警告: 無法加載系統默認字體作為網格標籤字體 (大小: {MINIMAP_COORD_LABEL_FONT_SIZE}): {e}")
            grid_coord_font = None
    else:
        print("警告: 主 HUD 字體未設置，網格標籤字體無法創建。")

# --- REMOVED: Minimap Texture Loading Functions ---
# _load_minimap_texture, clear_cached_map_texture, update_map_texture REMOVED

# --- Keep init_renderer ---
def init_renderer():
    """Initializes the renderer, loads common textures."""
    global grass_tex, tree_bark_tex, tree_leaves_tex, cab_metal_tex
    # Load common non-map textures
    grass_tex = texture_loader.load_texture("grass.png")
    tree_bark_tex = texture_loader.load_texture("tree_bark.png")
    tree_leaves_tex = texture_loader.load_texture("tree_leaves.png")
    cab_metal_tex = texture_loader.load_texture("metal.png") # Assuming cab uses metal texture

    # --- REMOVED: Hardcoded loading of minimap background ---

    # Set OpenGL states (Keep)
    glEnable(GL_DEPTH_TEST)
    glEnable(GL_TEXTURE_2D)
    glEnable(GL_LIGHTING)
    glEnable(GL_LIGHT0)
    glEnable(GL_COLOR_MATERIAL) # Allow glColor to affect material
    glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)

    # Set lighting (Keep)
    glLightfv(GL_LIGHT0, GL_AMBIENT, [0.3, 0.3, 0.3, 1.0])
    glLightfv(GL_LIGHT0, GL_DIFFUSE, [0.8, 0.8, 0.8, 1.0])
    glLightfv(GL_LIGHT0, GL_SPECULAR, [0.5, 0.5, 0.5, 1.0])
    glLightfv(GL_LIGHT0, GL_POSITION, [100.0, 150.0, 100.0, 1.0]) # Position light

    glEnable(GL_NORMALIZE) # Automatically normalize normals

# --- Keep draw_ground ---
def draw_ground(show_ground):
    """繪製地面"""
    if not show_ground:
        return

    if grass_tex:
        glBindTexture(GL_TEXTURE_2D, grass_tex)
        glEnable(GL_TEXTURE_2D) # Ensure texture enabled if tex exists
    else:
        glDisable(GL_TEXTURE_2D) # Disable if no texture

    glColor3f(0.3, 0.7, 0.3) # Grass color (fallback)
    glBegin(GL_QUADS)
    # Calculate texture coordinates for repetition
    tex_repeat = GROUND_SIZE / 10.0 # Repeat texture every 10 units
    glNormal3f(0, 1, 0) # Ground normal points up
    glTexCoord2f(0, 0); glVertex3f(-GROUND_SIZE, 0, -GROUND_SIZE)
    glTexCoord2f(tex_repeat, 0); glVertex3f(GROUND_SIZE, 0, -GROUND_SIZE)
    glTexCoord2f(tex_repeat, tex_repeat); glVertex3f(GROUND_SIZE, 0, GROUND_SIZE)
    glTexCoord2f(0, tex_repeat); glVertex3f(-GROUND_SIZE, 0, GROUND_SIZE)
    glEnd()

    # Restore texture state if it was enabled
    if grass_tex:
        glBindTexture(GL_TEXTURE_2D, 0) # Unbind texture
    # Keep TEXTURE_2D enabled by default after this function? Or restore previous state?
    # Let's keep it enabled as subsequent objects likely use textures.
    glEnable(GL_TEXTURE_2D)


# --- Keep draw_track ---
def draw_track(track_obj):
    """Uses VBO/VAO to draw the track and ballast."""
    if not track_obj or not track_obj.segments:
        return

    glDisable(GL_TEXTURE_2D) # Track and ballast are not textured
    # VAO usage implicitly enables client state, no need for glEnableClientState usually

    # Keep track/ballast colors defined at top
    # half_track_width = TRACK_WIDTH / 2.0 # Not needed here, calculated in segment
    # half_ballast_width = BALLAST_WIDTH / 2.0 # Not needed here

    for segment in track_obj.segments:
        # --- Draw Ballast (using VAO) ---
        if segment.ballast_vao and segment.ballast_vertices:
            glColor3fv(BALLAST_COLOR)
            glBindVertexArray(segment.ballast_vao)
            vertex_count = len(segment.ballast_vertices) // 3
            glDrawArrays(GL_TRIANGLES, 0, vertex_count) # Use GL_TRIANGLES
            # No need to unbind VAO inside loop, just once at end? Or unbind each time?
            # Unbinding each time is safer practice.
            glBindVertexArray(0)

        # --- Draw Rails (using VAO) ---
        glLineWidth(2.0) # Set line width for rails
        glColor3fv(RAIL_COLOR)

        # Left Rail
        if segment.rail_left_vao and segment.rail_left_vertices:
            glBindVertexArray(segment.rail_left_vao)
            vertex_count = len(segment.rail_left_vertices) // 3
            glDrawArrays(GL_LINE_STRIP, 0, vertex_count)
            glBindVertexArray(0)

        # Right Rail
        if segment.rail_right_vao and segment.rail_right_vertices:
            glBindVertexArray(segment.rail_right_vao)
            vertex_count = len(segment.rail_right_vertices) // 3
            glDrawArrays(GL_LINE_STRIP, 0, vertex_count)
            glBindVertexArray(0)

    # Restore default state
    glEnable(GL_TEXTURE_2D) # Re-enable textures for subsequent objects

# --- Keep _calculate_uv helper ---
@njit
def _calculate_uv(u_base, v_base, center_u, center_v, u_offset, v_offset, angle_rad, uv_mode, uscale=1.0, vscale=1.0):
    """Helper function to calculate final UV coordinates for a vertex."""
    # --- KEEPING LOGIC IDENTICAL ---
    # Apply scaling *before* rotation if uv_mode is 0 (Tile)
    if uv_mode == 0:
        # Check for zero scale to prevent division errors
        if uscale == 0: uscale = 1e-6
        if vscale == 0: vscale = 1e-6
        u_scaled = u_base / uscale
        v_scaled = v_base / vscale
        # Use scaled base coords
        u_base = u_scaled
        v_base = v_scaled
        # Adjust center for rotation if scaling is done first? Center remains geometric center.
        center_u_scaled = center_u / uscale
        center_v_scaled = center_v / vscale
        center_u = center_u_scaled # Use scaled center for rotation origin? Makes sense.
        center_v = center_v_scaled

    cos_t = math.cos(angle_rad)
    sin_t = math.sin(angle_rad)

    # Translate to origin (using potentially scaled center if mode is 0)
    u_trans = u_base - center_u
    v_trans = v_base - center_v

    # Rotate
    u_rot = u_trans * cos_t - v_trans * sin_t
    v_rot = u_trans * sin_t + v_trans * cos_t

    # Translate back and apply offset
    final_u = u_rot + center_u + u_offset
    final_v = v_rot + center_v + v_offset

    return final_u, final_v


# --- Keep draw_cube ---
def draw_cube(width, depth, height, texture_id=None,
              u_offset=0.0, v_offset=0.0, tex_angle_deg=0.0, uv_mode=1,
              uscale=1.0, vscale=1.0):
    """
    繪製一個立方體，可選紋理，支援紋理偏移、旋轉和平鋪/拉伸模式。
    基於底部中心 (0,0,0)，頂部在 Y=height。
    uv_mode=1: 拉伸填滿 (0-1 範圍) (忽略 pixels_per_unit)
    uv_mode=0: 單位平鋪 (範圍 0-尺寸) ，使用 uscale, vscale
    """
    # --- KEEPING LOGIC IDENTICAL ---
    if texture_id is not None and glIsTexture(texture_id): # Check if texture ID is valid
        glBindTexture(GL_TEXTURE_2D, texture_id)
        glEnable(GL_TEXTURE_2D)
        # Set texture wrap mode based on uv_mode
        if uv_mode == 0: # Tile mode needs GL_REPEAT
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
        else: # Stretch mode might use GL_CLAMP_TO_EDGE or GL_REPEAT, REPEAT is often fine
             glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT) # Or GL_CLAMP_TO_EDGE
             glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT) # Or GL_CLAMP_TO_EDGE
    else:
        glDisable(GL_TEXTURE_2D)

    w, d, h = width / 2.0, depth / 2.0, height # 中心在底部 (0, 0, 0), 頂部在 Y=h
    angle_rad = math.radians(tex_angle_deg)

    glBegin(GL_QUADS)

    # --- Bottom face (Y=0) ---
    face_w, face_h = width, depth
    current_uscale, current_vscale = uscale, vscale
    if uv_mode == 1: base_coords = [(1, 0), (0, 0), (0, 1), (1, 1)]; center_u, center_v = 0.5, 0.5
    else: base_coords = [(width, 0), (0, 0), (0, depth), (width, depth)]; center_u, center_v = width / 2.0, depth / 2.0
    glNormal3f(0, -1, 0)
    uv = _calculate_uv(*base_coords[0], center_u, center_v, u_offset, v_offset, angle_rad, uv_mode, current_uscale, current_vscale); glTexCoord2f(*uv); glVertex3f( w, 0,  d)
    uv = _calculate_uv(*base_coords[1], center_u, center_v, u_offset, v_offset, angle_rad, uv_mode, current_uscale, current_vscale); glTexCoord2f(*uv); glVertex3f(-w, 0,  d)
    uv = _calculate_uv(*base_coords[2], center_u, center_v, u_offset, v_offset, angle_rad, uv_mode, current_uscale, current_vscale); glTexCoord2f(*uv); glVertex3f(-w, 0, -d)
    uv = _calculate_uv(*base_coords[3], center_u, center_v, u_offset, v_offset, angle_rad, uv_mode, current_uscale, current_vscale); glTexCoord2f(*uv); glVertex3f( w, 0, -d)

    # --- Top face (Y=h) ---
    face_w, face_h = width, depth
    current_uscale, current_vscale = uscale, vscale
    if uv_mode == 1: base_coords = [(1, 1), (0, 1), (0, 0), (1, 0)]; center_u, center_v = 0.5, 0.5
    else: base_coords = [(width, depth), (0, depth), (0, 0), (width, 0)]; center_u, center_v = width / 2.0, depth / 2.0
    glNormal3f(0, 1, 0)
    uv = _calculate_uv(*base_coords[0], center_u, center_v, u_offset, v_offset, angle_rad, uv_mode, current_uscale, current_vscale); glTexCoord2f(*uv); glVertex3f( w, h, -d)
    uv = _calculate_uv(*base_coords[1], center_u, center_v, u_offset, v_offset, angle_rad, uv_mode, current_uscale, current_vscale); glTexCoord2f(*uv); glVertex3f(-w, h, -d)
    uv = _calculate_uv(*base_coords[2], center_u, center_v, u_offset, v_offset, angle_rad, uv_mode, current_uscale, current_vscale); glTexCoord2f(*uv); glVertex3f(-w, h,  d)
    uv = _calculate_uv(*base_coords[3], center_u, center_v, u_offset, v_offset, angle_rad, uv_mode, current_uscale, current_vscale); glTexCoord2f(*uv); glVertex3f( w, h,  d)

    # --- Front face (Z=d) ---
    face_w, face_h = width, height
    current_uscale, current_vscale = uscale, vscale
    if uv_mode == 1: base_coords = [(1, 0), (0, 0), (0, 1), (1, 1)]; center_u, center_v = 0.5, 0.5
    else: base_coords = [(width, 0), (0, 0), (0, height), (width, height)]; center_u, center_v = width / 2.0, height / 2.0
    glNormal3f(0, 0, 1)
    uv = _calculate_uv(*base_coords[0], center_u, center_v, u_offset, v_offset, angle_rad, uv_mode, current_uscale, current_vscale); glTexCoord2f(*uv); glVertex3f( w, 0, d)
    uv = _calculate_uv(*base_coords[1], center_u, center_v, u_offset, v_offset, angle_rad, uv_mode, current_uscale, current_vscale); glTexCoord2f(*uv); glVertex3f(-w, 0, d)
    uv = _calculate_uv(*base_coords[2], center_u, center_v, u_offset, v_offset, angle_rad, uv_mode, current_uscale, current_vscale); glTexCoord2f(*uv); glVertex3f(-w, h, d)
    uv = _calculate_uv(*base_coords[3], center_u, center_v, u_offset, v_offset, angle_rad, uv_mode, current_uscale, current_vscale); glTexCoord2f(*uv); glVertex3f( w, h, d)

    # --- Back face (Z=-d) ---
    face_w, face_h = width, height
    current_uscale, current_vscale = uscale, vscale
    if uv_mode == 1: base_coords = [(0, 1), (1, 1), (1, 0), (0, 0)]; center_u, center_v = 0.5, 0.5
    else: base_coords = [(width, height), (0, height), (0, 0), (width, 0)]; center_u, center_v = width / 2.0, height / 2.0
    glNormal3f(0, 0, -1)
    uv = _calculate_uv(*base_coords[0], center_u, center_v, u_offset, v_offset, angle_rad, uv_mode, current_uscale, current_vscale); glTexCoord2f(*uv); glVertex3f( w, h, -d)
    uv = _calculate_uv(*base_coords[1], center_u, center_v, u_offset, v_offset, angle_rad, uv_mode, current_uscale, current_vscale); glTexCoord2f(*uv); glVertex3f(-w, h, -d)
    uv = _calculate_uv(*base_coords[2], center_u, center_v, u_offset, v_offset, angle_rad, uv_mode, current_uscale, current_vscale); glTexCoord2f(*uv); glVertex3f(-w, 0, -d)
    uv = _calculate_uv(*base_coords[3], center_u, center_v, u_offset, v_offset, angle_rad, uv_mode, current_uscale, current_vscale); glTexCoord2f(*uv); glVertex3f( w, 0, -d)

    # --- Left face (X=-w) ---
    face_w, face_h = depth, height
    current_uscale, current_vscale = uscale, vscale
    if uv_mode == 1: base_coords = [(1, 0), (0, 0), (0, 1), (1, 1)]; center_u, center_v = 0.5, 0.5
    else: base_coords = [(depth, 0), (0, 0), (0, height), (depth, height)]; center_u, center_v = depth / 2.0, height / 2.0
    glNormal3f(-1, 0, 0)
    uv = _calculate_uv(*base_coords[0], center_u, center_v, u_offset, v_offset, angle_rad, uv_mode, current_uscale, current_vscale); glTexCoord2f(*uv); glVertex3f(-w, 0, -d)
    uv = _calculate_uv(*base_coords[1], center_u, center_v, u_offset, v_offset, angle_rad, uv_mode, current_uscale, current_vscale); glTexCoord2f(*uv); glVertex3f(-w, 0,  d)
    uv = _calculate_uv(*base_coords[2], center_u, center_v, u_offset, v_offset, angle_rad, uv_mode, current_uscale, current_vscale); glTexCoord2f(*uv); glVertex3f(-w, h,  d)
    uv = _calculate_uv(*base_coords[3], center_u, center_v, u_offset, v_offset, angle_rad, uv_mode, current_uscale, current_vscale); glTexCoord2f(*uv); glVertex3f(-w, h, -d)

    # --- Right face (X=w) ---
    face_w, face_h = depth, height
    current_uscale, current_vscale = uscale, vscale
    if uv_mode == 1: base_coords = [(0, 0), (1, 0), (1, 1), (0, 1)]; center_u, center_v = 0.5, 0.5
    else: base_coords = [(0, 0), (depth, 0), (depth, height), (0, height)]; center_u, center_v = depth / 2.0, height / 2.0
    glNormal3f(1, 0, 0)
    uv = _calculate_uv(*base_coords[0], center_u, center_v, u_offset, v_offset, angle_rad, uv_mode, current_uscale, current_vscale); glTexCoord2f(*uv); glVertex3f( w, 0,  d)
    uv = _calculate_uv(*base_coords[1], center_u, center_v, u_offset, v_offset, angle_rad, uv_mode, current_uscale, current_vscale); glTexCoord2f(*uv); glVertex3f( w, 0, -d)
    uv = _calculate_uv(*base_coords[2], center_u, center_v, u_offset, v_offset, angle_rad, uv_mode, current_uscale, current_vscale); glTexCoord2f(*uv); glVertex3f( w, h, -d)
    uv = _calculate_uv(*base_coords[3], center_u, center_v, u_offset, v_offset, angle_rad, uv_mode, current_uscale, current_vscale); glTexCoord2f(*uv); glVertex3f( w, h,  d)

    glEnd()

    glBindTexture(GL_TEXTURE_2D, 0) # Unbind
    glEnable(GL_TEXTURE_2D) # Ensure it's enabled afterwards

# --- Keep draw_cylinder ---
def draw_cylinder(radius, height, texture_id=None,
                  u_offset=0.0, v_offset=0.0, tex_angle_deg=0.0, uv_mode=1,
                  uscale=1.0, vscale=1.0):
    """
    繪製圓柱體，可選紋理.
    uv_mode=0: 和 tex_angle_deg 在此基礎實現中可能效果不佳。
    """
    # --- KEEPING LOGIC IDENTICAL (including lack of angle support) ---
    if texture_id is not None and glIsTexture(texture_id):
        glBindTexture(GL_TEXTURE_2D, texture_id)
        glEnable(GL_TEXTURE_2D)
        # Set wrap mode (REPEAT is usually desired for cylinders)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
    else:
        glDisable(GL_TEXTURE_2D)

    quadric = gluNewQuadric()
    if quadric: # Check if quadric creation succeeded
        gluQuadricTexture(quadric, GL_TRUE) # Enable texture coordinates
        gluQuadricNormals(quadric, GLU_SMOOTH) # Smooth normals

        # --- Apply Texture Matrix Transformation (for offset/scale) ---
        glMatrixMode(GL_TEXTURE)
        glPushMatrix() # Save current texture matrix
        glLoadIdentity() # Reset texture matrix
        # 1. Apply Offset (Translate texture lookup)
        glTranslatef(u_offset, v_offset, 0)

        # 2. Apply Rotation (Skipped - complex for GLU cylinder)
        # if tex_angle_deg != 0.0: pass

        # 3. Apply Scaling (if mode is 0 - Tile/Scale)
        if uv_mode == 0:
            safe_uscale = uscale if uscale > 1e-6 else 1e-6
            safe_vscale = vscale if vscale > 1e-6 else 1e-6
            glScalef(1.0 / safe_uscale, 1.0 / safe_vscale, 1.0)

        # --- Switch back to ModelView matrix ---
        glMatrixMode(GL_MODELVIEW)

        # --- Draw Cylinder using GLU ---
        # Body
        gluCylinder(quadric, radius, radius, height, CYLINDER_SLICES, 1)

        # --- Draw Caps (Reset Texture Matrix for Caps) ---
        glMatrixMode(GL_TEXTURE)
        glLoadIdentity() # Reset texture matrix for caps
        glMatrixMode(GL_MODELVIEW)

        # Bottom cap
        glPushMatrix()
        glRotatef(180, 1, 0, 0)
        gluDisk(quadric, 0, radius, CYLINDER_SLICES, 1)
        glPopMatrix()

        # Top cap
        glPushMatrix()
        glTranslatef(0, 0, height) # Z is height axis for GLU cylinder
        gluDisk(quadric, 0, radius, CYLINDER_SLICES, 1)
        glPopMatrix()

        gluDeleteQuadric(quadric)

        # --- Restore Texture Matrix ---
        glMatrixMode(GL_TEXTURE)
        glPopMatrix() # Restore previous texture matrix (before translate/scale)
        glMatrixMode(GL_MODELVIEW)

    else:
        print("Error creating GLU quadric object for cylinder.")

    glBindTexture(GL_TEXTURE_2D, 0) # Unbind
    glEnable(GL_TEXTURE_2D) # Re-enable


# --- Keep draw_tree ---
def draw_tree(x, y, z, height):
    """繪製一棵簡單的樹 (圓柱體+圓錐體)"""
    # --- KEEPING LOGIC IDENTICAL ---
    trunk_height = height * 0.6
    leaves_height = height * 0.4

    glPushMatrix()
    glTranslatef(x, y, z) # Move to tree base position

    # --- Draw Trunk ---
    if tree_bark_tex and glIsTexture(tree_bark_tex):
        glBindTexture(GL_TEXTURE_2D, tree_bark_tex)
        glEnable(GL_TEXTURE_2D)
        glColor3f(1.0, 1.0, 1.0) # Use white color when texturing
    else:
        glDisable(GL_TEXTURE_2D)
        glColor3f(0.5, 0.35, 0.05) # Fallback color

    quadric = gluNewQuadric()
    if quadric:
        gluQuadricTexture(quadric, GL_TRUE)
        gluQuadricNormals(quadric, GLU_SMOOTH)
        glPushMatrix()
        glRotatef(-90, 1, 0, 0) # Rotate cylinder to be Y-up
        gluCylinder(quadric, TREE_TRUNK_RADIUS, TREE_TRUNK_RADIUS * 0.8, trunk_height, CYLINDER_SLICES//2, 1)
        glPopMatrix()
        gluDeleteQuadric(quadric)
    else: print("Error creating quadric for tree trunk.")

    # --- Draw Leaves ---
    if tree_leaves_tex and glIsTexture(tree_leaves_tex):
        glBindTexture(GL_TEXTURE_2D, tree_leaves_tex)
        glEnable(GL_TEXTURE_2D)
        glColor3f(1.0, 1.0, 1.0) # Use white color when texturing
    else:
        glDisable(GL_TEXTURE_2D)
        glColor3f(0.1, 0.5, 0.1) # Fallback color

    glPushMatrix()
    glTranslatef(0, trunk_height, 0) # Move to the base of the leaves

    quadric = gluNewQuadric()
    if quadric:
        gluQuadricTexture(quadric, GL_TRUE)
        gluQuadricNormals(quadric, GLU_SMOOTH)
        glPushMatrix()
        glRotatef(-90, 1, 0, 0) # Rotate cone to be Y-up
        gluCylinder(quadric, TREE_LEAVES_RADIUS, 0, leaves_height * 1.5, CYLINDER_SLICES, 5) # Cone
        glPopMatrix()
        gluDeleteQuadric(quadric)
    else: print("Error creating quadric for tree leaves.")

    glPopMatrix() # Restore from leaves translation
    glPopMatrix() # Restore from tree base translation

    glBindTexture(GL_TEXTURE_2D, 0) # Unbind texture
    glEnable(GL_TEXTURE_2D) # Ensure texture is enabled
    glColor3f(1.0, 1.0, 1.0) # Reset color to white


# --- Keep draw_scene_objects ---
def draw_scene_objects(scene):
    """繪製場景中的所有物件"""
    # --- KEEPING LOGIC IDENTICAL ---
    glColor3f(1.0, 1.0, 1.0) # Default to white, let textures/colors override

    # Draw Buildings using absolute coords from parser
    for obj_data in scene.buildings:
        (obj_type, x, y, z, rx, abs_ry, rz, w, d, h, tex_id,
         u_offset, v_offset, tex_angle_deg, uv_mode,
         uscale, vscale, tex_file) = obj_data # Unpack all, including new tex params
        glPushMatrix()
        glTranslatef(x, y, z)
        glRotatef(abs_ry, 0, 1, 0) # Apply absolute Y rotation
        glRotatef(rx, 1, 0, 0)
        glRotatef(rz, 0, 0, 1)
        # Call draw_cube with all texture parameters
        draw_cube(w, d, h, tex_id, u_offset, v_offset, tex_angle_deg, uv_mode, uscale, vscale)
        glPopMatrix()

    # Draw Cylinders using absolute coords from parser
    for obj_data in scene.cylinders:
        # Unpack all params including texture options
        (obj_type, x, y, z, rx, abs_ry, rz, radius, h, tex_id, # Note order rx, rz, abs_ry
         u_offset, v_offset, tex_angle_deg, uv_mode,
         uscale, vscale, tex_file) = obj_data
        glPushMatrix()
        glTranslatef(x, y, z)
        # Apply rotations (Y first is common)
        glRotatef(abs_ry, 0, 1, 0) # Apply absolute Y rotation
        glRotatef(rx, 1, 0, 0)
        glRotatef(rz, 0, 0, 1)

        # Rotate standard Z-aligned GLU cylinder to be Y-up *before* drawing
        glPushMatrix()
        glRotatef(-90, 1, 0, 0) # Rotate coordinate system so Z becomes Y
        # Call draw_cylinder with all texture parameters
        draw_cylinder(radius, h, tex_id, u_offset, v_offset, tex_angle_deg, uv_mode, uscale, vscale)
        glPopMatrix() # Restore orientation before object rotations

        glPopMatrix() # Restore position

    # Draw Trees
    glColor3f(1.0, 1.0, 1.0) # Reset color for trees
    for tree_data in scene.trees:
        x, y, z, height = tree_data
        draw_tree(x, y, z, height)


# --- Keep draw_tram_cab ---
def draw_tram_cab(tram, camera):
    """繪製駕駛艙和儀表板 (固定在電車上)"""
    # ... (Cab drawing code remains largely the same, ensure correct transforms) ...
    # --- Cab Geometry ---
    cab_width = 3
    cab_height = 1 # Height above floor
    cab_depth = 2
    cab_floor_y = 1.5 # Floor level of the cab relative to tram's position.y

    # --- Dashboard ---
    dash_height = 0.6
    dash_depth = 0.3
    dash_pos_y = 1.5 # 儀表板離地高度
    dash_pos_z = -1 # 儀表板在駕駛艙內的前後位置 (相對於駕駛艙中心)

    # --- Speedo ---
    speedo_radius = 0.15
    speedo_center_x = -cab_width * 0.25
    speedo_center_y = dash_pos_y + dash_height * 0.6
    speedo_center_z = dash_pos_z - dash_depth * 0.5 + 0.51 # 稍微突出

    # --- Lever ---
    lever_base_x = cab_width * 0
    lever_base_y = dash_pos_y + dash_height * 0.2
    lever_base_z = dash_pos_z - dash_depth * 0.4 + 0.5
    lever_length = 0.4
    lever_max_angle = -40.0 # 向前或向後的最大角度

    # ----------------------------------------
    #  核心：應用電車的變換
    # ----------------------------------------
    glPushMatrix()

    # 1. 移動到電車當前位置
    glTranslatef(tram.position[0], tram.position[1], tram.position[2])

    # 2. 旋轉以匹配電車朝向
    #    計算旋轉角度 (從 Z+ 軸開始)
#     angle_y = math.degrees(math.atan2(tram.forward_vector_xz[1], tram.forward_vector_xz[0]))
    #    OpenGL glRotatef 是繞 Y 軸旋轉，但我們的角度是從 X 軸計算的 atan2(y,x)
    #    需要調整，或者直接使用 forward vector 構建矩陣。
    #    簡單方法：atan2 給出的是與 X 軸正方向的夾角。需要轉換為繞 Y 軸的旋轉。
    #    如果 forward = (1,0) -> angle = 0
    #    如果 forward = (0,1) -> angle = 90
    #    如果 forward = (-1,0) -> angle = 180
    #    如果 forward = (0,-1) -> angle = -90 or 270
    #    glRotatef 的 Y 軸旋轉：正角度是逆時針（從上往下看）
    #    我們需要從 Z+ (0,0,1) 旋轉到 (forward_x, 0, forward_z)
    #    角度應該是 atan2(forward_x, forward_z) -> 這是繞 Y 軸的正確角度
    render_angle_y = math.degrees(math.arctan2(tram.forward_vector_xz[0], tram.forward_vector_xz[1]))
    glRotatef(180.0, 0, 1, 0)
    glRotatef(render_angle_y, 0, 1, 0)

    # --- 在電車的局部坐標系中繪製 ---

    # 可選：繪製一個簡單的電車平台 (方便觀察)
    platform_width = cab_width + 0.2
    platform_length = cab_depth + 1.0
    platform_height = 0.2
    glColor3f(0.5, 0.5, 0.5)
    glPushMatrix()
    glTranslatef(0, -platform_height, -platform_length / 2 + cab_depth/2) # 平台中心稍微靠後
#     draw_cube_centered(platform_width, platform_length, platform_height)
    draw_cube(platform_width, platform_length, platform_height)
    
    # 修改為居中放置:
#     glTranslatef(0, -platform_height, 0) # 將平台中心 Z 設為 0 (與駕駛艙中心一致)
#     draw_cube(platform_width, platform_length, platform_height)


    glPopMatrix()


    # 繪製駕駛艙外殼 (一個簡單的盒子)
    glColor3fv(CAB_COLOR)
    if cab_metal_tex:
        glBindTexture(GL_TEXTURE_D, cab_metal_tex)
        glEnable(GL_TEXTURE_2D)
    else:
        glDisable(GL_TEXTURE_2D)

    # 繪製一個沒有頂部和前部的盒子作為基礎駕駛艙
    glBegin(GL_QUADS)
    # Floor
    glNormal3f(0, 1, 0);
    glVertex3f(-cab_width/2, 1, -cab_depth/2)
    glVertex3f( cab_width/2, 1, -cab_depth/2)
    glVertex3f( cab_width/2, 1,  cab_depth/2)
    glVertex3f(-cab_width/2, 1,  cab_depth/2)
    # head wall
    glNormal3f(0, 0, -1);
    glVertex3f(-cab_width/2, 1 + cab_height, -cab_depth/2)
    glVertex3f( cab_width/2, 1 + cab_height, -cab_depth/2)
    glVertex3f( cab_width/2, 1,          -cab_depth/2)
    glVertex3f(-cab_width/2, 1,          -cab_depth/2)
    # Left wall
    glNormal3f(-1, 0, 0);
    glVertex3f(-cab_width/2, 1 + cab_height,  cab_depth/2)
    glVertex3f(-cab_width/2, 1 + cab_height, -cab_depth/2)
    glVertex3f(-cab_width/2, 1,          -cab_depth/2)
    glVertex3f(-cab_width/2, 1,           cab_depth/2)
    # Right wall
    glNormal3f(1, 0, 0);
    glVertex3f( cab_width/2, 1 + cab_height, -cab_depth/2)
    glVertex3f( cab_width/2, 1 + cab_height,  cab_depth/2)
    glVertex3f( cab_width/2, 1,           cab_depth/2)
    glVertex3f( cab_width/2, 1,          -cab_depth/2)
    # back wall
    glNormal3f(0, 0, 1);
    glVertex3f(-cab_width/2, 1 + cab_height + 1, cab_depth/2)
    glVertex3f( cab_width/2, 1 + cab_height + 1, cab_depth/2)
    glVertex3f( cab_width/2, 1,          cab_depth/2)
    glVertex3f(-cab_width/2, 1,          cab_depth/2)
    # top 
    glNormal3f(0, -1, 0);
    glVertex3f(-cab_width/2, 1 + cab_height + 1, -cab_depth/2)
    glVertex3f( cab_width/2, 1 + cab_height + 1, -cab_depth/2)
    glVertex3f( cab_width/2, 1 + cab_height + 1,  cab_depth/2)
    glVertex3f(-cab_width/2, 1 + cab_height + 1,  cab_depth/2)
    # middle front wall
    glNormal3f(0, 0, -1);
    glVertex3f(-cab_width/5, 1 + cab_height + 1, -cab_depth/2)
    glVertex3f( cab_width/5, 1 + cab_height + 1, -cab_depth/2)
    glVertex3f( cab_width/5, 1 + cab_height,          -cab_depth/2)
    glVertex3f(-cab_width/5, 1 + cab_height,          -cab_depth/2)
    # left A-pillar
    glNormal3f(0, 0, -1);
    glVertex3f(-cab_width/2, 1 + cab_height + 1, -cab_depth/2)
    glVertex3f(-cab_width/2 + 0.1, 1 + cab_height + 1, -cab_depth/2)
    glVertex3f(-cab_width/2 + 0.1, 1 + cab_height, -cab_depth/2)
    glVertex3f(-cab_width/2, 1 + cab_height, -cab_depth/2)
    glNormal3f(-1, 0, 0);
    glVertex3f(-cab_width/2, 1 + cab_height + 1,  -cab_depth/2 + 0.5)
    glVertex3f(-cab_width/2, 1 + cab_height + 1, -cab_depth/2)
    glVertex3f(-cab_width/2, 1 + cab_height, -cab_depth/2)
    glVertex3f(-cab_width/2, 1 + cab_height, -cab_depth/2 + 0.5)
    
    # right B-pillar
    glNormal3f(0, 0, -1);
    glVertex3f(cab_width/2, 1 + cab_height + 1, -cab_depth/2)
    glVertex3f(cab_width/2 - 0.1, 1 + cab_height + 1, -cab_depth/2)
    glVertex3f(cab_width/2 - 0.1, 1 + cab_height, -cab_depth/2)
    glVertex3f(cab_width/2, 1 + cab_height, -cab_depth/2)    
    glNormal3f(1, 0, 0);
    glVertex3f( cab_width/2, 1 + cab_height + 1, -cab_depth/2 + 0.5)
    glVertex3f( cab_width/2, 1 + cab_height + 1,  -cab_depth/2)
    glVertex3f( cab_width/2, 1 + cab_height,           -cab_depth/2)
    glVertex3f( cab_width/2, 1 + cab_height,          -cab_depth/2 + 0.5)

    glEnd()

    # 繪製儀表板
    glColor3fv(DASHBOARD_COLOR)
    glDisable(GL_TEXTURE_2D) # 儀表板不用紋理
    glPushMatrix()
    glTranslatef(0, dash_pos_y, dash_pos_z)
    # 稍微傾斜一點方便觀看
    glRotatef(-15, 1, 0, 0)
#     draw_cube_centered(cab_width * 0.95, dash_depth, dash_height) # 畫儀表板方塊
    draw_cube(cab_width * 0.95, dash_depth, dash_height) # 畫儀表板方塊
    
    glPopMatrix() # 恢復儀表板變換

    # --- 繪製儀表和操作桿 (在儀表板表面) ---
    glDisable(GL_LIGHTING) # 儀表和指針通常不受光照影響，顏色固定
    glLineWidth(2.0)

    # 繪製速度表盤
    glColor3f(0.9, 0.9, 0.9) # 表盤背景色
    glPushMatrix()
    # 移動到儀表板表面，考慮傾斜
    glTranslatef(0, dash_pos_y, dash_pos_z)
    glRotatef(-15, 1, 0, 0)
    glTranslatef(speedo_center_x, speedo_center_y - dash_pos_y , speedo_center_z - dash_pos_z ) # 相對儀表板中心

    # 畫圓盤背景
    glBegin(GL_TRIANGLE_FAN)
    glVertex3f(0, 0, 0.01) # 中心點稍微突出
    for i in range(33): # 32 段 + 回到起點
        angle = math.radians(i * 360 / 32)
        glVertex3f(math.cos(angle) * speedo_radius, math.sin(angle) * speedo_radius, 0.01)
    glEnd()

    # 畫刻度
    glColor3f(0.1, 0.1, 0.1) # 刻度顏色
    glBegin(GL_LINES)
    for speed_kmh in range(0, int(tram.max_speed * 3.6) + 1, 10): # 每 10km/h 一個長刻度
        angle_rad = math.radians(90 - (speed_kmh / (tram.max_speed * 3.6)) * 180) # 假設 0 在頂部, 180度範圍
        if tram.max_speed == 0: angle_rad = math.radians(90)
        x1 = math.cos(angle_rad) * speedo_radius * 0.8
        y1 = math.sin(angle_rad) * speedo_radius * 0.8
        x2 = math.cos(angle_rad) * speedo_radius
        y2 = math.sin(angle_rad) * speedo_radius
        glVertex3f(x1, y1, 0.02)
        glVertex3f(x2, y2, 0.02)
    glEnd()

    # 繪製速度指針
    current_kmh = tram.get_speed_kmh()
    speed_ratio = current_kmh / (tram.max_speed * 3.6)
    if tram.max_speed == 0: speed_ratio = 0
    needle_angle_rad = math.radians(90 - speed_ratio * 180) # 90度是0km/h, -90度是最大速度

    glColor3fv(NEEDLE_COLOR)
    glBegin(GL_TRIANGLES)
    # 指針根部
    glVertex3f(0, 0, 0.03)
    # 指針尖端
    needle_x = math.cos(needle_angle_rad) * speedo_radius * 0.9
    needle_y = math.sin(needle_angle_rad) * speedo_radius * 0.9
    glVertex3f(needle_x, needle_y, 0.03)
    # 指針側面的一個點，使其有寬度
    side_angle = needle_angle_rad + math.pi / 2
    glVertex3f(math.cos(side_angle) * 0.01, math.sin(side_angle) * 0.01, 0.03)
    glEnd()

    glPopMatrix() # 恢復速度表變換


    # 繪製操作桿
    glColor3fv(LEVER_COLOR)
    glPushMatrix()
    # 移動到操作桿基座，考慮儀表板傾斜
    glTranslatef(0, dash_pos_y, dash_pos_z)
    glRotatef(-15, 1, 0, 0)
    glTranslatef(lever_base_x, lever_base_y - dash_pos_y, lever_base_z - dash_pos_z)

    # 計算操作桿角度
    control_state = tram.get_control_state() # -1 (煞車/後退), 0 (空檔), 1 (前進)
    lever_angle = control_state * lever_max_angle # 簡單線性映射

    glRotatef(lever_angle, 1, 0, 0) # 繞 X 軸傾斜 (向前/後)

    # 畫操作桿 (一個細長的方塊)
    lever_width = 0.05
    glBegin(GL_QUADS)
    # Front
    glNormal3f(0,0,1); glVertex3f(-lever_width/2, lever_length, lever_width/2); glVertex3f(lever_width/2, lever_length, lever_width/2); glVertex3f(lever_width/2, 0, lever_width/2); glVertex3f(-lever_width/2, 0, lever_width/2)
    # Back
    glNormal3f(0,0,-1); glVertex3f(-lever_width/2, 0, -lever_width/2); glVertex3f(lever_width/2, 0, -lever_width/2); glVertex3f(lever_width/2, lever_length, -lever_width/2); glVertex3f(-lever_width/2, lever_length, -lever_width/2)
    # Top
    glNormal3f(0,1,0); glVertex3f(-lever_width/2, lever_length, -lever_width/2); glVertex3f(lever_width/2, lever_length, -lever_width/2); glVertex3f(lever_width/2, lever_length, lever_width/2); glVertex3f(-lever_width/2, lever_length, lever_width/2)
    # Bottom
    glNormal3f(0,-1,0); glVertex3f(-lever_width/2, 0, lever_width/2); glVertex3f(lever_width/2, 0, lever_width/2); glVertex3f(lever_width/2, 0, -lever_width/2); glVertex3f(-lever_width/2, 0, -lever_width/2)
    # Left
    glNormal3f(-1,0,0); glVertex3f(-lever_width/2, lever_length, lever_width/2); glVertex3f(-lever_width/2, 0, lever_width/2); glVertex3f(-lever_width/2, 0, -lever_width/2); glVertex3f(-lever_width/2, lever_length, -lever_width/2)
    # Right
    glNormal3f(1,0,0); glVertex3f(lever_width/2, lever_length, -lever_width/2); glVertex3f(lever_width/2, 0, -lever_width/2); glVertex3f(lever_width/2, 0, lever_width/2); glVertex3f(lever_width/2, lever_length, lever_width/2)
    glEnd()

    glPopMatrix() # 恢復操作桿變換

    glEnable(GL_LIGHTING) # 恢復光照
    glEnable(GL_TEXTURE_2D) # 恢復紋理
    glPopMatrix() # 恢復電車世界變換

# def draw_tram_cab(tram, camera):
#     """繪製駕駛艙和儀表板 (固定在電車上)"""
#     # --- KEEPING LOGIC IDENTICAL ---
#     # Cab Geometry
# #     cab_floor_y = 1.5 # Floor level - Not explicitly used? Positioning seems relative
#     cab_width = 2.6 # 修改車廂寬度
#     cab_height = 2.2 # 修改車廂高度
#     cab_depth = 2.5 # 修改車廂深度
# 
#     # Dashboard
#     dash_height = 0.6
#     dash_depth = 0.3
#     dash_pos_y = 1.5 # Relative to tram base Y
#     dash_pos_z = -1.0 # Relative to tram local Z origin
# 
#     # Speedo
#     speedo_radius = 0.15
#     speedo_center_x = -cab_width * 0.25 # Relative to tram local X origin
#     speedo_center_y = dash_pos_y + dash_height * 0.6
#     speedo_center_z = dash_pos_z + dash_depth * 0.5 + 0.01 # Slightly proud of dash front
# 
#     # Lever
#     lever_base_x = cab_width * 0.25 # Move lever to the right?
#     lever_base_y = dash_pos_y + dash_height * 0.2
#     lever_base_z = dash_pos_z + dash_depth * 0.5 - 0.05 # Slightly behind dash front
#     lever_length = 0.4
#     lever_max_angle = -40.0 # Forward/backward tilt
# 
#     # Apply Tram Transform
#     glPushMatrix()
#     glTranslatef(tram.position[0], tram.position[1], tram.position[2])
#     # Calculate Y rotation angle from forward vector (atan2 of x, z)
#     render_angle_y = math.degrees(math.arctan2(tram.forward_vector_xz[0], tram.forward_vector_xz[1]))
#     glRotatef(render_angle_y, 0, 1, 0) # Rotate world to match tram's heading
# 
#     # Draw Platform (Optional visual aid)
#     platform_width = cab_width + 0.2
#     platform_length = cab_depth + 1.0
#     platform_height = 0.2
#     glColor3f(0.5, 0.5, 0.5)
#     glPushMatrix()
#     # Position platform base slightly below tram origin Y, centered X/Z
#     glTranslatef(0, -platform_height, 0)
#     # Use draw_cube which draws with origin at bottom center
#     draw_cube(platform_width, platform_length, platform_height)
#     glPopMatrix()
# 
#     # Draw Cab Shell (using immediate mode quads - KEEPING IDENTICAL)
#     glColor3fv(CAB_COLOR)
#     if cab_metal_tex and glIsTexture(cab_metal_tex): # Check texture validity
#         glBindTexture(GL_TEXTURE_2D, cab_metal_tex)
#         glEnable(GL_TEXTURE_2D)
#     else:
#         glDisable(GL_TEXTURE_2D)
# 
#     glBegin(GL_QUADS)
#     # Floor (@Y=0 relative to tram pos)
#     glNormal3f(0, 1, 0); glVertex3f(-cab_width/2, 0, -cab_depth/2); glVertex3f( cab_width/2, 0, -cab_depth/2); glVertex3f( cab_width/2, 0,  cab_depth/2); glVertex3f(-cab_width/2, 0,  cab_depth/2)
#     # Back wall (@Z=cab_depth/2)
#     glNormal3f(0, 0, 1); glVertex3f(-cab_width/2, cab_height, cab_depth/2); glVertex3f( cab_width/2, cab_height, cab_depth/2); glVertex3f( cab_width/2, 0, cab_depth/2); glVertex3f(-cab_width/2, 0, cab_depth/2)
#     # Left wall (@X=-cab_width/2)
#     glNormal3f(-1, 0, 0); glVertex3f(-cab_width/2, cab_height,  cab_depth/2); glVertex3f(-cab_width/2, cab_height, -cab_depth/2); glVertex3f(-cab_width/2, 0, -cab_depth/2); glVertex3f(-cab_width/2, 0,  cab_depth/2)
#     # Right wall (@X=cab_width/2)
#     glNormal3f(1, 0, 0); glVertex3f( cab_width/2, cab_height, -cab_depth/2); glVertex3f( cab_width/2, cab_height,  cab_depth/2); glVertex3f( cab_width/2, 0,  cab_depth/2); glVertex3f( cab_width/2, 0, -cab_depth/2)
#     # Roof (@Y=cab_height)
#     glNormal3f(0, 1, 0); glVertex3f(-cab_width/2, cab_height, -cab_depth/2); glVertex3f( cab_width/2, cab_height, -cab_depth/2); glVertex3f( cab_width/2, cab_height,  cab_depth/2); glVertex3f(-cab_width/2, cab_height,  cab_depth/2)
#     # Front partial wall (below dash?)
#     # glNormal3f(0, 0, -1); glVertex3f(-cab_width/2, dash_pos_y, -cab_depth/2); glVertex3f( cab_width/2, dash_pos_y, -cab_depth/2); glVertex3f( cab_width/2, 0, -cab_depth/2); glVertex3f(-cab_width/2, 0, -cab_depth/2)
#     glEnd()
# 
#     # Draw Dashboard
#     glColor3fv(DASHBOARD_COLOR)
#     glDisable(GL_TEXTURE_2D) # Dashboard not textured
#     glPushMatrix()
#     # Position dashboard relative to tram origin
#     glTranslatef(0, dash_pos_y, dash_pos_z) # Use absolute Y, relative Z
#     glRotatef(-15, 1, 0, 0) # Tilt dashboard back slightly
#     # Draw dashboard cube (origin at bottom center)
#     draw_cube(cab_width * 0.95, dash_depth, dash_height)
#     glPopMatrix()
# 
#     # Draw Gauges and Lever (Disable lighting, use fixed colors)
#     glDisable(GL_LIGHTING)
#     glLineWidth(2.0)
# 
#     # Speedo Dial
#     glColor3f(0.9, 0.9, 0.9) # Dial background
#     glPushMatrix()
#     # Translate to speedo center on the (potentially tilted) dashboard plane
#     # Need to account for the dashboard's transform
#     glTranslatef(0, dash_pos_y, dash_pos_z) # Move to dash origin
#     glRotatef(-15, 1, 0, 0)         # Apply dash tilt
#     glTranslatef(speedo_center_x, speedo_center_y - dash_pos_y, speedo_center_z - dash_pos_z) # Move relative to dash origin
# 
#     # Draw dial background circle
#     glBegin(GL_TRIANGLE_FAN)
#     glVertex3f(0, 0, 0.01) # Center slightly proud
#     num_dial_segments = 32
#     for i in range(num_dial_segments + 1):
#         angle = math.radians(i * 360 / num_dial_segments)
#         glVertex3f(math.cos(angle) * speedo_radius, math.sin(angle) * speedo_radius, 0.01)
#     glEnd()
# 
#     # Draw ticks
#     glColor3f(0.1, 0.1, 0.1)
#     glBegin(GL_LINES)
#     max_speed_kmh = tram.max_speed * 3.6
#     if max_speed_kmh <= 0: max_speed_kmh = 80 # Avoid division by zero if max speed is 0
#     for speed_kmh in range(0, int(max_speed_kmh) + 1, 10):
#         angle_rad = math.radians(90 - (speed_kmh / max_speed_kmh) * 180) # 0 at top, 180 deg range
#         x1 = math.cos(angle_rad) * speedo_radius * 0.8; y1 = math.sin(angle_rad) * speedo_radius * 0.8
#         x2 = math.cos(angle_rad) * speedo_radius; y2 = math.sin(angle_rad) * speedo_radius
#         glVertex3f(x1, y1, 0.02); glVertex3f(x2, y2, 0.02) # Ticks slightly prouder
#     glEnd()
# 
#     # Draw Speedo Needle
#     current_kmh = tram.get_speed_kmh()
#     speed_ratio = current_kmh / max_speed_kmh
#     needle_angle_rad = math.radians(90 - speed_ratio * 180) # Map speed to angle
# 
#     glColor3fv(NEEDLE_COLOR)
#     glBegin(GL_TRIANGLES) # Simple triangle needle
#     glVertex3f(0, 0, 0.03) # Base center (proudest)
#     needle_x = math.cos(needle_angle_rad) * speedo_radius * 0.9
#     needle_y = math.sin(needle_angle_rad) * speedo_radius * 0.9
#     # Give needle slight width
#     side_angle = needle_angle_rad + math.pi / 2
#     side_offset_x = math.cos(side_angle) * 0.01
#     side_offset_y = math.sin(side_angle) * 0.01
#     glVertex3f(needle_x - side_offset_x, needle_y - side_offset_y, 0.03)
#     glVertex3f(needle_x + side_offset_x, needle_y + side_offset_y, 0.03)
#     glEnd()
# 
#     glPopMatrix() # Restore from speedo transform
# 
#     # Draw Control Lever
#     glColor3fv(LEVER_COLOR)
#     glPushMatrix()
#     # Translate to lever base on the dashboard plane
#     glTranslatef(0, dash_pos_y, dash_pos_z) # Move to dash origin
#     glRotatef(-15, 1, 0, 0)         # Apply dash tilt
#     glTranslatef(lever_base_x, lever_base_y - dash_pos_y, lever_base_z - dash_pos_z) # Move relative to dash origin
# 
#     # Rotate lever based on tram control state
#     control_state = tram.get_control_state() # -1 (brake), 0 (neutral), 1 (accel)
#     lever_angle = control_state * lever_max_angle # Map state to tilt angle
# 
#     glRotatef(lever_angle, 1, 0, 0) # Rotate around X axis (forward/backward tilt)
# 
#     # Draw lever as a thin cube (using immediate mode - KEEPING IDENTICAL)
#     lever_width = 0.05
#     glBegin(GL_QUADS)
#     # Front
#     glNormal3f(0,0,1); glVertex3f(-lever_width/2, lever_length, lever_width/2); glVertex3f(lever_width/2, lever_length, lever_width/2); glVertex3f(lever_width/2, 0, lever_width/2); glVertex3f(-lever_width/2, 0, lever_width/2)
#     # Back
#     glNormal3f(0,0,-1); glVertex3f(-lever_width/2, 0, -lever_width/2); glVertex3f(lever_width/2, 0, -lever_width/2); glVertex3f(lever_width/2, lever_length, -lever_width/2); glVertex3f(-lever_width/2, lever_length, -lever_width/2)
#     # Top
#     glNormal3f(0,1,0); glVertex3f(-lever_width/2, lever_length, -lever_width/2); glVertex3f(lever_width/2, lever_length, -lever_width/2); glVertex3f(lever_width/2, lever_length, lever_width/2); glVertex3f(-lever_width/2, lever_length, lever_width/2)
#     # Bottom
#     glNormal3f(0,-1,0); glVertex3f(-lever_width/2, 0, lever_width/2); glVertex3f(lever_width/2, 0, lever_width/2); glVertex3f(lever_width/2, 0, -lever_width/2); glVertex3f(-lever_width/2, 0, -lever_width/2)
#     # Left
#     glNormal3f(-1,0,0); glVertex3f(-lever_width/2, lever_length, lever_width/2); glVertex3f(-lever_width/2, 0, lever_width/2); glVertex3f(-lever_width/2, 0, -lever_width/2); glVertex3f(-lever_width/2, lever_length, -lever_width/2)
#     # Right
#     glNormal3f(1,0,0); glVertex3f(lever_width/2, lever_length, -lever_width/2); glVertex3f(lever_width/2, 0, -lever_width/2); glVertex3f(lever_width/2, 0, lever_width/2); glVertex3f(lever_width/2, lever_length, lever_width/2)
#     glEnd()
# 
#     glPopMatrix() # Restore from lever transform
# 
#     # Restore GL state
#     glEnable(GL_LIGHTING)
#     glEnable(GL_TEXTURE_2D)
#     glPopMatrix() # Restore from tram transform

# --- REMOVED: _world_to_map_coords function ---



# --- Keep _draw_text_texture helper ---
def _draw_text_texture(text_surface, x, y):
    """將 Pygame Surface 繪製為 OpenGL 紋理"""
    # --- KEEPING LOGIC IDENTICAL ---
    if not text_surface: return # Avoid error if surface is None
    text_width, text_height = text_surface.get_size()
    if text_width <= 0 or text_height <= 0: return # Avoid empty texture error

    try:
        texture_data = pygame.image.tostring(text_surface, "RGBA", True)

        tex_id = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, tex_id)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, text_width, text_height, 0,
                     GL_RGBA, GL_UNSIGNED_BYTE, texture_data)

        glEnable(GL_TEXTURE_2D)
        # Assume blend state is set by caller (e.g., HUD drawing)
        # glColor4f(1.0, 1.0, 1.0, 1.0) # Set color in caller
        glBegin(GL_QUADS)
        glTexCoord2f(0, 0); glVertex2f(x, y)
        glTexCoord2f(1, 0); glVertex2f(x + text_width, y)
        glTexCoord2f(1, 1); glVertex2f(x + text_width, y + text_height)
        glTexCoord2f(0, 1); glVertex2f(x, y + text_height)
        glEnd()

        glBindTexture(GL_TEXTURE_2D, 0)
        glDeleteTextures(1, [tex_id]) # Delete texture immediately

    except Exception as e:
        print(f"Error drawing text texture: {e}")
        # Clean up texture ID if generated but failed later
        if 'tex_id' in locals() and tex_id and glIsTexture(tex_id):
             glDeleteTextures(1, [tex_id])


# --- Keep draw_coordinates ---
def draw_coordinates(tram_position, screen_width, screen_height):
    """在 HUD 左上角繪製電車坐標"""
    # --- KEEPING LOGIC IDENTICAL ---
    global hud_display_font
    if not hud_display_font:
        return

    # Format coordinates
    coord_text = f"X: {tram_position[0]:.2f}  Y: {tram_position[1]:.2f}  Z: {tram_position[2]:.2f}"

    try:
        text_surface = hud_display_font.render(coord_text, True, COORD_TEXT_COLOR)
        text_width, text_height = text_surface.get_size()
    except Exception as e:
        print(f"渲染 HUD 文字時出錯: {e}")
        return

    # Switch to 2D ortho projection
    glMatrixMode(GL_PROJECTION); glPushMatrix(); glLoadIdentity()
    gluOrtho2D(0, screen_width, 0, screen_height) # Y=0 is bottom
    glMatrixMode(GL_MODELVIEW); glPushMatrix(); glLoadIdentity()

    # Setup GL state for 2D HUD drawing
    glPushAttrib(GL_ENABLE_BIT | GL_TEXTURE_BIT | GL_COLOR_BUFFER_BIT | GL_CURRENT_BIT) # Save state
    glDisable(GL_DEPTH_TEST)
    glDisable(GL_LIGHTING)
    glEnable(GL_TEXTURE_2D) # Needed for text texture
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glColor4f(1.0, 1.0, 1.0, 1.0) # Use white base color for text texture

    # Calculate draw position (top-left corner)
    draw_x = COORD_PADDING_X
    draw_y = screen_height - COORD_PADDING_Y - text_height # Adjust for Y=0 at bottom

    # Draw the text using the helper
    _draw_text_texture(text_surface, draw_x, draw_y)

    # Restore GL state
    glPopAttrib()

    # Restore matrices
    glMatrixMode(GL_PROJECTION); glPopMatrix()
    glMatrixMode(GL_MODELVIEW); glPopMatrix()

# --- Keep Test Drawing Functions if needed ---
def test_draw_cube_centered(width, depth, height, texture_id=None):
    """繪製一個以原點 (0,0,0) 為中心的立方體"""
    # --- KEEPING LOGIC IDENTICAL ---
    if texture_id is not None and glIsTexture(texture_id):
        glBindTexture(GL_TEXTURE_2D, texture_id)
        glEnable(GL_TEXTURE_2D)
    else:
        glDisable(GL_TEXTURE_2D)

    w2, d2, h2 = width / 2.0, depth / 2.0, height / 2.0 # Half sizes

    glBegin(GL_QUADS)
    # Bottom face (Y=-h2)
    glNormal3f(0, -1, 0); glTexCoord2f(1, 1); glVertex3f( w2, -h2, -d2); glTexCoord2f(0, 1); glVertex3f(-w2, -h2, -d2); glTexCoord2f(0, 0); glVertex3f(-w2, -h2,  d2); glTexCoord2f(1, 0); glVertex3f( w2, -h2,  d2)
    # Top face (Y=h2)
    glNormal3f(0, 1, 0); glTexCoord2f(1, 1); glVertex3f( w2, h2,  d2); glTexCoord2f(0, 1); glVertex3f(-w2, h2,  d2); glTexCoord2f(0, 0); glVertex3f(-w2, h2, -d2); glTexCoord2f(1, 0); glVertex3f( w2, h2, -d2)
    # Front face (Z=d2)
    glNormal3f(0, 0, 1); glTexCoord2f(1, 1); glVertex3f( w2,  h2, d2); glTexCoord2f(0, 1); glVertex3f(-w2,  h2, d2); glTexCoord2f(0, 0); glVertex3f(-w2, -h2, d2); glTexCoord2f(1, 0); glVertex3f( w2, -h2, d2)
    # Back face (Z=-d2)
    glNormal3f(0, 0, -1); glTexCoord2f(1, 1); glVertex3f( w2, -h2, -d2); glTexCoord2f(0, 1); glVertex3f(-w2, -h2, -d2); glTexCoord2f(0, 0); glVertex3f(-w2,  h2, -d2); glTexCoord2f(1, 0); glVertex3f( w2,  h2, -d2)
    # Left face (X=-w2)
    glNormal3f(-1, 0, 0); glTexCoord2f(1, 1); glVertex3f(-w2,  h2,  d2); glTexCoord2f(0, 1); glVertex3f(-w2,  h2, -d2); glTexCoord2f(0, 0); glVertex3f(-w2, -h2, -d2); glTexCoord2f(1, 0); glVertex3f(-w2, -h2,  d2)
    # Right face (X=w2)
    glNormal3f(1, 0, 0); glTexCoord2f(1, 1); glVertex3f( w2,  h2, -d2); glTexCoord2f(0, 1); glVertex3f( w2,  h2,  d2); glTexCoord2f(0, 0); glVertex3f( w2, -h2,  d2); glTexCoord2f(1, 0); glVertex3f( w2, -h2, -d2)
    glEnd()

    glBindTexture(GL_TEXTURE_2D, 0)
    glEnable(GL_TEXTURE_2D) # Restore default enabled state

def test_draw_cylinder_y_up_centered(radius, height, texture_id=None, slices=CYLINDER_SLICES):
    """繪製一個以原點(0,0,0)為中心，沿 Y 軸的圓柱體"""
    # --- KEEPING LOGIC IDENTICAL ---
    if texture_id is not None and glIsTexture(texture_id):
         glBindTexture(GL_TEXTURE_2D, texture_id)
         glEnable(GL_TEXTURE_2D)
    else:
         glDisable(GL_TEXTURE_2D)

    quadric = gluNewQuadric()
    if not quadric: print("Error creating quadric"); return
    gluQuadricTexture(quadric, GL_TRUE)
    gluQuadricNormals(quadric, GLU_SMOOTH)

    half_height = height / 2.0

    glPushMatrix()
    glRotatef(-90, 1, 0, 0) # Rotate Z to Y
    glTranslatef(0, 0, -half_height) # Center along new Z (original Y)

    # Cylinder body
    gluCylinder(quadric, radius, radius, height, slices, 1)
    # Bottom cap (at current Z= -half_height)
    gluDisk(quadric, 0, radius, slices, 1)
    # Top cap (at current Z= +half_height)
    glPushMatrix()
    glTranslatef(0, 0, height)
    gluDisk(quadric, 0, radius, slices, 1)
    glPopMatrix()

    glPopMatrix() # Restore transform

    gluDeleteQuadric(quadric)
    glBindTexture(GL_TEXTURE_2D, 0)
    glEnable(GL_TEXTURE_2D)

# --- REMOVED: _render_map_view function ---

# --- REMOVED: draw_minimap function ---