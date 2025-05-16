# texture_loader.py
import pygame
from OpenGL.GL import *
import os
import time # 用於時間戳
from PyQt5.QtOpenGL import QGLContext # 需要導入

texture_cache = {} # 新結構: {filename: {"id": texture_id, "has_alpha": bool}}

def load_texture(filename):
    # ...
#     current_ctx = QGLContext.currentContext()
#     if current_ctx:
#         print(f"DEBUG LOADER: Current QGLContext: {current_ctx}, Format: {current_ctx.format().majorVersion()}.{current_ctx.format().minorVersion()}, isValid: {current_ctx.isValid()}")
#         # 你還可以比較 current_ctx 是否與你期望的 preview_widget.context() 是同一個對象
#         # (這需要在 texture_loader 能訪問到 preview_widget 的情況下)
#     else:
#         print("DEBUG LOADER: No QGLContext is current!")
    # ...
#     timestamp = time.time()
#     print(f"DEBUG LOADER [{timestamp:.3f}]: load_texture CALLED for '{filename}'")
#     print(f"紋理載入前檢查 {texture_cache}")
    """載入紋理並返回其 OpenGL ID，使用快取避免重複載入"""
    if filename in texture_cache:
#         print(f"filename in texture_cache:  texture_cache[{filename}] = {texture_cache[filename]} ")
#         print(f"紋理快取命中 {filename} id:{texture_cache[filename].get('id')}")
#         print()
        return texture_cache[filename]

    filepath = os.path.join("textures", filename)
    if not os.path.exists(filepath):
#         print(f"警告: 紋理檔案 '{filepath}' 不存在")
#         print()
        return {"id": None, "has_alpha": False} # 返回帶預設值的字典

    try:
        surface = pygame.image.load(filepath)
#         print(f"surface: {surface}")
        # --- 簡化的 Alpha 通道檢測 ---
        # 只要 Surface 報告有 per-pixel alpha，就認為它可能使用了 Alpha。
        # pygame.SRCALPHA 標誌表示 Surface 每個像素都有自己的 alpha 值。
        # surface.convert_alpha() 會確保 surface 有 per-pixel alpha。
        # 我們可以先 convert_alpha() 然後再檢查 flags，或者直接檢查原始 surface 的 flags。
        # 為了更可靠地判斷是否 *真的* 有 alpha 通道被使用，
        # convert_alpha() 是個好方法，它會添加 alpha 如果沒有，或者優化現有的。
        
        # 先嘗試 convert_alpha()，它會返回一個帶有最佳 alpha 格式的新 surface
        # 如果原始圖像就沒有任何透明信息，convert_alpha() 後的 alpha 通道可能都是 255
        # 但對於我們的“自動檢測”，如果它能被 convert_alpha() 並且結果有 SRCALPHA 標誌，
        # 我們可以初步認為它“意圖”使用 alpha。
        
        temp_surface_for_alpha_check = surface.convert_alpha() # 確保有 Alpha 能力
        has_significant_alpha = bool(temp_surface_for_alpha_check.get_flags() & pygame.SRCALPHA)
        
        # 一個更嚴格（但可能錯誤排除某些情況）的檢查是看原始 surface
        # has_significant_alpha = bool(surface.get_flags() & pygame.SRCALPHA)
        # print(f"DEBUG: Texture '{filename}', original flags: {surface.get_flags()}, SRCALPHA: {pygame.SRCALPHA}, has_significant_alpha based on original: {has_significant_alpha}")

        # 如果想更精確判斷 Alpha 是否真的被“使用”（即存在非255的值），
        # 需要遍歷像素，這在加載時會有開銷。
        # 實驗階段，上述基於 convert_alpha() 後的 SRCALPHA 標誌是一個合理的起點。
        # if has_significant_alpha:
        #     is_alpha_actually_used = False
        #     for y in range(temp_surface_for_alpha_check.get_height()):
        #         for x in range(temp_surface_for_alpha_check.get_width()):
        #             if temp_surface_for_alpha_check.get_at((x,y))[3] < 255:
        #                 is_alpha_actually_used = True
        #                 break
        #         if is_alpha_actually_used:
        #             break
        #     has_significant_alpha = is_alpha_actually_used # 更新為更精確的判斷
        #     if not has_significant_alpha:
        #          print(f"DEBUG: Texture '{filename}' has SRCALPHA flag after convert_alpha, but all alpha values are 255.")


        # -------------------------
        
        # 有些圖片可能需要轉換格式以包含 Alpha 通道
        texture_data = pygame.image.tostring(surface, "RGBA", True) # 使用 RGBA 以支援透明度

        texture_id = glGenTextures(1)
        
        # --- 新增：在存入快取前檢查 ID 是否已存在於快取中 (用於不同的檔名) ---
#         for existing_filename, existing_info in texture_cache.items():
#             if existing_info and existing_info.get("id") == texture_id:
#                 print(f"CRITICAL WARNING LOADER [{timestamp:.3f}]: For new file '{filename}', glGenTextures returned ID {texture_id}, "
#                       f"which is ALREADY IN CACHE for a DIFFERENT file '{existing_filename}' with info {existing_info}!")
#                 # 這裡可以選擇是拋出錯誤、返回 None，還是繼續（可能導致問題）
#                 # 為了調試，我們先打印警告，然後繼續，看看後續會發生什麼
        # --------------------------------------------------------------------
        
        
        
        glBindTexture(GL_TEXTURE_2D, texture_id)

        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR_MIPMAP_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)

        # 建立紋理及其 mipmaps
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, surface.get_width(), surface.get_height(),
                     0, GL_RGBA, GL_UNSIGNED_BYTE, texture_data)
        glGenerateMipmap(GL_TEXTURE_2D) # 自動生成 Mipmap

        glBindTexture(GL_TEXTURE_2D, 0) # 解除綁定

        texture_info = {"id": texture_id, "has_alpha": has_significant_alpha}
        texture_cache[filename] = texture_info
        
#         print(f"紋理載入檢查無快取後 {texture_cache}")
    
        print(f"紋理已載入: {filename} (ID: {texture_id})")
        return texture_info
    except Exception as e:
        print(f"載入紋理 '{filepath}' 時發生錯誤: {e}")
        return {"id": None, "has_alpha": False} # 確保返回一致的結構

    print()

def clear_texture_cache():
#     timestamp = time.time()
#     print(f"CRITICAL DEBUG [{timestamp:.3f}]: clear_texture_cache() CALLED!")
    """清除紋理快取"""
    global texture_cache
    # 可以在這裡添加 glDeleteTextures 釋放 OpenGL 資源
    print("清除紋理快取...")
    for texture_info in texture_cache.values():
        if texture_info is not None and glIsTexture(texture_info.get("id")):
             glDeleteTextures(1, [texture_info.get("id")])
    texture_cache = {}