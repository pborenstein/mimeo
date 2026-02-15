"""Tests for content generation."""

import tempfile
from pathlib import Path

import pytest

from mimeo.content import generate_minimal_site, _format_domain


class TestContentGeneration:
    """Tests for content generation functions."""

    def test_format_domain(self) -> None:
        """Test domain formatting with spaces."""
        assert _format_domain("example.com") == "e x a m p l e . c o m"
        assert _format_domain("test.io") == "t e s t . i o"
        assert _format_domain("a") == "a"

    def test_format_domain_preserves_case(self) -> None:
        """Test that domain formatting preserves case."""
        assert _format_domain("Example.COM") == "E x a m p l e . C O M"

    def test_generate_minimal_site_creates_directory(self) -> None:
        """Test that generate_minimal_site creates output directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "new_dir"
            assert not output_dir.exists()

            generate_minimal_site("example.com", output_dir)

            assert output_dir.exists()
            assert output_dir.is_dir()

    def test_generate_minimal_site_creates_index_html(self) -> None:
        """Test that generate_minimal_site creates index.html."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            generate_minimal_site("example.com", output_dir)

            index_path = output_dir / "index.html"
            assert index_path.exists()
            assert index_path.is_file()

    def test_generate_minimal_site_content_structure(self) -> None:
        """Test that generated HTML has correct structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            domain = "example.com"

            generate_minimal_site(domain, output_dir)

            index_path = output_dir / "index.html"
            content = index_path.read_text()

            # Check for essential HTML elements
            assert "<!DOCTYPE html>" in content
            assert "<html lang=\"en\">" in content
            assert "<meta charset=\"UTF-8\">" in content
            assert "<meta name=\"viewport\"" in content
            assert f"<title>{domain}</title>" in content
            assert "</html>" in content

    def test_generate_minimal_site_includes_domain(self) -> None:
        """Test that generated HTML includes the domain name."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            domain = "test.example.com"

            generate_minimal_site(domain, output_dir)

            index_path = output_dir / "index.html"
            content = index_path.read_text()

            # Check domain is formatted with spaces
            formatted_domain = _format_domain(domain)
            assert formatted_domain in content

    def test_generate_minimal_site_has_styles(self) -> None:
        """Test that generated HTML includes CSS styles."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            generate_minimal_site("example.com", output_dir)

            index_path = output_dir / "index.html"
            content = index_path.read_text()

            # Check for key CSS properties
            assert "<style>" in content
            assert "background-color: #1a1a1a" in content
            assert "color: #e0e0e0" in content
            assert "display: flex" in content
            assert "justify-content: center" in content
            assert "align-items: center" in content
            assert "letter-spacing:" in content

    def test_generate_minimal_site_overwrites_existing(self) -> None:
        """Test that generate_minimal_site overwrites existing files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            index_path = output_dir / "index.html"

            # Create initial file
            generate_minimal_site("first.com", output_dir)
            first_content = index_path.read_text()

            # Overwrite with new domain
            generate_minimal_site("second.com", output_dir)
            second_content = index_path.read_text()

            # Content should be different
            assert first_content != second_content
            assert "f i r s t . c o m" in first_content
            assert "s e c o n d . c o m" in second_content

    def test_generate_minimal_site_with_subdomain(self) -> None:
        """Test generation with a subdomain."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            domain = "blog.example.com"

            generate_minimal_site(domain, output_dir)

            index_path = output_dir / "index.html"
            content = index_path.read_text()

            assert "b l o g . e x a m p l e . c o m" in content
            assert f"<title>{domain}</title>" in content

    def test_generate_minimal_site_with_special_tld(self) -> None:
        """Test generation with special TLDs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            domain = "mimeo.lol"

            generate_minimal_site(domain, output_dir)

            index_path = output_dir / "index.html"
            content = index_path.read_text()

            assert "m i m e o . l o l" in content

    def test_generate_minimal_site_mobile_responsive(self) -> None:
        """Test that generated HTML includes mobile viewport meta tag."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            generate_minimal_site("example.com", output_dir)

            index_path = output_dir / "index.html"
            content = index_path.read_text()

            assert "width=device-width" in content
            assert "initial-scale=1.0" in content
