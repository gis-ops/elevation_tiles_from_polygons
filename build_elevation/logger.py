import logging

LOGGER = logging.getLogger("build_elevation")
LOGGER.setLevel(logging.INFO)

handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s"))
LOGGER.addHandler(handler)
