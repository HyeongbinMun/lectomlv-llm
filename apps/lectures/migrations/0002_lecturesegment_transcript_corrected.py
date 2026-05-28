from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("lectures", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="lecturesegment",
            name="transcript_corrected",
            field=models.TextField(
                blank=True,
                default="",
                help_text="수동 교정 자막 텍스트 (비어 있으면 transcript 사용, \\n으로 줄바꿈)",
            ),
        ),
    ]
