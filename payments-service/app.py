
from flask import Flask, jsonify, request, Response
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, jwt_required, get_jwt_identity
from datetime import datetime
import os
import uuid
import requests

app = Flask(__name__)
CORS(app)

app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///payments.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET', 'dev-secret')

db = SQLAlchemy(app)
jwt = JWTManager(app)

BOOKINGS_SERVICE_URL = os.getenv('BOOKINGS_SERVICE_URL', 'http://localhost:5003')


class Payment(db.Model):
    __tablename__ = 'payments'

    id              = db.Column(db.String(100), primary_key=True, default=lambda: str(uuid.uuid4()))
    booking_id      = db.Column(db.Integer, nullable=False)
    tenant_id       = db.Column(db.Integer, nullable=False)
    amount          = db.Column(db.Float, nullable=False)
    currency        = db.Column(db.String(10), default='INR')
    method          = db.Column(db.String(50))
    status          = db.Column(db.String(20), default='pending')
    transaction_ref = db.Column(db.String(200))
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at      = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id':              self.id,
            'booking_id':      self.booking_id,
            'tenant_id':       self.tenant_id,
            'amount':          self.amount,
            'currency':        self.currency,
            'method':          self.method,
            'status':          self.status,
            'transaction_ref': self.transaction_ref,
            'created_at':      self.created_at.isoformat(),
        }


@app.route('/payments/initiate', methods=['POST'])
@jwt_required()
def initiate_payment():
    tenant_id = int(get_jwt_identity())
    data = request.get_json()

    for field in ['booking_id', 'amount', 'method']:
        if field not in data:
            return jsonify({'error': f'{field} is required'}), 400

    payment = Payment(
        booking_id=data['booking_id'],
        tenant_id=tenant_id,
        amount=data['amount'],
        method=data['method'],
        status='pending',
    )
    db.session.add(payment)
    db.session.commit()

    return jsonify({
        'payment_id': payment.id,
        'amount':     payment.amount,
        'currency':   payment.currency,
        'status':     'pending',
        'message':    'Payment initiated. Complete payment to confirm booking.'
    }), 201


@app.route('/payments/<payment_id>/complete', methods=['POST'])
@jwt_required()
def complete_payment(payment_id):
    payment = Payment.query.get_or_404(payment_id)
    data    = request.get_json()

    payment.status          = 'success'
    payment.transaction_ref = data.get('transaction_ref', f'TXN-{uuid.uuid4().hex[:8].upper()}')
    db.session.commit()

    try:
        token = request.headers.get('Authorization')
        requests.post(
            f'{BOOKINGS_SERVICE_URL}/bookings/{payment.booking_id}/confirm',
            json={'payment_id': payment.id},
            headers={'Authorization': token},
            timeout=5
        )
    except requests.exceptions.RequestException as e:
        print(f'Warning: Could not confirm booking {payment.booking_id}: {e}')

    return jsonify({'message': 'Payment successful! Booking confirmed.', 'payment': payment.to_dict()})


@app.route('/payments/<payment_id>/refund', methods=['POST'])
@jwt_required()
def refund_payment(payment_id):
    payment = Payment.query.get_or_404(payment_id)

    if payment.status != 'success':
        return jsonify({'error': 'Only successful payments can be refunded'}), 400

    payment.status = 'refunded'
    db.session.commit()
    return jsonify({'message': 'Refund initiated', 'payment': payment.to_dict()})


@app.route('/payments/my', methods=['GET'])
@jwt_required()
def my_payments():
    tenant_id = int(get_jwt_identity())
    payments  = Payment.query.filter_by(tenant_id=tenant_id).order_by(Payment.created_at.desc()).all()
    return jsonify({'payments': [p.to_dict() for p in payments]})


@app.route('/health')
def health():
    return jsonify({'service': 'payments', 'status': 'healthy'})


with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5004, debug=True)
