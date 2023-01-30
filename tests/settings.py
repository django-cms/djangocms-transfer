#!/usr/bin/env python
HELPER_SETTINGS = {
    "INSTALLED_APPS": [],
    "CMS_LANGUAGES": {
        1: [
            {
                "code": "en",
                "name": "English",
            }
        ]
    },
    "LANGUAGE_CODE": "en",
    "ALLOWED_HOSTS": ["localhost"],
    "DEFAULT_AUTO_FIELD": "django.db.models.AutoField",
}


def run():
    from app_helper import runner

    runner.cms("djangocms_transfer")


if __name__ == "__main__":
    run()
