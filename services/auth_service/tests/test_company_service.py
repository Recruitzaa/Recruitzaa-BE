from services.auth_service.app.services.company_service import normalize_domain


def test_normalize_domain_accepts_full_url():
    assert normalize_domain("https://www.Example.com/about") == "example.com"


def test_normalize_domain_accepts_bare_domain():
    assert normalize_domain("jobs.example.com") == "jobs.example.com"


def test_normalize_domain_handles_missing_website():
    assert normalize_domain(None) is None
