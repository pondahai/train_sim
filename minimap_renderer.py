# minimap_renderer.py
import pygame
from OpenGL.GL import *
from OpenGL.GLU import *
import numpy as np
import numpy as math # Keep consistent
import os
# --- 新增：導入 Pillow ---
from PIL import Image
# ------------------------

# --- Import shared modules/constants ---
from scene_parser import Scene
from tram import Tram
import renderer # Needed for colors, sizes, grid constants, _draw_text_texture, 
# Import texture loader directly for editor preview background loading
import texture_loader
from track import TRACK_WIDTH

from numba import jit, njit # Keep numba imports

# --- Minimap Constants ---
# Constants for Simulator
MINIMAP_SIZE = 500
MINIMAP_PADDING = 10
DEFAULT_MINIMAP_RANGE = 200.0
MINIMAP_MIN_RANGE = 10.0
MINIMAP_MAX_RANGE = 5000.0
MINIMAP_ZOOM_FACTOR = 1.1
MINIMAP_PLAYER_COLOR = (1.0, 0.0, 0.0)
MINIMAP_PLAYER_SIZE = 12
# Constants for Editor Preview (mostly shared, some might differ)
EDITOR_BG_COLOR = (0.15, 0.15, 0.18, 1.0) # Editor preview BG fallback if no map texture
# Constants used by BOTH (Simulator Overlay & Editor Dynamic Draw)
MINIMAP_TRACK_COLOR = (1.0, 0.0, 0.0) # White track
MINIMAP_GRID_SCALE = 50.0
MINIMAP_GRID_LABEL_COLOR = (255, 255, 0, 180)
# MINIMAP_GRID_LABEL_FONT_SIZE = 24
MINIMAP_GRID_LABEL_OFFSET = 2
#
# MINIMAP_COORD_LABEL_FONT_SZIE = 12
# Constants for Dynamic Drawing (Editor Preview - matching original renderer)
MINIMAP_DYNAMIC_GRID_COLOR = (0.5, 0.5, 0.5, 0.3) # Color for editor grid lines
MINIMAP_DYNAMIC_BUILDING_COLOR = (0.6, 0.4, 0.9) # Editor building lines
MINIMAP_DYNAMIC_BUILDING_LABEL_COLOR = tuple(c * 255 for c in MINIMAP_DYNAMIC_BUILDING_COLOR) + (180,)
MINIMAP_DYNAMIC_CYLINDER_COLOR = (0.5, 0.9, 0.5) # Editor cylinder lines/circles
MINIMAP_DYNAMIC_CYLINDER_LABEL_COLOR = tuple(c * 255 for c in MINIMAP_DYNAMIC_CYLINDER_COLOR) + (180,)
MINIMAP_DYNAMIC_TREE_COLOR = (0.1, 0.8, 0.1) # Editor tree points

MINIMAP_DYNAMIC_SPHERE_COLOR = (0.9, 0.7, 0.2) # 範例顏色：橙色
MINIMAP_BAKE_SPHERE_COLOR = (*MINIMAP_DYNAMIC_SPHERE_COLOR[:3], 0.5) # 用於烘焙的半透明顏色
MINIMAP_DYNAMIC_SPHERE_LABEL_COLOR = tuple(c * 255 for c in MINIMAP_DYNAMIC_SPHERE_COLOR) + (180,) # 標籤顏色

# Constants for FBO Baking
MINIMAP_BG_FALLBACK_COLOR = (0.2, 0.2, 0.2, 0.7) # Simulator fallback BG
MINIMAP_BAKE_GRID_COLOR = MINIMAP_DYNAMIC_GRID_COLOR # Use same color for baked grid
MINIMAP_BAKE_BUILDING_COLOR = (*MINIMAP_DYNAMIC_BUILDING_COLOR[:3], 0.5) # Use alpha for bake
MINIMAP_BAKE_CYLINDER_COLOR = (*MINIMAP_DYNAMIC_CYLINDER_COLOR[:3], 0.5)
MINIMAP_BAKE_TREE_COLOR = (*MINIMAP_DYNAMIC_TREE_COLOR[:3], 0.5)
# MINIMAP_BAKE_BUILDING_COLOR = tuple(int(c * 255) for c in MINIMAP_DYNAMIC_BUILDING_COLOR) + (180,)#(MINIMAP_DYNAMIC_BUILDING_COLOR, 0.8) # Use alpha for bake
# MINIMAP_BAKE_CYLINDER_COLOR = tuple(int(c * 255) for c in MINIMAP_DYNAMIC_CYLINDER_COLOR) + (180,)#(MINIMAP_DYNAMIC_CYLINDER_COLOR, 0.8)


# --- State Variables ---
# Baked Texture Info (Simulator)
composite_fbo = None
composite_map_texture_id = None
composite_texture_width_px = 0
composite_texture_height_px = 0
composite_map_world_cx = 0.0
composite_map_world_cz = 0.0
composite_map_world_width = 0.0
composite_map_world_height = 0.0
composite_map_world_scale = 1.0

# Original Background Texture Info (loaded temporarily during bake)
original_bg_texture_id_bake = None # Rename to avoid conflict
original_bg_width_px_bake = 0
original_bg_height_px_bake = 0

# --- NEW: State for Editor Dynamic Background Texture ---
editor_bg_texture_id = None
editor_bg_width_px = 0
editor_bg_height_px = 0
editor_current_map_filename = None # Track the filename loaded for editor

# Simulator Zoom State
current_simulator_minimap_range = DEFAULT_MINIMAP_RANGE

# Fonts
grid_label_font = None
coord_label_font = None

# --- Helper Functions ---

def set_grid_label_font(font):
    global grid_label_font
    grid_label_font = font

def set_coord_label_font(font):
    global coord_label_font
    coord_label_font = font

# --- Coordinate Conversion (Keep identical, used by both draw modes) ---
@njit # Re-enable if performance requires and testing passes
def _world_to_map_coords_adapted(world_x, world_z, view_center_x, view_center_z, map_widget_center_x, map_widget_center_y, scale):
    """
    Internal helper: Converts world XZ to map widget coordinates.
    Assumes map X+ = world X+, map Y+ = world Z+.
    Applies X-axis flip. KEEPING LOGIC IDENTICAL.
    """
    delta_x = world_x - view_center_x
    delta_z = world_z - view_center_z
    # 軌道左右顛倒 因此修改成減號 (KEEP THIS COMMENT AND LOGIC)
    map_x = map_widget_center_x - delta_x * scale
    map_y = map_widget_center_y + delta_z * scale
    return map_x, map_y

# --- Keep FBO Coord Conversion (Used only by bake) ---
# Using your tested version
@njit # Consider adding back if confirmed stable
def _world_to_fbo_coords(world_x, world_z, fbo_world_cx, fbo_world_cz, fbo_world_width, fbo_world_height, fbo_tex_width_px, fbo_tex_height_px):
    """Converts world XZ coords to FBO pixel coords (YOUR TESTED VERSION)."""
    if fbo_world_width <= 1e-6 or fbo_world_height <= 1e-6: return 0, 0
    world_min_x = fbo_world_cx - fbo_world_width / 2.0
    world_min_z = fbo_world_cz - fbo_world_height / 2.0
    delta_x = world_x - world_min_x
    delta_z = world_z - world_min_z
    # Implicit scale=1, specific inversions
    fbo_px_x = fbo_tex_width_px - delta_x * 1
    fbo_px_y = fbo_tex_height_px - delta_z * 1
    # Return with Y flipped again
    return float(fbo_px_x), float(fbo_tex_height_px - fbo_px_y) # Ensure float

def bake_static_map_elements(scene: Scene):
    """ Renders static elements to composite_map_texture for SIMULATOR use.
        Creates a 1:1 pixel-to-world-unit texture. The scene.map_world_scale
        is ONLY used to scale the original background image to fit this target texture.
    """
    global composite_fbo, composite_map_texture_id, composite_texture_width_px, composite_texture_height_px
    global composite_map_world_cx, composite_map_world_cz, composite_map_world_width, composite_map_world_height, composite_map_world_scale
    global original_bg_texture_id_bake, original_bg_width_px_bake, original_bg_height_px_bake

    print("開始烘焙靜態小地圖元素 (供模擬器使用, 強制 1:1 比例)...")
    # --- Cleanup previous bake ---
    _cleanup_bake_resources()

    if not scene or not scene.map_filename: print("警告: 無法烘焙，場景或地圖檔未定義。"); return
    # Check scene scale validity, as it's used for initial background scaling
    if scene.map_world_scale <= 1e-6: print(f"警告: 場景中的地圖縮放比例無效 ({scene.map_world_scale})，無法用於校準背景。"); return

    # --- 1. Load Original Background Texture (for bake) ---
    filepath = os.path.join("textures", scene.map_filename)
    if not os.path.exists(filepath): print(f"錯誤: 找不到背景圖 '{filepath}'，無法烘焙。"); return
    else:
        try:
            # Using Pillow for broader format support might be better here, but stick to Pygame for now
            surface = pygame.image.load(filepath).convert_alpha()
            texture_data = pygame.image.tostring(surface, "RGBA", True)
            original_bg_width_px_bake = surface.get_width()
            original_bg_height_px_bake = surface.get_height()
            if original_bg_width_px_bake <= 0 or original_bg_height_px_bake <= 0: print(f"錯誤: 背景圖 '{filepath}' 尺寸無效。"); return

            original_bg_texture_id_bake = glGenTextures(1)
            glBindTexture(GL_TEXTURE_2D, original_bg_texture_id_bake)
            # Use GL_LINEAR for scaling the background smoothly
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE); glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR); glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
            glPixelStorei(GL_UNPACK_ALIGNMENT, 1) # Safety for non-multiple-of-4 widths
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, original_bg_width_px_bake, original_bg_height_px_bake, 0, GL_RGBA, GL_UNSIGNED_BYTE, texture_data)
            glBindTexture(GL_TEXTURE_2D, 0)
            print(f"烘焙用背景紋理已載入: ID={original_bg_texture_id_bake}, 原始尺寸={original_bg_width_px_bake}x{original_bg_height_px_bake}")
        except Exception as e:
            print(f"載入烘焙用背景紋理 '{filepath}' 時出錯: {e}")
            if original_bg_texture_id_bake: glDeleteTextures(1, [original_bg_texture_id_bake]); original_bg_texture_id_bake = None
            original_bg_width_px_bake = 0; original_bg_height_px_bake = 0
            return

    # --- 2. Determine Composite Texture Properties (CRITICAL CHANGE) ---
    # Calculate the target world dimensions covered by the scaled background
    target_world_width = original_bg_width_px_bake * scene.map_world_scale
    target_world_height = original_bg_height_px_bake * scene.map_world_scale

    # The composite texture's pixel dimensions will match these world dimensions (1:1)
    composite_texture_width_px = int(round(target_world_width))
    composite_texture_height_px = int(round(target_world_height))

    # Ensure dimensions are at least 1 pixel
    if composite_texture_width_px <= 0 or composite_texture_height_px <= 0:
        print(f"錯誤: 計算出的合成紋理尺寸無效 ({composite_texture_width_px}x{composite_texture_height_px})，請檢查原始圖片尺寸和 scene.map_world_scale。")
        if original_bg_texture_id_bake: glDeleteTextures(1, [original_bg_texture_id_bake]); original_bg_texture_id_bake = None
        return

    # The composite texture's world dimensions are its pixel dimensions
    composite_map_world_width = float(composite_texture_width_px)
    composite_map_world_height = float(composite_texture_height_px)

    # Store the world center from the scene
    composite_map_world_cx = scene.map_world_center_x
    composite_map_world_cz = scene.map_world_center_z

    # The effective scale of THIS composite texture is always 1.0
    composite_map_world_scale = 1.0 # Store for potential future reference/debugging

    print(f"烘焙紋理設定 (1:1 比例): 目標像素尺寸={composite_texture_width_px}x{composite_texture_height_px}")
    print(f"  對應世界範圍: 寬={composite_map_world_width:.1f}, 高={composite_map_world_height:.1f}")
    print(f"  世界中心=({composite_map_world_cx:.1f},{composite_map_world_cz:.1f})")
    print(f"  (原始背景圖經 scene scale {scene.map_world_scale:.3f} 校準)")


    # --- 3. Create FBO and Composite Texture ---
    try:
        composite_map_texture_id = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, composite_map_texture_id)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE); glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        # Keep MIN_FILTER linear, maybe MAG_FILTER too for smoother look when zoomed in? Use Linear for both.
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR); glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        # Create empty texture with the target 1:1 dimensions
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, composite_texture_width_px, composite_texture_height_px, 0, GL_RGBA, GL_UNSIGNED_BYTE, None)
        glBindTexture(GL_TEXTURE_2D, 0)

        composite_fbo = glGenFramebuffers(1)
        glBindFramebuffer(GL_FRAMEBUFFER, composite_fbo)
        glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, composite_map_texture_id, 0)
        status = glCheckFramebufferStatus(GL_FRAMEBUFFER)
        if status != GL_FRAMEBUFFER_COMPLETE:
            print(f"錯誤: FBO 不完整! 狀態碼: {status}")
            glBindFramebuffer(GL_FRAMEBUFFER, 0); _cleanup_bake_resources(); return
        print(f"FBO 已創建 (ID={composite_fbo}) 並綁定 1:1 紋理 (ID={composite_map_texture_id})")
    except Exception as e: print(f"創建 FBO 或烘焙紋理時出錯: {e}"); _cleanup_bake_resources(); return

    # --- 4. Render to FBO ---
    glPushAttrib(GL_VIEWPORT_BIT | GL_TRANSFORM_BIT | GL_ENABLE_BIT | GL_COLOR_BUFFER_BIT | GL_CURRENT_BIT | GL_LINE_BIT | GL_POINT_BIT | GL_TEXTURE_BIT)
    glMatrixMode(GL_PROJECTION); glPushMatrix(); glMatrixMode(GL_MODELVIEW); glPushMatrix()
    try:
        glBindFramebuffer(GL_FRAMEBUFFER, composite_fbo)
        # Set viewport and projection to match the FBO's pixel dimensions
        glViewport(0, 0, composite_texture_width_px, composite_texture_height_px)
        glMatrixMode(GL_PROJECTION); glLoadIdentity();
        # Ortho projection maps directly to pixel coordinates of the FBO
        glOrtho(0, composite_texture_width_px, 0, composite_texture_height_px, -1, 1)
        glMatrixMode(GL_MODELVIEW); glLoadIdentity()
        glDisable(GL_DEPTH_TEST); glDisable(GL_LIGHTING); glEnable(GL_BLEND); glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        # Clear with fallback color first
        r, g, b, a = MINIMAP_BG_FALLBACK_COLOR; glClearColor(r, g, b, a); glClear(GL_COLOR_BUFFER_BIT)

        # --- A. Render Original Background (Scaled to fit FBO) ---
        if original_bg_texture_id_bake is not None:
            glEnable(GL_TEXTURE_2D); glBindTexture(GL_TEXTURE_2D, original_bg_texture_id_bake); glColor4f(1.0, 1.0, 1.0, 1.0)
            # Draw quad covering the entire FBO using standard UVs. OpenGL handles the scaling.
            glBegin(GL_QUADS)
            glTexCoord2f(0, 0); glVertex2f(0, 0) # Bottom-Left FBO pixel
            glTexCoord2f(1, 0); glVertex2f(composite_texture_width_px, 0) # Bottom-Right
            glTexCoord2f(1, 1); glVertex2f(composite_texture_width_px, composite_texture_height_px) # Top-Right
            glTexCoord2f(0, 1); glVertex2f(0, composite_texture_height_px) # Top-Left
            glEnd()
            glBindTexture(GL_TEXTURE_2D, 0); glDisable(GL_TEXTURE_2D);
            print("原始背景圖已(經校準縮放)繪製到 FBO。")

        # --- B. Render Static Elements (Now onto the 1:1 FBO) ---
        # _render_static_elements_to_fbo uses the global composite_* variables,
        # which now correctly reflect the 1:1 scale. _world_to_fbo_coords will work correctly.
        _render_static_elements_to_fbo(scene)

    except Exception as e: print(f"在 FBO 渲染過程中發生錯誤: {e}")
    finally:
        glBindFramebuffer(GL_FRAMEBUFFER, 0); glMatrixMode(GL_PROJECTION); glPopMatrix(); glMatrixMode(GL_MODELVIEW); glPopMatrix(); glPopAttrib()

    # --- 5. Cleanup temporary bake resources ---
    if original_bg_texture_id_bake is not None:
        glDeleteTextures(1, [original_bg_texture_id_bake]); original_bg_texture_id_bake = None; print("烘焙用背景紋理已釋放。")

    print(f"靜態小地圖元素已成功烘焙到 1:1 紋理 ID={composite_map_texture_id} (供模擬器使用)")

# --- Keep _rotate_point_3d (Needed by minimap_renderer bake) ---
# Make sure it's accessible (not private `__`)
@njit
def _rotate_point_3d(point, rx_deg, ry_deg, rz_deg):
    """Applies rotations (in degrees) to a 3D point."""
    # --- KEEPING LOGIC IDENTICAL ---
    # Note: Assumes math=numpy
    rad_x = math.radians(rx_deg)
    rad_y = math.radians(ry_deg)
    rad_z = math.radians(rz_deg)
    cos_x, sin_x = math.cos(rad_x), math.sin(rad_x)
    cos_y, sin_y = math.cos(rad_y), math.sin(rad_y)
    cos_z, sin_z = math.cos(rad_z), math.sin(rad_z)

    x, y, z = point



    # Apply Y rotation (Yaw)
    x1 = x * cos_y + z * sin_y
    y1 = y
    z1 = -x * sin_y + z * cos_y

    # Apply X rotation (Pitch)
    x2 = x1
    y2 = y1 * cos_x - z1 * sin_x
    z2 = y1 * sin_x + z1 * cos_x

    # Apply Z rotation (Roll)
    x3 = x2 * cos_z - y2 * sin_z
    y3 = x2 * sin_z + y2 * cos_z
    z3 = z2

    return np.array([x3, y3, z3])

def _render_static_elements_to_fbo(scene: Scene):
    """ Renders grid, buildings, cylinders, trees into the currently bound FBO. """
    # --- KEEPING LOGIC IDENTICAL (using your tested _world_to_fbo_coords) ---
    print("正在向 FBO 繪製靜態元素 (網格/建築/圓柱/樹)...")
    fbo_w=composite_texture_width_px;
    fbo_h=composite_texture_height_px;
    world_cx=composite_map_world_cx;
    world_cz=composite_map_world_cz;
    world_w=composite_map_world_width;
    world_h=composite_map_world_height
    if fbo_w<=0 or fbo_h<=0 or world_w<=1e-6 or world_h<=1e-6:
        print("警告: FBO/世界尺寸無效。");
        return
    world_min_x = world_cx - world_w/2.0;
    world_max_x = world_cx + world_w/2.0;
    world_min_z = world_cz - world_h/2.0;
    world_max_z = world_cz + world_h/2.0
    glDisable(GL_TEXTURE_2D);
    glLineWidth(1)

    # Grid Lines
    glColor4fv((*MINIMAP_BAKE_GRID_COLOR[:3], 0.5)) # Use specific bake color/alpha
    start_grid_x = math.floor(world_min_x / MINIMAP_GRID_SCALE) * MINIMAP_GRID_SCALE; start_grid_z = math.floor(world_min_z / MINIMAP_GRID_SCALE) * MINIMAP_GRID_SCALE
    current_grid_x = start_grid_x
    while current_grid_x <= world_max_x:
        if current_grid_x >= world_min_x: x1, y1 = _world_to_fbo_coords(current_grid_x, world_min_z, world_cx, world_cz, world_w, world_h, fbo_w, fbo_h); x2, y2 = _world_to_fbo_coords(current_grid_x, world_max_z, world_cx, world_cz, world_w, world_h, fbo_w, fbo_h); glBegin(GL_LINES); glVertex2f(x1, y1); glVertex2f(x2, y2); glEnd()
        current_grid_x += MINIMAP_GRID_SCALE
    current_grid_z = start_grid_z
    while current_grid_z <= world_max_z:
        if current_grid_z >= world_min_z: x1, y1 = _world_to_fbo_coords(world_min_x, current_grid_z, world_cx, world_cz, world_w, world_h, fbo_w, fbo_h); x2, y2 = _world_to_fbo_coords(world_max_x, current_grid_z, world_cx, world_cz, world_w, world_h, fbo_w, fbo_h); glBegin(GL_LINES); glVertex2f(x1, y1); glVertex2f(x2, y2); glEnd()
        current_grid_z += MINIMAP_GRID_SCALE

    # Buildings (Filled Quads)
    glColor4fv(MINIMAP_BAKE_BUILDING_COLOR)
    for item in scene.buildings:
        line_num, bldg = item
        b_type, wx, wy, wz, rx, abs_ry, rz, ww, wd, wh, tid, *_ = bldg;
        half_w, half_d = ww/2.0, wd/2.0
        corners_local = [np.array([-half_w,0,-half_d]), np.array([half_w,0,-half_d]), np.array([half_w,0,half_d]), np.array([-half_w,0,half_d])]
        angle_y_rad = math.radians(-abs_ry);
        cos_y, sin_y = math.cos(angle_y_rad), math.sin(angle_y_rad)
        fbo_coords = []
        for corner in corners_local:
            rotated_x = corner[0]*cos_y - corner[2]*sin_y; rotated_z = corner[0]*sin_y + corner[2]*cos_y
            world_corner_x = wx + rotated_x; world_corner_z = wz + rotated_z
            map_x, map_y = _world_to_fbo_coords(world_corner_x, world_corner_z, world_cx, world_cz, world_w, world_h, fbo_w, fbo_h)
            fbo_coords.append((map_x, map_y))
        if len(fbo_coords)==4:
            glBegin(GL_QUADS); #GL_LINE_LOOP
            [glVertex2f(mx, my) for mx, my in fbo_coords];
            glEnd()

    # Cylinders (Filled Circles or Boxes)
    glColor4fv(MINIMAP_BAKE_CYLINDER_COLOR); num_circle_segments = 16
    for item in scene.cylinders:
        line_num, cyl = item
        # 注意來自scene_parser那邊的剖析結果的變數排列
        c_type, wx, wy, wz, rx, ry, rz, cr, ch, tid, *_ = cyl;
        # 以下是傾斜後的投影計算 已經修過修改符合現狀
        is_tilted = abs(rx)>0.1 or abs(rz)>0.1
        if is_tilted: #is_tilted:
            try: # Keep tilted box approx logic identical to previous version
                p_bottom_local = np.array([0,ch/2,0]);
                p_top_local = np.array([0,-ch/2,0])
                p_bottom_rotated_rel = _rotate_point_3d(p_bottom_local, -rx, ry, -rz)
                p_top_rotated_rel = _rotate_point_3d(p_top_local, -rx, ry, -rz)
                p_bottom_world = np.array([wx,wy,wz]) + p_bottom_rotated_rel #p_bottom_rotated_rel
                p_top_world = np.array([wx,wy,wz]) + p_top_rotated_rel
                p_bottom_xz = np.array([p_bottom_world[0], p_bottom_world[2]]);
                p_top_xz = np.array([p_top_world[0], p_top_world[2]])
                axis_proj_xz = p_top_xz - p_bottom_xz;
                length_proj = np.linalg.norm(axis_proj_xz)
                angle_map_rad = math.arctan2(axis_proj_xz[1], axis_proj_xz[0]) if length_proj > 1e-6 else 0
                center_fbo_x, center_fbo_y = _world_to_fbo_coords(wx, wz, world_cx, world_cz, world_w, world_h, fbo_w, fbo_h)

                proj_len_world = length_proj #max(ch, 2*cr);
                proj_wid_world = 2 * cr #min(ch, 2*cr)
                
                scale_x_fbo = fbo_w / world_w;
                scale_z_fbo = fbo_h / world_h;
                ################################################
                # 計算投影方向與偏移
#                 if length_proj > 1e-6:
#                     direction_x = axis_proj_xz[0] / length_proj
#                     direction_z = axis_proj_xz[1] / length_proj
#                 else:
#                     direction_x, direction_z = 0.0, 0.0
#                 #（沿投影方向移動0.5*ch）
#                 delta_world_x = direction_x * 0.5 * length_proj
#                 delta_world_z = direction_z * 0.5 * length_proj
#                 delta_fbo_x = delta_world_x * scale_x_fbo
#                 delta_fbo_y = delta_world_z * scale_z_fbo
# #                 print(f"delta_fbo_x {delta_fbo_x} delta_fbo_y {delta_fbo_y}")
#                 # 調整中心坐標
#                 center_fbo_x += delta_fbo_x
#                 center_fbo_y += delta_fbo_y


#                 min_scale = min(scale_x_fbo, scale_z_fbo)
                proj_len_px = length_proj * scale_x_fbo;
                proj_wid_px = proj_wid_world * scale_z_fbo
                
                
                
                ##############################################


#                 print(f"center_fbo_x {center_fbo_x} center_fbo_y {center_fbo_y} proj_len_px {proj_len_px} proj_wid_px {proj_wid_px}")
                glPushMatrix();
                glTranslatef(center_fbo_x, center_fbo_y, 0);
                glRotatef(ry-math.degrees(angle_map_rad), 0, 0, 1)
                #
#                 glTranslatef(-proj_len_px/2, -proj_wid_px/2, 0);
                glTranslatef(-proj_len_px/2, 0, 0);
                
                glBegin(GL_QUADS); #GL_LINE_LOOP
                glVertex2f(-proj_len_px/2,-proj_wid_px/2);
                glVertex2f(-proj_len_px/2,proj_wid_px/2);
                glVertex2f(proj_len_px/2,proj_wid_px/2);
                glVertex2f(proj_len_px/2,-proj_wid_px/2);
                glEnd()
                glPopMatrix()
            except Exception as e: print(f"Error baking tilted cylinder: {e}")
        else:
            center_fbo_x, center_fbo_y = _world_to_fbo_coords(wx, wz, world_cx, world_cz, world_w, world_h, fbo_w, fbo_h)
            radius_px_x = cr*(fbo_w/world_w);
            radius_px_y = cr*(fbo_h/world_h);
            radius_px = min(radius_px_x, radius_px_y)
#             print(f"center_fbo_x{center_fbo_x} center_fbo_y{center_fbo_y} radius_px_x{radius_px_x} radius_px_y{radius_px_y} radius_px{radius_px}")
            if radius_px > 0.5:
                glBegin(GL_TRIANGLE_FAN);
                glVertex2f(center_fbo_x, center_fbo_y)
                for i in range(num_circle_segments+1):
                    angle = 2*math.pi*i/num_circle_segments;
                    glVertex2f(
                        center_fbo_x+radius_px*math.cos(angle),
                        center_fbo_y+radius_px*math.sin(angle)
                    )
                glEnd()

    # Trees (Points or Small Circles)
    glColor4fv(MINIMAP_BAKE_TREE_COLOR); tree_radius_px = 2; glPointSize(tree_radius_px*3)
    glBegin(GL_POINTS) # Using points for simplicity in bake
    for item in scene.trees:
        line_num, tree = item
        tx, ty, tz, th = tree; fbo_x, fbo_y = _world_to_fbo_coords(tx, tz, world_cx, world_cz, world_w, world_h, fbo_w, fbo_h)
        if 0 <= fbo_x <= fbo_w and 0 <= fbo_y <= fbo_h: glVertex2f(fbo_x, fbo_y)
    glEnd();
    
    # --- Bake Spheres (Filled Circles) ---
    glColor4fv(MINIMAP_BAKE_SPHERE_COLOR) # 使用烘焙顏色
    num_circle_segments_bake = 16 # 烘焙時可以用更高精度
    for item in scene.spheres:
        line_num, sphere_data = item
        try:
            s_type, wx, wy, wz, srx, sabs_ry, srz, cr, *rest = sphere_data
        except ValueError:
             print(f"警告: 解包 sphere 數據 (FBO烘焙) 時出錯 (來源行: {line_num})")
             continue

        # 轉換到 FBO 像素座標
        center_fbo_x, center_fbo_y = _world_to_fbo_coords(wx, wz, world_cx, world_cz, world_w, world_h, fbo_w, fbo_h)
        # 計算 FBO 上的像素半徑 (假設 X/Z 縮放一致或取平均)
        radius_px = cr * (fbo_w / world_w) # 或者 min(fbo_w/world_w, fbo_h/world_h)

        if radius_px > 0.5: # 簡單剔除
            glBegin(GL_TRIANGLE_FAN)
            glVertex2f(center_fbo_x, center_fbo_y) # 中心點
            for i in range(num_circle_segments_bake + 1): # +1確保閉合
                angle = 2 * math.pi * i / num_circle_segments_bake
                glVertex2f(center_fbo_x + radius_px * math.cos(angle),
                           center_fbo_y + radius_px * math.sin(angle))
            glEnd()    
    
    
    
    glPointSize(1.0)

    print("靜態元素 FBO 繪製完成。")


# --- Simulator Runtime Drawing (Keep as before) ---
def draw_simulator_minimap(scene: Scene, tram: Tram, screen_width, screen_height):
    """ Draws the SIMULATOR minimap using the baked texture + overlays. """
    global current_simulator_minimap_range
    if composite_map_texture_id is None: return # Skip if no baked texture

    # --- KEEPING LOGIC IDENTICAL ---
    map_draw_size=MINIMAP_SIZE;
    map_left=screen_width-map_draw_size-MINIMAP_PADDING;
    map_right=screen_width-MINIMAP_PADDING;
    map_bottom=screen_height-map_draw_size-MINIMAP_PADDING;
    map_top=screen_height-MINIMAP_PADDING;
    map_center_x_screen=map_left+map_draw_size/2.;
    map_center_y_screen=map_bottom+map_draw_size/2.
    player_x=tram.position[0];
    player_z=tram.position[2];
    view_range=current_simulator_minimap_range

    glMatrixMode(GL_PROJECTION);
    glPushMatrix();
    glLoadIdentity();
    # 這裡改這樣是為了修正在模擬器畫面中小地圖顯示比例不是正方形的問題
    gluOrtho2D(map_left-50, map_right, map_bottom-50, map_top);
    glMatrixMode(GL_MODELVIEW);
    glPushMatrix();
    glLoadIdentity()
    glPushAttrib(GL_ENABLE_BIT|GL_COLOR_BUFFER_BIT|GL_VIEWPORT_BIT|GL_SCISSOR_BIT|GL_LINE_BIT|GL_POINT_BIT|GL_TEXTURE_BIT|GL_CURRENT_BIT)
    glDisable(GL_DEPTH_TEST); glDisable(GL_LIGHTING);
    glEnable(GL_BLEND);
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glViewport(int(map_left), int(map_bottom), int(map_draw_size), int(map_draw_size));
    glEnable(GL_SCISSOR_TEST); glScissor(int(map_left), int(map_bottom), int(map_draw_size), int(map_draw_size))

    # A. Draw Baked Texture Background (Calculate UVs based on view)
    glEnable(GL_TEXTURE_2D); glBindTexture(GL_TEXTURE_2D, composite_map_texture_id); glColor4f(1.,1.,1.,1.)
    if composite_map_world_width<=1e-6 or composite_map_world_height<=1e-6: u_min,u_max,v_min,v_max = 0.,1.,0.,1.
    else:
        world_half_range=view_range/2.; view_l=player_x-world_half_range; view_r=player_x+world_half_range; view_b=player_z-world_half_range; view_t=player_z+world_half_range
        baked_min_x=composite_map_world_cx-composite_map_world_width/2.; baked_max_x=composite_map_world_cx+composite_map_world_width/2.; baked_min_z=composite_map_world_cz-composite_map_world_height/2.; baked_max_z=composite_map_world_cz+composite_map_world_height/2.
        u_min=(baked_max_x-view_r)/composite_map_world_width; u_max=(baked_max_x-view_l)/composite_map_world_width # Flipped X
        v_min=(view_b-baked_min_z)/composite_map_world_height; v_max=(view_t-baked_min_z)/composite_map_world_height
    glBegin(GL_QUADS); glTexCoord2f(u_min,v_min); glVertex2f(map_left,map_bottom); glTexCoord2f(u_max,v_min); glVertex2f(map_right,map_bottom); glTexCoord2f(u_max,v_max); glVertex2f(map_right,map_top); glTexCoord2f(u_min,v_max); glVertex2f(map_left,map_top); glEnd()
    glBindTexture(GL_TEXTURE_2D,0); glDisable(GL_TEXTURE_2D)

    # B. Overlay Dynamic Elements
    overlay_scale = map_draw_size / view_range
    # B.1 Draw Track
    if scene and scene.track:
        glLineWidth(2.0); glColor3fv(MINIMAP_TRACK_COLOR)
        for segment in scene.track.segments:
            if not segment.points or len(segment.points)<2:
                continue
#             print(f"segment: {segment}")
            # 畫出軌道端點
            map_x, map_y = _world_to_map_coords_adapted(segment.points[0][0], segment.points[0][2],
                                                player_x, player_z,
                                                map_center_x_screen, map_center_y_screen, overlay_scale)
            glPointSize(8)
            glBegin(GL_POINTS)
            glColor3fv(MINIMAP_TRACK_COLOR)
            glVertex2f(map_x, map_y)  # 
            glEnd()        
             
            glBegin(GL_LINE_STRIP)
            for point_world in segment.points:
                map_x,map_y = _world_to_map_coords_adapted(point_world[0], point_world[2], player_x, player_z, map_center_x_screen, map_center_y_screen, overlay_scale);
                glVertex2f(map_x, map_y)
            glEnd()
    # B.2 Draw Player Marker
    glColor3fv(MINIMAP_PLAYER_COLOR);
    player_screen_x=map_center_x_screen;
    player_screen_y=map_center_y_screen
    player_angle_rad = math.arctan2(tram.forward_vector_xz[1], tram.forward_vector_xz[0]) + math.pi # Keep - sign
    tip_angle=player_angle_rad;
    left_angle=player_angle_rad-math.pi*.75;
    right_angle=player_angle_rad+math.pi*.75
    tip_x=player_screen_x+math.cos(tip_angle)*MINIMAP_PLAYER_SIZE;
    tip_y=player_screen_y-math.sin(tip_angle)*MINIMAP_PLAYER_SIZE
    left_x=player_screen_x+math.cos(left_angle)*MINIMAP_PLAYER_SIZE*1.7;
    left_y=player_screen_y-math.sin(left_angle)*MINIMAP_PLAYER_SIZE*1.7
    right_x=player_screen_x+math.cos(right_angle)*MINIMAP_PLAYER_SIZE*1.7;
    right_y=player_screen_y-math.sin(right_angle)*MINIMAP_PLAYER_SIZE*1.7
    glBegin(GL_TRIANGLES);
    glVertex2f(tip_x,tip_y);
    glVertex2f(left_x,left_y);
    glVertex2f(right_x,right_y);
    glEnd()

    # Disable Scissor for Labels
    glDisable(GL_SCISSOR_TEST)
    # B.3 Draw Grid Labels
    show_labels = grid_label_font and view_range < DEFAULT_MINIMAP_RANGE * 4.5
    if show_labels:
        world_half_x=(map_draw_size/overlay_scale)/2.; world_half_z=(map_draw_size/overlay_scale)/2.
        world_l=player_x-world_half_x; world_r=player_x+world_half_x; world_b=player_z-world_half_z; world_t=player_z+world_half_z
        start_gx=math.floor(world_l/MINIMAP_GRID_SCALE)*MINIMAP_GRID_SCALE; start_gz=math.floor(world_b/MINIMAP_GRID_SCALE)*MINIMAP_GRID_SCALE
        current_gx=start_gx
        while current_gx <= world_r:
            map_x,_ = _world_to_map_coords_adapted(current_gx, player_z, player_x, player_z, map_center_x_screen, map_center_y_screen, overlay_scale)
            if map_left<=map_x<=map_right:
                label_text=f"{current_gx:.0f}";
                try:
                    text_surface=grid_label_font.render(label_text,True,MINIMAP_GRID_LABEL_COLOR);
                    dx=map_x-text_surface.get_width()/2;
                    dy=map_bottom-MINIMAP_GRID_LABEL_OFFSET-text_surface.get_height();
                    renderer._draw_text_texture(text_surface,dx,dy);
                except Exception as e:
                    pass
            current_gx += MINIMAP_GRID_SCALE
        current_gz=start_gz
        while current_gz <= world_t:
            _,map_y = _world_to_map_coords_adapted(player_x, current_gz, player_x, player_z, map_center_x_screen, map_center_y_screen, overlay_scale)
            if map_bottom<=map_y<=map_top:
                label_text=f"{current_gz:.0f}";
                try:
                    text_surface=grid_label_font.render(label_text,True,MINIMAP_GRID_LABEL_COLOR);
                    dx=map_left-MINIMAP_GRID_LABEL_OFFSET-text_surface.get_width();
                    dy=map_y-text_surface.get_height()/2;
                    renderer._draw_text_texture(text_surface,dx,dy);
                except Exception as e:
                    pass
            current_gz += MINIMAP_GRID_SCALE

    glPopAttrib(); glMatrixMode(GL_PROJECTION); glPopMatrix(); glMatrixMode(GL_MODELVIEW); glPopMatrix()


# --- Editor Runtime Drawing (DYNAMIC RENDERING RESTORED) ---
def draw_editor_preview(scene: Scene, view_center_x, view_center_z, view_range, widget_width, widget_height, highlight_line_nums: set = set()):
    """ Draws the EDITOR minimap preview using DYNAMIC rendering (like original). """
    global editor_bg_texture_id, editor_bg_width_px, editor_bg_height_px, editor_current_map_filename

    widget_center_x_screen = widget_width / 2.0
    widget_center_y_screen = widget_height / 2.0

    # Determine scale based on view range and widget size
    if view_range <= 1e-6: view_range = MINIMAP_MIN_RANGE # Avoid division by zero
    scale = min(widget_width, widget_height) / view_range

    # --- Setup GL State (assumed mostly done by caller widget) ---
    # But ensure texture is off initially
    glDisable(GL_TEXTURE_2D)

    # --- 1. Draw Background (Dynamically load/draw original texture) ---
    bg_drawn = False
    if scene and scene.map_filename:
        # Check if editor needs to load/reload its background texture
        if scene.map_filename != editor_current_map_filename:
            print(f"編輯器偵測到地圖變更: {scene.map_filename}")
            # Cleanup old editor texture if exists
            if editor_bg_texture_id and glIsTexture(editor_bg_texture_id):
                glDeleteTextures(1, [editor_bg_texture_id])
            editor_bg_texture_id = None
            editor_bg_width_px = 0
            editor_bg_height_px = 0
            editor_current_map_filename = scene.map_filename # Store new name

            # Attempt to load new texture using texture_loader (or similar logic)
            filepath = os.path.join("textures", scene.map_filename)
            if os.path.exists(filepath):
                try:
                    # --- 使用 Pillow 載入圖像 ---
                    print(f"嘗試使用 Pillow 載入圖像: {filepath}") # Debug
                    img = Image.open(filepath)
                    # 確保圖像為 RGBA 格式 (如果不是，轉換它)
                    if img.mode != 'RGBA':
                        print(f"圖像模式為 {img.mode}，轉換為 RGBA...") # Debug
                        img = img.convert('RGBA')
                    # 獲取圖像數據
                    texture_data = img.tobytes("raw", "RGBA", 0, -1) # OpenGL 通常需要 Y 軸倒置的數據
                    editor_bg_width_px, editor_bg_height_px = img.size
                    print(f"Pillow 載入成功: 尺寸={img.size}, 模式={img.mode}") # Debug
                    # -----------------------------
#                     print(f"嘗試載入 Pygame Surface: {filepath}") # Debug
#                     surface = pygame.image.load(filepath).convert_alpha()
#                     print(f"Surface 載入成功: 尺寸={surface.get_size()}, 格式={pygame.PixelFormat(surface.get_bitsize(), surface.get_masks()).format}") # Debug
#                     print("嘗試轉換 Surface 為 RGBA 字串...") # Debug
#                     texture_data = pygame.image.tostring(surface, "RGBA", True)
#                     print(f"字串轉換成功: 長度={len(texture_data)}") # Debug
#                     editor_bg_width_px = surface.get_width()
#                     editor_bg_height_px = surface.get_height()
                    
                    if editor_bg_width_px > 0 and editor_bg_height_px > 0:
                         editor_bg_texture_id = glGenTextures(1)
                         glBindTexture(GL_TEXTURE_2D, editor_bg_texture_id)
                         glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
                         glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
                         glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
                         glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)

                         # --- 新增：檢查載入前的錯誤 ---
                         error_before = glGetError()
                         if error_before != GL_NO_ERROR:
                             print(f"警告: glTexImage2D 之前存在 OpenGL 錯誤: {gluErrorString(error_before)}")
                         # ---------------------------

                         # --- 新增：設定像素解包對齊方式 ---
                         # 有些圖片的行寬不是4字節的倍數，可能導致問題，設為1最安全
                         glPixelStorei(GL_UNPACK_ALIGNMENT, 1)
                         # ---------------------------------

                         glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, editor_bg_width_px, editor_bg_height_px, 0, GL_RGBA, GL_UNSIGNED_BYTE, texture_data)

                         # --- 新增：檢查載入後的錯誤 ---
                         error_after = glGetError()
                         if error_after != GL_NO_ERROR:
                             print(f"錯誤: glTexImage2D 執行時發生 OpenGL 錯誤: {gluErrorString(error_after)}")
                             # 如果出錯，嘗試刪除無效的紋理 ID
                             glDeleteTextures(1, [editor_bg_texture_id])
                             editor_bg_texture_id = None # 標記為無效
                         else:
                             print(f"編輯器背景紋理 glTexImage2D 成功: ID={editor_bg_texture_id}")
                         # ---------------------------

                         glBindTexture(GL_TEXTURE_2D, 0)
                         print(f"編輯器背景紋理已載入: ID={editor_bg_texture_id}, 尺寸={editor_bg_width_px}x{editor_bg_height_px}")
                    else: print("錯誤: 編輯器背景圖尺寸無效。")
                except Exception as e: print(f"載入編輯器背景紋理 '{filepath}' 時出錯: {e}"); editor_bg_texture_id = None
            else: print(f"警告: 找不到編輯器背景圖 '{filepath}'。")

        # If texture is loaded, draw it
        if editor_bg_texture_id and editor_bg_width_px > 0 and editor_bg_height_px > 0 and abs(scene.map_world_scale) > 1e-6:
            glEnable(GL_TEXTURE_2D)
            glBindTexture(GL_TEXTURE_2D, editor_bg_texture_id)
            glColor4f(1.0, 1.0, 1.0, 1.0)

            # Calculate UVs based on editor view (Similar to original simulator logic)
            image_world_width = editor_bg_width_px * scene.map_world_scale
            image_world_height = editor_bg_height_px * scene.map_world_scale
            img_world_x_min = scene.map_world_center_x - (image_world_width / 2.0)
            img_world_z_min = scene.map_world_center_z - (image_world_height / 2.0)
            img_world_x_max = scene.map_world_center_x + (image_world_width / 2.0) # Flipped UV calc needs max

            view_half_w_world = (widget_width / scale) / 2.0
            view_half_h_world = (widget_height / scale) / 2.0
            view_l=view_center_x - view_half_w_world; view_r=view_center_x + view_half_w_world
            view_b=view_center_z - view_half_h_world; view_t=view_center_z + view_half_h_world

            if abs(image_world_width)<1e-6 or abs(image_world_height)<1e-6: u_min,u_max,v_min,v_max = 0.,1.,0.,1.
            else: # Use flipped X UV calculation consistent with _world_to_map_coords_adapted X flip
                u_min = (img_world_x_max - view_r) / image_world_width
                u_max = (img_world_x_max - view_l) / image_world_width
                v_min = (view_b - img_world_z_min) / image_world_height
                v_max = (view_t - img_world_z_min) / image_world_height

            glBegin(GL_QUADS)
            glTexCoord2f(u_min, v_min); glVertex2f(0, 0) # Bottom Left Widget Coord
            glTexCoord2f(u_max, v_min); glVertex2f(widget_width, 0) # Bottom Right Widget Coord
            glTexCoord2f(u_max, v_max); glVertex2f(widget_width, widget_height) # Top Right Widget Coord
            glTexCoord2f(u_min, v_max); glVertex2f(0, widget_height) # Top Left Widget Coord
            glEnd()
            glBindTexture(GL_TEXTURE_2D, 0)
            glDisable(GL_TEXTURE_2D)
            bg_drawn = True

        # If no texture drawn, draw solid fallback color
        if not bg_drawn:
            glPushAttrib(GL_CURRENT_BIT)
            r,g,b,a = EDITOR_BG_COLOR; glColor4f(r,g,b,a)
            glRectf(0, 0, widget_width, widget_height)
            glPopAttrib()

        # --- 2. Draw Grid Lines Dynamically ---
        # (Using logic from original _render_map_view)
        if view_range < DEFAULT_MINIMAP_RANGE * 3.0: # Condition from original
            glColor4fv((*MINIMAP_DYNAMIC_GRID_COLOR[:3], 0.5)) # Use dynamic color/alpha
            glLineWidth(2)
            # Calculate world boundaries visible
            world_half_range_x = (widget_width / scale) / 2.0
            world_half_range_z = (widget_height / scale) / 2.0
            world_view_left = view_center_x - world_half_range_x;
            world_view_right = view_center_x + world_half_range_x
            world_view_bottom_z = view_center_z - world_half_range_z;
            world_view_top_z = view_center_z + world_half_range_z
            start_grid_x = math.floor(world_view_left / MINIMAP_GRID_SCALE) * MINIMAP_GRID_SCALE
            start_grid_z = math.floor(world_view_bottom_z / MINIMAP_GRID_SCALE) * MINIMAP_GRID_SCALE

            # --- Draw Vertical Lines ---
            current_grid_x = start_grid_x
            while True: # Loop potentially infinitely in world space
                map_x, _ = _world_to_map_coords_adapted(current_grid_x, view_center_z, view_center_x, view_center_z, widget_center_x_screen, widget_center_y_screen, scale)
                
                # Check if the line's SCREEN coordinate is beyond the right edge of the widget
                # The X-axis is flipped in _world_to_map_coords_adapted, so as world_x increases, map_x decreases.
                # We need to check if map_x is less than 0 (went off the left edge visually).
                if map_x < 0: # Check if line moved off the *left* edge of the widget
                     break # Stop drawing vertical lines

                # Check if the line's SCREEN coordinate is still to the right of the *right* edge
                # Only draw if it's potentially visible (within or entering the widget)
                if map_x <= widget_width:
                    glBegin(GL_LINES)
                    glVertex2f(map_x, 0)
                    glVertex2f(map_x, widget_height)
                    glEnd()

                current_grid_x += MINIMAP_GRID_SCALE # Move to the next line in world coordinates

            # --- Draw Horizontal Lines ---
            current_grid_z = start_grid_z
            while True: # Loop potentially infinitely in world space
                _, map_y = _world_to_map_coords_adapted(view_center_x, current_grid_z, view_center_x, view_center_z, widget_center_x_screen, widget_center_y_screen, scale)

                # Check if the line's SCREEN coordinate is beyond the top edge of the widget
                if map_y > widget_height: # Check if line moved off the *top* edge
                     break # Stop drawing horizontal lines

                # Check if the line's SCREEN coordinate is still below the *bottom* edge
                # Only draw if it's potentially visible (within or entering the widget)
                if map_y >= 0:
                     glBegin(GL_LINES)
                     glVertex2f(0, map_y)
                     glVertex2f(widget_width, map_y)
                     glEnd()

                current_grid_z += MINIMAP_GRID_SCALE # Move to the next line

    # --- 3. Draw Static Objects Dynamically ---
    # (Using logic from original _render_map_view)
    if scene:
        # Buildings (Lines)
        glColor3fv(MINIMAP_DYNAMIC_BUILDING_COLOR)
        glLineWidth(2.0)
        for item in scene.buildings:
            line_num, bldg = item # 解包行號和數據元組
            b_type, wx, wy, wz, rx, abs_ry, rz, ww, wd, wh, tid, *_ = bldg # 解包數據元組
            
            glPushAttrib(GL_CURRENT_BIT) # 保存當前顏色狀態
            try:
                if line_num in highlight_line_nums:
                    glColor3f(1.0, 1.0, 0.0) # 高亮顏色 (黃色)
                    glLineWidth(3.0) # 可以加粗線條
                else:
                    glColor3fv(MINIMAP_DYNAMIC_BUILDING_COLOR)
                    glLineWidth(2.0) # 正常線條寬度
            
                half_w,half_d = ww/2.,wd/2.
                corners_local = [np.array([-half_w,0,-half_d]),np.array([half_w,0,-half_d]),np.array([half_w,0,half_d]),np.array([-half_w,0,half_d])]
                angle_y_rad = math.radians(-abs_ry);
                cos_y,sin_y = math.cos(angle_y_rad),math.sin(angle_y_rad)
                map_coords = []
                for corner in corners_local:
                    rotated_x = corner[0]*cos_y - corner[2]*sin_y;
                    rotated_z = corner[0]*sin_y + corner[2]*cos_y
                    world_corner_x = wx + rotated_x;
                    world_corner_z = wz + rotated_z
                    map_x,map_y = _world_to_map_coords_adapted(world_corner_x, world_corner_z, view_center_x, view_center_z, widget_center_x_screen, widget_center_y_screen, scale)
                    map_coords.append((map_x, map_y))
                if len(map_coords)==4:
                    glBegin(GL_LINE_LOOP);
                    [glVertex2f(mx,my) for mx,my in map_coords];
#                     print("DEBUG: Before glEnd for Building loop")
                    glEnd()
                
                # 求取矩形中心座標
                sum_x = sum(coord[0] for coord in map_coords)
                sum_y = sum(coord[1] for coord in map_coords)
                center = (sum_x / 4, sum_y / 4)

                # 顯示Y值
                label_text=f"{wy:.1f}";
                label_color = MINIMAP_GRID_LABEL_COLOR if line_num in highlight_line_nums else MINIMAP_DYNAMIC_BUILDING_LABEL_COLOR
                try:
                    text_surface=coord_label_font.render(label_text,True,label_color);
                    dx=center[0] + 0;
                    dy=center[1];
                    renderer._draw_text_texture(text_surface,dx,dy);
                except Exception as e:
                    pass
                
            finally:
                glPopAttrib() # 恢復狀態

        # Cylinders (Circles/Boxes)
        glColor3fv(MINIMAP_DYNAMIC_CYLINDER_COLOR); num_circle_segments = 12
        for item in scene.cylinders:
            line_num, cyl = item # 解包行號和數據元組
            # 注意來自scene_parser那邊的剖析結果的變數排列
            c_type, wx, wy, wz, rx, ry, rz, cr, ch, tid, *_ = cyl;
            
            glPushAttrib(GL_CURRENT_BIT) # 保存當前顏色狀態
            try:
                if line_num in highlight_line_nums:
                    glColor3f(1.0, 1.0, 0.0) # 高亮顏色 (黃色)
                    glLineWidth(3.0) # 可以加粗線條
                else:
                    glColor3fv(MINIMAP_DYNAMIC_BUILDING_COLOR)
                    glLineWidth(2.0) # 正常線條寬度
                
                # 以下是傾斜後的投影計算 已經修過修改符合現狀
                is_tilted = abs(rx)>0.1 or abs(rz)>0.1
                if is_tilted: # Draw tilted approx box (lines)
                    try:
                        p_bl = np.array([0,ch/2,0]);
                        p_tl = np.array([0,-ch/2,0])
                        p_br = _rotate_point_3d(p_bl, -rx, ry, -rz);
                        p_tr = _rotate_point_3d(p_tl, -rx, ry, -rz)
                        p_bw = np.array([wx,wy,wz])+p_br;
                        p_tw = np.array([wx,wy,wz])+p_tr
                        p_bxz = np.array([p_bw[0],p_bw[2]]);
                        p_txz = np.array([p_tw[0],p_tw[2]])
                        axis_proj = p_txz - p_bxz;
                        length_proj = np.linalg.norm(axis_proj)
                        angle_map = math.arctan2(axis_proj[1], axis_proj[0]) if length_proj>1e-6 else 0
                        center_map_x, center_map_y = _world_to_map_coords_adapted(wx, wz, view_center_x, view_center_z, widget_center_x_screen, widget_center_y_screen, scale)
                        
                        proj_len = length_proj
                        proj_wid = 2*cr # Approx size in screen units

                        scale_x_fbo = scale # / widget_width;
                        scale_z_fbo = scale # / widget_height;
                        ###############################################
                        # 計算投影方向與偏移
    #                     if length_proj > 1e-6:
    #                         direction_x = axis_proj[0] / length_proj
    #                         direction_z = axis_proj[1] / length_proj
    #                     else:
    #                         direction_x, direction_z = 0.0, 0.0
    #                     #（沿投影方向移動0.5*ch）
    #                     delta_world_x = direction_x * 0.5 * ch
    #                     delta_world_z = direction_z * 0.5 * ch
    #                     delta_fbo_x = delta_world_x * scale_x_fbo
    #                     delta_fbo_y = delta_world_z * scale_z_fbo
    #     #                 print(f"delta_fbo_x {delta_fbo_x} delta_fbo_y {delta_fbo_y}")
    #                     # 調整中心坐標
    #                     center_map_x += delta_fbo_x
    #                     center_map_y += delta_fbo_y
                        ###################################################


                        proj_len_px = length_proj * scale_x_fbo;
                        proj_wid_px = proj_wid * scale_z_fbo

                        glPushMatrix();
                        glTranslatef(center_map_x, center_map_y, 0);
                        glRotatef(ry-math.degrees(angle_map), 0, 0, 1)
                        # 往旋轉後的矩形中心點偏移
#                         glTranslatef(-proj_len_px/2, -proj_wid_px/2, 0);
                        glTranslatef(-proj_len_px/2, 0, 0);
                        
                        glBegin(GL_LINE_LOOP);
                        glVertex2f(-proj_len_px/2,-proj_wid_px/2);
                        glVertex2f(-proj_len_px/2,proj_wid_px/2);
                        glVertex2f(proj_len_px/2,proj_wid_px/2);
                        glVertex2f(proj_len_px/2,-proj_wid_px/2);
                        glEnd()
                        glPopMatrix()
                    except Exception as e: pass # Ignore errors during dynamic draw?
                else: # Draw circle (lines)
                    center_map_x, center_map_y = _world_to_map_coords_adapted(wx, wz, view_center_x, view_center_z, widget_center_x_screen, widget_center_y_screen, scale)
                    radius_map = cr * scale
                    if radius_map > 0.5: # Basic culling/detail check
                        glBegin(GL_LINE_LOOP)
                        for i in range(num_circle_segments):
                            angle = 2*math.pi*i/num_circle_segments;
                            glVertex2f(
                                center_map_x+radius_map*math.cos(angle),
                                center_map_y+radius_map*math.sin(angle)
                                )
                        glEnd()

                # 顯示Y值
                label_text=f"{wy:.1f}";
                label_color = MINIMAP_GRID_LABEL_COLOR if line_num in highlight_line_nums else MINIMAP_DYNAMIC_CYLINDER_LABEL_COLOR
                try:
                    text_surface=coord_label_font.render(label_text,True,label_color);
                    dx=center_map_x + 0;
                    dy=center_map_y;
                    renderer._draw_text_texture(text_surface,dx,dy);
                except Exception as e:
                    pass
                
            finally:
                glPopAttrib() # 恢復狀態

        # Trees (Points)
        glColor3fv(MINIMAP_DYNAMIC_TREE_COLOR)
        min_pt, max_pt = 2.0, 10.0;
        vr = view_range;
        dr = DEFAULT_MINIMAP_RANGE;
        mr = MINIMAP_MIN_RANGE
        zoom_ratio = max(0, min(1, (dr-vr)/(dr-mr))) if (dr-mr)!=0 else 0;
        point_size = min_pt+(max_pt-min_pt)*zoom_ratio
        glPointSize(max(1.0, point_size))
        
        glBegin(GL_POINTS)
        for item in scene.trees:
            line_num, tree = item # 解包行號和數據元組
            if line_num not in highlight_line_nums: # 只處理非高亮的
                tx, ty, tz, th = tree;
                map_x, map_y = _world_to_map_coords_adapted(tx, tz, view_center_x, view_center_z, widget_center_x_screen, widget_center_y_screen, scale)
                # Basic point culling
                if 0 <= map_x <= widget_width and 0 <= map_y <= widget_height:
                    glVertex2f(map_x, map_y)
        glEnd() # 結束非高亮點的繪製
        
        # --- 繪製高亮的樹 ---
        if highlight_line_nums: # 只有當有需要高亮的行時才執行
            glColor3f(1.0, 1.0, 0.0) # 高亮顏色
            glPointSize(max(1.0, point_size) * 1.5) # 高亮點可以稍微大一點 (示例)

            glBegin(GL_POINTS)
            for item in scene.trees:
                line_num, tree_data = item
                if line_num in highlight_line_nums: # 只處理高亮的
                    tx, ty, tz, th = tree_data
                    map_x, map_y = _world_to_map_coords_adapted(tx, tz, view_center_x, view_center_z, widget_center_x_screen, widget_center_y_screen, scale)
                    # Basic point culling
                    if 0 <= map_x <= widget_width and 0 <= map_y <= widget_height:
                        glVertex2f(map_x, map_y)
            glEnd() # 結束高亮點的繪製

        # --- Draw Spheres (Circles) Dynamically ---
        num_circle_segments = 12 # 圓的邊數 (可以根據縮放調整)
        for item in scene.spheres:
            line_num, sphere_data = item
            # 解包獲取必要資訊 (世界座標 wx, wy, wz 和半徑 cr)
            try:
                s_type, wx, wy, wz, srx, sabs_ry, srz, cr, *rest = sphere_data
            except ValueError:
                 print(f"警告: 解包 sphere 數據 (動態小地圖) 時出錯 (來源行: {line_num})")
                 continue

            glPushAttrib(GL_CURRENT_BIT | GL_LINE_BIT) # 保存顏色和線寬狀態
            try:
                # --- 高亮處理 ---
                is_highlighted = line_num in highlight_line_nums
                if is_highlighted:
                    glColor3f(1.0, 1.0, 0.0) # 高亮黃色
                    glLineWidth(3.0)
                else:
                    glColor3fv(MINIMAP_DYNAMIC_SPHERE_COLOR)
                    glLineWidth(2.0)

                # --- 繪製圓形 ---
                center_map_x, center_map_y = _world_to_map_coords_adapted(wx, wz, view_center_x, view_center_z, widget_center_x_screen, widget_center_y_screen, scale)
                radius_map = cr * scale
                if radius_map > 0.5: # 簡單的細節剔除
                    glBegin(GL_LINE_LOOP)
                    for i in range(num_circle_segments):
                        angle = 2 * math.pi * i / num_circle_segments
                        glVertex2f(center_map_x + radius_map * math.cos(angle),
                                   center_map_y + radius_map * math.sin(angle))
                    glEnd()

                # --- 繪製 Y 座標標籤 ---
                label_text = f"{wy:.1f}"
                label_color = MINIMAP_GRID_LABEL_COLOR if is_highlighted else MINIMAP_DYNAMIC_SPHERE_LABEL_COLOR
                try:
                    if coord_label_font: # 確保字體存在
                        text_surface = coord_label_font.render(label_text, True, label_color)
                        # 計算繪製位置 (例如在圓心右側)
                        dx = center_map_x + radius_map + 2 # 加一點偏移
                        dy = center_map_y - text_surface.get_height() / 2
                        renderer._draw_text_texture(text_surface, dx, dy)
                except Exception as e:
                    pass # 忽略繪製標籤錯誤
            finally:
                glPopAttrib() # 恢復顏色和線寬

        # 恢復默認點大小
        glPointSize(1.0)

#                     glColor3f(1.0, 1.0, 0.0) # 高亮顏色 (黃色)
#                     glLineWidth(3.0) # 可以加粗線條
#                 else:
#                     glColor3fv(MINIMAP_DYNAMIC_BUILDING_COLOR)
#                     glLineWidth(2.0) # 正常線條寬度
            

        
#         print("DEBUG: Before glEnd for Trees")
#         glEnd();
#         glPointSize(1.0)


#             glPushAttrib(GL_CURRENT_BIT) # 保存當前顏色狀態
#             try:
#             finally:
#                 glPopAttrib() # 恢復狀態

    # --- 4. Draw Track Lines Dynamically ---
    if scene and scene.track:
        glLineWidth(2.0) # Match simulator track overlay width?
        glPointSize(8)
        glColor3fv(MINIMAP_TRACK_COLOR)
        
        for segment in scene.track.segments:
            if not segment.points or len(segment.points) < 2:
                continue
            
            glPushAttrib(GL_CURRENT_BIT | GL_LINE_BIT | GL_POINT_BIT) # 保存狀態
            is_highlighted = False # Flag to track highlighting
            try:
                line_num = segment.source_line_number # 獲取行號
                is_highlighted = line_num in highlight_line_nums
                if is_highlighted:
                    glColor3f(1.0, 1.0, 0.0) # 高亮顏色
                    glLineWidth(4.0)        # 加粗線條
                    glPointSize(10)         # 加大端點
                else:
                    glColor3fv(MINIMAP_TRACK_COLOR)
                    glLineWidth(2.0)
                    glPointSize(8)
            
#             print(f"segment: {dir(segment)}")
                # 畫出軌道端點
                map_x, map_y = _world_to_map_coords_adapted(segment.points[0][0], segment.points[0][2],
                                                    view_center_x, view_center_z,
                                                    widget_center_x_screen, widget_center_y_screen, scale)
#                 glPointSize(8)
                glBegin(GL_POINTS)
#                 glColor3fv(MINIMAP_TRACK_COLOR)
                glVertex2f(map_x, map_y)  # 
                glEnd()        

                glBegin(GL_LINE_STRIP)
                for point_world in segment.points:
                    widget_x, widget_y = _world_to_map_coords_adapted(point_world[0], point_world[2], view_center_x, view_center_z, widget_center_x_screen, widget_center_y_screen, scale)
                    glVertex2f(widget_x, widget_y)
                glEnd()

            finally:
                glPopAttrib() # 恢復狀態

            # 顯示端點info
            # 'ballast_vao', 'ballast_vbo', 'ballast_vertices',
            # 'cleanup_buffers', 'create_gl_buffers', 'end_angle_rad',
            # 'end_pos', 'get_position_orientation', 'gradient_factor',
            # 'horizontal_length', 'length', 'orientations', 'points',
            # 'rail_left_vao', 'rail_left_vbo', 'rail_left_vertices',
            # 'rail_right_vao', 'rail_right_vbo', 'rail_right_vertices',
            # 'setup_buffers', 'start_angle_rad', 'start_pos'
            is_curve = True if segment.start_angle_rad != segment.end_angle_rad else False
            if is_curve:
                track_info = f"C {segment.angle_deg:.1f}°"
            else:
                track_info = f"S {segment.horizontal_length}"
            label_text=f"{track_info} y: {segment.points[0][1]:.1f}";
            label_color = (255, 255, 0, 255) if is_highlighted else MINIMAP_GRID_LABEL_COLOR
            try:
                text_surface=coord_label_font.render(label_text,True,label_color);
                dx=map_x + 5;
                dy=map_y;
                renderer._draw_text_texture(text_surface,dx,dy);
            except Exception as e:
                pass
            
                
                
    # --- 5. Draw Grid Labels Dynamically ---
    # (Logic copied from simulator overlay drawing part)
    show_labels = grid_label_font and view_range < DEFAULT_MINIMAP_RANGE * 4.5
    if show_labels:
        world_half_x=(widget_width/scale)/2.; world_half_z=(widget_height/scale)/2.
        world_l=view_center_x-world_half_x; world_r=view_center_x+world_half_x; world_b=view_center_z-world_half_z; world_t=view_center_z+world_half_z
        start_gx=math.floor(world_l/MINIMAP_GRID_SCALE)*MINIMAP_GRID_SCALE; start_gz=math.floor(world_b/MINIMAP_GRID_SCALE)*MINIMAP_GRID_SCALE
        current_gx=start_gx
        while current_gx <= world_r:
            widget_x,_ = _world_to_map_coords_adapted(current_gx, view_center_z, view_center_x, view_center_z, widget_center_x_screen, widget_center_y_screen, scale)
            if 0<=widget_x<=widget_width:
                label_text=f"{current_gx:.0f}";
                try:
                    text_surface=grid_label_font.render(label_text,True,MINIMAP_GRID_LABEL_COLOR);
                    dx=widget_x-text_surface.get_width()/2;
                    dy=MINIMAP_GRID_LABEL_OFFSET;
                    renderer._draw_text_texture(text_surface,dx,dy);
                except Exception as e:
                    pass
            current_gx += MINIMAP_GRID_SCALE
        current_gz=start_gz
        while current_gz <= world_t:
            _,widget_y = _world_to_map_coords_adapted(view_center_x, current_gz, view_center_x, view_center_z, widget_center_x_screen, widget_center_y_screen, scale)
            if 0<=widget_y<=widget_height:
                label_text=f"{current_gz:.0f}";
                try:
                    text_surface=grid_label_font.render(label_text,True,MINIMAP_GRID_LABEL_COLOR);
                    dx=MINIMAP_GRID_LABEL_OFFSET;
                    dy=widget_y-text_surface.get_height()/2;
                    renderer._draw_text_texture(text_surface,dx,dy);
                except Exception as e:
                    pass
            current_gz += MINIMAP_GRID_SCALE


# --- Simulator Zoom Control (Keep) ---
def zoom_simulator_minimap(factor):
    global current_simulator_minimap_range
    new_range = current_simulator_minimap_range * factor
    current_simulator_minimap_range = max(MINIMAP_MIN_RANGE, min(MINIMAP_MAX_RANGE, new_range))
    print(f"Simulator minimap range set to: {current_simulator_minimap_range:.1f}")

# --- Cleanup Functions ---
def _cleanup_bake_resources():
    """Cleans up only the FBO and baked texture."""
    global composite_fbo, composite_map_texture_id, original_bg_texture_id_bake
    if composite_fbo:
        try: glBindFramebuffer(GL_FRAMEBUFFER, 0); glDeleteFramebuffers(1, [composite_fbo]);
        except Exception as e: print(f"Warn: Error deleting FBO: {e}")
        composite_fbo = None
    if composite_map_texture_id:
        try:
            if glIsTexture(composite_map_texture_id): glDeleteTextures(1, [composite_map_texture_id])
        except Exception as e: print(f"Warn: Error deleting baked texture: {e}")
        composite_map_texture_id = None
    if original_bg_texture_id_bake: # Should be cleaned in bake, but safety check
         try:
             if glIsTexture(original_bg_texture_id_bake): glDeleteTextures(1, [original_bg_texture_id_bake])
         except Exception as e: print(f"Warn: Error deleting bake BG texture in cleanup: {e}")
         original_bg_texture_id_bake = None

def cleanup_minimap_renderer():
    """Cleans up ALL resources (baked FBO/tex + editor dynamic tex)."""
    global editor_bg_texture_id, editor_current_map_filename
    print("清理小地圖渲染器資源 (Baked + Editor)...")
    _cleanup_bake_resources() # Clean up baked stuff

    # Clean up editor's dynamic background texture
    if editor_bg_texture_id:
        try:
            if glIsTexture(editor_bg_texture_id): glDeleteTextures(1, [editor_bg_texture_id])
        except Exception as e: print(f"Warn: Error deleting editor BG texture: {e}")
        editor_bg_texture_id = None
    editor_current_map_filename = None
    print("小地圖渲染器資源已清理。")

# --- Initialization (Keep placeholder) ---
def init_minimap_renderer():
    pass