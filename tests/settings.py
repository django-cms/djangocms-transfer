import os


SECRET_KEY = "djangocms-transfer-test"

ALLOWED_HOSTS = ["localhost"]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sites",
    "django.contrib.sessions",
    "django.contrib.admin",
    "django.contrib.messages",

    "cms",
    "menus",
    "treebeard",
    "sekizai",
    "djangocms_text",
    "djangocms_link",
    "djangocms_transfer",
    "tests.test_app",
]

MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "cms.middleware.toolbar.ToolbarMiddleware"
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            os.path.join((os.path.dirname(__file__)), "templates"),
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "sekizai.context_processors.sekizai",
            ],
        },
    },
]

SITE_ID = 1

CMS_TEMPLATES = (
    ("page.html", "Normal page"),
)

CMS_LANGUAGES = {
    1: [{
        "code": "en",
        "name": "English",
    }]
}

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
        "TEST": {
            # disable migrations when creating test database
            "MIGRATE": False,
        },
    }
}

if os.environ.get("DJANGOCMS_TRANSFER_TEST_POSTGRES"):
    DATABASES["default"] = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "postgres",
        "USER": os.environ.get("PGUSER", "postgres"),
        "PASSWORD": os.environ.get("PGPASSWORD", ""),
        "HOST": os.environ.get("PGHOST", "localhost"),
        "PORT": os.environ.get("PGPORT", "5432"),
        "TEST": {"MIGRATE": False, "CHARSET": "UTF8", "TEMPLATE": "template0"},
    }

CMS_CONFIRM_VERSION4 = True

USE_TZ = True

LANGUAGE_CODE = "en"

ROOT_URLCONF = "tests.urls"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
