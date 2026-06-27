"""Setup script for backward compatibility.

This file is kept for:
1. Older pip versions that don't support pyproject.toml
2. Developers who prefer `python setup.py develop`
3. Tools that expect setup.py (e.g., some IDEs)
"""

from setuptools import setup, find_packages

setup(
    name="win-computer-use",
    version="1.0.0",
    description="Windows desktop automation for AI agents",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="CarlosShao",
    author_email="carlos.shao@example.com",
    url="https://github.com/CarlosShao/win-computer-use",
    packages=find_packages(where="."),
    include_package_data=True,
    python_requires=">=3.10",
    install_requires=[
        "pywinauto>=0.6.8",
        "opencv-python>=4.8.0",
        "numpy>=1.24.0",
        "Pillow>=10.0.0",
        "uiautomation>=2.0.0",
        "mss>=9.0",
        "pytesseract>=0.3.10",
    ],
    extras_require={
        "server": ["fastapi>=0.104.0", "uvicorn>=0.24.0"],
        "ocr": ["rapidocr>=2.0.0", "tesserocr>=2.6.0"],
    },
    entry_points={
        "console_scripts": [
            "win-computer-use=win_computer_use.cli:main",
            "win-computer-use-server=win_computer_use.server:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: Microsoft :: Windows",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: System :: Operating System",
    ],
)
