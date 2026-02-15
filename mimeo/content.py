"""Content generation for Mimeo sites."""

from pathlib import Path


def generate_minimal_site(domain: str, output_dir: Path) -> None:
    """Generate a minimal landing page for a domain.

    Creates a simple, elegant landing page displaying the domain name
    in the style of mimeo.lol.

    Args:
        domain: Domain name to display
        output_dir: Directory to write the HTML file to

    Raises:
        OSError: If unable to create directory or write file
    """
    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate HTML content with domain name
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{domain}</title>
    <style>
        body {{
            margin: 0;
            height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            background-color: #1a1a1a;
            color: #e0e0e0;
            font-family: sans-serif;
            font-size: 2rem;
        }}
        .domain {{
            letter-spacing: 0.5rem;
        }}
    </style>
</head>
<body>
    <div class="domain">{_format_domain(domain)}</div>
</body>
</html>
"""

    # Write to index.html
    index_path = output_dir / "index.html"
    index_path.write_text(html_content)


def _format_domain(domain: str) -> str:
    """Format domain name with spaces between characters.

    Args:
        domain: Domain name to format

    Returns:
        Domain name with spaces between each character
    """
    return " ".join(domain)
