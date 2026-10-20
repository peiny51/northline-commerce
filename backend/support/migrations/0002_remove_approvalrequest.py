# Remove the obsolete approval workflow. Existing approval rows will be deleted.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("support", "0001_initial"),
    ]

    operations = [
        migrations.DeleteModel(
            name="ApprovalRequest",
        ),
    ]
