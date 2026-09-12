import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from app.models.regions import RegionStatsResponse
from app.routers.regions import get_region_stats
from app.services.data_provider import DATA_DIR, MockDataProvider


class RegionContractTests(unittest.TestCase):
    def setUp(self):
        self.provider = MockDataProvider()
        self.data = RegionStatsResponse.model_validate(get_region_stats(self.provider))

    def test_district_and_neighborhood_populations_are_separate(self):
        districts = [r for r in self.data.regions if r.scope == "district"]
        neighborhoods = [r for r in self.data.regions if r.scope == "neighborhood"]
        self.assertEqual(len(districts), 14)
        self.assertEqual(len(neighborhoods), 5)
        self.assertEqual(len({r.id for r in self.data.regions}), 19)
        parent = next(r for r in districts if r.id == "jeonju")
        self.assertLess(sum(r.total_units for r in neighborhoods), parent.total_units)
        self.assertLessEqual(sum(r.vacant_units for r in neighborhoods), parent.vacant_units)
        for region in neighborhoods:
            self.assertEqual(region.parent_id, parent.id)
            self.assertIsNotNone(self.provider.get_building(region.building_id))

    def test_rates_and_series_share_the_same_reference(self):
        self.assertEqual(len(self.data.months), 6)
        self.assertEqual(self.data.months[-1], self.data.data_reference_month)
        for region in self.data.regions:
            self.assertEqual(len(region.vacancy_trend_6m), 6)
            self.assertEqual(region.vacancy_rate, region.vacancy_trend_6m[-1])
            self.assertEqual(region.vacant_units, region.monthly_vacant_units[-1])
            for count, rate in zip(region.monthly_vacant_units, region.vacancy_trend_6m):
                self.assertGreaterEqual(count, 0)
                self.assertLessEqual(count, region.total_units)
                self.assertAlmostEqual(rate, count / region.total_units * 100, delta=0.051)

    def test_invalid_counts_or_incomplete_history_cannot_be_displayed(self):
        for total, history in [(0, [0] * 6), (10, [11] * 6), (10, [-1] * 6), (10, [1])]:
            raw = self.provider.get_region_stats()
            raw["regions"][0]["total_units"] = total
            raw["regions"][0]["monthly_vacant_units"] = history
            with self.subTest(total=total, history=history), self.assertRaises(ValueError):
                get_region_stats(SimpleNamespace(get_region_stats=lambda: raw))

    def test_custom_provider_directory_is_respected(self):
        with tempfile.TemporaryDirectory() as directory:
            custom = Path(directory)
            for filename in ["buildings.json", "market_data.json", "permits.json"]:
                (custom / filename).write_bytes((DATA_DIR / filename).read_bytes())
            payload = {"regions": [], "description": "custom source"}
            (custom / "region_stats.json").write_text(json.dumps(payload), encoding="utf-8")
            self.assertEqual(MockDataProvider(custom).get_region_stats(), payload)


if __name__ == "__main__":
    unittest.main()
