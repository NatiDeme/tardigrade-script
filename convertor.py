import csv
import geojson
from shapely.geometry import Polygon, mapping, LineString
from pyproj import Proj, Transformer
import math


def load_csv_data(file_path):
    """Load CSV data and extract directions, risks, and center point."""
    directions = {}
    risks = {"R0": {},"R1": {}, "R2": {}}
    center = None

    with open(file_path, "r", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            area = row["Area"]
          
            if area == "Site":
                # Extract center coordinates from the "Site" first row
                center = (float(row["Lon_NO"]), float(row["Lat_NO"]))
                direction='Site'
                radius='0'
                risk = row["Risk"]
                radius_key = f"R{radius}"
                if direction not in directions:
                    directions[direction] = True
                risks[radius_key][direction] = risk
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
    # Adjust angles to start from North (90°) and go counterclockwise
    start_angle = 90 - start_angle  # Subtract from 90 to start from North
    end_angle = 90 - end_angle
    
    # Swap start and end angles to go counterclockwise
    start_angle, end_angle = end_angle, start_angle

    angle_step = (end_angle - start_angle) / num_points

    for angle in range(num_points + 1):
        theta = math.radians(start_angle + angle * angle_step)
        # Use sin for Y and cos for X for correct rotation
        x = radius * math.cos(theta)
        y = radius * math.sin(theta)
        lon, lat = transformer_to_geo.transform(x, y)  # Converts back to geographic
        points.append((lon, lat))
    return points

def create_sector_polygon(center, inner_radius, outer_radius, start_angle, end_angle, transformer_to_geo):
    """Create a sector polygon without overlapping points."""
    # Calculate outer arc points
    outer_arc = calculate_arc_points(center, outer_radius, start_angle, end_angle, transformer_to_geo)
    
    # Calculate inner arc points in reverse order
    inner_arc = calculate_arc_points(center, inner_radius, end_angle, start_angle, transformer_to_geo)
    
    # Combine points to form a closed polygon
    points = outer_arc + inner_arc + [outer_arc[0]]
    
    return Polygon(points)

def calculate_radial_line(center, angle, radius, transformer_to_geo):
    """Calculate a line from center to the outer radius at given angle."""
    adjusted_angle = 90 - angle
    theta = math.radians(adjusted_angle)
    x = radius * math.cos(theta)
    y = radius * math.sin(theta)
    end_point = transformer_to_geo.transform(x, y)
    return LineString([center, end_point])

def generate_pie_chart(directions, risks, center, radius_most_inner, radius_inner, radius_outer, transformer_to_geo):
    """Generate pie charts for inner and outer circles."""
    features = []

    # Most Inner circle (R0)
    most_inner_arc_points= calculate_arc_points(center, radius_most_inner, 0, 360, transformer_to_geo)
    most_inner_polygon = Polygon(most_inner_arc_points + [most_inner_arc_points[0]])

    site_risk = risks["R0"].get("Site", "Unknown")
    
    features.append(geojson.Feature(
        geometry=mapping(most_inner_polygon),
        properties={"Area": "Site", "Risk": site_risk, "Type": "polygon"}
    ))
     
    # Calculate segments for R1 (100m) and R2 (200m)
    num_segments = len([d for d in directions if d != 'Site'])
    segment_angle = 360 / num_segments
    current_angle = 0

    
    
    for direction in directions:
        # Calculate start and end angles for the current segment
        if direction == 'Site':
            continue
        
        start_angle = current_angle
        end_angle = current_angle + segment_angle

        # Add radial lines for segment boundaries
        for angle in [start_angle, end_angle]:
            radial_line = calculate_radial_line(center, angle, 200, transformer_to_geo)
            features.append(geojson.Feature(
                geometry=mapping(radial_line),
                properties={
                    "Type": "line",
                    "Angle": angle
                }
            ))
        

        # Inner circle (R2)
        if direction in risks["R1"]:
            inner_arc_points = create_sector_polygon(center, radius_most_inner, radius_inner, start_angle, end_angle, transformer_to_geo)

            features.append(geojson.Feature(
                geometry=mapping(inner_arc_points),
                properties={"Area": f"{direction}_R1", "Risk": risks["R1"][direction], "Type": "polygon"}
            ))

        # Outer circle (R3)
        if direction in risks["R2"]:
            outer_arc_points = create_sector_polygon(center,radius_inner, radius_outer, start_angle, end_angle, transformer_to_geo)

            features.append(geojson.Feature(
                geometry=mapping(outer_arc_points),
                properties={"Area": f"{direction}_R2", "Risk": risks["R2"][direction], "Type": "polygon"}
            ))
        
        current_angle += segment_angle

    return geojson.FeatureCollection(features)


def main():
    # Input CSV file
    input_csv = "./input.csv"

    # Load directions, risks, and center from csv
    directions, risks, center = load_csv_data(input_csv)

    # Initialize transformer from WGS84 to azimuthal equidistant projection
    local_proj = Proj(proj="aeqd", lat_0=center[1], lon_0=center[0])
    transformer_to_geo = Transformer.from_proj(local_proj, "epsg:4326", always_xy=True)

    # Merge into a single nested pie chart
    nested_pie_chart = generate_pie_chart(directions, risks, center, 20, 100, 200, transformer_to_geo)

    # Save to GeoJSON
    with open("nested_pie_chart.geojson", "w") as f:
        geojson.dump(nested_pie_chart, f)

    print("Nested pie chart saved as: nested_pie_chart.geojson")


if __name__ == "__main__":
    main()