===================
django CMS Transfer
===================

|pypi| |coverage| |python| |django| |djangocms|


**django CMS Transfer** is an **experimental** package that allows you to export
and import plugin data from a page or a placeholder. It does not support foreign
key relations and won't import/export related data, such as `media <https://github.com/django-cms/djangocms-transfer/issues/18>`_.

.. note::

        This project is endorsed by the `django CMS Association <https://www.django-cms.org/en/about-us/>`_.
        That means that it is officially accepted by the dCA as being in line with our roadmap vision and development/plugin policy.
        Join us on `Slack <https://www.django-cms.org/slack/>`_.

.. image:: preview.gif


Documentation
=============

The setting ``DJANGO_CMS_TRANSFER_SERIALIZER`` allows registration of a custom JSON serializer. An example use case would be subclassing Django's built-in Python serializer to base64-encode inline image data.

See ``REQUIREMENTS`` in the `setup.py <https://github.com/divio/djangocms-transfer/blob/master/setup.py>`_
file for additional dependencies:



Installation
------------

For a manual install:

* run ``pip install djangocms-transfer``
* add ``djangocms_transfer`` to your ``INSTALLED_APPS``


Version Compatibility
---------------------

For django CMS 4.0 or later, you must use djangocms-transfer 2.0 or later.

For django CMS 3.7 through 3.11 use versions 1.x of djangocms-transfer.


How to Use
----------

To export/import a page, click on the "*Page*" menu on the toolbar
and select your desired choice.

To export/import a plugin, Open the "*Structure board*", click on the
dropdown menu for the specific plugin and select your choice.


Customization
-------------

Following settings are available:

* **DJANGOCMS_TRANSFER_PROCESS_EXPORT_PLUGIN_DATA**:

  Enables processing of plugin instances prior to serialization, e.g.
  ``myapp.module.function``.

* **DJANGOCMS_TRANSFER_PROCESS_IMPORT_PLUGIN_DATA**:

  Enables processing of plugin instances prior to saving, e.g.
  ``myapp.module.function``.
  For example: set default-values for ForeignKeys (images for django_filer, ..)

As an example the combination of ``_PROCESS_EXPORT_PLUGIN_DATA`` and
``_PROCESS_IMPORT_PLUGIN_DATA`` lets you export and import the data between
different systems while setting the contents as you need it::

    # settings.py
    .._PROCESS_EXPORT_PLUGIN_DATA = "myapp.some.module.export_function"
    .._PROCESS_IMPORT_PLUGIN_DATA = "myapp.some.module.import_function"

    # custom functions
    def export_function(plugin, plugin_data):
        # remove child-plugins which can't be handled
        if plugin.parent_id and plugin.parent.plugin_type == "SomeParentPlugin":
            return None
        # change data
        if plugin.plugin_type == "SomePlugin":
            plugin_data["data"].update({
                "some_field": "TODO: change me",
            })
        return plugin_data

    def import_function(deserialized_object):
        some_related_object = MyModel.objects.first()
        for field in deserialized_object.object._meta.fields:
            # example of setting a default value for a related field
            if isinstance(field, ForeignKey):
                value = getattr(deserialized_object.object, field.attname)
                if field.related_model == MyModel and value is not None:
                    setattr(deserialized_object.object, field.name, some_related_object)


Running Tests
-------------

You can run tests by executing::

    python -m venv env
    source env/bin/activate
    pip install -r tests/requirements/dj51_cms41.txt
    coverage run -m pytest


*******************************************
Contribute to this project and win rewards
*******************************************

Because this is an open-source project, we welcome everyone to
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


.. |pypi| image:: https://badge.fury.io/py/djangocms-transfer.svg
    :target: http://badge.fury.io/py/djangocms-transfer
.. |coverage| image:: https://codecov.io/gh/django-cms/djangocms-transfer/branch/master/graph/badge.svg
    :target: https://codecov.io/gh/django-cms/djangocms-transfer

.. |python| image:: https://img.shields.io/badge/python-3.9+-blue.svg
    :target: https://pypi.org/project/djangocms-transfer/
.. |django| image:: https://img.shields.io/badge/django-4.2,%205.0,%205.1-blue.svg
    :target: https://www.djangoproject.com/
.. |djangocms| image:: https://img.shields.io/badge/django%20CMS-4-blue.svg
    :target: https://www.django-cms.org/
