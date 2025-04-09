# main.py
import pygame
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *
import time
import sys
import os # 用於檢查檔案修改時間

# --- 專案模組 ---
import scene_parser
import texture_loader
import renderer
from camera import Camera
from tram import Tram

# --- 設定 ---
SCREEN_WIDTH = 1024
SCREEN_HEIGHT = 720
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
    except Exception as e:
        print(f"警告：無法載入系統預設字體，HUD 將無法顯示文字: {e}")
        # 可以選擇載入一個後備的 .ttf 檔案
        # try:
        #     hud_font = pygame.font.Font("path/to/your/font.ttf", 24)
        # except:
        #      hud_font = None # 確保 hud_font 有定義

    # --- 初始化依賴 ---
    scene_parser.set_texture_loader(texture_loader) # 將 texture_loader 傳遞給 scene_parser
    renderer.init_renderer() # 初始化渲染器 (載入基本紋理等)

     # *** 將字體傳遞給渲染器 ***
    if hud_font:
        renderer.set_hud_font(hud_font)
    else:
        print("警告: HUD 字體未載入，坐標顯示將不可用。")

    # --- 載入場景 ---
    if not scene_parser.load_scene(force_reload=True):
        print("初始場景載入失敗，請檢查 scene.txt")
        # 即使失敗也繼續，但場景會是空的
    scene = scene_parser.get_current_scene()

    # --- 創建物件 ---
    tram_instance = Tram(scene.track) # 將解析出的軌道傳給電車
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

        # --- 事件處理 ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_g:
                    show_ground_flag = not show_ground_flag
                elif event.key == pygame.K_l:
                    tram_instance.toggle_looping()
                elif event.key == pygame.K_TAB:
                    lock_state = not camera_instance.mouse_locked
                    camera_instance.set_mouse_lock(lock_state)
                    pygame.mouse.set_visible(lock_state)
                    pygame.event.set_grab(not lock_state)
                elif event.key == pygame.K_r:
                     print("手動觸發場景重新載入...")
                     if scene_parser.load_scene(force_reload=True):
                         scene = scene_parser.get_current_scene()
                         # 重設電車和攝影機到新軌道起點 (可選)
                         tram_instance.track = scene.track # 更新電車引用的軌道
                         tram_instance.distance_on_track = 0.0
                         # camera_instance.reset() # 如果有重設方法
                         print("場景已手動重新載入.")
                     else:
                         print("手動重新載入失敗.")
                elif event.key == pygame.K_m: # <-- 新增：處理 M 鍵
                    show_minimap = not show_minimap
                    print(f"小地圖: {'開啟' if show_minimap else '關閉'}")
                elif event.key == pygame.K_i: # <-- 新增：處理 I 鍵
                    show_coordinates = not show_coordinates
                    print(f"坐標顯示: {'開啟' if show_coordinates else '關閉'}")
                elif event.key == pygame.K_PAGEUP:
                    renderer.zoom_minimap(1 / renderer.MINIMAP_ZOOM_FACTOR) # 放大 (範圍變小)
                elif event.key == pygame.K_PAGEDOWN:
                    renderer.zoom_minimap(renderer.MINIMAP_ZOOM_FACTOR)    # 縮小 (範圍變大)
                    
            elif event.type == pygame.MOUSEWHEEL:
                tram_instance.adjust_speed(event.y) # event.y 是滾動方向和幅度

            elif event.type == pygame.MOUSEMOTION:
                if not camera_instance.mouse_locked:
                    dx, dy = event.rel
                    camera_instance.update_angles(dx, dy)

        # --- 鍵盤持續按下處理 ---
        keys = pygame.key.get_pressed()
        if keys[K_w] or keys[K_UP]:
            tram_instance.accelerate()
        if keys[K_s] or keys[K_DOWN]:
            tram_instance.brake()

        # --- 遊戲邏輯更新 ---
        tram_instance.update(dt)
        camera_instance.update_position_orientation(tram_instance.position, tram_instance.forward_vector_xz)

        # --- 定期檢查場景檔案更新 ---
        current_time = time.time()
        if current_time - last_scene_check_time > SCENE_CHECK_INTERVAL:
            if scene_parser.load_scene(): # load_scene 會自行判斷是否需要重載
                scene = scene_parser.get_current_scene()
                 # 如果場景成功重載，更新電車的軌道引用
                tram_instance.track = scene.track
                # 可以選擇是否重置電車位置
                # tram_instance.distance_on_track = 0.0
            last_scene_check_time = current_time


        # --- OpenGL 渲染 ---
        # 清除緩衝區
        glClearColor(0.5, 0.7, 1.0, 1.0) # 天空藍背景
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
        renderer.draw_track(scene.track)
        renderer.draw_scene_objects(scene)

        # --- 繪製電車駕駛艙 (在世界坐標中，跟隨電車) ---
        # 注意：這部分繪製必須在設定好視圖之後，作為世界的一部分
        renderer.draw_tram_cab(tram_instance, camera_instance)

        # --- 渲染 HUD (小地圖) --- <-- 新增：繪製小地圖
        if show_minimap:
            renderer.draw_minimap(scene, tram_instance, SCREEN_WIDTH, SCREEN_HEIGHT)

        # 坐標顯示 <-- 新增
        if show_coordinates and hud_font: # 確保字體已載入
             renderer.draw_coordinates(tram_instance.position, SCREEN_WIDTH, SCREEN_HEIGHT)


        # --- 交換緩衝區顯示 ---
        pygame.display.flip()

    # --- 清理 ---
    pygame.font.quit() # <-- 新增：清理字體模組
    pygame.quit()
    sys.exit()

if __name__ == '__main__':
    # 確保在主程式執行目錄下尋找資源
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    main()