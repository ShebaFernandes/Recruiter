from django.db import migrations
from django.db.models import Count
from django.db.models.functions import Lower


def add_indexes(apps, schema_editor):
    user = apps.get_model("auth", "User")
    # Fail without changing accounts. An operator must review collisions privately.
    for field in ("email", "username"):
        accounts = user.objects.using(schema_editor.connection.alias)
        if field == "email":
            # Staff may have a shared contact email with an explicit distinct login
            # identity. Preserve that existing administrator provisioning contract.
            accounts = accounts.filter(is_staff=False, is_superuser=False)
        collisions = (
            accounts.exclude(**{field: ""})
            .annotate(identifier=Lower(field))
            .values("identifier")
            .annotate(n=Count("id"))
            .filter(n__gt=1)
        )
        if collisions.exists():
            raise RuntimeError("Duplicate login identifiers require review before OAuth migration.")
    schema_editor.execute(
        "CREATE UNIQUE INDEX enter_unique_login_email ON auth_user (LOWER(email)) WHERE email <> '' AND NOT is_staff AND NOT is_superuser"
    )
    schema_editor.execute(
        "CREATE UNIQUE INDEX enter_unique_login_username ON auth_user (LOWER(username))"
    )


def remove_indexes(apps, schema_editor):
    schema_editor.execute("DROP INDEX IF EXISTS enter_unique_login_email")
    schema_editor.execute("DROP INDEX IF EXISTS enter_unique_login_username")


class Migration(migrations.Migration):
    dependencies = [("talent", "0034_googleoauthtransaction_externalidentity")]
    operations = [migrations.RunPython(add_indexes, remove_indexes)]
