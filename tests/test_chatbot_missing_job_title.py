import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.chatbot.tools as tools
from app.models import Base, Resource


@pytest.fixture
def sqlite_session(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    with Session() as session:
        session.add_all([
            Resource(emp_id=1, resource_name="Has Title", job_title="Engineer"),
            Resource(emp_id=2, resource_name="No Title", job_title=None),
            Resource(emp_id=3, resource_name="Blank Title", job_title="   "),
        ])
        session.commit()

    monkeypatch.setattr(tools, "get_session", lambda: Session())
    yield Session

    Base.metadata.drop_all(engine)


def test_search_resources_handles_missing_job_title_query(sqlite_session):
    result = tools.search_resources(query="resources without a job title")

    assert result["total_count"] == 2
    resource_names = {item["resource_name"] for item in result["resources"]}
    assert resource_names == {"No Title", "Blank Title"}
