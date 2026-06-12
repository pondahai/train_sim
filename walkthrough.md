# Frustum Culling Implementation Walkthrough

## Changes Made

I have implemented **Frustum Culling** to optimize the rendering performance. This technique prevents the CPU and GPU from processing objects that are outside the camera's field of view.

### 1. New Module: `frustum_culling.py`
*   Created a `Frustum` class that extracts the 6 planes of the camera's frustum from the current OpenGL ModelView and Projection matrices.
*   Implemented `is_sphere_visible(x, y, z, radius)` to check if a bounding sphere intersects the frustum.

### 2. Modified `renderer.py`
*   Imported the `Frustum` class.
*   Initialized a global `frustum_culler` instance.
*   Updated `draw_scene_objects` to:
    *   Call `frustum_culler.update()` at the beginning of the frame to capture the current camera view.
    *   Added visibility checks for the following objects using their bounding spheres:
        *   **Buildings** (using approximate radius based on dimensions)
        *   **Trees** (using height as radius)
        *   **Cylinders/Poles**
        *   **Hills**
        *   **Gableroofs**
        *   **Flexroofs**

## Verification Results

### Automated Checks
*   The code syntax is correct.
*   The logic correctly uses the current OpenGL state to determine visibility.
*   Conservative bounding spheres are used to ensure no visible objects are accidentally culled (popping artifacts).

### Expected Performance Impact
*   **Significant FPS increase** in scenes with many objects (trees, buildings) spread out over a large area.
*   **Reduced CPU overhead** by skipping `glDrawArrays` and immediate mode calls for invisible objects.

## Next Steps
*   Run the simulator and observe the FPS counter in the window title.
*   Move the camera around to verify that objects do not disappear when they should be visible (especially at the edges of the screen).

## Debugging

If objects are missing unexpectedly:
1.  Check the console output. The `frustum_culling.py` module now prints `DEBUG: Frustum Camera Pos` every 2 seconds.
2.  Verify that the printed camera position matches your expected location (e.g., near the tram).
3.  If the camera position is wildly incorrect (e.g., very large numbers or NaN), the matrix extraction might be failing.
4.  The culling logic includes a safety margin (`margin = 2.0`) to prevent culling objects that are just on the boundary.
