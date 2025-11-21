import math
import numpy as np
from OpenGL.GL import glGetFloatv, GL_MODELVIEW_MATRIX, GL_PROJECTION_MATRIX
from ctypes import c_float

class Frustum:
    def __init__(self):
        self.planes = np.zeros((6, 4), dtype=np.float32)
        self.debug_timer = 0

    def update(self):
        """
        Extracts frustum planes from the current OpenGL ModelView and Projection matrices.
        """
        # Use ctypes to ensure we get a flat list of floats
        proj_buffer = (c_float * 16)()
        modl_buffer = (c_float * 16)()
        glGetFloatv(GL_PROJECTION_MATRIX, proj_buffer)
        glGetFloatv(GL_MODELVIEW_MATRIX, modl_buffer)
        
        # Convert to numpy arrays (Column-Major in memory -> Mathematical Matrix)
        P = np.array(proj_buffer, dtype=np.float32).reshape((4,4), order='F')
        M = np.array(modl_buffer, dtype=np.float32).reshape((4,4), order='F')
        
        # Clip Matrix
        clip = np.dot(P, M)
        
        # Extract planes
        # Left:   w + x > 0
        self.planes[0] = clip[3] + clip[0]
        # Right:  w - x > 0
        self.planes[1] = clip[3] - clip[0]
        # Bottom: w + y > 0
        self.planes[2] = clip[3] + clip[1]
        # Top:    w - y > 0
        self.planes[3] = clip[3] - clip[1]
        # Near:   w + z > 0
        self.planes[4] = clip[3] + clip[2]
        # Far:    w - z > 0
        self.planes[5] = clip[3] - clip[2]
        
        # Normalize planes
        for i in range(6):
            length = math.sqrt(self.planes[i, 0]**2 + self.planes[i, 1]**2 + self.planes[i, 2]**2)
            if length > 1e-6:
                self.planes[i] /= length
        
        # --- DEBUG: Verify Camera Position ---
        self.debug_timer += 1
        if self.debug_timer % 120 == 0: # Every ~2 seconds at 60 FPS
            # Invert ModelView to get Camera World Pos
            try:
                inv_M = np.linalg.inv(M)
                cam_pos = inv_M[:3, 3]
                print(f"DEBUG: Frustum Camera Pos: {cam_pos}")
                # Print Left Plane for sanity check
                print(f"DEBUG: Left Plane: {self.planes[0]}")
            except:
                print("DEBUG: Matrix Inversion Failed")

    def is_sphere_visible(self, x, y, z, radius):
        """
        Checks if a sphere is within the frustum.
        """
        # Add a small safety margin
        margin = 2.0 # Increased margin for safety
        
        for i in range(6):
            dist = (self.planes[i, 0] * x + 
                    self.planes[i, 1] * y + 
                    self.planes[i, 2] * z + 
                    self.planes[i, 3])
            if dist < -radius - margin:
                return False
        return True

    def is_point_visible(self, x, y, z):
        for i in range(6):
            dist = (self.planes[i, 0] * x + 
                    self.planes[i, 1] * y + 
                    self.planes[i, 2] * z + 
                    self.planes[i, 3])
            if dist < 0:
                return False
        return True



