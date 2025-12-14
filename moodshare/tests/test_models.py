"""
MODEL TESTS
===========

UNIT TESTING EXPLAINED:
-----------------------
Unit tests check individual pieces of code in isolation.
For models, we test:
- Creating objects
- Methods work correctly
- Relationships work correctly
- Validation works correctly

NAMING CONVENTION:
------------------
- Test files: test_*.py or *_test.py
- Test functions: test_*
- Test classes: Test*

This naming lets pytest auto-discover tests.

RUNNING TESTS:
--------------
    pytest tests/test_models.py -v      # Run with verbose output
    pytest tests/test_models.py::test_password_hashing  # Run specific test
    pytest --cov=app tests/             # Run with coverage report
"""

import pytest
from app import db
from app.models import User, Post


class TestUserModel:
    """
    TEST USER MODEL
    ---------------
    Groups all User model tests together.
    """

    def test_password_hashing(self, test_app):
        """
        TEST: Password hashing works correctly.

        WHAT WE'RE TESTING:
        - set_password() hashes the password (doesn't store plain text)
        - check_password() returns True for correct password
        - check_password() returns False for wrong password

        WHY THIS MATTERS:
        - Security: Plain text passwords are a massive vulnerability
        - The hash should be different from the original password
        """
        user = User(username='testuser', email='test@example.com')
        user.set_password('mypassword')

        # Hash should NOT be the plain password
        assert user.password_hash != 'mypassword'

        # Correct password should verify
        assert user.check_password('mypassword') is True

        # Wrong password should not verify
        assert user.check_password('wrongpassword') is False

    def test_avatar_url(self, test_app):
        """
        TEST: Avatar URL generation works correctly.

        The avatar() method generates a Gravatar URL based on email.
        We're checking that:
        - It returns a valid URL
        - Different sizes work
        - The URL contains the expected domain
        """
        user = User(username='testuser', email='test@example.com')

        avatar_url = user.avatar(128)

        # Should be a Gravatar URL
        assert 'gravatar.com' in avatar_url
        # Should contain size parameter
        assert '128' in avatar_url

    def test_follow_unfollow(self, test_app, sample_user, sample_user2):
        """
        TEST: Follow/unfollow functionality works correctly.

        TESTING RELATIONSHIPS:
        This tests the many-to-many relationship between users.

        We verify:
        - Initial state: not following
        - After follow: is_following returns True
        - After unfollow: is_following returns False
        """
        # Initially not following
        assert sample_user.is_following(sample_user2) is False

        # Follow
        sample_user.follow(sample_user2)
        db.session.commit()
        assert sample_user.is_following(sample_user2) is True
        assert sample_user2.followers.count() == 1

        # Unfollow
        sample_user.unfollow(sample_user2)
        db.session.commit()
        assert sample_user.is_following(sample_user2) is False
        assert sample_user2.followers.count() == 0

    def test_follow_self_prevention(self, test_app, sample_user):
        """
        TEST: User cannot follow themselves.

        Note: This is checked in the route, not the model.
        The model allows it but the route prevents it.
        """
        # The model doesn't prevent this, but doesn't break either
        sample_user.follow(sample_user)
        db.session.commit()
        # User can technically follow themselves in model
        # (This should be prevented at the route level)

    def test_followed_posts(self, test_app, sample_user, sample_user2):
        """
        TEST: followed_posts() returns correct posts.

        This tests the complex query that:
        1. Gets posts from users we follow
        2. Includes our own posts
        3. Orders by timestamp (newest first)
        """
        # Create posts
        post1 = Post(body='Post from user 1', author=sample_user)
        post2 = Post(body='Post from user 2', author=sample_user2)
        db.session.add_all([post1, post2])
        db.session.commit()

        # Initially, user1 only sees their own posts
        followed_posts = sample_user.followed_posts().all()
        assert len(followed_posts) == 1
        assert followed_posts[0].body == 'Post from user 1'

        # After following user2, user1 sees both posts
        sample_user.follow(sample_user2)
        db.session.commit()
        followed_posts = sample_user.followed_posts().all()
        assert len(followed_posts) == 2


class TestPostModel:
    """
    TEST POST MODEL
    ---------------
    Tests for the Post model and its methods.
    """

    def test_post_creation(self, test_app, sample_user):
        """
        TEST: Post can be created with body and author.
        """
        post = Post(body='Test post content', author=sample_user)
        db.session.add(post)
        db.session.commit()

        assert post.id is not None
        assert post.body == 'Test post content'
        assert post.author == sample_user
        assert post.timestamp is not None

    def test_post_like_unlike(self, test_app, sample_user, sample_user2, sample_post):
        """
        TEST: Like/unlike functionality works correctly.

        Tests the many-to-many relationship between User and Post.
        """
        # Initially no likes
        assert sample_post.like_count() == 0
        assert sample_post.is_liked_by(sample_user) is False
        assert sample_post.is_liked_by(sample_user2) is False

        # User2 likes the post
        sample_post.like(sample_user2)
        db.session.commit()
        assert sample_post.like_count() == 1
        assert sample_post.is_liked_by(sample_user2) is True

        # User2 unlikes the post
        sample_post.unlike(sample_user2)
        db.session.commit()
        assert sample_post.like_count() == 0
        assert sample_post.is_liked_by(sample_user2) is False

    def test_like_idempotent(self, test_app, sample_user2, sample_post):
        """
        TEST: Liking twice doesn't create duplicate likes.

        IDEMPOTENT means: doing something twice has the same effect as once.
        This prevents database errors from double-clicks.
        """
        sample_post.like(sample_user2)
        sample_post.like(sample_user2)  # Like again
        db.session.commit()

        # Should still be just 1 like
        assert sample_post.like_count() == 1

    def test_unlike_when_not_liked(self, test_app, sample_user2, sample_post):
        """
        TEST: Unliking when not liked doesn't cause errors.
        """
        # Should not raise an error
        sample_post.unlike(sample_user2)
        db.session.commit()
        assert sample_post.like_count() == 0


class TestPasswordResetToken:
    """
    TEST PASSWORD RESET TOKENS
    --------------------------
    Tests for JWT token generation and verification.
    """

    def test_valid_token(self, test_app, sample_user):
        """
        TEST: Valid token can be verified.
        """
        token = sample_user.get_reset_password_token()
        verified_user = User.verify_reset_password_token(token)

        assert verified_user is not None
        assert verified_user.id == sample_user.id

    def test_invalid_token(self, test_app):
        """
        TEST: Invalid token returns None.
        """
        verified_user = User.verify_reset_password_token('invalid-token')
        assert verified_user is None
