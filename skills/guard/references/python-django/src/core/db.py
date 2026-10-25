"""Database side of tenant isolation — RLS policies as migration operations.

(Template path is `src/core/`; init moves the package under src if it differs.)

The policy is **not created at runtime**: every tenant table receives it through a
migration, so it is part of the schema and can be verified by querying the catalog.
`tests/tenancy/test_rls_policies.py` compares the registry of tenant models against
what is really in the database — a model without a policy fails the suite.
"""

from django.db import migrations

from core.tenancy import TENANT_SETTING

#: The same name on every table — the guard test looks the policy up by it.
POLICY_NAME = "tenant_isolation"

#: The column every tenant table is filtered by.
TENANT_COLUMN = "organization_id"

# `nullif(…, '')` is deliberate: outside a tenant context the setting falls back to an
# empty string and `''::uuid` would raise. This way the comparison is NULL and the
# query returns nothing — failing into emptiness, not into somebody else's data.
_ORGANIZATION = f"nullif(current_setting('{TENANT_SETTING}', true), '')::uuid"


def rls_sql(table: str) -> str:
    return f"""
        ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY;
        ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY;
        CREATE POLICY "{POLICY_NAME}" ON "{table}"
            USING ({TENANT_COLUMN} = {_ORGANIZATION})
            WITH CHECK ({TENANT_COLUMN} = {_ORGANIZATION});
    """


def rls_sql_reverse(table: str) -> str:
    return f"""
        DROP POLICY IF EXISTS "{POLICY_NAME}" ON "{table}";
        ALTER TABLE "{table}" NO FORCE ROW LEVEL SECURITY;
        ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY;
    """


def rls_operations(*tables: str) -> list[migrations.RunSQL]:
    """Operations to add to the migration that introduces tenant tables.

    `FORCE` matters: without it the table owner — the migration role — is not subject
    to the policy, so tests connecting with it would "verify" isolation on a connection
    the policy does not even apply to. `WITH CHECK` matters too: without it the read
    ban holds while writing on behalf of another tenant is allowed.
    """
    return [
        migrations.RunSQL(sql=rls_sql(table), reverse_sql=rls_sql_reverse(table))
        for table in tables
    ]


#: Policy that lets the **migration** role maintain a tenant table. Under FORCE even the
#: owner is subject to the tenant policy, and maintenance (retention, data moves) has no
#: tenant context: a `DELETE` filtered by the policy deletes zero rows and reports
#: success. Granted to `CURRENT_USER` — the role running migrations; the application
#: role keeps only the tenant policy.
MAINTENANCE_POLICY_NAME = "maintenance_by_migration_role"


def rls_maintenance_sql(table: str) -> str:
    return f"""
        CREATE POLICY "{MAINTENANCE_POLICY_NAME}" ON "{table}"
            TO CURRENT_USER USING (true) WITH CHECK (true);
    """


def rls_maintenance_sql_reverse(table: str) -> str:
    return f'DROP POLICY IF EXISTS "{MAINTENANCE_POLICY_NAME}" ON "{table}";'


def rls_maintenance_operations(*tables: str) -> list[migrations.RunSQL]:
    return [
        migrations.RunSQL(
            sql=rls_maintenance_sql(table), reverse_sql=rls_maintenance_sql_reverse(table)
        )
        for table in tables
    ]
