from datetime import date, timedelta
import requests
import pandas as pd
from shapely.geometry import Polygon, mapping
from shapely.geometry.polygon import LinearRing  # Để validate polygon
import json  # Để parse GeoJSON
import rasterio
from rasterio.enums import Resampling  # Thêm cho resample
from rasterio.plot import show
from rasterio.mask import mask  # Để clip local
import matplotlib
matplotlib.use('Agg')  # Backend non-interactive cho server headless
import matplotlib.pyplot as plt
import os
import argparse  # Để parse args tốt hơn
import time
import base64
from pyproj import Transformer

# Sentinel Hub Bearer Token
TOKEN = 'eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6IncxWjNSSGNyWjVVMGFQWXhNX1hscCJ9.eyJlbWFpbCI6ImFkbWluQGZwdG9qLmNvbSIsImFwaV9rZXkiOiJQTEFLNjg2N2FhYzMyMmZmNDYxYTg5YzcyZGIxZGZlMzBlNjkiLCJvcmdhbml6YXRpb25faWQiOjc2MzYwNCwicGxfcHJpbmNpcGFsIjoicHJuOmFkbWluOnByaW5jaXBhbDp1c2VyOjc5NTU4MyIsInJvbGVfbGV2ZWwiOjEwMCwic2hfdXNlcl9pZCI6IjBiYzZiZmNjLTJiYzMtNGQwYy05N2NlLWZkOGE0Yjk4YmE4YyIsInVzZXJfaWQiOjc5NTU4MywiYWNjb3VudCI6IjY0OGI1ZTRhLWNkZmUtNGYzOC04NDk2LTdhMjRlZTZiY2NjOCIsInBsX3Byb2plY3QiOiI2NDhiNWU0YS1jZGZlLTRmMzgtODQ5Ni03YTI0ZWU2YmNjYzgiLCJwbF9wcm9qZWN0X3JvbGUiOjEwMDAsInBsX3dvcmtzcGFjZSI6Ijk0ZDZmMWNhLWIzMDEtNDBjYS05MDA4LTBjNDJiMjg3NTcxYiIsInBsX3dvcmtzcGFjZV9yb2xlIjoxMDAwLCJwbF9jdXN0b21lcl9hY2NvdW50IjoiNzAzZjg4NzItOTg1Ny00ZGRlLWI5MDMtY2UzNDNkZDA1NjA0IiwicGxfY3VzdG9tZXJfYWNjb3VudF9yb2xlIjoxMDAwLCJjaWQiOiJsMng4ano5YkNsMjVFb2d2SHE1YTA0eW1BWjA0VUNWOCIsImlzcyI6Imh0dHBzOi8vbG9naW4ucGxhbmV0LmNvbS8iLCJzdWIiOiJhdXRoMHxwbGFuZXQtdXNlci1kYnw3OTU1ODMiLCJhdWQiOlsiaHR0cHM6Ly9hcGkucGxhbmV0LmNvbS8iLCJodHRwczovL3BsYW5ldC1lZHAtcHJvZC0xLnVzLmF1dGgwLmNvbS91c2VyaW5mbyJdLCJpYXQiOjE3NjEwMjM5NTIsImV4cCI6MTc2MTAzMjU1Miwic2NvcGUiOiJvcGVuaWQgcHJvZmlsZSBlbWFpbCIsImF6cCI6ImwyeDhqejliQ2wyNUVvZ3ZIcTVhMDR5bUFaMDRVQ1Y4In0.SdYif24_HYkn5bS0gKLS6XY0DwsvU8N22XuQFT7MVoCJYFNgfObgGJ9GvoHP8AgEg4jy09duTOMJ7tgVYaB3q0YA_tL1EnYcfvYk3miIwkzkh1CtZ-5s6Rh8EFpwvSUlCNyLWae7WVhPuohfwf40VpCOLVBilts2w9RBxJyv9dDnFJbpYnBIC_bQvRksj_xclpzkk1mTgjNjGzKiRE9gczzxE1dYRuEgtITdOHD6JDs4UqRvrwzJzZHpPpCGUL_yQxZ90CJahQ56GfPg5W8k5jNfP6T23EZBBqge1CfAG_D4oHdiwBYCZm4w01sTJmfNFpaQ-6pKYNTSV1B4KbcO2Q'
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

# Parser args: python getimage.py --geojson input.geojson --upscale 2
parser = argparse.ArgumentParser(description="Tải và crop ảnh Sentinel-2 theo GeoJSON polygon vuông từ user, với upscale cho nét hơn.")
parser.add_argument('--geojson', type=str, required=True, help="Đường dẫn file GeoJSON polygon vuông (4 cạnh) từ user vẽ trên map.")
parser.add_argument('--cloud', type=float, default=50.0, help="Cloud cover threshold (default 50%).")
parser.add_argument('--days', type=int, default=30, help="Số ngày tìm kiếm gần nhất (default 30).")
parser.add_argument('--upscale', type=int, default=2, help="Yếu tố upscale để làm nét hơn (default 2, dùng Resampling.bilinear).")
args = parser.parse_args()

# Đọc GeoJSON và tạo footprint
with open(args.geojson, 'r') as f:
    geojson_data = json.load(f)

if geojson_data['type'] != 'Feature' or geojson_data['geometry']['type'] != 'Polygon':
    raise Exception("GeoJSON phải là Feature với Polygon geometry.")

coords = geojson_data['geometry']['coordinates'][0]  # Lấy exterior ring
if len(coords) != 5 or not isinstance(coords[0], (list, tuple)) or len(coords[0]) != 2:
    raise Exception("Polygon phải vuông 4 cạnh + đóng (5 điểm).")

# Tạo Polygon từ coords (lon, lat -> x, y)
footprint_coords = [(c[0], c[1]) for c in coords]
footprint = Polygon(footprint_coords)
if not footprint.is_valid or not isinstance(footprint.exterior, LinearRing) or footprint.area == 0:
    raise Exception("Polygon không hợp lệ hoặc không vuông.")

aoi_geojson = geojson_data['geometry']  # Cho search, nhưng không dùng cho clip nữa

# Tính kích thước AOI để in
bounds = footprint.bounds  # (minx, miny, maxx, maxy) = (min_lon, min_lat, max_lon, max_lat)
delta_lat = bounds[3] - bounds[1]
delta_lon = bounds[2] - bounds[0]
approx_size_km = delta_lat * 111  # ~111 km/° lat, approx cho lon ở 21N
print(f"AOI từ GeoJSON user vẽ: lat {bounds[1]:.6f}-{bounds[3]:.6f}, lon {bounds[0]:.6f}-{bounds[2]:.6f} (~{approx_size_km:.1f}km x {approx_size_km * (delta_lon / delta_lat):.1f}km)")

# Ngày tìm kiếm
today = date.today()
end_date = today.strftime("%Y-%m-%d")
start_date = (today - timedelta(days=args.days)).strftime("%Y-%m-%d")

# 1. Tìm scene mới nhất
def find_latest_scene():
    search_request = {
        "collections": ["sentinel-2-l2a"],
        "datetime": f"{start_date}T00:00:00Z/{end_date}T23:59:59Z",
        "bbox": [bounds[0], bounds[1], bounds[2], bounds[3]],
        "filter": f"eo:cloud_cover <= {args.cloud}",
        "limit": 50
    }
    print("Search request:", json.dumps(search_request, indent=2))
    search_url = "https://services.sentinel-hub.com/api/v1/catalog/1.0.0/search"
    response = requests.post(search_url, headers=HEADERS, json=search_request)
    print("Response status:", response.status_code)
    print("Response text:", response.text)
    if response.status_code != 200:
        raise Exception(f"Query failed: {response.text}")

    json_data = response.json()
    features = json_data.get("features", [])
    if not features:
        raise Exception("Không tìm thấy ảnh phù hợp. Thử tăng --days, --cloud, hoặc mở rộng AOI trong GeoJSON.")

    # Sắp xếp theo ngày mới nhất
    features.sort(key=lambda f: f["properties"]["datetime"], reverse=True)
    latest_feature = features[0]
    item_id = latest_feature["id"]
    sensing_date = latest_feature["properties"]["datetime"].split("T")[0]
    cloud_cover = latest_feature["properties"]["eo:cloud_cover"]
    print(f"Tìm thấy scene mới nhất: {item_id} (ngày: {sensing_date}, cloud: {cloud_cover}%)")
    
    return item_id, sensing_date, cloud_cover

# 2. Tải full true color asset dùng Process API
def download_true_color(sensing_date):
    # Project bbox to UTM 48N (EPSG:32648)
    transformer = Transformer.from_crs("epsg:4326", "epsg:32648", always_xy=True)
    minx, miny = transformer.transform(bounds[0], bounds[1])
    maxx, maxy = transformer.transform(bounds[2], bounds[3])
    projected_bbox = [minx, miny, maxx, maxy]

    process_request = {
        "input": {
            "bounds": {
                "properties": {
                    "crs": "http://www.opengis.net/def/crs/EPSG/0/32648"
                },
                "bbox": projected_bbox
            },
            "data": [
                {
                    "dataFilter": {
                        "timeRange": {
                            "from": f"{sensing_date}T00:00:00Z",
                            "to": f"{sensing_date}T23:59:59Z"
                        }
                    },
                    "type": "sentinel-2-l2a"
                }
            ]
        },
        "output": {
            "resx": 10,
            "resy": 10,
            "responses": [
                {
                    "identifier": "default",
                    "format": {
                        "type": "image/tiff"
                    }
                }
            ]
        },
        "evalscript": """
//VERSION=3
function setup() {
  return {
    input: ["B02", "B03", "B04"],
    output: { bands: 3 }
  };
}
function evaluatePixel(sample) {
  return [2.5 * sample.B04, 2.5 * sample.B03, 2.5 * sample.B02];
}
"""
    }
    print("Process request:", json.dumps(process_request, indent=2))
    process_url = "https://services.sentinel-hub.com/api/v1/process"
    response = requests.post(process_url, headers=HEADERS, json=process_request, stream=True)
    print("Response status:", response.status_code)
    print("Response text:", response.text if response.status_code != 200 else "OK")
    if response.status_code != 200:
        raise Exception(f"Process failed: {response.text}")
    
    full_tif = f"./downloads/{sensing_date}_full_true_color.tif"
    if os.path.exists(full_tif):
        print(f"File full đã tồn tại: {full_tif}. Bỏ qua tải.")
        return full_tif
    os.makedirs('./downloads/', exist_ok=True)
    
    with open(full_tif, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    print(f"Đã tải full true color TIFF: {full_tif}")
    return full_tif

# 3. Clip local dùng rasterio.mask
def clip_local(full_path, footprint):
    clipped_path = full_path.replace("_full_true_color.tif", "_clipped_true_color.tif")
    if os.path.exists(clipped_path):
        print(f"File clipped đã tồn tại: {clipped_path}. Bỏ qua clip.")
        return clipped_path
    
    with rasterio.open(full_path) as src:
        # Reproject footprint to src.crs if necessary
        if src.crs.to_epsg() != 4326:
            transformer = Transformer.from_crs("epsg:4326", src.crs, always_xy=True)
            projected_coords = [transformer.transform(lon, lat) for lon, lat in footprint.exterior.coords]
            projected_footprint = Polygon(projected_coords)
        else:
            projected_footprint = footprint
        
        # Mask với polygon
        clipped_array, clipped_transform = mask(src, [mapping(projected_footprint)], crop=True, nodata=0)
        
        profile = src.profile.copy()
        profile.update({
            "height": clipped_array.shape[1],
            "width": clipped_array.shape[2],
            "transform": clipped_transform,
            "dtype": clipped_array.dtype,
            "nodata": 0
        })
    
    with rasterio.open(clipped_path, 'w', **profile) as dst:
        dst.write(clipped_array)
    
    print(f"Đã clip local: {clipped_path}")
    return clipped_path

# Main
try:
    item_id, sensing_date, cloud_cover = find_latest_scene()
    full_path = download_true_color(sensing_date)
    tci_path = clip_local(full_path, footprint)
    
    output_path = './output_image_cropped_upscaled.png'
    upscale_factor = args.upscale
    
    with rasterio.open(tci_path) as src:
        height, width = src.height, src.width
        up_height = height * upscale_factor
        up_width = width * upscale_factor
        up_image = src.read(
            out_shape=(src.count, up_height, up_width),
            resampling=Resampling.bilinear
        )
        up_transform = src.transform * src.transform.scale(1 / upscale_factor, 1 / upscale_factor)
        up_meta = src.meta.copy()
        up_meta.update({"height": up_height, "width": up_width, "transform": up_transform})
    
    temp_up_tif = './temp_up.tif'
    with rasterio.open(temp_up_tif, 'w', **up_meta) as dest:
        dest.write(up_image)
    
    # Plot và lưu (tăng DPI cho nét)
    with rasterio.open(temp_up_tif) as up_src:
        fig, ax = plt.subplots(figsize=(12, 12))
        show(up_src, ax=ax, title=f"Ảnh Sentinel-2 (true color clipped local & upscaled x{upscale_factor} từ GeoJSON) - {sensing_date}\n(AOI từ user: cloud {cloud_cover}%)")
        plt.savefig(output_path, dpi=800, bbox_inches='tight')
        plt.close(fig)
    
    # Cleanup temp
    os.remove(temp_up_tif)
    
    print(f"Đã lưu ảnh true color clipped upscaled: {output_path}")

except Exception as e:
    print(f"Lỗi: {e}")