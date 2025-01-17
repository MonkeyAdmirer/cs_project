# External imports
import streamlit as st
import requests
import urllib.parse
import sqlite3
# Used to help generate even more unique keys for games
import time
import uuid

def sanitize_key(text):
    """Sanitize text to be used as a key by removing special characters"""
    return ''.join(c for c in text if c.isalnum())

# Database Code: Initializes the database and defines methods to interact with it
def initializeDB():
    # Create tables for Completed, Playing, Not Played games, and Reviews
    connection = sqlite3.connect('./peyton.db')
    cursor = connection.cursor()

    # Create Completed table with fields for 100% and On Hold status
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Completed (
            name TEXT NOT NULL,
            hundredpercent TEXT NOT NULL,
            hold TEXT NOT NULL
        );
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Playing (
            name TEXT NOT NULL
        );
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS NotPlayed (
            name TEXT NOT NULL
        );
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Reviews (
            name TEXT PRIMARY KEY,
            review INTEGER NOT NULL
        );
    ''')
    connection.commit()
    connection.close()

def get_completed():
    # Modified to return all rows from Completed table
    connection = sqlite3.connect('./peyton.db')
    cursor = connection.cursor()
    result = cursor.execute("SELECT name, hundredpercent, hold FROM Completed;").fetchall()
    connection.close()
    return result

def get_playing():
    # Fetch all games from the Playing table
    connection = sqlite3.connect('./peyton.db')
    cursor = connection.cursor()
    result = cursor.execute("SELECT name FROM Playing;").fetchall()
    connection.close()
    return [r[0] for r in result]  # Convert tuples to list of names

def get_notplayed():
    # Fetch all games from the Not Played table
    connection = sqlite3.connect('./peyton.db')
    cursor = connection.cursor()
    result = cursor.execute("SELECT name FROM NotPlayed;").fetchall()
    connection.close()
    return [r[0] for r in result]  # Convert tuples to list of names

def get_reviews():
    # Fetch all reviews from the Reviews table
    connection = sqlite3.connect('./peyton.db')
    cursor = connection.cursor()
    result = cursor.execute("SELECT name, review FROM Reviews;").fetchall()
    connection.close()
    return {r[0]: r[1] for r in result}  # Convert to dictionary with game names as keys

def add_completed(name, hundred, hold):
    # First check if the game exists
    connection = sqlite3.connect('./peyton.db')
    cursor = connection.cursor()
    
    # Check if game already exists
    existing = cursor.execute("SELECT * FROM Completed WHERE name = ?", (name,)).fetchone()
    
    if existing:
        # Update existing record
        cursor.execute(
            "UPDATE Completed SET hundredpercent = ?, hold = ? WHERE name = ?;",
            (hundred, hold, name)
        )
    else:
        # Insert new record
        cursor.execute(
            "INSERT INTO Completed (name, hundredpercent, hold) VALUES (?, ?, ?);",
            (name, hundred, hold)
        )
    
    connection.commit()
    connection.close()

def add_playing(name):
    # Add a game to the Playing table
    connection = sqlite3.connect('./peyton.db')
    cursor = connection.cursor()
    cursor.execute("INSERT INTO Playing (name) VALUES (?);", (name,))
    connection.commit()
    connection.close()

def add_notplayed(name):
    # Add a game to the Not Played table
    connection = sqlite3.connect('./peyton.db')
    cursor = connection.cursor()
    cursor.execute("INSERT INTO NotPlayed (name) VALUES (?);", (name,))
    connection.commit()
    connection.close()

def add_or_update_review(name, rating):
    connection = sqlite3.connect('./peyton.db')
    cursor = connection.cursor()
    try:
        # First try to update existing review
        cursor.execute("""
            UPDATE Reviews SET review = ? WHERE name = ?
        """, (rating, name))
        
        # If no rows were updated (review didn't exist), insert new review
        if cursor.rowcount == 0:
            cursor.execute("""
                INSERT INTO Reviews (name, review) VALUES (?, ?)
            """, (name, rating))
        
        connection.commit()
    except Exception as e:
        print(f"Error updating review: {e}")
        connection.rollback()
    finally:
        connection.close()

# Function to remove a game from a specific category
def remove_game(table_name, game_name):
    """
    Remove a game from a specified table.
    Returns True if successful, False otherwise.
    """
    connection = None
    try:
        connection = sqlite3.connect('./peyton.db')
        cursor = connection.cursor()
        
        # Validate table name to prevent SQL injection
        valid_tables = ['Completed', 'Playing', 'NotPlayed']
        if table_name not in valid_tables:
            print(f"Invalid table name: {table_name}")
            return False
            
        # First check if the game exists
        cursor.execute(f"SELECT COUNT(*) FROM {table_name} WHERE name = ?", (game_name,))
        count = cursor.fetchone()[0]
        
        if count > 0:
            # Delete the game
            cursor.execute(f"DELETE FROM {table_name} WHERE name = ?", (game_name,))
            connection.commit()
            
            # Also remove from Reviews if it exists there
            cursor.execute("DELETE FROM Reviews WHERE name = ?", (game_name,))
            connection.commit()
            
            return True
        return False
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        if connection:
            connection.rollback()
        return False
    finally:
        if connection:
            connection.close()

# Initialize the database
initializeDB()

# Steam OAuth Configuration
STEAM_OPENID_URL = "https://steamcommunity.com/openid/login"
REDIRECT_URI = "http://localhost:8501"  # Replace with your Streamlit app's URL
STEAM_API_KEY = "0E946B515504AE10AE711984A10A7AE2"  # Replace with your Steam API Key

# Construct the OpenID request URL
def authenticate_with_steam():
    params = {
        "openid.ns": "http://specs.openid.net/auth/2.0",
        "openid.mode": "checkid_setup",
        "openid.return_to": REDIRECT_URI,
        "openid.realm": REDIRECT_URI,
        "openid.identity": "http://specs.openid.net/auth/2.0/identifier_select",
        "openid.claimed_id": "http://specs.openid.net/auth/2.0/identifier_select",
    }
    auth_url = f"{STEAM_OPENID_URL}?" + urllib.parse.urlencode(params)
    return auth_url

# Validate Steam OpenID login
def verify_steam_login(query_params):
    validation_url = "https://steamcommunity.com/openid/login"
    query_params["openid.mode"] = "check_authentication"
    response = requests.post(validation_url, data=query_params)

    # Check if the response is valid
    if "is_valid:true" in response.text:
        claimed_id = query_params.get("openid.claimed_id")
        if claimed_id and isinstance(claimed_id, list):
            claimed_id = claimed_id[0]  # Extract the first element if it's a list
        if claimed_id:
            steam_id = claimed_id.split("/")[-1]  # Extract SteamID from claimed_id URL
            return steam_id
    return None

# Fetch user's Steam library
def fetch_steam_library(steam_id):
    url = "http://api.steampowered.com/IPlayerService/GetOwnedGames/v1/"
    params = {
        "key": STEAM_API_KEY,
        "steamid": steam_id,
        "include_appinfo": True,
    }
    response = requests.get(url, params=params)
    if response.ok:
        return response.json().get("response", {}).get("games", [])
    return []

def get_game_achievements(steam_id, app_id):
    """Fetch achievement data for a specific game."""
    url = "http://api.steampowered.com/ISteamUserStats/GetPlayerAchievements/v1/"
    params = {
        "key": STEAM_API_KEY,
        "steamid": steam_id,
        "appid": app_id,
    }
    try:
        response = requests.get(url, params=params)
        if response.ok:
            data = response.json()
            if data.get("playerstats", {}).get("success", False):
                return data["playerstats"].get("achievements", [])
    except:
        pass
    return None

# Initialize session state
if "steam_id" not in st.session_state:
    st.session_state.steam_id = None
if "game_categories" not in st.session_state:
    st.session_state.game_categories = {}
if "reviews" not in st.session_state:
    st.session_state.reviews = get_reviews()
if "element_counter" not in st.session_state:
    st.session_state.element_counter = 0

def get_unique_key(prefix="", game_name=""):
    """Generate a unique key for Streamlit elements"""
    st.session_state.element_counter += 1
    sanitized_name = ''.join(c for c in game_name if c.isalnum())  # Remove special characters
    return f"{prefix}-{sanitized_name}-{st.session_state.element_counter}"

# Sidebar Menu
with st.sidebar:
    st.title("Navigation")
    if st.session_state.steam_id is None:
        # If not logged in, only show login menu
        selected_menu = "Login Menu"
    else:
        # If logged in, show all menu options
        selected_menu = st.radio(
            "Select Menu",
            ["Login Menu", "Library Menu", "Sorted Menu"],
            key="navigation"
        )

# Main Content Area
st.title("Backlogr")

if selected_menu == "Login Menu":
    # Login Section
    if st.session_state.steam_id is None:
        st.write("To start tracking your backlog, log in with your Steam account.")

        if st.button("Login with Steam"):
            auth_url = authenticate_with_steam()
            st.markdown(f"[Click here to authenticate with Steam]({auth_url})", unsafe_allow_html=True)

        # Handle the OpenID callback after redirection
        query_params = st.query_params
        if query_params:
            if "openid.ns" in query_params:
                steam_id = verify_steam_login(query_params)
                if steam_id:
                    st.session_state.steam_id = steam_id
                    st.success(f"Logged in successfully! Steam ID: {steam_id}")
                else:
                    st.error("Steam login failed. Please try again.")
    else:
        st.write(f"You are logged in as Steam ID: {st.session_state.steam_id}")
        if st.button("Logout"):
            st.session_state.steam_id = None
            st.rerun()

elif selected_menu == "Library Menu" and st.session_state.steam_id:
    # Library Section
    st.write("### Your Library")
    library = fetch_steam_library(st.session_state["steam_id"])
    
    def is_game_categorized(game_name):
        """Check if a game exists in any category"""
        # Check Completed table
        completed_games = [g[0] for g in get_completed()]
        if game_name in completed_games:
            return True
        
        # Check Playing table
        if game_name in get_playing():
            return True
            
        # Check Not Played table
        if game_name in get_notplayed():
            return True
            
        return False
    
    if library:
        st.write(f"Total Games: {len(library)}")
        for game in library:
            name = game["name"]
            playtime = game["playtime_forever"]
            app_id = game["appid"]
            
            playtime_hours = round(playtime / 60, 1)
            
            # Only automatically categorize if the game isn't already in any category
            if name not in st.session_state.game_categories and not is_game_categorized(name):
                if playtime == 0:
                    add_notplayed(name)
                    st.session_state.game_categories[name] = "Not Played"
                else:
                    st.session_state.game_categories[name] = ""

            options = [
                "Select a category",
                "Completed",
                "Completed (100%)",
                "On Hold",
                "Playing",
                "Not Played",
            ]
            
            # Safely get the current category, defaulting to empty string if not found
            current_category = st.session_state.game_categories.get(name, "")
            
            selection = st.selectbox(
                f"{name} ({playtime_hours} hours played)",
                options,
                index=options.index(current_category) if current_category in options else 0,
                key=f"dropdown-{name}",
            )

            if selection != "Select a category" and selection != current_category:
                # Remove from previous category if it exists
                if name in [g[0] for g in get_completed()]:
                    remove_game("Completed", name)
                elif current_category == "Playing":
                    remove_game("Playing", name)
                elif current_category == "Not Played":
                    remove_game("NotPlayed", name)

                # Add to new category
                if selection == "Completed (100%)":
                    add_completed(name, "Yes", "No")
                elif selection == "On Hold":
                    add_completed(name, "No", "Yes")
                elif selection == "Completed":
                    add_completed(name, "No", "No")
                elif selection == "Playing":
                    add_playing(name)
                elif selection == "Not Played":
                    add_notplayed(name)

                st.session_state.game_categories[name] = selection
                st.rerun()
    else:
        st.error("Failed to fetch Steam library. Please try again.")

if selected_menu == "Sorted Menu" and st.session_state.steam_id:
    st.write("### Categorized Games")
    
    completed_games = get_completed()
    reviews = get_reviews()

    def handle_removal(category_name, game_name):
        """Handles removing a game from the specified category and updates the session state."""
        category_table_map = {
            "Completed": "Completed",
            "Playing": "Playing",
            "Not Played": "NotPlayed"
        }

        table_name = category_table_map.get(category_name)

        if table_name:
            # Remove from database
            if remove_game(table_name, game_name):
                # Clean up session state
                if game_name in st.session_state.game_categories:
                    del st.session_state.game_categories[game_name]
                if game_name in st.session_state.reviews:
                    del st.session_state.reviews[game_name]
                if game_name in st.session_state:
                    del st.session_state[game_name]
                
                return True
        return False

    def handle_rating_change(game_name, rating_key):
        """Handle rating changes with proper state management"""
        # Get the new rating value from session state using the slider's key
        if rating_key in st.session_state:
            new_rating = st.session_state[rating_key]
            # Update the review in the database
            add_or_update_review(game_name, new_rating)
            # Update the session state reviews
            st.session_state.reviews[game_name] = new_rating

    # Display Completed (100%) games
    with st.expander("**Completed (100%)**", expanded=True):
        hundred_percent_games = [game for game in completed_games if game[1] == "Yes"]
        if hundred_percent_games:
            for idx, game in enumerate(hundred_percent_games):
                col1, col2 = st.columns([4, 1])
                with col1:
                    current_rating = reviews.get(game[0], 0)
                    rating_key = f"rating_100_{sanitize_key(game[0])}_{idx}"
                    rating = st.slider(
                        f"Rate {game[0]}",
                        min_value=0,
                        max_value=5,
                        value=current_rating,
                        key=rating_key,
                        on_change=handle_rating_change,
                        args=(game[0], rating_key)
                    )
                with col2:
                    remove_key = f"remove_100_{sanitize_key(game[0])}_{idx}"
                    if st.button("Remove", key=remove_key):
                        if handle_removal("Completed", game[0]):
                            st.success(f"Removed {game[0]}")
                            st.rerun()
        else:
            st.write("No games in this category.")

    # Display On Hold games
    with st.expander("**On Hold**", expanded=True):
        on_hold_games = [game for game in completed_games if game[2] == "Yes"]
        if on_hold_games:
            for idx, game in enumerate(on_hold_games):
                col1, col2 = st.columns([4, 1])
                with col1:
                    current_rating = reviews.get(game[0], 0)
                    rating_key = f"rating_hold_{sanitize_key(game[0])}_{idx}"
                    rating = st.slider(
                        f"Rate {game[0]}",
                        min_value=0,
                        max_value=5,
                        value=current_rating,
                        key=rating_key,
                        on_change=handle_rating_change,
                        args=(game[0], rating_key)
                    )
                with col2:
                    remove_key = f"remove_hold_{sanitize_key(game[0])}_{idx}"
                    if st.button("Remove", key=remove_key):
                        if handle_removal("Completed", game[0]):
                            st.success(f"Removed {game[0]}")
                            st.rerun()
        else:
            st.write("No games in this category.")

    # Display regular Completed games
    with st.expander("**Completed**", expanded=True):
        regular_completed = [game for game in completed_games if game[1] == "No" and game[2] == "No"]
        if regular_completed:
            for idx, game in enumerate(regular_completed):
                col1, col2 = st.columns([4, 1])
                with col1:
                    current_rating = reviews.get(game[0], 0)
                    rating_key = f"rating_completed_{sanitize_key(game[0])}_{idx}"
                    rating = st.slider(
                        f"Rate {game[0]}",
                        min_value=0,
                        max_value=5,
                        value=current_rating,
                        key=rating_key,
                        on_change=handle_rating_change,
                        args=(game[0], rating_key)
                    )
                with col2:
                    remove_key = f"remove_completed_{sanitize_key(game[0])}_{idx}"
                    if st.button("Remove", key=remove_key):
                        if handle_removal("Completed", game[0]):
                            st.success(f"Removed {game[0]}")
                            st.rerun()
        else:
            st.write("No games in this category.")

    # Display Playing games
    with st.expander("**Playing**", expanded=True):
        playing_games = get_playing()
        if playing_games:
            for idx, game in enumerate(playing_games):
                col1, col2 = st.columns([4, 1])
                with col1:
                    current_rating = reviews.get(game, 0)
                    rating_key = f"rating_playing_{sanitize_key(game)}_{idx}"
                    rating = st.slider(
                        f"Rate {game}",
                        min_value=0,
                        max_value=5,
                        value=current_rating,
                        key=rating_key,
                        on_change=handle_rating_change,
                        args=(game, rating_key)
                    )
                with col2:
                    remove_key = f"remove_playing_{sanitize_key(game)}_{idx}"
                    if st.button("Remove", key=remove_key):
                        if handle_removal("Playing", game):
                            st.success(f"Removed {game}")
                            st.rerun()
        else:
            st.write("No games in this category.")

    # Display Not Played games
    with st.expander("**Not Played**", expanded=True):
        not_played_games = get_notplayed()
        if not_played_games:
            for idx, game in enumerate(not_played_games):
                col1, col2 = st.columns([4, 1])
                with col1:
                    current_rating = reviews.get(game, 0)
                    rating_key = f"rating_notplayed_{sanitize_key(game)}_{idx}"
                    rating = st.slider(
                        f"Rate {game}",
                        min_value=0,
                        max_value=5,
                        value=current_rating,
                        key=rating_key,
                        on_change=handle_rating_change,
                        args=(game, rating_key)
                    )
                with col2:
                    remove_key = f"remove_notplayed_{sanitize_key(game)}_{idx}"
                    if st.button("Remove", key=remove_key):
                        if handle_removal("Not Played", game):
                            st.success(f"Removed {game}")
                            st.rerun()
        else:
            st.write("No games in this category.")