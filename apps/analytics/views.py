import json
from datetime import timedelta

from django.db.models import Count, Avg, FloatField
from django.db.models.functions import Cast
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.contrib.admin.views.decorators import staff_member_required 

from .models import AnalyticsSession, AnalyticsEvent


def _get_client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _get_or_create_session(request):
    cookie_name = "fx_analytics_sid"
    sid = request.COOKIES.get(cookie_name)
    session = None

    if sid:
        try:
            session = AnalyticsSession.objects.get(session_id=sid)
        except AnalyticsSession.DoesNotExist:
            session = None

    if not session:
        session = AnalyticsSession.objects.create(
            user=request.user if request.user.is_authenticated else None,
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
            ip_address=_get_client_ip(request),
        )

    return session


@csrf_exempt  # this endpoint only accepts simple analytics JSON
def analytics_event(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    session = _get_or_create_session(request)

    try:
        data = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid JSON"}, status=400)

    event_type = data.get("event_type", "unknown")
    page_path = data.get("page_path", "")
    referrer = data.get("referrer", "")
    metadata = data.get("metadata", {}) or {}

    AnalyticsEvent.objects.create(
        session=session,
        user=session.user,
        event_type=event_type,
        page_path=page_path,
        referrer=referrer,
        metadata=metadata,
    )

    response = JsonResponse({"ok": True})

    # Set cookie if missing
    cookie_name = "fx_analytics_sid"
    if not request.COOKIES.get(cookie_name):
        response.set_cookie(
            cookie_name,
            session.session_id,
            max_age=60 * 60 * 24 * 7,  # 7 days
            httponly=True,
            samesite="Lax",
        )

    return response

@staff_member_required  # 👈 only staff/superusers can access
def behaviour_console(request):
    since = timezone.now() - timedelta(days=30)

    base_qs = AnalyticsEvent.objects.filter(created_at__gte=since)

    # Top pages by views
    page_views = (
        base_qs.filter(event_type="page_view")
        .values("page_path")
        .annotate(count=Count("id"))
        .order_by("-count")[:20]
    )

    # Top downloads
    downloads = (
        base_qs.filter(event_type="download")
        .values("metadata__filename")
        .annotate(count=Count("id"))
        .order_by("-count")[:20]
    )

    # Pages by average time on page
    slow_pages = (
        base_qs.filter(event_type="time_on_page")
        .annotate(seconds_value=Cast("metadata__seconds", FloatField()))
        .values("page_path")
        .annotate(avg_seconds=Avg("seconds_value"))
        .order_by("-avg_seconds")[:20]
    )

    # Pages by average scroll depth (%)
    scroll_depth = (
        base_qs.filter(event_type="scroll_depth")
        .annotate(percent_value=Cast("metadata__percent", FloatField()))
        .values("page_path")
        .annotate(avg_percent=Avg("percent_value"))
        .order_by("-avg_percent")[:20]
    )

    # Home project thumbnails
    project_clicks = (
        base_qs.filter(event_type="project_click")
        .values("metadata__project_label")
        .annotate(clicks=Count("id"))
        .order_by("-clicks")[:20]
    )

    # CTA buttons (GitHub / Market / Forecast)
    cta_clicks = (
        base_qs.filter(event_type="cta_click")
        .values("metadata__label", "page_path")
        .annotate(clicks=Count("id"))
        .order_by("-clicks")[:20]
    )

    context = {
        "since": since,
        "page_views": page_views,
        "downloads": downloads,
        "slow_pages": slow_pages,
        "scroll_depth": scroll_depth,
        "project_clicks": project_clicks,
        "cta_clicks": cta_clicks,
    }
    return render(request, "ops/behaviour_console.html", context)
