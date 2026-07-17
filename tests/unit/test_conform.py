"""Conformance rules: the silver layer's business logic."""

from techtrend.lake.conform import (
    HOUSE_BRAND,
    conform_products,
    derive_audience,
    derive_category,
    infer_brand,
    parse_colors,
)


class TestCategoryRules:
    def test_footwear_boots(self):
        assert derive_category("Mens Bogs Bozeman Boots, Tall") == ("Footwear", "Boots")

    def test_first_match_wins(self):
        # 'pack' and 'boot' both present; rule order decides deterministically
        cat, _ = derive_category("Boot Pack Carrier")
        assert cat == "Footwear"

    def test_unmatched_falls_back(self):
        assert derive_category("Mystery Widget") == ("General Merchandise", "General")


class TestBrandInference:
    def test_manufacturer_found_anywhere(self):
        assert infer_brand("Womens Teva Hurricane XLT2 Sandals") == "Teva"

    def test_own_label_conforms_to_house_brand(self):
        assert infer_brand("Wicked Good Camp Moccasins") == HOUSE_BRAND


class TestAudience:
    def test_womens(self):
        assert derive_audience("Womens Trail Shoes") == "Womens"

    def test_infant_variants_unify(self):
        assert derive_audience("Infant Booties") == "Infants"
        assert derive_audience("Infants Booties") == "Infants"

    def test_default_unisex(self):
        assert derive_audience("Allagash Pack Basket") == "Unisex"


class TestColorParsing:
    def test_parses_quoted_list(self):
        assert parse_colors("['Grey/White', 'Navy']") == "Grey/White|Navy"

    def test_unparseable_is_null_not_garbage(self):
        assert parse_colors("no colors here") is None
        assert parse_colors(None) is None


def test_conform_preserves_source_lineage(sample_products):
    out = conform_products(sample_products)
    assert out.get_column("source_category").to_list() == ["Fashion"] * 3
    assert set(out.columns) >= {"category", "brand", "audience", "color_options"}
    assert out.get_column("brand").to_list() == ["Teva", "Buck", HOUSE_BRAND]
