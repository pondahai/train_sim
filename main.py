# main.py
import pygame
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *
import time
import sys
import os # 用於檢查檔案修改時間
import numpy as np
import numpy as math
# import math

# --- 專案模組 ---
import scene_parser
import texture_loader
import renderer
from camera import Camera
from tram import Tram

import cProfile
import pstats

# profilier enable
profiler = cProfile.Profile()
profiler.enable()

# --- 設定 ---
SCREEN_WIDTH = 1200
SCREEN_HEIGHT = 600
TARGET_FPS = 60
SCENE_CHECK_INTERVAL = 2.0 # 秒，檢查 scene.txt 更新的頻率

# --- 全域字體 (在 main 之外或內部皆可) ---
hud_font = None

def main():
    global hud_font # 引用全域字體變數    
    # --- Pygame 初始化 ---
    pygame.init()
    pygame.font.init() # <-- 新增：初始化字體模組    
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), DOUBLEBUF | OPENGL)
    pygame.display.set_caption("簡易 3D 電車模擬器")
    pygame.mouse.set_visible(False) # 隱藏系統滑鼠指標
    pygame.event.set_grab(False)     # 鎖定滑鼠在視窗內

    # --- 載入字體 ---
    try:
        # 嘗試使用系統預設字體，大小為 24
        hud_font = pygame.font.SysFont(None, 24)
        print("HUD 字體已載入。")
    except Exception as e:
        print(f"警告：無法載入系統預設字體，HUD 將無法顯示文字: {e}")
        # 可以選擇載入一個後備的 .ttf 檔案
        # try:
        #     hud_font = pygame.font.Font("path/to/your/font.ttf", 24)
        # except:
        #      hud_font = None # 確保 hud_font 有定義

    # --- 初始化依賴 ---
    scene_parser.set_texture_loader(texture_loader) # Pass texture_loader
    scene_parser.set_renderer_module(renderer)      # <<<--- NEW: Pass renderer module
    renderer.init_renderer() # Initialize renderer (loads common textures, sets GL state)

     # *** 將字體傳遞給渲染器 ***
    if hud_font:
        renderer.set_hud_font(hud_font) # This also tries to create grid font
    else:
        print("警告: HUD 字體未載入，坐標和網格標籤顯示將不可用。")

    # --- 載入場景 ---
    scene = None # Initialize scene variable
    # Initial load, force it.
    if scene_parser.load_scene(force_reload=True):
        scene = scene_parser.get_current_scene()
        # Initial map texture load is now handled within load_scene calling renderer.update_map_texture
        if scene and scene.track:
             print("Initial load successful, creating track buffers...")
             scene.track.create_all_segment_buffers()
        print("初始場景載入成功。")
    else:
        print("初始場景載入失敗，請檢查 scene.txt。場景將為空。")
        scene = scene_parser.get_current_scene() # Get the (likely empty) scene

    # --- 創建物件 ---
    tram_instance = Tram(scene.track) # Pass the initial track (might be empty)
    # Set tram start position based on scene file or default
#     tram_instance.position = np.copy(scene.start_position)
#     tram_instance.distance_on_track = 0.0 # Assume start pos corresponds to distance 0
    # Set initial tram orientation based on start angle
#     start_angle_rad = math.radians(scene.start_angle_deg)
    # Correct forward vector calculation: Y rotation -> XZ plane
#     tram_instance.forward_vector_xz = (math.sin(start_angle_rad), math.cos(start_angle_rad)) # sin for X, cos for Z if angle is rotation from +Z
    # If angle is rotation from +X: (cos(angle), sin(angle))
    # Let's assume angle in scene.txt is from +Z axis (like atan2(x,z)) for consistency?
    # Or maybe angle from +X axis (like atan2(z,x))? Check scene_parser...
    # scene_parser uses 0 angle = +X axis. So forward vector is (cos, sin).
#     tram_instance.forward_vector_xz = (math.cos(start_angle_rad), math.sin(start_angle_rad))
#     print(f"Tram initial pos: {tram_instance.position}, angle: {scene.start_angle_deg} deg, forward: {tram_instance.forward_vector_xz}")


    camera_instance = Camera()

    # --- 遊戲狀態 ---
    running = True
    clock = pygame.time.Clock()
    last_scene_check_time = time.time()
    show_ground_flag = False
    show_minimap = True # <-- 新增：小地圖顯示狀態
    show_coordinates = False # <-- 新增：坐標顯示狀態，預設關閉

    # --- 主迴圈 ---
    while running:
        dt = clock.tick(TARGET_FPS) / 1000.0 # 每幀時間 (秒)
        # Avoid huge dt if lagging or paused
        dt = min(dt, 0.1)

        # --- 事件處理 ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    # Toggle mouse lock first, then quit if already unlocked
                    if camera_instance.mouse_locked:
                        camera_instance.set_mouse_lock(False)
                        pygame.mouse.set_visible(True)
                        pygame.event.set_grab(False)
                    else:
                        running = False
                elif event.key == pygame.K_g:
                    show_ground_flag = not show_ground_flag
                elif event.key == pygame.K_l:
                    tram_instance.toggle_looping()
                elif event.key == pygame.K_TAB: # Explicitly toggle mouse lock
                    lock_state = not camera_instance.mouse_locked
                    print(f"lock_state: {lock_state}")
                    camera_instance.set_mouse_lock(lock_state)
                    pygame.mouse.set_visible(not lock_state)
                    pygame.event.set_grab(lock_state)
                elif event.key == pygame.K_r:
                     print("手動觸發場景重新載入...")
                     # scene_parser.load_scene now handles texture cache clear and map update call
                     if scene_parser.load_scene(force_reload=True):
                         scene = scene_parser.get_current_scene()
                         if scene and scene.track:
                             print("Manual reload successful, creating track buffers...")
                             scene.track.create_all_segment_buffers()
                         # Reset tram
                         tram_instance.track = scene.track if scene else None                         # tram_instance.distance_on_track = 0.0
                         # tram_instance.current_speed = 0.0
                         tram_instance.position = np.copy(scene.start_position)
                         start_angle_rad = math.radians(scene.start_angle_deg)
                         tram_instance.forward_vector_xz = (math.cos(start_angle_rad), math.sin(start_angle_rad))
                         # camera_instance might need reset if desired
                         print("場景已手動重新載入並重設電車。")
                     else:
                         print("手動重新載入失敗。")
                         # scene might be empty now if load failed
                         scene = scene_parser.get_current_scene()
                         tram_instance.track = scene.track if scene else None
                elif event.key == pygame.K_m:
                    show_minimap = not show_minimap
                    print(f"小地圖: {'開啟' if show_minimap else '關閉'}")
                elif event.key == pygame.K_i:
                    show_coordinates = not show_coordinates
                    print(f"坐標顯示: {'開啟' if show_coordinates else '關閉'}")
                elif event.key == pygame.K_PAGEUP:
                    renderer.zoom_minimap(1 / renderer.MINIMAP_ZOOM_FACTOR) # Zoom In
                elif event.key == pygame.K_PAGEDOWN:
                    renderer.zoom_minimap(renderer.MINIMAP_ZOOM_FACTOR)    # Zoom Out

            elif event.type == pygame.MOUSEBUTTONDOWN:
                 # If mouse is not locked, lock it on click
                 if not camera_instance.mouse_locked and event.button == 1: # Left click
                     print("mouse")
                     camera_instance.set_mouse_lock(True)
                     pygame.mouse.set_visible(False)
                     pygame.event.set_grab(True)

            elif event.type == pygame.MOUSEWHEEL:
                tram_instance.adjust_speed(event.y) # event.y is scroll amount

            elif event.type == pygame.MOUSEMOTION:
                # Only update camera angles if mouse is locked
                if camera_instance.mouse_locked:
                    dx, dy = event.rel
                    camera_instance.update_angles(dx, dy)

        # --- 鍵盤持續按下處理 ---
        keys = pygame.key.get_pressed()
        # Only control tram if mouse is locked (or define alternative controls)
        if camera_instance.mouse_locked:
            if keys[K_w] or keys[K_UP]:
                tram_instance.accelerate()
            if keys[K_s] or keys[K_DOWN]:
                tram_instance.brake()
        # else: # Maybe allow keyboard control even if mouse unlocked?
        #     if keys[K_w] or keys[K_UP]: tram_instance.accelerate()
        #     if keys[K_s] or keys[K_DOWN]: tram_instance.brake()


        # --- 遊戲邏輯更新 ---
        tram_instance.update(dt)
        camera_instance.update_position_orientation(tram_instance.position, tram_instance.forward_vector_xz)

        # --- 定期檢查場景檔案更新 ---
        current_time = time.time()
        if current_time - last_scene_check_time > SCENE_CHECK_INTERVAL:
            if scene_parser.load_scene(): # load_scene 會自行判斷是否需要重載
                scene = scene_parser.get_current_scene()
                # *** FIX: Create buffers AFTER successful auto reload ***
                if scene and scene.track:
                    print("Auto reload successful, creating track buffers...")
                    scene.track.create_all_segment_buffers()
                # Update tram track reference
                tram_instance.track = scene.track if scene else None
                # 可以選擇是否重置電車位置
                # tram_instance.distance_on_track = 0.0
                print("場景自動重新載入完成。")
            last_scene_check_time = current_time


        # --- OpenGL 渲染 ---
        # Clear buffers
        glClearColor(0.5, 0.7, 1.0, 1.0) # Sky blue background
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        # 設定投影矩陣
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(45, (SCREEN_WIDTH / SCREEN_HEIGHT), 0.1, renderer.GROUND_SIZE * 2) # 調整視角和剪裁平面

        # 設定模型視圖矩陣
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

        # 應用攝影機視角 (gluLookAt)
        camera_instance.apply_view()

        # --- 繪製場景 ---
        renderer.draw_ground(show_ground_flag)
        if scene and scene.track: # Check if scene and track exist
            renderer.draw_track(scene.track)
        renderer.draw_scene_objects(scene)

        # --- 繪製電車駕駛艙 (在世界坐標中，跟隨電車) ---
        # 注意：這部分繪製必須在設定好視圖之後，作為世界的一部分
        renderer.draw_tram_cab(tram_instance, camera_instance)

        # --- 渲染 HUD (小地圖) --- <-- 新增：繪製小地圖
        if show_minimap:
            renderer.draw_minimap(scene, tram_instance, SCREEN_WIDTH, SCREEN_HEIGHT)

        if show_coordinates and hud_font: # Check font loaded
             renderer.draw_coordinates(tram_instance.position, SCREEN_WIDTH, SCREEN_HEIGHT)


        # --- 交換緩衝區顯示 ---
        pygame.display.flip()

    # --- 清理 ---
    print("正在退出...")
    if scene and scene.track:
         scene.track.clear()
    if 'scene' in locals() and scene and scene.track: # 確保 scene 和 track 存在
         scene.track.clear() # 清理最後加載的軌道資源
    # Explicitly clear texture cache including map texture?
    # texture_loader.clear_texture_cache() # scene_parser calls this on load/reload
    if renderer:
        renderer.clear_cached_map_texture() # Clean up map texture specifically
        
# profiler disable
    print("profiler,disable()")
    profiler.disable()
    stats = pstats.Stats(profiler).sort_stats('cumulative') # 按累積時間排序
    stats.print_stats(20) # 打印最耗時的 20 個函數
    # stats.dump_stats('profile_results.prof') # 保存結果供其他工具分析

    pygame.font.quit() # Cleanup font module
    pygame.quit()
    sys.exit()

if __name__ == '__main__':
    # Ensure running from script's directory for relative paths
    try:
        os.chdir(os.path.dirname(os.path.abspath(__file__)))
        print(f"工作目錄設定為: {os.getcwd()}")
    except Exception as e:
        print(f"無法更改工作目錄: {e}")
    main()

