"""Read the existing local CSV archive without implying a complete account ledger."""
import csv
import math
from collections import deque
from pathlib import Path


def read_local_trade_history(limit=200, path=None):
    archive = Path(path) if path else Path(__file__).resolve().parent.parent / 'data' / 'trade_log.csv'
    result = {'trades': [], 'total': 0, 'stats': None, 'source': 'local_csv',
              'history_available': archive.exists(), 'complete_history': False,
              'message': 'Local archive only. Older remote history is unavailable in JSON mode. Recorded percentages may use legacy exit accounting; no portfolio performance is inferred.'}
    if not archive.exists():
        result['message'] = 'No local trade archive is available on this instance. Older remote history is unavailable in JSON mode; this does not prove there were no past trades.'
        return result
    def number(value):
        try:
            parsed = float(value)
            return parsed if math.isfinite(parsed) else None
        except (ValueError, TypeError):
            return None
    with archive.open(newline='', encoding='utf-8-sig') as stream:
        reader = csv.DictReader(stream)
        if not {'Date', 'Ticker', 'P&L%'}.issubset(reader.fieldnames or []):
            raise ValueError('Local trade archive has unsupported columns')
        rows = deque(reader, maxlen=max(1, min(int(limit), 500)))
    for row in reversed(rows):
        result['trades'].append({'date_closed': row.get('Date'), 'ticker': row.get('Ticker'),
                                'pnl_pct': number(row.get('P&L%')), 'conviction': number(row.get('Conviction%')),
                                'exit_reason': row.get('Exit Reason'), 'regime': row.get('Regime')})
    result['total'] = len(result['trades'])
    return result
