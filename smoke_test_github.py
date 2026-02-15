#!/usr/bin/env python3
"""Smoke test for GitHub Pages integration.

This script tests the GitHub Pages provider against the real GitHub API.

Usage:
    uv run python smoke_test_github.py

Requirements:
    - gh CLI must be installed and authenticated
    - Will create a test repository (mimeo-test-<timestamp>)
    - Will clean up the repository after testing

The test will:
1. Create a test repository
2. Deploy a simple HTML page
3. Configure GitHub Pages with custom domain
4. Verify the repository was created correctly
5. Clean up (delete the test repository)
"""

import sys
import time
from datetime import datetime
from pathlib import Path

from mimeo.providers.host.github import GitHubHost


def create_test_content(test_dir: Path) -> None:
    """Create test HTML content.

    Args:
        test_dir: Directory to create content in
    """
    test_dir.mkdir(parents=True, exist_ok=True)

    # Create simple index.html
    index_html = test_dir / "index.html"
    index_html.write_text(
        """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mimeo Test Site</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        .container {
            text-align: center;
            padding: 2rem;
        }
        h1 {
            font-size: 3rem;
            margin: 0;
        }
        p {
            font-size: 1.2rem;
            opacity: 0.9;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Mimeo Test Site</h1>
        <p>GitHub Pages integration test</p>
        <p>Generated: """ + datetime.now().isoformat() + """</p>
    </div>
</body>
</html>
"""
    )

    # Create CNAME file
    cname = test_dir / "CNAME"
    cname.write_text("mimeo-test.example.com\n")

    print(f"Created test content in {test_dir}")


def cleanup_test_repo(repo_name: str) -> None:
    """Clean up test repository.

    Args:
        repo_name: Repository name to delete
    """
    import subprocess

    try:
        print(f"\nCleaning up test repository: {repo_name}")
        result = subprocess.run(
            ["gh", "repo", "delete", repo_name, "--yes"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            print(f"Successfully deleted {repo_name}")
        else:
            print(f"Warning: Could not delete {repo_name}: {result.stderr}")
            print("You may need to delete it manually at:")
            print(f"  https://github.com/{repo_name}/settings")
    except Exception as e:
        print(f"Warning: Failed to clean up {repo_name}: {e}")
        print("You may need to delete it manually")


def main() -> int:
    """Run smoke test."""
    print("=" * 70)
    print("GitHub Pages Provider Smoke Test")
    print("=" * 70)

    # Generate test domain with timestamp
    # Use a valid domain format for GitHub Pages custom domain
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    # Use example.com as it's reserved for documentation/testing (RFC 2606)
    test_domain = f"mimeo-test-{timestamp}.example.com"

    print(f"\nTest domain: {test_domain}")
    print(f"This will create a GitHub repository and test Pages configuration.")
    print("\nPress Enter to continue or Ctrl+C to abort...")
    input()

    # Create test content directory
    test_dir = Path(f"/tmp/mimeo-test-{timestamp}")

    try:
        # Step 1: Create test content
        print("\n[1/5] Creating test content...")
        create_test_content(test_dir)

        # Step 2: Initialize GitHub host provider
        print("\n[2/5] Initializing GitHub host provider...")
        host = GitHubHost()
        print("GitHub CLI authenticated successfully")

        # Get authenticated user for cleanup
        user = host._get_authenticated_user()
        repo_full_name = f"{user}/{test_domain}"
        print(f"Repository will be created as: {repo_full_name}")

        # Step 3: Deploy site
        print(f"\n[3/5] Deploying site to {test_domain}...")
        url = host.deploy_site(test_domain, test_dir)
        print(f"Deployment successful!")
        print(f"Site URL: {url}")

        # Step 4: Verify deployment
        print("\n[4/5] Verifying deployment...")
        print(f"Checking repository: {repo_full_name}")

        # Check repository exists
        repo_info = host._gh_api(f"repos/{repo_full_name}")
        print(f"  Repository name: {repo_info.get('name')}")
        print(f"  Full name: {repo_info.get('full_name')}")
        print(f"  Private: {repo_info.get('private')}")
        print(f"  Default branch: {repo_info.get('default_branch')}")

        # Check GitHub Pages configuration
        pages_info = host._gh_api(f"repos/{repo_full_name}/pages")
        print(f"  Pages status: {pages_info.get('status')}")
        print(f"  Pages URL: {pages_info.get('html_url')}")
        print(f"  Custom domain: {pages_info.get('cname')}")
        print(f"  Build type: {pages_info.get('build_type')}")

        # Step 5: Success!
        print("\n[5/5] Smoke test completed successfully!")
        print("\nResults:")
        print(f"  Repository: https://github.com/{repo_full_name}")
        print(f"  Pages URL: {pages_info.get('html_url')}")
        print(f"  Custom domain: {pages_info.get('cname')}")

        print("\nNote: GitHub Pages may take a few minutes to build and deploy.")
        print(f"Check the Actions tab: https://github.com/{repo_full_name}/actions")

        # Ask about cleanup
        print("\nClean up test repository? (y/n): ", end="")
        cleanup = input().strip().lower()
        if cleanup == "y":
            cleanup_test_repo(repo_full_name)
        else:
            print(f"Test repository preserved at: https://github.com/{repo_full_name}")

        return 0

    except KeyboardInterrupt:
        print("\n\nSmoke test aborted by user")
        return 1
    except Exception as e:
        print(f"\nSmoke test failed with error: {e}")
        import traceback
        traceback.print_exc()

        # Attempt cleanup on error
        try:
            user = GitHubHost()._get_authenticated_user()
            cleanup_test_repo(f"{user}/{test_domain}")
        except Exception:
            pass

        return 1
    finally:
        # Clean up test content directory
        if test_dir.exists():
            import shutil
            shutil.rmtree(test_dir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
