from flask import render_template, flash, redirect, url_for, request
from app import app
from app import db
from app.forms import (LoginForm, RegistrationForm, EditProfileForm, EmptyForm,
                       PostForm, ResetPasswordRequestForm, ResetPasswordForm, SearchForm)
# login
from urllib.parse import urlparse
from flask_login import current_user, login_user, logout_user, login_required
from app.models import User, Post
from datetime import datetime
from app.email import send_password_reset_email

@app.route('/', methods=['GET', 'POST'])
@app.route('/index', methods=['GET', 'POST'])
@login_required  # decorater used for login
def index():
    form = PostForm()
    if form.validate_on_submit():
        post = Post(body=form.post.data, author=current_user)
        db.session.add(post)
        db.session.commit()
        flash('Your post is now live!')
        return redirect(url_for('index'))
    page = request.args.get('page', 1, type=int)
    posts = current_user.followed_posts().paginate(
        page=page, per_page=app.config['POSTS_PER_PAGE'], error_out=False)
    next_url = url_for('index', page=posts.next_num) \
        if posts.has_next else None
    prev_url = url_for('index', page=posts.prev_num) \
        if posts.has_prev else None
    return render_template('index.html', title='Home', form=form,
                           posts=posts.items, next_url=next_url,
                           prev_url=prev_url)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password')
            return redirect(url_for('login'))
        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get('next')
        if not next_page or urlparse(next_page).netloc != '':
            next_page = url_for('index')
        return redirect(next_page)
    return render_template('login.html', title='Sign In', form=form)


@app.route('/reset_password_request', methods=['GET', 'POST'])
def reset_password_request():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = ResetPasswordRequestForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            send_password_reset_email(user)
        flash('Check your email for the instructions to reset your password')
        return redirect(url_for('login'))
    return render_template('reset_password_request.html',
                           title='Reset Password', form=form)

#password reset view function
@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    user = User.verify_reset_password_token(token)
    if not user:
        return redirect(url_for('index'))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash('Your password has been reset.')
        return redirect(url_for('login'))
    return render_template('reset_password.html', form=form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Congratulations, you are now a registered user!')
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form)


# user profile page
@app.route('/user/<username>')
@login_required
def user(username):
    user = User.query.filter_by(username=username).first_or_404()
    page = request.args.get('page', 1, type=int)
    posts = user.posts.order_by(Post.timestamp.desc()).paginate(
        page=page, per_page=app.config['POSTS_PER_PAGE'], error_out=False)
    next_url = url_for('user', username=user.username, page=posts.next_num) \
        if posts.has_next else None
    prev_url = url_for('user', username=user.username, page=posts.prev_num) \
        if posts.has_prev else None
    form = EmptyForm()
    return render_template('user.html', user=user, posts=posts.items,
                           next_url=next_url, prev_url=prev_url, form=form)


@app.before_request
def before_request():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.utcnow()
        db.session.commit()


@app.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm(current_user.username)
    if form.validate_on_submit():
        current_user.username = form.username.data
        current_user.about_me = form.about_me.data
        db.session.commit()
        flash('Your changes have been saved.')
        return redirect(url_for('edit_profile'))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.about_me.data = current_user.about_me
    return render_template('edit_profile.html', title='Edit Profile', form=form)


@app.route('/follow/<username>', methods=['POST'])
@login_required
def follow(username):
    form = EmptyForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=username).first()
        if user is None:
            flash('User {} not found.'.format(username))
            return redirect(url_for('index'))
        if user == current_user:
            flash('You cannot follow yourself!')
            return redirect(url_for('user', username=username))
        current_user.follow(user)
        db.session.commit()
        flash('You are following {}!'.format(username))
        return redirect(url_for('user', username=username))
    else:
        return redirect(url_for('index'))


@app.route('/unfollow/<username>', methods=['POST'])
@login_required
def unfollow(username):
    form = EmptyForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=username).first()
        if user is None:
            flash('User {} not found.'.format(username))
            return redirect(url_for('index'))
        if user == current_user:
            flash('You cannot unfollow yourself!')
            return redirect(url_for('user', username=username))
        current_user.unfollow(user)
        db.session.commit()
        flash('You are not following {}.'.format(username))
        return redirect(url_for('user', username=username))
    else:
        return redirect(url_for('index'))


@app.route('/explore')
@login_required
def explore():
    page = request.args.get('page', 1, type=int)
    posts = Post.query.order_by(Post.timestamp.desc()).paginate(
        page=page, per_page=app.config['POSTS_PER_PAGE'], error_out=False)
    next_url = url_for('explore', page=posts.next_num) \
        if posts.has_next else None
    prev_url = url_for('explore', page=posts.prev_num) \
        if posts.has_prev else None
    return render_template("index.html", title='Explore', posts=posts.items,
                           next_url=next_url, prev_url=prev_url)


# =============================================================================
# LIKE/UNLIKE ROUTES
# =============================================================================
#
# HTTP METHODS EXPLAINED:
# -----------------------
# - GET: Retrieve data (viewing pages)
# - POST: Submit data (forms, actions like like/unlike)
# - DELETE: Remove data (we'll use POST for compatibility)
#
# WHY POST and not GET for likes?
# - GET requests should be "safe" (no side effects)
# - Liking a post CHANGES data, so we use POST
# - Also prevents accidental likes from link prefetching
#
# THE 'referrer' PARAMETER:
# - After liking, we redirect back to where the user was
# - request.referrer gives us the previous page URL
# - This creates a smooth UX (user stays on same page)
# =============================================================================

@app.route('/like/<int:post_id>', methods=['POST'])
@login_required
def like_post(post_id):
    """Like a post. Redirects back to the referring page."""
    post = Post.query.get_or_404(post_id)
    post.like(current_user)
    db.session.commit()

    # Redirect back to where the user came from
    return redirect(request.referrer or url_for('index'))


@app.route('/unlike/<int:post_id>', methods=['POST'])
@login_required
def unlike_post(post_id):
    """Unlike a post. Redirects back to the referring page."""
    post = Post.query.get_or_404(post_id)
    post.unlike(current_user)
    db.session.commit()

    # Redirect back to where the user came from
    return redirect(request.referrer or url_for('index'))


# =============================================================================
# DELETE POST ROUTE
# =============================================================================
#
# AUTHORIZATION EXPLAINED:
# ------------------------
# Authentication = "Who are you?" (handled by @login_required)
# Authorization = "What can you do?" (checked with post.author == current_user)
#
# A user should ONLY be able to delete their OWN posts.
# If someone tries to delete another user's post, we reject with 403 Forbidden.
#
# HTTP STATUS CODES:
# - 200 = OK
# - 403 = Forbidden (authenticated but not authorized)
# - 404 = Not Found
# =============================================================================

@app.route('/delete/<int:post_id>', methods=['POST'])
@login_required
def delete_post(post_id):
    """Delete a post. Only the author can delete their own posts."""
    post = Post.query.get_or_404(post_id)

    # AUTHORIZATION CHECK: Only author can delete
    if post.author != current_user:
        flash('You can only delete your own posts!')
        return redirect(url_for('index'))

    db.session.delete(post)
    db.session.commit()
    flash('Post deleted.')

    return redirect(request.referrer or url_for('index'))


# =============================================================================
# SEARCH ROUTE
# =============================================================================
#
# SQL LIKE QUERIES EXPLAINED:
# ---------------------------
# The LIKE operator in SQL allows pattern matching:
# - % = matches any sequence of characters
# - _ = matches exactly one character
#
# Examples:
# - LIKE '%hello%' matches 'say hello world', 'hello', 'helloooo'
# - LIKE 'hello%' matches 'hello world' but not 'say hello'
#
# In SQLAlchemy, we use .ilike() for case-insensitive matching.
#
# QUERY PARAMETERS EXPLAINED:
# ---------------------------
# request.args contains URL query parameters
# For URL /search?q=hello&page=2:
# - request.args.get('q') returns 'hello'
# - request.args.get('page', 1, type=int) returns 2 (as integer)
# =============================================================================

@app.route('/search')
@login_required
def search():
    """Search for users and posts."""
    form = SearchForm()

    # If no search query, show empty search page
    if not form.validate():
        return render_template('search.html', title='Search', form=form,
                             users=[], posts=[])

    # Get the search query
    query = form.q.data
    page = request.args.get('page', 1, type=int)

    # Search for users (case-insensitive username match)
    users = User.query.filter(
        User.username.ilike(f'%{query}%')
    ).limit(10).all()

    # Search for posts (case-insensitive body match)
    posts = Post.query.filter(
        Post.body.ilike(f'%{query}%')
    ).order_by(Post.timestamp.desc()).paginate(
        page=page, per_page=app.config['POSTS_PER_PAGE'], error_out=False
    )

    next_url = url_for('search', q=query, page=posts.next_num) \
        if posts.has_next else None
    prev_url = url_for('search', q=query, page=posts.prev_num) \
        if posts.has_prev else None

    return render_template('search.html', title='Search', form=form,
                         users=users, posts=posts.items, query=query,
                         next_url=next_url, prev_url=prev_url)
