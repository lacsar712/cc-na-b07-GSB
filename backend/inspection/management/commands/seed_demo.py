from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand
from django.utils import timezone

from inspection.models import Inspection
from inspection.rules import judge


class Command(BaseCommand):
    help = "seed two inspections and two accounts"

    def handle(self, *args, **options):
        group, _ = Group.objects.get_or_create(name="inspector")
        keeper, created = User.objects.get_or_create(username="keeper")
        if created or not keeper.check_password("light123456"):
            keeper.set_password("light123456")
            keeper.save()
        keeper.groups.add(group)
        watch, created = User.objects.get_or_create(username="watch")
        if created or not watch.check_password("watch123456"):
            watch.set_password("watch123456")
            watch.save()
        watch.groups.remove(group)
        if Inspection.objects.exists():
            self.stdout.write("already seeded")
            return
        samples = [
            ("LH-01", 1400, 1200, 0.4),
            ("LH-09", 800, 1200, 0.2),
        ]
        for code, measured, required, bearing in samples:
            verdict, note = judge(measured, required, bearing)
            Inspection.objects.create(
                aid_code=code,
                measured_cd=measured,
                required_cd=required,
                bearing_error_deg=bearing,
                verdict=verdict,
                note=note,
                created_by="keeper",
            )
        # 交卷封存：合格的明亮种子 LH-01 封存并写明原因，默认总表只剩偏暗的 LH-09。
        bright = Inspection.objects.get(aid_code="LH-01")
        bright.archived = True
        bright.archive_reason = "交卷封存：LH-01 合格实测，明亮种子归档备查"
        bright.archived_by = "keeper"
        bright.archived_at = timezone.now()
        bright.save(
            update_fields=["archived", "archive_reason", "archived_by", "archived_at"]
        )
        self.stdout.write("seeded")
