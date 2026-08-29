from unittest.mock import MagicMock, patch

from ai_rfp_excel.frontend.api_client import APIClient
from ai_rfp_excel.frontend.components import (
    render_confidence_badge,
    render_metric_card,
    render_status_pill,
)


def test_components_status_pill() -> None:
    pill_comp = render_status_pill("COMPLIANT")
    assert "COMPLIANT" in pill_comp
    assert "status-pill-compliant" in pill_comp

    pill_non_comp = render_status_pill("NON_COMPLIANT")
    assert "NON-COMPLIANT" in pill_non_comp
    assert "status-pill-non-compliant" in pill_non_comp

    pill_amb = render_status_pill("AMBIGUOUS")
    assert "AMBIGUOUS" in pill_amb
    assert "status-pill-ambiguous" in pill_amb

    pill_nf = render_status_pill("NOT_FOUND")
    assert "NOT FOUND" in pill_nf
    assert "status-pill-missing" in pill_nf


def test_components_confidence_badge() -> None:
    badge_high = render_confidence_badge(0.95)
    assert "95%" in badge_high
    assert "High" in badge_high
    assert "#059669" in badge_high

    badge_med = render_confidence_badge(0.75)
    assert "75%" in badge_med
    assert "Medium" in badge_med
    assert "#d97706" in badge_med

    badge_low = render_confidence_badge(0.50)
    assert "50%" in badge_low
    assert "Low" in badge_low
    assert "#dc2626" in badge_low


def test_components_metric_card() -> None:
    card_html = render_metric_card(
        label="Compliance Score",
        value="98.5%",
        description="Across 42 specs",
        status="success",
    )
    assert "Compliance Score" in card_html
    assert "98.5%" in card_html
    assert "Across 42 specs" in card_html
    assert "border-left: 4px solid #059669" in card_html


def test_api_client_initialization_and_token() -> None:
    client = APIClient(base_url="http://localhost:8000")
    assert client.base_url == "http://localhost:8000"
    assert client.token is None
    assert client._get_headers() == {}

    client.set_token("test-jwt-token")
    assert client._get_headers() == {"Authorization": "Bearer test-jwt-token"}

    url = client.get_download_url("test_file.xlsx")
    assert url == "http://localhost:8000/excel/download/test_file.xlsx"


def test_api_client_login_success() -> None:
    client = APIClient(base_url="http://localhost:8000")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "access_token": "mock-token-xyz",
        "user": {"id": "u1", "username": "evaluator", "is_admin": False},
    }

    with patch("httpx.Client") as mock_client_cls:
        mock_instance = MagicMock()
        mock_instance.post.return_value = mock_resp
        mock_client_cls.return_value.__enter__.return_value = mock_instance

        success, res = client.login("evaluator", "password123")
        assert success is True
        assert isinstance(res, dict)
        assert res["access_token"] == "mock-token-xyz"
        assert client.token == "mock-token-xyz"


def test_api_client_login_failure() -> None:
    client = APIClient(base_url="http://localhost:8000")
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.json.return_value = {"detail": "Invalid credentials"}

    with patch("httpx.Client") as mock_client_cls:
        mock_instance = MagicMock()
        mock_instance.post.return_value = mock_resp
        mock_client_cls.return_value.__enter__.return_value = mock_instance

        success, res = client.login("wrong_user", "wrong_pass")
        assert success is False
        assert res == "Invalid credentials"


def test_api_client_get_me_success() -> None:
    client = APIClient(base_url="http://localhost:8000", token="valid-jwt-token")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "id": "user-123",
        "username": "admin",
        "email": "admin@example.com",
        "is_admin": True,
    }

    with patch("httpx.Client") as mock_client_cls:
        mock_instance = MagicMock()
        mock_instance.get.return_value = mock_resp
        mock_client_cls.return_value.__enter__.return_value = mock_instance

        user = client.get_me()
        assert user is not None
        assert user["username"] == "admin"
        assert user["is_admin"] is True
        mock_instance.get.assert_called_once_with(
            "http://localhost:8000/auth/me",
            headers={"Authorization": "Bearer valid-jwt-token"},
        )


def test_api_client_get_me_unauthorized() -> None:
    client = APIClient(base_url="http://localhost:8000", token="expired-token")

    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.json.return_value = {"detail": "Could not validate credentials"}

    with patch("httpx.Client") as mock_client_cls:
        mock_instance = MagicMock()
        mock_instance.get.return_value = mock_resp
        mock_client_cls.return_value.__enter__.return_value = mock_instance

        user = client.get_me()
        assert user is None


def test_api_client_get_me_no_token() -> None:
    client = APIClient(base_url="http://localhost:8000", token=None)
    assert client.get_me() is None


def test_api_client_list_runs() -> None:
    client = APIClient(base_url="http://localhost:8000", token="test-token")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = [
        {"run_id": "run-1", "status": "completed", "total_requirements": 10},
        {"run_id": "run-2", "status": "processing", "total_requirements": 5},
    ]

    with patch("httpx.Client") as mock_client_cls:
        mock_instance = MagicMock()
        mock_instance.get.return_value = mock_resp
        mock_client_cls.return_value.__enter__.return_value = mock_instance

        runs = client.list_runs(status_filter="Completed")
        assert len(runs) == 2
        assert runs[0]["run_id"] == "run-1"
        mock_instance.get.assert_called_once_with(
            "http://localhost:8000/runs",
            params={"status": "completed"},
            headers={"Authorization": "Bearer test-token"},
        )


def test_api_client_set_model_preference() -> None:
    client = APIClient(base_url="http://localhost:8000", token="test-token")
    mock_resp = MagicMock()
    mock_resp.status_code = 200

    with patch("httpx.Client") as mock_client_cls:
        mock_instance = MagicMock()
        mock_instance.put.return_value = mock_resp
        mock_client_cls.return_value.__enter__.return_value = mock_instance

        ok = client.set_model_preference("qwen3:4b")
        assert ok is True
        mock_instance.put.assert_called_once_with(
            "http://localhost:8000/ai/preference",
            json={"model_tag": "qwen3:4b"},
            headers={"Authorization": "Bearer test-token"},
        )


def test_views_modules_importable() -> None:
    from ai_rfp_excel.frontend.views.history import render_history
    from ai_rfp_excel.frontend.views.settings import render_settings
    from ai_rfp_excel.frontend.views.workspace import render_workspace

    assert callable(render_workspace)
    assert callable(render_history)
    assert callable(render_settings)
