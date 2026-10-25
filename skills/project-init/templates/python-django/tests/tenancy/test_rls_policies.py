# kit:file tenancy
"""Schema guards: every tenant model has the column and the RLS policy — and every
model linked to an organization is tenant data or is named as an exception.

These tests do not exercise behaviour; they check that the mechanism is switched on.
A model inheriting from `core.models.TenantModel` lands in the registry by itself; if
its migration lacks `core.db.rls_operations(...)`, it fails here rather than in
production by showing somebody else's data.

The registry is derived from inheritance, so it guards only one direction. The other
— a model with a foreign key to `Organization` inheriting from plain `UuidModel` — is
guarded at the bottom: silence is not a decision.
"""

import pytest
from django.apps import apps
from django.db import connection

from core.db import POLICY_NAME
from core.register import tenant_models
from core.tenancy import TENANT_SETTING

pytestmark = pytest.mark.django_db

#: Concrete models linked to `Organization` that deliberately are **not** tenant data.
#: The value is the reason, in prose — a bare list would say somebody once looked at
#: the model, not why they left it outside RLS. Typical members: the business relation
#: between the platform and the customer (subscription, invoice — read across
#: organizations, reached by callbacks without a tenant context) and identity data
#: (membership, invitation — read through the user, the context is verified against it).
NON_TENANT_WITH_ORGANIZATION: dict[str, str] = {
    "tenancy.Membership": (
        "Identity data — always read through the user, never through the tenant, and it "
        "is what the tenant context itself is verified against."
    ),
}


def _label(model):
    return model._meta.label


def _models_linked_to_an_organization():
    """Concrete, hand-declared models with an FK/O2O to `Organization`."""
    Organization = apps.get_model("tenancy", "Organization")
    return sorted(
        (
            model
            for model in apps.get_models()
            if not model._meta.abstract
            and not model._meta.auto_created
            and any(field.related_model is Organization for field in model._meta.fields)
        ),
        key=_label,
    )


def test_the_registry_is_not_empty():
    """An empty registry would turn every test below into a silent no-op."""
    assert tenant_models(), "no model inherits from core.models.TenantModel"


@pytest.mark.parametrize("model", tenant_models(), ids=_label)
def test_a_tenant_model_has_the_organization_column(model):
    assert "organization" in {field.name for field in model._meta.fields}


@pytest.mark.parametrize("model", tenant_models(), ids=_label)
def test_a_tenant_table_has_rls_enabled_and_forced(model):
    table = model._meta.db_table
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = %s",
            [table],
        )
        row = cursor.fetchone()
    assert row is not None, f"table {table} does not exist in the database"
    enabled, forced = row
    assert enabled, f"{table}: ENABLE ROW LEVEL SECURITY is missing"
    # Without FORCE the owner — the migration role the tests connect with — is outside
    # the policy, and the isolation tests would prove nothing.
    assert forced, f"{table}: FORCE ROW LEVEL SECURITY is missing"


@pytest.mark.parametrize("model", tenant_models(), ids=_label)
def test_a_tenant_table_has_a_policy_reading_the_tenant_setting(model):
    table = model._meta.db_table
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT qual, with_check FROM pg_policies WHERE tablename = %s AND policyname = %s",
            [table, POLICY_NAME],
        )
        row = cursor.fetchone()
    assert row is not None, (
        f"{table}: policy {POLICY_NAME!r} is missing — add core.db.rls_operations(<table>) "
        "to the migration"
    )
    qual, with_check = row
    # Without WITH CHECK the read ban holds while writing for another tenant is allowed.
    assert with_check, f"{table}: the policy has no WITH CHECK"
    # The policy must read the setting the application sets: a half-done rename keeps
    # the expression looking right while every tenant query comes back empty.
    for expression in (qual, with_check):
        assert "organization_id" in expression
        assert TENANT_SETTING in expression, (
            f"{table}: the policy reads another setting than {TENANT_SETTING!r} — "
            "rebuild the database after renaming it"
        )


def test_there_is_something_to_classify():
    """Both sides empty would turn the reverse guard into a silent no-op."""
    assert _models_linked_to_an_organization(), "no model is linked to Organization"
    assert NON_TENANT_WITH_ORGANIZATION, (
        "the exception list is empty — either every model became tenant data (then this "
        "test should go too), or somebody emptied the list"
    )


def test_a_model_linked_to_an_organization_is_tenant_data_or_a_named_exception():
    from core.models import TenantModel

    unclassified = [
        _label(model)
        for model in _models_linked_to_an_organization()
        if not issubclass(model, TenantModel) and _label(model) not in NON_TENANT_WITH_ORGANIZATION
    ]
    assert not unclassified, (
        "a model linked to Organization must be tenant data (core.models.TenantModel + "
        "core.db.rls_operations in its migration) or be named with its reason in "
        "NON_TENANT_WITH_ORGANIZATION: " + ", ".join(unclassified)
    )


def test_every_exception_carries_a_reason():
    empty = [label for label, reason in NON_TENANT_WITH_ORGANIZATION.items() if not reason.strip()]
    assert not empty, "an exception without a reason is an oversight: " + ", ".join(empty)


def test_the_exceptions_are_alive():
    """A stale exception is worse than none — it covers a model nobody checked again."""
    from core.models import TenantModel

    non_tenant = {
        _label(model)
        for model in _models_linked_to_an_organization()
        if not issubclass(model, TenantModel)
    }
    stale = sorted(set(NON_TENANT_WITH_ORGANIZATION) - non_tenant)
    assert not stale, "entries that no longer hold — delete them: " + ", ".join(stale)
