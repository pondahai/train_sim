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

# Keep profiler if used
# import cProfile
# import pstats
# profiler = cProfile.Profile()
# profiler.enable()

# --- Settings (Keep) ---
SCREEN_WIDTH = 1200
SCREEN_HEIGHT = 600
TARGET_FPS = 60
SCENE_CHECK_INTERVAL = 2.0 # Seconds for checking scene.txt updates

# --- Global Font (Keep) ---
hud_font = None

# --- NEW: Global for active background ---
active_background_info = None

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
                     if scene_parser.load_scene(force_reload=True): # Reload scene data
                         scene = scene_parser.get_current_scene()
                         # --- NEW: Update active background after reload ---
                         active_background_info = scene.initial_background_info if scene else None
                         print(f"手動重載後背景設定為: {active_background_info}")

                         if scene and scene.track:
                             print("手動重載成功，創建軌道緩衝區...")
                             scene.track.create_all_segment_buffers()
                         minimap_renderer.bake_static_map_elements(scene)
                         print("手動重載後小地圖已烘焙。")

                         # Reset tram based on NEW scene data
                         tram_instance.track = scene.track if scene else None
                         if scene:
                             # 場景重載後不要重置
#                               tram_instance.position = np.copy(scene.start_position)
#                               start_angle_rad = math.radians(scene.start_angle_deg)
#                               tram_instance.forward_vector_xz = (math.cos(start_angle_rad), math.sin(start_angle_rad))
#                               tram_instance.distance_on_track = 0.0 # Reset distance
                              tram_instance.current_speed = 0.0 # Reset speed
                         else: # Reset to default if reload somehow resulted in empty scene
                              tram_instance.position = np.array([0.0, 0.0, 0.0])
                              tram_instance.forward_vector_xz = (1.0, 0.0)
                              tram_instance.distance_on_track = 0.0
                              tram_instance.current_speed = 0.0

                         print("場景已手動重新載入並重設電車。")
                     else:
                         print("手動重新載入失敗。")
                         scene = scene_parser.get_current_scene() # Get potentially empty scene
                         # --- NEW: Reset background on failed reload too ---
                         active_background_info = scene.initial_background_info if scene else None
                         tram_instance.track = scene.track if scene else None
                         minimap_renderer.bake_static_map_elements(scene)

                elif event.key == pygame.K_c: show_cab = not show_cab
                elif event.key == pygame.K_m: show_minimap = not show_minimap; print(f"小地圖: {'開啟' if show_minimap else '關閉'}")
                elif event.key == pygame.K_i: show_hud_info = not show_hud_info; print(f"資訊顯示: {'開啟' if show_hud_info else '關閉'}")
                elif event.key == pygame.K_PAGEUP: minimap_renderer.zoom_simulator_minimap(1 / minimap_renderer.MINIMAP_ZOOM_FACTOR)
                elif event.key == pygame.K_PAGEDOWN: minimap_renderer.zoom_simulator_minimap(minimap_renderer.MINIMAP_ZOOM_FACTOR)

            elif event.type == pygame.MOUSEBUTTONDOWN:
                 if not camera_instance.mouse_locked and event.button == 1:
                     camera_instance.set_mouse_lock(True); pygame.mouse.set_visible(False); pygame.event.set_grab(True)
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
            if scene_parser.load_scene(): # load_scene returns True if reloaded
                scene = scene_parser.get_current_scene()
                # --- NEW: Update active background on auto-reload ---
                active_background_info = scene.initial_background_info if scene else None
                print(f"自動重載後背景設定為: {active_background_info}")

                if scene and scene.track:
                    print("自動重載成功，創建軌道緩衝區...")
                    scene.track.create_all_segment_buffers()
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
    if scene and scene.track:
         scene.track.clear()
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

    # Keep profiler cleanup if used
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