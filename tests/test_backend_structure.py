import ast
from pathlib import Path

from configure import PROJECT_CONFIG


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_backend_main_uses_generic_application_lifespan():
    source = (PROJECT_ROOT / "backend_main.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert not any(module.startswith("applications.") for module in imported_modules)
    assert "application_lifespan" in source


def test_ide_database_url_is_assembled_by_project_config():
    assert PROJECT_CONFIG.IDE_DATABASE_URL.startswith("mysql+aiomysql://")
    assert PROJECT_CONFIG.IDE_DATABASE_NAME in PROJECT_CONFIG.IDE_DATABASE_URL


def test_removed_module_config_adapters_do_not_exist():
    assert not (PROJECT_ROOT / "applications/ticket_review/config.py").exists()
    assert not (PROJECT_ROOT / "applications/code_server_ide/config.py").exists()


def test_test_case_generate_uses_project_layers():
    module_root = PROJECT_ROOT / "applications/test_case_generate"
    assert module_root.is_dir()
    assert not (PROJECT_ROOT / "applications/weixianzhe").exists()
    assert not (module_root / "config.py").exists()
    assert not (module_root / "schemas/response.py").exists()
    assert PROJECT_CONFIG.TEST_CASE_SKILLS == "test-case-generator"
    assert PROJECT_CONFIG.TEST_CASE_OUTPUT_DIR
