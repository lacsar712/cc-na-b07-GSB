from django.db import models


class Inspection(models.Model):
    aid_code = models.CharField("航标编号", max_length=40)
    measured_cd = models.FloatField("实测光强")
    required_cd = models.FloatField("要求光强")
    bearing_error_deg = models.FloatField("方位偏差")
    verdict = models.CharField("结论", max_length=20)
    note = models.CharField("说明", max_length=200)
    created_by = models.CharField("登记人", max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]

    @property
    def is_archived(self) -> bool:
        record = getattr(self, "archive_record", None)
        return record is not None


class ArchiveRecord(models.Model):
    """封存册：一条巡检记录被封存后，在此留档操作者、时刻与原因。"""

    inspection = models.OneToOneField(
        Inspection,
        on_delete=models.CASCADE,
        related_name="archive_record",
        verbose_name="巡检记录",
    )
    reason = models.CharField("封存原因", max_length=200)
    archived_by = models.CharField("封存操作者", max_length=64)
    archived_at = models.DateTimeField("封存时刻", auto_now_add=True)

    class Meta:
        ordering = ["-archived_at"]
