"""Tests for tools/automerge.py — the GitHub auto-merge arbitration rules.

These rules decide, from PR metadata and a file list alone, whether a small PR may be
auto-merged. Every branch of ``arvioi``/``polku_ok``/``botin_*`` is exercised here,
since the module ships with no coverage of its own.
"""
import unittest
import unittest.mock

from tools import automerge as am


def pr(**overrides):
    """A default, mergeable same-repo PR; override any field."""
    base = {
        "draft": False,
        "head_repo": "org/repo",
        "base_repo": "org/repo",
        "labels": [],
        "author": "someone",
        "head_ref": "fix-1",
        "base_ref": "main",
    }
    base.update(overrides)
    return base


def files(*filenames):
    return [{"filename": f, "status": "modified", "changes": 1,
             "previous_filename": None} for f in filenames]


class PolkuOkTests(unittest.TestCase):
    def test_markdown_ok(self):
        self.assertTrue(am.polku_ok("README.md")[0])

    def test_docs_markdown_ok(self):
        self.assertTrue(am.polku_ok("docs/guide/foo.md")[0])

    def test_test_py_ok(self):
        self.assertTrue(am.polku_ok("test/x/test_foo.py")[0])

    def test_non_doc_extension_rejected(self):
        self.assertFalse(am.polku_ok("src/app.py")[0])

    def test_empty_path_rejected(self):
        ok, syy = am.polku_ok("")
        self.assertFalse(ok)
        self.assertIn("tyhja", syy)

    def test_protected_paths_rejected(self):
        for p in ("tools/x.py", ".github/workflows/ci.yml", "isanta/d.py",
                  "foo/systemd/unit", "agentti/config.py", "agentti/rajat.py",
                  ".env", "dist/x.md", "yojono/a.md", "action.yaml", "action.yml",
                  "requirements.txt", "pyproject.toml", "package.json", "Dockerfile",
                  "a/../b.md"):
            self.assertFalse(am.polku_ok(p)[0], p)

    def test_secret_pattern_rejected(self):
        self.assertFalse(am.polku_ok("secret.md")[0])
        self.assertFalse(am.polku_ok("my_APItoken.md")[0])


class BotinForkkiSyytTests(unittest.TestCase):
    def test_ok_fork_from_bot(self):
        p = pr(head_repo="agenttifirma-bot/repo", base_repo="org/repo",
               author="agenttifirma-bot", head_ref="yo/readme-abc123", base_ref="main")
        self.assertEqual(am.botin_forkki_syyt(p), [])

    def test_master_base_accepted(self):
        p = pr(head_repo="agenttifirma-bot/repo", base_repo="org/repo",
               author="agenttifirma-bot", head_ref="yo/testit-x", base_ref="master")
        self.assertEqual(am.botin_forkki_syyt(p), [])

    def test_non_bot_author_rejected(self):
        p = pr(head_repo="agenttifirma-bot/repo", author="human", head_ref="yo/readme-x")
        self.assertIn("PR ei ole saman repon haarasta", am.botin_forkki_syyt(p))

    def test_author_case_insensitive(self):
        p = pr(head_repo="agenttifirma-bot/repo", author="AgenttiFirma-BOT",
               head_ref="yo/readme-x")
        self.assertEqual(am.botin_forkki_syyt(p), [])

    def test_wrong_repo_named_fork_rejected(self):
        # head_repo must be BOTTI/<base repo name>
        p = pr(head_repo="agenttifirma-bot/other", base_repo="org/repo",
               author="agenttifirma-bot", head_ref="yo/readme-x")
        self.assertIn("forkki ei ole botin oma fork samasta reposta", am.botin_forkki_syyt(p))

    def test_empty_base_repo_name(self):
        p = pr(head_repo="agenttifirma-bot/x", base_repo="norepo",
               author="agenttifirma-bot", head_ref="yo/readme-x")
        # "norepo" has no "/", so base repo name is empty -> rejected
        self.assertIn("forkki ei ole botin oma fork samasta reposta", am.botin_forkki_syyt(p))

    def test_non_main_base_rejected(self):
        p = pr(head_repo="agenttifirma-bot/repo", base_repo="org/repo",
               author="agenttifirma-bot", head_ref="yo/readme-x", base_ref="dev")
        self.assertIn("base ei ole main eika master", am.botin_forkki_syyt(p))

    def test_bad_branch_name_rejected(self):
        p = pr(head_repo="agenttifirma-bot/repo", base_repo="org/repo",
               author="agenttifirma-bot", head_ref="feature-x")
        self.assertIn("botin haaran nimi ei ole yo/(readme|testit|ominaisuus)-*",
                      am.botin_forkki_syyt(p))

    def test_branch_must_be_readme_testit_or_ominaisuus(self):
        p = pr(head_repo="agenttifirma-bot/repo", base_repo="org/repo",
               author="agenttifirma-bot", head_ref="yo/other-x")
        self.assertIn("botin haaran nimi ei ole yo/(readme|testit|ominaisuus)-*",
                      am.botin_forkki_syyt(p))


class BotinKoodiOkTests(unittest.TestCase):
    def test_py_and_md_allowed(self):
        self.assertTrue(am.botin_koodi_ok("src/foo.py")[0])
        self.assertTrue(am.botin_koodi_ok("README.md")[0])

    def test_bad_suffix_rejected(self):
        self.assertFalse(am.botin_koodi_ok("src/foo.txt")[0])

    def test_unsafe_path_chars_rejected(self):
        self.assertFalse(am.botin_koodi_ok("src/foo bar.py")[0])

    def test_protected_paths_rejected(self):
        for p in (".github/w.yml", "tools/x.py", "requirements.txt", "pyproject.toml", "yojono/a.py"):
            self.assertFalse(am.botin_koodi_ok(p)[0], p)


class ArvioiTests(unittest.TestCase):
    def test_simple_doc_pr_accepted(self):
        sallittu, syyt = am.arvioi(pr(), files("README.md"))
        self.assertTrue(sallittu, syyt)
        self.assertEqual(syyt, [])

    def test_draft_rejected(self):
        self.assertFalse(am.arvioi(pr(draft=True), files("README.md"))[0])

    def test_no_files_rejected(self):
        self.assertFalse(am.arvioi(pr(), [])[0])

    def test_too_many_files_rejected(self):
        self.assertFalse(am.arvioi(pr(), files(*["f%d.md" % i for i in range(21)]))[0])

    def test_too_many_lines_rejected(self):
        fs = {"filename": "README.md", "status": "modified", "changes": 201, "previous_filename": None}
        self.assertFalse(am.arvioi(pr(), [fs])[0])

    def test_exactly_at_line_limit_ok(self):
        fs = {"filename": "README.md", "status": "modified", "changes": 200, "previous_filename": None}
        self.assertTrue(am.arvioi(pr(), [fs])[0])

    def test_removed_file_rejected(self):
        self.assertFalse(am.arvioi(pr(), [{"filename": "x.md", "status": "removed", "changes": 1,
                                            "previous_filename": None}])[0])

    def test_renamed_file_rejected(self):
        self.assertFalse(am.arvioi(pr(), [{"filename": "b.md", "status": "renamed", "changes": 1,
                                            "previous_filename": "a.md"}])[0])

    def test_opt_out_label_rejected(self):
        self.assertFalse(am.arvioi(pr(labels=["ei-automerge"]), files("README.md"))[0])

    def test_previous_filename_checked_too(self):
        # a moved/renamed file whose previous path is protected must be rejected
        ok = am.arvioi(pr(), [{"filename": "README.md", "status": "modified", "changes": 1,
                               "previous_filename": ".env"}])
        self.assertFalse(ok[0])


class SamanRepoArvioiTests(unittest.TestCase):
    """Saman repon PR (ei forkki): vain dokumentit ja testit, ei sovelluskoodia. Botin forkin laajempi koodisaanto ei saa vuotaa tahan."""

    def test_samassa_repossa_sovelluskoodi_hylataan(self):
        sallittu, syyt = am.arvioi(pr(), files("src/app.py"))
        self.assertFalse(sallittu)
        self.assertTrue(syyt)

    def test_samassa_repossa_sovelluskoodi_hylataan_myos_ominaisuushaaralla(self):
        # haaran nimi yo/ominaisuus-* ei avaa koodia saman repon PR:lle, vain botin forkille
        self.assertFalse(am.arvioi(pr(head_ref="yo/ominaisuus-x"), files("src/app.py"))[0])

    def test_samassa_repossa_testi_ja_dokumentti_sallitaan(self):
        sallittu, syyt = am.arvioi(pr(), files("test/test_uusi.py", "README.md"))
        self.assertTrue(sallittu, syyt)

    def test_samassa_repossa_yksi_koodi_tiedosto_riittaa_hylkaykseen(self):
        self.assertFalse(am.arvioi(pr(), files("README.md", "src/app.py"))[0])


class BotinForkArvioiTests(unittest.TestCase):
    def bot_pr(self, head_ref="yo/readme-abc", **kw):
        return pr(head_repo="agenttifirma-bot/repo", base_repo="org/repo",
                  author="agenttifirma-bot", head_ref=head_ref, base_ref="main", **kw)

    def test_bot_readme_only_md(self):
        sallittu, syyt = am.arvioi(self.bot_pr(), files("README.md"))
        self.assertTrue(sallittu, syyt)

    def test_bot_readme_rejects_py(self):
        self.assertFalse(am.arvioi(self.bot_pr(), files("foo.py"))[0])

    def test_bot_ominaisuus_allows_code(self):
        sallittu, syyt = am.arvioi(self.bot_pr("yo/ominaisuus-start"),
                                   [{"filename": "src/app.py", "status": "added", "changes": 5,
                                     "previous_filename": None}])
        self.assertTrue(sallittu, syyt)

    def test_bot_ominaisuus_code_line_limit_400(self):
        fs = {"filename": "src/app.py", "status": "modified", "changes": 401, "previous_filename": None}
        self.assertFalse(am.arvioi(self.bot_pr("yo/ominaisuus-x"), [fs])[0])
        fs["changes"] = 400
        self.assertTrue(am.arvioi(self.bot_pr("yo/testit-x"), [fs])[0])

    def test_bot_ominaisuus_dependency_file_rejected(self):
        fs = {"filename": "requirements.txt", "status": "modified", "changes": 1, "previous_filename": None}
        self.assertFalse(am.arvioi(self.bot_pr("yo/ominaisuus-x"), [fs])[0])

    def test_bot_non_fork_author_on_fork_rejected(self):
        p = pr(head_repo="agenttifirma-bot/repo", author="human", head_ref="yo/readme-x")
        self.assertFalse(am.arvioi(p, files("README.md"))[0])

    def test_bot_changes_sum_uses_default_limit_for_readme(self):
        # readme branch keeps MAX_RIVEJA (200), not the 400 code limit
        fs = {"filename": "README.md", "status": "modified", "changes": 250, "previous_filename": None}
        self.assertFalse(am.arvioi(self.bot_pr("yo/readme-x"), [fs])[0])


class MainTests(unittest.TestCase):
    def test_invalid_repo_or_number_returns_2(self):
        import os
        with unittest.mock.patch.dict(os.environ, {"GITHUB_REPOSITORY": "bad repo", "PR_NUMBER": "12"},
                                      clear=True):
            self.assertEqual(am.main(), 2)
        with unittest.mock.patch.dict(os.environ, {"GITHUB_REPOSITORY": "org/repo", "PR_NUMBER": "abc"},
                                      clear=True):
            self.assertEqual(am.main(), 2)

    def test_gh_failure_returns_1(self):
        import os
        with unittest.mock.patch.dict(os.environ, {"GITHUB_REPOSITORY": "org/repo", "PR_NUMBER": "1"},
                                      clear=True), \
                unittest.mock.patch.object(am, "hae_pr", side_effect=RuntimeError("boom")):
            self.assertEqual(am.main(), 1)


if __name__ == "__main__":
    unittest.main()