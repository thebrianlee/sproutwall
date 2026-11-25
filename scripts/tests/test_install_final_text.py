"""What install.sh and the guide say about the final check after an install
over SSH: the two unknowns a root-only SSH settings file causes
with SSH off, the keyboard-free case, and the owner who keeps SSH on."""

import unittest

from . import test_install_sh as base


class FinalCheckAfterSshTests(base.InstallShTestCase):
    def setUp(self):
        super().setUp()
        base.OverSshTests.ssh_config(self)

    def finish_text(self, run):
        return run.out[run.out.index("== Sproutwall is installed ==") : run.out.index("== SSH (last question) ==")]

    def test_finish_accepts_both_unknowns_only_with_ssh_confirmed_off(self):
        run = self.run_install(base.SSH_ANSWERS, **base.SSH_ENV)
        self.assertEqual(run.code, 0, run.out + run.err)
        finish = self.finish_text(run)
        self.assertIn("ssh_policy unknown (review_ssh) and temporary_access", finish)
        self.assertIn("unknown (retry_local)", finish)
        self.assertIn("Only those two unknowns are acceptable", finish)
        self.assertIn("inactive for both:  systemctl is-active ssh.service ssh.socket", finish)
        self.assertIn("Any other unknown, and any other fail, is still a stop.", finish)

    def test_finish_covers_no_keyboard_and_ssh_kept_on(self):
        run = self.run_install(base.SSH_ANSWERS, **base.SSH_ENV)
        self.assertEqual(run.code, 0, run.out + run.err)
        finish = self.finish_text(run)
        self.assertIn("No keyboard for the device?", finish)
        self.assertIn("stand in for the final check", finish)
        self.assertIn("SSH kept on (your choice): you may run the final check over SSH", finish)
        self.assertNotIn("run it in the device's own Terminal.\n", finish)

    def test_ssh_off_points_keyboard_free_users_to_the_stand_in(self):
        run = self.run_install(base.SSH_ANSWERS, **base.SSH_ENV)
        self.assertEqual(run.code, 0, run.out + run.err)
        tail = run.out[run.out.index("Turn SSH off now?") :]
        self.assertIn("SSH is off: systemctl is-active ssh.service ssh.socket prints inactive for both.", tail)
        self.assertIn("Without one,", tail)

    def test_keeping_ssh_on_names_what_the_final_check_reports(self):
        run = self.run_install(base.SSH_ANSWERS[:-1] + ["n"], **base.SSH_ENV)
        self.assertEqual(run.code, 0, run.out + run.err)
        tail = run.out[run.out.index("Turn SSH off now?") :]
        self.assertIn("SSH stays on.", tail)
        self.assertIn("reports ssh_policy and temporary_access", tail)
        self.assertNotIn("until it is off", tail)


class GuideFinalCheckTests(unittest.TestCase):
    def test_step_8_does_not_tell_an_owner_who_keeps_ssh_to_turn_it_off(self):
        guide = base.read(base.GUIDE)
        step8 = guide[guide.index("## Step 8:") : guide.index("## If something goes wrong")]
        self.assertNotIn("If you answered no, or went step by step, turn it off now", step8)
        self.assertIn("If you answered no because you want to keep SSH on, leave it on", step8)
        self.assertIn("**SSH kept on (your choice):**", step8)
        self.assertIn("**No keyboard for the device:**", step8)
        self.assertIn("`temporary_access` unknown (`retry_local`)", step8)

    def test_step_by_step_over_ssh_needs_key_only_ssh(self):
        guide = base.read(base.GUIDE)
        self.assertIn("Over SSH (tier B), going step by step needs key-only SSH in this preview", guide)
        step1 = guide[guide.index("## Step 1:") : guide.index("## Step 2:")]
        self.assertIn("needed to go step by step over SSH", step1)
