"""
Backlogr: A Steam library management tool with game categorization, reviews, and visual statistics.

Features:
1. Login using Steam OAuth.
2. Automatically sort games based on playtime.
3. Allow users to categorize games manually into "Completed", "Playing", "Not Played", etc.
4. Provide a review system with a slider for ratings.
5. Visualize game statistics by genre and playtime distribution.
"""

# External imports
import streamlit as st
import requests
import urllib.parse
import sqlite3
# To create visual representations
import matplotlib.pyplot as plt
import numpy as np

def sanitize_key(text):
    """
    Sanitize a given text to generate a clean and safe key for use in Streamlit elements.

    This function removes all non-alphanumeric characters from the input text, ensuring that the 
    resulting key is compatible with Streamlit's key requirements and free of special characters 
    that could cause issues.

    Args:
        text (str): The input string to be sanitized.

    Returns:
        str: A sanitized string containing only alphanumeric characters.
    """
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
    """Fetch basic game information without genres"""
    url = "http://api.steampowered.com/IPlayerService/GetOwnedGames/v1/"
    params = {
        "key": STEAM_API_KEY,
        "steamid": steam_id,
        "include_appinfo": True,
        "include_played_free_games": True
    }
    try:
        response = requests.get(url, params=params)
        if response.ok:
            return response.json().get("response", {}).get("games", [])
        return []
    except Exception as e:
        print(f"Error fetching library: {e}")
        return []

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
            ["Login Menu", "Library Menu", "Sorted Menu", "Visual Stats"],  # Added "Visual Stats"
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
        """
        Check if a game already exists in any category.
        Prevents duplicate categorization during automatic sorting.
        """
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
        """
        Handles removing a game from the specified category.
        Updates the session state and database.

        Args:
            category_name (str): The category from which to remove the game.
            game_name (str): The name of the game to remove.

        Returns:
            bool: True if successful, False otherwise.
        """
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

elif selected_menu == "Visual Stats" and st.session_state.steam_id:
    st.write("### Genre Statistics")
    
    # Import required libraries
    import matplotlib.pyplot as plt
    import numpy as np
    
    # Fetch library if not already in session state
    library = fetch_steam_library(st.session_state.steam_id)
    
    if library:
        st.write(f"Analyzing {len(library)} games in your library...")
        
        # Process genre data
        genre_data = {
            'Action': {'total_playtime': 0, 'game_count': 0},
            'Adventure': {'total_playtime': 0, 'game_count': 0},
            'RPG': {'total_playtime': 0, 'game_count': 0},
            'Strategy': {'total_playtime': 0, 'game_count': 0},
            'Simulation': {'total_playtime': 0, 'game_count': 0},
            'Sports': {'total_playtime': 0, 'game_count': 0},
            'Indie': {'total_playtime': 0, 'game_count': 0},
            'Other': {'total_playtime': 0, 'game_count': 0}
        }
        
        for game in library:
            playtime = game.get('playtime_forever', 0) / 60  # Convert to hours
            
            # Expanded keyword lists for better genre detection
            action_keywords = {'action', 'shooter', 'fps', 'fight', 'combat', 'battle', 'warfare', 'war', 'dead', 'doom', 
                             'counter', 'strike', 'call of duty', 'battlefield', 'halo', 'metal gear', 'sleeping dogs', 'turok',
                             'resident evil', 'hitman', 'portal', 'borderlands', 'space marine', 'wukong', 'sekiro', 'metro', 'max payne', 'half-life'}
            
            adventure_keywords = {'adventure', 'quest', 'journey', 'exploration', 'tomb raider', 'uncharted', 's.t.a.l.k.e.r.', 'red dead redemption',
                                'assassin', 'walking', 'life is strange', 'telltale', 'story', 'tsushima', 'last of us', 'dying light', }
            
            rpg_keywords = {'rpg', 'role', 'fantasy', 'witcher', 'elder scrolls', 'fallout', 'final fantasy', 
                           'mass effect', 'dragon', 'souls', 'persona', 'dark souls', 'skyrim', 'diablo', 'chrono trigger', # goated game
                           'kingdom', 'divinity', 'baldur', 'souls', 'deus ex', 'elden', 'path of exile', 'dragon', 'cyberpunk'}
            
            strategy_keywords = {'strategy', 'tactic', 'command', 'civilization', 'total war', 'hearts of iron',
                               'crusader kings', 'age of empires', 'starcraft', 'dawn of war', 'xcom', 'stellaris',
                               'city builder', 'management', 'defense', 'tower'}
            
            simulation_keywords = {'simulation', 'simulator', 'tycoon', 'farm', 'euro truck', 'flight', 'sims',
                                 'cities:', 'city:', 'planet', 'zoo', 'hospital', 'cooking', 'fishing', 'train',
                                 'building', 'construction'}
            
            sports_keywords = {'sports', 'football', 'soccer', 'basketball', 'nba', 'fifa', 'baseball', 'racing',
                             'race', 'car', 'drift', 'rally', 'forza', 'need for speed', 'dirt', 'golf', 'tennis',
                             'skateboard', 'skate', 'tony hawk', 'motorsport', 'rugby', 'hockey'}
            
            indie_keywords = {'indie', 'pixel', 'roguelike', 'rogue', 'platformer', 'puzzle', 'stardew', 'terraria',
                            'minecraft', 'undertale', 'hollow knight', 'binding of isaac', 'inside', 'limbo', 
                            'celeste', 'hades', "don't starve", 'castle crashers', 'balatro'}

            name = game.get('name', '').lower()
            
            # More sophisticated genre detection
            if any(keyword in name for keyword in action_keywords):
                genre = 'Action'
            elif any(keyword in name for keyword in adventure_keywords):
                genre = 'Adventure'
            elif any(keyword in name for keyword in rpg_keywords):
                genre = 'RPG'
            elif any(keyword in name for keyword in strategy_keywords):
                genre = 'Strategy'
            elif any(keyword in name for keyword in simulation_keywords):
                genre = 'Simulation'
            elif any(keyword in name for keyword in sports_keywords):
                genre = 'Sports'
            elif any(keyword in name for keyword in indie_keywords):
                genre = 'Indie'
            else:
                genre = 'Other'
            
            genre_data[genre]['total_playtime'] += playtime
            genre_data[genre]['game_count'] += 1
        
        # Calculate average playtime for each genre
        avg_playtime = {
            genre: data['total_playtime'] / data['game_count'] if data['game_count'] > 0 else 0
            for genre, data in genre_data.items()
        }
        
        # Remove genres with no games
        avg_playtime = {k: v for k, v in avg_playtime.items() if v > 0}
        
        # Create the visualizations with dark theme
        plt.style.use('dark_background')
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 7))
        
        # Set figure background color to match website
        fig.patch.set_facecolor('#1E1E1E')
        ax1.set_facecolor('#1E1E1E')
        ax2.set_facecolor('#1E1E1E')
        
        # Pie chart
        values = list(avg_playtime.values())
        labels = list(avg_playtime.keys())
        
        if values:  # Only create charts if we have data
            wedges, texts, autotexts = ax1.pie(
                values,
                labels=labels,
                autopct='%1.1f%%',
                textprops={'fontsize': 8, 'color': 'white'},
                colors=plt.cm.Set3.colors
            )
            ax1.set_title('Distribution of Average Playtime by Genre', color='white')
            
            # Bar chart
            y_pos = np.arange(len(labels))
            game_counts = [genre_data[genre]['game_count'] for genre in labels]
            
            ax2.barh(y_pos, values, color=plt.cm.Set3.colors)
            ax2.set_yticks(y_pos)
            ax2.set_yticklabels(labels, color='white')
            ax2.invert_yaxis()
            ax2.set_xlabel('Average Hours Played', color='white')
            ax2.set_title('Average Playtime by Genre', color='white')
            
            # Make axis labels white
            ax2.tick_params(colors='white')
            ax2.xaxis.label.set_color('white')
            
            # Add game count annotations in white
            for i, v in enumerate(values):
                ax2.text(v + 1, i, f'({game_counts[i]} games)', va='center', fontsize=8, color='white')
            
            plt.tight_layout()
            
            # Display the chart in Streamlit
            st.pyplot(fig)
            
            # Display detailed statistics
            st.write("### Detailed Statistics")
            
            # Create a two-column layout for statistics
            col1, col2 = st.columns(2)
            
            # Sort genres by average playtime
            sorted_stats = sorted(
                [(genre, avg_playtime[genre], genre_data[genre]['game_count']) 
                 for genre in labels],
                key=lambda x: x[1],
                reverse=True
            )
            
            # Split the stats between columns
            mid_point = len(sorted_stats) // 2
            
            with col1:
                for genre, avg_time, count in sorted_stats[:mid_point]:
                    st.write(f"**{genre}**: {avg_time:.1f} hours avg. ({count} games)")
                    
            with col2:
                for genre, avg_time, count in sorted_stats[mid_point:]:
                    st.write(f"**{genre}**: {avg_time:.1f} hours avg. ({count} games)")
        else:
            st.warning("No playtime data available for analysis.")
            
    else:
        st.error("Failed to fetch library data. Please try again.")
