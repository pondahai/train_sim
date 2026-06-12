# shaders_inline.py

HILL_VERTEX_SHADER_SOURCE = """
#version 330 core
layout (location = 0) in vec3 vertexPosition_modelspace; // 模型空間中的頂點位置
layout (location = 1) in vec3 vertexNormal_modelspace;   // 模型空間中的法線
layout (location = 2) in vec2 vertexTexCoords;           // 紋理UV座標

out vec3 FragPos_worldspace;    // 傳遞給片段著色器的世界空間位置
out vec3 Normal_worldspace;     // 傳遞給片段著色器的世界空間法線
out vec2 TexCoords_frag;        // 傳遞給片段著色器的紋理UV座標

uniform mat4 model;           // 模型矩陣
uniform mat4 view;            // 視圖矩陣
uniform mat4 projection;      // 投影矩陣

void main()
{
    FragPos_worldspace = vec3(model * vec4(vertexPosition_modelspace, 1.0)); 
    Normal_worldspace = normalize(mat3(transpose(inverse(model))) * vertexNormal_modelspace);
    TexCoords_frag = vertexTexCoords;
    gl_Position = projection * view * vec4(FragPos_worldspace, 1.0); 
}
"""

HILL_FRAGMENT_SHADER_SOURCE = """
#version 330 core
out vec4 FragColor;

in vec3 FragPos_worldspace;
in vec3 Normal_worldspace;
in vec2 TexCoords_frag;

uniform sampler2D texture_diffuse1;     // 山丘的紋理
uniform bool u_use_diffuse_texture;     // CPU端告知是否使用 texture_diffuse1
uniform vec3 u_fallback_diffuse_color;  // CPU端傳入的無紋理時的漫反射基色
uniform bool u_texture_has_alpha;       // 紋理是否有 alpha 通道用於測試
uniform float u_alpha_test_threshold;   // Alpha 測試閾值

uniform vec3 lightPos_worldspace;       // 光源的世界位置
uniform vec3 lightColor;              // 光源顏色
uniform vec3 viewPos_worldspace;        // 觀察者/攝影機的世界位置
uniform float u_ambient_strength;
uniform float u_specular_strength;
uniform float u_shininess;

void main()
{
    vec3 base_color_rgb;
    float base_alpha = 1.0;

    if (u_use_diffuse_texture) {
        vec4 texSample = texture(texture_diffuse1, TexCoords_frag);
        if (u_texture_has_alpha && texSample.a < u_alpha_test_threshold) {
            discard; // Alpha test
        }
        base_color_rgb = texSample.rgb;
        base_alpha = texSample.a;
    } else {
        base_color_rgb = u_fallback_diffuse_color;
    }

    // Lighting calculations
    vec3 ambient = u_ambient_strength * lightColor;
    vec3 norm = normalize(Normal_worldspace);
    vec3 lightDir = normalize(lightPos_worldspace - FragPos_worldspace);
    float diff = max(dot(norm, lightDir), 0.0);
    vec3 diffuse = diff * lightColor;
    vec3 viewDir = normalize(viewPos_worldspace - FragPos_worldspace);
    vec3 reflectDir = reflect(-lightDir, norm);  
    float spec = pow(max(dot(viewDir, reflectDir), 0.0), u_shininess);
    vec3 specular = u_specular_strength * spec * lightColor;  
    vec3 lighting_effect = ambient + diffuse + specular;
    vec3 final_rgb = lighting_effect * base_color_rgb;
    
    FragColor = vec4(final_rgb, base_alpha);
}
"""

# 如果將來有其他著色器，也按此格式添加：
# FLEXROOF_VERTEX_SHADER_SOURCE = """..."""
# FLEXROOF_FRAGMENT_SHADER_SOURCE = """..."""

BUILDING_VERTEX_SHADER_SOURCE = """
#version 330 core
layout (location = 0) in vec3 aPos;         // Model space position
layout (location = 1) in vec3 aNormal;      // Model space normal
layout (location = 2) in vec2 aTexCoords_atlas_input; // Atlas UV coordinates

out vec3 FragPos_world;
out vec3 Normal_world;
out vec2 TexCoords_transformed_atlas;

uniform mat4 model;
uniform mat4 view;
uniform mat4 projection;

// *** 修改/新增 Uniforms ***
uniform vec2 u_tex_offset;        // 平移 (u_offset, v_offset)
uniform float u_tex_angle_rad;    // 旋轉角度 (弧度)
uniform vec2 u_tex_scale;         // 縮放/重複 (uscale, vscale)
// uniform int u_uv_mode_compat;  // <--- 移除這個 uniform

void main()
{
    FragPos_world = vec3(model * vec4(aPos, 1.0));
    Normal_world = normalize(mat3(transpose(inverse(model))) * aNormal);
    
    vec2 transformed_uv = aTexCoords_atlas_input; // 從VBO讀取的原始圖集UV開始

    // 1. 應用縮放/重複 (u_tex_scale)
    // 假設 u_tex_scale.x/y 是用戶期望的重複次數
    vec2 final_scale = u_tex_scale;
    // 防止除以零或非常小的縮放導致問題
    if (abs(final_scale.x) < 0.0001) final_scale.x = (final_scale.x < 0.0 ? -0.0001 : 0.0001);
    if (abs(final_scale.y) < 0.0001) final_scale.y = (final_scale.y < 0.0 ? -0.0001 : 0.0001);
    transformed_uv = transformed_uv * final_scale;

    // 2. 應用旋轉 (u_tex_angle_rad)
    // 旋轉中心點: 假設是整個圖集 (0-1範圍) 的中心 (0.5, 0.5)
    // 重要的注意點：這個旋轉是在 transformed_uv (已經被 final_scale 縮放過) 的基礎上進行的。
    // 如果希望旋轉的是 *原始* 圖集UV，然後再縮放，順序需要調整。
    // 目前的順序是：原始圖集UV -> 縮放 -> 旋轉 -> 平移。
    // 這意味著縮放會影響旋轉的“半徑”。
    // 如果希望旋轉獨立於縮放（即旋轉原始圖集，然後縮放這個旋轉後的結果），
    // 則應先旋轉 aTexCoords_atlas_input，然後再乘以 final_scale。
    // 為了與上次討論保持一致（先縮放再旋轉），我們保持這個順序。
    if (abs(u_tex_angle_rad) > 0.001) { // 僅當角度有效時執行
        vec2 rotation_center = vec2(0.5, 0.5); 
        // 如果 transformed_uv 的範圍因縮放而改變，這個中心點可能需要相應調整
        // 例如：vec2 rotation_center = vec2(0.5 * final_scale.x, 0.5 * final_scale.y);
        // 但這會使旋轉依賴於縮放，可能不是期望的。
        // 保持 (0.5,0.5) 作為“邏輯”中心，旋轉的是“紋理內容本身”。
        mat2 rotation_matrix = mat2(
            cos(u_tex_angle_rad), -sin(u_tex_angle_rad),
            sin(u_tex_angle_rad),  cos(u_tex_angle_rad)
        );
        transformed_uv = rotation_matrix * (transformed_uv - rotation_center) + rotation_center;
    }

    // 3. 應用平移 (u_tex_offset)
    transformed_uv += u_tex_offset;
    
    TexCoords_transformed_atlas = transformed_uv; // 傳遞給片段著色器
    gl_Position = projection * view * model * vec4(aPos, 1.0);
}
"""

BUILDING_FRAGMENT_SHADER_SOURCE = """
#version 330 core
out vec4 FragColor;

in vec3 FragPos_world;
in vec3 Normal_world;
in vec2 TexCoords_transformed_atlas; // These are already the final Atlas UVs

uniform sampler2D texture_diffuse1;
uniform bool u_use_texture;
uniform vec3 u_fallback_color;
uniform bool u_texture_has_alpha;
uniform float u_alpha_test_threshold;

// Lighting uniforms (same as hill shader)
uniform vec3 lightPos_worldspace;
uniform vec3 lightColor;
uniform vec3 viewPos_worldspace;
uniform float u_ambient_strength;
uniform float u_specular_strength;
uniform float u_shininess;

void main()
{
    vec3 base_color_rgb;
    float base_alpha = 1.0;

    if (u_use_texture) {
        vec4 texSample = texture(texture_diffuse1, TexCoords_transformed_atlas);
        if (u_texture_has_alpha && texSample.a < u_alpha_test_threshold) {
            discard; // Alpha test
        }
        base_color_rgb = texSample.rgb;
        base_alpha = texSample.a; 
    } else {
        base_color_rgb = u_fallback_color;
    }

    // Lighting calculations
    vec3 ambient = u_ambient_strength * lightColor;
    vec3 norm = normalize(Normal_world); // Use Normal_world
    vec3 lightDir = normalize(lightPos_worldspace - FragPos_world);
    float diff = max(dot(norm, lightDir), 0.0);
    vec3 diffuse = diff * lightColor;
    vec3 viewDir = normalize(viewPos_worldspace - FragPos_world);
    vec3 reflectDir = reflect(-lightDir, norm);  
    float spec = pow(max(dot(viewDir, reflectDir), 0.0), u_shininess);
    vec3 specular = u_specular_strength * spec * lightColor;  
    
    vec3 lighting_effect = ambient + diffuse + specular;
    vec3 final_rgb = lighting_effect * base_color_rgb;
    
    FragColor = vec4(final_rgb, base_alpha);
}
"""
