"""Basic tests for Mimeo."""

from mimeo import __version__


def test_version():
    """Test version is defined."""
    assert __version__ is not None
    assert isinstance(__version__, str)
