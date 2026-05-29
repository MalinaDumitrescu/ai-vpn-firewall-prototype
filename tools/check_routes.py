import urllib.request, json, sys
for port in [8000, 8765]:
    try:
        r = urllib.request.urlopen(f'http://127.0.0.1:{port}/openapi.json', timeout=3)
        d = json.loads(r.read())
        paths = sorted(d['paths'].keys())
        bench = [p for p in paths if 'benchmark' in p]
        print(f"\nPort {port}: {len(paths)} routes, benchmark routes: {bench}")
    except Exception as e:
        print(f"\nPort {port}: ERROR {e}")

