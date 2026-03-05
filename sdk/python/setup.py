"""Setup script for the AgentPier Python SDK."""

from setuptools import setup, find_packages

# Read README for long description
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

# Read version from __init__.py
with open("agentpier/__init__.py", "r", encoding="utf-8") as fh:
    for line in fh:
        if line.startswith("__version__"):
            version = line.split("=")[1].strip().strip('"').strip("'")
            break
    else:
        raise RuntimeError("Unable to find version string")

setup(
    name="agentpier",
    version=version,
    author="AgentPier",
    author_email="support@agentpier.org",
    description="Python SDK for the AgentPier trust scoring API",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/gatewaybuddy/agentpier",
    project_urls={
        "Bug Tracker": "https://github.com/gatewaybuddy/agentpier/issues",
        "Documentation": "https://docs.agentpier.org",
        "Source": "https://github.com/gatewaybuddy/agentpier",
        "API Reference": "https://api.agentpier.org/docs"
    },
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8", 
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
    install_requires=[
        "requests>=2.25.0",
    ],
    extras_require={
        "dev": [
            "pytest>=6.0",
            "pytest-mock>=3.0",
            "pytest-cov>=2.0",
            "black>=22.0",
            "flake8>=4.0",
            "mypy>=0.900",
            "twine>=4.0"
        ]
    },
    keywords=[
        "agentpier",
        "trust",
        "ai",
        "agents", 
        "marketplace",
        "reputation",
        "scoring",
        "api",
        "sdk"
    ],
    zip_safe=False,
    include_package_data=True
)