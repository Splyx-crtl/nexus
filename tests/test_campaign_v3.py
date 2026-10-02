"""The v3 campaign framework: mission schema, validator, event-driven runner, scenarios, generators, and the solver bot —
plus Act I's actual (small, hand-written + generated) content, proving the whole pipeline end to end."""
import unittest

from nexus.campaign.content import ALL_MISSIONS
from nexus.campaign.content.act1 import ACT1_GENERATED, ACT1_HAND_WRITTEN
from nexus.campaign.generators import generate_grep_mini, generate_hidden_file_mini
from nexus.campaign.mission import Mission, MissionError, Objective
from nexus.campaign.runner import MissionRunner
from nexus.campaign.scenarios import SCENARIOS
from nexus.campaign.solver import solve, solve_all
from nexus.campaign.validator import KNOWN_EVENTS, validate_all, validate_mission


class MissionSchema(unittest.TestCase):
    def test_a_minimal_mission_is_valid(self):
        m = Mission(id="x1", number=1, act=1, size="mini", title="T", scenario="awakening_boot",
                    objectives=[Objective(event="command", match={"name": "ls"}, text="list", hints=["a"])],
                    solution=["ls"])
        self.assertEqual(validate_mission(m), [])

    def test_bad_size_or_act_is_rejected_at_construction(self):
        base = dict(id="x", number=1, title="T", scenario="s", objectives=[Objective(event="command")])
        with self.assertRaises(MissionError):
            Mission(**base, act=1, size="huge")
        with self.assertRaises(MissionError):
            Mission(**base, act=99, size="mini")
        with self.assertRaises(MissionError):
            Mission(id="", number=1, act=1, size="mini", title="T", scenario="s", objectives=[Objective(event="command")])

    def test_needs_at_least_one_objective(self):
        with self.assertRaises(MissionError):
            Mission(id="x", number=1, act=1, size="mini", title="T", scenario="s", objectives=[])

    def test_objective_hint_tiers_are_capped(self):
        with self.assertRaises(MissionError):
            Objective(event="command", hints=["a", "b", "c", "d"])

    def test_required_and_bonus_split(self):
        m = Mission(id="x", number=1, act=1, size="mini", title="T", scenario="s",
                    objectives=[Objective(event="command", text="main"), Objective(event="ls", text="extra", optional=True)],
                    solution=["x"])
        self.assertEqual([o.text for o in m.required_objectives], ["main"])
        self.assertEqual([o.text for o in m.bonus_objectives], ["extra"])

    def test_round_trip_dict(self):
        m = Mission(id="x", number=1, act=1, size="mini", title="T", scenario="awakening_boot",
                    objectives=[Objective(event="command", match={"name": "ls"}, text="list")], solution=["ls"])
        again = Mission.from_dict(m.to_dict())
        self.assertEqual(again.id, "x")
        self.assertEqual(again.objectives[0].match, {"name": "ls"})


class Validator(unittest.TestCase):
    def test_unknown_scenario_and_missing_solution_are_flagged(self):
        m = Mission(id="x", number=1, act=1, size="mini", title="T", scenario="no-such-scenario",
                    objectives=[Objective(event="command", text="t", hints=["h"])])
        problems = validate_mission(m)
        self.assertTrue(any("unknown scenario" in p for p in problems))
        self.assertTrue(any("no reference 'solution'" in p for p in problems))

    def test_unknown_event_and_missing_text_and_hints_are_flagged(self):
        m = Mission(id="x", number=1, act=1, size="mini", title="T", scenario="awakening_boot",
                    objectives=[Objective(event="not_a_real_event")], solution=["ls"])
        problems = validate_mission(m)
        self.assertTrue(any("unknown event" in p for p in problems))
        self.assertTrue(any("no player-facing 'text'" in p for p in problems))
        self.assertTrue(any("no hints" in p for p in problems))

    def test_known_events_cover_what_the_engine_actually_emits(self):
        self.assertIn("command", KNOWN_EVENTS)
        self.assertIn("file_read", KNOWN_EVENTS)
        self.assertIn("grep_match", KNOWN_EVENTS)

    def test_cross_mission_checks(self):
        a = Mission(id="a", number=1, act=1, size="mini", title="A", scenario="awakening_boot",
                    objectives=[Objective(event="command", text="t", hints=["h"])], solution=["ls"])
        b = Mission(id="b", number=1, act=1, size="mini", title="B", scenario="awakening_boot",            # same number as a
                    objectives=[Objective(event="command", text="t", hints=["h"])], solution=["ls"], requires=["nope"])
        problems = validate_all([a, b])
        self.assertIn("a", problems)
        self.assertIn("b", problems)
        self.assertTrue(any("level number" in p for p in problems["a"]))
        self.assertTrue(any("requires unknown mission" in p for p in problems["b"]))

    def test_act1_content_has_no_problems(self):
        self.assertEqual(validate_all(ALL_MISSIONS), {})

    def test_a_command_used_before_its_unlock_level_is_flagged(self):
        """Regression test for the real bug this file's design caught: a mission using 'grep' (unlocks at engine level 8)
        at a mission number below 8 is unsolvable for an actual player, who would not have grep yet."""
        m = Mission(id="x", number=4, act=1, size="mini", title="T", scenario="awakening_logs",
                    objectives=[Objective(event="grep_match", match={"pattern__contains": "x"}, text="t", hints=["h"])],
                    solution=["grep x /var/log/system.log"])
        problems = validate_mission(m)
        self.assertTrue(any("unlocks at level 8" in p and "mission is level 4" in p for p in problems))

    def test_a_command_at_exactly_its_unlock_level_is_fine(self):
        m = Mission(id="x", number=8, act=1, size="mini", title="T", scenario="awakening_logs",
                    objectives=[Objective(event="grep_match", match={"pattern__contains": "x"}, text="t", hints=["h"])],
                    solution=["grep x /var/log/system.log"])
        self.assertEqual(validate_mission(m), [])

    def test_duplicate_objective_id_is_flagged(self):
        m = Mission(id="x", number=1, act=1, size="mini", title="T", scenario="awakening_boot",
                    objectives=[Objective(event="command", id="dup", text="a", hints=["h"]),
                               Objective(event="command", id="dup", text="b", hints=["h"])], solution=["ls"])
        self.assertTrue(any("duplicate objective id" in p for p in validate_mission(m)))


class Runner(unittest.TestCase):
    def test_tracks_objectives_in_real_time(self):
        m = Mission(id="x", number=1, act=1, size="mini", title="T", scenario="awakening_boot",
                    objectives=[Objective(event="command", match={"name": "ls", "status": 0}, text="list")], solution=["ls"])
        runner = MissionRunner.start(m)
        self.assertFalse(runner.is_complete)
        self.assertEqual(runner.missing[0].objective.text, "list")
        runner.shell.run("ls")
        self.assertTrue(runner.is_complete)
        self.assertEqual(runner.missing, [])

    def test_on_progress_fires_exactly_when_an_objective_completes(self):
        m = Mission(id="x", number=1, act=1, size="mini", title="T", scenario="awakening_boot",
                    objectives=[Objective(event="command", match={"name": "ls"}, text="list")], solution=["ls"])
        runner = MissionRunner.start(m)
        seen = []
        runner.on_progress = lambda s: seen.append(s.objective.text)
        runner.shell.run("whoami")
        self.assertEqual(seen, [])
        runner.shell.run("ls")
        self.assertEqual(seen, ["list"])
        runner.shell.run("ls")                                        # already done: no second notification
        self.assertEqual(seen, ["list"])

    def test_optional_objectives_do_not_block_completion(self):
        m = Mission(id="x", number=1, act=1, size="mini", title="T", scenario="awakening_boot",
                    objectives=[Objective(event="command", match={"name": "ls"}, text="main"),
                               Objective(event="command", match={"name": "whoami"}, text="bonus", optional=True)],
                    solution=["ls"])
        runner = MissionRunner.start(m)
        runner.shell.run("ls")
        self.assertTrue(runner.is_complete)
        self.assertEqual([p["done"] for p in runner.progress()], [True, False])

    def test_count_requires_several_matches(self):
        m = Mission(id="x", number=1, act=1, size="mini", title="T", scenario="awakening_boot",
                    objectives=[Objective(event="command", match={"name": "ls"}, text="list twice", count=2)], solution=["ls", "ls"])
        runner = MissionRunner.start(m)
        runner.shell.run("ls")
        self.assertFalse(runner.is_complete)
        runner.shell.run("ls")
        self.assertTrue(runner.is_complete)

    def test_glob_and_contains_matchers(self):
        m = Mission(id="x", number=1, act=1, size="mini", title="T", scenario="awakening_deaddrop",
                    objectives=[Objective(event="file_read", match={"path__glob": "*dropbox*"}, text="glob"),
                               Objective(event="command", match={"name": "ls", "args__contains": "-a"}, text="contains")],
                    solution=["ls -a", "cat .dropbox/readme"])
        runner = MissionRunner.start(m)
        runner.shell.run("ls -a")
        runner.shell.run("cat .dropbox/readme")
        self.assertTrue(runner.is_complete)

    def test_chains_to_an_existing_listener_and_detach_restores_it(self):
        from nexus.campaign.scenarios import SCENARIOS
        from nexus.shell.interp import Shell
        m = Mission(id="x", number=1, act=1, size="mini", title="T", scenario="awakening_boot",
                    objectives=[Objective(event="command", match={"name": "ls"}, text="list")], solution=["ls"])
        world, session = SCENARIOS["awakening_boot"]()
        outer_seen = []
        base_listener = lambda e, d: outer_seen.append(e)
        shell = Shell(world, session, listener=base_listener)
        runner = MissionRunner(m, shell)
        shell.run("ls")
        self.assertTrue(runner.is_complete)
        self.assertIn("command", outer_seen)                          # the pre-existing listener still fires too
        runner.detach()
        self.assertIs(shell.listener, base_listener)

    def test_unknown_scenario_raises(self):
        m = Mission(id="x", number=1, act=1, size="mini", title="T", scenario="does-not-exist",
                    objectives=[Objective(event="command")], solution=["ls"])
        with self.assertRaises(KeyError):
            MissionRunner.start(m)

    def test_level_gating_is_honoured(self):
        m = Mission(id="x", number=1, act=3, size="mini", title="T", scenario="awakening_logs",
                    objectives=[Objective(event="grep_match", match={"pattern__contains": "contractor_temp"}, text="t")],
                    solution=["grep contractor_temp /var/log/system.log"])
        runner = MissionRunner.start(m, level=lambda: 1)              # grep unlocks much later than level 1
        runner.shell.run("grep contractor_temp /var/log/system.log")
        self.assertFalse(runner.is_complete)


class Scenarios(unittest.TestCase):
    def test_every_registered_scenario_builds_a_working_session(self):
        for name, build in SCENARIOS.items():
            world, session = build()
            self.assertIn(session.machine.id, world.machines, name)
            self.assertEqual(session.shell, "bash", name)


class Generators(unittest.TestCase):
    def test_grep_mini_is_deterministic_and_solvable(self):
        a = generate_grep_mini("g1", 8, 1, seed=42)
        b = generate_grep_mini("g1b", 8, 1, seed=42)
        self.assertEqual(a.title, b.title)                            # same seed -> same keyword
        self.assertTrue(solve(a).ok)

    def test_different_seeds_can_differ(self):
        titles = {generate_grep_mini(f"g{i}", 8, 1, seed=i).title for i in range(8)}
        self.assertGreater(len(titles), 1)

    def test_hidden_file_mini_is_solvable(self):
        m = generate_hidden_file_mini("h1", 7, 1, seed=7)
        self.assertTrue(solve(m).ok)

    def test_generated_missions_pass_the_validator(self):
        self.assertEqual(validate_all(ACT1_GENERATED), {})


class SolverBot(unittest.TestCase):
    def test_every_act1_mission_is_solvable(self):
        results = solve_all(ALL_MISSIONS)
        failed = {mid: (r.missing, r.error) for mid, r in results.items() if not r.ok}
        self.assertEqual(failed, {})

    def test_a_broken_solution_is_caught(self):
        m = Mission(id="x", number=1, act=1, size="mini", title="T", scenario="awakening_boot",
                    objectives=[Objective(event="command", match={"name": "ls"}, text="list")], solution=["whoami"])
        result = solve(m)
        self.assertFalse(result.ok)
        self.assertEqual(result.missing, ["list"])

    def test_transcript_is_captured(self):
        m = ACT1_HAND_WRITTEN[0]
        result = solve(m)
        self.assertTrue(result.ok)
        self.assertEqual([line for line, _ in result.transcript], m.solution)

    def test_solve_defaults_to_the_missions_own_level_not_unlimited(self):
        """The same regression as the validator test above, but proving the solver itself (not just the static check)
        would have caught it: solving at the mission's own number, a too-early command simply never unlocks."""
        m = Mission(id="x", number=4, act=1, size="mini", title="T", scenario="awakening_logs",
                    objectives=[Objective(event="grep_match", match={"pattern__contains": "contractor"}, text="t")],
                    solution=["grep contractor /var/log/system.log"])
        self.assertFalse(solve(m).ok)
        self.assertTrue(solve(m, level=lambda: 10**6).ok)              # an unrestricted level masks the same bug

    def test_builtins_also_emit_a_command_event(self):
        """echo/cd/etc. are bash builtins, dispatched without going through run_command() — they need their own event too,
        or a mission like act1_m09 (reply by echoing into a file) could never complete."""
        m = Mission(id="x", number=9, act=1, size="mini", title="T", scenario="awakening_boot",
                    objectives=[Objective(event="command", match={"name": "echo", "status": 0}, text="t")], solution=["echo hi"])
        self.assertTrue(solve(m).ok)


if __name__ == "__main__":
    unittest.main()
