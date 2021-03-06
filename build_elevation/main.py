import logging

from shapely.geometry import shape, box, Polygon
import json
import math
import click
from urllib import request
import gzip
from pathlib import Path
from typing import List, Union

from .logger import LOGGER


def get_json(filepath: Path) -> dict:
    """Opens a JSON file and loads it into memory as a dictionary."""
    with open(filepath) as f:
        obj = json.load(f)

    return obj


def geojson_feature_to_poly(geojson: dict) -> Polygon:
    """Creates a shapely Polygon from the first feature in a GeoJSON-like dict."""
    if not len(geojson) == 1:
        LOGGER.warn(f"GeoJSON with more than one feature detected. Proceeding with the first one.")
    return Polygon(shape(geojson[0]["geometry"]))


def create_grid_from_bounds(bounds: List[Union[int]]) -> List[Polygon]:
    """Creates regular grid of size 1x1 within specified bounds
    """
    grid_polys = []
    for x in range(bounds[0], bounds[2]):
        for y in range(bounds[1], bounds[3]):
            poly = box(x, y, x + 1, y + 1)
            grid_polys.append(poly)

    return grid_polys


def download_tile(southwest: List[int], directory: Path) -> None:
    """Download tile whose filename matches the southwestern coordinate tuple."""
    x, y = southwest
    tile_name = '%s%02d%s%03d.hgt' % ('S' if y < 0 else 'N', abs(y), 'W' if x < 0 else 'E', abs(x))
    dir_name = '%s%02d' % ('S' if y < 0 else 'N', abs(y))
    url = f"http://s3.amazonaws.com/elevation-tiles-prod/skadi/{dir_name}/{tile_name}.gz"
    dest_directory = Path(directory, dir_name)
    Path.mkdir(dest_directory, exist_ok=True)
    filepath = Path(dest_directory, tile_name)
    if not filepath.is_file():
        LOGGER.info(f"Downloading tile from {url}")
        with request.urlopen(url) as res:
            with gzip.GzipFile(fileobj=res, mode='rb') as gz:
                with open(filepath, 'wb') as f:
                    f.write(gz.read())
    else:
        LOGGER.info(f"Already downloaded tile {url}")


@click.command()
@click.argument("input_geojson_dir", type=Path)
@click.argument("output_dir", type=Path)
@click.option("--verbose", "-v", type=bool, is_flag=True)
def main(input_geojson_dir: Path, output_dir: Path, verbose=True) -> None:
    """
    Downloads all elevation tiles that intersect with GeoJSON geometries specified in the config file.
    The config file is expected as an osmium extract config file.
    """
    if not input_geojson_dir.is_dir():
        LOGGER.critical(f"Directory {output_dir} does not contain any GeoJSON.")
    output_dir.mkdir(exist_ok=True)
    if verbose:
        LOGGER.setLevel(logging.DEBUG)

    expected = 0
    total = 0
    for fp in input_geojson_dir.resolve().iterdir():
        if not fp.suffix == '.geojson':
            continue
        LOGGER.debug(f"opening {fp.name}")

        geojson = get_json(fp)
        poly = geojson_feature_to_poly(geojson["features"])
        bounds = poly.bounds
        rounded_bounds = xmin, ymin, xmax, ymax = [math.floor(x) if i < 2 else math.ceil(x) for i, x in enumerate(bounds)]
        expected += (xmax-xmin)*(ymax-ymin)
        grid_polys = create_grid_from_bounds(rounded_bounds)
        for grid_poly in grid_polys:
            if poly.intersects(grid_poly):
                sw = grid_poly.bounds[0:2]
                download_tile(sw, output_dir)
                total += 1

    LOGGER.debug(f"Bbox extraction would've yielded {expected} tiles.")

    LOGGER.info(f"Successfully saved {total} tiles to {output_dir}!")
