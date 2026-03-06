"""Setup script for AgentPier CrewAI Integration"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="agentpier-crewai",
    version="0.1.0",
    author="AgentPier",
    author_email="support@agentpier.com",
    description="Trust scoring integration for CrewAI agents",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/gatewaybuddy/agentpier",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    python_requires=">=3.8",
    install_requires=[
        "crewai==1.10.1",
        "agentpier>=1.0.0",
        "pydantic>=1.8.0",
    ],
    extras_require={
        "dev": [
            "pytest>=6.0",
            "black>=21.0",
            "isort>=5.0",
            "mypy>=0.900",
        ]
    },
    keywords="ai agents trust scoring crewai agentpier reputation",
    project_urls={
        "Bug Reports": "https://github.com/gatewaybuddy/agentpier/issues",
        "Source": "https://github.com/gatewaybuddy/agentpier",
        "Documentation": "https://docs.agentpier.com",
    },
)
