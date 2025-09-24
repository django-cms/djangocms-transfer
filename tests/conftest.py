import os
import sys

import django
import pytest
from django.conf import settings
from django.test.utils import get_runner


def transfer(first, second=None):
    if second:
        return first, second
    return first


@pytest.fixture
def use_nonexistent_transfer_hook(settings):
    settings.DJANGOCMS_TRANSFER_PROCESS_EXPORT_PLUGIN_DATA = "a.b.c"
    settings.DJANGOCMS_TRANSFER_PROCESS_IMPORT_PLUGIN_DATA = "a.b.c"


@pytest.fixture
def use_existent_transfer_hook(settings):
    settings.DJANGOCMS_TRANSFER_PROCESS_EXPORT_PLUGIN_DATA = "tests.conftest.transfer"
    settings.DJANGOCMS_TRANSFER_PROCESS_IMPORT_PLUGIN_DATA = "tests.conftest.transfer"


def pytest_configure():
    os.environ["DJANGO_SETTINGS_MODULE"] = "tests.settings"
    django.setup()


def run(path):
    TestRunner = get_runner(settings)
    test_runner = TestRunner()
    failures = test_runner.run_tests(path)
    sys.exit(bool(failures))


if __name__ == "__main__":
    run(sys.argv[1:])
