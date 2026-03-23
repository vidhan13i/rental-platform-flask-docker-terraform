from flask import Flask, jsonify, request, Response
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, jwt_required, get_jwt_identity
from datetime import datetime
import os

app = Flask(__name__)
CORS(app)

app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///reviews.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET', 'dev-secret')

db = SQLAlchemy(app)
jwt = JWTManager(app)


class Review(db.Model):
    __tablename__ = 'reviews'

    id          = db.Column(db.Integer, primary_key=True)
    property_id = db.Column(db.Integer, nullable=False)
    tenant_id   = db.Column(db.Integer, nullable=False)
    booking_id  = db.Column(db.Integer, nullable=False, unique=True)
    rating      = db.Column(db.Integer, nullable=False)
    comment     = db.Column(db.Text)
    cleanliness = db.Column(db.Integer)
    location    = db.Column(db.Integer)
    value       = db.Column(db.Integer)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id':          self.id,
            'property_id': self.property_id,
            'tenant_id':   self.tenant_id,
            'booking_id':  self.booking_id,
            'rating':      self.rating,
            'comment':     self.comment,
            'sub_ratings': {
                'cleanliness': self.cleanliness,
                'location':    self.location,
                'value':       self.value,
            },
            'created_at': self.created_at.isoformat(),
        }


@app.route('/reviews/property/<int:property_id>', methods=['GET'])
def get_property_reviews(property_id):
    reviews    = Review.query.filter_by(property_id=property_id).order_by(Review.created_at.desc()).all()
    avg_rating = round(sum(r.rating for r in reviews) / len(reviews), 1) if reviews else 0

    return jsonify({
        'property_id':    property_id,
        'total_reviews':  len(reviews),
        'average_rating': avg_rating,
        'reviews':        [r.to_dict() for r in reviews],
    })


@app.route('/reviews', methods=['POST'])
@jwt_required()
def create_review():
    tenant_id = int(get_jwt_identity())
    data      = request.get_json()

    for field in ['property_id', 'booking_id', 'rating']:
        if field not in data:
            return jsonify({'error': f'{field} is required'}), 400

    if not 1 <= data['rating'] <= 5:
        return jsonify({'error': 'Rating must be between 1 and 5'}), 400

    if Review.query.filter_by(booking_id=data['booking_id']).first():
        return jsonify({'error': 'You already reviewed this booking'}), 409

    review = Review(
        property_id=data['property_id'],
        tenant_id=tenant_id,
        booking_id=data['booking_id'],
        rating=data['rating'],
        comment=data.get('comment'),
        cleanliness=data.get('cleanliness'),
        location=data.get('location'),
        value=data.get('value'),
    )
    db.session.add(review)
    db.session.commit()

    return jsonify({'message': 'Review submitted!', 'review': review.to_dict()}), 201


@app.route('/reviews/<int:review_id>', methods=['DELETE'])
@jwt_required()
def delete_review(review_id):
    tenant_id = int(get_jwt_identity())
    review    = Review.query.get_or_404(review_id)

    if review.tenant_id != tenant_id:
        return jsonify({'error': 'You can only delete your own reviews'}), 403

    db.session.delete(review)
    db.session.commit()
    return jsonify({'message': 'Review deleted'})


@app.route('/health')
def health():
    return jsonify({'service': 'reviews', 'status': 'healthy'})


with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5005, debug=True)
