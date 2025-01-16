# External imports
import streamlit as st
import requests
import urllib.parse
import sqlite3

# Database Code: Initializes the database and defines methods to interact with it
def initializeDB():
    # Create tables for Completed, Playing, and Not Played games
    connection = sqlite3.connect('./peyton.db')
    cursor = connection.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Completed (
            name TEXT NOT NULL,
            hundredpercent TEXT NOT NULL,  -- Indicates if the game has 100% achievements
            hold TEXT NOT NULL  -- Indicates if the game is on hold
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
    connection.commit()
    connection.close()

def get_completed():
    # Fetch all games from the Completed table, including 100% and hold status
    connection = sqlite3.connect('./peyton.db')
    cursor = connection.cursor()
    result = cursor.execute("SELECT * FROM Completed;").fetchall()
    connection.close()
    return result

def get_playing():
    # Fetch all games from the Playing table
    connection = sqlite3.connect('./peyton.db')
    cursor = connection.cursor()
    result = cursor.execute("SELECT name FROM Playing;").fetchall()
    connection.close()
    return result

def get_notplayed():
    # Fetch all games from the Not Played table
    connection = sqlite3.connect('./peyton.db')
    cursor = connection.cursor()
    result = cursor.execute("SELECT name FROM NotPlayed;").fetchall()
    connection.close()
    return result

def add_completed(name, hundred, hold):
    # Add a game to the Completed table with its 100% and hold status
    connection = sqlite3.connect('./peyton.db')
    cursor = connection.cursor()
    cursor.execute(
        "INSERT INTO Completed (name, hundredpercent, hold) VALUES (?, ?, ?);",
        (name, hundred, hold),
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

def is_duplicate(name):
    # Check if a game is already categorized in any table
    categorized_games = set(get_completed() + get_playing() + get_notplayed())
    return name in categorized_games

# Function to remove a game from a specific category
def remove_game(table_name, game_name):
    connection = sqlite3.connect('./peyton.db')
    cursor = connection.cursor()
    cursor.execute(f"DELETE FROM {table_name} WHERE name = ?", (game_name,))
    connection.commit()
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

# Initialize session state
if "steam_id" not in st.session_state:
    st.session_state.steam_id = None

# Streamlit App
st.title("Backlogr")

# Login button and redirection
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
    st.write(f"Logged in as Steam ID: {st.session_state.steam_id}")

# Fetch and categorize the Steam library
if st.session_state.get("steam_id"):
    st.write("Fetching your Steam library...")
    library = fetch_steam_library(st.session_state["steam_id"])
    if library:
        categorized_games = set([row[0] for row in get_completed()] + get_playing() + get_notplayed())
        st.write(f"Found {len(library)} games in your library:")

        for game in library:
            name = game["name"]
            playtime = game["playtime_forever"]

            # Skip already categorized games
            if name in categorized_games:
                continue

            # Dropdown for categorizing games
            options = ["Select a category", "Completed (100%)", "On Hold", "Playing", "Not Played"]
            selection = st.selectbox(f"{name} ({playtime} minutes played)", options, key=name)

           # Add the game to the selected category
            if selection == "Completed (100%)":
                add_completed(name, "Yes", "No")
                st.session_state["refresh"] = not st.session_state.get("refresh", False)  # Simulate rerun
            elif selection == "On Hold":
                add_completed(name, "No", "Yes")
                st.session_state["refresh"] = not st.session_state.get("refresh", False)
            elif selection == "Playing":
                add_playing(name)
                st.session_state["refresh"] = not st.session_state.get("refresh", False)
            elif selection == "Not Played":
                add_notplayed(name)
                st.session_state["refresh"] = not st.session_state.get("refresh", False)
    else:
        st.write("It looks like your Steam library is private or no games were found. Please make your library public in your Steam settings.")

# Display categorized games and allow users to remove them from categories
st.write("### Categorized Games")
for category, fetch_func, remove_func in [
    ("Completed (100%)", get_completed, lambda name: remove_game("Completed", name)),
    ("Playing", get_playing, lambda name: remove_game("Playing", name)),
    ("Not Played", get_notplayed, lambda name: remove_game("NotPlayed", name)),
]:
    st.write(f"**{category}**")
    games = fetch_func()
    for game in games:
        game_name = game[0] if isinstance(game, tuple) else game  # Handle tuple or single value
        if st.button(f"Remove {game_name}", key=f"remove-{category}-{game_name}"):
            remove_func(game_name)
            # Clear cache or reset Streamlit's session state for proper updates
            if "removed_game" not in st.session_state:
                st.session_state["removed_game"] = []
            st.session_state["removed_game"].append(game_name)

# Clear cached data and refresh the UI without rerunning the entire app
if "removed_game" in st.session_state:
    st.session_state["removed_game"] = []
    st.cache_data.clear()  # Clear cached data
    st.experimental_update_report_ctx()  # Streamlit-specific method to refresh UI state so the updated categories can be displayed