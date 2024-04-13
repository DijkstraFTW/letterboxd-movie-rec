import pytest
from airflow.models import DagBag

@pytest.fixture(scope="session")
def dag_bag():
    dag_folder = "../dags"
    return DagBag(dag_folder=dag_folder, include_examples=False)

def test_no_import_errors(dag_bag):
    """Ensure there are no DAG import failures."""
    assert not dag_bag.import_errors, f"DAG import failures: {dag_bag.import_errors}"

def test_three_or_less_retries(dag_bag):
    """Ensure that all DAGs have three or fewer retries."""
    for dag_id, dag in dag_bag.dags.items():
        retries = dag.default_args.get("retries", 0)
        assert retries <= 3, f"DAG {dag_id} has too many retries: {retries}"

def test_desc_len_greater_than_fifteen(dag_bag):
    """Ensure that all DAGs have descriptions longer than 15 characters."""
    for dag_id, dag in dag_bag.dags.items():
        assert len(dag.description) > 15

def test_owner_len_greater_than_five(dag_bag):
    """Ensure that all DAGs have owners longer than 5 characters."""
    for dag_id, dag in dag_bag.dags.items():
        assert len(dag.owner) > 5

def test_owner_not_airflow(dag_bag):
    """Ensure that no DAGs are owned by 'airflow'."""
    for dag_id, dag in dag_bag.dags.items():
        assert str.lower(dag.owner) != "airflow"
