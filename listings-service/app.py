from flask import Flask, jsonify, request, Response
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, jwt_required, get_jwt_identity
import os
import requests

app = Flask(__name__)
CORS(app)

app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///listings.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET', 'dev-secret')

db = SQLAlchemy(app)
jwt = JWTManager(app)

USERS_SERVICE_URL = os.getenv('USERS_SERVICE_URL', 'http://localhost:5001')


class Property(db.Model):
    __tablename__ = 'properties'

    id              = db.Column(db.Integer, primary_key=True)
    landlord_id     = db.Column(db.Integer, nullable=False)
    title           = db.Column(db.String(200), nullable=False)
    description     = db.Column(db.Text)
    address         = db.Column(db.String(300), nullable=False)
    city            = db.Column(db.String(100), nullable=False)
    state           = db.Column(db.String(100), nullable=False)
    country         = db.Column(db.String(100), default='India')
    price_per_night = db.Column(db.Float, nullable=False)
    bedrooms        = db.Column(db.Integer, default=1)
    bathrooms       = db.Column(db.Integer, default=1)
    max_guests      = db.Column(db.Integer, default=2)
    amenities       = db.Column(db.Text)
    images          = db.Column(db.Text)
    is_available    = db.Column(db.Boolean, default=True)

    def to_dict(self):
        return {
            'id':              self.id,
            'landlord_id':     self.landlord_id,
            'title':           self.title,
            'description':     self.description,
            'address':         self.address,
            'city':            self.city,
            'state':           self.state,
            'country':         self.country,
            'price_per_night': self.price_per_night,
            'bedrooms':        self.bedrooms,
            'bathrooms':       self.bathrooms,
            'max_guests':      self.max_guests,
            'amenities':       self.amenities.split(',') if self.amenities else [],
            'images':          self.images.split(',') if self.images else [],
            'is_available':    self.is_available,
        }


@app.route('/listings', methods=['GET'])
def get_listings():
    query = Property.query.filter_by(is_available=True)

    city = request.args.get('city')
    if city:
        query = query.filter(Property.city.ilike(f'%{city}%'))

    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)
    if min_price:
        query = query.filter(Property.price_per_night >= min_price)
    if max_price:
        query = query.filter(Property.price_per_night <= max_price)

    bedrooms = request.args.get('bedrooms', type=int)
    if bedrooms:
        query = query.filter(Property.bedrooms >= bedrooms)

    return jsonify({'listings': [p.to_dict() for p in query.all()]})


@app.route('/listings/<int:property_id>', methods=['GET'])
def get_listing(property_id):
    return jsonify(Property.query.get_or_404(property_id).to_dict())


@app.route('/listings', methods=['POST'])
@jwt_required()
def create_listing():
    landlord_id = get_jwt_identity()
    data = request.get_json()

    for field in ['title', 'address', 'city', 'state', 'price_per_night']:
        if field not in data:
            return jsonify({'error': f'{field} is required'}), 400

    prop = Property(
        landlord_id=landlord_id,
        title=data['title'],
        description=data.get('description', ''),
        address=data['address'],
        city=data['city'],
        state=data['state'],
        country=data.get('country', 'India'),
        price_per_night=data['price_per_night'],
        bedrooms=data.get('bedrooms', 1),
        bathrooms=data.get('bathrooms', 1),
        max_guests=data.get('max_guests', 2),
        amenities=','.join(data.get('amenities', [])),
        images=','.join(data.get('images', [])),
    )
    db.session.add(prop)
    db.session.commit()

    return jsonify({'message': 'Property listed successfully', 'listing': prop.to_dict()}), 201


@app.route('/listings/<int:property_id>', methods=['PUT'])
@jwt_required()
def update_listing(property_id):
    landlord_id = int(get_jwt_identity())
    prop = Property.query.get_or_404(property_id)

    if prop.landlord_id != landlord_id:
        return jsonify({'error': 'You can only edit your own listings'}), 403

    data = request.get_json()
    prop.title           = data.get('title',           prop.title)
    prop.description     = data.get('description',     prop.description)
    prop.price_per_night = data.get('price_per_night', prop.price_per_night)
    prop.is_available    = data.get('is_available',    prop.is_available)
    prop.bedrooms        = data.get('bedrooms',        prop.bedrooms)
    prop.bathrooms       = data.get('bathrooms',       prop.bathrooms)
    if 'amenities' in data:
        prop.amenities = ','.join(data['amenities'])

    db.session.commit()
    return jsonify(prop.to_dict())


@app.route('/listings/<int:property_id>', methods=['DELETE'])
@jwt_required()
def delete_listing(property_id):
    landlord_id = int(get_jwt_identity())
    prop = Property.query.get_or_404(property_id)

    if prop.landlord_id != landlord_id:
        return jsonify({'error': 'You can only delete your own listings'}), 403

    db.session.delete(prop)
    db.session.commit()
    return jsonify({'message': 'Listing deleted'})


@app.route('/listings/<int:property_id>/availability', methods=['PATCH'])
def toggle_availability(property_id):
    prop = Property.query.get_or_404(property_id)
    data = request.get_json()
    prop.is_available = data.get('is_available', prop.is_available)
    db.session.commit()
    return jsonify({'is_available': prop.is_available})


@app.route('/health')
def health():
    return jsonify({'service': 'listings', 'status': 'healthy'})


with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002, debug=True)
