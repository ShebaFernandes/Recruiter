from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("talent", "0022_resume_ai_http_diagnostics")]

    operations = [
        migrations.AlterField(
            model_name="resumeaiusage",
            name="resume",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="ai_usage",
                to="talent.resume",
            ),
        ),
    ]
