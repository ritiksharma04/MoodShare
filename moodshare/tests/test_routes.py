"""
ROUTE TESTS (Integration Tests)
===============================

INTEGRATION TESTING EXPLAINED:
------------------------------
Integration tests check that multiple components work together.
For routes, we test:
- HTTP response codes (200, 302, 404, etc.)
- Page content (does it contain expected text?)
- Form submissions (does login work?)
- Authentication/authorization (are protected routes protected?)

HTTP STATUS CODES REFERENCE:
----------------------------
- 200 = OK
- 302 = Redirect (e.g., after form submission)
- 400 = Bad Request
- 401 = Unauthorized
- 403 = Forbidden
- 404 = Not Found
- 500 = Internal Server Error

TESTING FORMS:
--------------
    response = client.post('/login', data={
        'username': 'test',
        'password': 'test'
    }, follow_redirects=True)

The 'follow_redirects=True' makes the client follow 302 redirects,
so you can check the final page content.
"""

import pytest
from app import db
from app.models import User, Post


class TestPublicRoutes:
    """
    TEST PUBLIC ROUTES
    ------------------
    Routes that don't require authentication.
    """

    def test_login_page_loads(self, client):
        """
        TEST: Login page is accessible.
        """
        response = client.get('/login')
        assert response.status_code == 200
        assert b'Sign In' in response.data or b'Welcome back' in response.data

    def test_register_page_loads(self, client):
        """
        TEST: Register page is accessible.
        """
        response = client.get('/register')
        assert response.status_code == 200
        assert b'Create account' in response.data or b'Register' in response.data

    def test_reset_password_request_page_loads(self, client):
        """
        TEST: Password reset request page is accessible.
        """
        response = client.get('/reset_password_request')
        assert response.status_code == 200


class TestAuthentication:
    """
    TEST AUTHENTICATION
    -------------------
    Login, logout, and registration.
    """

    def test_successful_login(self, client, sample_user):
        """
        TEST: User can log in with correct credentials.

        WHAT WE'RE TESTING:
        1. POST to /login with valid credentials
        2. Should redirect (302) to index
        3. After redirect, should see welcome message
        """
        response = client.post('/login', data={
            'username': sample_user.username,
            'password': 'testpass123'
        }, follow_redirects=True)

        assert response.status_code == 200
        # After login, should see the username or home page content
        assert b'testuser' in response.data or b'Welcome back' in response.data

    def test_failed_login(self, client, sample_user):
        """
        TEST: Login fails with wrong password.
        """
        response = client.post('/login', data={
            'username': sample_user.username,
            'password': 'wrongpassword'
        }, follow_redirects=True)

        assert response.status_code == 200
        assert b'Invalid username or password' in response.data

    def test_logout(self, logged_in_client):
        """
        TEST: User can log out.
        """
        response = logged_in_client.get('/logout', follow_redirects=True)
        assert response.status_code == 200
        # After logout, should see login link
        assert b'Login' in response.data

    def test_successful_registration(self, client):
        """
        TEST: New user can register.
        """
        response = client.post('/register', data={
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password': 'newpassword123',
            'password2': 'newpassword123'
        }, follow_redirects=True)

        assert response.status_code == 200
        # Should redirect to login with success message
        assert b'Congratulations' in response.data or b'Sign In' in response.data

        # User should exist in database
        user = User.query.filter_by(username='newuser').first()
        assert user is not None
        assert user.email == 'newuser@example.com'

    def test_duplicate_username_registration(self, client, sample_user):
        """
        TEST: Registration fails with duplicate username.
        """
        response = client.post('/register', data={
            'username': sample_user.username,  # Already exists
            'email': 'different@example.com',
            'password': 'password123',
            'password2': 'password123'
        }, follow_redirects=True)

        assert response.status_code == 200
        assert b'Please use a different username' in response.data


class TestProtectedRoutes:
    """
    TEST PROTECTED ROUTES
    ---------------------
    Routes that require authentication.
    """

    def test_index_requires_login(self, client):
        """
        TEST: Index page redirects to login if not authenticated.
        """
        response = client.get('/')
        assert response.status_code == 302
        assert '/login' in response.location

    def test_index_accessible_when_logged_in(self, logged_in_client):
        """
        TEST: Index page is accessible when logged in.
        """
        response = logged_in_client.get('/')
        assert response.status_code == 200
        assert b'Welcome back' in response.data or b'Your Feed' in response.data

    def test_explore_accessible_when_logged_in(self, logged_in_client):
        """
        TEST: Explore page is accessible when logged in.
        """
        response = logged_in_client.get('/explore')
        assert response.status_code == 200

    def test_profile_page_loads(self, logged_in_client, sample_user):
        """
        TEST: User profile page loads correctly.
        """
        response = logged_in_client.get(f'/user/{sample_user.username}')
        assert response.status_code == 200
        assert sample_user.username.encode() in response.data

    def test_nonexistent_user_returns_404(self, logged_in_client):
        """
        TEST: Accessing nonexistent user returns 404.
        """
        response = logged_in_client.get('/user/nonexistentuser')
        assert response.status_code == 404


class TestPostFeatures:
    """
    TEST POST FEATURES
    ------------------
    Creating, liking, deleting posts.
    """

    def test_create_post(self, logged_in_client, sample_user):
        """
        TEST: User can create a post.
        """
        response = logged_in_client.post('/', data={
            'post': 'This is my test post!'
        }, follow_redirects=True)

        assert response.status_code == 200
        assert b'Your post is now live' in response.data

        # Post should exist in database
        post = Post.query.filter_by(body='This is my test post!').first()
        assert post is not None
        assert post.author.username == sample_user.username

    def test_like_post(self, logged_in_client, sample_post):
        """
        TEST: User can like a post.
        """
        initial_count = sample_post.like_count()

        response = logged_in_client.post(
            f'/like/{sample_post.id}',
            follow_redirects=True
        )

        assert response.status_code == 200
        # Refresh post from database
        db.session.refresh(sample_post)
        assert sample_post.like_count() == initial_count + 1

    def test_unlike_post(self, logged_in_client, sample_post, sample_user):
        """
        TEST: User can unlike a post they liked.
        """
        # First like the post
        sample_post.like(sample_user)
        db.session.commit()

        response = logged_in_client.post(
            f'/unlike/{sample_post.id}',
            follow_redirects=True
        )

        assert response.status_code == 200
        db.session.refresh(sample_post)
        assert sample_post.like_count() == 0

    def test_delete_own_post(self, logged_in_client, sample_post):
        """
        TEST: User can delete their own post.
        """
        post_id = sample_post.id

        response = logged_in_client.post(
            f'/delete/{post_id}',
            follow_redirects=True
        )

        assert response.status_code == 200
        assert b'Post deleted' in response.data

        # Post should not exist
        deleted_post = Post.query.get(post_id)
        assert deleted_post is None

    def test_cannot_delete_others_post(self, client, sample_user2, sample_post):
        """
        TEST: User cannot delete another user's post.
        """
        # Login as user2
        client.post('/login', data={
            'username': sample_user2.username,
            'password': 'testpass123'
        }, follow_redirects=True)

        post_id = sample_post.id

        response = client.post(
            f'/delete/{post_id}',
            follow_redirects=True
        )

        assert response.status_code == 200
        assert b'You can only delete your own posts' in response.data

        # Post should still exist
        post = Post.query.get(post_id)
        assert post is not None


class TestFollowFeatures:
    """
    TEST FOLLOW FEATURES
    --------------------
    Following and unfollowing users.
    """

    def test_follow_user(self, logged_in_client, sample_user, sample_user2):
        """
        TEST: User can follow another user.
        """
        response = logged_in_client.post(
            f'/follow/{sample_user2.username}',
            follow_redirects=True
        )

        assert response.status_code == 200
        assert b'You are following' in response.data

        db.session.refresh(sample_user)
        assert sample_user.is_following(sample_user2)

    def test_unfollow_user(self, logged_in_client, sample_user, sample_user2):
        """
        TEST: User can unfollow another user.
        """
        # First follow
        sample_user.follow(sample_user2)
        db.session.commit()

        response = logged_in_client.post(
            f'/unfollow/{sample_user2.username}',
            follow_redirects=True
        )

        assert response.status_code == 200
        assert b'You are not following' in response.data

        db.session.refresh(sample_user)
        assert not sample_user.is_following(sample_user2)


class TestSearchFeature:
    """
    TEST SEARCH FEATURE
    -------------------
    Searching for users and posts.
    """

    def test_search_page_loads(self, logged_in_client):
        """
        TEST: Search page is accessible.
        """
        response = logged_in_client.get('/search')
        assert response.status_code == 200

    def test_search_finds_user(self, logged_in_client, sample_user):
        """
        TEST: Search can find users by username.
        """
        response = logged_in_client.get(f'/search?q={sample_user.username}')
        assert response.status_code == 200
        assert sample_user.username.encode() in response.data

    def test_search_finds_post(self, logged_in_client, sample_post):
        """
        TEST: Search can find posts by content.
        """
        # Search for a word in the post
        response = logged_in_client.get('/search?q=test')
        assert response.status_code == 200
        # Should show the post
        assert b'test post' in response.data.lower()

    def test_search_no_results(self, logged_in_client):
        """
        TEST: Search shows appropriate message when no results.
        """
        response = logged_in_client.get('/search?q=xyznonexistent123')
        assert response.status_code == 200
        assert b'No results found' in response.data


class TestEditProfile:
    """
    TEST EDIT PROFILE
    -----------------
    Profile editing functionality.
    """

    def test_edit_profile_page_loads(self, logged_in_client):
        """
        TEST: Edit profile page is accessible.
        """
        response = logged_in_client.get('/edit_profile')
        assert response.status_code == 200
        assert b'Edit Profile' in response.data

    def test_update_profile(self, logged_in_client, sample_user):
        """
        TEST: User can update their profile.
        """
        response = logged_in_client.post('/edit_profile', data={
            'username': sample_user.username,
            'about_me': 'This is my new bio!'
        }, follow_redirects=True)

        assert response.status_code == 200
        assert b'Your changes have been saved' in response.data

        db.session.refresh(sample_user)
        assert sample_user.about_me == 'This is my new bio!'
