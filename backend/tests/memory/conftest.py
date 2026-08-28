"""Memory Kernel test fixtures. Skip clearly when Bolt is unreachable."""

from __future__ import annotations

import pytest
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, AuthError

from app.core.settings import settings

FIXTURE_DOCUMENT_ID = "test-memory-fixture"


def _bolt_reachable() -> tuple[bool, str]:
    uri = settings.neo4j_uri
    try:
        driver = GraphDatabase.driver(
            uri,
            auth=(settings.neo4j_username, settings.neo4j_password),
        )
        try:
            driver.verify_connectivity()
        finally:
            driver.close()
        return True, ""
    except ServiceUnavailable as exc:
        return False, f"Neo4j {uri} is unreachable: {exc}"
    except AuthError as exc:
        return False, f"Neo4j auth failed for {uri}: {exc}"
    except Exception as exc:  # pragma: no cover - unexpected driver errors
        return False, f"Neo4j {uri} is unreachable: {exc}"


@pytest.fixture(scope="session")
def neo4j_driver():
    ok, reason = _bolt_reachable()
    if not ok:
        pytest.skip(reason)
    from app.arms.memory.graph_db import close_driver, get_driver

    driver = get_driver()
    yield driver
    close_driver()


@pytest.fixture
def fixture_document_id() -> str:
    return FIXTURE_DOCUMENT_ID


@pytest.fixture
def cleanup_fixture_document(neo4j_driver, fixture_document_id):
    yield fixture_document_id
    from app.arms.memory.graph_db import delete_document_cascade

    delete_document_cascade(fixture_document_id)
