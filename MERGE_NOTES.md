# 合流說明(2026-06-12)

本資料夾是兩個版本的合流結果:

- **基底**:GitHub 版 `C:\Users\pondahai\Documents\GitHub\train_sim`(commit afc48b4)
  ——含 2026-06-12 的效能優化(uniform location 快取、glGetError 除錯旗標、
  文字紋理快取、texture_loader 的 PyQt5 可選 import)
- **移植來源**:`Dropbox\train_sim\train_sim_gemini_3_1_pro_v1`(2026-02-27 開發版)

## 從 gemini 版移植的內容

| 項目 | 說明 |
|---|---|
| 樹木/圓柱 VBO+著色器 | `renderer.py`:init_tree/cylinder_shader、generate/create/cleanup 緩衝區函數、draw_scene_objects 的 VBO 繪製路徑(移植時已改用 `_get_uniform_loc` 快取) |
| 著色器源碼 | `shaders_inline.py`(gemini 版為 GitHub 版的超集,含 TREE/CYLINDER shaders) |
| 小地圖軌道烘焙 | `minimap_renderer.py`:軌道改烘進靜態 FBO(畫在建築之上),模擬器小地圖不再每幀逐點重畫軌道 |
| PyQt 場景編輯器 | `scene_editor.py`:**已去重**(原檔 7147 行內含三份重複的 class 定義,只保留最後一份生效版本,2621 行) |
| 場景與素材 | 各站場景檔(圓山/劍潭/士林/芝山/石牌/海科館八斗子等)、scene.txt(實際路線)、textures/、map/、text/、editor_settings.json |

## 合流時修正的 gemini 版問題

1. **main.py 內含四份重複的 main()**(2348 行),且各份只處理一種物件的
   緩衝區——生效的最後一份只建圓柱緩衝區,**山丘與樹木在 gemini 版實際上
   不會顯示**。合流版改為通用的 `create_scene_buffers()` /
   `cleanup_scene_buffers()` helper,四類物件(山丘/建築/樹木/圓柱)在所有
   載入路徑(初始/R鍵重載/選單載入/自動重載/退出)都正確處理。
2. **scene_editor.py 三份重複 class** 已去重。
3. **launch.bat 引用不存在的 map_v1_8.txt 與壞掉的 .venv**
   (該 venv 建立於另一台電腦,本機不可用)——已改用系統 python。
4. gemini 版「每幀開始即啟用的 cProfile」未移植(會拖慢整體效能;
   需要分析時用 GitHub 版 main.py 內註解掉的 profiler 程式碼)。

## 注意事項

- **執行請用 launch.bat / launch_editor.bat**(或先 `set PYTHONIOENCODING=utf-8`):
  scene_parser 部分訊息含 cp950 無法編碼的字元,沒設定時場景解析會被
  UnicodeEncodeError 中斷。
- 編輯器需要 **PyQt5**(`pip install PyQt5`,本機已於 2026-06-12 安裝)。
- 球體(sphere)仍走舊的 GLU 即時模式,尚未 VBO 化(見 TODO.md)。

## 驗證紀錄(2026-06-12,本機)

- 全部 .py 通過 py_compile
- 模擬器以實際路線 scene.txt 跑 25 秒無錯誤:
  山丘 11、建築 824、樹木 48、圓柱 381 個物件的緩衝區全部建立,小地圖烘焙成功
- 編輯器啟動並執行 20 秒無錯誤
