def judge(measured_cd: float, required_cd: float, bearing_error_deg: float) -> tuple[str, str]:
    if measured_cd < required_cd:
        return "不合格", "光强不足"
    if abs(bearing_error_deg) > 2:
        return "不合格", "方位偏差过大"
    return "合格", "光强与方位均在限内"


def archive_block_reason(inspection) -> str | None:
    """返回不能封存的原因；可以封存时返回 None。仅合格实测允许封存。"""
    if getattr(inspection, "archive_record", None) is not None:
        return "该记录已封存，不能重复封存"
    if inspection.verdict != "合格":
        return f"不合格实测不得封存：当前结论为{inspection.verdict}（{inspection.note}），须先改正至合格"
    return None
