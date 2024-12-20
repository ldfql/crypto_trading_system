import pytest

def test_ci_workflow():
    """Test to verify CI workflow is working."""
    assert True, "Basic test to verify CI pipeline"

def test_dependency_versions():
    """Test to verify dependency versions are correct."""
    import fastapi
    import pydantic
    import sqlalchemy
    import numpy

    assert fastapi.__version__.startswith("0.104"), "FastAPI version check"
    assert pydantic.__version__.startswith("2.5"), "Pydantic version check"
    assert sqlalchemy.__version__.startswith("2.0"), "SQLAlchemy version check"
    assert numpy.__version__.startswith("1.26"), "NumPy version check"
