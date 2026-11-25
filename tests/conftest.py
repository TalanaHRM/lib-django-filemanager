import django
from django.conf import settings


def pytest_configure():
    if not settings.configured:
        settings.configure(
            SECRET_KEY="test-only",
            INSTALLED_APPS=["django.contrib.staticfiles", "filemanager"],
            STATIC_URL="/static/",
            TEMPLATES=[{"BACKEND": "django.template.backends.django.DjangoTemplates", "APP_DIRS": True}],
            DATABASES={},
            USE_TZ=True,
        )
        django.setup()
