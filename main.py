# main.py
import pygame
from pygame.locals import *
import math
import sys
import os

from OpenGL.GL import *
from OpenGL.GLU import *

# 檢查並導入本地模組
try:
    from shapes import draw_cube, draw_cylinder, draw_tree
    from track import Track
    from cabin import draw_dashboard, draw_control_lever, draw_window_frame
except ImportError as e:
    print(f"錯誤：無法導入必要的模組。請確保 shapes.py, track.py, cabin.py 在同一目錄下。")
    print(f"詳細錯誤: {e}")
    sys.exit(1)


# --- 常數 ---
SCREEN_WIDTH = 1024
SCREEN_HEIGHT = 768
GROUND_SIZE = 1500.0 # 大地的大小
CAMERA_HEIGHT = 1.6 # 駕駛員視角高度 (相對於軌道)
SCENE_FILE = "scene.txt" # Define scene filename as a constant
CHECK_INTERVAL = 1.0    # Check file modification every X seconds
TEXTURE_DIR = "textures" # Optional: Subdirectory for textures

# --- 全域變數 ---
track = Track()
track.filepath = SCENE_FILE # Store filepath in track object
buildings = []
trees = []
textures = {} # !!! Cache for loaded textures {filename: texture_id} !!!

tram_distance = 0.0  # 電車沿軌道行駛的距離
tram_speed = 0.0     # 電車速度 (m/s)
MAX_SPEED = 20.0     # 最大速度 (約 72 km/h)
ACCELERATION = 2.0   # 加速度 (m/s^2)
BRAKING = 3.0      # 煞車減速度
FRICTION = 0.5       # 摩擦力/阻力

camera_yaw = 0.0     # 水平視角 (左右看) - 相對於電車前方
camera_pitch = 0.0   # 垂直視角 (上下看)
MOUSE_SENSITIVITY = 0.1

# Variables for scene reloading
last_mtime = 0.0
time_since_last_check = 0.0

# --- Ground display toggle ---
show_ground = False # Ground is visible by default
loop_track = True # <<< Make track loop by default


# --- Texture Loading Function ---
def load_texture(filename):
    """載入圖片檔案並轉換為 OpenGL 紋理"""
    global textures
    if filename in textures:
        return textures[filename] # Return cached texture ID

    # Construct full path (optional, if using a subdirectory)
    filepath = os.path.join(TEXTURE_DIR, filename) if TEXTURE_DIR else filename
    # filepath = filename # If textures are in the same directory

    try:
        print(f"正在載入紋理: {filepath}")
        surface = pygame.image.load(filepath)
        # Convert to format OpenGL understands (RGBA)
        # The 'True' argument flips the image vertically, which is often needed for OpenGL texture mapping
        texture_data = pygame.image.tostring(surface, "RGBA", True)
        width = surface.get_width()
        height = surface.get_height()

        # Generate one texture ID
        tex_id = glGenTextures(1)

        # Bind the texture ID
        glBindTexture(GL_TEXTURE_2D, tex_id)

        # Set texture parameters
        # GL_LINEAR provides smoother interpolation than GL_NEAREST
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        # GL_REPEAT tiles the texture if coords go outside [0,1]
        # GL_CLAMP_TO_EDGE clamps coords to the edge
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)

        # Upload the texture data
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, width, height, 0, GL_RGBA, GL_UNSIGNED_BYTE, texture_data)

        textures[filename] = tex_id # Cache the loaded texture ID
        print(f"紋理 '{filename}' (ID: {tex_id}) 載入成功。")
        glBindTexture(GL_TEXTURE_2D, 0) # Unbind texture
        return tex_id

    except pygame.error as e:
        print(f"錯誤: 無法載入紋理檔案 '{filepath}': {e}")
        textures[filename] = None # Cache failure to avoid retrying constantly
        return None
    except FileNotFoundError:
         print(f"錯誤: 找不到紋理檔案 '{filepath}'")
         textures[filename] = None
         return None
    except Exception as e:
        print(f"載入紋理 '{filepath}' 時發生未知錯誤: {e}")
        textures[filename] = None
        return None

# --- 初始化 ---
def init_opengl():
    """初始化 OpenGL 設定"""
    glEnable(GL_DEPTH_TEST) # 啟用深度測試
    glEnable(GL_LIGHTING)   # 啟用光照
    glEnable(GL_LIGHT0)     # 啟用 0 號光源
    glEnable(GL_COLOR_MATERIAL) # 啟用顏色材質，允許 glColor 控制物體顏色
    glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)

    # 設定光源屬性 (簡單的白色平行光)
    glLightfv(GL_LIGHT0, GL_POSITION, [1.0, 1.0, 0.5, 0.0]) # 方向光 (w=0)
    glLightfv(GL_LIGHT0, GL_AMBIENT, [0.3, 0.3, 0.3, 1.0])  # 環境光
    glLightfv(GL_LIGHT0, GL_DIFFUSE, [0.9, 0.9, 0.9, 1.0])  # 漫反射光

    # 設定視角
    glMatrixMode(GL_PROJECTION)
    gluPerspective(45, (SCREEN_WIDTH / SCREEN_HEIGHT), 0.1, GROUND_SIZE * 2) # 視野角度, 寬高比, 近裁剪面, 遠裁剪面
    glMatrixMode(GL_MODELVIEW)

    # 背景色 (淡藍色天空)
    glClearColor(0.6, 0.8, 1.0, 1.0)

    # 啟用平滑著色
    glShadeModel(GL_SMOOTH)



def load_scene(filename="scene.txt"):
    """載入並解析場景檔案"""
    global buildings, trees, track, last_mtime # Declare globals we modify
    #buildings = []
    #trees = []
    if not os.path.exists(filename):
        print(f"錯誤: 場景檔案 '{filename}' 不存在.")
        # Clear existing scene if file is gone
        track.reset()
        buildings.clear()
        trees.clear()
        last_mtime = 0.0
        return False

    print(f"正在載入場景檔案: {filename}")
    # !!! 清空舊數據 !!!
    track.reset() # Use the new reset method
    buildings.clear()
    trees.clear()
    track.filepath = filename # Ensure filepath is set/updated


    try:
        current_mtime = os.path.getmtime(filename)
        print(f"檔案 '{filename}' 存在，最後修改時間: {current_mtime}")
        
        with open(filename, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                parts = line.split()
                command = parts[0].lower()

                try:
                    if command == 'straight':
                        if len(parts) == 2:
                            length = float(parts[1])
                            track.add_segment('straight', length)
                        else:
                            print(f"警告: 第 {line_num} 行 'straight' 指令參數數量錯誤。需要 1 個參數 (長度)。")
                    elif command == 'curve':
                         if len(parts) == 3:
                            radius = float(parts[1])
                            angle = float(parts[2])
                            track.add_segment('curve', radius, angle)
                         else:
                            print(f"警告: 第 {line_num} 行 'curve' 指令參數數量錯誤。需要 2 個參數 (半徑, 角度)。")
                    elif command == 'building':
                        if len(parts) >= 7:
                            x, y, z, w, d, h = map(float, parts[1:7])
                            texture_file = parts[7] if len(parts) >= 8 else None
                            if len(parts) > 8:
                                print(f"警告: 第 {line_num} 行 'building' 指令有多餘參數。")
                            buildings.append({'type': 'cube', 'pos': (x, y, z),
                                              'size': (w, d, h), 'texture_file': texture_file})                                
                        else:
                            print(f"警告: 第 {line_num} 行 'building' 指令參數數量錯誤。需要 6 個參數 (x y z width depth height)。")
                    elif command == 'cylinder': # Cylinder building
                        if len(parts) >= 6:
                            x, y, z, r, h = map(float, parts[1:6])
                            texture_file = parts[6] if len(parts) >= 7 else None
                            if len(parts) > 7:
                                print(f"警告: 第 {line_num} 行 'cylinder' 指令有多餘參數。")
                            buildings.append({'type': 'cylinder', 'pos': (x, y, z),
                                              'radius': r, 'height': h, 'texture_file': texture_file})
                                
                        else:
                            print(f"警告: 第 {line_num} 行 'cylinder' 指令參數錯誤。需要 5 個 (x y z radius height) [texture]。")                            
                    elif command == 'tree':
                        if len(parts) == 5:
                             x, y, z, h = map(float, parts[1:])
                             trees.append({'pos': (x, y, z), 'height': h})
                        else:
                            print(f"警告: 第 {line_num} 行 'tree' 指令參數數量錯誤。需要 4 個參數 (x y z height)。")
                    else:
                        print(f"警告: 第 {line_num} 行無法識別的指令 '{command}'。")
                except ValueError as e:
                    print(f"警告: 第 {line_num} 行參數轉換錯誤: {e}。 行: '{line}'")

        print(f"場景載入完成: {len(track.segments)} 個軌道段, {len(buildings)} 個建築物, {len(trees)} 棵樹。")
        last_mtime = current_mtime # Update last modification time on successful load
        return True

    except FileNotFoundError:
        print(f"錯誤: 在嘗試讀取時場景檔案 '{filename}' 消失了。")
        last_mtime = 0.0
        return False

    except Exception as e:
        print(f"讀取場景檔案 '{filename}' 時發生錯誤: {e}")
        return False

def check_and_reload_scene():
    """檢查場景檔案是否有變更，若有則重新載入"""
    global last_mtime, tram_distance, tram_speed # Need to modify these

    if not track.filepath: # Should not happen if initialized correctly
        return

    try:
        current_mtime = os.path.getmtime(track.filepath)

        # Check if file was modified since last load/check
        # Use a small tolerance for floating point comparison if needed, but > check is usually fine
        if current_mtime > last_mtime:
            print("-" * 20)
            print(f"檢測到場景檔案 '{track.filepath}' 已變更!")
            print(f"舊修改時間: {last_mtime}, 新修改時間: {current_mtime}")
            if load_scene(track.filepath):
                print("重新載入場景成功，正在預處理軌道...")
                track.preprocess() # !!! 重新預處理軌道 !!!
                if track.total_length == 0:
                     print("警告: 重新載入後軌道長度為 0。")
                # 重置電車狀態
                print("重置電車位置和速度。")
#                 tram_distance = 0.0
#                 tram_speed = 0.0
            else:
                print("重新載入場景失敗。保留舊場景（如果有的話）或空場景。")
                # Keep the old last_mtime so we don't constantly try to reload a bad file
            print("-" * 20)
        # Update last_mtime only if the file exists now, even if not changed
        # This handles the case where the file was deleted and then recreated
        elif last_mtime == 0.0:
             print(f"場景檔案 '{track.filepath}' 首次出現或重新出現，執行初始載入。")
             if load_scene(track.filepath):
                 track.preprocess()
                 tram_distance = 0.0
                 tram_speed = 0.0
             last_mtime = current_mtime # Set mtime even if load failed, file exists

    except FileNotFoundError:
        if last_mtime != 0.0: # Only print message once if file disappears
            print(f"警告: 場景檔案 '{track.filepath}' 已被移除或無法訪問。")
            # Clear the scene? Optional, depends on desired behavior.
            # load_scene(track.filepath) # This will now handle the FileNotFoundError
            track.reset()
            buildings.clear()
            trees.clear()
            print("場景已清空。")
            last_mtime = 0.0 # Reset mtime so we detect if it reappears


# --- 繪圖 ---
def draw_ground():
    """繪製大地"""
    glColor3f(0.4, 0.7, 0.3) # 綠色地面
    glBegin(GL_QUADS)
    glNormal3f(0.0, 1.0, 0.0) # 法線朝上
    glVertex3f(-GROUND_SIZE, 0.0, -GROUND_SIZE)
    glVertex3f(GROUND_SIZE, 0.0, -GROUND_SIZE)
    glVertex3f(GROUND_SIZE, 0.0, GROUND_SIZE)
    glVertex3f(-GROUND_SIZE, 0.0, GROUND_SIZE)
    glEnd()

def draw_cabin_elements(control_level):
    """繪製駕駛艙元素 (固定視角)"""
    # 為了讓駕駛艙元素固定在視角前，我們需要在設置好視角變換後，
    # 清除模型視圖矩陣，然後再繪製這些元素。
    # 這通常需要切換到正交投影，但這裡我們用一個技巧：
    # 在 glLoadIdentity() 之後，但在應用視角旋轉和平移之前繪製。
    # 不過這會導致它跟隨世界旋轉，並不理想。

    # 更可靠的方法: 繪製完世界後，設置正交投影繪製 HUD
    # 這裡我們先用簡單的方法繪製在世界座標系近處
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity() # 重置模型視圖矩陣，元素相對於攝影機原點

    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()
    
    glPushAttrib(GL_ENABLE_BIT | GL_DEPTH_BUFFER_BIT) # 保存啟用狀態和深度緩衝區狀態
    glDisable(GL_DEPTH_TEST)
    
    # 禁用光照，使駕駛艙元素顏色固定
    glDisable(GL_LIGHTING)

    # 繪製儀表板
#     draw_dashboard()

    # 繪製控制桿
    draw_control_lever(level=control_level) # control_level 來自速度或按鍵狀態

    # 繪製窗框 (可選)
    # draw_window_frame() # 這個用線條畫，效果可能一般

    # 恢復光照
    glEnable(GL_LIGHTING)

    # 3. 恢復之前的啟用狀態和深度緩衝區狀態
    glPopAttrib()

    # 4. 恢復之前的模型視圖和投影矩陣
    glPopMatrix() # 恢復模型視圖矩陣
    glMatrixMode(GL_PROJECTION)
    glPopMatrix() # 恢復投影矩陣
    glMatrixMode(GL_MODELVIEW) # 切換回模型視圖模式
    
def draw_scene():
    """繪製所有場景元素"""
    global buildings, trees, track

    # 繪製大地
    if show_ground:
        draw_ground()

    # 繪製軌道
    track.draw()

    # 繪製建築物
    default_building_color = (0.8, 0.75, 0.7)
    
#     glColor3f(0.8, 0.75, 0.7) # 建築物米色
    for b in buildings:
        pos = b['pos']
        
        texture_file = b.get('texture_file') # Use .get for safety
        texture_id = None
#         draw_cube(pos[0], pos[1], pos[2], size[0], size[1], size[2])
        if texture_file:
            texture_id = load_texture(texture_file) # Attempt to load/get from cache

        # If texture loading failed or no texture specified, set default color
        if texture_id is None:
            glColor3fv(default_building_color)
        # Else: draw_cube/draw_cylinder will set color to white if texture_id is valid

        building_type = b.get('type', 'cube') # Default to cube if type missing

        if building_type == 'cube':
            size = b['size']
            draw_cube(pos[0], pos[1], pos[2], size[0], size[1], size[2], texture_id=texture_id)
        elif building_type == 'cylinder':
            radius = b['radius']
            height = b['height']
            # Pass texture_id to draw_cylinder
            draw_cylinder(pos[0], pos[1], pos[2], radius, height, slices=256, texture_id=texture_id)

        # Ensure texturing is disabled after drawing each object *if* it was enabled
        # (draw_cube and draw_cylinder should handle this internally now)
        # glDisable(GL_TEXTURE_2D) # Probably redundant now


    # 繪製樹木 (使用 shapes.py 中的函式)
    for t in trees:
        pos = t['pos']
        height = t['height']
        draw_tree(pos[0], pos[1], pos[2], height)



# --- 更新 ---
def update(dt):
    """更新遊戲狀態"""
    global tram_distance, tram_speed, camera_yaw, camera_pitch, loop_track

    keys = pygame.key.get_pressed()
    control_input = 0.0

    # 控制電車速度
    if keys[K_w] or keys[K_UP]:
        tram_speed += ACCELERATION * dt
        control_input = 1.0
    elif keys[K_s] or keys[K_DOWN]:
        tram_speed -= BRAKING * dt
        control_input = -1.0
    else:
        # 施加摩擦力/阻力
        if abs(tram_speed) > 1e-2:
            friction_effect = FRICTION * dt
            # Prevent friction from reversing direction
            if abs(tram_speed) > friction_effect:
                 tram_speed -= math.copysign(friction_effect, tram_speed)
            else:
                 tram_speed = 0.0
        else:
            tram_speed = 0.0

    # 限制速度
    tram_speed = max(-MAX_SPEED / 2, min(MAX_SPEED, tram_speed)) # 倒車速度限制

    # 更新電車在軌道上的距離
    if track.total_length > 0:
        tram_distance += tram_speed * dt
        
        
        # --- Handle Track End Behavior ---
        if loop_track:
            # Use 'while' loops to handle potentially large dt * tram_speed steps
            while tram_distance >= track.total_length:
                tram_distance -= track.total_length
            while tram_distance < 0:
                tram_distance += track.total_length
        else: # Stop at ends
            if tram_distance <= 0:
                 tram_distance = 0
                 if tram_speed < 0: tram_speed = 0 # Stop if moving backward
            elif tram_distance >= track.total_length:
                 tram_distance = track.total_length
                 if tram_speed > 0: tram_speed = 0 # Stop if moving forward
        # --------------------------------
    else:
        # 如果沒有軌道，電車不能移動
        tram_speed = 0.0
        tram_distance = 0.0

    # 循環軌道 (如果需要)
    # if tram_distance > track.total_length:
    #     tram_distance -= track.total_length
    # elif tram_distance < 0:
    #     tram_distance += track.total_length

    # 防止超出軌道範圍 (更常見)
#     tram_distance = max(0, min(track.total_length, tram_distance))
#     if tram_distance == 0 or tram_distance == track.total_length:
#          if abs(tram_speed) > 0.1: # 到達終點時施加額外制動
#              tram_speed *= 0.9 # 快速減速
#          if abs(tram_speed) < 0.1:
#             tram_speed = 0.0 # 完全停止
        

    if pygame.mouse.get_focused(): # Only process mouse if grabbed
        dx, dy = pygame.mouse.get_rel()
        camera_yaw += dx * MOUSE_SENSITIVITY
        camera_pitch += dy * MOUSE_SENSITIVITY
        camera_pitch = max(-89.0, min(89.0, camera_pitch))

    return control_input # 返回控制桿狀態用於繪圖

# --- 主迴圈 ---
def main():
    global SCREEN_WIDTH, SCREEN_HEIGHT, camera_yaw, camera_pitch, time_since_last_check, show_ground, loop_track   # Allow modification # 允許修改全域變數

    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), DOUBLEBUF | OPENGL)
    pygame.display.set_caption("簡易 3D 電車模擬器")
    pygame.mouse.set_visible(False) # 隱藏滑鼠指標
#     pygame.event.set_grab(True)     # 將滑鼠鎖定在視窗內

    init_opengl()

    # Ensure TEXTURE_DIR exists if you use it
    if TEXTURE_DIR and not os.path.exists(TEXTURE_DIR):
        try:
            print(f"創建紋理目錄: {TEXTURE_DIR}")
            os.makedirs(TEXTURE_DIR)
        except OSError as e:
             print(f"無法創建紋理目錄 '{TEXTURE_DIR}': {e}")
        
    print("執行初始場景載入...")
    if load_scene(SCENE_FILE):
         print("初始場景載入成功，預處理軌道...")
         track.preprocess()
         if track.total_length == 0:
               print("警告: 初始軌道長度為 0。")
    else:
        print("初始場景載入失敗。可能是檔案不存在或格式錯誤。")
        # last_mtime is already 0.0
    



    clock = pygame.time.Clock()
    running = True

    while running:
        dt = clock.tick(60) / 1000.0 # 獲取每幀時間差 (秒)
        time_since_last_check += dt

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                # --- Ground Toggle ---
                if event.key == pygame.K_g:
                    show_ground = not show_ground
                    print(f"地面顯示: {'啟用' if show_ground else '禁用'}")
                # --- Track Loop Toggle ---
                if event.key == pygame.K_l:
                    loop_track = not loop_track
                    print(f"軌道循環: {'啟用' if loop_track else '禁用'}")
                # --- Mouse Grab Toggle ---
                if event.key == pygame.K_TAB:
                    if pygame.event.get_grab():
                         pygame.event.set_grab(False)
                         pygame.mouse.set_visible(True)
                    else:
                         pygame.event.set_grab(True)
                         pygame.mouse.set_visible(False)
                    
                # --- Manual Reload (Optional) ---
                if event.key == pygame.K_r:
                   print("手動觸發場景重新載入...")
                   check_and_reload_scene()
                   time_since_last_check = 0 # Reset check timer
            if event.type == pygame.MOUSEWHEEL: # 添加滾輪控制速度 (可選)
                global tram_speed
                tram_speed += event.y * 0.5 # 滾輪向上增加速度
            # --- Handle window resizing ---
            if event.type == pygame.VIDEORESIZE:
                SCREEN_WIDTH, SCREEN_HEIGHT = event.w, event.h
                glViewport(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT)
                glMatrixMode(GL_PROJECTION)
                glLoadIdentity()
                gluPerspective(45, (SCREEN_WIDTH / SCREEN_HEIGHT), 0.1, GROUND_SIZE * 2.5)
                glMatrixMode(GL_MODELVIEW)

        # --- Check for scene file changes periodically ---
        if time_since_last_check >= CHECK_INTERVAL:
            check_and_reload_scene()
            time_since_last_check = 0.0 # Reset timer

        # 更新遊戲狀態
        control_level = update(dt)

        # --- 渲染 ---
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity() # 重置模型視圖矩陣

        # 獲取當前電車在軌道上的位置和方向
        tram_pos, tram_tangent = track.get_position_and_tangent(tram_distance)
        eye_pos = (tram_pos[0], tram_pos[1] + CAMERA_HEIGHT, tram_pos[2])

        # --- 設定攝影機 ---
        # 方法1: 使用 gluLookAt (如果不需要相對電車的自由觀察，更簡單)
        # look_at_point = (eye_pos[0] + tram_tangent[0],
        #                  eye_pos[1] + tram_tangent[1], # 通常為 0
        #                  eye_pos[2] + tram_tangent[2])
        # gluLookAt(eye_pos[0], eye_pos[1], eye_pos[2], # 眼睛位置
        #           look_at_point[0], look_at_point[1], look_at_point[2], # 看向的點
        #           0, 1, 0) # 上方向向量

        # 方法2: 使用 glTranslate / glRotate (實現滑鼠自由觀察)
        # Calculate track angle (handle potential zero tangent)
        if abs(tram_tangent[0]) > 1e-6 or abs(tram_tangent[2]) > 1e-6:
            track_angle_rad = math.atan2(tram_tangent[0], tram_tangent[2]) # Z is forward, X is right
            track_angle_deg = 180-math.degrees(track_angle_rad)
        else:
            track_angle_deg = 0 # Default angle if tangent is zero

        # 4. Apply mouse pitch (up/down look) FIRST in the code.
        #    This rotates the coordinate system around its *local* X-axis before other rotations.
        glRotatef(camera_pitch, 1, 0, 0)

        # 3. Apply mouse yaw (left/right look) SECOND.
        #    This rotates the coordinate system around its *local* Y-axis.
        glRotatef(camera_yaw, 0, 1, 0)

        # 3. 旋轉視角以匹配電車方向
        glRotatef(track_angle_deg, 0, 1, 0)

        # 4. 將世界平移到攝影機位置
        glTranslatef(-eye_pos[0], -eye_pos[1], -eye_pos[2])

        # --- 繪製世界 ---
        draw_scene()

        # --- 繪製駕駛艙 (在所有世界物體之後，但在 flip 之前) ---
        # 為了讓駕駛艙元素固定，我們需要在應用視角變換 *之前* 保存矩陣，
        # 或者在繪製完世界後，重置矩陣並繪製 HUD。
        # 這裡採用後者（雖然 cabin.py 裡畫法需要調整才能完美固定）
        # **注意:** cabin.py 中的繪製方式是畫在攝影機近處的世界座標中，
        #         所以它會跟隨視角移動，但不會跟隨世界移動。
        #         要完全固定的 HUD 需要正交投影。
        # 我們先在模型視圖變換的最後階段調用它
        draw_cabin_elements(control_level)


        pygame.display.flip() # 交換緩衝區顯示

    pygame.quit()
    sys.exit()

if __name__ == '__main__':
    # Ensure global camera angles start at 0 before main loop
    camera_yaw = 0.0
    camera_pitch = 0.0
    main()