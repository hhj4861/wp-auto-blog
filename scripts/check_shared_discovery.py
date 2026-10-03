"""One bounded discovery request; no publication, report write, or topic retry."""
import json
import os
import re
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.shared_discovery import discover
from src.shared_discovery_client import DiscoveryError

if __name__ == '__main__':
    try:
        accepted, result = discover(os.environ.get('DISCOVERY_CHECK_CATEGORY', '테크'))
        print(json.dumps({'requestId': result['requestId'], 'state': result['state'],
                          'acceptedCount': len(accepted), 'usage': result.get('usage'),
                          'requiresHumanReview': True}, ensure_ascii=False))
    except DiscoveryError as error:
        code = str(error)
        print(json.dumps({'error': code if re.fullmatch('[a-z_]{1,80}', code) else 'discovery_failed'}))
        raise SystemExit(1)
    except Exception:
        print('{"error":"shared_discovery_check_failed"}')
        raise SystemExit(1)
