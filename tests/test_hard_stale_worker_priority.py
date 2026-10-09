"""Synthetic scheduling only: no news, source, model or publication writes."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import general_news_verification_robot as robot
import parallel_general_news_fallback as parallel

NOW = datetime(2026, 10, 9, 16, 45, tzinfo=timezone.utc)


def state(ages):
    return {"desks": {robot.PUBLIC_DESK[desk]: [{"publishedAt": (NOW - timedelta(hours=age)).isoformat()}] for desk, age in ages.items()}}


class HardStalePriorityTests(unittest.TestCase):
    def test_real_hard_stale_three_desks_get_separate_workers_before_soft_stale(self):
        data = state({"world": 5, "asia": 50, "japan": 35, "finance": 37, "football": 9})
        with patch.object(robot, "soft_stale_desks", return_value=["world", "asia", "japan", "finance", "football"]):
            request = robot.prepare_request({"desks": {}}, data, {}, NOW)
        self.assertEqual(request["staleDesks"], ["asia", "japan", "finance", "world", "football"])
        self.assertEqual(parallel.partition(request, 2)["staleDesks"], ["finance"])
        self.assertEqual(set(request["staleDesks"]), {"world", "asia", "japan", "finance", "football"})

    def test_actual_shared_hard_boundaries_are_unchanged(self):
        for desk, boundary in (("world", 24), ("finance", 24), ("football", 48)):
            self.assertEqual(robot.public_freshness_priority(state({desk: boundary}), desk, NOW), 1)
            self.assertEqual(robot.public_freshness_priority(state({desk: boundary + .001}), desk, NOW), 0)

    def test_missing_unparseable_and_future_story_clocks_do_not_gain_freshness(self):
        for rows in ([], [{"publishedAt": "unknown"}], [{"publishedAt": (NOW + timedelta(hours=1)).isoformat()}]):
            self.assertEqual(robot.public_freshness_priority({"desks": {"world": rows}}, "world", NOW), 0)

    def test_complete_candidate_set_gates_and_four_per_desk_cap_are_kept(self):
        rows = [{"id": f"synthetic-{i}", "desk": "finance", "title": f"SYNTHETIC fixture financial event {i}", "source": "Reuters", "url": f"https://example.invalid/{i}", "publishedAt": NOW.isoformat()} for i in range(6)]
        with patch.object(robot, "soft_stale_desks", return_value=["finance"]):
            result = robot.prepare_request({"desks": {"finance": rows}}, state({"finance": 37}), {}, NOW)
        self.assertEqual(result["candidateCount"], 4)
        self.assertEqual(parallel.PROBES_PER_WORKER, 4)
        self.assertEqual(parallel.CALLS_PER_WORKER, 1)
        self.assertEqual(parallel.WORKERS, 3)

    def test_sorting_does_not_mutate_desk_story_copy_or_clock(self):
        import copy
        data = state({"world": 5, "asia": 50}); before = copy.deepcopy(data)
        with patch.object(robot, "soft_stale_desks", return_value=["world", "asia"]):
            robot.prepare_request({"desks": {}}, data, {}, NOW)
        self.assertEqual(data, before)


if __name__ == "__main__":
    unittest.main()
