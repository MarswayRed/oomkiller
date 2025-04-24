# setup.py
import os
from setuptools import setup, find_packages

def read_requirements(file_path='requirements.txt'):
    """Reads requirements from a file."""
    if not os.path.exists(file_path):
        return []
    with open(file_path, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip() and not line.startswith('#')]

def read_readme(file_path='README.md'):
    """Reads the README file."""
    if not os.path.exists(file_path):
        return "OOM Killer Helper Service" # Fallback description
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception:
        return "OOM Killer Helper Service" # Fallback description

# --- Package Information ---
NAME = 'oomkiller'
VERSION = '1.0.0'
DESCRIPTION = 'A guardian of memory space.'
LONG_DESCRIPTION = read_readme()
AUTHOR = 'Your Name / Your Organization'
AUTHOR_EMAIL = 'marswayred@gmail.red'
URL = 'https://github.com/marswayred/oomkiller'
LICENSE = 'MIT'

# --- Dependencies ---
INSTALL_REQUIRES = read_requirements()

# --- Entry Points (Command Line Script) ---
ENTRY_POINTS = {
    'console_scripts': [
        'oomkiller-daemon = oomkiller:main',
    ],
}

setup(
    name=NAME,
    version=VERSION,
    description=DESCRIPTION,
    long_description=LONG_DESCRIPTION,
    long_description_content_type='text/markdown',
    author=AUTHOR,
    author_email=AUTHOR_EMAIL,
    url=URL,
    license=LICENSE,
    py_modules=['oomkiller'],
    install_requires=INSTALL_REQUIRES,
    python_requires='>=3.6',
    entry_points=ENTRY_POINTS,
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: POSIX :: Linux',
        'Topic :: System :: Monitoring',
        'Topic :: System :: Systems Administration',
    ],
)