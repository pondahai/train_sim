# -*- coding: utf-8 -*-
"""OSM 建物 → scene.txt `building` 行的獨立驗證腳本。

TODO.md「OSM 自動生成沿線建物」實作順序的第 1 步:
輸入經緯度＋範圍,從 Overpass API 抓建物輪廓,
每棟擬合最小面積外接矩形,輸出 `building` 行(stdout 或 --out 檔案)。
詳細設計見 docs/osm_buildings_research.md。

用法範例:
    python tools/osm_buildings.py --lat 25.0936 --lon 121.5264 --radius 300
    python tools/osm_buildings.py --bbox 25.091 121.523 25.096 121.530 --out out.txt
    python tools/osm_buildings.py --selftest

座標慣例(輸出的 building 行):
    rel_x = 東向公尺、rel_z = 北向公尺(相對原點,預設為查詢中心)、
    rel_y = 0、ry = -(矩形長軸自東向逆時針角度)。
    scene_parser 對 rel 座標做的是剛體旋轉,建物之間的相對配置不變;
    矩形有 180° 對稱性,此 ry 慣例與位置轉換一致。

資料授權: © OpenStreetMap contributors (ODbL)。
"""
import argparse
import hashlib
import json
import math
import os
import sys
import urllib.parse
import urllib.request

DEFAULT_API_URL = "https://overpass-api.de/api/interpreter"
DEFAULT_CACHE_DIR = "osm_cache"
METERS_PER_DEG_LAT = 110540.0
METERS_PER_DEG_LON_EQUATOR = 111320.0


# --- 經緯度 → 局部公尺(等距圓柱近似,10km 內誤差 < 0.1%) ---
def latlon_to_en(lat, lon, lat0, lon0):
    east = (lon - lon0) * math.cos(math.radians(lat0)) * METERS_PER_DEG_LON_EQUATOR
    north = (lat - lat0) * METERS_PER_DEG_LAT
    return east, north


def polygon_area(points):
    """Shoelace 面積(絕對值,平方公尺)。points: [(x, y), ...]"""
    n = len(points)
    s = 0.0
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return abs(s) * 0.5


def convex_hull(points):
    """Andrew monotone chain。回傳逆時針凸包頂點。"""
    pts = sorted(set(points))
    if len(pts) <= 2:
        return list(pts)

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def min_area_rect(points):
    """最小面積外接矩形(rotating calipers:逐凸包邊試方向)。

    回傳 (cx, cy, w, d, angle_deg):
    w 為沿長軸的邊長、angle_deg 為長軸自 +x(東)逆時針角度,
    d 為垂直方向邊長,(cx, cy) 為矩形中心。
    """
    hull = convex_hull(points)
    if len(hull) == 0:
        return None
    if len(hull) == 1:
        return (hull[0][0], hull[0][1], 0.0, 0.0, 0.0)

    best = None
    n = len(hull)
    for i in range(n):
        x1, y1 = hull[i]
        x2, y2 = hull[(i + 1) % n]
        ex, ey = x2 - x1, y2 - y1
        elen = math.hypot(ex, ey)
        if elen < 1e-9:
            continue
        ux, uy = ex / elen, ey / elen          # 邊方向
        vx, vy = -uy, ux                       # 垂直方向
        us = [p[0] * ux + p[1] * uy for p in hull]
        vs = [p[0] * vx + p[1] * vy for p in hull]
        umin, umax = min(us), max(us)
        vmin, vmax = min(vs), max(vs)
        area = (umax - umin) * (vmax - vmin)
        if best is None or area < best[0]:
            best = (area, ux, uy, vx, vy, umin, umax, vmin, vmax)

    if best is None:
        return None
    _, ux, uy, vx, vy, umin, umax, vmin, vmax = best
    uc, vc = (umin + umax) * 0.5, (vmin + vmax) * 0.5
    cx = uc * ux + vc * vx
    cy = uc * uy + vc * vy
    w, d = umax - umin, vmax - vmin
    angle = math.degrees(math.atan2(uy, ux))
    if w < d:  # 讓 w 對應長軸,角度跟著轉 90°
        w, d = d, w
        angle += 90.0
    angle = (angle + 90.0) % 180.0 - 90.0      # 正規化到 (-90, 90]
    return (cx, cy, w, d, angle)


def parse_building_height(tags, level_height, default_levels):
    """高度(公尺):height 標籤 → levels×層高 → 預設層數×層高。

    回傳 (height, source) source ∈ {'height', 'levels', 'default'}。
    """
    h = tags.get("height")
    if h:
        try:
            return float(str(h).lower().replace("m", "").replace(",", ".").strip()), "height"
        except ValueError:
            pass
    levels = tags.get("building:levels")
    if levels:
        try:
            lv = float(str(levels).replace(",", ".").strip())
            if lv > 0:
                return lv * level_height, "levels"
        except ValueError:
            pass
    return default_levels * level_height, "default"


# --- Overpass ---
def build_overpass_query(south, west, north, east, timeout_s):
    return (
        f"[out:json][timeout:{timeout_s}];"
        f'way["building"]({south:.7f},{west:.7f},{north:.7f},{east:.7f});'
        "out geom;"
    )


def fetch_overpass(query, api_url, cache_dir, use_cache, timeout_s):
    cache_path = None
    if use_cache:
        key = hashlib.sha1(query.encode("utf-8")).hexdigest()[:16]
        cache_path = os.path.join(cache_dir, f"overpass_{key}.json")
        if os.path.exists(cache_path):
            print(f"# 使用快取: {cache_path}", file=sys.stderr)
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)

    print(f"# 查詢 Overpass API: {api_url}", file=sys.stderr)
    req = urllib.request.Request(
        api_url,
        data=("data=" + urllib.parse.quote(query)).encode("utf-8"),
        headers={"User-Agent": "train_sim-osm-buildings/0.1"},
    )
    with urllib.request.urlopen(req, timeout=timeout_s + 30) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    if cache_path:
        os.makedirs(cache_dir, exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        print(f"# 已快取到: {cache_path}", file=sys.stderr)
    return data


def buildings_from_overpass(data, lat0, lon0, min_area, level_height, default_levels):
    """Overpass JSON → [(cx, cz, w, d, ry, h, source), ...](scene 座標慣例)。"""
    results = []
    skipped_small = 0
    height_sources = {"height": 0, "levels": 0, "default": 0}
    for el in data.get("elements", []):
        if el.get("type") != "way":
            continue
        geom = el.get("geometry")
        if not geom or len(geom) < 3:
            continue
        pts = [latlon_to_en(g["lat"], g["lon"], lat0, lon0) for g in geom]
        # 閉合 way 首尾重複,去掉尾點避免影響凸包
        if len(pts) > 1 and pts[0] == pts[-1]:
            pts = pts[:-1]
        if len(pts) < 3:
            continue
        if polygon_area(pts) < min_area:
            skipped_small += 1
            continue
        rect = min_area_rect(pts)
        if rect is None or rect[2] <= 0 or rect[3] <= 0:
            continue
        cx, cy, w, d, angle = rect
        h, source = parse_building_height(el.get("tags", {}), level_height, default_levels)
        height_sources[source] += 1
        # ry = -angle:見模組 docstring 的座標慣例
        results.append((cx, cy, w, d, -angle, h, source))
    print(
        f"# 建物 {len(results)} 棟(高度來源 height:{height_sources['height']} "
        f"levels:{height_sources['levels']} 預設:{height_sources['default']});"
        f" 面積 < {min_area}m2 略過 {skipped_small} 個",
        file=sys.stderr,
    )
    return results


def format_building_lines(buildings, comment):
    lines = [
        f"# auto-osm begin {comment}",
        "# 資料來源: © OpenStreetMap contributors (ODbL)",
    ]
    for cx, cz, w, d, ry, h, _source in buildings:
        lines.append(
            f"building {cx:.2f} 0 {cz:.2f} 0 {ry:.2f} 0 {w:.2f} {d:.2f} {h:.1f}"
        )
    lines.append("# auto-osm end")
    return lines


# --- 離線自我測試(不需網路,驗證矩形擬合) ---
def selftest():
    ok = True

    def check(name, cond, detail=""):
        nonlocal ok
        status = "OK " if cond else "FAIL"
        print(f"[{status}] {name} {detail}")
        if not cond:
            ok = False

    # 1. 軸對齊矩形 20x10,中心 (5, 3)
    pts = [(-5, -2), (15, -2), (15, 8), (-5, 8)]
    cx, cy, w, d, a = min_area_rect(pts)
    check("軸對齊矩形", abs(cx - 5) < 1e-6 and abs(cy - 3) < 1e-6
          and abs(w - 20) < 1e-6 and abs(d - 10) < 1e-6 and abs(a) < 1e-6,
          f"({cx:.2f},{cy:.2f}) {w:.2f}x{d:.2f} @{a:.2f}°")

    # 2. 旋轉 30° 的 20x10 矩形
    base = [(-10, -5), (10, -5), (10, 5), (-10, 5)]
    r = math.radians(30)
    pts = [(x * math.cos(r) - y * math.sin(r), x * math.sin(r) + y * math.cos(r))
           for x, y in base]
    cx, cy, w, d, a = min_area_rect(pts)
    check("旋轉 30° 矩形", abs(w - 20) < 1e-6 and abs(d - 10) < 1e-6
          and abs(((a - 30) + 90) % 180 - 90) < 1e-6,
          f"{w:.2f}x{d:.2f} @{a:.2f}°")

    # 3. L 形(外接矩形應為 30x20)
    pts = [(0, 0), (30, 0), (30, 10), (10, 10), (10, 20), (0, 20)]
    cx, cy, w, d, a = min_area_rect(pts)
    check("L 形外接", abs(w - 30) < 1e-6 and abs(d - 20) < 1e-6,
          f"{w:.2f}x{d:.2f} @{a:.2f}°")
    check("L 形面積", abs(polygon_area(pts) - 400) < 1e-6,
          f"{polygon_area(pts):.1f} m2")

    # 4. 含內部點(凸包應忽略)
    pts = [(-5, -2), (15, -2), (15, 8), (-5, 8), (3, 3), (7, 1)]
    _, _, w, d, _ = min_area_rect(pts)
    check("內部點忽略", abs(w - 20) < 1e-6 and abs(d - 10) < 1e-6, f"{w:.2f}x{d:.2f}")

    # 5. 經緯度轉換:緯度 +0.001° ≈ 北向 110.54m
    e, n = latlon_to_en(25.001, 121.5, 25.0, 121.5)
    check("緯度→北向", abs(n - 110.54) < 0.01, f"n={n:.2f}m")
    e, n = latlon_to_en(25.0, 121.501, 25.0, 121.5)
    expect_e = math.cos(math.radians(25.0)) * 111.320
    check("經度→東向", abs(e - expect_e) < 0.01, f"e={e:.2f}m (預期 {expect_e:.2f})")

    # 6. 高度 fallback 順序
    check("height 標籤", parse_building_height({"height": "12.5 m"}, 3, 3) == (12.5, "height"))
    check("levels 標籤", parse_building_height({"building:levels": "4"}, 3, 3) == (12.0, "levels"))
    check("預設高度", parse_building_height({}, 3.0, 3) == (9.0, "default"))

    print("自我測試:", "全部通過" if ok else "有失敗項目")
    return 0 if ok else 1


def main():
    # Windows 主控台常是 cp950,無法編碼 © 等字元時以 ? 取代而非整個崩潰
    for stream in (sys.stdout, sys.stderr):
        try: stream.reconfigure(errors="replace")
        except Exception: pass

    ap = argparse.ArgumentParser(
        description="從 OSM/Overpass 抓建物,輸出 scene.txt 的 building 行(驗證腳本)")
    ap.add_argument("--lat", type=float, help="查詢中心緯度")
    ap.add_argument("--lon", type=float, help="查詢中心經度")
    ap.add_argument("--radius", type=float, default=300.0, help="查詢半徑(公尺,預設 300)")
    ap.add_argument("--bbox", type=float, nargs=4, metavar=("S", "W", "N", "E"),
                    help="直接給 bbox(南 西 北 東),取代 --lat/--lon/--radius")
    ap.add_argument("--origin-lat", type=float, help="場景 (0,0) 對應緯度(預設=查詢中心)")
    ap.add_argument("--origin-lon", type=float, help="場景 (0,0) 對應經度(預設=查詢中心)")
    ap.add_argument("--min-area", type=float, default=20.0, help="最小建物面積 m2(預設 20)")
    ap.add_argument("--level-height", type=float, default=3.0, help="每層樓高(預設 3m)")
    ap.add_argument("--default-levels", type=float, default=3.0, help="無標籤時的預設層數(預設 3)")
    ap.add_argument("--max-count", type=int, default=0, help="輸出棟數上限(取面積最大者,0=不限)")
    ap.add_argument("--out", help="輸出檔案(預設 stdout;檔案以附加模式寫入)")
    ap.add_argument("--api-url", default=DEFAULT_API_URL)
    ap.add_argument("--cache-dir", default=DEFAULT_CACHE_DIR)
    ap.add_argument("--no-cache", action="store_true", help="不讀寫快取")
    ap.add_argument("--timeout", type=int, default=60, help="Overpass 查詢 timeout 秒數")
    ap.add_argument("--selftest", action="store_true", help="執行離線自我測試後結束")
    args = ap.parse_args()

    if args.selftest:
        sys.exit(selftest())

    if args.bbox:
        south, west, north, east = args.bbox
        center_lat = (south + north) * 0.5
        center_lon = (west + east) * 0.5
    elif args.lat is not None and args.lon is not None:
        center_lat, center_lon = args.lat, args.lon
        dlat = args.radius / METERS_PER_DEG_LAT
        dlon = args.radius / (METERS_PER_DEG_LON_EQUATOR * math.cos(math.radians(center_lat)))
        south, north = center_lat - dlat, center_lat + dlat
        west, east = center_lon - dlon, center_lon + dlon
    else:
        ap.error("需要 --lat/--lon 或 --bbox(或 --selftest)")
        return

    lat0 = args.origin_lat if args.origin_lat is not None else center_lat
    lon0 = args.origin_lon if args.origin_lon is not None else center_lon

    query = build_overpass_query(south, west, north, east, args.timeout)
    try:
        data = fetch_overpass(query, args.api_url, args.cache_dir,
                              not args.no_cache, args.timeout)
    except Exception as e:
        print(f"錯誤: Overpass 查詢失敗: {e}", file=sys.stderr)
        sys.exit(1)

    buildings = buildings_from_overpass(
        data, lat0, lon0, args.min_area, args.level_height, args.default_levels)

    if args.max_count and len(buildings) > args.max_count:
        buildings.sort(key=lambda b: b[2] * b[3], reverse=True)
        buildings = buildings[:args.max_count]
        print(f"# 套用 --max-count,保留面積最大的 {args.max_count} 棟", file=sys.stderr)

    comment = (f"origin=({lat0:.6f},{lon0:.6f}) "
               f"bbox=({south:.5f},{west:.5f},{north:.5f},{east:.5f})")
    lines = format_building_lines(buildings, comment)

    if args.out:
        with open(args.out, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        print(f"# 已附加 {len(buildings)} 行 building 到 {args.out}", file=sys.stderr)
    else:
        print("\n".join(lines))


if __name__ == "__main__":
    main()
