from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from inspection.models import ArchiveRecord, Inspection
from inspection.rules import archive_block_reason, judge


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
    # 默认总表不显示已封存行，封存的行改到封存册里查
    rows = Inspection.objects.filter(archive_record__isnull=True)
    return render(request, "list.html", {"rows": rows, "can_write": _can_write(request.user)})


@login_required
def archive_book_view(request):
    # 只读账号也能读封存册
    records = ArchiveRecord.objects.select_related("inspection")
    return render(
        request,
        "archive_book.html",
        {"records": records, "can_write": _can_write(request.user)},
    )


@login_required
def detail_view(request, pk):
    row = get_object_or_404(Inspection, pk=pk)
    return render(request, "detail.html", {"row": row, "can_write": _can_write(request.user)})


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
@require_http_methods(["GET", "POST"])
def correct_view(request, pk):
    if not _can_write(request.user):
        return HttpResponseForbidden("仅持灯账号可改正巡检记录")
    row = get_object_or_404(Inspection, pk=pk)
    # 已封存行禁止再改正亮度或偏角：服务端拒绝并保持原值
    if row.is_archived:
        return HttpResponseForbidden(
            f"该记录已封存（封存原因：{row.archive_record.reason}），禁止改正亮度或偏角"
        )
    error = ""
    if request.method == "POST":
        try:
            measured = float(request.POST["measured_cd"])
            bearing = float(request.POST["bearing_error_deg"])
        except (KeyError, ValueError):
            error = "请填写亮度与方位偏差两项数值"
        else:
            verdict, note = judge(measured, row.required_cd, bearing)
            row.measured_cd = measured
            row.bearing_error_deg = bearing
            row.verdict = verdict
            row.note = note
            row.save(update_fields=["measured_cd", "bearing_error_deg", "verdict", "note"])
            return redirect("detail", pk=row.pk)
    return render(request, "correct.html", {"row": row, "error": error})


@login_required
@require_http_methods(["POST"])
def archive_view(request, pk):
    if not _can_write(request.user):
        return HttpResponseForbidden("仅持灯账号可执行封存")
    row = get_object_or_404(Inspection, pk=pk)
    reason = request.POST.get("reason", "").strip()
    if not reason:
        return _render_detail_error(request, row, "封存必须填写原因", status=400)
    block = archive_block_reason(row)
    if block is not None:
        # 不合格的行尝试封存时，说明为何不行
        return _render_detail_error(request, row, block, status=400)
    ArchiveRecord.objects.create(
        inspection=row,
        reason=reason,
        archived_by=request.user.username,
    )
    return redirect("archive_book")


def _render_detail_error(request, row, message, status):
    return render(
        request,
        "detail.html",
        {"row": row, "can_write": _can_write(request.user), "archive_error": message},
        status=status,
    )
