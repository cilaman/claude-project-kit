"""Base model conventions.

`TenantModel` is the only correct way to create a tenant entity: it carries
`organization_id`, fills it from the active context, and thereby lands in the registry
(`core.register.tenant_models`) the isolation guard tests watch.
"""

import uuid

from django.db import models

from core.tenancy import required_organization_id


class UuidModel(models.Model):
    """UUID primary key — tenant data must not be guessable by incrementing."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class TimestampedModel(models.Model):
    """When the record was created and last changed. Not an audit trail — that also
    records who made the change, and belongs to a dedicated entity."""

    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        abstract = True


class TenantModel(UuidModel):
    """Base of a tenant entity — data belonging to one organization.

    The caller does not write `organization_id`: it comes from the active tenant
    context. Callers setting it themselves would sooner or later set it wrong — RLS
    would stop it, but only as an error from the database.

    Every subclass needs a migration with `core.db.rls_operations(<table>)`; otherwise
    `tests/tenancy/test_rls_policies.py` fails.
    """

    # Adapt the app label if the organization lives elsewhere.
    organization = models.ForeignKey(
        "tenancy.Organization",
        on_delete=models.CASCADE,
        related_name="+",
        editable=False,
        db_index=True,
    )

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if self.organization_id is None:
            self.organization_id = required_organization_id()
        return super().save(*args, **kwargs)

    def full_clean(self, *args, **kwargs):
        """Validates with the tenant column already filled in.

        Django skips every uniqueness check whose fields include an excluded one, so
        `full_clean(exclude=["organization"])` would leave every
        `UniqueConstraint(fields=["organization", …])` unchecked until the database
        raises — a 500 instead of an error next to the field. Filling the column here
        from the same source as `save()` keeps both promises.
        """
        if self.organization_id is None:
            self.organization_id = required_organization_id()
        return super().full_clean(*args, **kwargs)
