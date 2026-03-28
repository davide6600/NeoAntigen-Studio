import pytest
from unittest.mock import patch, MagicMock
from agent.data.ensembl_lookup import lookup_variant_gene

@pytest.fixture
def mock_cache_dir(tmp_path):
    with patch("agent.data.ensembl_lookup.CACHE_DIR", tmp_path):
        yield tmp_path

@patch("agent.data.ensembl_lookup.requests.get")
def test_lookup_variant_gene_success(mock_get, mock_cache_dir):
    mock_resp = MagicMock()
    mock_resp.json.return_value = [
        {"external_name": "BRAF"}
    ]
    mock_get.return_value = mock_resp
    
    gene = lookup_variant_gene("chr7", 140453136, "A", "T")
    assert gene == "BRAF"
    
    # Check cache hit
    gene2 = lookup_variant_gene("chr7", 140453136, "A", "T")
    assert gene2 == "BRAF"
    assert mock_get.call_count == 1  # Not called again

@patch("agent.data.ensembl_lookup.requests.get")
def test_lookup_variant_gene_empty(mock_get, mock_cache_dir):
    mock_resp = MagicMock()
    mock_resp.json.return_value = []
    mock_get.return_value = mock_resp
    
    gene = lookup_variant_gene("chr99", 1000, "A", "T")
    assert gene == "UNKNOWN"

@patch("agent.data.ensembl_lookup.requests.get")
def test_lookup_variant_gene_error(mock_get, mock_cache_dir):
    mock_get.side_effect = Exception("Network Error")
    
    gene = lookup_variant_gene("chr1", 100, "A", "T")
    assert gene == "UNKNOWN"
