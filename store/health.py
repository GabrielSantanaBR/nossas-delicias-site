from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def health_check(request):
    checks = {'app': 'ok', 'database': 'unknown', 'cache': 'unknown'}
    healthy = True

    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            if cursor.fetchone()[0] != 1:
                raise RuntimeError('Unexpected database health result.')
        checks['database'] = 'ok'
    except Exception:
        checks['database'] = 'error'
        healthy = False

    try:
        key = 'nd:healthcheck'
        cache.set(key, 'ok', timeout=10)
        if cache.get(key) != 'ok':
            raise RuntimeError('Unexpected cache health result.')
        checks['cache'] = 'ok'
    except Exception:
        checks['cache'] = 'error'
        healthy = False

    return JsonResponse({'status': 'ok' if healthy else 'degraded', 'checks': checks}, status=200 if healthy else 503)
