from flask import Flask, jsonify, request, Response
from flask_cors import CORS
import requests
import os

app = Flask(__name__)
CORS(app)

SERVICES = {
    'users':    os.getenv('USERS_SERVICE_URL',    'http://users-service:5001'),
    'listings': os.getenv('LISTINGS_SERVICE_URL', 'http://listings-service:5002'),
    'bookings': os.getenv('BOOKINGS_SERVICE_URL', 'http://bookings-service:5003'),
    'payments': os.getenv('PAYMENTS_SERVICE_URL', 'http://payments-service:5004'),
    'reviews':  os.getenv('REVIEWS_SERVICE_URL',  'http://reviews-service:5005'),
}


def proxy(service_name, path):
    service_url = SERVICES.get(service_name)
    if not service_url:
        return jsonify({'error': 'Service not found'}), 404

    target_url = f'{service_url}{path}'
    if request.query_string:
        target_url += f'?{request.query_string.decode()}'

    headers = {key: value for key, value in request.headers if key != 'Host'}

    try:
        resp = requests.request(
            method=request.method,
            url=target_url,
            headers=headers,
            json=request.get_json(silent=True),
            timeout=10,
        )
        return Response(resp.content, status=resp.status_code, content_type=resp.headers.get('Content-Type'))

    except requests.exceptions.ConnectionError:
        return jsonify({'error': f'{service_name} service is unavailable'}), 503
    except requests.exceptions.Timeout:
        return jsonify({'error': f'{service_name} service timed out'}), 504


@app.route('/users/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
def users_routes(path):
    return proxy('users', f'/users/{path}')

@app.route('/listings', methods=['GET', 'POST'])
@app.route('/listings/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
def listings_routes(path=''):
    return proxy('listings', f'/listings/{path}' if path else '/listings')

@app.route('/bookings', methods=['GET', 'POST'])
@app.route('/bookings/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
def bookings_routes(path=''):
    return proxy('bookings', f'/bookings/{path}' if path else '/bookings')

@app.route('/payments', methods=['GET', 'POST'])
@app.route('/payments/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
def payments_routes(path=''):
    return proxy('payments', f'/payments/{path}' if path else '/payments')

@app.route('/reviews', methods=['GET', 'POST'])
@app.route('/reviews/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
def reviews_routes(path=''):
    return proxy('reviews', f'/reviews/{path}' if path else '/reviews')


@app.route('/health')
def health():
    results = {}
    for name, url in SERVICES.items():
        try:
            resp = requests.get(f'{url}/health', timeout=3)
            results[name] = 'healthy' if resp.status_code == 200 else 'unhealthy'
        except Exception:
            results[name] = 'unreachable'
    overall = 'healthy' if all(v == 'healthy' for v in results.values()) else 'degraded'
    return jsonify({'gateway': 'healthy', 'services': results, 'overall': overall})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
