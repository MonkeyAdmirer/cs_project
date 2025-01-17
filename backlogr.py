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

    # Create Completed table with fields for 100% and On Hold status
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
if "game_categories" not in st.session_state:
    st.session_state.game_categories = {}

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
        st.write("### Categorized Games")
        
        # Get all completed games
        completed_games = get_completed()
        
        # Display Completed (100%) games
        st.write("**Completed (100%)**")
        hundred_percent_games = [game for game in completed_games if game[1] == "Yes"]
        if hundred_percent_games:
            for game in hundred_percent_games:
                if st.button(f"Remove {game[0]}", key=f"remove-100-{game[0]}"):
                    remove_game("Completed", game[0])
                    st.session_state.game_categories[game[0]] = ""
                    st.rerun()
        else:
            st.write("No games in Completed (100%) category.")
        
        # Display On Hold games
        st.write("**On Hold**")
        on_hold_games = [game for game in completed_games if game[2] == "Yes"]
        if on_hold_games:
            for game in on_hold_games:
                if st.button(f"Remove {game[0]}", key=f"remove-hold-{game[0]}"):
                    remove_game("Completed", game[0])
                    st.session_state.game_categories[game[0]] = ""
                    st.rerun()
        else:
            st.write("No games in On Hold category.")
        
        # Display regular Completed games
        st.write("**Completed**")
        regular_completed = [game for game in completed_games if game[1] == "No" and game[2] == "No"]
        if regular_completed:
            for game in regular_completed:
                if st.button(f"Remove {game[0]}", key=f"remove-completed-{game[0]}"):
                    remove_game("Completed", game[0])
                    st.session_state.game_categories[game[0]] = ""
                    st.rerun()
        else:
            st.write("No games in Completed category.")

        # Display Playing games
        st.write("**Playing**")
        playing_games = get_playing()
        if playing_games:
            for game in playing_games:
                if st.button(f"Remove {game}", key=f"remove-playing-{game}"):
                    remove_game("Playing", game)
                    st.session_state.game_categories[game] = ""
                    st.rerun()
        else:
            st.write("No games in Playing category.")

        # Display Not Played games
        st.write("**Not Played**")
        not_played_games = get_notplayed()
        if not_played_games:
            for game in not_played_games:
                if st.button(f"Remove {game}", key=f"remove-notplayed-{game}"):
                    remove_game("NotPlayed", game)
                    st.session_state.game_categories[game] = ""
                    st.rerun()
        else:
            st.write("No games in Not Played category.")

        # Display game library with categorization options
        st.write(f"\n### Your Library ({len(library)} games)")
        for game in library:
            name = game["name"]
            playtime = game["playtime_forever"]

            if name not in st.session_state.game_categories:
                st.session_state.game_categories[name] = ""

            options = [
                "Select a category",
                "Completed",
                "Completed (100%)",
                "On Hold",
                "Playing",
                "Not Played",
            ]
            
            selection = st.selectbox(
                f"{name} ({playtime} minutes played)",
                options,
                index=options.index(st.session_state.game_categories[name])
                if st.session_state.game_categories[name] in options
                else 0,
                key=f"dropdown-{name}",
            )

            if selection != "Select a category" and selection != st.session_state.game_categories[name]:
                # Remove from previous category if it exists
                if name in [g[0] for g in completed_games]:
                    remove_game("Completed", name)
                elif st.session_state.game_categories[name] == "Playing":
                    remove_game("Playing", name)
                elif st.session_state.game_categories[name] == "Not Played":
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
else:
    st.write("Please log in to view and manage your categorized games.")