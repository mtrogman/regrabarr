import sys
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Select, View, Button
from datetime import datetime
import requests
import json
import yaml
import logging

bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())
logging.basicConfig(stream=sys.stdout, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def getConfig(file):
    with open(file, 'r') as yaml_file:
        config = yaml.safe_load(yaml_file)
    return config

config_location = "/config/config.yml"
config = getConfig(config_location)
bot_token = config['bot']['token']
radarr_api_key = config['radarr']['api_key']
radarr_base_url = config['radarr']['url']
sonarr_api_key = config['sonarr']['api_key']
sonarr_base_url = config['sonarr']['url']


# Replace async with synchronous requests
def perform_request(method, url, data=None, headers=None):
    try:
        if method == 'GET':
            response = requests.get(url, headers=headers)
        elif method == 'POST':
            response = requests.post(url, json=data, headers=headers)
        elif method == 'DELETE':
            response = requests.delete(url, headers=headers)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

        return response

    except requests.exceptions.RequestException as e:
        print(f"Error performing {method} request: {e}")
        logging.error(f"Error performing {method} request: {e}")
        return None

class ConfirmButtonsMovie(View):
    def __init__(self, interaction, movie_data):
        super().__init__()
        regrab_button = Button(style=discord.ButtonStyle.primary, label="Regrab")
        regrab_button.callback = self.regrab_callback
        self.add_item(regrab_button)

        cancel_button = Button(style=discord.ButtonStyle.danger, label="Cancel")
        cancel_button.callback = self.cancel_callback
        self.add_item(cancel_button)

        self.interaction = interaction
        self.movie_data = movie_data

    async def regrab_callback(self, button):
        # Use self.movie_data to access movie details
        movie_title = self.movie_data['title']
        movie_year = self.movie_data['year']
        movie_id = self.movie_data['id']
        movie_tmdb = self.movie_data['tmdbId']

        await self.interaction.delete_original_response()

        # Delete the movie
        delete_url = f"{radarr_base_url}/movie/{movie_id}?deleteFiles=true&apikey={radarr_api_key}"
        delete_response = perform_request('DELETE', delete_url)
        print(f"Deleted {movie_title} with a response of {delete_response}")
        logging.info(f"Deleted {movie_title} with a response of {delete_response}")

        # Add the movie back (and search for it)
        add_url = f"{radarr_base_url}/movie?apikey={radarr_api_key}"
        data = {
            "tmdbId": movie_tmdb,
            "monitored": True,
            "qualityProfileId": 1,
            "minimumAvailability": "released",
            "addOptions": {
                "searchForMovie": True
            },
            "rootFolderPath": "/movies",
            "title": movie_title
        }
        headers = {
            "Content-Type": "application/json"
        }
        add_response = perform_request('POST', add_url, data, headers)
        print(f"Added {movie_title} with a response of {add_response}")
        logging.info(f"Added {movie_title} with a response of {add_response}")

        # Respond to discord
        await self.interaction.followup.send(content=f"`{self.interaction.user.name} your request to delete and redownload {movie_title}` ({movie_year}) is being processed.")

    # Cancel just responds with msg
    async def cancel_callback(self, button):
        await self.interaction.delete_original_response()
        await self.interaction.followup.send(content="Cancelled the request.", ephemeral=True)
class ConfirmButtonsSeries(View):
    def __init__(self, interaction, selected_episode_data):
        super().__init__()
        regrab_button = Button(style=discord.ButtonStyle.primary, label="Regrab")
        regrab_button.callback = self.regrab_callback
        self.add_item(regrab_button)

        cancel_button = Button(style=discord.ButtonStyle.danger, label="Cancel")
        cancel_button.callback = self.cancel_callback
        self.add_item(cancel_button)

        self.interaction = interaction
        self.selected_episode_data = selected_episode_data

    async def regrab_callback(self, button):
        # Checks if episodeFileId is 0 and if it is doesn't delete it since it's not there.
        if self.selected_episode_data['episodeFileId'] != 0:
            # Delete the show
            delete_url = f"{sonarr_base_url}/episodefile/{self.selected_episode_data['episodeFileId']}?apikey={sonarr_api_key}"
            try:
                delete_response = requests.delete(delete_url)
                delete_response.raise_for_status()  # Raise an exception for non-200 responses
                print(f"Deleted EpisodeFileID {self.selected_episode_data['episodeFileId']} with a response of {delete_response.status_code}")
                logging.info(f"Deleted EpisodeFileID {self.selected_episode_data['episodeFileId']} with a response of {delete_response.status_code}")
            except requests.exceptions.RequestException as e:
                print(f"Error deleting EpisodeFileID {self.selected_episode_data['episodeFileId']}: {e}")
                logging.error(f"Error deleting EpisodeFileID {self.selected_episode_data['episodeFileId']}: {e}")
        else:
            print(f"No Episode Found")
            logging.info(f"No Episode Found")

        # Search for the episode
        search_url = f"{sonarr_base_url}/command/"
        headers = {
            "Content-Type": "application/json",
            "X-Api-Key": sonarr_api_key
        }
        data = {
            "episodeIds": [self.selected_episode_data['episodeId']],
            "name": "EpisodeSearch",
        }

        try:
            search_response = requests.post(search_url, headers=headers, json=data)
            search_response.raise_for_status()  # Raise an exception for non-200 responses
            print(f"Searching for EpisodeID {self.selected_episode_data['episodeId']} with a response of {search_response.status_code}")
            logging.info(f"Searching for EpisodeID {self.selected_episode_data['episodeId']} with a response of {search_response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"Error searching for EpisodeID {self.selected_episode_data['episodeId']}: {e}")
            logging.error(f"Error searching for EpisodeID {self.selected_episode_data['episodeId']}: {e}")

        await self.interaction.delete_original_response()
        await self.interaction.followup.send(content=f"`{self.interaction.user.name} your request to (re)grab {self.selected_episode_data['series']}` Season {self.selected_episode_data['season']}) Episode {self.selected_episode_data['episode']} is being processed.")

    # Cancel just responds with msg
    async def cancel_callback(self, button):
        await self.interaction.delete_original_response()
        await self.interaction.followup.send(content="Cancelled the request.", ephemeral=True)

# View & Select required to build out Discord Dropdown.
class MovieSelectorView(View):
    def __init__(self, search_results):
        super().__init__()
        self.search_results = search_results
        self.add_item(MovieSelector(search_results))
class MovieSelector(Select):
    def __init__(self, search_results):
        self.search_results = search_results
        options = [
            discord.SelectOption(
                label=movie['title'],
                value=str(idx),
                description=str(movie['year'])
            )
            for idx, movie in enumerate(search_results)
        ]
        super().__init__(placeholder="Please select a movie", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        selected_movie_index = int(self.values[0])
        selected_movie_data = self.search_results[selected_movie_index]

        movie_title = selected_movie_data['title']
        movie_year = selected_movie_data['year']
        movie_overview = selected_movie_data['overview']

        confirmation_message = (
            f"Please confirm that you would like to regrab the following movie:\n"
            f"**Title:** {movie_title}\n"
            f"**Year:** {movie_year}\n"
            f"**Overview:** {movie_overview}\n"
        )

        confirmation_view = ConfirmButtonsMovie(interaction, selected_movie_data)

        await interaction.response.edit_message(
            content=confirmation_message,
            view=confirmation_view
        )
# Call to get list of top 10 Movies found that match the search and to put into Discord Dropdown
async def fetch_movie(movie_name):
    url = f"{radarr_base_url}/movie/lookup?term={movie_name}"
    headers = {"X-Api-Key": radarr_api_key}

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise an exception for non-200 responses

        if response.status_code == 200:
            movie_list = response.json()
            return movie_list[:10]  # Return the first 10 movies
        else:
            return []
    except requests.exceptions.RequestException as e:
        print(f"Error fetching movie data: {e}")
        logging.error(f"Error fetching movie data: {e}")
        return []

# View & Select required to build out TV Series Discord Dropdown.
class SeriesSelectorView(View):
    def __init__(self, series_results):
        super().__init__()
        self.series_results = series_results
        self.add_item(TVSeriesSelector(series_results))
class TVSeriesSelector(Select):
    def __init__(self, series_results):
        self.series_results = series_results
        options = [
            discord.SelectOption(
                label=series['title'],
                value=str(idx),
                description=str(series['year'])
            )
            for idx, series in enumerate(series_results)
        ]
        super().__init__(placeholder="Please select a TV series", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        selected_series_index = int(self.values[0])
        selected_series_data = self.series_results[selected_series_index]
        seasons_results = await fetch_seasons(selected_series_data)
        global seriesId
        seriesId = selected_series_data['id']

        await interaction.response.edit_message(content="Please select a season", view=SeasonSelectorView(seasons_results))
# Call to get list of top 10 TV Series found that match the search and to put into Discord Dropdown
async def fetch_series(series_name):
    url = f"{sonarr_base_url}/series/lookup?term={series_name}"
    headers = {"X-Api-Key": sonarr_api_key}

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise an exception for non-200 responses

        if response.status_code == 200:
            series_list = response.json()
            return series_list[:10]  # Return the first 10 series
        else:
            return []
    except requests.exceptions.RequestException as e:
        print(f"Error fetching series data: {e}")
        logging.error(f"Error fetching series data: {e}")
        return []

# View & Select required to build out TV Season Discord Dropdown.
class SeasonSelectorView(View):
    def __init__(self, season_results):
        super().__init__()
        self.series_results = season_results
        self.add_item(SeasonSelector(season_results))
class SeasonSelector(Select):
    def __init__(self, seasons_results):
        self.seasons_results = seasons_results
        options = [
            discord.SelectOption(
                label=f"Season {season['seasonNumber']}",
                value=str(idx)
            )
            for idx, season in enumerate(seasons_results)
        ]
        super().__init__(placeholder="Please select a season", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        selected_season_index = int(self.values[0])
        selected_season_number = self.seasons_results[selected_season_index]['seasonNumber']
        global episode_results
        episode_results = await fetch_episodes(selected_season_number)
        await interaction.response.edit_message(content="Please select an episode", view=EpisodeSelectorView(episode_results))
# Call to get list of seasons within the series and put into Discord Dropdown
async def fetch_seasons(selected_series_data, ):
    seasons = selected_series_data.get('seasons', [])
    # Filter out season 0 which is extras
    seasons = [season for season in seasons if season['seasonNumber'] != 0]

    return seasons

# View & Select required to build out TV Episode Discord Dropdown.
class EpisodeSelectorView(View):
    def __init__(self, episode_results):
        super().__init__()
        self.series_results = episode_results
        self.add_item(EpisodeSelector(episode_results))
class EpisodeSelector(Select):
    def __init__(self, episodes_results):
        options = []
        current_date = datetime.now().date()

        for idx, episode in enumerate(episodes_results):
            episode_number = episode['episodeNumber']
            episode_name = f"Episode {episode_number}"
            air_date_str = episode.get('airDate', 'Air Date Unknown')

            # Check if the episode has already aired and parse the air date
            try:
                air_date = datetime.strptime(air_date_str, "%Y-%m-%d").date()
                is_past_air_date = air_date <= current_date
            except ValueError:
                is_past_air_date = False

            # Exclude episodes that haven't aired yet
            if is_past_air_date:
                formatted_description = f"Air Date: {air_date.strftime('%b %d %Y')}"
                options.append(discord.SelectOption(
                    label=episode_name,
                    value=str(idx),
                    description=formatted_description
                ))

        super().__init__(placeholder="Please select an episode", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        selected_episode_id = int(self.values[0])
        selected_episode_data_json = await fetch_episode_details(selected_episode_id)

        # Parse the JSON string into a dictionary
        selected_episode_data = json.loads(selected_episode_data_json)

        # Construct the confirmation message with episode details
        confirmation_message = (
            f"Please confirm that you would like to regrab the following episode:\n"
            f"**Series:** {selected_episode_data['series']}\n"
            f"**Season:** Season {selected_episode_data['season']}\n"
            f"**Episode:** Episode {selected_episode_data['episode']}\n"
            f"**Episode:** Title {selected_episode_data['title']}\n"
            f"**Air Date:** {selected_episode_data['airDate']}\n" 
            f"**Episode:** Overview {selected_episode_data['overview']}\n"
        )

        # Create and display the ConfirmButtons view for confirmation
        confirmation_view = ConfirmButtonsSeries(interaction, selected_episode_data)
        await interaction.response.edit_message(content=confirmation_message, view=confirmation_view)
# Call to get list of episodes within the season and put into Discord Dropdown
async def fetch_episodes(selected_season_number):
    url = f"{sonarr_base_url}/episode"
    parameters = {
        'seriesId': seriesId,
        'seasonNumber': selected_season_number
    }
    headers = {"X-Api-Key": sonarr_api_key}

    try:
        response = requests.get(url, headers=headers, params=parameters)
        response.raise_for_status()  # Raise an exception for non-200 responses

        if response.status_code == 200:
            return response.json()
        else:
            print(f"Response was not a 200 (was a {response.status_code}) for fetch episode of {seriesId} Season {selected_season_number}")
            logging.warn(f"Response was not a 200 (was a {response.status_code}) for fetch episode of {seriesId} Season {selected_season_number}")
            return []
    except requests.exceptions.RequestException as e:
        print(f"Error fetching episode data: {e}")
        logging.error(f"Error fetching episode data: {e}")
        return []

# Call to get details of the episode selected to populate the confirmation button info
async def fetch_episode_details(episode_num):
    episode_details = episode_results[episode_num]

    # Create a dictionary to store the parameters
    episode_info = {
        "series": episode_details['title'],
        "season": episode_details['seasonNumber'],
        "episode": episode_details['episodeNumber'],
        "title": episode_details['title'],
        "overview": episode_details['overview'],
        "episodeFileId": episode_details['episodeFileId'],
        "episodeId": episode_details['id'],
        "airDate": episode_details['airDate']
    }
    episode_json = json.dumps(episode_info)
    return episode_json


# Variable to store the selected item
selected_movie = None
selected_series = None


# Sync commands with discord
@bot.event
async def on_ready():
    print(f"Bot is Up and Ready!")
    logging.info('Bot is Up and Ready!')
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
        logging.info(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(e)
        logging.error(f"{e}")

# Bot command to "regrab" (delete and search) for movie
@bot.tree.command(name="regrab_movie", description="Will delete and redownload selected movie")
@app_commands.describe(movie="What movie should we regrab?")
async def regrab_movie(ctx, *, movie: str):
    movie_results = await fetch_movie(movie)
    if not movie_results:
        await ctx.response.send_message(
            f"{ctx.user.name} no movie matching the following title was found: {movie}")
        return
    global selected_movie
    await ctx.response.send_message("Select a movie to regrab", view=MovieSelectorView(movie_results), ephemeral=True)

# Bot command to "regrab" (delete and search) for TV Show Episode
@bot.tree.command(name="regrab_episode", description="Will delete and redownload selected episode")
@app_commands.describe(series="What TV series should we regrab from?")
async def regrab_episode(ctx, *, series: str):
    # Fetch TV series matching the input series name
    series_results = await fetch_series(series)
    if not series_results:
        await ctx.response.send_message(f"No TV series matching the title: {series}")
        return
    global selected_series
    await ctx.response.send_message("Select a TV series to regrab", view=SeriesSelectorView(series_results), ephemeral=True)

bot.run(bot_token)
