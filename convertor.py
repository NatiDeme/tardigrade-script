#########################################################
# Generates a geojson nested pie-chart from csv
# Author: Nicolas Bozon
# Copyright 2024 MapTiler AG
#########################################################

import csv
import geojson
from shapely.geometry import Polygon, mapping
from pyproj import Proj, Transformer
import math


def load_csv_data(file_path):
    # print(file_path)
    """Load CSV data and extract directions, risks, and center point."""
    directions = {}
    risks = {"R1": {},"R2": {}, "R3": {}}
    center = None

    with open(file_path, "r", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            area = row["Area"]
          
            if area == "Site":
                # Extract center coordinates from the "Site" first row
                center = (float(row["Lon_NO"]), float(row["Lat_NO"]))
                continue

            direction, radius = area.split("_R")
            radius_key = f"R{radius}"
            risk = row["Risk"]

            # Map direction and risk
            if direction not in directions:
                directions[direction] = True
            risks[radius_key][direction] = risk

    if not center:
        raise ValueError("Center (site row) not found in the CSV file.")
    return list(directions.keys()), risks, center


def calculate_arc_points(center, radius, start_angle, end_angle, transformer_to_geo, num_points=30):
    """Calculate points along an arc for a given radius and angle range."""
    points = []
    for angle in range(num_points + 1):
        theta = math.radians(start_angle + (end_angle - start_angle) * angle / num_points)
        # Use sin for X and cos for Y for correct rotation
        x = radius * math.sin(theta)
        y = radius * math.cos(theta)
        lon, lat = transformer_to_geo.transform(x, y)  # Converts back to geographic
        points.append((lon, lat))
    return points


def generate_pie_chart(directions, risks, center, radius_most_inner, radius_inner, radius_outer, transformer_to_geo):
    """Generate pie charts for inner and outer circles."""
    most_inner_features = []
    inner_features = []
    outer_features = []

    num_segments = len(directions)
    for i, direction in enumerate(directions):
        # Calculate start and end angles for the current segment
        start_angle = i * (360 / num_segments)
        end_angle = start_angle + (360 / num_segments)

        # Most Inner circle (R1)
        most_inner_arc_points = calculate_arc_points(center, radius_most_inner, start_angle, end_angle, transformer_to_geo)
        most_inner_polygon_points = [center] + most_inner_arc_points + [center]
        most_inner_polygon = Polygon(most_inner_polygon_points)

        most_inner_features.append(geojson.Feature(
            geometry=mapping(most_inner_polygon),
            properties={"Area": f"{direction}_R1", "Risk": risks["R1"][direction]}
        ))

        # Inner circle (R2)
        inner_arc_points = calculate_arc_points(center, radius_inner, start_angle, end_angle, transformer_to_geo)
        inner_polygon_points = inner_arc_points + most_inner_arc_points[::-1]
        inner_polygon = Polygon(inner_polygon_points)

        inner_features.append(geojson.Feature(
            geometry=mapping(inner_polygon),
            properties={"Area": f"{direction}_R2", "Risk": risks["R2"][direction]}
        ))

        # Outer circle (R3)
        outer_arc_points = calculate_arc_points(center, radius_outer, start_angle, end_angle, transformer_to_geo)
        outer_polygon_points = outer_arc_points + inner_arc_points[::-1]
        outer_polygon = Polygon(outer_polygon_points)

        outer_features.append(geojson.Feature(
            geometry=mapping(outer_polygon),
            properties={"Area": f"{direction}_R2", "Risk": risks["R2"][direction]}
        ))

    return geojson.FeatureCollection(most_inner_features), geojson.FeatureCollection(inner_features), geojson.FeatureCollection(outer_features)


def merge_inner_outer(most_inner, inner, outer):
    """Merge inner and outer pie charts into a single nested pie chart."""
    merged_features = most_inner["features"] + inner["features"] + outer["features"]
    return geojson.FeatureCollection(merged_features)


def main():
    # Input CSV file
    input_csv = "./input.csv"

    # Load directions, risks, and center from csv
    directions, risks, center = load_csv_data(input_csv)

    # Initialize transformer from WGS84 to azimuthal equidistant projection
    local_proj = Proj(proj="aeqd", lat_0=center[1], lon_0=center[0])
    transformer_to_local = Transformer.from_proj("epsg:4326", local_proj, always_xy=True)
    transformer_to_geo = Transformer.from_proj(local_proj, "epsg:4326", always_xy=True)

    # Generate inner and outer pie charts
    most_inner_pie_chart, inner_pie_chart, outer_pie_chart = generate_pie_chart(directions, risks, center, 20, 100, 200, transformer_to_geo)

    # Merge into a single nested pie chart
    nested_pie_chart = merge_inner_outer(most_inner_pie_chart, inner_pie_chart, outer_pie_chart)

    # Save to GeoJSON
    with open("nested_pie_chart_second.geojson", "w") as f:
        geojson.dump(nested_pie_chart, f)

    print("Nested pie chart saved as: nested_pie_chart.geojson")


if __name__ == "__main__":
    main()