# main.py
import pygame
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *
import time
import sys
import os # Keep for checking file modification time and path handling
import numpy as np
import numpy as math # Keep consistent
# import math # Original import removed

# --- Project Modules ---
import scene_parser
import texture_loader
import renderer           # Keep for 3D rendering functions
import minimap_renderer # *** NEW: Import the minimap module ***
from camera import Camera
from tram import Tram

import tkinter as tk
from tkinter import filedialog

## Keep profiler if used
# import cProfile
# import pstats
# profiler = cProfile.Profile()
# profiler.enable()


# --- Settings (Keep) ---
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 400
TARGET_FPS = 60
SCENE_CHECK_INTERVAL = 2.0 # Seconds for checking scene.txt updates

# --- Global Font (Keep) ---
hud_font = None

# --- NEW: Global for active background ---
active_background_info = None


def show_context_menu(current_scene_filepath):
    root = tk.Tk()
    root.withdraw() # 隱藏主窗口

    selected_action = None # 用於存儲用戶的選擇
    new_filepath = None

    def on_load_scene():
        nonlocal selected_action, new_filepath
        selected_action = "load_scene"
        # 暫時解除 Pygame 的滑鼠捕獲，如果有的話
        pygame_mouse_grabbed = pygame.event.get_grab()
        if pygame_mouse_grabbed:
            pygame.event.set_grab(False)
            pygame.mouse.set_visible(True)

        # 確定初始目錄
        initial_dir = os.getcwd()
        if current_scene_filepath and os.path.exists(os.path.dirname(current_scene_filepath)):
            initial_dir = os.path.dirname(current_scene_filepath)
        
        filepath = filedialog.askopenfilename(
            parent=root, # 確保對話框在 tkinter 窗口之上
            title="選擇場景檔案",
            initialdir=initial_dir,
            filetypes=(("場景檔案", "*.txt"), ("所有檔案", "*.*"))
        )
        if filepath:
            new_filepath = filepath
        
        if pygame_mouse_grabbed: # 恢復滑鼠捕獲
            pygame.event.set_grab(True)
            pygame.mouse.set_visible(False) # 如果之前不可見
        
        menu_window.destroy()


    def on_exit_app():
        nonlocal selected_action
        selected_action = "exit"
        menu_window.destroy()

    # 創建一個頂層小窗口作為選單
    menu_window = tk.Toplevel(root)
    menu_window.title("選單")
    menu_window.resizable(False, False)
    # 讓選單窗口置頂，並獲取焦點
    menu_window.attributes('-topmost', True)
    menu_window.grab_set() # 捕獲事件，使其成為模態

    # 計算選單窗口位置 (例如在滑鼠點擊位置附近)
    # 注意：pygame.mouse.get_pos() 是相對於 Pygame 窗口的
    # 我們需要將其轉換為螢幕座標
    screen_x, screen_y = pygame.mouse.get_pos() # 獲取 Pygame 窗口內的滑鼠座標
    # 這一步轉換可能不夠完美，因為 tk.Toplevel 的 geometry 是相對於螢幕的
    # pygame.display.Info() 可以獲取窗口位置，但稍微複雜
    # 簡單起見，先放在螢幕中間或一個固定偏移
    # menu_window.geometry(f"+{root.winfo_screenwidth()//2-50}+{root.winfo_screenheight()//2-30}") # 居中
    # 或者嘗試基於 Pygame 窗口位置（如果能獲取到）
    try:
        # 嘗試獲取 Pygame 窗口在螢幕上的信息 (這部分可能不夠通用或可靠)
        # display_info = pygame.display.get_wm_info() # SDL1
        # display_info = pygame.display.get_window_manager_info() # SDL2 (可能需要特定導入)
        # 更好的方式可能是直接在螢幕中間彈出
        # 或者，讓選單出現在 Pygame 窗口的大致中心
        pygame_win_info = pygame.display.Info()
        px, py = pygame_win_info.current_w // 2, pygame_win_info.current_h // 2 # Pygame 窗口中心
        menu_window.geometry(f"+{px-50}+{py-30}") # 相對螢幕，但定位在 Pygame 窗口中心附近
    except Exception:
        # Fallback to screen center
        menu_window.geometry(f"+{root.winfo_screenwidth()//2-50}+{root.winfo_screenheight()//2-30}")


    load_button = tk.Button(menu_window, text="載入場景 (Load Scene)", command=on_load_scene, width=20)
    load_button.pack(pady=5, padx=10)

    exit_button = tk.Button(menu_window, text="離開 (Exit)", command=on_exit_app, width=20)
    exit_button.pack(pady=5, padx=10)

    menu_window.protocol("WM_DELETE_WINDOW", menu_window.destroy) # 處理點擊關閉按鈕
    
    # 等待選單窗口關閉
    root.wait_window(menu_window)
    
    try:
        root.destroy() # 銷毀隱藏的根窗口
    except tk.TclError:
        pass # 可能已經被銷毀

    if selected_action == "load_scene":
        return selected_action, new_filepath
    elif selected_action == "exit":
        return selected_action, None
    return None, None # 沒有選擇或關閉了選單

def main():
    global hud_font, active_background_info # <--- Add active_background_info

    # --- Pygame Initialization (Keep) ---
    pygame.init()
    pygame.font.init() # Initialize font module
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), DOUBLEBUF | OPENGL)
    pygame.display.set_caption("簡易 3D 電車模擬器")
    pygame.mouse.set_visible(False)
    pygame.event.set_grab(False) # Start with mouse unlocked

    # --- Load Font (Keep) ---
    try:
        hud_font = pygame.font.SysFont(None, 24)
        print("HUD 字體已載入。")
    except Exception as e:
        print(f"警告：無法載入系統預設字體，HUD 將無法顯示文字: {e}")
        hud_font = None

    # --- Initialize Dependencies (Keep) ---
    scene_parser.set_texture_loader(texture_loader)
    renderer.init_renderer() # Initialize main 3D renderer states and common textures

    ### --- START OF MODIFICATION: Initialize Hill Shader ---
    if hasattr(renderer, 'init_hill_shader'):
        print("正在初始化山丘著色器...")
        renderer.init_hill_shader()
        if renderer._hill_shader_program_id is None: # 檢查是否成功
            print("警告: 山丘著色器初始化失敗！山丘可能無法正常渲染。")
    else:
        print("警告: renderer 模塊中未找到 init_hill_shader 函數。")
    ### --- END OF MODIFICATION ---

    # Pass font to main renderer and minimap renderer
    if hud_font:
        renderer.set_hud_font(hud_font)
        # Pass the created grid/coord font from renderer to minimap_renderer
        if renderer.grid_label_font:
            minimap_renderer.set_grid_label_font(renderer.grid_label_font)
        if renderer.coord_label_font:
            minimap_renderer.set_coord_label_font(renderer.coord_label_font)
    else:
        print("警告: HUD 字體未載入，部分 UI 顯示將不可用。")

    # --- Load Initial Scene and Perform Post-Load Steps ---
    scene = None
    if scene_parser.load_scene(force_reload=True): # Initial load
        scene = scene_parser.get_current_scene()
        if scene:
            # --- NEW: Set initial background ---
            active_background_info = scene.initial_background_info
            print(f"初始背景設定為: {active_background_info}")

            if scene.track:
                print("初始場景載入成功，創建軌道緩衝區...")
                scene.track.create_all_segment_buffers() # Create VBOs for the loaded track

            ### --- START OF MODIFICATION: Create Hill Buffers for Initial Scene ---
            if hasattr(scene, 'hills') and scene.hills and renderer._hill_shader_program_id:
                print("正在為初始場景的山丘創建渲染緩衝區...")
                new_hills_list_init = []
                for i, hill_entry in enumerate(scene.hills):
                    # create_hill_buffers 返回 (修改後的 hill_data_tuple, success_flag)
                    # 而 hill_entry 是 (line_id, hill_data_tuple)
                    original_line_id, original_hill_data = hill_entry
                    modified_hill_data, success = renderer.create_hill_buffers(hill_entry)
                    if success:
                        new_hills_list_init.append((original_line_id, modified_hill_data))
                    else:
                        # 如果創建失敗，保留原始數據（不含VBO/VAO ID）
                        # 或者可以選擇從列表中移除該山丘，或記錄錯誤
                        print(f"警告: 為山丘 (行: {original_line_id}) 創建緩衝區失敗。")
                        new_hills_list_init.append(hill_entry) # 保留原始條目
                scene.hills = new_hills_list_init # 更新場景中的列表
                print("初始場景山丘緩衝區創建完成。")
            elif renderer._hill_shader_program_id is None and hasattr(scene, 'hills') and scene.hills:
                print("警告: 山丘著色器未就緒，跳過為初始場景山丘創建緩衝區。")
            ### --- END OF MODIFICATION ---
            # --- 新增: 為初始場景的 Buildings 創建緩衝區 ---
            if hasattr(scene, 'buildings') and scene.buildings and renderer._building_shader_program_id:
                print("正在為初始場景的 Buildings 創建渲染緩衝區...")
                new_buildings_list_init = []
                for i, bldg_entry in enumerate(scene.buildings):
                    line_id, bldg_data_tuple = bldg_entry
                    modified_bldg_data, success = renderer.create_building_buffers(bldg_entry)
                    if success:
                        new_buildings_list_init.append((line_id, modified_bldg_data))
                    else:
                        new_buildings_list_init.append(bldg_entry) # 保留原始條目以防創建失敗
                scene.buildings = new_buildings_list_init
                print("初始場景 Buildings 緩衝區創建完成。")
            elif renderer._building_shader_program_id is None and hasattr(scene, 'buildings') and scene.buildings:
                 print("警告: Building 著色器未就緒，跳過為初始場景 Buildings 創建緩衝區。")
            # --- 結束新增 ---


            # Bake minimap AFTER successful scene load and track buffer creation
            minimap_renderer.bake_static_map_elements(scene)
            print("初始小地圖已烘焙。")
    else:
        print("初始場景載入失敗，請檢查 scene.txt。場景將為空。")
        scene = scene_parser.get_current_scene() # Get the (likely empty) scene
        active_background_info = None # No background if scene failed
        minimap_renderer.bake_static_map_elements(scene) # Bake with empty scene data


    # --- Create Objects (Keep tram/camera creation) ---
    tram_instance = Tram(scene.track if scene else None)
    if scene: # Check if scene loaded successfully
        tram_instance.position = np.copy(scene.start_position)
        start_angle_rad = math.radians(scene.start_angle_deg)
        tram_instance.forward_vector_xz = (math.cos(start_angle_rad), math.sin(start_angle_rad))
        tram_instance.distance_on_track = 0.0 # Reset distance explicitly
        print(f"Tram initial pos: {tram_instance.position}, angle: {scene.start_angle_deg} deg, forward: {tram_instance.forward_vector_xz}")
    else:
        tram_instance.position = np.array([0.0, 0.0, 0.0])
        tram_instance.forward_vector_xz = (1.0, 0.0) # Default forward +X
        tram_instance.distance_on_track = 0.0

    camera_instance = Camera()

    # --- Game State (Keep) ---
    running = True
    clock = pygame.time.Clock()
    last_scene_check_time = time.time()
    show_ground_flag = False # Default ground to not visible
    show_minimap = True
    show_hud_info = False
    show_cab = True

    # --- Global variable to store current scene file path for the menu ---
    current_loaded_scene_file = "scene.txt" # Initialize with default

    # --- Main Loop ---
    while running:
        dt = clock.tick(TARGET_FPS) / 1000.0
        dt = min(dt, 0.1) # Prevent large dt spikes

        # --- Event Handling (Minor Modifications) ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
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
                elif event.key == pygame.K_TAB:
                    lock_state = not camera_instance.mouse_locked
                    camera_instance.set_mouse_lock(lock_state)
                    pygame.mouse.set_visible(not lock_state)
                    pygame.event.set_grab(lock_state)
                elif event.key == pygame.K_r:
                    print("手動觸發場景重新載入...")

                    ### --- START OF MODIFICATION: Cleanup Old Scene Resources FIRST ---
                    if scene: # 確保舊的 scene 對象存在
                        # 清理舊場景的山丘緩衝區
                        if hasattr(scene, 'hills') and scene.hills:
                            if hasattr(renderer, 'cleanup_all_hill_buffers'):
                                print("重新加載前，清理舊場景的山丘緩衝區...")
                                renderer.cleanup_all_hill_buffers(scene.hills)
                            else:
                                print("警告: renderer 模塊中未找到 cleanup_all_hill_buffers 函數。")
                        
                        # （可選）如果軌道等其他資源也需要在 load_scene 前清理，也放在這裡
                        # 例如: if scene.track: scene.track.clear()
                        # 但通常 load_scene 內部會處理紋理緩存等，軌道緩衝區的創建通常在加載後。
                        # 主要問題是VBO/VAO這種與特定場景實例數據關聯的資源。
                    ### --- END OF MODIFICATION ---
                        # --- 新增: 清理舊 Building 緩衝區 ---
                        if hasattr(scene, 'buildings') and scene.buildings and hasattr(renderer, 'cleanup_all_building_buffers'):
                            renderer.cleanup_all_building_buffers(scene.buildings)
                        # --- 結束新增 ---
                        if scene.track: scene.track.clear() # 清理軌道緩衝區

                    if scene_parser.load_scene(force_reload=True): # 現在 load_scene 會創建一個全新的 scene
                        scene = scene_parser.get_current_scene() # scene 現在是新加載的對象
                        
                        active_background_info = scene.initial_background_info if scene else None
                        print(f"手動重載後背景設定為: {active_background_info}")

                        if scene and scene.track:
                            print("手動重載成功，為新軌道創建緩衝區...")
                            scene.track.create_all_segment_buffers() # 為新軌道創建

                        ### --- START OF MODIFICATION: Create Hill Buffers for NEWLY Reloaded Scene ---
                        if scene and hasattr(scene, 'hills') and scene.hills and renderer._hill_shader_program_id:
                            print("正在為重新載入的場景的山丘創建渲染緩衝區...")
                            new_hills_list_reload = []
                            for i, hill_entry_reload in enumerate(scene.hills):
                                original_line_id_reload, _ = hill_entry_reload
                                # 確保傳遞的是 hill_entry_reload，而不是舊的 scene 中的數據
                                modified_hill_data_reload, success_reload = renderer.create_hill_buffers(hill_entry_reload)
                                if success_reload:
                                    new_hills_list_reload.append((original_line_id_reload, modified_hill_data_reload))
                                else:
                                    print(f"警告: 為重新載入的山丘 (行: {original_line_id_reload}) 創建緩衝區失敗。")
                                    new_hills_list_reload.append(hill_entry_reload)
                            scene.hills = new_hills_list_reload # 更新新場景的 hills 列表
                            print("重新載入場景山丘緩衝區創建完成。")
                        elif renderer._hill_shader_program_id is None and hasattr(scene, 'hills') and scene.hills:
                            print("警告: 山丘著色器未就緒，跳過為重新載入場景山丘創建緩衝區。")
                        ### --- END OF MODIFICATION ---
                        # --- 新增: 為重載場景的 Buildings 創建緩衝區 ---
                        if scene and hasattr(scene, 'buildings') and scene.buildings and renderer._building_shader_program_id:
                            print("正在為重載場景的 Buildings 創建渲染緩衝區...")
                            new_buildings_list_reload = []
                            for i, bldg_entry_reload in enumerate(scene.buildings):
                                line_id, _ = bldg_entry_reload
                                modified_bldg_data, success = renderer.create_building_buffers(bldg_entry_reload)
                                if success: new_buildings_list_reload.append((line_id, modified_bldg_data))
                                else: new_buildings_list_reload.append(bldg_entry_reload)
                            scene.buildings = new_buildings_list_reload
                            print("重載場景 Buildings 緩衝區創建完成。")
                        # --- 結束新增 ---
                                 
                        minimap_renderer.bake_static_map_elements(scene)
                        print("手動重載後小地圖已烘焙。")

                        # Reset tram based on NEW scene data
                        tram_instance.track = scene.track if scene else None
                        if scene:
                            tram_instance.current_speed = 0.0 # Reset speed
                        else: 
                            tram_instance.position = np.array([0.0, 0.0, 0.0])
                            tram_instance.forward_vector_xz = (1.0, 0.0)
                            tram_instance.distance_on_track = 0.0
                            tram_instance.current_speed = 0.0
                        print("場景已手動重新載入並重設電車。")
                    else:
                        print("手動重新載入失敗。")
                        # scene 變量可能仍然指向舊的場景，或者 load_scene 內部可能將其設為空
                        # 為了安全，如果 load_scene 失敗，最好也 clear 一下舊的 scene （如果還存在）
                        if scene and hasattr(scene, 'hills') and scene.hills: # 如果 scene 還是舊的
                             if hasattr(renderer, 'cleanup_all_hill_buffers'):
                                 renderer.cleanup_all_hill_buffers(scene.hills)
                        scene = scene_parser.get_current_scene() # 獲取 load_scene 失敗後可能的空場景
                        active_background_info = scene.initial_background_info if scene else None
                        tram_instance.track = scene.track if scene else None
                        minimap_renderer.bake_static_map_elements(scene)

                elif event.key == pygame.K_c: show_cab = not show_cab
                elif event.key == pygame.K_m: show_minimap = not show_minimap; print(f"小地圖: {'開啟' if show_minimap else '關閉'}")
                elif event.key == pygame.K_i: show_hud_info = not show_hud_info; print(f"資訊顯示: {'開啟' if show_hud_info else '關閉'}")
                elif event.key == pygame.K_PAGEUP: minimap_renderer.zoom_simulator_minimap(1 / minimap_renderer.MINIMAP_ZOOM_FACTOR)
                elif event.key == pygame.K_PAGEDOWN: minimap_renderer.zoom_simulator_minimap(minimap_renderer.MINIMAP_ZOOM_FACTOR)

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1: # 左鍵
                    if not camera_instance.mouse_locked and event.button == 1:
                         camera_instance.set_mouse_lock(True); pygame.mouse.set_visible(False); pygame.event.set_grab(True)
                elif event.button == 3: # 右鍵
                    # 釋放滑鼠鎖定（如果有的話），以便tkinter窗口能正常工作
                    mouse_was_locked = camera_instance.mouse_locked
                    if mouse_was_locked:
                        camera_instance.set_mouse_lock(False)
                        pygame.mouse.set_visible(True)
                        pygame.event.set_grab(False)

                    action, filepath_from_menu = show_context_menu(current_loaded_scene_file)

                    if mouse_was_locked: # 恢復滑鼠鎖定
                        # 確保在恢復前 camera 實例仍然有效
                        if camera_instance: # 簡單檢查
                            camera_instance.set_mouse_lock(True)
                            pygame.mouse.set_visible(False)
                            pygame.event.set_grab(True)
                    
                    if action == "load_scene" and filepath_from_menu:
                        print(f"選單選擇：載入場景檔案 '{filepath_from_menu}'")
                        
                        # --- 1. 清理舊場景的 OpenGL 資源 ---
                        if scene: # 確保舊的 scene 對象存在
                            print(f"清理舊場景 '{current_loaded_scene_file}' 的資源...")
                            
                            # --- a. 清理舊山丘緩衝區 ---
                            if hasattr(scene, 'hills') and scene.hills:
                                if hasattr(renderer, 'cleanup_all_hill_buffers'):
                                    print("清理舊場景的山丘緩衝區...")
                                    renderer.cleanup_all_hill_buffers(scene.hills)
                                else:
                                    print("警告: renderer 模塊中未找到 cleanup_all_hill_buffers。")
                            # --- 新增: 清理舊 Building 緩衝區 ---
                            if hasattr(scene, 'buildings') and scene.buildings and hasattr(renderer, 'cleanup_all_building_buffers'):
                                renderer.cleanup_all_building_buffers(scene.buildings)
                            # --- 結束新增 ---
                            
                            # --- b. 清理舊軌道緩衝區 (如果 scene.cleanup_resources 不做這個，或者做得不夠徹底) ---
                            if scene.track: # 確保舊軌道存在
                                print("清理舊場景的軌道緩衝區...")
                                scene.track.clear() # Track.clear() 應處理其內部VBOs

                            # --- c. (可選)調用通用的場景清理 (如果它還做其他事情) ---
                            # 如果 scene.cleanup_resources() 只是簡單的 scene.track.clear()，上面已經做了
                            # if hasattr(scene, 'cleanup_resources'):
                            #     scene.cleanup_resources() 
                            
                            # d. 清理紋理緩存 (load_scene 內部通常會做，但這裡再做一次也無妨，確保徹底)
                            if texture_loader:
                                print("清理紋理緩存...")
                                texture_loader.clear_texture_cache()
                            # 清理天空盒緩存
                            if hasattr(renderer, 'skybox_texture_cache'):
                                for tex_id in renderer.skybox_texture_cache.values():
                                    try:
                                        if glIsTexture(tex_id): glDeleteTextures(1, [tex_id])
                                    except: pass
                                renderer.skybox_texture_cache.clear()

                        # --- 2. 使用 scene_parser 載入新場景數據 ---
                        if scene_parser.load_scene(specific_filepath=filepath_from_menu, force_reload=True):
                            scene = scene_parser.get_current_scene() # 獲取新載入的 scene
                            current_loaded_scene_file = filepath_from_menu
                            
                            active_background_info = scene.initial_background_info if scene else None
                            
                            # --- 3. 為新載入的場景創建軌道緩衝區 ---
                            if scene and scene.track:
                                print(f"場景 '{filepath_from_menu}' 數據已載入，正在創建新軌道緩衝區...")
                                scene.track.create_all_segment_buffers()
                                print("新軌道緩衝區創建完成。")
                            
                            ### --- START OF MODIFICATION: Create Hill Buffers for NEW Scene from Menu ---
                            if scene and hasattr(scene, 'hills') and scene.hills and renderer._hill_shader_program_id:
                                print("正在為通過選單載入的新場景的山丘創建渲染緩衝區...")
                                new_hills_list_menu = []
                                for i, hill_entry_menu in enumerate(scene.hills):
                                    original_line_id_menu, _ = hill_entry_menu
                                    modified_hill_data_menu, success_menu = renderer.create_hill_buffers(hill_entry_menu)
                                    if success_menu:
                                        new_hills_list_menu.append((original_line_id_menu, modified_hill_data_menu))
                                    else:
                                        print(f"警告: 為選單載入的山丘 (行: {original_line_id_menu}) 創建緩衝區失敗。")
                                        new_hills_list_menu.append(hill_entry_menu)
                                scene.hills = new_hills_list_menu # 更新新場景的 hills 列表
                                print("選單載入場景山丘緩衝區創建完成。")
                            elif renderer._hill_shader_program_id is None and hasattr(scene, 'hills') and scene.hills:
                                print("警告: 山丘著色器未就緒，跳過為選單載入場景山丘創建緩衝區。")
                            ### --- END OF MODIFICATION ---
                            # --- 新增: 為選單載入場景的 Buildings 創建緩衝區 ---
                            if scene and hasattr(scene, 'buildings') and scene.buildings and renderer._building_shader_program_id:
                                print("正在為選單載入場景的 Buildings 創建渲染緩衝區...")
                                new_buildings_list_menu_b = []
                                for i, bldg_entry_menu in enumerate(scene.buildings):
                                    line_id, _ = bldg_entry_menu
                                    modified_bldg_data, success = renderer.create_building_buffers(bldg_entry_menu)
                                    if success: new_buildings_list_menu_b.append((line_id, modified_bldg_data))
                                    else: new_buildings_list_menu_b.append(bldg_entry_menu)
                                scene.buildings = new_buildings_list_menu_b
                                print("選單載入場景 Buildings 緩衝區創建完成。")
                            # --- 結束新增 ---
                            
                            minimap_renderer.bake_static_map_elements(scene)
                            print("新場景的小地圖已烘焙。")
                            
                            tram_instance.track = scene.track if scene else None
                            
                            if scene: # 確保 scene 成功加載
                                tram_instance.position = np.copy(scene.start_position)
                                start_angle_rad_main = math.radians(scene.start_angle_deg)
                                tram_instance.forward_vector_xz = (math.cos(start_angle_rad_main), math.sin(start_angle_rad_main))
                                tram_instance.distance_on_track = 0.0
                                tram_instance.current_speed = 0.0
                                pygame.display.set_caption(f"簡易 3D 電車模擬器 - {os.path.basename(filepath_from_menu)}")
                                print(f"場景 '{filepath_from_menu}' 已成功載入並準備就緒。電車已重置。")
                            else: # scene is None after load_scene returned True (異常)
                                print(f"錯誤: scene_parser.load_scene 聲稱成功，但 scene 為 None。")
                                # Fallback to default state
                                tram_instance.position = np.array([0.0, 0.0, 0.0])
                                tram_instance.forward_vector_xz = (1.0, 0.0)
                                tram_instance.distance_on_track = 0.0
                                tram_instance.current_speed = 0.0
                                active_background_info = None
                                minimap_renderer.bake_static_map_elements(scene_parser.get_current_scene()) # 傳遞空場景
                                pygame.display.set_caption("簡易 3D 電車模擬器 - 載入錯誤")
                        else: # scene_parser.load_scene 返回 False
                            print(f"通過選單載入場景 '{filepath_from_menu}' 失敗。模擬器將保留原場景（如果存在）。")
                            # 恢復舊的視窗標題
                            if current_loaded_scene_file and os.path.exists(current_loaded_scene_file): # 確保路徑有效
                                pygame.display.set_caption(f"簡易 3D 電車模擬器 - {os.path.basename(current_loaded_scene_file)}")
                            else: # 如果之前的路徑也無效了，回到預設
                                pygame.display.set_caption("簡易 3D 電車模擬器") 
                    elif action == "exit":
                        print("選單選擇：離開")
                        running = False
                        
            elif event.type == pygame.MOUSEWHEEL: tram_instance.adjust_speed(event.y)
            elif event.type == pygame.MOUSEMOTION:
                if camera_instance.mouse_locked: dx, dy = event.rel; camera_instance.update_angles(dx, dy)

        # --- Keyboard Hold Handling (Keep) ---
        keys = pygame.key.get_pressed()
        if camera_instance.mouse_locked:
            if keys[K_w] or keys[K_UP]: tram_instance.accelerate()
            if keys[K_s] or keys[K_DOWN]: tram_instance.brake()

        # --- Game Logic Update ---
        tram_instance.update(dt)
        camera_instance.update_position_orientation(tram_instance.position, tram_instance.forward_vector_xz)

        # --- NEW: Update Active Background based on Tram Distance ---
        if scene and scene.background_triggers:
            current_dist = tram_instance.distance_on_track
            found_info = scene.initial_background_info # Start with initial/default
            # Iterate through sorted triggers
            for trigger_dist, bg_info in scene.background_triggers: # Assumes sorted
                if current_dist >= trigger_dist:
                    found_info = bg_info # Update to the latest one we've passed
                else:
                    break # No need to check further triggers
            # Only update if the found info is different from the active one
            if found_info != active_background_info:
                 print(f"里程 {current_dist:.2f} 觸發背景變更為: {found_info}")
                 active_background_info = found_info


        # --- Periodic Scene File Check ---
        current_time = time.time()
        if current_time - last_scene_check_time > SCENE_CHECK_INTERVAL:
            # --- 在檢查前，如果 scene 存在，先記錄需要清理的 building 列表 ---
            old_buildings_to_cleanup_auto = list(scene.buildings) if scene and hasattr(scene, 'buildings') else []
            if scene_parser.load_scene(): # load_scene returns True if reloaded
                # --- 清理舊的 building 緩衝區 (如果 scene 被成功重載替換了) ---
                if old_buildings_to_cleanup_auto and hasattr(renderer, 'cleanup_all_building_buffers'):
                     # 這裡假設 load_scene 成功時，scene 已經是新的了，
                     # 所以 old_buildings_to_cleanup_auto 引用的是被替換掉的舊場景的 buildings
                     # 但更安全的方式是，如果 load_scene 內部返回了新的 scene，
                     # 並且我們知道它與舊的不同，才清理舊的。
                     # 為了簡化，我們先假設如果 load_scene 返回 True，就清理 old_buildings_to_cleanup_auto
                     # (這需要保證 scene_parser.load_scene 在返回 True 前，已經更新了全局 current_scene)
                    renderer.cleanup_all_building_buffers(old_buildings_to_cleanup_auto)
                    
                scene = scene_parser.get_current_scene()
                # --- NEW: Update active background on auto-reload ---
                active_background_info = scene.initial_background_info if scene else None
                print(f"自動重載後背景設定為: {active_background_info}")

                if scene and scene.track:
                    print("自動重載成功，創建軌道緩衝區...")
                    scene.track.create_all_segment_buffers()
                    
                # --- 新增: 為自動重載場景的 Buildings 創建緩衝區 ---
                if scene and hasattr(scene, 'buildings') and scene.buildings and renderer._building_shader_program_id:
                    print("正在為自動重載場景的 Buildings 創建渲染緩衝區...")
                    new_buildings_list_auto = []
                    for i, bldg_entry_auto in enumerate(scene.buildings):
                        line_id, _ = bldg_entry_auto
                        modified_bldg_data, success = renderer.create_building_buffers(bldg_entry_auto)
                        if success: new_buildings_list_auto.append((line_id, modified_bldg_data))
                        else: new_buildings_list_auto.append(bldg_entry_auto)
                    scene.buildings = new_buildings_list_auto
                    print("自動重載場景 Buildings 緩衝區創建完成。")
                # --- 結束新增 ---
                    
                    
                minimap_renderer.bake_static_map_elements(scene)
                print("自動重載後小地圖已烘焙。")
                tram_instance.track = scene.track if scene else None # Update tram's track reference
                # Optionally reset tram position? Current code doesn't.
                print("場景自動重新載入完成。")
            last_scene_check_time = current_time


        # --- OpenGL Rendering ---
        # Clear buffers (Set clear color *before* drawing background)
        glClearColor(0.5, 0.7, 1.0, 1.0) # Default Sky blue
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        # Set 3D Projection
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        far_clip = renderer.GROUND_SIZE * 4 if hasattr(renderer, 'GROUND_SIZE') else 1000.0 # Use larger far clip for background
        gluPerspective(45, (SCREEN_WIDTH / SCREEN_HEIGHT), 0.1, far_clip)

        # Set ModelView Matrix
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

        # Apply Camera View (Get camera position *before* applying lookat)
#         camera_pos_for_background = camera_instance.base_position # Use base position for background translation
        camera_instance.apply_view()

        # --- Draw Background (Skybox/Skydome) FIRST ---
        if active_background_info:
            renderer.draw_background(active_background_info, camera_instance, tram_instance)
            # Potentially force depth clear after background if using glDisable(GL_DEPTH_TEST)
            # glClear(GL_DEPTH_BUFFER_BIT) # Uncomment if background uses disable depth test


        # --- Draw 3D Scene (Keep) ---
        renderer.draw_ground(show_ground_flag)
        if scene and scene.track:
            renderer.draw_track(scene.track) # Uses pre-built buffers
        # Pass the scene object, which contains absolute coordinates
        renderer.draw_scene_objects(scene)

        # --- Draw Tram Cab (Keep) ---
        if show_cab:
            # Ensure correct depth testing for the cab
            glEnable(GL_DEPTH_TEST) # Make sure depth test is on for cab
            renderer.draw_tram_cab(tram_instance, camera_instance)

        # --- Draw HUD ---
        if show_minimap:
            minimap_renderer.draw_simulator_minimap(scene, tram_instance, SCREEN_WIDTH, SCREEN_HEIGHT)
        if show_hud_info and hud_font:
            renderer.draw_info(tram_instance, SCREEN_WIDTH, SCREEN_HEIGHT)

        # --- Swap Buffers (Keep) ---
        pygame.display.flip()

    # --- Cleanup ---
    print("正在退出...")
    if scene:
        if scene.track:
         scene.track.clear()
         
    ### --- START OF MODIFICATION: Cleanup Hill Buffers on Exit ---
        if hasattr(scene, 'hills') and scene.hills and hasattr(renderer, 'cleanup_all_hill_buffers'):
            print("程序退出前，清理山丘緩衝區...")
            renderer.cleanup_all_hill_buffers(scene.hills)
        else:
            print("警告: renderer 模塊中未找到 cleanup_all_hill_buffers 函數。")
    ### --- END OF MODIFICATION ---
         
        # --- 新增: 清理最後場景的 Building 緩衝區 ---
        if hasattr(scene, 'buildings') and scene.buildings and hasattr(renderer, 'cleanup_all_building_buffers'):
            renderer.cleanup_all_building_buffers(scene.buildings)
        # --- 結束新增 ---
         
    minimap_renderer.cleanup_minimap_renderer()
    # Texture cache cleanup is handled by scene_parser.load_scene,
    # but maybe one final clear is good practice?
    if texture_loader:
         texture_loader.clear_texture_cache()
         # Clear skybox cache too
         if hasattr(renderer, 'skybox_texture_cache'):
             for tex_id in renderer.skybox_texture_cache.values():
                 try:
                     if glIsTexture(tex_id): glDeleteTextures(1, [tex_id])
                 except: pass # Ignore errors during cleanup
             renderer.skybox_texture_cache.clear()
             print("Skybox 紋理快取已清除。")

    ### --- START OF MODIFICATION: Cleanup Hill Shader Program on Exit ---
    if hasattr(renderer, '_hill_shader_program_id') and renderer._hill_shader_program_id is not None:
        try:
            glDeleteProgram(renderer._hill_shader_program_id)
            renderer._hill_shader_program_id = None # 標記為已清理
            print("山丘著色器程序已清理。")
        except Exception as e_shader_del:
            print(f"清理山丘著色器程序時出錯: {e_shader_del}")
    ### --- END OF MODIFICATION ---

    ## Keep profiler cleanup if used
    # print("profiler,disable()")
    # profiler.disable()
    # stats = pstats.Stats(profiler).sort_stats('cumulative')
    # stats.print_stats(20); stats.dump_stats('profile_results.prof')

    pygame.font.quit()
    pygame.quit()
    sys.exit()

if __name__ == '__main__':
    # Keep working directory setup
    try:
        os.chdir(os.path.dirname(os.path.abspath(__file__)))
        print(f"工作目錄設定為: {os.getcwd()}")
    except Exception as e:
        print(f"無法更改工作目錄: {e}")
    main()