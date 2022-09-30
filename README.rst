#######
rst2rst
#######

This project provides a `docutils`_ writer that produces `reStructuredText`_.
It allows users to transform RST documents, as an example, to standardize or
beautify RST syntax.

A ``rst2rst`` command is also provided.

The project was initiated as an utility for a `style guide for Sphinx-based
documentations`_. See also the `original ticket`_.


*******
Testing
*******

.. Note:: Testing requires the optional ``docutils`` dependency `Pygments`_.
          This is installed automatically when using ``tox``.

To run tests, navigate to the tests subdirectory and run::

  python -u alltests.py

It is also possible to test across multiple versions of ``python`` and
``docutils`` in one go with the use of `pyenv`_ and `tox`_::

  <install pyenv>
  pip install tox
  pyenv install 3.9.10 3.10.4
  pyenv shell 3.9.10 3.10.4
  tox


**********
Ressources
**********

* `code repository`_
* `bugtracker`_


**********
References
**********

.. target-notes::

.. _`docutils`: http://docutils.sourceforge.net/
.. _`reStructuredText`: http://docutils.sourceforge.net/rst.html
.. _`style guide for Sphinx-based documentations`:
   http://documentation-style-guide-sphinx.readthedocs.org
.. _`original ticket`:
   https://github.com/benoitbryon/documentation-style-guide-sphinx/issues/8
.. _`Pygments`: https://pypi.org/project/Pygments/
.. _`pyenv`: https://github.com/pyenv/pyenv
.. _`tox`: https://tox.wiki/en/latest/index.html
.. _`code repository`: https://github.com/benoitbryon/rst2rst
.. _`bugtracker`: https://github.com/benoitbryon/rst2rst/issues
