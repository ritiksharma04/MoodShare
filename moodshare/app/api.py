"""
REST API MODULE
===============

REST API EXPLAINED:
-------------------
REST (Representational State Transfer) is an architectural style for APIs.

Key principles:
1. Resources are identified by URLs (/api/posts, /api/users/1)
2. HTTP methods define actions:
   - GET = Read data
   - POST = Create data
   - PUT/PATCH = Update data
   - DELETE = Remove data
3. Responses are typically JSON
4. Stateless - each request contains all info needed (via tokens)

WHY USE AN API?
- Mobile apps can consume it
- Single Page Applications (React, Vue) can use it
- Third-party integrations
- Separation of frontend and backend

TOKEN AUTHENTICATION:
---------------------
Instead of sessions (which need cookies), APIs use tokens.
1. Client sends username/password to /api/auth/login
2. Server returns a JWT token
3. Client includes token in all future requests: "Authorization: Bearer <token>"
4. Server validates token and identifies user

JWT (JSON Web Token):
- Self-contained: Contains user ID, expiration, etc.
- Signed: Can't be tampered with
- Stateless: Server doesn't need to store sessions
"""

from functools import wraps
from flask import Blueprint, jsonify, request, g
from app import db
from app.models import User, Post
import jwt
from datetime import datetime, timedelta
from config import Config

# Create a Blueprint for API routes
# Blueprints help organize Flask apps into modules
api = Blueprint('api', __name__, url_prefix='/api')


# =============================================================================
# AUTHENTICATION DECORATOR
# =============================================================================
#
# DECORATORS EXPLAINED:
# ---------------------
# A decorator wraps a function to add functionality.
# @token_required checks for valid JWT before running the route.
#
# Flow:
# 1. Get token from "Authorization: Bearer <token>" header
# 2. Decode and validate the JWT
# 3. Load the user from the token's user_id
# 4. Pass user to the route function via g.current_user
# =============================================================================

def token_required(f):
    """Decorator to require valid JWT token for API routes."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        # Check for Authorization header
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            # Expected format: "Bearer <token>"
            parts = auth_header.split()
            if len(parts) == 2 and parts[0] == 'Bearer':
                token = parts[1]

        if not token:
            return jsonify({
                'error': 'Missing token',
                'message': 'Authorization header with Bearer token is required'
            }), 401

        try:
            # Decode the JWT token
            payload = jwt.decode(token, Config.SECRET_KEY, algorithms=['HS256'])
            # Get user from database
            g.current_user = User.query.get(payload['user_id'])
            if g.current_user is None:
                return jsonify({'error': 'User not found'}), 401
        except jwt.ExpiredSignatureError:
            return jsonify({
                'error': 'Token expired',
                'message': 'Please login again to get a new token'
            }), 401
        except jwt.InvalidTokenError:
            return jsonify({
                'error': 'Invalid token',
                'message': 'The token is invalid'
            }), 401

        return f(*args, **kwargs)
    return decorated


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def user_to_dict(user):
    """Convert User object to dictionary for JSON response."""
    return {
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'about_me': user.about_me,
        'last_seen': user.last_seen.isoformat() if user.last_seen else None,
        'avatar': user.avatar(128),
        'post_count': user.posts.count(),
        'follower_count': user.followers.count(),
        'following_count': user.followed.count()
    }


def post_to_dict(post, current_user=None):
    """Convert Post object to dictionary for JSON response."""
    return {
        'id': post.id,
        'body': post.body,
        'timestamp': post.timestamp.isoformat(),
        'author': {
            'id': post.author.id,
            'username': post.author.username,
            'avatar': post.author.avatar(48)
        },
        'like_count': post.like_count(),
        'is_liked': post.is_liked_by(current_user) if current_user else False
    }


# =============================================================================
# AUTHENTICATION ROUTES
# =============================================================================

@api.route('/auth/login', methods=['POST'])
def api_login():
    """
    LOGIN AND GET TOKEN
    -------------------
    POST /api/auth/login
    Body: {"username": "test", "password": "password123"}
    Returns: {"token": "eyJ...", "user": {...}}

    The token is valid for 24 hours.
    """
    data = request.get_json()

    if not data:
        return jsonify({'error': 'Missing JSON body'}), 400

    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400

    user = User.query.filter_by(username=username).first()

    if user is None or not user.check_password(password):
        return jsonify({'error': 'Invalid username or password'}), 401

    # Generate JWT token
    token = jwt.encode({
        'user_id': user.id,
        'exp': datetime.utcnow() + timedelta(hours=24)
    }, Config.SECRET_KEY, algorithm='HS256')

    return jsonify({
        'token': token,
        'expires_in': 86400,  # 24 hours in seconds
        'user': user_to_dict(user)
    })


# =============================================================================
# POSTS ROUTES
# =============================================================================

@api.route('/posts', methods=['GET'])
@token_required
def get_posts():
    """
    GET ALL POSTS (paginated)
    -------------------------
    GET /api/posts?page=1&per_page=20

    Returns paginated list of all posts, newest first.
    """
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)  # Max 100

    posts = Post.query.order_by(Post.timestamp.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return jsonify({
        'posts': [post_to_dict(p, g.current_user) for p in posts.items],
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total_pages': posts.pages,
            'total_items': posts.total,
            'has_next': posts.has_next,
            'has_prev': posts.has_prev
        }
    })


@api.route('/posts', methods=['POST'])
@token_required
def create_post():
    """
    CREATE A NEW POST
    -----------------
    POST /api/posts
    Body: {"body": "Hello world!"}

    Creates a post for the authenticated user.
    """
    data = request.get_json()

    if not data or 'body' not in data:
        return jsonify({'error': 'Post body is required'}), 400

    body = data['body'].strip()

    if len(body) == 0:
        return jsonify({'error': 'Post body cannot be empty'}), 400

    if len(body) > 140:
        return jsonify({'error': 'Post body cannot exceed 140 characters'}), 400

    post = Post(body=body, author=g.current_user)
    db.session.add(post)
    db.session.commit()

    return jsonify({
        'message': 'Post created successfully',
        'post': post_to_dict(post, g.current_user)
    }), 201


@api.route('/posts/<int:post_id>', methods=['GET'])
@token_required
def get_post(post_id):
    """
    GET A SINGLE POST
    -----------------
    GET /api/posts/123

    Returns the post with the given ID.
    """
    post = Post.query.get_or_404(post_id)
    return jsonify({'post': post_to_dict(post, g.current_user)})


@api.route('/posts/<int:post_id>', methods=['DELETE'])
@token_required
def delete_post_api(post_id):
    """
    DELETE A POST
    -------------
    DELETE /api/posts/123

    Only the post author can delete their post.
    """
    post = Post.query.get_or_404(post_id)

    # Authorization check
    if post.author != g.current_user:
        return jsonify({'error': 'You can only delete your own posts'}), 403

    db.session.delete(post)
    db.session.commit()

    return jsonify({'message': 'Post deleted successfully'})


@api.route('/posts/<int:post_id>/like', methods=['POST'])
@token_required
def like_post_api(post_id):
    """
    LIKE A POST
    -----------
    POST /api/posts/123/like

    Adds a like from the authenticated user.
    """
    post = Post.query.get_or_404(post_id)

    if post.is_liked_by(g.current_user):
        return jsonify({'message': 'Already liked', 'like_count': post.like_count()})

    post.like(g.current_user)
    db.session.commit()

    return jsonify({
        'message': 'Post liked',
        'like_count': post.like_count()
    })


@api.route('/posts/<int:post_id>/like', methods=['DELETE'])
@token_required
def unlike_post_api(post_id):
    """
    UNLIKE A POST
    -------------
    DELETE /api/posts/123/like

    Removes a like from the authenticated user.
    """
    post = Post.query.get_or_404(post_id)

    if not post.is_liked_by(g.current_user):
        return jsonify({'message': 'Not liked', 'like_count': post.like_count()})

    post.unlike(g.current_user)
    db.session.commit()

    return jsonify({
        'message': 'Post unliked',
        'like_count': post.like_count()
    })


# =============================================================================
# USER ROUTES
# =============================================================================

@api.route('/users/<int:user_id>', methods=['GET'])
@token_required
def get_user(user_id):
    """
    GET USER PROFILE
    ----------------
    GET /api/users/123

    Returns the user's profile information.
    """
    user = User.query.get_or_404(user_id)
    return jsonify({'user': user_to_dict(user)})


@api.route('/users/<int:user_id>/posts', methods=['GET'])
@token_required
def get_user_posts(user_id):
    """
    GET USER'S POSTS
    ----------------
    GET /api/users/123/posts?page=1

    Returns paginated posts by the specified user.
    """
    user = User.query.get_or_404(user_id)
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)

    posts = user.posts.order_by(Post.timestamp.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return jsonify({
        'user': {'id': user.id, 'username': user.username},
        'posts': [post_to_dict(p, g.current_user) for p in posts.items],
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total_pages': posts.pages,
            'total_items': posts.total
        }
    })


@api.route('/me', methods=['GET'])
@token_required
def get_current_user():
    """
    GET CURRENT USER
    ----------------
    GET /api/me

    Returns the authenticated user's profile.
    """
    return jsonify({'user': user_to_dict(g.current_user)})


@api.route('/feed', methods=['GET'])
@token_required
def get_feed():
    """
    GET USER'S FEED
    ---------------
    GET /api/feed?page=1

    Returns posts from users the authenticated user follows.
    """
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)

    posts = g.current_user.followed_posts().paginate(
        page=page, per_page=per_page, error_out=False
    )

    return jsonify({
        'posts': [post_to_dict(p, g.current_user) for p in posts.items],
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total_pages': posts.pages,
            'total_items': posts.total
        }
    })
