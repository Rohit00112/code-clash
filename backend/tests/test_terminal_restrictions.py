from app.api.v1.terminal import _extract_install_packages


def test_extract_install_packages_basic():
    assert _extract_install_packages("pip install numpy pandas") == ["numpy", "pandas"]


def test_extract_install_packages_with_versions():
    assert _extract_install_packages("pip install numpy==1.26.4 pandas>=2.0") == ["numpy", "pandas"]


def test_extract_install_packages_ignores_flags():
    assert _extract_install_packages("python -m pip install --upgrade numpy") == ["numpy"]


def test_extract_install_packages_invalid_prefix():
    assert _extract_install_packages("npm install lodash") == []
