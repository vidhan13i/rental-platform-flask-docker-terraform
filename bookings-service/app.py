from flask import Flask, jsonify, request, Response
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, jwt_required, get_jwt_identity
from datetime import datetime, date
import os
import requests

app = Flask(__name__)
CORS(app)

app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///bookings.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET', 'dev-secret')

db = SQLAlchemy(app)
jwt = JWTManager(app)

LISTINGS_SERVICE_URL = os.getenv('LISTINGS_SERVICE_URL', 'http://localhost:5002')
PAYMENTS_SERVICE_URL = os.getenv('PAYMENTS_SERVICE_URL', 'http://localhost:5004')


class Booking(db.Model):
    __tablename__ = 'bookings'

    id          = db.Column(db.Integer, primary_key=True)
    tenant_id   = db.Column(db.Integer, nullable=False)
    property_id = db.Column(db.Integer, nullable=False)
    check_in    = db.Column(db.Date, nullable=False)
    check_out   = db.Column(db.Date, nullable=False)
    guests      = db.Column(db.Integer, default=1)
    total_price = db.Column(db.Float, nullable=False)
    status      = db.Column(db.String(20), default='pending')
    payment_id  = db.Column(db.String(100))
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id':          self.id,
            'tenant_id':   self.tenant_id,
            'property_id': self.property_id,
            'check_in':    self.check_in.isoformat(),
            'check_out':   self.check_out.isoformat(),
            'guests':      self.guests,
            'total_price': self.total_price,
            'status':      self.status,
            'payment_id':  self.payment_id,
            'created_at':  self.created_at.isoformat(),
        }


def get_listing(property_id):
    try:
        resp = requests.get(f'{LISTINGS_SERVICE_URL}/listings/{property_id}', timeout=5)
        if resp.status_code == 200:
            return resp.json()
    except requests.exceptions.RequestException:
        pass
    return None


def has_date_conflict(property_id, check_in, check_out, exclude_id=None):
    query = Booking.query.filter(
        Booking.property_id == property_id,
        Booking.status != 'cancelled',
        Booking.check_in < check_out,
        Booking.check_out > check_in,
    )
    if exclude_id:
        query = query.filter(Booking.id != exclude_id)
    return query.first() is not None


@app.route('/bookings', methods=['POST'])
@jwt_required()
def create_booking():
    tenant_id = int(get_jwt_identity())
    data = request.get_json()

    for field in ['property_id', 'check_in', 'check_out', 'guests']:
        if field not in data:
            return jsonify({'error': f'{field} is required'}), 400

    try:
        check_in  = date.fromisoformat(data['check_in'])
        check_out = date.fromisoformat(data['check_out'])
    except ValueError:
        return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400

    if check_out <= check_in:
        return jsonify({'error': 'Check-out must be after check-in'}), 400

    listing = get_listing(data['property_id'])
    if not listing:
        return jsonify({'error': 'Property not found'}), 404

    if not listing['is_available']:
        return jsonify({'error': 'Property is not available'}), 409

    if has_date_conflict(data['property_id'], check_in, check_out):
        return jsonify({'error': 'Property already booked for these dates'}), 409

    nights      = (check_out - check_in).days
    total_price = nights * listing['price_per_night']

    booking = Booking(
        tenant_id=tenant_id,
        property_id=data['property_id'],
        check_in=check_in,
        check_out=check_out,
        guests=data['guests'],
        total_price=total_price,
        status='pending',
    )
    db.session.add(booking)
    db.session.commit()

    return jsonify({'message': 'Booking created. Proceed to payment.', 'booking': booking.to_dict()}), 201


@app.route('/bookings/<int:booking_id>/confirm', methods=['POST'])
@jwt_required()
def confirm_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    data = request.get_json()
    booking.status     = 'confirmed'
    booking.payment_id = data.get('payment_id')
    db.session.commit()
    return jsonify({'message': 'Booking confirmed!', 'booking': booking.to_dict()})


@app.route('/bookings/<int:booking_id>/cancel', methods=['POST'])
@jwt_required()
def cancel_booking(booking_id):
    tenant_id = int(get_jwt_identity())
    booking   = Booking.query.get_or_404(booking_id)

    if booking.tenant_id != tenant_id:
        return jsonify({'error': 'You can only cancel your own bookings'}), 403

    if booking.status == 'cancelled':
        return jsonify({'error': 'Booking is already cancelled'}), 400

    booking.status = 'cancelled'
    db.session.commit()
    return jsonify({'message': 'Booking cancelled', 'booking': booking.to_dict()})


@app.route('/bookings/my', methods=['GET'])
@jwt_required()
def my_bookings():
    tenant_id = int(get_jwt_identity())
    bookings  = Booking.query.filter_by(tenant_id=tenant_id).order_by(Booking.created_at.desc()).all()
    return jsonify({'bookings': [b.to_dict() for b in bookings]})


@app.route('/bookings/property/<int:property_id>', methods=['GET'])
@jwt_required()
def property_bookings(property_id):
    bookings = Booking.query.filter_by(property_id=property_id, status='confirmed').all()
    return jsonify({'bookings': [b.to_dict() for b in bookings]})


@app.route('/health')
def health():
    return jsonify({'service': 'bookings', 'status': 'healthy'})


with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5003, debug=True)
