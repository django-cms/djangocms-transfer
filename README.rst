===================
django CMS Transfer
===================

|pypi| |build| |coverage|

**django CMS Transfer** is an **experimental** package that allows you to export
and import plugin data from a page or a placeholder. It does not support foreign
key relations and won't import/export related data, such as `media <https://github.com/django-cms/djangocms-transfer/issues/18>`_.

.. note:: 
        
        This project is endorsed by the `django CMS Association <https://www.django-cms.org/en/about-us/>`_.
        That means that it is officially accepted by the dCA as being in line with our roadmap vision and development/plugin policy. 
        Join us on `Slack <https://www.django-cms.org/slack/>`_.

.. image:: preview.gif


*******************************************
Contribute to this project and win rewards
*******************************************

Because this is a an open-source project, we welcome everyone to
`get involved in the project <https://www.django-cms.org/en/contribute/>`_ and
`receive a reward <https://www.django-cms.org/en/bounty-program/>`_ for their contribution. 
Become part of a fantastic community and help us make django CMS the best CMS in the world.   

We'll be delighted to receive your
feedback in the form of issues and pull requests. Before submitting your
pull request, please review our `contribution guidelines
<http://docs.django-cms.org/en/latest/contributing/index.html>`_.

We're grateful to all contributors who have helped create and maintain this package.
Contributors are listed at the `contributors <https://github.com/django-cms/djangocms-transfer/graphs/contributors>`_
section.


Documentation
=============

The setting ``DJANGO_CMS_TRANSFER_SERIALIZER`` allows to register a custom json serializer. An example for an use case could be to subclass Django's build-in python serializer and let it base64-encode inline image data base64. 

See ``REQUIREMENTS`` in the `setup.py <https://github.com/divio/djangocms-transfer/blob/master/setup.py>`_
file for additional dependencies:

|python| |django| |djangocms|


Installation
------------

For a manual install:

* run ``pip install djangocms-transfer``
* add ``djangocms_transfer`` to your ``INSTALLED_APPS``
* run ``python manage.py migrate djangocms_transfer``


Running Tests
-------------

You can run tests by executing::

    virtualenv env
    source env/bin/activate
    pip install -r tests/requirements.txt
    python setup.py test


.. |pypi| image:: https://badge.fury.io/py/djangocms-transfer.svg
    :target: http://badge.fury.io/py/djangocms-transfer
.. |build| image:: https://travis-ci.org/divio/djangocms-transfer.svg?branch=master
    :target: https://travis-ci.org/divio/djangocms-transfer
.. |coverage| image:: https://codecov.io/gh/divio/djangocms-transfer/branch/master/graph/badge.svg
    :target: https://codecov.io/gh/divio/djangocms-transfer

.. |python| image:: https://img.shields.io/badge/python-3.5+-blue.svg
    :target: https://pypi.org/project/djangocms-transfer/
.. |django| image:: https://img.shields.io/badge/django-2.2,%203.0,%203.1-blue.svg
    :target: https://www.djangoproject.com/
.. |djangocms| image:: https://img.shields.io/badge/django%20CMS-3.7%2B-blue.svg
    :target: https://www.django-cms.org/
