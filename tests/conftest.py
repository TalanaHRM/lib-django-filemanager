import django
from django.conf import settings


def pytest_configure():
    if not settings.configured:
        settings.configure(
            SECRET_KEY="test-only",
            INSTALLED_APPS=["filemanager"],
            DATABASES={},
            USE_TZ=True,
        )
        django.setup()
