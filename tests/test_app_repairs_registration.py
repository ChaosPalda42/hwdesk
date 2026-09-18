def test_repairs_blueprint_registered(app):
    # The Flask app should have the repairs routes mounted under /api/v1
    urls = [rule.rule for rule in app.url_map.iter_rules()]
    assert "/api/v1/assets/<int:asset_id>/repairs" in urls
    assert "/api/v1/repairs/<int:repair_id>/close" in urls
