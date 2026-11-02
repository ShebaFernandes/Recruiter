from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("talent", "0028_enquiry_follow_up_and_notifications")]

    operations = [
        migrations.AlterField(
            model_name="resumeprocessingjob",
            name="attempts",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
