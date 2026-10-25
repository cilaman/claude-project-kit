"""The registry of tenant models — derived from inheritance, never typed.

A hand-kept list would be a second home of the fact "this model is tenant data" and
would miss exactly the model somebody forgot. Inheriting from `TenantModel` is the
declaration; this only reads it. The opposite direction (a model linked to an
organization that does *not* inherit) is guarded in `tests/tenancy/test_rls_policies.py`.
"""

from django.apps import apps


def tenant_models():
    """Concrete models inheriting from `core.models.TenantModel`, sorted by label."""
    from core.models import TenantModel

    return sorted(
        (
            model
            for model in apps.get_models()
            if issubclass(model, TenantModel) and not model._meta.abstract
        ),
        key=lambda model: model._meta.label,
    )
