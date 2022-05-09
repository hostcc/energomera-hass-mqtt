"""
Configuration file for the Sphinx documentation builder.

This file only contains a selection of the most common options. For a full
list see the documentation:
https://www.sphinx-doc.org/en/master/usage/configuration.html
"""

# -- Path setup --------------------------------------------------------------
import sys
from sphinx.util.inspect import getdoc
from sphinx.util.docstrings import separate_metadata
sys.path.extend(['../src'])

# -- Project information -----------------------------------------------------

project = 'energomera-hass-mqtt'
copyright = '2022, Ilia Sotnikov'
author = 'Ilia Sotnikov'


extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.autosummary',
    'sphinx.ext.intersphinx',
    'sphinx.ext.autosectionlabel',
]

exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = 'sphinx_rtd_theme'

autodoc_default_options = {
    'members': True,
    'inherited-members': True,
    'show-inheritance': True,
    'member-order': 'bysource',
    'class-doc-from': 'both',
}

source_suffix = {
    '.rst': 'restructuredtext',
    '.md': 'markdown',
}

intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
}
