# train_sim

# 簡易 3D 電車模擬器

這是一個使用 OpenGL 和 Pygame 開發的簡易 3D 電車模擬器。您可以控制電車的速度，並觀察其在軌道上的運行。

## 目錄結構

- `main.py` - 主程式文件，包含遊戲的主要邏輯和渲染。
- `shapes.py` - 包含繪製幾何形狀的函式。
- `track.py` - 處理軌道數據的模組。
- `cabin.py` - 渲染駕駛艙的模組。
- `scene.txt` - 場景文件，描述軌道、建築物和樹木的位置和屬性。
- `textures/` - 紋理文件夾，存放遊戲中使用的圖片紋理。

## 安裝依賴

請確保您已安裝以下 Python 庫：

- Pygame
- PyOpenGL

您可以使用以下命令安裝這些庫：

```sh
pip install pygame PyOpenGL
```

## 遊戲操作

- `W` 或 `向上鍵`：加速
- `S` 或 `向下鍵`：減速
- `G`：顯示/隱藏地面
- `L`：啟用/禁用軌道循環
- `TAB`：鎖定/解鎖滑鼠
- `R`：手動重新載入場景
- 滾輪：調整電車速度

## 遊戲啟動

運行 `main.py` 來啟動遊戲：

```sh
python main.py
```

## 場景文件格式

`scene.txt` 文件用於描述場景中的物體。每行代表一個指令，格式如下：

- `straight <length>`：添加一段直軌道，長度為 `<length>`。
- `curve <radius> <angle>`：添加一段彎曲軌道，半徑為 `<radius>`，角度為 `<angle>`。
- `building <x> <y> <z> <width> <depth> <height> [texture_file]`：添加一個建築物，位置為 `(x, y, z)`，尺寸為 `(width, depth, height)`，可選的紋理文件為 `[texture_file]`。
- `cylinder <x> <y> <z> <radius> <height> [texture_file]`：添加一個圓柱形建築物，位置為 `(x, y, z)`，半徑為 `<radius>`，高度為 `<height>`，可選的紋理文件為 `[texture_file]`。
- `tree <x> <y> <z> <height>`：添加一棵樹，位置為 `(x, y, z)`，高度為 `<height>`。

## 授權

本項目基於 MIT 許可證開源。詳情請參閱 LICENSE 文件。

---

希望這個 README 文件能夠幫助您更好地了解並使用這個簡易 3D 電車模擬器。如果您有任何問題或建議，歡迎提交 issue 或 pull request。
