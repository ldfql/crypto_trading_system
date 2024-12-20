#!/usr/bin/env python3
"""Verify CI/CD configuration and dependencies."""
import os
import sys
import subprocess
import json
from pathlib import Path

def check_python_config():
    """Verify Python configuration and dependencies."""
    try:
        # Check Python version
        python_version = sys.version_info
        if python_version.major != 3 or python_version.minor != 12:
            print(f"Warning: Python version {python_version.major}.{python_version.minor} "
                  "does not match CI requirement (3.12)")
            return False

        # Check pip dependencies
        requirements_file = Path(__file__).parent.parent / "requirements.txt"
        dev_requirements_file = Path(__file__).parent.parent / "requirements-dev.txt"

        if not requirements_file.exists() or not dev_requirements_file.exists():
            print("Error: Missing requirements files")
            return False

        # Verify pip can install requirements
        subprocess.run(["pip", "install", "-r", str(requirements_file)], check=True)
        subprocess.run(["pip", "install", "-r", str(dev_requirements_file)], check=True)

        return True
    except Exception as e:
        print(f"Error checking Python configuration: {e}")
        return False

def check_node_config():
    """Verify Node.js configuration and dependencies."""
    try:
        frontend_dir = Path(__file__).parent.parent.parent / "frontend" / "crypto-trading-pwa"
        if not frontend_dir.exists():
            print("Error: Frontend directory not found")
            return False

        package_json = frontend_dir / "package.json"
        if not package_json.exists():
            print("Error: package.json not found")
            return False

        with open(package_json) as f:
            pkg_data = json.load(f)
            if "dependencies" not in pkg_data or "devDependencies" not in pkg_data:
                print("Error: Invalid package.json structure")
                return False

        return True
    except Exception as e:
        print(f"Error checking Node.js configuration: {e}")
        return False

def check_github_workflow():
    """Verify GitHub Actions workflow configuration."""
    try:
        workflow_file = Path(__file__).parent.parent.parent / ".github" / "workflows" / "ci.yml"
        if not workflow_file.exists():
            print("Error: GitHub Actions workflow file not found")
            return False

        # Basic YAML validation
        subprocess.run(["python", "-c", "import yaml; yaml.safe_load(open('{}'))".format(workflow_file)], check=True)
        return True
    except Exception as e:
        print(f"Error checking GitHub workflow: {e}")
        return False

def main():
    """Run all configuration checks."""
    success = True

    print("Checking Python configuration...")
    if not check_python_config():
        success = False

    print("\nChecking Node.js configuration...")
    if not check_node_config():
        success = False

    print("\nChecking GitHub Actions workflow...")
    if not check_github_workflow():
        success = False

    if not success:
        print("\nCI/CD configuration verification failed!")
        sys.exit(1)

    print("\nCI/CD configuration verification successful!")
    sys.exit(0)

if __name__ == "__main__":
    main()
