from datetime import datetime
from app import app, db
from app import login
from werkzeug.security import generate_password_hash, check_password_hash #hash password library
from flask_login import UserMixin
from hashlib import md5
from time import time
import jwt

#associated model class/auxillary table
followers = db.Table('followers',
    db.Column('follower_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('followed_id', db.Integer, db.ForeignKey('user.id'))
)

# =============================================================================
# LIKES TABLE - Many-to-Many relationship between User and Post
# =============================================================================
#
# DATABASE RELATIONSHIPS EXPLAINED:
# ---------------------------------
# 1. ONE-TO-MANY: One User has many Posts (already exists via user_id foreign key)
#    User (1) ---> (*) Post
#
# 2. MANY-TO-MANY: Users can like many Posts, Posts can be liked by many Users
#    User (*) <---> (*) Post
#    This requires an "association table" (likes) to connect them.
#
# HOW IT WORKS:
# - User A likes Post 1 -> Insert row (user_id=A, post_id=1) into likes table
# - User A likes Post 2 -> Insert row (user_id=A, post_id=2) into likes table
# - User B likes Post 1 -> Insert row (user_id=B, post_id=1) into likes table
#
# The association table just stores pairs of IDs - no other data.
# =============================================================================
likes = db.Table('likes',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('post_id', db.Integer, db.ForeignKey('post.id'), primary_key=True)
)

#login user mixin class
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True)
    email = db.Column(db.String(120), index=True, unique=True)
    password_hash = db.Column(db.String(128))
    posts = db.relationship('Post', backref='author', lazy='dynamic')

    about_me = db.Column(db.String(140))
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)

    followed = db.relationship(
        'User', secondary=followers,
        primaryjoin=(followers.c.follower_id == id),
        secondaryjoin=(followers.c.followed_id == id),
        backref=db.backref('followers', lazy='dynamic'), lazy='dynamic')


    def follow(self, user):
        if not self.is_following(user):
            self.followed.append(user)

    def unfollow(self, user):
        if self.is_following(user):
            self.followed.remove(user)

    def is_following(self, user):
        return self.followed.filter(
            followers.c.followed_id == user.id).count() > 0

    def followed_posts(self):
        followed = Post.query.join(
            followers, (followers.c.followed_id == Post.user_id)).filter(
                followers.c.follower_id == self.id)
        own = Post.query.filter_by(user_id=self.id)
        return followed.union(own).order_by(Post.timestamp.desc())


    def __repr__(self):
        return '<User {}>'.format(self.username)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def avatar(self, size):
        digest = md5(self.email.lower().encode('utf-8')).hexdigest()
        return 'https://www.gravatar.com/avatar/{}?d=identicon&s={}'.format(
            digest, size)

    def get_reset_password_token(self, expires_in=600):
        return jwt.encode(
            {'reset_password': self.id, 'exp': time() + expires_in},
            app.config['SECRET_KEY'], algorithm='HS256')

    @staticmethod
    def verify_reset_password_token(token):
        try:
            id = jwt.decode(token, app.config['SECRET_KEY'],
                            algorithms=['HS256'])['reset_password']
        except:
            return
        return User.query.get(id)


@login.user_loader
def load_user(id):
    return User.query.get(int(id))





class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.String(140))
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    # ==========================================================================
    # LIKES RELATIONSHIP
    # ==========================================================================
    #
    # This creates a relationship between Post and User through the 'likes' table.
    #
    # PARAMETERS EXPLAINED:
    # - 'User': The model we're relating to
    # - secondary=likes: The association table connecting Post and User
    # - backref='liked_posts': Creates reverse access (user.liked_posts)
    # - lazy='dynamic': Returns a query object, not a list (for efficiency)
    #
    # USAGE:
    # - post.likers -> Query of users who liked this post
    # - post.likers.count() -> Number of likes
    # - user.liked_posts -> Query of posts this user liked
    # ==========================================================================
    likers = db.relationship(
        'User',
        secondary=likes,
        backref=db.backref('liked_posts', lazy='dynamic'),
        lazy='dynamic'
    )

    def like(self, user):
        """Add a like from the given user."""
        if not self.is_liked_by(user):
            self.likers.append(user)

    def unlike(self, user):
        """Remove a like from the given user."""
        if self.is_liked_by(user):
            self.likers.remove(user)

    def is_liked_by(self, user):
        """Check if this post is liked by the given user."""
        return self.likers.filter(likes.c.user_id == user.id).count() > 0

    def like_count(self):
        """Return the number of likes for this post."""
        return self.likers.count()

    def __repr__(self):
        return '<Post {}>'.format(self.body)
