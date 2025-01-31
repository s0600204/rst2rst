# -*- coding: utf-8 -*-
"""Python packaging."""
import os
from setuptools import setup


def read_relative_file(filename):
    """Returns contents of the given file, which path is supposed relative
    to this module."""
    with open(os.path.join(os.path.dirname(__file__), filename)) as f:
        return f.read().strip()


NAME = 'rst2rst'
README = read_relative_file('README.rst')
VERSION = read_relative_file(os.path.join(NAME, 'version.txt')).strip()
PACKAGES = [NAME]
REQUIRES = ['setuptools', 'docutils>=0.10']
ENTRY_POINTS = {
    'console_scripts': [
        'rst2rst = rst2rst.scripts.rst2rst:main',
    ]
}

if __name__ == '__main__':  # Don't run setup() when we import this module.
    setup(name=NAME,
          version=VERSION,
          description='Transform reStructuredText documents. Standardize RST syntax',
          long_description=README,
          classifiers=['Development Status :: 3 - Alpha',
                       'License :: OSI Approved :: BSD License',
                       'Programming Language :: Python :: 3',
                       'Programming Language :: Python :: 3.5',
                       'Programming Language :: Python :: 3.6',
                       'Programming Language :: Python :: 3.7',
                       'Programming Language :: Python :: 3.8',
                       'Programming Language :: Python :: 3.9',
                       'Programming Language :: Python :: 3.10',
                       'Topic :: Documentation',
                       'Topic :: Software Development :: Documentation',
                       'Topic :: Software Development :: Quality Assurance',
                       'Topic :: Text Processing',
                       ],
          keywords='rst writer reStructuredText',
          author='Benoît Bryon',
          author_email='benoit@marmelune.net',
          url='https://github.com/benoitbryon/%s' % NAME,
          license='BSD',
          packages=[NAME],
          include_package_data=True,
          zip_safe=False,
          python_requires='>=3.5.4',
          install_requires=REQUIRES,
          entry_points=ENTRY_POINTS)
