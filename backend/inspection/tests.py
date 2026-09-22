"""封存/改正规则的端到端验收测试（测试库用 SQLite 即可）。"""
from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from inspection.models import ArchiveRecord, Inspection


class ArchiveAcceptanceTests(TestCase):
    def setUp(self):
        inspectors = Group.objects.create(name="inspector")
        self.keeper = User.objects.create_user("keeper", password="x")
        self.keeper.groups.add(inspectors)
        self.watch = User.objects.create_user("watch", password="x")

        self.bright = Inspection.objects.create(
            aid_code="LH-01", measured_cd=1400, required_cd=1200,
            bearing_error_deg=0.4, verdict="合格", note="光强与方位均在限内",
            created_by="keeper",
        )
        self.dim = Inspection.objects.create(
            aid_code="LH-09", measured_cd=800, required_cd=1200,
            bearing_error_deg=0.2, verdict="不合格", note="光强不足",
            created_by="keeper",
        )

    def _login(self, user):
        self.client.force_login(user)

    def test_archive_qualified_hides_from_main_list_and_records_book(self):
        """交卷：封存明亮种子并写明原因；总表只剩偏暗那条；封存册能看见原因。"""
        self._login(self.keeper)
        resp = self.client.post(
            reverse("archive", args=[self.bright.pk]),
            {"reason": "交卷封存：明亮种子已复核归档"},
        )
        self.assertRedirects(resp, reverse("archive_book"))

        record = ArchiveRecord.objects.get(inspection=self.bright)
        self.assertEqual(record.reason, "交卷封存：明亮种子已复核归档")
        self.assertEqual(record.archived_by, "keeper")
        self.assertIsNotNone(record.archived_at)

        main = self.client.get(reverse("list"))
        codes = list(main.context["rows"].values_list("aid_code", flat=True))
        self.assertEqual(codes, ["LH-09"])

        book = self.client.get(reverse("archive_book"))
        booked = list(book.context["records"])
        self.assertEqual(len(booked), 1)
        self.assertEqual(booked[0], record)
        self.assertContains(book, "交卷封存：明亮种子已复核归档")
        self.assertContains(book, "keeper")

    def test_archived_row_cannot_be_corrected_and_value_kept(self):
        """改正被封那条的亮度：服务端拒绝且数值不变。"""
        ArchiveRecord.objects.create(
            inspection=self.bright, reason="交卷封存", archived_by="keeper"
        )
        self._login(self.keeper)
        resp = self.client.post(
            reverse("correct", args=[self.bright.pk]),
            {"measured_cd": 9999, "bearing_error_deg": 1.5},
        )
        self.assertEqual(resp.status_code, 403)
        self.bright.refresh_from_db()
        self.assertEqual(self.bright.measured_cd, 1400)
        self.assertEqual(self.bright.bearing_error_deg, 0.4)

        # GET 改正表单同样拒绝
        self.assertEqual(
            self.client.get(reverse("correct", args=[self.bright.pk])).status_code, 403
        )

    def test_archive_requires_reason(self):
        self._login(self.keeper)
        resp = self.client.post(reverse("archive", args=[self.bright.pk]), {"reason": "  "})
        self.assertEqual(resp.status_code, 400)
        self.assertContains(resp, "封存必须填写原因", status_code=400)
        self.assertFalse(ArchiveRecord.objects.exists())

    def test_archive_unqualified_explains_why(self):
        """不合格的行尝试封存时要说明为何不行。"""
        self._login(self.keeper)
        resp = self.client.post(
            reverse("archive", args=[self.dim.pk]), {"reason": "想封存不合格行"}
        )
        self.assertEqual(resp.status_code, 400)
        self.assertContains(resp, "不合格实测不得封存", status_code=400)
        self.assertContains(resp, "光强不足", status_code=400)
        self.assertFalse(ArchiveRecord.objects.exists())

    def test_readonly_can_read_book_but_cannot_archive_or_correct(self):
        ArchiveRecord.objects.create(
            inspection=self.bright, reason="交卷封存", archived_by="keeper"
        )
        self._login(self.watch)
        # 只读能读封存册
        self.assertEqual(self.client.get(reverse("archive_book")).status_code, 200)
        # 不能封存
        resp = self.client.post(
            reverse("archive", args=[self.dim.pk]), {"reason": "无权尝试"}
        )
        self.assertEqual(resp.status_code, 403)
        # 不能改未封存行
        self.assertEqual(
            self.client.post(
                reverse("correct", args=[self.dim.pk]),
                {"measured_cd": 2000, "bearing_error_deg": 0},
            ).status_code,
            403,
        )
        # 也不能改被封行
        self.assertEqual(
            self.client.post(
                reverse("correct", args=[self.bright.pk]),
                {"measured_cd": 1, "bearing_error_deg": 0},
            ).status_code,
            403,
        )
        self.dim.refresh_from_db()
        self.assertEqual(self.dim.measured_cd, 800)

    def test_keeper_can_correct_unarchived_and_verdict_rejudged(self):
        """未封存行改正后重新判定：偏暗改到合格。"""
        self._login(self.keeper)
        resp = self.client.post(
            reverse("correct", args=[self.dim.pk]),
            {"measured_cd": 1300, "bearing_error_deg": -0.3},
        )
        self.assertRedirects(resp, reverse("detail", args=[self.dim.pk]))
        self.dim.refresh_from_db()
        self.assertEqual(self.dim.measured_cd, 1300)
        self.assertEqual(self.dim.bearing_error_deg, -0.3)
        self.assertEqual(self.dim.verdict, "合格")

    def test_double_archive_rejected(self):
        ArchiveRecord.objects.create(
            inspection=self.bright, reason="首次封存", archived_by="keeper"
        )
        self._login(self.keeper)
        resp = self.client.post(
            reverse("archive", args=[self.bright.pk]), {"reason": "再次封存"}
        )
        self.assertEqual(resp.status_code, 400)
        self.assertContains(resp, "已封存", status_code=400)
        self.assertEqual(ArchiveRecord.objects.count(), 1)
