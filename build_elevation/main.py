from shapely.geometry import shape, box, Polygon
import json
import math
import click
from urllib import request
import gzip
from pathlib import Path, PurePath

from .logger import LOGGER

def get_json(filepath):
    with open(filepath) as f:
        obj = json.load(f)

    return obj


def geojson_feature_to_poly(geojson):
    """Assumes that the GeoJSON file has one feature only"""
    if not len(geojson) == 1:
        LOGGER.warn(f"GeoJSON with more than one feature detected. Proceeding with the first one.")
    return Polygon(shape(geojson[0]["geometry"]))


def create_grid_from_bounds(bounds):
    """Creates regular grid of size 1x1 within specified bounds
    """
    grid_polys = []
    for x in range(bounds[0], bounds[2]):
        for y in range(bounds[1], bounds[3]):
            poly = box(x, y, x + 1, y + 1)
            grid_polys.append(poly)

    return grid_polys


def download_tile(southwest, directory):
    """Download tile whose filename matches the southwestern coordinate tuple."""
    x, y = southwest
    tile_name = '%s%02d%s%03d.hgt' % ('S' if y < 0 else 'N', abs(y), 'W' if x < 0 else 'E', abs(x))
    dir_name = '%s%02d' % ('S' if y < 0 else 'N', abs(y))
    url = f"http://s3.amazonaws.com/elevation-tiles-prod/skadi/{dir_name}/{tile_name}.gz"
    dest_directory = Path(directory, dir_name)
    Path.mkdir(dest_directory, exist_ok=True)
    filepath = Path(dest_directory, tile_name)
    if not filepath.is_file():
        LOGGER.info(f"Downloading tile at {url}")
        with request.urlopen(url) as res:
            with gzip.GzipFile(fileobj=res, mode='rb') as gz:
                with open(filepath, 'wb') as f:
                    f.write(gz.read())
    else:
        LOGGER.info(f"Already downloaded tile {url}")


@click.command()
@click.argument("config_file", type=click.Path())
@click.argument("elevation_folder", type=click.Path())
def main(config_file, elevation_folder):
    """Downloads all elevation tiles that intersect with GeoJSON geometries specified in the config file.
    The config file is expected as an osmium extract config file.
    """
    config = get_json(config_file)
    expected = 0
    total = 0
    for extract in config["extracts"]:
        geojson_file = extract["polygon"]["file_name"]
        geojson = get_json(geojson_file)["features"]
        poly = geojson_feature_to_poly(geojson)
        bounds = poly.bounds
        rounded_bounds = xmin, ymin, xmax, ymax = [math.floor(x) if i < 2 else math.ceil(x) for i, x in enumerate(bounds)]
        expected += (xmax-xmin)*(ymax-ymin)
        grid_polys = create_grid_from_bounds(rounded_bounds)
        for grid_poly in grid_polys:
            if poly.intersects(grid_poly):
                sw = grid_poly.bounds[0:2]
                download_tile(sw, elevation_folder)
                total += 1

    LOGGER.info(f"Intersection saved {expected - total} tiles!")
