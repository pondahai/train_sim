# TODO — 待辦清單

## 第一部分:效能優化

2026-06-11 效能檢視後的待辦項目。已完成的部分:uniform location 快取、
`draw_track` 的 `glGetError` 改為除錯旗標(`DEBUG_TRACK_GL_CHECKS`)、
HUD 與小地圖格線標籤的文字紋理快取、`texture_loader.py` 的 PyQt5 import 改為可選。

驗證方式:打開 `main.py` 內已註解的 cProfile 程式碼實測,或比較標題列 FPS。

---

## 高優先:圓柱 / 球 / 樹改用 VBO(工程量較大)

目前這三類物件仍走即時模式,每幀重新計算幾何:

- `draw_cylinder`(renderer.py,`gluNewQuadric` 處)每個圓柱每幀
  `gluNewQuadric()` → 重新鑲嵌整個網格 → `gluDeleteQuadric()`。
- `draw_sphere`(renderer.py)同樣每幀重建 quadric。
- `draw_tree`(renderer.py)每棵樹每幀 `glPushAttrib`/`glPopAttrib`
  (極昂貴的狀態保存)加 `glBegin/glEnd` 即時模式。

做法:比照 buildings/hills 的模式,載入場景時建立 VBO/VAO
(`create_building_buffers` 可當範本),繪製時只綁 VAO + `glDrawArrays`。
樹只是兩個交叉面片,所有樹可合併成單一 VBO 一次 draw call 畫完,
alpha test 等狀態整批設定一次。

## 中優先:每幀矩陣讀回與重複求逆

- `glGetFloatv(GL_MODELVIEW_MATRIX / GL_PROJECTION_MATRIX)` 每幀讀回三次:
  視錐更新(frustum_culling.py `update()`)、建築區塊、山丘區塊
  (renderer.py `draw_scene_objects`)。`glGetFloatv` 會造成 pipeline 同步。
  應在 `draw_scene_objects` 開頭讀一次,傳給視錐與兩個 shader 區塊共用。
- 建築與山丘各自用 `np.linalg.inv` 從 modelview 反推相機位置,每幀兩次。
  相機位置 `camera_instance` 本來就有,從 main.py 傳進來即可,完全不必求逆。

## 中優先:每物件每幀的 `glIsTexture`

建築(`draw_scene_objects` 內)、山丘、圓柱(`draw_cylinder`)、
樹(`draw_tree`)、球(`draw_sphere`)每幀都對每個物件呼叫 `glIsTexture`
(driver 往返)。紋理有效與否在載入時就確定,應在 scene_parser 打包資料時
存一個布林旗標,繪製時直接用。

## 中優先:`draw_track` 的 draw call 合併

每段軌道分道碴/左軌/右軌三次 `glBindVertexArray` + `glDrawArrays`,
visual branches 再各三次。段數多時可把同類幾何合併成單一大 VBO,
一次畫完所有道碴、一次畫完所有軌條。

## 低優先(小項)

- **`glTexParameteri` 每幀重設**:`draw_sphere`、`draw_tree` 每次呼叫都設
  wrap mode。wrap mode 是紋理物件屬性,在 `texture_loader.load_texture`
  載入時設一次即可。
- **視錐剔除的 Python 迴圈與除錯碼**(frustum_culling.py):
  - 平面正規化用 Python 迴圈逐一處理,可向量化成一行 numpy
    (`np.linalg.norm(planes[:, :3], axis=1)`)。
  - `update()` 內每 120 幀做一次 `np.linalg.inv` + `print` 的 DEBUG 區塊,
    正式執行時應移除或加旗標(目前每 2 秒固定輸出 DEBUG 訊息)。
- **`import numpy as math`**(main.py、renderer.py 等):純量運算
  (`math.radians`、`math.cos`、`arctan2`…)走 numpy 比內建 `math` 慢數倍,
  熱路徑(每幀的小地圖角度計算等)受影響。改回內建 `math` 需逐一確認
  numpy 專有函數名(如 `arctan2` → `atan2`)。
- **小地圖軌道線每幀逐點轉換**(minimap_renderer.py
  `draw_simulator_minimap` 的 B.1 區塊):軌道是靜態的,每幀對每個點呼叫
  `_world_to_map_coords_adapted` + 即時模式頂點。可預先把點存成 numpy
  陣列做整批運算,或烘進 VBO 後只更新平移/縮放。
- **編輯器文字繪製尚未接上快取**:`minimap_renderer.py` 編輯器路徑
  (約 1556、1776、1813、1876、1974、2081、2329、2402、2478、2491 行)
  仍用舊的 `renderer._draw_text_texture`(每次重建紋理)。模擬器路徑已改用
  `renderer._get_cached_text_texture` + `_draw_text_quad`,編輯器可比照換掉。

---

# 第二部分:新功能

## OSM 自動生成沿線建物

編輯器設定經緯度,自動從開源地圖(OSM/Overpass API)抓取建物輪廓與
樓層高度,沿線生成 `building` 方塊;另可把淡化地圖當背景。
評估結論:可行,渲染端零修改。

詳細研究與技術設計見 [docs/osm_buildings_research.md](docs/osm_buildings_research.md)。

實作順序:
1. 獨立驗證腳本(經緯度＋範圍 → building 行)
2. 底圖拼接＋淡化(輸出 `map` 行)
3. 編輯器 UI(經緯度輸入、範圍選擇、生成/清除按鈕)
