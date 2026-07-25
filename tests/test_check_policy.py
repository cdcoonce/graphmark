"""The [check] policy block: CheckPolicy parsing and its deliberate strictness.

A CI gate whose misconfiguration reports green forever is the worst failure a gate can have, so
unknown keys inside [check] are an error — even though load_config stays deliberately lenient
about unknown keys everywhere else.
"""

from __future__ import annotations

import pytest

from graphmark.config import CheckPolicy, VaultConfig, load_config


def _write(tmp_path, body: str):
    toml = tmp_path / "vault.toml"
    toml.write_text('root = "vault"\n' + body)
    return toml


class TestCheckPolicyDefaults:
    def test_absent_block_yields_an_all_none_policy(self, tmp_path):
        cfg = load_config(_write(tmp_path, ""))
        assert cfg.check == CheckPolicy()
        assert cfg.check.max_orphans is None
        assert cfg.check.max_unresolved_links is None
        assert cfg.check.max_siloed is None

    def test_directly_constructed_config_has_a_policy(self, tmp_path):
        assert VaultConfig(root=tmp_path).check == CheckPolicy()

    def test_policy_is_frozen(self):
        policy = CheckPolicy(max_orphans=5)
        with pytest.raises(Exception):  # noqa: B017 - dataclasses raises FrozenInstanceError
            policy.max_orphans = 6

    def test_is_configured_reports_whether_anything_is_enforced(self):
        assert CheckPolicy().is_configured() is False
        assert CheckPolicy(max_orphans=0).is_configured() is True


class TestCheckPolicyParsing:
    def test_full_block_parses(self, tmp_path):
        cfg = load_config(
            _write(
                tmp_path,
                "[check]\nmax_orphans = 10\nmax_unresolved_links = 0\nmax_siloed = 3\n",
            )
        )
        assert cfg.check == CheckPolicy(max_orphans=10, max_unresolved_links=0, max_siloed=3)

    def test_partial_block_leaves_the_rest_unenforced(self, tmp_path):
        cfg = load_config(_write(tmp_path, "[check]\nmax_orphans = 10\n"))
        assert cfg.check.max_orphans == 10
        assert cfg.check.max_unresolved_links is None
        assert cfg.check.max_siloed is None

    def test_zero_is_a_real_threshold_not_absence(self, tmp_path):
        # max_unresolved_links = 0 means "no broken links allowed" — it must not read as unset.
        cfg = load_config(_write(tmp_path, "[check]\nmax_unresolved_links = 0\n"))
        assert cfg.check.max_unresolved_links == 0
        assert cfg.check.is_configured() is True

    def test_empty_block_is_still_unconfigured(self, tmp_path):
        cfg = load_config(_write(tmp_path, "[check]\n"))
        assert cfg.check.is_configured() is False


class TestCheckPolicyStrictness:
    def test_unknown_key_inside_check_raises(self, tmp_path):
        toml = _write(tmp_path, "[check]\nmax_orphan = 10\n")  # note the typo
        with pytest.raises(ValueError) as exc:
            load_config(toml)
        msg = str(exc.value)
        assert "max_orphan" in msg
        assert str(toml) in msg

    def test_the_error_lists_the_valid_keys(self, tmp_path):
        with pytest.raises(ValueError) as exc:
            load_config(_write(tmp_path, "[check]\nbogus = 1\n"))
        assert "max_orphans" in str(exc.value)

    def test_unknown_keys_outside_check_are_still_ignored(self, tmp_path):
        # The strictness is scoped to [check]; the documented lenient behavior elsewhere stands.
        cfg = load_config(_write(tmp_path, "totally_unknown = 5\n"))
        assert cfg.check == CheckPolicy()

    @pytest.mark.parametrize("value", ["-1", '"ten"', "1.5", "true"])
    def test_invalid_threshold_values_raise(self, tmp_path, value):
        with pytest.raises(ValueError):
            load_config(_write(tmp_path, f"[check]\nmax_orphans = {value}\n"))

    def test_non_table_check_value_raises(self, tmp_path):
        with pytest.raises(ValueError):
            load_config(_write(tmp_path, 'check = "yes"\n'))
