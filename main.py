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

def main():
    global hud_font

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
    # Set loaders/modules BEFORE loading scene or initializing renderers
    scene_parser.set_texture_loader(texture_loader)
    # scene_parser.set_renderer_module(renderer) # No longer needed
    renderer.init_renderer() # Initialize main 3D renderer states and common textures

    # Pass font to main renderer (for coordinates) and minimap renderer (for labels)
    if hud_font:
        renderer.set_hud_font(hud_font) # Main renderer still uses it
        minimap_renderer.set_grid_label_font(renderer.grid_label_font) # Pass the created grid font
    else:
        print("警告: HUD 字體未載入，坐標和網格標籤顯示將不可用。")

    # --- Load Initial Scene and Perform Post-Load Steps ---
    scene = None
    if scene_parser.load_scene(force_reload=True): # Initial load
        scene = scene_parser.get_current_scene()
        if scene and scene.track:
            print("初始場景載入成功，創建軌道緩衝區...")
            scene.track.create_all_segment_buffers() # Create VBOs for the loaded track
        # *** NEW: Bake minimap AFTER successful scene load and track buffer creation ***
        minimap_renderer.bake_static_map_elements(scene)
        print("初始小地圖已烘焙。")
    else:
        print("初始場景載入失敗，請檢查 scene.txt。場景將為空。")
        scene = scene_parser.get_current_scene() # Get the (likely empty) scene
        # Bake empty scene? Or handle None scene in bake function?
        minimap_renderer.bake_static_map_elements(scene) # Bake with empty scene data


    # --- Create Objects (Keep tram/camera creation) ---
    # Pass track reference, could be None if initial load failed
    tram_instance = Tram(scene.track if scene else None)
    # Set initial tram position/orientation based on parsed scene data (KEEP LOGIC)
    if scene: # Check if scene loaded successfully
        tram_instance.position = np.copy(scene.start_position)
        start_angle_rad = math.radians(scene.start_angle_deg)
        tram_instance.forward_vector_xz = (math.cos(start_angle_rad), math.sin(start_angle_rad)) # Ensure correct calculation for angle from +X
        # Tram distance is updated automatically in its update based on position
        # Need to ensure the tram starts *exactly* at the calculated start position
        # which should correspond to distance 0 if start pos matches track start.
        tram_instance.distance_on_track = 0.0 # Reset distance explicitly
        print(f"Tram initial pos: {tram_instance.position}, angle: {scene.start_angle_deg} deg, forward: {tram_instance.forward_vector_xz}")
    else:
        # Default position if scene failed to load
        tram_instance.position = np.array([0.0, 0.0, 0.0])
        tram_instance.forward_vector_xz = (1.0, 0.0) # Default forward +X
        tram_instance.distance_on_track = 0.0


    camera_instance = Camera()

    # --- Game State (Keep) ---
    running = True
    clock = pygame.time.Clock()
    last_scene_check_time = time.time()
    show_ground_flag = True # Default ground to visible
    show_minimap = True
    show_coordinates = False

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
                     # Reload scene data
                     if scene_parser.load_scene(force_reload=True):
                         scene = scene_parser.get_current_scene()
                         # Create track buffers for the NEW scene
                         if scene and scene.track:
                             print("手動重載成功，創建軌道緩衝區...")
                             scene.track.create_all_segment_buffers()
                         # *** NEW: Bake minimap for the NEW scene ***
                         minimap_renderer.bake_static_map_elements(scene)
                         print("手動重載後小地圖已烘焙。")

                         # Reset tram based on NEW scene data
                         tram_instance.track = scene.track if scene else None
                         if scene:
                              tram_instance.position = np.copy(scene.start_position)
                              start_angle_rad = math.radians(scene.start_angle_deg)
                              tram_instance.forward_vector_xz = (math.cos(start_angle_rad), math.sin(start_angle_rad))
                              tram_instance.distance_on_track = 0.0 # Reset distance
                              tram_instance.current_speed = 0.0 # Reset speed
                         else: # Reset to default if reload somehow resulted in empty scene
                              tram_instance.position = np.array([0.0, 0.0, 0.0])
                              tram_instance.forward_vector_xz = (1.0, 0.0)
                              tram_instance.distance_on_track = 0.0
                              tram_instance.current_speed = 0.0

                         print("場景已手動重新載入並重設電車。")
                     else:
                         print("手動重新載入失敗。")
                         # scene might be empty now if load failed
                         scene = scene_parser.get_current_scene()
                         tram_instance.track = scene.track if scene else None
                         # Bake minimap even if reload failed (will bake empty state)
                         minimap_renderer.bake_static_map_elements(scene)

                elif event.key == pygame.K_m:
                    show_minimap = not show_minimap
                    print(f"小地圖: {'開啟' if show_minimap else '關閉'}")
                elif event.key == pygame.K_i:
                    show_coordinates = not show_coordinates
                    print(f"坐標顯示: {'開啟' if show_coordinates else '關閉'}")
                elif event.key == pygame.K_PAGEUP:
                    # *** MODIFIED: Call minimap zoom function ***
                    minimap_renderer.zoom_simulator_minimap(1 / minimap_renderer.MINIMAP_ZOOM_FACTOR) # Zoom In
                elif event.key == pygame.K_PAGEDOWN:
                    # *** MODIFIED: Call minimap zoom function ***
                    minimap_renderer.zoom_simulator_minimap(minimap_renderer.MINIMAP_ZOOM_FACTOR)    # Zoom Out

            elif event.type == pygame.MOUSEBUTTONDOWN:
                 if not camera_instance.mouse_locked and event.button == 1: # Left click
                     camera_instance.set_mouse_lock(True)
                     pygame.mouse.set_visible(False)
                     pygame.event.set_grab(True)

            elif event.type == pygame.MOUSEWHEEL:
                tram_instance.adjust_speed(event.y) # Keep tram speed adjust

            elif event.type == pygame.MOUSEMOTION:
                if camera_instance.mouse_locked:
                    dx, dy = event.rel
                    camera_instance.update_angles(dx, dy)

        # --- Keyboard Hold Handling (Keep) ---
        keys = pygame.key.get_pressed()
        if camera_instance.mouse_locked:
            if keys[K_w] or keys[K_UP]:
                tram_instance.accelerate()
            if keys[K_s] or keys[K_DOWN]:
                tram_instance.brake()

        # --- Game Logic Update (Keep) ---
        tram_instance.update(dt)
        # Update camera based on tram state (Keep logic)
        camera_instance.update_position_orientation(tram_instance.position, tram_instance.forward_vector_xz)

        # --- Periodic Scene File Check ---
        current_time = time.time()
        if current_time - last_scene_check_time > SCENE_CHECK_INTERVAL:
            if scene_parser.load_scene(): # load_scene returns True if reloaded
                scene = scene_parser.get_current_scene()
                # *** Perform post-load steps for the NEW scene ***
                if scene and scene.track:
                    print("自動重載成功，創建軌道緩衝區...")
                    scene.track.create_all_segment_buffers()
                # *** Bake minimap for the NEW scene ***
                minimap_renderer.bake_static_map_elements(scene)
                print("自動重載後小地圖已烘焙。")

                # Update tram track reference
                tram_instance.track = scene.track if scene else None
                # Optionally reset tram position on auto-reload? Current code doesn't.
                print("場景自動重新載入完成。")
            last_scene_check_time = current_time


        # --- OpenGL Rendering ---
        # Clear buffers (Keep)
        glClearColor(0.5, 0.7, 1.0, 1.0) # Sky blue background
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        # Set 3D Projection (Keep)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        # Use GROUND_SIZE from renderer, ensure it's accessible or define here
        far_clip = renderer.GROUND_SIZE * 2 if hasattr(renderer, 'GROUND_SIZE') else 500.0
        gluPerspective(45, (SCREEN_WIDTH / SCREEN_HEIGHT), 0.1, far_clip)

        # Set ModelView Matrix (Keep)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

        # Apply Camera View (Keep)
        camera_instance.apply_view()

        # --- Draw 3D Scene (Keep) ---
        renderer.draw_ground(show_ground_flag)
        if scene and scene.track:
            renderer.draw_track(scene.track) # Uses pre-built buffers
        # Pass the scene object, which contains absolute coordinates
        renderer.draw_scene_objects(scene)

        # --- Draw Tram Cab (Keep) ---
        renderer.draw_tram_cab(tram_instance, camera_instance)

        # --- Draw HUD ---
        # *** MODIFIED: Call minimap renderer's draw function ***
        if show_minimap:
            minimap_renderer.draw_simulator_minimap(scene, tram_instance, SCREEN_WIDTH, SCREEN_HEIGHT)

        # Draw Coordinates (Keep)
        if show_coordinates and hud_font:
             renderer.draw_coordinates(tram_instance.position, SCREEN_WIDTH, SCREEN_HEIGHT)


        # --- Swap Buffers (Keep) ---
        pygame.display.flip()

    # --- Cleanup ---
    print("正在退出...")
    # Clean up track buffers from the last loaded scene
    if scene and scene.track:
         scene.track.clear()
    # *** NEW: Clean up minimap renderer resources ***
    minimap_renderer.cleanup_minimap_renderer()
    # Texture cache is cleaned by scene_parser on load, but maybe clear once more?
    # texture_loader.clear_texture_cache() # Already done in load_scene

    # Keep profiler cleanup if used
    # print("profiler,disable()")
    # profiler.disable()
    # stats = pstats.Stats(profiler).sort_stats('cumulative')
    # stats.print_stats(20)
    # stats.dump_stats('profile_results.prof')

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