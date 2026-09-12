"""Test-only fixtures, excluded from production packages.

``policy`` and ``generator`` served the original main loop (AgentLoop). That
loop is now fixture-only: production runs use the official EoH adapter in
``eoh_frozen``. Nothing here may be used as a production search policy or a
production prompt source. Fixture identity is always marked ``fixture_only``
so it can never share defaults with production skill metadata.
"""
