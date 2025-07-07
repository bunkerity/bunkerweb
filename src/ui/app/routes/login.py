from datetime import datetime
from os import getenv, sep
from os.path import join
from sys import path as sys_path

# Add BunkerWeb dependency paths to Python path for module imports
for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) 
                  for paths in (("deps", "python"), ("utils",), ("api",), 
                               ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

# Import the setup_logger function from bw_logger module and give it the
# shorter alias 'bwlog' for convenience.
from bw_logger import setup_logger as bwlog

# Initialize bw_logger module
logger = bwlog(
    title="UI",
    log_file_path="/var/log/bunkerweb/ui.log"
)

# Check if debug logging is enabled
DEBUG_MODE = getenv("LOG_LEVEL", "INFO").upper() == "DEBUG"

if DEBUG_MODE:
    logger.debug("Debug mode enabled for login module")

from flask import Blueprint, current_app, flash as flask_flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_user

from app.dependencies import DB
from app.utils import BISCUIT_PRIVATE_KEY_FILE, LOGGER, flash
from app.models.biscuit import BiscuitTokenFactory, PrivateKey

login = Blueprint("login", __name__)


# Handle comprehensive user authentication with multi-layered security and session management.
# Processes login credentials with database validation, implements session regeneration against
# fixation attacks, manages Biscuit token generation, and enforces security policies including
# two-factor authentication recommendations and persistent session handling.
@login.route("/login", methods=["GET", "POST"])
def login_page():
    if DEBUG_MODE:
        logger.debug(f"login_page() called - processing authentication request")
        logger.debug(f"Request method: {request.method}, Content-Type: {request.content_type}")
        logger.debug(f"Client information - IP: {request.remote_addr}, User-Agent: {request.headers.get('User-Agent', 'Unknown')}")
        logger.debug(f"Request args: {dict(request.args)}")
        logger.debug(f"Current session keys: {list(session.keys()) if session else 'No session'}")
        logger.debug(f"Flask session ID exists: {'_id' in session if session else False}")
    
    admin_user = DB.get_ui_user()
    if DEBUG_MODE:
        logger.debug("Checking for admin user existence in database")
    
    if not admin_user:
        if DEBUG_MODE:
            logger.debug("No admin user found in database - system requires initial setup")
        return redirect(url_for("setup.setup_page"))
    elif current_user.is_authenticated:  # type: ignore
        if DEBUG_MODE:
            logger.debug(f"User already authenticated: {current_user.username} (ID: {current_user.get_id()})")
            logger.debug(f"Current user admin status: {getattr(current_user, 'admin', 'Unknown')}")
            logger.debug("Redirecting authenticated user to home page")
        return redirect(url_for("home.home_page"))

    if DEBUG_MODE:
        logger.debug(f"Admin user found in database: {admin_user.username}")
        logger.debug(f"Admin user properties - ID: {admin_user.get_id()}, admin: {admin_user.admin}")
        logger.debug(f"Admin user TOTP enabled: {bool(admin_user.totp_secret)}")
        logger.debug(f"Current user authentication status: {current_user.is_authenticated}")
        logger.debug("Proceeding with login page processing")

    fail = False
    if request.method == "POST" and "username" in request.form and "password" in request.form:
        if DEBUG_MODE:
            logger.debug("POST request received with required authentication fields")
            logger.debug(f"Login attempt for username: '{request.form['username']}'")
            logger.debug(f"Password field length: {len(request.form['password'])} characters")
            logger.debug(f"Form fields present: {list(request.form.keys())}")
            logger.debug(f"Remember-me checkbox: {'remember-me' in request.form and request.form.get('remember-me') == 'on'}")
            logger.debug(f"User preferences - theme: '{request.form.get('theme', 'not specified')}', language: '{request.form.get('language', 'not specified')}'")
            logger.debug(f"Next URL parameter: '{request.args.get('next', 'not specified')}'")
        
        LOGGER.warning(f"Login attempt from {request.remote_addr} with username \"{request.form['username']}\"")

        ui_user = DB.get_ui_user(username=request.form["username"])
        if DEBUG_MODE:
            logger.debug(f"Database user lookup completed for username: '{request.form['username']}'")
            logger.debug(f"User found in database: {ui_user is not None}")
            if ui_user:
                logger.debug(f"User details - username: '{ui_user.username}', admin: {ui_user.admin}")
                logger.debug(f"User security - TOTP enabled: {bool(ui_user.totp_secret)}")
                logger.debug(f"User preferences - theme: '{ui_user.theme}', method: '{ui_user.method}', language: '{ui_user.language}'")
                logger.debug(f"User email: '{ui_user.email or 'Not set'}'")
                logger.debug("Proceeding with password verification")
            else:
                logger.debug("Username not found in database - authentication will fail")
        
        if ui_user and ui_user.username == request.form["username"] and ui_user.check_password(request.form["password"]):
            if DEBUG_MODE:
                logger.debug("Authentication validation successful - all checks passed")
                logger.debug(f"Username match: {ui_user.username == request.form['username']}")
                logger.debug("Password verification completed successfully")
                logger.debug("Initiating secure session establishment process")
                logger.debug(f"Current session before regeneration: {dict(session) if session else 'Empty'}")
            
            # Regenerate the session to mitigate session fixation
            session.clear()  # Clear the current session
            current_app.session_interface.regenerate(session)  # Regenerate the session ID
            
            if DEBUG_MODE:
                logger.debug("Session fixation protection applied successfully")
                logger.debug("Previous session data cleared and new session ID generated")
                logger.debug(f"New session ID generated: {session.get('_id', 'Unknown')}")

            # log the user in
            session["creation_date"] = datetime.now().astimezone()
            session["ip"] = request.remote_addr
            session["user_agent"] = request.headers.get("User-Agent")
            session["totp_validated"] = False
            session["flash_messages"] = []
            
            if DEBUG_MODE:
                logger.debug("Session metadata initialized with security tracking information")
                logger.debug(f"Session creation timestamp: {session['creation_date']}")
                logger.debug(f"Client IP address logged: {session['ip']}")
                logger.debug(f"User-Agent stored: {session['user_agent'][:100]}{'...' if len(session['user_agent']) > 100 else ''}")
                logger.debug(f"TOTP validation status: {session['totp_validated']}")
                logger.debug("Flash messages queue initialized")

            ret = DB.mark_ui_user_login(ui_user.username, session["creation_date"], session["ip"], session["user_agent"])
            if isinstance(ret, str):
                logger.exception("Database login marking operation failed")
                LOGGER.error(f"Couldn't mark the user login: {ret}")
                if DEBUG_MODE:
                    logger.debug(f"Login marking error details: {ret}")
                    logger.debug("Continuing without database session tracking")
            else:
                session["session_id"] = ret
                if DEBUG_MODE:
                    logger.debug(f"Login successfully recorded in database")
                    logger.debug(f"Assigned database session ID: {ret}")
                    logger.debug(f"Session ID type: {type(ret)}, length: {len(str(ret))}")

            always_remember = getenv("ALWAYS_REMEMBER", "no").lower() == "yes"
            remember_me = always_remember or request.form.get("remember-me") == "on"
            if DEBUG_MODE:
                logger.debug("Processing session persistence configuration")
                logger.debug(f"Environment ALWAYS_REMEMBER setting: '{getenv('ALWAYS_REMEMBER', 'not set')}'")
                logger.debug(f"Always remember resolved to: {always_remember}")
                logger.debug(f"User remember-me checkbox state: {request.form.get('remember-me') == 'on'}")
                logger.debug(f"Final remember_me decision: {remember_me}")
                logger.debug(f"Session will be {'persistent' if remember_me else 'temporary'}")
            
            if remember_me:
                if always_remember:
                    LOGGER.info("ALWAYS_REMEMBER is set to yes, so the sessions will always be remembered")
                    if DEBUG_MODE:
                        logger.debug("Using environment-enforced session persistence")
                elif DEBUG_MODE:
                    logger.debug("Using user-requested session persistence")
                
                session.permanent = True
                if DEBUG_MODE:
                    logger.debug("Session marked as permanent - will persist beyond browser closure")

            if not login_user(ui_user, remember=remember_me):
                if DEBUG_MODE:
                    logger.debug("Flask-Login login_user() operation failed")
                    logger.debug(f"Attempted to login user: {ui_user.username} with remember={remember_me}")
                flask_flash("Couldn't log you in, please try again", "error")
                return (render_template("login.html", error="Couldn't log you in, please try again"),)

            if DEBUG_MODE:
                logger.debug("Flask-Login authentication completed successfully")
                logger.debug(f"User session established for: {ui_user.username}")
                logger.debug(f"Current user object: {current_user.get_id()}")
                logger.debug(f"Authentication state: {current_user.is_authenticated}")

            # Generate and add Biscuit token to session
            try:
                if DEBUG_MODE:
                    logger.debug("Initiating Biscuit token generation process")
                    logger.debug(f"Biscuit private key file path: {BISCUIT_PRIVATE_KEY_FILE}")
                    logger.debug(f"Private key file exists: {BISCUIT_PRIVATE_KEY_FILE.exists()}")
                
                if BISCUIT_PRIVATE_KEY_FILE.exists():
                    if DEBUG_MODE:
                        logger.debug("Biscuit private key file located - proceeding with token creation")
                    
                    private_key = PrivateKey.from_hex(BISCUIT_PRIVATE_KEY_FILE.read_text().strip())
                    token_factory = BiscuitTokenFactory(private_key)
                    role = "super_admin" if ui_user.admin else [role.role_name for role in ui_user.roles][0]  # For now we shall only have one role per user
                    
                    if DEBUG_MODE:
                        logger.debug(f"User role determination - admin: {ui_user.admin}")
                        logger.debug(f"User roles count: {len(ui_user.roles) if ui_user.roles else 0}")
                        logger.debug(f"Assigned role for token: '{role}'")
                    
                    biscuit_token = token_factory.create_token_for_role(role, ui_user.username)
                    session["biscuit_token"] = biscuit_token.to_base64()
                    
                    if DEBUG_MODE:
                        logger.debug("Biscuit token created and encoded successfully")
                        logger.debug(f"Token length: {len(session['biscuit_token'])} characters")
                        logger.debug("Biscuit token stored in session for authorization")
                else:
                    LOGGER.warning("BISCUIT_PRIVATE_KEY_PATH not configured, skipping Biscuit token generation")
                    if DEBUG_MODE:
                        logger.debug("Biscuit private key file not found - authentication will work without authorization tokens")
            except Exception as e:
                logger.exception("Critical error during Biscuit token generation")
                LOGGER.error(f"Failed to create Biscuit token: {e}")
                if DEBUG_MODE:
                    logger.debug(f"Biscuit token generation failure details:")
                    logger.debug(f"  Exception type: {type(e).__name__}")
                    logger.debug(f"  Exception message: {str(e)}")
                    logger.debug("  Continuing login process without Biscuit token")

            user_data = {
                "username": current_user.get_id(),
                "password": current_user.password.encode("utf-8"),
                "email": current_user.email,
                "totp_secret": current_user.totp_secret,
                "method": current_user.method,
                "theme": request.form.get("theme", "light"),
                "language": request.form.get("language", "en"),
            }
            
            if DEBUG_MODE:
                logger.debug("Preparing user preference updates from login form")
                logger.debug(f"Current user preferences - theme: '{current_user.theme}', language: '{current_user.language}'")
                logger.debug(f"Requested preferences - theme: '{user_data['theme']}', language: '{user_data['language']}'")
                logger.debug(f"Preference changes needed: {current_user.theme != user_data['theme'] or current_user.language != user_data['language']}")

            ret = DB.update_ui_user(**user_data, old_username=current_user.get_id())
            if ret:
                logger.exception("User preference update failed during login")
                LOGGER.error(f"Couldn't update the user {current_user.get_id()}: {ret}")
                if DEBUG_MODE:
                    logger.debug(f"Database update error details: {ret}")
                    logger.debug("Login will continue despite preference update failure")
            elif DEBUG_MODE:
                logger.debug("User preferences synchronized successfully with login form data")

            LOGGER.info(f"User {ui_user.username} logged in successfully" + (" with remember me" if request.form.get("remember-me") == "on" else ""))
            
            if DEBUG_MODE:
                logger.debug(f"Login process completed successfully for user: {ui_user.username}")
                logger.debug(f"Session persistence: {'enabled' if remember_me else 'disabled'}")
                logger.debug(f"Total session keys: {len(session)}")

            if not ui_user.totp_secret:
                if DEBUG_MODE:
                    logger.debug("User lacks TOTP configuration - displaying security recommendation")
                flash(
                    f'Please enable two-factor authentication to secure your account <a href="{url_for("profile.profile_page", _anchor="security")}">here</a>',
                    "warning",
                )
            elif DEBUG_MODE:
                logger.debug("User has TOTP properly configured - no additional security warnings needed")

            # redirect him to the page he originally wanted or to the home page
            next_url = request.args.get("next", "").split("?next=")[-1] or url_for("home.home_page")
            if DEBUG_MODE:
                logger.debug(f"Processing post-login redirect destination")
                logger.debug(f"Original next parameter: '{request.args.get('next', 'not provided')}'")
                logger.debug(f"Processed next URL: '{next_url}'")
                logger.debug(f"Redirect safety check: {'url_for result' if next_url == url_for('home.home_page') else 'user provided URL'}")
            
            return redirect(url_for("loading", next=next_url))
        else:
            if DEBUG_MODE:
                logger.debug("Authentication validation failed - analyzing failure reasons")
                if not ui_user:
                    logger.debug("Primary failure: Username not found in database")
                elif ui_user.username != request.form["username"]:
                    logger.debug("Primary failure: Username case mismatch or encoding issue")
                    logger.debug(f"Database username: '{ui_user.username}' vs Form username: '{request.form['username']}'")
                else:
                    logger.debug("Primary failure: Password verification failed")
                    logger.debug("Password hash comparison returned False")
                logger.debug("Setting authentication failure state")
            
            flask_flash("Invalid username or password", "error")
            fail = True
    elif request.method == "POST":
        if DEBUG_MODE:
            logger.debug("POST request received but missing required authentication fields")
            logger.debug(f"Form fields present: {list(request.form.keys())}")
            logger.debug("Username or password field missing - cannot proceed with authentication")
    
    kwargs = {
        "is_totp": bool(current_user.totp_secret),
    } | ({"error": "Invalid username or password"} if fail else {})
    
    if DEBUG_MODE:
        logger.debug("Preparing login template response")
        logger.debug(f"Authentication failure state: {fail}")
        logger.debug(f"Current user TOTP status: {bool(current_user.totp_secret)}")
        logger.debug(f"Template kwargs: {list(kwargs.keys())}")
        logger.debug(f"Response status code: {401 if fail else 200}")
        logger.debug(f"Will render login.html with {'error' if fail else 'normal'} state")

    return render_template("login.html", **kwargs), 401 if fail else 200
