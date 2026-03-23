from flask import Flask, jsonify, request, Response
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import timedelta
import os

app = Flask(__name__)
CORS(app)

app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///users.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET', 'dev-secret')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=24)

db = SQLAlchemy(app)
jwt = JWTManager(app)


class User(db.Model):
    __tablename__ = 'users'

    id         = db.Column(db.Integer, primary_key=True)
    email      = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(80), nullable=False)
    last_name  = db.Column(db.String(80), nullable=False)
    phone      = db.Column(db.String(20))
    role       = db.Column(db.String(20), default='tenant')
    is_active  = db.Column(db.Boolean, default=True)

    def to_dict(self):
        return {
            'id':         self.id,
            'email':      self.email,
            'first_name': self.first_name,
            'last_name':  self.last_name,
            'phone':      self.phone,
            'role':       self.role,
        }


@app.route('/users/register', methods=['POST'])
def register():
    data = request.get_json()

    for field in ['email', 'password', 'first_name', 'last_name', 'role']:
        if field not in data:
            return jsonify({'error': f'{field} is required'}), 400

    if User.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Email already registered'}), 409

    user = User(
        email=data['email'],
        password_hash=generate_password_hash(data['password']),
        first_name=data['first_name'],
        last_name=data['last_name'],
        phone=data.get('phone'),
        role=data.get('role', 'tenant'),
    )
    db.session.add(user)
    db.session.commit()

    return jsonify({'message': 'Registered successfully', 'user': user.to_dict()}), 201


@app.route('/users/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(email=data.get('email')).first()

    if not user or not check_password_hash(user.password_hash, data.get('password', '')):
        return jsonify({'error': 'Invalid email or password'}), 401

    token = create_access_token(identity=str(user.id))
    return jsonify({'token': token, 'user': user.to_dict()})


@app.route('/users/profile', methods=['GET'])
@jwt_required()
def get_profile():
    user = User.query.get(get_jwt_identity())
    if not user:
        return jsonify({'error': 'User not found'}), 404
    return jsonify(user.to_dict())


@app.route('/users/profile', methods=['PUT'])
@jwt_required()
def update_profile():
    user = User.query.get(get_jwt_identity())
    if not user:
        return jsonify({'error': 'User not found'}), 404

    data = request.get_json()
    user.first_name = data.get('first_name', user.first_name)
    user.last_name  = data.get('last_name',  user.last_name)
    user.phone      = data.get('phone',      user.phone)
    db.session.commit()

    return jsonify(user.to_dict())


@app.route('/users/validate', methods=['GET'])
@jwt_required()
def validate_token():
    user = User.query.get(get_jwt_identity())
    if not user:
        return jsonify({'valid': False}), 401
    return jsonify({'valid': True, 'user': user.to_dict()})


@app.route('/health')
def health():
    return jsonify({'service': 'users', 'status': 'healthy'})


with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
