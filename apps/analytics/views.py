import json
from datetime import timedelta

from django.db.models import Count, Avg, FloatField
from django.db.models.functions import Cast
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.contrib.admin.views.decorators import staff_member_required 

from .models import AnalyticsSession, AnalyticsEvent

import requests  




def _get_client_ip(request):
    """
    Get the best-guess client IP, handling proxies.
    """
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        # In case of multiple IPs, take the first one (original client)
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _populate_geo(session: AnalyticsSession):
    """
    Enrich a session with country/region/city using a GeoIP service.
    Called only when the session is first created.
    """
    # Don't overwrite if already set or if no IP
    if session.country or not session.ip_address:
        return

    ip = session.ip_address

    # Skip obvious local/private IPs (local dev, internal networks)
    if (
        ip.startswith("127.")
        or ip.startswith("10.")
        or ip.startswith("192.168.")
        or ip.startswith("172.16.")
        or ip.startswith("172.17.")
        or ip.startswith("172.18.")
        or ip.startswith("172.19.")
        or ip.startswith("172.20.")
        or ip.startswith("172.21.")
        or ip.startswith("172.22.")
        or ip.startswith("172.23.")
        or ip.startswith("172.24.")
        or ip.startswith("172.25.")
        or ip.startswith("172.26.")
        or ip.startswith("172.27.")
        or ip.startswith("172.28.")
        or ip.startswith("172.29.")
        or ip.startswith("172.30.")
        or ip.startswith("172.31.")
    ):
        return

    try:
        # Simple free service – fine for a personal portfolio
        resp = requests.get(f"https://ipapi.co/{ip}/json/", timeout=2)
        if resp.status_code == 200:
            data = resp.json()
            session.country = data.get("country_name", "") or ""
            session.region = (
                data.get("region", "")
                or data.get("region_name", "")
                or ""
            )
            session.city = data.get("city", "") or ""
            session.save(update_fields=["country", "region", "city"])
    except Exception:
        # Fail quietly – never break the page because of geo lookup
        pass


def _get_or_create_session(request):
    """
    Return an existing AnalyticsSession for this browser (by cookie),
    or create a new one. Respects the opt-out cookie.
    """

    # If this browser opted out, don't create or use a session
    if request.COOKIES.get("fx_analytics_optout") == "1":
        return None

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
        # NEW: enrich geo info on first creation
        _populate_geo(session)

    return session


@csrf_exempt  # this endpoint only accepts simple analytics JSON
def analytics_event(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)
    

    # 🔹 If this browser opted out, ignore the event
    if request.COOKIES.get("fx_analytics_optout") == "1":
        return JsonResponse({"ok": True, "ignored": True})

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

    event_qs = AnalyticsEvent.objects.filter(created_at__gte=since)
    session_qs = AnalyticsSession.objects.filter(created_at__gte=since)

    # Top pages by views
    page_views = (
        event_qs.filter(event_type="page_view")
        .values("page_path")
        .annotate(count=Count("id"))
        .order_by("-count")[:20]
    )

    # Top downloads
    downloads = (
        event_qs.filter(event_type="download")
        .values("metadata__filename")
        .annotate(count=Count("id"))
        .order_by("-count")[:20]
    )

    # Pages by average time on page
    slow_pages = (
        event_qs.filter(event_type="time_on_page")
        .annotate(seconds_value=Cast("metadata__seconds", FloatField()))
        .values("page_path")
        .annotate(avg_seconds=Avg("seconds_value"))
        .order_by("-avg_seconds")[:20]
    )

    # Pages by average scroll depth
    scroll_depth = (
        event_qs.filter(event_type="scroll_depth")
        .annotate(percent_value=Cast("metadata__percent", FloatField()))
        .values("page_path")
        .annotate(avg_percent=Avg("percent_value"))
        .order_by("-avg_percent")[:20]
    )

    # 🔹 Top referrers (how people arrived)
    top_referrers = (
        event_qs.filter(event_type="page_view")
        .exclude(referrer="")
        .values("referrer")
        .annotate(count=Count("id"))
        .order_by("-count")[:20]
    )

    # Project thumbnails (home cards)
    project_clicks = (
        event_qs.filter(event_type="project_click")
        .values("metadata__project_label")
        .annotate(clicks=Count("id"))
        .order_by("-clicks")[:20]
    )

    # CTA buttons (GitHub / Market / Forecast)
    cta_clicks = (
        event_qs.filter(event_type="cta_click")
        .values("metadata__label", "page_path")
        .annotate(clicks=Count("id"))
        .order_by("-clicks")[:20]
    )

    # 🔹 Geo aggregates
    top_countries = (
        session_qs.exclude(country="")
        .values("country")
        .annotate(count=Count("id"))
        .order_by("-count")[:20]
    )

    au_regions = (
        session_qs.filter(country="Australia")
        .exclude(region="")
        .values("region")
        .annotate(count=Count("id"))
        .order_by("-count")[:20]
    )

    au_cities = (
        session_qs.filter(country="Australia")
        .exclude(city="")
        .values("city")
        .annotate(count=Count("id"))
        .order_by("-count")[:20]
    )

    context = {
        "since": since,
        "page_views": page_views,
        "downloads": downloads,
        "slow_pages": slow_pages,
        "scroll_depth": scroll_depth,
        "top_referrers": top_referrers,
        "project_clicks": project_clicks,
        "cta_clicks": cta_clicks,
        "top_countries": top_countries,
        "au_regions": au_regions,
        "au_cities": au_cities,
    }
    return render(request, "ops/behaviour_console.html", context)




def analytics_optout(request):
    """
    Set a long-lived cookie so this browser is excluded from analytics.
    Visit /analytics/optout/ once on each of your devices.
    """
    response = HttpResponse(
        "Analytics tracking has been DISABLED for this browser. "
        "You can re-enable it at /analytics/optin/."
    )
    response.set_cookie(
        "fx_analytics_optout",
        "1",
        max_age=60 * 60 * 24 * 365 * 5,  # 5 years
        samesite="Lax",
    )
    return response




def analytics_optin(request):
    """
    Remove the opt-out cookie so this browser is tracked again.
    """
    response = HttpResponse(
        "Analytics tracking has been RE-ENABLED for this browser."
    )
    response.delete_cookie("fx_analytics_optout")
    return response
