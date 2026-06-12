# 專案執行效率分析報告

## 1. 現狀分析 (Current Status)

經過對 `main.py`, `renderer.py`, 和 `minimap_renderer.py` 的代碼審查，我們發現目前的渲染架構採用了 **混合模式 (Mixed Mode)**：

*   **高效部分 (Efficient)**:
    *   **軌道 (Tracks)**: 使用 VBO (Vertex Buffer Objects) 進行渲染，效率良好。
    *   **建築 (Buildings)**: 使用 VBO 和 Shader 進行渲染，這是現代 OpenGL 的做法，效率高。
    *   **山丘 (Hills)**: 同樣使用 VBO 和 Shader。
    *   **小地圖 (Minimap)**: 靜態元素 (軌道、建築等) 會預先烘焙 (Bake) 到一張紋理中，運行時只需繪製該紋理，非常高效。

*   **低效部分 (Inefficient - Bottlenecks)**:
    *   **樹木 (Trees)**: 目前使用 **立即模式 (Immediate Mode)** (`glBegin`/`glEnd`) 繪製。如果場景中有數百或數千棵樹，這將是主要的性能瓶頸。
    *   **圓柱體/電線桿 (Cylinders/Poles)**: 同樣使用立即模式。
    *   **屋頂 (Roofs)**: `Gableroof` 和 `Flexroof` 也是使用立即模式繪製。
    *   **地面 (Ground)**: 使用立即模式繪製一個大四邊形 (影響較小，但仍過時)。
    *   **Python 迴圈開銷**: 即使是使用 VBO 的物件 (如建築)，目前的代碼仍是在 Python 迴圈中逐個遍歷並調用 `glDrawArrays`。Python 的迴圈開銷加上大量的 OpenGL Draw Call (繪製調用) 會導致 CPU 瓶頸。

*   **缺失的優化 (Missing Optimizations)**:
    *   **視錐體剔除 (Frustum Culling)**: 目前似乎沒有實作剔除邏輯。這意味著即使物體在相機背後或遠處不可見，CPU 仍會處理它們並發送給 GPU，浪費資源。
    *   **實例化渲染 (Instancing)**: 對於樹木、電線桿這種重複出現且幾何體相同的物件，目前沒有使用 `glDrawArraysInstanced`。

## 2. 性能瓶頸示意

假設場景中有 1000 棵樹和 500 棟建築：

*   **目前**: Python 迴圈執行 1500 次。
    *   1000 次 `draw_tree` (立即模式，慢)。
    *   500 次 `glDrawArrays` (VBO，快，但 Draw Call 次數多)。
*   **結果**: CPU 忙於發送指令，GPU 可能在等待，FPS 低下。

## 3. 改進建議 (Proposed Improvements)

我們建議分階段進行優化：

### 第一階段：基礎優化 (High Priority)
1.  **樹木與圓柱體的 VBO 化**: 將 `draw_tree` 和 `draw_cylinder` 改寫為使用 VBO。這能顯著減少幾何體傳輸開銷。
2.  **視錐體剔除 (Frustum Culling)**: 在 `draw_scene_objects` 迴圈中加入簡單的檢查，如果物件不在相機視野內，直接跳過繪製。這能大幅減少 Draw Call。

### 第二階段：進階優化 (Medium Priority)
3.  **實例化渲染 (Instancing)**: 對於樹木和圓柱體，使用 **Instanced Rendering**。
    *   **目標**: 將 1000 棵樹的繪製壓縮為 **1 次** Draw Call。
    *   **方法**: 創建一個包含樹木幾何體的 VBO，和一個包含所有樹木位置/旋轉的 Instance VBO。
4.  **屋頂優化**: 將屋頂也轉為 VBO 渲染。

### 第三階段：架構重構 (Long Term)
5.  **批次處理 (Batching)**: 將使用相同紋理的靜態建築合併為一個大的 VBO，進一步減少 Draw Call。

## 4. 下一步行動

我已經在 `main.py` 中加入了 FPS 顯示，方便您觀察目前的性能。

**建議的下一步**:
優先實作 **樹木的 VBO 化** 或 **視錐體剔除**。這兩者通常能帶來最大的性能提升。

您希望我們先從哪一項開始？
