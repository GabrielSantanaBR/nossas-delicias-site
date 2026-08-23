from django.apps import AppConfig


class StoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'store'

    def ready(self):
        # Financial and management models live in separate modules to keep the
        # core commerce model file readable. Importing them here registers them
        # under the store application before checks/migrations run.
        from . import financial_models  # noqa: F401
        from . import management_models  # noqa: F401
        from . import signals  # noqa: F401
