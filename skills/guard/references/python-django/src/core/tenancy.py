"""Tenant context — the only way the application touches an organization's data.

(Template path is `src/core/`; init moves the package under src if it differs.)

Tenant isolation is a property of the database, not of developer discipline. This
module does two things and nothing more:

1. opens a transaction with the `TENANT_SETTING` connection setting in place — the RLS
   policies (`core.db`) read it to decide which rows the connection sees at all;
2. lowers the connection role to the application role **without** `BYPASSRLS`
   (`SET LOCAL ROLE`), so the policies apply even where a more privileged role opened
   the connection — typically in tests, which create the database and migrate it.

Without a context, tenant tables return **nothing**. Failing into emptiness instead of
into somebody else's data is the point.

The context is set **only** here — by the middleware within a request, by
`tenant_context()` outside one — never by a hand-written `SET`. The module must not
import domain modules (it sits below them).
"""

from __future__ import annotations

import re
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from uuid import UUID

from django.apps import apps
from django.conf import settings
from django.db import connection, transaction
from django.http import Http404

#: Name of the connection setting the RLS policies read. The name ends up inside the
#: policy expressions when the migrations run, so renaming it here alone leaves every
#: policy of an existing database reading a setting nobody sets — and every tenant
#: query empty. Rebuild the database after a rename.
TENANT_SETTING = "myproject.organization_id"

_IDENTIFIER_RE = re.compile(r"^[a-z_][a-z0-9_]*$")


@dataclass(frozen=True)
class TenantContext:
    """What the application knows about the active tenant — ids and role only, no
    model instances, because `core` must not depend on the domain modules."""

    organization_id: UUID
    #: Membership role; `None` for a context opened outside a membership (management
    #: command, job). See `tenant_context` for what `None` means to the domain guards.
    role: str | None = None


_active_context: ContextVar[TenantContext | None] = ContextVar("tenant_context", default=None)


def active_context() -> TenantContext | None:
    return _active_context.get()


def active_organization_id() -> UUID | None:
    context = _active_context.get()
    return context.organization_id if context else None


class OutsideTenantContext(RuntimeError):
    """Code reached for tenant data without an open context."""


def required_organization_id() -> UUID:
    """Like `active_organization_id`, but fails loudly without a context."""
    organization_id = active_organization_id()
    if organization_id is None:
        raise OutsideTenantContext(
            "the operation needs an open tenant context — open one with "
            "core.tenancy.tenant_context(...), never with a hand-written SET"
        )
    return organization_id


def _quote_ident(name: str) -> str:
    """Inline a role name into SQL safely: `SET ROLE` takes no parameter, so anything
    that is not a plain identifier is rejected rather than escaped."""
    if not _IDENTIFIER_RE.match(name):
        raise ValueError(f"not a permissible database role name: {name!r}")
    return f'"{name}"'


@contextmanager
def tenant_context(organization_id: UUID | str, *, role: str | None = None):
    """Open a tenant context for one block — management commands, jobs, tests.

    Within a request the middleware below opens it. Nesting is allowed; leaving the
    block restores exactly the previous state, not the default one.

    **`role=None` means a system run** (seeding, import, nightly job acting for the
    organization). The obligation is therefore the opposite one: a channel acting on
    behalf of a member must pass `role=`, as the middleware does — a context opened
    without a role by a caller who has one silently turns a reader into the system.
    """
    if isinstance(organization_id, str):
        organization_id = UUID(organization_id)
    app_role = _quote_ident(settings.APP_DB_ROLE)

    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_setting(%s, true), current_user", [TENANT_SETTING])
            previous_organization, previous_role = cursor.fetchone()
            cursor.execute(f"SET LOCAL ROLE {app_role}")
            cursor.execute(
                "SELECT set_config(%s, %s, true)", [TENANT_SETTING, str(organization_id)]
            )

        token = _active_context.set(TenantContext(organization_id=organization_id, role=role))
        try:
            yield _active_context.get()
        finally:
            _active_context.reset(token)

        # Cleanup belongs on the success path only: on an exception `atomic()` rolls the
        # savepoint back and both `SET LOCAL`s with it, while querying a broken
        # transaction would mask the original error. After success the savepoint is
        # released and the settings would survive until the end of the outer
        # transaction — in tests, into the next query that must not see the tenant.
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT set_config(%s, %s, true)", [TENANT_SETTING, previous_organization or ""]
            )
            cursor.execute(f"SET LOCAL ROLE {_quote_ident(previous_role)}")


class TenantContextMiddleware:
    """Derives the organization from the `/o/<slug>/…` path and verifies membership.

    An invalid membership yields **404, not 403** — the existence of somebody else's
    organization is never confirmed.

    Adapt to the project: the membership model (`tenancy.Membership` with `user`,
    `organization`, `role`, and an active state) and the path shape are assumptions.
    """

    PATH_RE = re.compile(r"^/o/(?P<slug>[-a-z0-9]+)/")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        match = self.PATH_RE.match(request.path)
        if not match:
            request.tenant = None
            return self.get_response(request)

        # Imported lazily: auth views resolve the user model at import time, and the
        # user model may inherit from `core.models`, which imports this module.
        from django.contrib.auth.views import redirect_to_login

        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            # The login page reveals nothing about any organization.
            return redirect_to_login(request.get_full_path())

        # Through the app registry, not an import: `core` sits below the domain
        # modules and must not depend on them statically.
        Membership = apps.get_model("tenancy", "Membership")
        membership = (
            Membership.objects.select_related("organization")
            .filter(user=user, organization__slug=match.group("slug"))
            .first()
        )
        if membership is None:
            raise Http404("no such organization, or no membership in it")

        with tenant_context(membership.organization_id, role=membership.role) as context:
            request.tenant = context
            request.membership = membership
            return self.get_response(request)
