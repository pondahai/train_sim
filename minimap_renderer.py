# minimap_renderer.py
import pygame
from OpenGL.GL import *
from OpenGL.GLU import *
from scipy.spatial import ConvexHull
import numpy as np
import numpy as math # Keep consistent
import os
# --- 新增：導入 Pillow ---
from PIL import Image
Image.MAX_IMAGE_PIXELS = None # 移除限制
# ------------------------

# --- Import shared modules/constants ---
from scene_parser import Scene
from tram import Tram
import renderer # Needed for colors, sizes, grid constants, _draw_text_texture, 
# Import texture loader directly for editor preview background loading
import texture_loader
from track import TRACK_WIDTH, TrackSegment # --- MODIFICATION: Import TrackSegment for type hinting if needed ---

from numba import jit, njit # Keep numba imports

# --- Minimap Constants ---
# Constants for Simulator
MINIMAP_SIZE = 300
MINIMAP_PADDING = 10
DEFAULT_MINIMAP_RANGE = 200.0
MINIMAP_MIN_RANGE = 10.0
MINIMAP_MAX_RANGE = 5000.0
MINIMAP_ZOOM_FACTOR = 1.1
MINIMAP_PLAYER_COLOR = (1.0, 0.0, 0.0)
MINIMAP_PLAYER_SIZE = 12
# Constants for Editor Preview (mostly shared, some might differ)
EDITOR_BG_COLOR = (0.85, 0.85, 0.88, 1.0) # Editor preview BG fallback if no map texture
# Constants used by BOTH (Simulator Overlay & Editor Dynamic Draw)
MINIMAP_TRACK_COLOR = (1.0, 0.0, 0.0)
MINIMAP_BRANCH_TRACK_COLOR = (1.0, 0.5, 0.0)
MINIMAP_GRID_SCALE = 50.0
MINIMAP_GRID_LABEL_COLOR = (255, 155, 0, 0.1)
# MINIMAP_GRID_LABEL_FONT_SIZE = 24
MINIMAP_GRID_LABEL_OFFSET = 2
#
# MINIMAP_COORD_LABEL_FONT_SZIE = 12
# Constants for Dynamic Drawing (Editor Preview - matching original renderer)
MINIMAP_DYNAMIC_GRID_COLOR = (0.5, 0.5, 0.5, 0.3) # Color for editor grid lines
MINIMAP_DYNAMIC_BUILDING_COLOR = (0.6, 0.4, 0.9) # Editor building lines
MINIMAP_DYNAMIC_BUILDING_LABEL_COLOR = tuple(c * 255 for c in MINIMAP_DYNAMIC_BUILDING_COLOR) + (30,)
MINIMAP_DYNAMIC_CYLINDER_COLOR = (0.5, 0.9, 0.5) # Editor cylinder lines/circles
MINIMAP_DYNAMIC_CYLINDER_LABEL_COLOR = tuple(c * 255 for c in MINIMAP_DYNAMIC_CYLINDER_COLOR) + (180,)
MINIMAP_DYNAMIC_TREE_COLOR = (0.1, 0.8, 0.1) # Editor tree points

MINIMAP_DYNAMIC_SPHERE_COLOR = (0.9, 0.7, 0.2) # 範例顏色：橙色
MINIMAP_BAKE_SPHERE_COLOR = (*MINIMAP_DYNAMIC_SPHERE_COLOR[:3], 0.5) # 用於烘焙的半透明顏色
MINIMAP_DYNAMIC_SPHERE_LABEL_COLOR = tuple(c * 255 for c in MINIMAP_DYNAMIC_SPHERE_COLOR) + (180,) # 標籤顏色

# 
MINIMAP_DYNAMIC_HILL_COLOR = (0.6, 0.45, 0.3) # 示例：棕色 (用於編輯器中心點和輪廓)
MINIMAP_DYNAMIC_HILL_LABEL_COLOR = tuple(c * 255 for c in MINIMAP_DYNAMIC_HILL_COLOR) + (180,) # 編輯器標籤顏色
MINIMAP_BAKE_HILL_COLOR = (*MINIMAP_DYNAMIC_HILL_COLOR[:3], 0.6) # 用於烘焙的半透明棕色 (基底輪廓)
MINIMAP_HIGHLIGHT_HILL_COLOR = (1.0, 1.0, 0.0) # 示例：高亮黃色
MINIMAP_HIGHLIGHT_HILL_LABEL_COLOR = (255, 255, 0, 255) # 高亮標籤顏色

# Constants for FBO Baking
MINIMAP_BG_FALLBACK_COLOR = (0.2, 0.2, 0.2, 0.7) # Simulator fallback BG
MINIMAP_BAKE_GRID_COLOR = MINIMAP_DYNAMIC_GRID_COLOR # Use same color for baked grid
MINIMAP_BAKE_BUILDING_COLOR = (*MINIMAP_DYNAMIC_BUILDING_COLOR[:3], 0.5) # Use alpha for bake
MINIMAP_BAKE_CYLINDER_COLOR = (*MINIMAP_DYNAMIC_CYLINDER_COLOR[:3], 0.5)
MINIMAP_BAKE_TREE_COLOR = (*MINIMAP_DYNAMIC_TREE_COLOR[:3], 1.0)
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


def _calculate_y_x_z_intrinsic_rotation_matrix(rx_deg, ry_deg, rz_deg):
    rx_rad, ry_rad, rz_rad = math.radians(rx_deg), math.radians(ry_deg), math.radians(rz_deg)
    
    cos_rx, sin_rx = math.cos(rx_rad), math.sin(rx_rad)
    cos_ry, sin_ry = math.cos(ry_rad), math.sin(ry_rad)
    cos_rz, sin_rz = math.cos(rz_rad), math.sin(rz_rad)

    # 旋轉矩陣 M_y (繞Y軸)
    m_y = np.array([
        [cos_ry,  0, sin_ry],
        [0,       1,      0],
        [-sin_ry, 0, cos_ry]
    ])
    
    # 旋轉矩陣 M_x (繞X軸)
    m_x = np.array([
        [1,      0,       0],
        [0, cos_rx, -sin_rx],
        [0, sin_rx,  cos_rx]
    ])
    
    # 旋轉矩陣 M_z (繞Z軸)
    m_z = np.array([
        [cos_rz, -sin_rz, 0],
        [sin_rz,  cos_rz, 0],
        [0,            0, 1]
    ])
    
    # 複合旋轉矩陣 M = M_y * M_x * M_z
    # (NumPy的 @ 符號用於矩陣乘法，np.dot也可以)
    composite_matrix = m_y @ m_x @ m_z
    return composite_matrix

# --- 凸包計算函數 (使用 SciPy) ---
def calculate_2d_convex_hull(points_xz: list) -> list:
    """
    計算2D點集的凸包，使用 scipy.spatial.ConvexHull。
    返回構成凸包的頂點列表 (按順時針或逆時針順序，由ConvexHull決定)。
    Args:
        points_xz: 一個包含 (x, z) 元組或 NumPy 數組的列表。
    Returns:
        一個包含 (x, z) 元組的列表，代表凸包的頂點。
        如果點數少於3或計算失敗，則返回簡化的結果或原始點。
    """
    num_points = len(points_xz)
    if num_points < 3:
        # print(f"DEBUG: ConvexHull - Input points < 3 ({num_points}), returning as is: {points_xz}")
        return list(points_xz) # 點少於3個，它們自身就是凸包 (或線段/點)

    try:
        points_array = np.asarray(points_xz) # ConvexHull 需要 NumPy 數組
        
        if points_array.shape[0] < 3: # 再次檢查轉換後的點數 (例如去重後)
            # print(f"DEBUG: ConvexHull - Points array has < 3 unique points after asarray, returning as is: {points_array.tolist()}")
            return points_array.tolist()

        hull = ConvexHull(points_array)
        # hull.vertices 是構成凸包的點在 points_array 中的索引
        convex_hull_vertex_list = [tuple(points_array[i]) for i in hull.vertices]
        # print(f"DEBUG: ConvexHull - Calculated hull: {convex_hull_vertex_list}")
        return convex_hull_vertex_list
            
    except Exception as e: # 通常是 scipy.spatial.qhull.QhullError
        print(f"警告: 使用 SciPy 計算凸包時出錯: {e}")
        print(f"DEBUG: ConvexHull - Failed for input points: {points_xz}")
        # Fallback 策略：返回這些點的軸對齊外包框 (AABB)
        if points_xz: 
            min_x = min(p[0] for p in points_xz)
            max_x = max(p[0] for p in points_xz)
            min_z = min(p[1] for p in points_xz)
            max_z = max(p[1] for p in points_xz)
            # print(f"DEBUG: ConvexHull - Fallback to AABB: [({min_x},{min_z}), ({max_x},{min_z}), ({max_x},{max_z}), ({min_x},{max_z})]")
            return [(min_x, min_z), (max_x, min_z), (max_x, max_z), (min_x, max_z)]
        return [] 
# --- 結束凸包計算函數 ---

# --- 輔助函數：計算旋轉後長方體的8個世界空間角點 --- 錨點是底部中心)
def get_world_space_corners_of_building(
    wx_bottom_center, wy_bottom_center, wz_bottom_center, 
    width, height, depth, 
    rx_deg, ry_deg, rz_deg
):
    half_w, half_d = width / 2.0, depth / 2.0
    
    # 局部角點，相對於底部中心 (0,0,0)
    # Y 的範圍是 [0, height]
    local_corners_from_bottom = [
        np.array([-half_w, 0,      -half_d]), np.array([ half_w, 0,      -half_d]),
        np.array([ half_w, height, -half_d]), np.array([-half_w, height, -half_d]), # 上面4個點的Y是height
        np.array([-half_w, 0,       half_d]), np.array([ half_w, 0,       half_d]),
        np.array([ half_w, height,  half_d]), np.array([-half_w, height,  half_d]),
    ]

    # --- 使用新的旋轉矩陣方法 ---
    # 注意：這裡的 rx_deg, ry_deg, rz_deg 應該是你在 renderer.py 中
    # 傳遞給 glRotatef 的那三個角度。
    # 如果你之前在調用 get_convex_hull_projection_for_building 時對 rx 和 rz 取反了，
    # 那麼在調用 _calculate_y_x_z_intrinsic_rotation_matrix 時也可能需要。
    # 但是，我們的目標是讓這個函數的 rx,ry,rz 與 glRotatef 的 rx,ry,rz 語義完全一致。
    
    # 所以，先假設 rx_deg, ry_deg, rz_deg 就是直接從 scene_parser 來的原始值
    # （或者已經補償了小地圖投影鏡像的值，如果需要的話）
    rotation_matrix = _calculate_y_x_z_intrinsic_rotation_matrix(rx_deg, ry_deg, rz_deg)

    world_corners_list = []
    for lc_offset in local_corners_from_bottom:
#         rotated_offset = _rotate_point_3d(lc_offset, rx_deg, ry_deg, rz_deg)
        rotated_offset = np.dot(rotation_matrix, lc_offset) # 應用複合旋轉矩陣
        world_corners_list.append(
            np.array([wx_bottom_center + rotated_offset[0], 
                      wy_bottom_center + rotated_offset[1], 
                      wz_bottom_center + rotated_offset[2]])
        )
    return world_corners_list

# --- 輔助函數：計算凸包投影 (使用SciPy) ---
def get_convex_hull_projection_for_building(
    wx, wy, wz, width, height, depth, rx_deg, ry_deg, rz_deg
) -> list:
    world_corners_3d = get_world_space_corners_of_building( # 確保這個函數已定義
        wx, wy, wz, width, height, depth, rx_deg, ry_deg, rz_deg
    )
    points_xz_projection = [(corner[0], corner[2]) for corner in world_corners_3d]
    hull_points_xz = calculate_2d_convex_hull(points_xz_projection) # <--- 調用在這裡
    return hull_points_xz

# --- 新增：Gableroof 的世界空間角點計算 ---
def get_world_space_outline_points_of_gableroof(
    wx, wy, wz,                     # 屋頂基準點的世界座標
    world_rx, world_ry, world_rz,   # 屋頂的世界旋轉角度 (度)
    base_width, base_length, 
    ridge_height_offset, 
    ridge_x_pos_offset, 
    eave_overhang_x, eave_overhang_z
):
    """
    計算 gableroof 的關鍵外部輪廓點（屋簷角點、屋脊端點）在世界空間中的3D座標。
    這些點將用於後續的XZ投影和凸包計算。
    局部座標系：Y=0 在屋簷平面，屋頂中心在 XZ 平面的 (0,0)。
    """
    e_y_local = 0.0 # 屋簷在局部Y=0
    r_y_local = ridge_height_offset # 屋脊相對於屋簷的高度
    r_x_local = ridge_x_pos_offset  # 屋脊X偏移

    hw = base_width / 2.0
    hl = base_length / 2.0

    # 考慮懸挑的屋簷X, Z邊界
    final_eave_lx = -hw - eave_overhang_x
    final_eave_rx =  hw + eave_overhang_x
    final_eave_fz = -hl - eave_overhang_z
    final_eave_bz =  hl + eave_overhang_z
    
    # 計算懸挑後屋簷點的Y座標 (沿斜面延伸)
    y_at_eave_lx = e_y_local
    dx_slope_left = r_x_local - (-hw) 
    if not math.isclose(dx_slope_left, 0):
        slope_y_per_x_left = (r_y_local - e_y_local) / dx_slope_left
        y_at_eave_lx = e_y_local - (eave_overhang_x * slope_y_per_x_left)

    y_at_eave_rx = e_y_local
    dx_slope_right = hw - r_x_local
    if not math.isclose(dx_slope_right, 0):
        slope_y_per_x_right = (r_y_local - e_y_local) / dx_slope_right
        y_at_eave_rx = e_y_local - (eave_overhang_x * slope_y_per_x_right)

    # 定義屋頂的6個關鍵局部輪廓點 (相對於其局部原點 (0, e_y_local, 0))
    # 這些點的Y座標是相對於屋頂的局部原點的 (即 glTranslatef(wx,wy,wz) 之後的Y)
    # wx, wy, wz 是外部傳入的屋頂基準點
    # 我們假設 wy 是屋簷的Y座標，所以 e_y_local 是0
    local_outline_points = [
        np.array([final_eave_lx, y_at_eave_lx, final_eave_fz]), # 前左屋簷
        np.array([final_eave_rx, y_at_eave_rx, final_eave_fz]), # 前右屋簷
        np.array([final_eave_lx, y_at_eave_lx, final_eave_bz]), # 後左屋簷
        np.array([final_eave_rx, y_at_eave_rx, final_eave_bz]), # 後右屋簷
        np.array([r_x_local,     r_y_local,    final_eave_fz]), # 前屋脊點
        np.array([r_x_local,     r_y_local,    final_eave_bz])  # 後屋脊點
    ]
    
    # 應用旋轉，並轉換到世界座標
    rotation_matrix = _calculate_y_x_z_intrinsic_rotation_matrix(world_rx, world_ry, world_rz)
    world_outline_points = []
    for lp in local_outline_points:
        rotated_lp_offset = np.dot(rotation_matrix, lp)
        world_outline_points.append(
            np.array([wx + rotated_lp_offset[0],
                      wy + rotated_lp_offset[1], # wy 是基準點Y
                      wz + rotated_lp_offset[2]])
        )
    return world_outline_points

# --- 新增：Gableroof 的凸包投影計算 ---
def get_convex_hull_projection_for_gableroof(
    wx, wy, wz, world_rx, world_ry, world_rz,
    base_w, base_l, ridge_h_off, 
    ridge_x_pos, eave_over_x, eave_over_z
) -> list:
    world_outline_points_3d = get_world_space_outline_points_of_gableroof( # 確保這個函數已定義
        wx, wy, wz, world_rx, world_ry, world_rz,
        base_w, base_l, ridge_h_off, 
        ridge_x_pos, eave_over_x, eave_over_z
    )
    points_xz_projection = [(p[0], p[2]) for p in world_outline_points_3d]
    hull_points_xz = calculate_2d_convex_hull(points_xz_projection) # <--- 調用在這裡
    return hull_points_xz

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

    # --- START OF MODIFICATION: Add Track rendering to FBO bake ---
    if scene and scene.track:
        
        glLineWidth(1.0) # Thinner lines for baked track

        for segment in scene.track.segments:
            # Draw main segment points
            if segment.points and len(segment.points) >= 2:
                glColor3fv(MINIMAP_TRACK_COLOR) # Use the defined track color
                glBegin(GL_LINE_STRIP)
                for point_world in segment.points:
                    map_x, map_y = _world_to_fbo_coords(point_world[0], point_world[2], world_cx, world_cz, world_w, world_h, fbo_w, fbo_h)
                    glVertex2f(map_x, map_y)
                glEnd()
            
            # Draw visual branches of the segment
            if hasattr(segment, 'visual_branches') and segment.visual_branches:
                glColor3fv(MINIMAP_BRANCH_TRACK_COLOR) # Use the defined track color
                for branch_def in segment.visual_branches:
                    if branch_def.get('points') and len(branch_def['points']) >= 2:
                        glBegin(GL_LINE_STRIP)
                        for point_world_branch in branch_def['points']:
                            map_x_b, map_y_b = _world_to_fbo_coords(point_world_branch[0], point_world_branch[2], world_cx, world_cz, world_w, world_h, fbo_w, fbo_h)
                            glVertex2f(map_x_b, map_y_b)
                        glEnd()
    # --- END OF MODIFICATION ---


    # Buildings (Filled Quads)
    glColor4fv(MINIMAP_BAKE_BUILDING_COLOR)
    if hasattr(scene, 'buildings'): # 檢查是否存在 buildings 列表
        for item in scene.buildings:
            # 假設 item 的結構是 (line_identifier, bldg_data_tuple)
            # bldg_data_tuple 的結構是 (obj_type, wx, wy, wz, rx_d, ry_d, rz_d, ww, wd, wh, ...)
            # 你需要根據你 scene_parser.py 中 building 的 obj_data_tuple 結構來正確解包
            line_identifier, bldg_data_tuple = item 
            try:
                # 假設核心幾何和旋轉參數在 bldg_data_tuple 的前面部分
                # obj_type = bldg_data_tuple[0]
                wx, wy, wz = bldg_data_tuple[1:4]
                rx_d, ry_d, rz_d = bldg_data_tuple[4:7] # 世界旋轉角度
                ww, wd, wh = bldg_data_tuple[7:10]   # 總尺寸
            except (IndexError, TypeError, ValueError) as e_unpack:
                print(f"警告 FBO: 解包 building 數據 (行: {line_identifier}) 失敗: {e_unpack}")
                print(f"DEBUG FBO: Building data tuple was: {bldg_data_tuple}")
                continue

            # 使用新的輔助函數獲取凸包的XZ投影頂點 (世界座標)
            hull_vertices_world_xz = get_convex_hull_projection_for_building(
                wx, wy, wz, ww, wh, wd, # 傳遞 building 的總尺寸 (注意 height 是 wh, depth 是 wd)
                rx_d, ry_d, rz_d        # 傳遞 building 的世界旋轉角度
            )
            
            if hull_vertices_world_xz and len(hull_vertices_world_xz) >= 3:
                fbo_poly_coords = []
                for corner_world_xz in hull_vertices_world_xz:
                    map_x, map_y = _world_to_fbo_coords(
                        corner_world_xz[0], corner_world_xz[1], 
                        world_cx, world_cz, world_w, world_h, fbo_w, fbo_h # FBO 相關參數
                    )
                    fbo_poly_coords.append((map_x, map_y))
                
                # 繪製填充多邊形
                glBegin(GL_POLYGON) # 用 GL_POLYGON 處理任意頂點數的凸多邊形
                for mx, my in fbo_poly_coords:
                    glVertex2f(mx, my)
                glEnd()
                
#         line_num, bldg = item
#         b_type, wx, wy, wz, rx, abs_ry, rz, ww, wd, wh, tid, *_ = bldg;
#         half_w, half_d = ww/2.0, wd/2.0
#         corners_local = [np.array([-half_w,0,-half_d]), np.array([half_w,0,-half_d]), np.array([half_w,0,half_d]), np.array([-half_w,0,half_d])]
#         angle_y_rad = math.radians(-abs_ry);
#         cos_y, sin_y = math.cos(angle_y_rad), math.sin(angle_y_rad)
#         fbo_coords = []
#         for corner in corners_local:
#             rotated_x = corner[0]*cos_y - corner[2]*sin_y; rotated_z = corner[0]*sin_y + corner[2]*cos_y
#             world_corner_x = wx + rotated_x; world_corner_z = wz + rotated_z
#             map_x, map_y = _world_to_fbo_coords(world_corner_x, world_corner_z, world_cx, world_cz, world_w, world_h, fbo_w, fbo_h)
#             fbo_coords.append((map_x, map_y))
#         if len(fbo_coords)==4:
#             glBegin(GL_QUADS); #GL_LINE_LOOP
#             [glVertex2f(mx, my) for mx, my in fbo_coords];
#             glEnd()

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
        obj_type, tx, ty, tz, th, _tex_id, _tex_file, *rest= tree; fbo_x, fbo_y = _world_to_fbo_coords(tx, tz, world_cx, world_cz, world_w, world_h, fbo_w, fbo_h)
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

    # --- Bake Hills (Base Outline Circles) ---
    glColor4fv(MINIMAP_BAKE_HILL_COLOR) # 使用半透明的烘焙顏色
    glLineWidth(1.5) # 可以稍微加粗一點輪廓線
    num_circle_segments_bake = 24 # 烘焙時可以用稍高精度

    for item in scene.hills:
        line_num, hill_data = item
        try:
            obj_type, cx, _base_y, cz, radius, _peak_h_offset, *_ = hill_data # 只需要中心和半徑
        except ValueError:
             # print(f"警告: 解包 hill 數據 (FBO烘焙) 時出錯 (來源行: {line_num})") # 可選警告
             continue

        # 計算中心點和半徑在 FBO 像素座標系的值
        center_fbo_x, center_fbo_y = _world_to_fbo_coords(cx, cz, world_cx, world_cz, world_w, world_h, fbo_w, fbo_h)
        # 半徑需要乘以 FBO 像素/世界單位 比例 (假設 FBO 的 X/Y 比例相同)
        radius_px = radius * (fbo_w / world_w) # 使用寬度比例

        if radius_px > 0.5: # 簡單剔除太小的圓
            glBegin(GL_LINE_LOOP) # Draw each hill's outline as a separate loop
            # 繪製圓形線圈
            for i in range(num_circle_segments_bake): # 不需要 +1，因為是 LINE_LOOP
                angle = 2 * math.pi * i / num_circle_segments_bake
                glVertex2f(center_fbo_x + radius_px * math.cos(angle),
                           center_fbo_y + radius_px * math.sin(angle))
            glEnd() # 結束所有山丘輪廓的繪製
    glLineWidth(1.0) # 恢復默認線寬

    # --- Bake Gableroofs (as simple rectangles) ---
    if hasattr(scene, 'gableroofs'):
        glColor4fv(MINIMAP_BAKE_BUILDING_COLOR) # 假設與建築物類似

        for item in scene.gableroofs:
            line_identifier, roof_data = item
            try:
                # 解包 gableroof_data_tuple (與 scene_parser.py 一致)
                # obj_type, (world_x, world_y, world_z, abs_rx, abs_ry, abs_rz,  <-- 0-6
                #  base_w, base_l, ridge_h_off,                       <-- 7-9
                #  ridge_x_pos, eave_over_x, eave_over_z,             <-- 10-12
                #  gl_tex_id, tex_has_alpha, tex_f_orig                 <-- 13-15)
                wx, wy, wz, rx_d, ry_d, rz_d = roof_data[1:7]
                base_w, base_l, ridge_h_off = roof_data[7:10]
                ridge_x_pos_offset = roof_data[10]
                eave_overhang_x = roof_data[11]
                eave_overhang_z = roof_data[12]
            except (IndexError, ValueError):
                # print(f"警告: 解包 gableroof 數據 (FBO烘焙) 時出錯 (行: {line_identifier})")
                continue

            hull_vertices_world_xz = get_convex_hull_projection_for_gableroof(
                wx, wy, wz, rx_d, ry_d, rz_d,
                base_w, base_l, ridge_h_off,
                ridge_x_pos_offset, eave_overhang_x, eave_overhang_z
            )
            
            if hull_vertices_world_xz and len(hull_vertices_world_xz) >= 3:
                fbo_poly_coords = []
                for corner_world_xz in hull_vertices_world_xz:
                    map_x, map_y = _world_to_fbo_coords(corner_world_xz[0], corner_world_xz[1], 
                                                        world_cx, world_cz, world_w, world_h, fbo_w, fbo_h)
                    fbo_poly_coords.append((map_x, map_y))
                
                glBegin(GL_POLYGON)
                for mx, my in fbo_poly_coords: glVertex2f(mx, my)
                glEnd()

            # --- 屋脊線的烘焙 (也需要完整3D旋轉) ---
            # 屋脊線的局部端點 (Y是相對於屋簷的 ridge_h_off)
            # 局部座標系 Y=0 在屋簷
            ridge_local_start = np.array([ridge_x_pos_offset, ridge_h_off, -base_l/2.0 - eave_overhang_z])
            ridge_local_end   = np.array([ridge_x_pos_offset, ridge_h_off,  base_l/2.0 + eave_overhang_z])

            rotation_matrix_ridge = _calculate_y_x_z_intrinsic_rotation_matrix(rx_d, ry_d, rz_d)
            
            rotated_ridge_start_offset = np.dot(rotation_matrix_ridge, ridge_local_start)
            world_ridge_start_x = wx + rotated_ridge_start_offset[0]
            world_ridge_start_z = wz + rotated_ridge_start_offset[2]
            map_rs_x, map_rs_y = _world_to_fbo_coords(world_ridge_start_x, world_ridge_start_z, 
                                                      world_cx, world_cz, world_w, world_h, fbo_w, fbo_h)

            rotated_ridge_end_offset = np.dot(rotation_matrix_ridge, ridge_local_end)
            world_ridge_end_x = wx + rotated_ridge_end_offset[0]
            world_ridge_end_z = wz + rotated_ridge_end_offset[2]
            map_re_x, map_re_y = _world_to_fbo_coords(world_ridge_end_x, world_ridge_end_z,
                                                      world_cx, world_cz, world_w, world_h, fbo_w, fbo_h)

            ridge_color_bake = (MINIMAP_BAKE_GRID_COLOR[0]*0.7, MINIMAP_BAKE_GRID_COLOR[1]*0.7, MINIMAP_BAKE_GRID_COLOR[2]*0.7, 0.8)
            glColor4fv(ridge_color_bake)
            glPushAttrib(GL_LINE_BIT); glEnable(GL_LINE_STIPPLE); glLineStipple(2, 0xAAAA); glLineWidth(1.0)
            glBegin(GL_LINES); glVertex2f(map_rs_x, map_rs_y); glVertex2f(map_re_x, map_re_y); glEnd()
            glDisable(GL_LINE_STIPPLE); glPopAttrib()
            # --- 結束屋脊線烘焙 ---
                
        # --- 結束烘焙 Gableroofs ---

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


def circle_intersects_aabb(circle_wx, circle_wz, circle_radius, 
                           aabb_min_x, aabb_max_x, aabb_min_z, aabb_max_z):
    # 找到AABB上離圓心最近的點的X座標
    closest_x = max(aabb_min_x, min(circle_wx, aabb_max_x))
    # 找到AABB上離圓心最近的點的Z座標
    closest_z = max(aabb_min_z, min(circle_wz, aabb_max_z))

    # 計算該最近點與圓心的距離的平方
    distance_squared = (circle_wx - closest_x)**2 + (circle_wz - closest_z)**2
    
    # 如果距離的平方小於等於半徑的平方，則相交
    return distance_squared <= (circle_radius**2)

# --- Editor Runtime Drawing (DYNAMIC RENDERING RESTORED) ---
def draw_editor_preview(scene: Scene, view_center_x, view_center_z, view_range, widget_width, widget_height,
                        is_dragging,
                        highlight_line_nums: set = set(),
                        line_to_focus_on: int = -1,
                        f7_tuning_target_line_num: int = -1):
    """ Draws the EDITOR minimap preview using DYNAMIC rendering (like original). """
    global editor_bg_texture_id, editor_bg_width_px, editor_bg_height_px, editor_current_map_filename
#     print(f"draw_editor_preview -> highlight_line_nums:{highlight_line_nums}, line_to_focus_on:{line_to_focus_on}")


    focused_element_world_x, focused_element_world_z = None, None
    # --- 步驟1：如果 line_to_focus_on 有效，則遍歷場景物件查找匹配項 --- line_to_focus_on 從每個物件裡面提取到這邊
    if scene and line_to_focus_on != -1: # 通常 line_to_focus_on > 0，但用 != -1 更通用
#         print(f"DEBUG Focus Scan: Attempting to find object for line_to_focus_on = {line_to_focus_on}")
        
        # 定義一個內部輔助函數來從 data_tuple 中提取 wx, wz
        def get_wx_wz_from_data(obj_data_tuple):
#             print(f"get_wx_wz_from_data->obj_data_tuple:{obj_data_tuple}")
            if not obj_data_tuple or not isinstance(obj_data_tuple, tuple) or len(obj_data_tuple) == 0:
                return None, None

            obj_type = obj_data_tuple[0] # 獲取物件類型字符串

            # 根據你的 scene_parser.py 中 obj_data_tuple 的實際結構來解包
            # 這些索引需要與 scene_parser.py 中的打包順序完全一致
            try:
                if obj_type == "building":
                    # (type, wx,wy,wz, rx,ry,rz, w,d,h, uO,vO,tA,uvM,uS,vS, texF,texID,texAlpha)
                    return obj_data_tuple[1], obj_data_tuple[3] # wx, wz
                elif obj_type == "gableroof":
                    # (wx,wy,wz, rx,ry,rz, base_w,base_l,ridge_h, ridge_x,eave_x,eave_z, texID,texAlpha,texF)
                    return obj_data_tuple[1], obj_data_tuple[3] # wx, wz (注意：gableroof 的元組第一個不是類型)
                                                                # 修正：假設 gableroof 的 data_tuple 也以類型開頭，
                                                                # 或者我們在 scene_parser 中統一所有物件 data_tuple 的前幾個元素
                                                                # 為了與 building 一致，假設 gableroof 的 obj_data_tuple 也是：
                                                                # ("gableroof", wx, wy, wz, ...)
                elif obj_type == "cylinder":
                    # (type, wx,wy,wz, rx,ry,rz, cr,ch, uO,vO,tA,uvM,uS,vS, texF,texID,texAlpha)
                    return obj_data_tuple[1], obj_data_tuple[3] # wx, wz
                elif obj_type == "sphere":
                    # (type, wx,wy,wz, rx,ry,rz, cr, texID,uO,vO,tA,uvM,uS,vS, texF,texAlpha)
                    return obj_data_tuple[1], obj_data_tuple[3] # wx, wz
                elif obj_type == "hill": # Hill 的 data_tuple 結構不同
                    # (cx, base_y, cz, radius, peak_h_offset, texID, uS,vS, texF, texAlpha)
                    # Hill 的中心是 cx, cz
                    return obj_data_tuple[1], obj_data_tuple[3] # cx, cz
                elif obj_type == "tree": # Tree 的 data_tuple 結構也不同
                    # (wx, wy, wz, height, tex_id, tex_file)
                    return obj_data_tuple[1], obj_data_tuple[3] # wx, wz
                # 可添加其他物件類型
            except (IndexError, TypeError):
                # print(f"DEBUG Focus Scan: Error unpacking wx, wz for type {obj_type} from data: {obj_data_tuple}")
                return None, None
            return None, None # 未知類型

        # 包含所有可能包含可定位物件的列表的列表
        all_object_lists = []
        if hasattr(scene, 'buildings'): all_object_lists.append(scene.buildings)
        if hasattr(scene, 'gableroofs'): all_object_lists.append(scene.gableroofs)
        if hasattr(scene, 'cylinders'): all_object_lists.append(scene.cylinders)
        if hasattr(scene, 'spheres'): all_object_lists.append(scene.spheres)
        if hasattr(scene, 'hills'): all_object_lists.append(scene.hills)
        if hasattr(scene, 'trees'): all_object_lists.append(scene.trees)
        # 如果軌道段 TrackSegment 的 source_line_number 也是你 line_to_focus_on 的目標，
        # 則也需要遍歷 scene.track.segments

        target_found_in_scan = False
        for object_list in all_object_lists:
            if target_found_in_scan: break # 如果已找到，跳出最外層循環
            for item in object_list:
                line_identifier, data_tuple = item # 解包行號標識和數據元組
                
                # 進行行號比較
                # 注意：如果 line_identifier 是 "檔名:行號" 字串，而 line_to_focus_on 是整數，
                # 這裡的比較需要更複雜的邏輯，或者 line_to_focus_on 就應該是那個字串。
                # 我們目前的折衷方案是，line_identifier 對於根場景物件是整數。
                if line_identifier == line_to_focus_on:
#                     print(f"line_to_focus_on:{line_to_focus_on}")
#                     print(f"data_tuple:{data_tuple}")
                    obj_wx, obj_wz = get_wx_wz_from_data(data_tuple)
                    if obj_wx is not None and obj_wz is not None:
                        focused_element_world_x = obj_wx
                        focused_element_world_z = obj_wz
                        target_found_in_scan = True
#                         print(f"DEBUG Focus Scan: Object for line {line_to_focus_on} FOUND at ({obj_wx:.1f}, {obj_wz:.1f}). Type: {data_tuple[0] if data_tuple else 'Unknown'}")
                        break # 跳出內層循環 (遍歷當前物件列表)
                    else:
                        print(f"DEBUG Focus Scan: Matched line {line_to_focus_on} but could not extract wx, wz from data: {data_tuple}")
        
        if not target_found_in_scan:
            print(f"DEBUG Focus Scan: No object found for line_to_focus_on = {line_to_focus_on}")
    # --- 結束步驟1 ---
    
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

    show_object_and_grid_labels = coord_label_font and grid_label_font and view_range < (DEFAULT_MINIMAP_RANGE * 3.0) 

    # 計算小地圖在世界座標系中的可視範圍 (AABB_viewport_world)
    world_half_render_width = (widget_width / scale) / 2.0
    world_half_render_height = (widget_height / scale) / 2.0 # 注意這是Z方向的範圍
    
    viewport_world_min_x = view_center_x - world_half_render_width
    viewport_world_max_x = view_center_x + world_half_render_width
    viewport_world_min_z = view_center_z - world_half_render_height
    viewport_world_max_z = view_center_z + world_half_render_height

    # --- 3. Draw Static Objects Dynamically ---
    # (Using logic from original _render_map_view)
    if scene:
        # Buildings (Line Loop of Convex Hull)
        if hasattr(scene, 'buildings'):
            for item in scene.buildings:
                line_identifier, bldg_data_tuple = item
                try:
                    # 與FBO中解包方式保持一致
                    obj_type, wx, wy, wz, rx_d, ry_d, rz_d, ww, wd, wh, \
                u_off, v_off, t_ang, uv_m, u_s, v_s, \
                tex_f, gl_id, tex_alpha, \
                parent_origin_ry_deg = bldg_data_tuple
                except (IndexError, TypeError, ValueError) as e_unpack_preview:
                    print(f"警告 Preview: 解包 building 數據 (行: {line_identifier}) 失敗: {e_unpack_preview}")
                    print(f"DEBUG Preview: Building data tuple was: {bldg_data_tuple}")
                    continue

                # --- 計算 building 的包圍圓半徑 (新方法) ---
                bldg_bounding_radius = max(ww, wh, wd) / 2.0
                if circle_intersects_aabb(wx, wz, bldg_bounding_radius,
                                          viewport_world_min_x, viewport_world_max_x,
                                          viewport_world_min_z, viewport_world_max_z):


                    glPushAttrib(GL_CURRENT_BIT | GL_LINE_BIT)
                    try:
                        is_highlighted = line_identifier in highlight_line_nums
                        is_also_f7_target = (f7_tuning_target_line_num != -1 and line_identifier == f7_tuning_target_line_num) # <--- 判斷是否為F7目標
#                         print(f"is_highlighted {is_highlighted}")
#                         print(f"is_also_f7_target {is_also_f7_target}")
                                
#                             if line_identifier == line_to_focus_on:
#                                 focused_element_world_x, focused_element_world_z = wx, wz
                        if is_highlighted or is_also_f7_target:

                            # --- 繪製局部軸線 (僅在高亮時) ---
                            # 需要物件的Y軸旋轉 ry_d (以及可能的 rx_d, rz_d 如果軸線也受其影響)
                            # 我們先只考慮Y軸旋轉對XZ平面軸線的影響
                            
                            # 軸線長度 (可以根據 scale 或物件尺寸調整)
                            axis_length_map = min(widget_width, widget_height) * 1.00 # 小地圖視窗尺寸的5%
                            # 或者一個固定的世界單位長度，然後再乘以 scale
                            # axis_world_length = max(ww, wd) * 0.3 # 物件最大邊的30%
                            # axis_length_map = axis_world_length * scale

                            # 物件的局部X軸在世界XZ平面上的方向 (考慮了Y軸旋轉)
                            # 局部X軸通常是 (1,0,0)。繞Y軸旋轉 ry_d 度後：
                            # world_ry_rad = math.radians(ry_d)
                            # local_x_axis_dir_x = math.cos(world_ry_rad)
                            # local_x_axis_dir_z = math.sin(world_ry_rad)
                            # 但我們的小地圖X軸是反的，Y軸旋轉是負的
                            angle_y_map_rad = math.radians(-parent_origin_ry_deg) # 與投影計算一致
                            
                            # 局部X軸 (1,0) 旋轉 angle_y_map_rad 後的方向 (在小地圖的XZ平面上)
                            map_local_x_dir_x = math.cos(angle_y_map_rad)
                            map_local_x_dir_z = math.sin(angle_y_map_rad)
                            
                            # 局部Z軸 (0,1) 旋轉 angle_y_map_rad 後的方向
                            map_local_z_dir_x = -math.sin(angle_y_map_rad) # cos(a+90) = -sin(a)
                            map_local_z_dir_z =  math.cos(angle_y_map_rad) # sin(a+90) = cos(a)

                            # 物件中心點在小地圖上的座標
                            center_map_x, center_map_y = _world_to_map_coords_adapted(
                                wx, wz, view_center_x, view_center_z,
                                widget_center_x_screen, widget_center_y_screen, scale
                            )

                            glLineWidth(2.0)
                            glBegin(GL_LINES)
                            # 軸的顏色
                            # 繪製X軸 (例如用稍亮的顏色，或與高亮色一致)
                            glColor3f(1.0, 0.5, 0.5) # 示例：粉紅色X軸
                            glVertex2f(center_map_x, center_map_y)
                            glVertex2f(center_map_x + map_local_x_dir_x * axis_length_map, 
                                       center_map_y + map_local_x_dir_z * axis_length_map)
                            
                            # 繪製Z軸 (例如用稍亮的顏色)
                            glColor3f(0.5, 1.0, 0.5) # 示例：淺綠色Z軸
                            glVertex2f(center_map_x, center_map_y)
                            glVertex2f(center_map_x + map_local_z_dir_x * axis_length_map, 
                                       center_map_y + map_local_z_dir_z * axis_length_map)
                            glEnd()
                            # --- 結束繪製局部軸線 ---
#                         else:
#                             glColor3fv(MINIMAP_DYNAMIC_BUILDING_COLOR); glLineWidth(2.0)

                        # 不同情況被選的顏色
                        if is_also_f7_target: # F7目標優先顯示紅色
#                             print("紅色")
                            glColor3f(1.0, 0.0, 0.0) # 紅色
                            glLineWidth(3.0) # 可以比普通高亮更粗一點
                        elif is_highlighted: # 普通高亮
#                             print("黃色")
                            glColor3f(1.0, 1.0, 0.0) # 黃色
                            glLineWidth(3.0)
                        else: # 非高亮
                            glColor3fv(MINIMAP_DYNAMIC_BUILDING_COLOR)
                            glLineWidth(2.0)

                        # 獲取凸包投影
                        hull_vertices_world_xz = get_convex_hull_projection_for_building(
                            wx, wy, wz, ww, wh, wd, rx_d, ry_d, rz_d
                        )

                        if hull_vertices_world_xz and len(hull_vertices_world_xz) >= 3:
                            map_poly_coords = []
                            for corner_world_xz in hull_vertices_world_xz:
                                map_x, map_y = _world_to_map_coords_adapted(
                                    corner_world_xz[0], corner_world_xz[1], 
                                    view_center_x, view_center_z, 
                                    widget_center_x_screen, widget_center_y_screen, scale
                                )
                                map_poly_coords.append((map_x, map_y))
                            
                            # 繪製線框多邊形
                            glBegin(GL_LINE_LOOP)
                            for mx, my in map_poly_coords:
                                glVertex2f(mx, my)
                            glEnd()
                            
                            # --- 標籤繪製 (使用凸包的點計算中心) ---
                            if map_poly_coords and not is_dragging: 
                                center_x_label = sum(p[0] for p in map_poly_coords) / len(map_poly_coords)
                                center_y_label = sum(p[1] for p in map_poly_coords) / len(map_poly_coords)
                                
                                label_prefix_text = ""
                                if isinstance(line_identifier, str) and ":" in line_identifier:
                                    label_prefix_text = line_identifier
                                elif isinstance(line_identifier, int):
                                    label_prefix_text = str(line_identifier)
                                else: label_prefix_text = "N/A"
                                label_text_content = f"{label_prefix_text}:{wy:.1f}"
                                label_color_actual = MINIMAP_GRID_LABEL_COLOR if is_highlighted else MINIMAP_DYNAMIC_BUILDING_LABEL_COLOR
                                
                                if show_object_and_grid_labels and coord_label_font:
                                    try:
                                        text_surface = coord_label_font.render(label_text_content, True, label_color_actual)
                                        dx = center_x_label + 2 # 示例偏移
                                        dy = center_y_label - text_surface.get_height() / 2 # 示例偏移
                                        renderer._draw_text_texture(text_surface, dx, dy)
                                    except Exception as e_label_bldg:
                                        pass 
                            # --- 結束標籤 ---
                    finally:
                        glPopAttrib()        
        # Buildings (Lines)
#         glColor3fv(MINIMAP_DYNAMIC_BUILDING_COLOR)
#         glLineWidth(2.0)
#         for item in scene.buildings:
#             line_num, bldg = item # 解包行號和數據元組
#             b_type, wx, wy, wz, rx, abs_ry, rz, ww, wd, wh, tid, *_ = bldg # 解包數據元組
#             
#             glPushAttrib(GL_CURRENT_BIT | GL_LINE_BIT) # 保存當前顏色狀態
#             try:
#                 if line_num in highlight_line_nums:
#                     glColor3f(1.0, 1.0, 0.0) # 高亮顏色 (黃色)
#                     glLineWidth(3.0) # 可以加粗線條
#                     if line_num == line_to_focus_on:
#                         focused_element_world_x = wx
#                         focused_element_world_z = wz                        
#                 else:
#                     glColor3fv(MINIMAP_DYNAMIC_BUILDING_COLOR)
#                     glLineWidth(2.0) # 正常線條寬度
#             
#                 half_w,half_d = ww/2.,wd/2.
#                 corners_local = [np.array([-half_w,0,-half_d]),np.array([half_w,0,-half_d]),np.array([half_w,0,half_d]),np.array([-half_w,0,half_d])]
#                 angle_y_rad = math.radians(-abs_ry);
#                 cos_y,sin_y = math.cos(angle_y_rad),math.sin(angle_y_rad)
#                 map_coords = []
#                 for corner in corners_local:
#                     rotated_x = corner[0]*cos_y - corner[2]*sin_y;
#                     rotated_z = corner[0]*sin_y + corner[2]*cos_y
#                     world_corner_x = wx + rotated_x;
#                     world_corner_z = wz + rotated_z
#                     map_x,map_y = _world_to_map_coords_adapted(world_corner_x, world_corner_z, view_center_x, view_center_z, widget_center_x_screen, widget_center_y_screen, scale)
#                     map_coords.append((map_x, map_y))
#                 if len(map_coords)==4:
#                     glBegin(GL_LINE_LOOP);
#                     [glVertex2f(mx,my) for mx,my in map_coords];
# #                     print("DEBUG: Before glEnd for Building loop")
#                     glEnd()
#                 
#                 # 求取矩形中心座標
#                 sum_x = sum(coord[0] for coord in map_coords)
#                 sum_y = sum(coord[1] for coord in map_coords)
#                 center = (sum_x / 4, sum_y / 4)
# 
#                 # 顯示line_num:Y值
#                 label_text=f"{line_num}:{wy:.1f}";
#                 label_color = MINIMAP_GRID_LABEL_COLOR if line_num in highlight_line_nums else MINIMAP_DYNAMIC_BUILDING_LABEL_COLOR
#                 try:
#                     if show_object_and_grid_labels and coord_label_font and not is_dragging:
#                         text_surface=coord_label_font.render(label_text,True,label_color);
#                         dx=center[0] + 0;
#                         dy=center[1];
#                         renderer._draw_text_texture(text_surface,dx,dy);
#                 except Exception as e:
#                     pass
#                 
#             finally:
#                 glPopAttrib() # 恢復狀態

        # Cylinders (Circles/Boxes)
#         glColor3fv(MINIMAP_DYNAMIC_CYLINDER_COLOR); num_circle_segments = 12
        if hasattr(scene, 'cylinders'): # 檢查列表是否存在
            for item in scene.cylinders:
                line_identifier, cyl = item # 解包行號和數據元組
                # 注意來自scene_parser那邊的剖析結果的變數排列
                try:
                    c_type, wx, wy, wz, rx, ry, rz, cr, ch, \
                    u_offset, v_offset, tex_angle_deg, \
                    uv_mode, uscale, vscale, \
                    tex_file, tex_id, tex_alpha, \
                    parent_origin_ry_deg = cyl;
                except: continue # 簡化錯誤處理
                
                # Cylinders 的包圍圓半徑就是其 cr
                # 如果有 RX/RZ 旋轉，其在XZ平面的投影可能變成橢圓，
                # 包圍圓半徑應取投影橢圓的長半軸，最壞情況是 ch/2 (如果完全躺倒) 和 cr 的組合。
                # 為了簡化和保守，我們可以取 max(cr, ch_c/2) 作為一個估算的XZ投影最大延伸。
                # 但對於頂視圖，如果主要關心的是底座圓形，cr 就足夠了。
                # 如果 cylinder 可以劇烈傾斜，那麼投影會複雜。
                # 先用 cr 作為基礎，如果傾斜不明顯，這是合理的。
                # 如果傾斜可能很大，那麼保守的包圍半徑可能是 sqrt(cr^2 + (ch_c/2)^2)
                # 我們先用一個簡單的：
                cyl_bounding_radius = cr
                if abs(rx) > 10 or abs(rz) > 10: # 如果有明顯的X或Z軸傾斜
                    # 一個更保守的（但可能過大）的半徑估算
                    cyl_bounding_radius = math.sqrt(cr**2 + (ch/2.0)**2) * 1.1 
                
                if circle_intersects_aabb(wx, wz, cyl_bounding_radius,
                                          viewport_world_min_x, viewport_world_max_x,
                                          viewport_world_min_z, viewport_world_max_z):
                
                    # 如果通過裁剪，則進行繪製
                    glPushAttrib(GL_CURRENT_BIT | GL_LINE_BIT) # --- MODIFICATION: Added GL_LINE_BIT ---
#                     glColor3fv(MINIMAP_DYNAMIC_CYLINDER_COLOR);
                    num_circle_segments = 12
                    try:
                        is_highlighted = line_identifier in highlight_line_nums
                        is_also_f7_target = (f7_tuning_target_line_num != -1 and line_identifier == f7_tuning_target_line_num) # <--- 判斷是否為F7目標

                        if is_highlighted or is_also_f7_target:
                            axis_length_map = min(widget_width, widget_height) * 1.00 # 小地圖視窗尺寸的5%
                            angle_y_map_rad = math.radians(-parent_origin_ry_deg) # 與投影計算一致
                            map_local_x_dir_x = math.cos(angle_y_map_rad)
                            map_local_x_dir_z = math.sin(angle_y_map_rad)
                            map_local_z_dir_x = -math.sin(angle_y_map_rad) # cos(a+90) = -sin(a)
                            map_local_z_dir_z =  math.cos(angle_y_map_rad) # sin(a+90) = cos(a)
                            center_map_x, center_map_y = _world_to_map_coords_adapted(
                                wx, wz, view_center_x, view_center_z,
                                widget_center_x_screen, widget_center_y_screen, scale
                            )
                            glLineWidth(2.0)
                            glBegin(GL_LINES)
                            glColor3f(1.0, 0.5, 0.5) # 示例：粉紅色X軸
                            glVertex2f(center_map_x, center_map_y)
                            glVertex2f(center_map_x + map_local_x_dir_x * axis_length_map, 
                                       center_map_y + map_local_x_dir_z * axis_length_map)
                            glColor3f(0.5, 1.0, 0.5) # 示例：淺綠色Z軸
                            glVertex2f(center_map_x, center_map_y)
                            glVertex2f(center_map_x + map_local_z_dir_x * axis_length_map, 
                                       center_map_y + map_local_z_dir_z * axis_length_map)
                            glEnd()
                        
                        if is_also_f7_target: # F7目標優先顯示紅色
    #                             print("紅色")
                            glColor3f(1.0, 0.0, 0.0) # 紅色
                            glLineWidth(3.0) # 可以比普通高亮更粗一點
                        elif is_highlighted:
                            glColor3f(1.0, 1.0, 0.0) # 高亮顏色 (黃色)
                            glLineWidth(3.0) # 可以加粗線條
#                             if line_num == line_to_focus_on:
#                                 focused_element_world_x = wx
#                                 focused_element_world_z = wz                        
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

                        # 顯示line_num:Y值
                        label_text=f"{line_identifier}:{wy:.1f}";
                        label_color = MINIMAP_GRID_LABEL_COLOR if is_highlighted else MINIMAP_DYNAMIC_CYLINDER_LABEL_COLOR
                        try:
                            if show_object_and_grid_labels and coord_label_font and not is_dragging: # --- MODIFICATION: Added coord_label_font check ---
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
        
        for item in scene.trees:
            line_num, tree = item # 解包行號和數據元組
            if line_num not in highlight_line_nums: # 只處理非高亮的
                obj_type, tx, ty, tz, th, _tex_id, _tex_file, parent_origin_ry_deg = tree;
                map_x, map_y = _world_to_map_coords_adapted(tx, tz, view_center_x, view_center_z, widget_center_x_screen, widget_center_y_screen, scale)
                # Basic point culling
                if 0 <= map_x <= widget_width and 0 <= map_y <= widget_height:
                    glBegin(GL_POINTS)
                    glVertex2f(map_x, map_y)
                    glEnd() # 結束非高亮點的繪製

                # --- 繪製 line_num:Y 座標標籤 ---
                label_text = f"{line_num}:{ty:.1f}"
                label_color = MINIMAP_DYNAMIC_TREE_COLOR 
                try:
                    if show_object_and_grid_labels and coord_label_font and not is_dragging: # 確保字體存在
                        text_surface = coord_label_font.render(label_text, True, label_color)
                        # 計算繪製位置 (例如在圓心右側)
                        dx = map_x + 2 # 加一點偏移
                        dy = map_y - text_surface.get_height() / 2
                        renderer._draw_text_texture(text_surface, dx, dy)
                except Exception as e:
                    pass # 忽略繪製標籤錯誤


        # --- 繪製高亮的樹 ---
        if highlight_line_nums: # 只有當有需要高亮的行時才執行

            for item in scene.trees:
                line_identifier, tree_data = item
                is_highlighted = line_identifier in highlight_line_nums
                if is_highlighted: # 只處理高亮的
                    obj_type, tx, ty, tz, th, _tex_id, _tex_file, parent_origin_ry_deg = tree_data
                    center_map_x, center_map_y = _world_to_map_coords_adapted(tx, tz, view_center_x, view_center_z, widget_center_x_screen, widget_center_y_screen, scale)

                    is_also_f7_target = (f7_tuning_target_line_num != -1 and line_identifier == f7_tuning_target_line_num) # <--- 判斷是否為F7目標

                    if is_highlighted or is_also_f7_target:
                        axis_length_map = min(widget_width, widget_height) * 1.00 # 小地圖視窗尺寸的5%
                        angle_y_map_rad = math.radians(-parent_origin_ry_deg) # 與投影計算一致
                        map_local_x_dir_x = math.cos(angle_y_map_rad)
                        map_local_x_dir_z = math.sin(angle_y_map_rad)
                        map_local_z_dir_x = -math.sin(angle_y_map_rad) # cos(a+90) = -sin(a)
                        map_local_z_dir_z =  math.cos(angle_y_map_rad) # sin(a+90) = cos(a)
#                         center_map_x, center_map_y = _world_to_map_coords_adapted(
#                             wx, wz, view_center_x, view_center_z,
#                             widget_center_x_screen, widget_center_y_screen, scale
#                         )
                        glLineWidth(2.0)
                        glBegin(GL_LINES)
                        glColor3f(1.0, 0.5, 0.5) # 示例：粉紅色X軸
                        glVertex2f(center_map_x, center_map_y)
                        glVertex2f(center_map_x + map_local_x_dir_x * axis_length_map, 
                                   center_map_y + map_local_x_dir_z * axis_length_map)
                        glColor3f(0.5, 1.0, 0.5) # 示例：淺綠色Z軸
                        glVertex2f(center_map_x, center_map_y)
                        glVertex2f(center_map_x + map_local_z_dir_x * axis_length_map, 
                                   center_map_y + map_local_z_dir_z * axis_length_map)
                        glEnd()

                    # Basic point culling
                    if is_also_f7_target: # F7目標優先顯示紅色
#                             print("紅色")
                        glColor3f(1.0, 0.0, 0.0) # 紅色
                        glPointSize(max(1.0, point_size) * 1.5) # 高亮點可以稍微大一點 (示例)
                    elif is_highlighted:
                        glColor3f(1.0, 1.0, 0.0) # 高亮顏色
                        glPointSize(max(1.0, point_size) * 1.5) # 高亮點可以稍微大一點 (示例)
                        
                    if 0 <= center_map_x <= widget_width and 0 <= center_map_y <= widget_height:
                        glBegin(GL_POINTS)
                        glVertex2f(center_map_x, center_map_y)
                        glEnd() # 結束高亮點的繪製

                    # --- 繪製 line_identifier:Y 座標標籤 ---
                    label_text = f"{line_identifier}:{ty:.1f}"
                    label_color = MINIMAP_DYNAMIC_TREE_COLOR 
                    try:
                        if show_object_and_grid_labels and coord_label_font and not is_dragging: # 確保字體存在
                            text_surface = coord_label_font.render(label_text, True, label_color)
                            # 計算繪製位置 (例如在圓心右側)
                            dx = center_map_x + 2 # 加一點偏移
                            dy = center_map_y - text_surface.get_height() / 2
                            renderer._draw_text_texture(text_surface, dx, dy)
                    except Exception as e:
                        pass # 忽略繪製標籤錯誤
                    
#                     if line_num == line_to_focus_on:
#                         focused_element_world_x = tx
#                         focused_element_world_z = tz                        

        # --- Draw Spheres (Circles) Dynamically ---
        if hasattr(scene, 'spheres'):
#         num_circle_segments_sphere = 12 # 圓的邊數 (可以根據縮放調整)
            for item in scene.spheres:
                line_identifier, sphere_data = item
                # 解包獲取必要資訊 (世界座標 wx, wy, wz 和半徑 cr)
                try:
                    s_type, wx, wy, wz, srx, sabs_ry, srz, cr, \
                    tex_id, u_offset, v_offset, tex_angle_deg, \
                    uv_mode, uscale, vscale, tex_file, \
                    parent_origin_ry_deg = sphere_data
                except ValueError:
                     print(f"警告: 解包 sphere 數據 (動態小地圖) 時出錯 (來源行: {line_identifier})")
                     continue

                # Spheres 的包圍圓半徑就是其 cr (球體旋轉不改變其投影包圍圓)
                sphere_bounding_radius = cr
                
                if circle_intersects_aabb(wx, wz, sphere_bounding_radius,
                                          viewport_world_min_x, viewport_world_max_x,
                                          viewport_world_min_z, viewport_world_max_z):
                    # 如果通過裁剪，則進行繪製

                    glPushAttrib(GL_CURRENT_BIT | GL_LINE_BIT) # 保存顏色和線寬狀態
                    num_circle_segments_sphere = 12
                    try:
                        center_map_x, center_map_y = _world_to_map_coords_adapted(wx, wz, view_center_x, view_center_z, widget_center_x_screen, widget_center_y_screen, scale)
                        # --- 高亮處理 ---
#                         is_highlighted = line_num in highlight_line_nums
                        is_highlighted = line_identifier in highlight_line_nums
                        is_also_f7_target = (f7_tuning_target_line_num != -1 and line_identifier == f7_tuning_target_line_num) # <--- 判斷是否為F7目標

                        if is_highlighted or is_also_f7_target:
                            axis_length_map = min(widget_width, widget_height) * 1.00 # 小地圖視窗尺寸的5%
                            angle_y_map_rad = math.radians(-parent_origin_ry_deg) # 與投影計算一致
                            map_local_x_dir_x = math.cos(angle_y_map_rad)
                            map_local_x_dir_z = math.sin(angle_y_map_rad)
                            map_local_z_dir_x = -math.sin(angle_y_map_rad) # cos(a+90) = -sin(a)
                            map_local_z_dir_z =  math.cos(angle_y_map_rad) # sin(a+90) = cos(a)
                            center_map_x, center_map_y = _world_to_map_coords_adapted(
                                wx, wz, view_center_x, view_center_z,
                                widget_center_x_screen, widget_center_y_screen, scale
                            )
                            glLineWidth(2.0)
                            glBegin(GL_LINES)
                            glColor3f(1.0, 0.5, 0.5) # 示例：粉紅色X軸
                            glVertex2f(center_map_x, center_map_y)
                            glVertex2f(center_map_x + map_local_x_dir_x * axis_length_map, 
                                       center_map_y + map_local_x_dir_z * axis_length_map)
                            glColor3f(0.5, 1.0, 0.5) # 示例：淺綠色Z軸
                            glVertex2f(center_map_x, center_map_y)
                            glVertex2f(center_map_x + map_local_z_dir_x * axis_length_map, 
                                       center_map_y + map_local_z_dir_z * axis_length_map)
                            glEnd()



                        if is_also_f7_target: # F7目標優先顯示紅色
    #                             print("紅色")
                            glColor3f(1.0, 0.0, 0.0) # 紅色
                            glLineWidth(3.0) # 可以比普通高亮更粗一點
                        elif is_highlighted:
                            glColor3f(1.0, 1.0, 0.0) # 高亮黃色
                            glLineWidth(3.0)
#                             if line_num == line_to_focus_on:
#                                 focused_element_world_x = wx
#                                 focused_element_world_z = wz                        
                        else:
                            glColor3fv(MINIMAP_DYNAMIC_SPHERE_COLOR)
                            glLineWidth(2.0)

                        # --- 繪製圓形 ---
                        radius_map = cr * scale
                        if radius_map > 0.5: # 簡單的細節剔除
                            glBegin(GL_LINE_LOOP)
                            for i in range(num_circle_segments_sphere):
                                angle = 2 * math.pi * i / num_circle_segments_sphere
                                glVertex2f(center_map_x + radius_map * math.cos(angle),
                                           center_map_y + radius_map * math.sin(angle))
                            glEnd()

                        # --- 繪製 line_identifier:Y 座標標籤 ---
                        label_text = f"{line_identifier}:{wy:.1f}"
                        label_color = MINIMAP_GRID_LABEL_COLOR if is_highlighted else MINIMAP_DYNAMIC_SPHERE_LABEL_COLOR
                        try:
                            if show_object_and_grid_labels and coord_label_font and not is_dragging: # 確保字體存在
                                text_surface = coord_label_font.render(label_text, True, label_color)
                                # 計算繪製位置 (例如在圓心右側)
                                dx = center_map_x + radius_map + 2 # 加一點偏移
                                dy = center_map_y - text_surface.get_height() / 2
                                renderer._draw_text_texture(text_surface, dx, dy)
                        except Exception as e:
                            pass # 忽略繪製標籤錯誤
                    finally:
                        glPopAttrib() # 恢復顏色和線寬

        # --- Draw Hills Dynamically (Editor Preview) ---
        num_circle_segments_editor_hill = 16 # 編輯器預覽用稍低精度即可
        hill_center_point_size = 6.0 # 中心點標記大小
        for item in scene.hills:
            line_identifier, hill_data = item
#             print(hill_data)
            try:
                # 解包數據 (需要中心, 高度, 半徑)
                (obj_type, cx, base_y, cz, base_radius, peak_height_offset, 
                 uscale, vscale,
                 uoff, voff,
                 tex_file, 
                 tex_id, tex_alpha, 
                 parent_origin_ry_deg) = hill_data
            except ValueError:
                print(f"警告: 解包 hill 數據 (編輯器預覽) 時出錯 (來源行: {line_num})") # 可選警告
                continue

            # --- 計算 Widget 座標 ---
            center_map_x, center_map_y = _world_to_map_coords_adapted(cx, cz, view_center_x, view_center_z, widget_center_x_screen, widget_center_y_screen, scale)
            radius_map = base_radius * scale # 基底在 Widget 上的半徑

            # --- 檢查是否在可見範圍內 (簡單檢查中心點) ---
            is_visible = 0 <= center_map_x <= widget_width and 0 <= center_map_y <= widget_height
#             # --- 檢查高亮狀態 ---
#             is_highlighted = line_identifier in highlight_line_nums
            

            if is_visible:

                # --- 保存和設置繪製狀態 ---
                glPushAttrib(GL_CURRENT_BIT | GL_POINT_BIT | GL_LINE_BIT)
                try:
                    is_highlighted = line_identifier in highlight_line_nums
                    is_also_f7_target = (f7_tuning_target_line_num != -1 and line_identifier == f7_tuning_target_line_num) # <--- 判斷是否為F7目標

                    if is_highlighted or is_also_f7_target:
                        axis_length_map = min(widget_width, widget_height) * 1.00 # 小地圖視窗尺寸的5%
                        angle_y_map_rad = math.radians(-parent_origin_ry_deg) # 與投影計算一致
                        map_local_x_dir_x = math.cos(angle_y_map_rad)
                        map_local_x_dir_z = math.sin(angle_y_map_rad)
                        map_local_z_dir_x = -math.sin(angle_y_map_rad) # cos(a+90) = -sin(a)
                        map_local_z_dir_z =  math.cos(angle_y_map_rad) # sin(a+90) = cos(a)
#                         center_map_x, center_map_y = _world_to_map_coords_adapted(
#                             wx, wz, view_center_x, view_center_z,
#                             widget_center_x_screen, widget_center_y_screen, scale
#                         )
                        glLineWidth(2.0)
                        glBegin(GL_LINES)
                        glColor3f(1.0, 0.5, 0.5) # 示例：粉紅色X軸
                        glVertex2f(center_map_x, center_map_y)
                        glVertex2f(center_map_x + map_local_x_dir_x * axis_length_map, 
                                   center_map_y + map_local_x_dir_z * axis_length_map)
                        glColor3f(0.5, 1.0, 0.5) # 示例：淺綠色Z軸
                        glVertex2f(center_map_x, center_map_y)
                        glVertex2f(center_map_x + map_local_z_dir_x * axis_length_map, 
                                   center_map_y + map_local_z_dir_z * axis_length_map)
                        glEnd()




                    if is_also_f7_target: # F7目標優先顯示紅色
#                             print("紅色")
                        glColor3f(1.0, 0.0, 0.0) # 紅色
                        glLineWidth(3.0) # 可以比普通高亮更粗一點
                    elif is_highlighted:
                        glColor3fv(MINIMAP_HIGHLIGHT_HILL_COLOR)
                        glPointSize(hill_center_point_size * 1.5) # 高亮點稍大
                        glLineWidth(2.5) # 高亮輪廓稍粗
                        label_color = MINIMAP_HIGHLIGHT_HILL_LABEL_COLOR
                    else:
                        glColor3fv(MINIMAP_DYNAMIC_HILL_COLOR)
                        glPointSize(hill_center_point_size)
                        glLineWidth(1.5)
                        label_color = MINIMAP_DYNAMIC_HILL_LABEL_COLOR

                    # --- 繪製中心點 ---
                    glBegin(GL_POINTS)
                    glVertex2f(center_map_x, center_map_y)
                    glEnd()

                    # --- 繪製基底圓形輪廓 ---
                    if radius_map > 1.0: # 只繪製有意義大小的輪廓
                        glBegin(GL_LINE_LOOP)
                        for i in range(num_circle_segments_editor_hill):
                            angle = 2 * math.pi * i / num_circle_segments_editor_hill
                            glVertex2f(center_map_x + radius_map * math.cos(angle),
                                       center_map_y + radius_map * math.sin(angle))
                        glEnd()

                    # --- 繪製高度標籤 ---
                    peak_absolute_y = base_y + peak_height_offset
                    label_text = f"{line_identifier}:{peak_absolute_y:.1f}m" # 格式化高度
                    try:
                        if show_object_and_grid_labels and coord_label_font and not is_dragging: # 確保字體已設置
                            text_surface = coord_label_font.render(label_text, True, label_color)
                            # 計算標籤位置 (例如，中心點右上方)
                            dx = center_map_x + 5 # 稍微偏右
                            dy = center_map_y + 5 # 稍微偏上
                            renderer._draw_text_texture(text_surface, dx, dy)
                    except Exception as e:
                        pass # 忽略繪製標籤錯誤
                finally:
                    glPopAttrib() # 恢復繪製狀態
                    
        # --- Draw gableroofs
        # MINIMAP_DYNAMIC_ROOF_COLOR = (0.8, 0.3, 0.3) # 可以定義一個特定的屋頂顏色
        # MINIMAP_DYNAMIC_ROOF_LABEL_COLOR = tuple(c * 255 for c in MINIMAP_DYNAMIC_ROOF_COLOR) + (180,)
        # 為了簡單，我們先用 building 的顏色
        # glColor3fv(MINIMAP_DYNAMIC_ROOF_COLOR)
        # glLineWidth(2.0)

        if hasattr(scene, 'gableroofs'):
            for item in scene.gableroofs:
                line_identifier, roof_data = item
                try:
                    # 與FBO中解包方式保持一致
                    wx, wy, wz, rx_d, ry_d, rz_d = roof_data[1:7]
                    base_w, base_l, ridge_h_off = roof_data[7:10]
                    ridge_x_pos_offset = roof_data[10]
                    eave_overhang_x = roof_data[11]
                    eave_overhang_z = roof_data[12]
                    parent_origin_ry_deg = roof_data[16]
                except (IndexError, ValueError):
                    # print(f"警告: 解包 gableroof 數據 (編輯器預覽) 時出錯 (行: {line_identifier})")
                    continue

                # --- 包圍圓裁剪 (與之前相同) ---
                actual_width_for_bound = base_w + 2 * abs(eave_overhang_x)
                actual_length_for_bound = base_l + 2 * abs(eave_overhang_z)
                roof_bounding_radius = math.sqrt(actual_width_for_bound**2 + actual_length_for_bound**2) / 2.0 * 1.1
                if not circle_intersects_aabb(wx, wz, roof_bounding_radius,
                                              viewport_world_min_x, viewport_world_max_x,
                                              viewport_world_min_z, viewport_world_max_z):
                    continue
                # --- 結束包圍圓裁剪 ---


                glPushAttrib(GL_CURRENT_BIT | GL_LINE_BIT)
                try:
                    is_highlighted = line_identifier in highlight_line_nums
                    is_also_f7_target = (f7_tuning_target_line_num != -1 and line_identifier == f7_tuning_target_line_num) # <--- 判斷是否為F7目標

                    if is_highlighted or is_also_f7_target:
                        axis_length_map = min(widget_width, widget_height) * 1.00 # 小地圖視窗尺寸的5%
                        angle_y_map_rad = math.radians(-parent_origin_ry_deg) # 與投影計算一致
                        map_local_x_dir_x = math.cos(angle_y_map_rad)
                        map_local_x_dir_z = math.sin(angle_y_map_rad)
                        map_local_z_dir_x = -math.sin(angle_y_map_rad) # cos(a+90) = -sin(a)
                        map_local_z_dir_z =  math.cos(angle_y_map_rad) # sin(a+90) = cos(a)
                        center_map_x, center_map_y = _world_to_map_coords_adapted(
                            wx, wz, view_center_x, view_center_z,
                            widget_center_x_screen, widget_center_y_screen, scale
                        )
                        glLineWidth(2.0)
                        glBegin(GL_LINES)
                        glColor3f(1.0, 0.5, 0.5) # 示例：粉紅色X軸
                        glVertex2f(center_map_x, center_map_y)
                        glVertex2f(center_map_x + map_local_x_dir_x * axis_length_map, 
                                   center_map_y + map_local_x_dir_z * axis_length_map)
                        glColor3f(0.5, 1.0, 0.5) # 示例：淺綠色Z軸
                        glVertex2f(center_map_x, center_map_y)
                        glVertex2f(center_map_x + map_local_z_dir_x * axis_length_map, 
                                   center_map_y + map_local_z_dir_z * axis_length_map)
                        glEnd()


#                     is_highlighted = line_identifier in highlight_line_nums
                    if is_also_f7_target: # F7目標優先顯示紅色
#                             print("紅色")
                        glColor3f(1.0, 0.0, 0.0) # 紅色
                        glLineWidth(3.0) # 可以比普通高亮更粗一點
                    elif is_highlighted:
                        glColor3f(1.0,1.0,0.0);
                        glLineWidth(3.0)
                    else:
                        glColor3fv(MINIMAP_DYNAMIC_BUILDING_COLOR);
                        glLineWidth(2.0) # 借用顏色


                    # --- 繪製凸包線框 ---
                    hull_vertices_world_xz = get_convex_hull_projection_for_gableroof(
                        wx, wy, wz, rx_d, ry_d, rz_d,
                        base_w, base_l, ridge_h_off,
                        ridge_x_pos_offset, eave_overhang_x, eave_overhang_z
                    )
                    if hull_vertices_world_xz and len(hull_vertices_world_xz) >= 3:
                        map_poly_coords = []
                        for corner_world_xz in hull_vertices_world_xz:
                            map_x, map_y = _world_to_map_coords_adapted(
                                corner_world_xz[0], corner_world_xz[1], 
                                view_center_x, view_center_z, 
                                widget_center_x_screen, widget_center_y_screen, scale)
                            map_poly_coords.append((map_x, map_y))
                        glBegin(GL_LINE_LOOP); [glVertex2f(mx, my) for mx, my in map_poly_coords]; glEnd()
                    # --- 結束繪製凸包 ---

                    # --- 繪製屋脊中線 (虛線, 也需要完整3D旋轉) ---
                    ridge_local_start = np.array([ridge_x_pos_offset, ridge_h_off, -base_l/2.0 - eave_overhang_z])
                    ridge_local_end   = np.array([ridge_x_pos_offset, ridge_h_off,  base_l/2.0 + eave_overhang_z])
                    rotation_matrix_ridge_preview = _calculate_y_x_z_intrinsic_rotation_matrix(rx_d, ry_d, rz_d)
                    
                    rotated_rs_offset = np.dot(rotation_matrix_ridge_preview, ridge_local_start)
                    map_rs_x, map_rs_y = _world_to_map_coords_adapted(wx + rotated_rs_offset[0], wz + rotated_rs_offset[2],
                                                                    view_center_x, view_center_z, widget_center_x_screen, widget_center_y_screen, scale)
                    rotated_re_offset = np.dot(rotation_matrix_ridge_preview, ridge_local_end)
                    map_re_x, map_re_y = _world_to_map_coords_adapted(wx + rotated_re_offset[0], wz + rotated_re_offset[2],
                                                                    view_center_x, view_center_z, widget_center_x_screen, widget_center_y_screen, scale)
                    
                    if is_highlighted: glColor3f(1.0,1.0,0.0) # 高亮屋脊
                    else: glColor3fv([c * 0.7 for c in MINIMAP_DYNAMIC_BUILDING_COLOR]) # 暗色屋脊
                    glEnable(GL_LINE_STIPPLE); glLineStipple(1, 0x00FF); glLineWidth(1.0)
                    glBegin(GL_LINES); glVertex2f(map_rs_x, map_rs_y); glVertex2f(map_re_x, map_re_y); glEnd()
                    glDisable(GL_LINE_STIPPLE)
                    # --- 結束繪製屋脊 ---
                    
                    # --- 標籤繪製 (邏輯不變，但可能需要調整標籤定位點) ---
                    if hull_vertices_world_xz and show_object_and_grid_labels and coord_label_font and not is_dragging:
                        # 使用凸包的幾何中心或AABB中心作為標籤定位點
                        if hull_vertices_world_xz:
                            center_x_label_calc = sum(p[0] for p in map_poly_coords) / len(map_poly_coords) if map_poly_coords else widget_center_x_screen
                            center_y_label_calc = sum(p[1] for p in map_poly_coords) / len(map_poly_coords) if map_poly_coords else widget_center_y_screen
                            # ... (你的標籤文本生成和繪製邏輯) ...
                finally:
                    glPopAttrib()
    # --- 結束繪製 Gableroofs ---
    
        # 恢復默認點大小
        glPointSize(1.0)

    # --- START OF MODIFICATION: Draw Track Lines Dynamically (including vbranches) ---
    if scene and scene.track: # Keep not is_dragging to reduce visual noise during drag
        default_track_line_width = 1.0  # --- MODIFICATION: Thinner default track lines ---
        highlight_track_line_width = 2.0 # --- MODIFICATION: Thicker highlight ---
        default_point_size = 4.0 # --- MODIFICATION: Smaller points ---
        highlight_point_size = 6.0 # --- MODIFICATION: Slightly larger highlighted points ---

        for segment in scene.track.segments:
            # --- Draw Main Segment ---
            if segment.points and len(segment.points) >= 2:
                glPushAttrib(GL_CURRENT_BIT | GL_LINE_BIT | GL_POINT_BIT)
                is_highlighted_main = False
                try:
                    line_num_main = segment.source_line_number 
                    is_highlighted_main = line_num_main in highlight_line_nums
                    if is_highlighted_main:
                        glColor3f(1.0, 1.0, 0.0) 
                        glLineWidth(highlight_track_line_width)        
                        glPointSize(highlight_point_size)         
                        if segment.source_line_number == line_to_focus_on:
                            focused_element_world_x = segment.points[0][0]
                            focused_element_world_z = segment.points[0][2]                        
                    else:
                        glColor3fv(MINIMAP_TRACK_COLOR)
                        glLineWidth(default_track_line_width)
                        glPointSize(default_point_size)
                
                    # Draw start point of main segment
                    map_x_main_start, map_y_main_start = _world_to_map_coords_adapted(
                        segment.points[0][0], segment.points[0][2],
                        view_center_x, view_center_z,
                        widget_center_x_screen, widget_center_y_screen, scale)
                    glBegin(GL_POINTS)
                    glVertex2f(map_x_main_start, map_y_main_start)
                    glEnd()        

                    # Draw line strip for main segment
                    glBegin(GL_LINE_STRIP)
                    for point_world in segment.points:
                        widget_x, widget_y = _world_to_map_coords_adapted(
                            point_world[0], point_world[2], 
                            view_center_x, view_center_z, 
                            widget_center_x_screen, widget_center_y_screen, scale)
                        glVertex2f(widget_x, widget_y)
                    glEnd()
                finally:
                    glPopAttrib()

                if not is_dragging:
                    # Display info for main segment (reuse map_x_main_start, map_y_main_start)
                    is_curve = True if hasattr(segment, 'angle_deg') and abs(segment.angle_deg) > 0.1 else False # Check if it's a curve
                    if is_curve:
                        track_info = f"C {segment.angle_deg:.1f}°"
                    else: # Assuming straight
                        track_info = f"S {segment.horizontal_length:.1f}" # Use horizontal_length
                    
                    label_text_main=f"{track_info} y: {segment.points[0][1]:.1f} ({line_num_main})"; # Added line_num
                    label_color_main = (255, 255, 0, 0.1) if is_highlighted_main else MINIMAP_GRID_LABEL_COLOR
                    try:
                        if show_object_and_grid_labels and coord_label_font: # Check if font exists
                            text_surface_main=coord_label_font.render(label_text_main,True,label_color_main);
                            dx_main=map_x_main_start + 5;
                            dy_main=map_y_main_start;
                            renderer._draw_text_texture(text_surface_main,dx_main,dy_main);
                    except Exception as e: pass
            
            # --- Draw Visual Branches ---
            if hasattr(segment, 'visual_branches') and segment.visual_branches:
                for idx, branch_def in enumerate(segment.visual_branches):
                    if branch_def.get('points') and len(branch_def['points']) >= 2:
                        glPushAttrib(GL_CURRENT_BIT | GL_LINE_BIT | GL_POINT_BIT)
                        # For vbranch, highlighting could be based on the parent segment's line number
                        # or if vbranch itself had a source_line_number (if it were a separate command in table)
                        # Assuming for now, vbranch highlight follows parent segment.
                        is_highlighted_branch = segment.source_line_number in highlight_line_nums 
                        try:
                            if is_highlighted_branch: # Highlight branch if parent is highlighted
                                glColor3f(1.0, 0.8, 0.2) # Slightly different highlight (e.g., orange)
                                glLineWidth(highlight_track_line_width * 0.8) # Maybe slightly thinner than main highlight  
                                glPointSize(highlight_point_size * 0.8)      
                                if segment.source_line_number == line_to_focus_on:
                                    focused_element_world_x = branch_def['points'][0][0]
                                    focused_element_world_z = branch_def['points'][0][2]                        
                            else:
                                glColor3fv(MINIMAP_BRANCH_TRACK_COLOR) # Or a different color for vbranches
                                glLineWidth(default_track_line_width * 0.8) # Slightly thinner than main track
                                glPointSize(default_point_size * 0.8)
                            
                            # Draw start point of the branch
                            map_x_branch_start, map_y_branch_start = _world_to_map_coords_adapted(
                                branch_def['points'][0][0], branch_def['points'][0][2],
                                view_center_x, view_center_z,
                                widget_center_x_screen, widget_center_y_screen, scale)
                            glBegin(GL_POINTS)
                            glVertex2f(map_x_branch_start, map_y_branch_start)
                            glEnd()

                            # Draw line strip for the branch
                            glBegin(GL_LINE_STRIP)
                            for point_world_b in branch_def['points']:
                                widget_x_b, widget_y_b = _world_to_map_coords_adapted(
                                    point_world_b[0], point_world_b[2], 
                                    view_center_x, view_center_z, 
                                    widget_center_x_screen, widget_center_y_screen, scale)
                                glVertex2f(widget_x_b, widget_y_b)
                            glEnd()
                        finally:
                            glPopAttrib()
                        
                        # Optional: Display info for vbranch (could get cluttered)
                        # branch_type_char = "S" if branch_def.get("type") == "straight" else "C"
                        # branch_len_or_angle = branch_def.get("length") if branch_type_char == "S" else branch_def.get("angle_deg")
                        # label_text_branch = f"v{branch_type_char} {branch_len_or_angle:.1f} y:{branch_def['points'][0][1]:.1f}"
                        # label_color_branch = (255,220,0,180) if is_highlighted_branch else (200,200,200,150)
                        # try:
                        #     if coord_label_font:
                        #         text_surface_b = coord_label_font.render(label_text_branch, True, label_color_branch)
                        #         renderer._draw_text_texture(text_surface_b, map_x_branch_start + 7, map_y_branch_start - 7)
                        # except: pass
    # --- END OF MODIFICATION ---
                
                
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
                    if grid_label_font: # Check font
                        text_surface=grid_label_font.render(label_text,True,MINIMAP_GRID_LABEL_COLOR);
                        dx=widget_x-text_surface.get_width()/2;
                        dy=MINIMAP_GRID_LABEL_OFFSET; # Labels at bottom
                        renderer._draw_text_texture(text_surface,dx,dy);
                except Exception as e: pass
            current_gx += MINIMAP_GRID_SCALE
        current_gz=start_gz
        while current_gz <= world_t:
            _,widget_y = _world_to_map_coords_adapted(view_center_x, current_gz, view_center_x, view_center_z, widget_center_x_screen, widget_center_y_screen, scale)
            if 0<=widget_y<=widget_height:
                label_text=f"{current_gz:.0f}";
                try:
                    if grid_label_font: # Check font
                        text_surface=grid_label_font.render(label_text,True,MINIMAP_GRID_LABEL_COLOR);
                        dx=MINIMAP_GRID_LABEL_OFFSET; # Labels at left
                        dy=widget_y-text_surface.get_height()/2;
                        renderer._draw_text_texture(text_surface,dx,dy);
                except Exception as e: pass
            current_gz += MINIMAP_GRID_SCALE

    return focused_element_world_x, focused_element_world_z

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
