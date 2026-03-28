import json
import pytest
from unittest.mock import patch, MagicMock
from agent.data.iedb_loader import fetch_mhc_binding_data, build_sklearn_model_from_iedb

@pytest.fixture
def mock_cache_dir(tmp_path):
    with patch("agent.data.iedb_loader.CACHE_DIR", tmp_path):
        yield tmp_path

@patch("agent.data.iedb_loader.requests.get")
def test_fetch_mhc_binding_data_primary(mock_get, mock_cache_dir):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "data": [
            {
                "linear_peptide_seq": "SIINFEKL",
                "measurement_value": "10.5",
                "qualitative_measure": "Positive"
            }
        ]
    }
    mock_get.return_value = mock_resp
    
    results = fetch_mhc_binding_data(max_results=1, use_cache=False)
    
    assert len(results) == 1
    assert results[0]["peptide_sequence"] == "SIINFEKL"
    assert results[0]["is_strong_binder"] is True
    assert results[0]["is_binder"] is True
    
    # test cache creation
    results_cache = fetch_mhc_binding_data(max_results=1, use_cache=True)
    assert len(list(mock_cache_dir.glob("*.json"))) == 1

@patch("agent.data.iedb_loader.requests.get")
@patch("agent.data.iedb_loader.requests.post")
def test_fetch_mhc_binding_data_legacy_fallback(mock_post, mock_get, mock_cache_dir):
    # Primary fails
    mock_get.side_effect = Exception("Connection Error")
    
    # Legacy succeeds
    mock_resp = MagicMock()
    mock_resp.headers = {"Content-Type": "application/json"}
    mock_resp.json.return_value = {
        "data": [
            {
                "linear_peptide_seq": "NLVPMVATV",
                "measurement_value": "400.0",
                "qualitative_measure": "Positive-Low"
            }
        ]
    }
    mock_post.return_value = mock_resp
    
    results = fetch_mhc_binding_data(use_cache=False)
    assert len(results) == 1
    assert results[0]["peptide_sequence"] == "NLVPMVATV"
    assert results[0]["is_binder"] is True
    assert results[0]["is_strong_binder"] is False

@patch("agent.data.iedb_loader.requests.get")
@patch("agent.data.iedb_loader.requests.post")
def test_fetch_mhc_binding_data_offline_fallback(mock_post, mock_get, mock_cache_dir):
    mock_get.side_effect = Exception("Offline")
    mock_post.side_effect = Exception("Offline")
    
    results = fetch_mhc_binding_data(use_cache=False)
    assert results == []

@patch("agent.data.iedb_loader.fetch_mhc_binding_data")
@patch("joblib.dump")
def test_build_sklearn_model_from_iedb(mock_dump, mock_fetch, mock_cache_dir, tmp_path):
    mock_fetch.return_value = [
        {"peptide_sequence": "SIINFEKL", "is_binder": True},
            {"peptide_sequence": "NLVPMVATV", "is_binder": True},
            {"peptide_sequence": "GGGGGGGGG", "is_binder": False},
            {"peptide_sequence": "AAAAAAAAA", "is_binder": False},
            {"peptide_sequence": "LLLLLLLLL", "is_binder": True},
            {"peptide_sequence": "QQQQQQQQQ", "is_binder": False},
            {"peptide_sequence": "RRRRRRRRR", "is_binder": False},
            {"peptide_sequence": "DDDDDDDDD", "is_binder": False},
        {"peptide_sequence": "TTTTTTTTT", "is_binder": False},
        {"peptide_sequence": "YYYYYYYYY", "is_binder": False},
    ]
    
    res = build_sklearn_model_from_iedb(["HLA-A*02:01"])
    
    assert res["n_samples"] >= 10
    assert "clf" in res
    assert res["accuracy"] >= 0.0
