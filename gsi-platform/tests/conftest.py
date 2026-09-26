"""Bridge legacy script-style report tests to pytest without suppressing checks."""
import logging
import pytest


@pytest.fixture
def res(request):
    module=request.module
    factories={'test_contracts_report':'test_report_keys_exist',
               'test_criticality':'test_pipeline',
               'test_rules_and_moghavemat':'test_moghavemat',
               'test_validation':'test_pipeline'}
    name=module.__name__.split('.')[-1]
    if name not in factories:raise ValueError(f'No legacy fixture factory for {name}')
    previous_disable = logging.root.manager.disable
    try:
        return getattr(module,factories[name])()
    finally:
        # Legacy factory functions may call logging.disable(...); module-scoped
        # fixture setup must not leak that process-global state to later modules.
        logging.disable(previous_disable)


@pytest.fixture
def df(res):
    return res.df


@pytest.fixture(autouse=True)
def assert_legacy_checks(request):
    yield
    failures=getattr(request.module,'FAIL',[])
    assert not failures, 'Legacy checks failed: '+repr(failures)


@pytest.fixture(autouse=True)
def isolated_operational_store(tmp_path, monkeypatch):
    monkeypatch.setenv('GSI_DWH_PATH', str(tmp_path / 'isolated_operational.sqlite'))


@pytest.fixture(autouse=True)
def restore_global_logging_state():
    """Prevent legacy tests from leaking logging.disable(...) into later tests."""
    previous_disable = logging.root.manager.disable
    yield
    logging.disable(previous_disable)

@pytest.fixture(autouse=True)
def isolate_legacy_synthetic_sources(request, monkeypatch):
    """Bind legacy script-style synthetic tests to their own source snapshot.

    Four old modules build synthetic workbooks and set GSI_* at import time.
    In a multi-module pytest run, gsi.config.settings/sources may already be
    imported, so changing os.environ alone is too late.  Rebind the shared
    Settings object and mutate the source registry in place for those modules,
    then restore both after the test.  Production code is not changed.
    """
    dirs = getattr(request.module, "DIRS", None) or getattr(request.module, "_D", None)
    if not isinstance(dirs, dict) or not {"foreign", "bls", "clearance", "hr", "output", "logs"}.issubset(dirs):
        yield
        return

    env_map = {
        "GSI_FOREIGN": dirs["foreign"],
        "GSI_BLS": dirs["bls"],
        "GSI_CLEARANCE": dirs["clearance"],
        "GSI_HR": dirs["hr"],
        "GSI_ESMAEILI": dirs.get("esmaeili", ""),
        "GSI_GS_COMBINE": dirs.get("gs_combine", ""),
        "GSI_MOHAMADI": dirs.get("mohamadi", ""),
        "GSI_OUTPUT": dirs["output"],
        "GSI_LOGS": dirs["logs"],
        "GSI_TODAY": "2026-08-31",
    }
    for k, v in env_map.items():
        monkeypatch.setenv(k, str(v))
    monkeypatch.delenv("GSI_SOURCES_YAML", raising=False)

    from gsi.config import settings as settings_mod
    from gsi.config import sources as sources_mod

    settings_obj = settings_mod.SETTINGS
    setting_fields = {
        "FOREIGN_DIR": dirs["foreign"],
        "BLS_TOTAL_DIR": dirs["bls"],
        "CLEARANCE_DIR": dirs["clearance"],
        "HR_DIR": dirs["hr"],
        "ESMAEILI_DIR": dirs.get("esmaeili", ""),
        "GS_COMBINE_OUT_DIR": dirs.get("gs_combine", ""),
        "MOHAMADI_DIR": dirs.get("mohamadi", ""),
        "OUTPUT_DIR": dirs["output"],
        "LOG_DIR": dirs["logs"],
        "TODAY_OVERRIDE": "2026-08-31",
    }
    saved_settings = {k: getattr(settings_obj, k) for k in setting_fields}
    saved_placeholders = dict(sources_mod._PLACEHOLDERS)
    saved_sources = dict(sources_mod.SOURCES)
    saved_aliases = dict(sources_mod.SOURCE_ALIASES)
    saved_merge = list(sources_mod.MERGE_ORDER)
    saved_weights = dict(sources_mod.SOURCE_WEIGHTS)

    try:
        for k, v in setting_fields.items():
            object.__setattr__(settings_obj, k, v)
        sources_mod._PLACEHOLDERS.update({
            "FOREIGN_DIR": dirs["foreign"],
            "BLS_TOTAL_DIR": dirs["bls"],
            "CLEARANCE_DIR": dirs["clearance"],
            "HR_DIR": dirs["hr"],
            "ESMAEILI_DIR": dirs.get("esmaeili", ""),
            "GS_FULL_CHAIN_DIR": getattr(settings_obj, "GS_FULL_CHAIN_DIR"),
            "GS_COMBINE_OUT_DIR": dirs.get("gs_combine", ""),
            "MOHAMADI_DIR": dirs.get("mohamadi", ""),
        })
        new_sources, new_aliases, new_merge = sources_mod._load()
        sources_mod.SOURCES.clear(); sources_mod.SOURCES.update(new_sources)
        sources_mod.SOURCE_ALIASES.clear(); sources_mod.SOURCE_ALIASES.update(new_aliases)
        sources_mod.MERGE_ORDER[:] = new_merge
        sources_mod.SOURCE_WEIGHTS.clear(); sources_mod.SOURCE_WEIGHTS.update(
            {k: v.weight for k, v in new_sources.items()}
        )
        yield
    finally:
        for k, v in saved_settings.items():
            object.__setattr__(settings_obj, k, v)
        sources_mod._PLACEHOLDERS.clear(); sources_mod._PLACEHOLDERS.update(saved_placeholders)
        sources_mod.SOURCES.clear(); sources_mod.SOURCES.update(saved_sources)
        sources_mod.SOURCE_ALIASES.clear(); sources_mod.SOURCE_ALIASES.update(saved_aliases)
        sources_mod.MERGE_ORDER[:] = saved_merge
        sources_mod.SOURCE_WEIGHTS.clear(); sources_mod.SOURCE_WEIGHTS.update(saved_weights)

@pytest.fixture(autouse=True)
def isolate_health_ledger(monkeypatch):
    """A prior suite's source schema failures must not become this run's facts."""
    from gsi import health
    monkeypatch.setattr(health, 'HEALTH', health.SystemHealth())
