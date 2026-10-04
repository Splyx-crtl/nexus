"""F2 Endless Ops (nexus/campaign/endless.py) — every template must be solvable across many random seeds, not just
one hand-checked instance, since real play generates an unbounded number of them."""
import unittest

from nexus.campaign.endless import TEMPLATES, generate_endless_chain, generate_endless_mission
from nexus.campaign.solver import solve
from nexus.campaign.validator import validate_mission

SEEDS = range(12)


class EndlessTemplates(unittest.TestCase):
    def test_every_template_is_solvable_across_many_seeds(self):
        for key in TEMPLATES:
            for seed in SEEDS:
                with self.subTest(template=key, seed=seed):
                    m = generate_endless_mission(f"t_{key}_{seed}", 500 + seed, 8, seed * 13 + 3, template_key=key)
                    self.assertEqual(validate_mission(m), [])
                    r = solve(m)
                    self.assertTrue(r.ok, f"{key} seed={seed} failed: {r.missing} {r.error}")

    def test_same_seed_and_template_is_deterministic(self):
        a = generate_endless_mission("det_a", 1, 8, seed=777, template_key="incident_response")
        b = generate_endless_mission("det_b", 1, 8, seed=777, template_key="incident_response")
        self.assertEqual(a.title, b.title)
        self.assertEqual(a.solution, b.solution)
        self.assertEqual([o.match for o in a.objectives], [o.match for o in b.objectives])

    def test_different_seeds_usually_differ(self):
        titles = {generate_endless_mission(f"v_{i}", 1, 8, seed=i, template_key="recon_sweep").title for i in range(10)}
        self.assertGreater(len(titles), 1)

    def test_no_template_key_still_produces_a_solvable_mission(self):
        # level 166: Act VIII's own level range, where endless ops are actually used — every command endless
        # templates use (including sshpass/ssh, unlocked at 13) is long since unlocked by then.
        for seed in SEEDS:
            m = generate_endless_mission(f"any_{seed}", 166, 8, seed=seed)
            self.assertEqual(validate_mission(m), [])
            self.assertTrue(solve(m).ok)


class EndlessChain(unittest.TestCase):
    def test_chain_links_requires_in_order(self):
        chain = generate_endless_chain("chain_a", 600, 8, seed=5, length=4)
        for i, m in enumerate(chain):
            expected = [] if i == 0 else [chain[i - 1].id]
            self.assertEqual(m.requires, expected)

    def test_chain_reward_ascends_for_a_fixed_template(self):
        # mixed templates have different base rewards, so only a same-template chain is guaranteed strictly
        # ascending — the difficulty multiplier is what's actually under test here.
        chain = generate_endless_chain("chain_b", 600, 8, seed=9, length=5, template_keys=["incident_response"])
        rewards = [m.reward_xp for m in chain]
        self.assertEqual(rewards, sorted(rewards))
        self.assertLess(rewards[0], rewards[-1])

    def test_chain_is_fully_solvable(self):
        chain = generate_endless_chain("chain_c", 600, 8, seed=21, length=6)
        for m in chain:
            self.assertEqual(validate_mission(m), [])
            r = solve(m)
            self.assertTrue(r.ok, f"{m.id} failed: {r.missing} {r.error}")

    def test_chain_respects_requires_first(self):
        chain = generate_endless_chain("chain_d", 600, 8, seed=3, length=2, requires_first=["act8_m170"])
        self.assertEqual(chain[0].requires, ["act8_m170"])


if __name__ == "__main__":
    unittest.main()
