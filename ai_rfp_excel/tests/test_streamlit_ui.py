from ai_rfp_excel.frontend.api_client import APIClient
from ai_rfp_excel.frontend.components import (
    render_confidence_badge,
    render_status_pill,
)


def test_components_status_pill() -> None:
    pill_comp = render_status_pill("COMPLIANT")
    assert "COMPLIANT" in pill_comp
    assert "#e2f0d9" in pill_comp

    pill_non_comp = render_status_pill("NON_COMPLIANT")
    assert "NON-COMPLIANT" in pill_non_comp
    assert "#fce4d6" in pill_non_comp

    pill_amb = render_status_pill("AMBIGUOUS")
    assert "AMBIGUOUS" in pill_amb
    assert "#fff2cc" in pill_amb

    pill_nf = render_status_pill("NOT_FOUND")
    assert "NOT FOUND" in pill_nf
    assert "#f2f2f2" in pill_nf


def test_components_confidence_badge() -> None:
    badge_high = render_confidence_badge(0.95)
    assert "95%" in badge_high
    assert "High" in badge_high
    assert "#28a745" in badge_high

    badge_med = render_confidence_badge(0.75)
    assert "75%" in badge_med
    assert "Medium" in badge_med
    assert "#fd7e14" in badge_med

    badge_low = render_confidence_badge(0.50)
    assert "50%" in badge_low
    assert "Low" in badge_low
    assert "#dc3545" in badge_low


def test_api_client_initialization_and_token() -> None:
    client = APIClient(base_url="http://localhost:8000")
    assert client.base_url == "http://localhost:8000"
    assert client.token is None
    assert client._get_headers() == {}

    client.set_token("test-jwt-token")
    assert client._get_headers() == {"Authorization": "Bearer test-jwt-token"}

    url = client.get_download_url("test_file.xlsx")
    assert url == "http://localhost:8000/excel/download/test_file.xlsx"
