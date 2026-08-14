from types import SimpleNamespace

import pytest

from open_coding_agent import config as config_module


def _args(**overrides):
    base = dict(api_key=None, model=None, root=None)
    base.update(overrides)
    return SimpleNamespace(**base)


def test_load_config_root_defaults_to_cwd(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("NVIDIA_API_KEY", "key")
    cfg = config_module.load_config(_args())
    assert cfg.root == str(tmp_path)


def test_load_config_root_override(monkeypatch, tmp_path):
    monkeypatch.setenv("NVIDIA_API_KEY", "key")
    other = tmp_path / "other"
    other.mkdir()
    cfg = config_module.load_config(_args(root=str(other)))
    assert cfg.root == str(other)


def test_load_config_raises_if_root_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("NVIDIA_API_KEY", "key")
    missing = tmp_path / "does-not-exist"
    with pytest.raises(SystemExit):
        config_module.load_config(_args(root=str(missing)))


def test_load_config_raises_without_api_key(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    with pytest.raises(SystemExit):
        config_module.load_config(_args())


def test_load_config_defaults(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("NVIDIA_API_KEY", "key")
    monkeypatch.delenv("OPENCODINGAGENT_MODEL", raising=False)
    cfg = config_module.load_config(_args())
    assert cfg.api_key == "key"
    assert cfg.model == config_module.DEFAULT_MODEL
