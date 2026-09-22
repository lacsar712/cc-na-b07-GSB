from urllib.parse import quote

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from inspection.models import Inspection
from inspection.rules import judge


def _detail_redirect(pk, error):
    return redirect(f"{reverse('detail', args=[pk])}?error={quote(error)}")


def _can_write(user) -> bool:
    return user.groups.filter(name="inspector").exists()


def health(_request):
    from django.http import JsonResponse

    return JsonResponse({"status": "ok", "service": "nav-aid-inspection"})


@require_http_methods(["GET", "POST"])
def login_view(request):
    from django.contrib.auth import authenticate, login

    error = ""
    if request.method == "POST":
        user = authenticate(
            request,
            username=request.POST.get("username", "").strip(),
            password=request.POST.get("password", ""),
        )
        if user is None:
            error = "用户名或密码错误"
        else:
            login(request, user)
            return redirect("list")
    return render(request, "login.html", {"error": error})


def logout_view(request):
    from django.contrib.auth import logout

    logout(request)
    return redirect("login")


@login_required
def list_view(request):
    rows = Inspection.objects.filter(archived=False)
    return render(request, "list.html", {"rows": rows, "can_write": _can_write(request.user)})


@login_required
def archive_book_view(request):
    """封存册：所有登录用户可读，记录操作者、时刻与原因。"""
    rows = Inspection.objects.filter(archived=True)
    return render(
        request,
        "archive_book.html",
        {"rows": rows, "can_write": _can_write(request.user)},
    )


@login_required
def detail_view(request, pk):
    row = get_object_or_404(Inspection, pk=pk)
    error = request.GET.get("error", "")
    return render(
        request,
        "detail.html",
        {"row": row, "can_write": _can_write(request.user), "error": error},
    )


@login_required
@require_http_methods(["GET", "POST"])
def create_view(request):
    if not _can_write(request.user):
        return HttpResponseForbidden("仅巡检员可登记灯光巡检")
    error = ""
    if request.method == "POST":
        try:
            measured = float(request.POST["measured_cd"])
            required = float(request.POST["required_cd"])
            bearing = float(request.POST["bearing_error_deg"])
            code = request.POST["aid_code"].strip()
            if not code:
                raise ValueError("empty")
        except (KeyError, ValueError):
            error = "请填编号和三项数值"
        else:
            verdict, note = judge(measured, required, bearing)
            row = Inspection.objects.create(
                aid_code=code,
                measured_cd=measured,
                required_cd=required,
                bearing_error_deg=bearing,
                verdict=verdict,
                note=note,
                created_by=request.user.username,
            )
            return redirect("detail", pk=row.pk)
    return render(request, "form.html", {"error": error})


@login_required
@require_http_methods(["POST"])
def archive_view(request, pk):
    """持灯账号封存合格实测；必须填写原因，不合格行禁止封存。"""
    if not _can_write(request.user):
        return HttpResponseForbidden("仅持灯账号可封存记录")
    row = get_object_or_404(Inspection, pk=pk)
    reason = request.POST.get("archive_reason", "").strip()
    if not reason:
        return _detail_redirect(pk, "封存必须填写原因")
    if row.archived:
        return _detail_redirect(pk, "该记录已封存")
    if row.verdict != "合格":
        return _detail_redirect(pk, "不合格记录不能封存：仅合格实测可入库封存")
    row.archived = True
    row.archive_reason = reason
    row.archived_by = request.user.username
    row.archived_at = timezone.now()
    row.save(update_fields=["archived", "archive_reason", "archived_by", "archived_at"])
    return redirect("archive_book")


@login_required
@require_http_methods(["POST"])
def correct_view(request, pk):
    """改正亮度或偏角；已封存行服务端拒绝并保持原值。"""
    if not _can_write(request.user):
        return HttpResponseForbidden("仅持灯账号可改正记录")
    row = get_object_or_404(Inspection, pk=pk)
    if row.archived:
        return HttpResponseForbidden("记录已封存，禁止改正亮度或偏角")
    try:
        measured = float(request.POST["measured_cd"])
        bearing = float(request.POST["bearing_error_deg"])
    except (KeyError, ValueError):
        return _detail_redirect(pk, "请填写有效的亮度和偏角数值")
    row.measured_cd = measured
    row.bearing_error_deg = bearing
    verdict, note = judge(measured, row.required_cd, bearing)
    row.verdict = verdict
    row.note = note
    row.save(update_fields=["measured_cd", "bearing_error_deg", "verdict", "note"])
    return redirect("detail", pk=row.pk)
