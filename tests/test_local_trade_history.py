from core.local_trade_history import read_local_trade_history


def test_missing_archive_is_not_a_claim_of_no_trades(tmp_path):
    result = read_local_trade_history(path=tmp_path / 'missing.csv')
    assert result['history_available'] is False
    assert result['complete_history'] is False
    assert result['stats'] is None
    assert 'does not prove' in result['message']


def test_archive_is_bounded_and_legacy_values_are_not_aggregated(tmp_path):
    path = tmp_path / 'history.csv'
    path.write_text('Date,Ticker,P&L%\n2026-09-20,AAPL,2\n2026-09-21,NVDA,NaN\n')
    result = read_local_trade_history(limit=1, path=path)
    assert result['total'] == 1
    assert result['trades'][0]['ticker'] == 'NVDA'
    assert result['trades'][0]['pnl_pct'] is None
    assert result['stats'] is None
