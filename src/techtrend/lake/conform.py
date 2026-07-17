"""Product conformance rules (silver layer).

The upstream extract ships degenerate attributes -- a single catch-all
category, ``brand = 'Generic'``, and colour lists stuffed into the
subcategory field. Conformance derives governed attributes from the data
itself:

* **category / subcategory** -- ordered keyword rules over the product
  name (first match wins; rules are data, reviewed like code),
* **brand** -- lexicon scan for manufacturer names appearing anywhere in
  the title; retailer own-label products conform to ``House Brand``,
* **audience** -- Womens / Mens / Kids / Toddlers / Infants / Adults,
* **color_options** -- the colour list parsed out of the corrupted
  subcategory field into a queryable pipe-delimited attribute.

Original source values are preserved as ``source_*`` columns -- conformed
data must always be traceable back to what the source actually said.
"""

from __future__ import annotations

import re

import polars as pl

# Ordered: first match wins. (category, subcategory, [keywords])
CATEGORY_RULES: list[tuple[str, str, list[str]]] = [
    ("Footwear", "Boots", ["boot"]),
    ("Footwear", "Sandals", ["sandal", "flip flop", "slide"]),
    ("Footwear", "Slippers & Moccasins", ["slipper", "moccasin", "mocs", "clog"]),
    ("Footwear", "Shoes", ["shoe", "sneaker", "oxford", "loafer", "hiker"]),
    ("Bags & Packs", "Backpacks", ["pack", "rucksack", "knapsack"]),
    ("Bags & Packs", "Bags & Totes", ["bag", "tote", "duffle", "basket", "case", "luggage"]),
    ("Knives & Tools", "Knives & Tools", ["knife", "multitool", "axe", "saw ", "tool"]),
    ("Apparel", "Outerwear", ["jacket", "parka", "coat", "vest", "anorak", "windbreaker"]),
    (
        "Apparel",
        "Tops",
        [
            "shirt",
            "tee",
            "sweater",
            "hoodie",
            "fleece",
            "pullover",
            "polo",
            "turtleneck",
            "cardigan",
            "top",
        ],
    ),
    ("Apparel", "Bottoms", ["pant", "jean", "short", "skirt", "legging", "chino"]),
    ("Apparel", "Sleep & Lounge", ["pajama", "robe", "nightgown", "boxers", "lounge"]),
    ("Apparel", "Dresses", ["dress"]),
    ("Apparel", "Socks & Base Layers", ["sock", "base layer", "long underwear", "tights"]),
    (
        "Headwear & Accessories",
        "Headwear",
        ["hat", "cap", "beanie", "headwear", "visor", "balaclava"],
    ),
    (
        "Headwear & Accessories",
        "Accessories",
        ["glove", "mitten", "scarf", "belt", "wallet", "sunglasses", "watch", "umbrella"],
    ),
    (
        "Camp & Outdoor",
        "Camp & Outdoor",
        [
            "tent",
            "sleeping",
            "lantern",
            "stove",
            "chair",
            "hammock",
            "cooler",
            "camp",
            "canoe",
            "kayak",
            "paddle",
            "snowshoe",
            "sled",
            "mold",
            "patch",
        ],
    ),
]
DEFAULT_CATEGORY = ("General Merchandise", "General")

# Manufacturer lexicon (scanned anywhere in the title). Own-label items
# without a manufacturer conform to "House Brand".
BRAND_LEXICON = [
    "L.L.Bean",
    "Teva",
    "Keen",
    "Merrell",
    "Bogs",
    "Hoka",
    "OluKai",
    "Kork-Ease",
    "Thule",
    "Darn Tough",
    "SmartWool",
    "Superfeet",
    "Buck",
    "Buff",
    "Oakley",
    "Costa",
    "Ray-Ban",
    "Carhartt",
    "Patagonia",
    "Sperry",
    "Birkenstock",
    "Chaco",
    "Salomon",
    "Oboz",
    "Dansko",
    "Blundstone",
    "Sorel",
    "Muck",
    "Crocs",
    "Minnetonka",
    "Vionic",
    "Sanuk",
    "Rainbow",
    "Reef",
]
HOUSE_BRAND = "House Brand"

AUDIENCES = ["Womens", "Mens", "Kids", "Toddlers", "Infants", "Infant", "Adults"]

_COLOR_TOKEN = re.compile(r"'([^']+)'")


def derive_category(name: str) -> tuple[str, str]:
    lowered = name.lower()
    for category, subcategory, keywords in CATEGORY_RULES:
        if any(k in lowered for k in keywords):
            return category, subcategory
    return DEFAULT_CATEGORY


def infer_brand(name: str) -> str:
    lowered = name.lower()
    for brand in BRAND_LEXICON:
        if brand.lower() in lowered:
            return brand
    return HOUSE_BRAND


def derive_audience(name: str) -> str:
    first = name.split(" ", 1)[0]
    if first in ("Infant", "Infants"):
        return "Infants"
    return first if first in AUDIENCES else "Unisex"


def parse_colors(raw: str | None) -> str | None:
    """``"['Grey/White', 'Navy']"`` -> ``"Grey/White|Navy"``; None if unparseable."""
    if not raw:
        return None
    tokens = _COLOR_TOKEN.findall(raw)
    return "|".join(t.strip() for t in tokens) if tokens else None


def conform_products(products: pl.DataFrame) -> pl.DataFrame:
    """Apply all conformance rules; keep source values for lineage."""
    names = products.get_column("name").to_list()
    cats = [derive_category(n) for n in names]
    return products.select(
        pl.col("product_id"),
        pl.col("name").str.strip_chars().alias("product_name"),
        pl.Series("category", [c for c, _ in cats]),
        pl.Series("subcategory", [s for _, s in cats]),
        pl.Series("brand", [infer_brand(n) for n in names]),
        pl.Series("audience", [derive_audience(n) for n in names]),
        pl.Series(
            "color_options",
            [parse_colors(v) for v in products.get_column("subcategory").to_list()],
            dtype=pl.Utf8,
        ),
        pl.col("base_price"),
        pl.col("base_rating"),
        pl.col("image_url"),
        pl.col("category").alias("source_category"),
        pl.col("brand").alias("source_brand"),
    )
