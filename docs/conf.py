# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
# import os
# import sys
# sys.path.insert(0, os.path.abspath('.'))

import os

def get_git_branch():
    """Get the git branch this repository is currently on"""
    path_to_here = os.path.abspath(os.path.dirname(__file__))

    # Invoke git to get the current branch which we use to get the theme
    try:
        p = subprocess.Popen(['git', 'branch'], stdout=subprocess.PIPE, cwd=path_to_here)

        # This will contain something like "* (HEAD detached at origin/MYBRANCH)"
        # or something like "* MYBRANCH"
        branch_output = p.communicate()[0]

        # This is if git is in a normal branch state
        match = re.search(r'\* (?P<branch_name>[^\(\)\n ]+)', branch_output)
        if match:
            return match.groupdict()['branch_name']

        # git is in a detached HEAD state
        match = re.search(r'\(HEAD detached at origin/(?P<branch_name>[^\)]+)\)', branch_output)
        if match:
            return match.groupdict()['branch_name']
    except Exception:
        print(u'Could not get the branch')

    # Couldn't figure out the branch probably due to an error
    return None

# -- Project information -----------------------------------------------------

project = 'bunkerized-nginx'
copyright = '2021, bunkerity'
author = 'bunkerity'

# The full version, including alpha/beta/rc tags
release = 'v1.2.6'


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = ['myst_parser', 'sphinx_sitemap']

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
import sphinx_rtd_theme
html_theme = "sphinx_rtd_theme"
html_theme_path = [sphinx_rtd_theme.get_html_theme_path()]

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']

# for sitemap
sitemap_filename = "sm.xml"
branch = get_git_branch()
if branch == "master" :
	html_baseurl = 'https://bunkerized-nginx.readthedocs.io/en/latest/'
else :
	html_baseurl = 'https://bunkerized-nginx.readthedocs.io/en/dev/'

# custom robots.txt
html_extra_path = ['robots.txt']
