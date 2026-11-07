"""
Generate a high-resolution, photorealistic city traffic map image
for CommitCon / Uber Driver portal covering Bengaluru (lat 12.83 to 13.23, lon 77.46 to 77.76).
"""

import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# Map boundaries
LAT_MIN = 12.83
LAT_MAX = 13.23
LON_MIN = 77.46
LON_MAX = 77.76

WIDTH = 2400
HEIGHT = 2400

def coord_to_px(lat, lon):
    """Convert (lat, lon) to image (x, y) coordinates."""
    x = int((lon - LON_MIN) / (LON_MAX - LON_MIN) * WIDTH)
    # Invert Y because latitude increases upwards
    y = int((LAT_MAX - lat) / (LAT_MAX - LAT_MIN) * HEIGHT)
    return x, y

def generate_map():
    # 1. Base Image - Clean modern map canvas
    im = Image.new("RGB", (WIDTH, HEIGHT), color="#F3F5F7")
    draw = ImageDraw.Draw(im)

    # 2. Draw urban neighborhoods / textured city blocks
    blocks = [
        # CBD / Downtown area
        (12.95, 77.56, 13.00, 77.62, "#EBF0F3"),
        # Tech Corridor East
        (12.91, 77.62, 12.98, 77.72, "#ECEFF2"),
        # Electronic City / South
        (12.84, 77.62, 12.90, 77.69, "#EAEFF3"),
        # North / Hebbal / Yelahanka
        (13.02, 77.56, 13.12, 77.64, "#EEF2F5"),
        # West / Rajajinagar / Peenya
        (12.96, 77.49, 13.06, 77.56, "#EDF0F3"),
        # Airport zone
        (13.16, 77.67, 13.22, 77.74, "#F0F4F7"),
    ]
    for lat1, lon1, lat2, lon2, col in blocks:
        x1, y2 = coord_to_px(lat1, lon1)
        x2, y1 = coord_to_px(lat2, lon2)
        draw.rectangle([min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)], fill=col)

    # 3. Water bodies (Lakes)
    lakes = [
        # Bellandur Lake
        [(12.936, 77.662), (12.942, 77.675), (12.935, 77.685), (12.928, 77.670)],
        # Varthur Lake
        [(12.945, 77.730), (12.955, 77.745), (12.942, 77.755), (12.935, 77.740)],
        # Ulsoor Lake
        [(12.981, 77.618), (12.986, 77.625), (12.982, 77.630), (12.977, 77.622)],
        # Hebbal Lake
        [(13.038, 77.585), (13.048, 77.595), (13.042, 77.602), (13.033, 77.592)],
        # Sankey Tank
        [(13.007, 77.570), (13.012, 77.574), (13.009, 77.578), (13.004, 77.574)],
        # Agara Lake
        [(12.920, 77.645), (12.928, 77.652), (12.922, 77.658), (12.915, 77.650)],
        # Madiwala Lake
        [(12.905, 77.615), (12.915, 77.625), (12.910, 77.632), (12.900, 77.622)],
        # Jakkur Lake
        [(13.072, 77.605), (13.082, 77.615), (13.078, 77.622), (13.068, 77.612)],
        # Yelahanka Lake
        [(13.105, 77.588), (13.115, 77.598), (13.110, 77.605), (13.100, 77.595)],
    ]
    for lake in lakes:
        pts = [coord_to_px(lat, lon) for lat, lon in lake]
        draw.polygon(pts, fill="#C4E0E8", outline="#A8D0DC")

    # 4. Green spaces / Parks
    parks = [
        # Cubbon Park
        [(12.972, 77.588), (12.980, 77.592), (12.977, 77.599), (12.969, 77.595)],
        # Lalbagh Botanical Garden
        [(12.946, 77.580), (12.955, 77.586), (12.951, 77.594), (12.942, 77.588)],
        # GKVK Botanical reserve (North)
        [(13.068, 77.565), (13.082, 77.575), (13.078, 77.588), (13.062, 77.578)],
        # Bannerghatta fringe (South)
        [(12.835, 77.565), (12.860, 77.585), (12.845, 77.605), (12.830, 77.585)],
        # KGA Golf Course
        [(12.955, 77.645), (12.963, 77.652), (12.958, 77.660), (12.950, 77.652)],
    ]
    for park in parks:
        pts = [coord_to_px(lat, lon) for lat, lon in park]
        draw.polygon(pts, fill="#D2EBD7", outline="#BDE0C4")

    # 5. Local Street Grid (Fine tertiary streets)
    # Generate horizontal and vertical street grid lines across urban centers
    grid_color = "#E3E7EC"
    for lat_step in range(85, 225, 4):
        lat = lat_step / 1000.0 * (LAT_MAX - LAT_MIN) + LAT_MIN
        y = coord_to_px(lat, LON_MIN)[1]
        draw.line([(0, y), (WIDTH, y)], fill=grid_color, width=1)
    for lon_step in range(60, 240, 4):
        lon = lon_step / 1000.0 * (LON_MAX - LON_MIN) + LON_MIN
        x = coord_to_px(LAT_MIN, lon)[0]
        draw.line([(x, 0), (x, HEIGHT)], fill=grid_color, width=1)

    # Secondary arterial roads (casing and fill)
    secondary_roads = [
        # East-West Arteries
        [(12.975, 77.50), (12.975, 77.72)], # MG Rd / Old Madras extension
        [(12.940, 77.52), (12.940, 77.70)], # South corridor
        [(13.000, 77.52), (13.000, 77.68)], # CV Raman / Rajajinagar
        [(13.040, 77.54), (13.040, 77.66)], # Sahakarnagar / Nagavara
        [(12.910, 77.56), (12.910, 77.68)], # JP Nagar / BTM
        # North-South Arteries
        [(12.86, 77.585), (13.12, 77.585)], # Bannerghatta - Hebbal mid axis
        [(12.88, 77.635), (13.05, 77.635)], # Koramangala - Indiranagar axis
        [(12.92, 77.540), (13.08, 77.540)], # West axis
        [(12.88, 77.685), (13.02, 77.685)], # Whitefield inner axis
    ]
    for road in secondary_roads:
        pts = [coord_to_px(lat, lon) for lat, lon in road]
        draw.line(pts, fill="#D1D7DE", width=4)
        draw.line(pts, fill="#FFFFFF", width=2)

    # 6. MAJOR HIGHWAYS & EXPRESSWAYS (THE TRAFFIC VIEW!)
    # Each major road has:
    # - Casing width 10px in dark slate / gray
    # - Traffic overlay width 6px with green, orange, red, and crimson colors!

    traffic_routes = [
        # === 1. AIRPORT EXPRESSWAY (NH 44 - North corridor to Z02) ===
        {
            "segments": [
                # Downtown to Hebbal (Moderate traffic)
                ([(12.978, 77.590), (13.000, 77.590), (13.035, 77.595)], "#F59E0B", "orange"),
                # Hebbal Flyover Bottleneck (Heavy congestion!)
                ([(13.035, 77.595), (13.050, 77.598)], "#EF4444", "red"),
                # Yelahanka to Airport Toll (Smooth / Fast!)
                ([(13.050, 77.598), (13.110, 77.610), (13.160, 77.640), (13.185, 77.685)], "#10B981", "green"),
                # Airport Terminal Approach (Slight slowdown / surge)
                ([(13.185, 77.685), (13.200, 77.708)], "#F59E0B", "orange"),
            ]
        },
        # === 2. OUTER RING ROAD (ORR) - Tech Corridor ===
        {
            "segments": [
                # Silk Board to Marathahalli (Severe Traffic / Red!)
                ([(12.917, 77.623), (12.925, 77.645), (12.935, 77.675), (12.955, 77.698)], "#DC2626", "crimson"),
                # Marathahalli to Mahadevapura (Heavy / Orange-Red)
                ([(12.955, 77.698), (12.985, 77.702), (13.005, 77.680)], "#EF4444", "red"),
                # Mahadevapura to Hebbal (Moderate / Yellow)
                ([(13.005, 77.680), (13.025, 77.640), (13.035, 77.595)], "#F59E0B", "orange"),
                # Hebbal to Yeshwantpur (Smooth / Green)
                ([(13.035, 77.595), (13.025, 77.555), (13.018, 77.535)], "#10B981", "green"),
            ]
        },
        # === 3. HOSUR ELEVATED EXPRESSWAY (South corridor to Z20) ===
        {
            "segments": [
                # Downtown to Silk Board (Dense Traffic / Red)
                ([(12.965, 77.595), (12.940, 77.605), (12.917, 77.623)], "#EF4444", "red"),
                # Silk Board to Bommanahalli (Heavy / Red)
                ([(12.917, 77.623), (12.900, 77.635)], "#DC2626", "crimson"),
                # Elevated Flyover to Electronic City (Fast / Green!)
                ([(12.900, 77.635), (12.875, 77.655), (12.855, 77.670)], "#10B981", "green"),
            ]
        },
        # === 4. OLD MADRAS ROAD / WHITEFIELD (East Corridor to Z03) ===
        {
            "segments": [
                # CBD to Indiranagar (Orange)
                ([(12.975, 77.605), (12.978, 77.640)], "#F59E0B", "orange"),
                # KR Puram / Tin Factory (Severe Bottleneck / Dark Red!)
                ([(12.978, 77.640), (12.998, 77.675), (13.002, 77.695)], "#B91C1C", "dark-red"),
                # Whitefield Tech corridor (Green / Orange)
                ([(13.002, 77.695), (12.985, 77.725), (12.965, 77.745)], "#10B981", "green"),
            ]
        },
        # === 5. MYSORE ROAD (South-West to Z19) ===
        {
            "segments": [
                ([(12.965, 77.570), (12.955, 77.540)], "#F59E0B", "orange"),
                ([(12.955, 77.540), (12.940, 77.500)], "#10B981", "green"),
            ]
        },
        # === 6. TUMKUR ROAD / INDUSTRIAL CORRIDOR (North-West to Z12) ===
        {
            "segments": [
                ([(13.018, 77.535), (13.045, 77.515)], "#EF4444", "red"),
                ([(13.045, 77.515), (13.080, 77.490)], "#10B981", "green"),
            ]
        },
        # === 7. NICE RING ROAD (Peripheral ring highway) ===
        {
            "segments": [
                ([(12.845, 77.670), (12.855, 77.605), (12.870, 77.535), (12.920, 77.495), (12.975, 77.475), (13.050, 77.485)], "#10B981", "green"),
            ]
        },
        # === 8. INNER RING ROAD & CBD CONNECTORS ===
        {
            "segments": [
                # Koramangala to Domlur (Heavy traffic)
                ([(12.935, 77.625), (12.960, 77.645)], "#EF4444", "red"),
                # Domlur to Indiranagar (Orange)
                ([(12.960, 77.645), (12.978, 77.640)], "#F59E0B", "orange"),
                # MG Road / Brigade Road / Richmond (Orange/Red)
                ([(12.975, 77.605), (12.971, 77.610), (12.965, 77.595)], "#DC2626", "red"),
                # Railway Station to Mall Area (Red)
                ([(12.977, 77.571), (12.985, 77.575)], "#EF4444", "red"),
            ]
        },
    ]

    # Draw Road Casings (Dark base underneath)
    for route in traffic_routes:
        for pts_geo, col, _ in route["segments"]:
            pts_px = [coord_to_px(lat, lon) for lat, lon in pts_geo]
            draw.line(pts_px, fill="#2C3540", width=10, joint="curve")

    # Draw Traffic Flow Colors (Green, Orange, Red, Crimson)
    for route in traffic_routes:
        for pts_geo, col, _ in route["segments"]:
            pts_px = [coord_to_px(lat, lon) for lat, lon in pts_geo]
            draw.line(pts_px, fill=col, width=6, joint="curve")

    # 7. Add Highway Shields & Landmark Text
    try:
        font_lg = ImageFont.truetype("arial.ttf", 26)
        font_md = ImageFont.truetype("arial.ttf", 20)
        font_sm = ImageFont.truetype("arial.ttf", 16)
        font_badge = ImageFont.truetype("arialbd.ttf", 18)
    except Exception:
        font_lg = font_md = font_sm = font_badge = ImageFont.load_default()

    labels = [
        ("NH 44 Airport Expy", 13.135, 77.635, "#1E3A8A"),
        ("Outer Ring Road (ORR)", 12.935, 77.685, "#991B1B"),
        ("Hosur Elevated Expy", 12.880, 77.658, "#1E3A8A"),
        ("Old Madras Road", 12.990, 77.665, "#9A3412"),
        ("NICE Peripheral Hwy", 12.855, 77.545, "#065F46"),
        ("Cubbon Park", 12.975, 77.593, "#15803D"),
        ("Lalbagh Garden", 12.948, 77.587, "#15803D"),
        ("Bellandur Lake", 12.932, 77.678, "#0369A1"),
        ("Ulsoor Lake", 12.983, 77.624, "#0369A1"),
        ("Hebbal Lake", 13.040, 77.597, "#0369A1"),
        ("Central CBD", 12.973, 77.601, "#374151"),
    ]

    for text, lat, lon, txt_col in labels:
        x, y = coord_to_px(lat, lon)
        # Background pill for readability
        bbox = draw.textbbox((x, y), text, font=font_sm)
        pad = 4
        pill_rect = [bbox[0] - pad, bbox[1] - pad, bbox[2] + pad, bbox[3] + pad]
        draw.rounded_rectangle(pill_rect, radius=4, fill="#FFFFFFE6", outline="#D1D5DB")
        draw.text((x, y), text, fill=txt_col, font=font_sm)

    # 8. Add Live Traffic Legend Box (Top-Left Corner)
    legend_x, legend_y = 40, 40
    leg_w, leg_h = 320, 160
    draw.rounded_rectangle(
        [legend_x, legend_y, legend_x + leg_w, legend_y + leg_h],
        radius=12,
        fill="#FFFFFFEE",
        outline="#CBD5E1",
        width=2,
    )
    draw.text((legend_x + 16, legend_y + 14), "LIVE TRAFFIC RADAR", fill="#0F172A", font=font_badge)

    leg_items = [
        ("#10B981", "Fast Flow (60 - 80 km/h)"),
        ("#F59E0B", "Moderate Delay (30 - 45 km/h)"),
        ("#EF4444", "Heavy Traffic (15 - 25 km/h)"),
        ("#B91C1C", "Severe Congestion / Bottleneck"),
    ]
    for i, (col, desc) in enumerate(leg_items):
        iy = legend_y + 48 + (i * 26)
        draw.line([(legend_x + 16, iy + 6), (legend_x + 44, iy + 6)], fill=col, width=5)
        draw.text((legend_x + 52, iy), desc, fill="#334155", font=font_sm)

    # Save output to static directory
    out_path = Path(__file__).parent.parent / "static" / "traffic_map.png"
    im.save(str(out_path), "PNG", optimize=True)
    print(f"Traffic map successfully generated at {out_path} ({WIDTH}x{HEIGHT})")

if __name__ == "__main__":
    generate_map()

