import os
from dotenv import load_dotenv

from flask import Flask, render_template, request, flash, redirect, session, g
from flask_debugtoolbar import DebugToolbarExtension
from sqlalchemy.exc import IntegrityError

from forms import UserAddForm, LoginForm, MessageForm,CsrfForm,ProfileEditForm
from models import db, connect_db, User, Message, UserLikedMessage
from werkzeug.exceptions import Unauthorized

load_dotenv()

CURR_USER_KEY = "curr_user"

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL']
app.config['SQLALCHEMY_ECHO'] = False
app.config['DEBUG_TB_INTERCEPT_REDIRECTS'] = True
app.config['SECRET_KEY'] = os.environ['SECRET_KEY']
toolbar = DebugToolbarExtension(app)
app.config['DEBUG_TB_INTERCEPT_REDIRECTS'] = False

connect_db(app)


##############################################################################
# User signup/login/logout
@app.before_request
def add_csrf_to_g():
    """Adds csrfForm to global"""
    g.csrf_form = CsrfForm()


@app.before_request
def add_user_to_g():
    """If we're logged in, add curr user to Flask global."""

    if CURR_USER_KEY in session:
        g.user = User.query.get(session[CURR_USER_KEY])

        if not g.user:
            del session[CURR_USER_KEY]

    else:
        g.user = None
        

def do_login(user):
    """Log in user."""

    session[CURR_USER_KEY] = user.id


def do_logout():
    """Log out user."""

    if CURR_USER_KEY in session:
        del session[CURR_USER_KEY]


@app.route('/signup', methods=["GET", "POST"])
def signup():
    """Handle user signup.

    Create new user and add to DB. Redirect to home page.

    If form not valid, present form.

    If the there already is a user with that username: flash message
    and re-present form.
    """
    print("session--------------->", session)

    if CURR_USER_KEY in session:
        return redirect(f"/users/{session[CURR_USER_KEY]}")

    do_logout()

    form = UserAddForm()

    if form.validate_on_submit():
        try:
            user = User.signup(
                username=form.username.data,
                password=form.password.data,
                email=form.email.data,
                image_url=form.image_url.data or User.image_url.default.arg,
            )
            db.session.commit()

        except IntegrityError:
            flash("Username already taken", 'danger')
            return render_template('users/signup.html', form=form)

        do_login(user)

        return redirect("/")

    else:
        return render_template('users/signup.html', form=form)


@app.route('/login', methods=["GET", "POST"])
def login():
    """Handle user login and redirect to homepage on success."""

    if CURR_USER_KEY in session:
        return redirect(f"/users/{session[CURR_USER_KEY]}")

    form = LoginForm()

    if form.validate_on_submit():
        user = User.authenticate(
            form.username.data,
            form.password.data,
        )
        if user:
            do_login(user)
            flash(f"Hello, {user.username}!", "success")
            return redirect("/")

        flash("Invalid credentials.", 'danger')

    return render_template('users/login.html', form=form)


@app.post('/logout')
def logout():
    """Handle logout of user and redirect to homepage."""

    if g.user and g.csrf_form.validate_on_submit():
        do_logout()

        return redirect('/')

    else:
        # didn't pass CSRF; ignore logout attempt
        print("not validating************")

        raise Unauthorized()

    # IMPLEMENT THIS AND FIX BUG
    # DO NOT CHANGE METHOD ON ROUTE



##############################################################################
# General user routes:

@app.get('/users')
def list_users():
    """Page with listing of users.

    Can take a 'q' param in querystring to search by that username.
    """
    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    search = request.args.get('q')

    if not search:
        users = User.query.all()
    else:
        users = User.query.filter(User.username.like(f"%{search}%")).all()

    return render_template('users/index.html', users=users)


@app.get('/users/<int:user_id>')
def show_user(user_id):
    """Show user profile."""

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    user = User.query.get_or_404(user_id)

    return render_template('users/show.html', user=user)


@app.get('/users/<int:user_id>/following')
def show_following(user_id):
    """Show list of people this user is following."""

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    user = User.query.get_or_404(user_id)
    # breakpoint()
    return render_template('users/following.html', user=user)


@app.get('/users/<int:user_id>/followers')
def show_followers(user_id):
    """Show list of followers of this user."""

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    user = User.query.get_or_404(user_id)
    return render_template('users/followers.html', user=user)


@app.post('/users/follow/<int:follow_id>')
def start_following(follow_id):
    """Add a follow for the currently-logged-in user.

    Redirect to following page for the current for the current user.
    """
    # breakpoint()
    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    followed_user = User.query.get_or_404(follow_id)
    g.user.following.append(followed_user)
    db.session.commit()
    # breakpoint()

    return redirect(f"/users/{g.user.id}/following")



@app.post('/users/stop-following/<int:follow_id>')
def stop_following(follow_id):
    """Have currently-logged-in-user stop following this user.

    Redirect to following page for the current for the current user.
    """

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    followed_user = User.query.get_or_404(follow_id)
    g.user.following.remove(followed_user)
    db.session.commit()

    return redirect(f"/users/{g.user.id}/following")


@app.route('/users/profile', methods=["GET", "POST"])
def show_profile_and_edit():
    """Update profile for current user."""

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")



    user = g.user
    form = ProfileEditForm(obj=user)

    if form.validate_on_submit():

        if User.authenticate(user.username, form.password.data):
            user.username = form.username.data
            user.email=form.email.data
            user.image_url=form.image_url.data or user.image_url
            user.header_image_url=form.header_image_url.data or user.header_image_url
            user.bio = form.bio.data

            db.session.commit()
            print("user is authenticated here")
            return redirect(f'/users/{user.id}')

        else:
            flash('Invalid password!')
            print("this is invalid password")
            return render_template('users/edit.html',form=form)

    print("submit is not validated")

    return render_template('users/edit.html',form=form)


@app.post('/users/delete')
def delete_user():
    """Delete user.

    Redirect to signup page.
    """
    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    do_logout()

    db.session.delete(g.user)
    db.session.commit()

    return redirect("/signup")


##############################################################################
# Messages routes:

@app.route('/messages/new', methods=["GET", "POST"])
def add_message():
    """Add a message:

    Show form if GET. If valid, update message and redirect to user page.
    """

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    form = MessageForm()

    if form.validate_on_submit():
        msg = Message(text=form.text.data)
        g.user.messages.append(msg)
        db.session.commit()

        return redirect(f"/users/{g.user.id}")

    return render_template('messages/create.html', form=form)


@app.get('/messages/<int:message_id>')
def show_message(message_id):
    """Show a message."""

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    msg = Message.query.get_or_404(message_id)
    return render_template('messages/show.html', message=msg)


@app.post('/messages/<int:message_id>/delete')
def delete_message(message_id):
    """Delete a message.

    Check that this message was written by the current user.
    Redirect to user page on success.
    """

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    msg = Message.query.get_or_404(message_id)
    db.session.delete(msg)
    db.session.commit()

    return redirect(f"/users/{g.user.id}")


##############################################################################
# Homepage and error pages


@app.get('/')
def homepage():
    """Show homepage:

    - anon users: no messages
    - logged in: 100 most recent messages of self & followed_users
    """

    if g.user:
        user = User.query.get_or_404(g.user.id)
        following_ids = [user.id for user in user.following]
        messages = (Message
                    .query
                    .filter((Message.user_id.in_(following_ids)) | (Message.user_id==user.id))
                    .order_by(Message.timestamp.desc())
                    .limit(100)
                    .all())

        return render_template('home.html', messages=messages, user=user)

    else:
        return render_template('home-anon.html')

############################handle likes#####################################
@app.post('/messages/<int:message_id>/like')
def add_like_or_unlike(message_id):
    "handle user like/unlike;redirect to homepage"


    if not (g.user and g.csrf_form.validate_on_submit()):
        flash("Access unauthorized.", "danger")
        return redirect("/")

    user = g.user
    liked_messages = user.liked_messages
    message = Message.query.get_or_404(message_id)
    come_from = request.form["come_from"]

    if message not in liked_messages:
        if message.user != user:
            user.liked_messages.append(message)

    else:
        user.liked_messages.remove(message)

    db.session.commit()

    return redirect(come_from)


@app.get('/users/<int:user_id>/likes')
def show_liked_messages(user_id):

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    user = User.query.get_or_404(user_id)
    liked_messages = user.liked_messages

    return render_template(
        'messages/liked_list2.html',
        messages=liked_messages,
        user=user
    )




































##############################################################################
@app.after_request
def add_header(response):
    """Add non-caching headers on every request."""

    # https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cache-Control
    response.cache_control.no_store = True
    return response
