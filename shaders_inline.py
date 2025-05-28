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