# texture_loader.py
import pygame
from OpenGL.GL import *
import os

texture_cache = {}

def load_texture(filename):
    """載入紋理並返回其 OpenGL ID，使用快取避免重複載入"""
    if filename in texture_cache:
        return texture_cache[filename]

    filepath = os.path.join("textures", filename)
    if not os.path.exists(filepath):
#         print(f"警告: 紋理檔案 '{filepath}' 不存在")
        return None

    try:
        surface = pygame.image.load(filepath)
        # 有些圖片可能需要轉換格式以包含 Alpha 通道
        texture_data = pygame.image.tostring(surface, "RGBA", True) # 使用 RGBA 以支援透明度

        texture_id = glGenTextures(1)
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

        texture_cache[filename] = texture_id
        print(f"紋理已載入: {filename} (ID: {texture_id})")
        return texture_id
    except Exception as e:
        print(f"載入紋理 '{filepath}' 時發生錯誤: {e}")
        return None

def clear_texture_cache():
    """清除紋理快取"""
    global texture_cache
    # 可以在這裡添加 glDeleteTextures 釋放 OpenGL 資源
    print("清除紋理快取...")
    for tex_id in texture_cache.values():
        if tex_id is not None and glIsTexture(tex_id):
             glDeleteTextures(1, [tex_id])
    texture_cache = {}