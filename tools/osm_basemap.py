# -*- coding: utf-8 -*-
"""OSM 圖磚 → 淡化底圖 PNG ＋ scene.txt `map` 行。

TODO.md「OSM 自動生成沿線建物」實作順序的第 2 步:
抓 XYZ 圖磚拼接、降飽和/加白,存到 textures/,
輸出對齊遊戲世界座標的 `map 圖檔 cx cz scale` 行。
與 tools/osm_buildings.py 用相同的 --lat/--lon/--radius 與原點,
兩者產物可直接疊在同一場景。

用法範例:
    python tools/osm_basemap.py --lat 25.0936 --lon 121.5264 --radius 300

座標慣例:遊戲世界 +X=西、+Z=北(見 osm_buildings.py docstring),
小地圖繪製時翻轉 X 顯示,因此底圖就是正常的北上、西左地圖,
不需鏡像;cx = -東向公尺、cz = 北向公尺、scale = 公尺/像素。

圖磚授權: © OpenStreetMap contributors (ODbL)。
請遵守 tile.openstreetmap.org 使用政策(已含 UA、本地快取)。
"""
import argparse
import math
import os
import sys
import urllib.request

from osm_buildings import latlon_to_en, METERS_PER_DEG_LAT, METERS_PER_DEG_LON_EQUATOR

DEFAULT_TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
DEFAULT_CACHE_DIR = os.path.join("osm_cache", "tiles")
TILE_SIZE = 256
EQUATOR_RESOLUTION = 156543.03392  # m/px,z=0 赤道


# --- Web Mercator 圖磚數學 ---
def latlon_to_tile(lat, lon, zoom):
    n = 2 ** zoom
    xt = (lon + 180.0) / 360.0 * n
    yt = (1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * n
    return xt, yt


def tile_to_latlon(xt, yt, zoom):
    n = 2 ** zoom
    lon = xt / n * 360.0 - 180.0
    lat = math.degrees(math.atan(math.sinh(math.pi * (1.0 - 2.0 * yt / n))))
    return lat, lon


def ground_resolution(lat, zoom):
    """地面公尺/像素(該緯度)。"""
    return EQUATOR_RESOLUTION * math.cos(math.radians(lat)) / (2 ** zoom)


def auto_zoom(lat, target_m_per_px=1.0):
    z = round(math.log2(EQUATOR_RESOLUTION * math.cos(math.radians(lat)) / target_m_per_px))
    return max(12, min(19, z))


def fetch_tile(z, x, y, tile_url, cache_dir):
    cache_path = os.path.join(cache_dir, str(z), str(x), f"{y}.png")
    if os.path.exists(cache_path):
        with open(cache_path, "rb") as f:
            return f.read()
    url = tile_url.format(z=z, x=x, y=y)
    req = urllib.request.Request(
        url, headers={"User-Agent": "train_sim-osm-basemap/0.1"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read()
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    with open(cache_path, "wb") as f:
        f.write(data)
    return data


def build_basemap(center_lat, center_lon, radius, zoom, lat0, lon0,
                  tile_url, cache_dir, desaturate, fade, max_tiles):
    from PIL import Image, ImageEnhance
    import io

    # bbox(度)
    dlat = radius / METERS_PER_DEG_LAT
    dlon = radius / (METERS_PER_DEG_LON_EQUATOR * math.cos(math.radians(center_lat)))
    south, north = center_lat - dlat, center_lat + dlat
    west, east = center_lon - dlon, center_lon + dlon

    # 覆蓋 bbox 的圖磚範圍(tile y 向南遞增)
    x_min_f, y_min_f = latlon_to_tile(north, west, zoom)
    x_max_f, y_max_f = latlon_to_tile(south, east, zoom)
    tx0, ty0 = int(math.floor(x_min_f)), int(math.floor(y_min_f))
    tx1, ty1 = int(math.floor(x_max_f)), int(math.floor(y_max_f))
    nx, ny = tx1 - tx0 + 1, ty1 - ty0 + 1
    if nx * ny > max_tiles:
        raise RuntimeError(
            f"需要 {nx}x{ny}={nx*ny} 張圖磚,超過上限 {max_tiles}。"
            f"請降低 zoom 或 radius。")

    print(f"# zoom={zoom},圖磚 {nx}x{ny}={nx*ny} 張", file=sys.stderr)
    stitched = Image.new("RGB", (nx * TILE_SIZE, ny * TILE_SIZE), (255, 255, 255))
    fetched = 0
    for iy in range(ny):
        for ix in range(nx):
            data = fetch_tile(zoom, tx0 + ix, ty0 + iy, tile_url, cache_dir)
            tile_img = Image.open(io.BytesIO(data)).convert("RGB")
            stitched.paste(tile_img, (ix * TILE_SIZE, iy * TILE_SIZE))
            fetched += 1
    print(f"# 已取得 {fetched} 張圖磚(含快取)", file=sys.stderr)

    # 淡化:先降飽和再與白色混合
    if desaturate > 0:
        stitched = ImageEnhance.Color(stitched).enhance(1.0 - desaturate)
    if fade > 0:
        white = Image.new("RGB", stitched.size, (255, 255, 255))
        stitched = Image.blend(stitched, white, fade)

    # 影像中心(像素中心)對應的經緯度 → 世界座標
    cxt = tx0 + nx / 2.0
    cyt = ty0 + ny / 2.0
    img_center_lat, img_center_lon = tile_to_latlon(cxt, cyt, zoom)
    e, n = latlon_to_en(img_center_lat, img_center_lon, lat0, lon0)
    world_cx = -e   # +X = 西
    world_cz = n    # +Z = 北
    scale = ground_resolution(img_center_lat, zoom)

    return stitched, world_cx, world_cz, scale


def main():
    for stream in (sys.stdout, sys.stderr):
        try: stream.reconfigure(errors="replace")
        except Exception: pass

    ap = argparse.ArgumentParser(
        description="抓 OSM 圖磚拼接淡化底圖,輸出 textures/ PNG 與 map 行")
    ap.add_argument("--lat", type=float, required=True, help="中心緯度")
    ap.add_argument("--lon", type=float, required=True, help="中心經度")
    ap.add_argument("--radius", type=float, default=300.0, help="覆蓋半徑(公尺,預設 300)")
    ap.add_argument("--origin-lat", type=float, help="場景 (0,0) 對應緯度(預設=中心)")
    ap.add_argument("--origin-lon", type=float, help="場景 (0,0) 對應經度(預設=中心)")
    ap.add_argument("--zoom", type=int, help="圖磚 zoom(預設自動,約 1 公尺/像素)")
    ap.add_argument("--desaturate", type=float, default=0.7, help="降飽和 0~1(預設 0.7)")
    ap.add_argument("--fade", type=float, default=0.55, help="白化 0~1(預設 0.55)")
    ap.add_argument("--out-name", help="輸出檔名(預設 map_osm_緯度_經度.png,存到 textures/)")
    ap.add_argument("--tile-url", default=DEFAULT_TILE_URL,
                    help="圖磚 URL 樣板,含 {z}/{x}/{y}(預設 OSM)")
    ap.add_argument("--cache-dir", default=DEFAULT_CACHE_DIR)
    ap.add_argument("--max-tiles", type=int, default=64, help="圖磚數量上限(預設 64)")
    args = ap.parse_args()

    lat0 = args.origin_lat if args.origin_lat is not None else args.lat
    lon0 = args.origin_lon if args.origin_lon is not None else args.lon
    zoom = args.zoom if args.zoom is not None else auto_zoom(args.lat)

    try:
        img, cx, cz, scale = build_basemap(
            args.lat, args.lon, args.radius, zoom, lat0, lon0,
            args.tile_url, args.cache_dir, args.desaturate, args.fade, args.max_tiles)
    except RuntimeError as e:
        print(f"錯誤: {e}", file=sys.stderr)
        sys.exit(1)

    name = args.out_name or f"map_osm_{args.lat:.4f}_{args.lon:.4f}.png"
    out_path = os.path.join("textures", name)
    os.makedirs("textures", exist_ok=True)
    img.save(out_path)
    print(f"# 已存 {out_path}({img.size[0]}x{img.size[1]} px,"
          f"約 {img.size[0]*scale:.0f}x{img.size[1]*scale:.0f} m)", file=sys.stderr)

    print(f"# 底圖 © OpenStreetMap contributors (ODbL)")
    print(f"map {name} {cx:.2f} {cz:.2f} {scale:.4f}")


if __name__ == "__main__":
    main()
