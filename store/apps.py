from django.apps import AppConfig


class StoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'store'

    def ready(self):
        # Financial models live in a separate module to keep the core commerce
        # model file readable. Importing them here registers them under `store`.
        from . import financial_models  # noqa: F401
        from . import signals  # noqa: F401
