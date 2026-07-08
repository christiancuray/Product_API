import pytest
from decimal import Decimal

from conftest import SEED_PRODUCTS


class TestGetAllProducts:
    def test_returns_all_seeded_products(self, dynamodb_table):
        _, db = dynamodb_table
        products = db.get_all_products()

        assert len(products) == len(SEED_PRODUCTS)

    def test_converts_all_prices_to_float(self, dynamodb_table):
        _, db = dynamodb_table
        products = db.get_all_products()

        for p in products:
            assert isinstance(p["price"], float)

    def test_returns_empty_list_when_table_is_empty(self, dynamodb_table):
        table, db = dynamodb_table
        for p in SEED_PRODUCTS:
            table.delete_item(Key={"id": p["id"]})

        assert db.get_all_products() == []

    def test_items_without_price_are_returned_unchanged(self, dynamodb_table):
        table, db = dynamodb_table
        table.put_item(Item={"id": "no_price", "title": "No Price Item", "category": "Home", "description": "D"})

        products = db.get_all_products()
        no_price = next(p for p in products if p["id"] == "no_price")

        assert "price" not in no_price

    def test_items_with_non_decimal_price_are_returned_unchanged(self, dynamodb_table):
        table, db = dynamodb_table
        table.put_item(Item={"id": "str_price", "title": "Free Item", "category": "Home", "description": "D", "price": "free"})

        products = db.get_all_products()
        item = next(p for p in products if p["id"] == "str_price")

        assert item["price"] == "free"

    def test_returns_all_fields_for_each_product(self, dynamodb_table):
        _, db = dynamodb_table
        products = db.get_all_products()
        prod = next(p for p in products if p["id"] == "prod_001")

        assert prod["title"] == "Wireless Headphones"
        assert prod["category"] == "Electronics"
        assert prod["description"] == "Noise-cancelling over-ear headphones"
        assert prod["version"] == 1


class TestGetProductsByCategory:
    def test_returns_products_for_matching_category(self, dynamodb_table):
        _, db = dynamodb_table
        results = db.get_products_by_category("Computers")

        assert len(results) == 2
        assert all(p["category"] == "Computers" for p in results)

    def test_returns_empty_list_for_unknown_category(self, dynamodb_table):
        _, db = dynamodb_table
        assert db.get_products_by_category("NonExistent") == []

    def test_converts_prices_to_float(self, dynamodb_table):
        _, db = dynamodb_table
        results = db.get_products_by_category("Electronics")

        assert all(isinstance(p["price"], float) for p in results)

    def test_single_category_result(self, dynamodb_table):
        _, db = dynamodb_table
        results = db.get_products_by_category("Electronics")

        assert len(results) == 1
        assert results[0]["title"] == "Wireless Headphones"

    def test_items_without_price_are_returned_unchanged(self, dynamodb_table):
        table, db = dynamodb_table
        table.put_item(Item={"id": "no_price_cat", "title": "Free Item", "category": "Computers", "description": "D"})

        results = db.get_products_by_category("Computers")
        no_price = next(p for p in results if p["id"] == "no_price_cat")

        assert "price" not in no_price

    def test_returns_all_fields_for_category_items(self, dynamodb_table):
        _, db = dynamodb_table
        results = db.get_products_by_category("Electronics")

        item = results[0]
        assert item["id"] == "prod_001"
        assert item["description"] == "Noise-cancelling over-ear headphones"
        assert item["version"] == 1

    def test_category_query_does_not_return_other_categories(self, dynamodb_table):
        _, db = dynamodb_table
        results = db.get_products_by_category("Computers")

        ids = {p["id"] for p in results}
        assert "prod_001" not in ids

    def test_multiple_inserts_reflected_in_category_query(self, dynamodb_table):
        table, db = dynamodb_table
        table.put_item(Item={
            "id": "prod_new_elec",
            "title": "Smart Speaker",
            "price": Decimal("79.99"),
            "category": "Electronics",
            "description": "Voice-controlled speaker",
            "version": 1,
        })

        results = db.get_products_by_category("Electronics")
        assert len(results) == 2
        assert any(p["id"] == "prod_new_elec" for p in results)
