import sys
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Select, View, Button
from datetime import datetime
import requests
import yaml
import logging

# Initialize bot and logging
bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())
logging.basicConfig(stream=sys.stdout, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# Load configuration
def get_config(file):
    with open(file, 'r') as yaml_file:
        config = yaml.safe_load(yaml_file)
    return config


config_location = "/config/config.yml"
config = get_config(config_location)
bot_token = config['bot']['token']
radarr_api_key = config['radarr']['api_key']
radarr_base_url = config['radarr']['url'].rstrip('/')
sonarr_api_key = config['sonarr']['api_key']
sonarr_base_url = config['sonarr']['url'].rstrip('/')

regrab_movie_command_name = config['bot'].get('regrab_movie', 'regrab_movie')
regrab_episode_command_name = config['bot'].get('regrab_episode', 'regrab_episode')

# Requests Session
session = requests.Session()

def get_quality_profiles(base_url, api_key):
    url = f"{base_url}/qualityprofile?apikey={api_key}"
    try:
        response = session.get(url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to get quality profiles: {e}")
        return []

def get_root_folders(base_url, api_key):
    url = f"{base_url}/rootfolder?apikey={api_key}"
    try:
        response = session.get(url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to get root folders: {e}")
        return []


def select_root_folder(root_folders):
    if root_folders:
        return root_folders[0]['path']
    else:
        raise Exception("No root folders available")


try:
    sonarr_root_folders = get_root_folders(sonarr_base_url, sonarr_api_key)
    radarr_root_folders = get_root_folders(radarr_base_url, radarr_api_key)

    sonarr_root_folder_path = select_root_folder(sonarr_root_folders)
    radarr_root_folder_path = select_root_folder(radarr_root_folders)

    radarr_quality_profiles = get_quality_profiles(radarr_base_url, radarr_api_key)
    sonarr_quality_profiles = get_quality_profiles(sonarr_base_url, sonarr_api_key)

    radarr_quality_profile_id = radarr_quality_profiles[0]['id']
    sonarr_quality_profile_id = sonarr_quality_profiles[0]['id']

    logging.info(f"Selected Sonarr Root Folder Path: {sonarr_root_folder_path}")
    logging.info(f"Selected Radarr Root Folder Path: {radarr_root_folder_path}")
    logging.info(f"Selected Radarr Quality Profile ID: {radarr_quality_profile_id}")
    logging.info(f"Selected Sonarr Quality Profile ID: {sonarr_quality_profile_id}")

except Exception as e:
    logging.error(f"Error: {e}")
    sys.exit(1)


def perform_request(method, url, data=None, headers=None, params=None):
    try:
        if method == 'GET':
            response = session.get(url, headers=headers, params=params)
        elif method == 'POST':
            response = session.post(url, json=data, headers=headers)
        elif method == 'DELETE':
            response = session.delete(url, headers=headers)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")
        response.raise_for_status()
        return response
    except requests.exceptions.RequestException as e:
        logging.error(f"Error performing {method} request: {e}")
        return None


class ConfirmButtonsMovie(View):
    def __init__(self, interaction, media_info):
        super().__init__()
        self.interaction = interaction
        self.media_info = media_info

        regrab_button = Button(style=discord.ButtonStyle.primary, label="Regrab")
        regrab_button.callback = self.regrab_callback
        self.add_item(regrab_button)

        cancel_button = Button(style=discord.ButtonStyle.danger, label="Cancel")
        cancel_button.callback = self.cancel_callback
        self.add_item(cancel_button)

    async def regrab_callback(self, interaction):
        movie_title = self.media_info['title']
        movie_year = self.media_info['year']
        movie_id = self.media_info['movieId']
        movie_tmdb = self.media_info['tmdbId']

        await self.interaction.delete_original_response()

        delete_url = f"{radarr_base_url}/movie/{movie_id}?deleteFiles=true&apikey={radarr_api_key}"
        delete_response = perform_request('DELETE', delete_url)
        logging.info(f"Deleted {movie_title} with a response of {delete_response}")

        add_url = f"{radarr_base_url}/movie?apikey={radarr_api_key}"
        data = {
            "tmdbId": movie_tmdb,
            "title": movie_title,
            "year": movie_year,
            "qualityProfileId": radarr_quality_profile_id,
            "rootFolderPath": radarr_root_folder_path,
            "monitored": True,
            "minimumAvailability": "released",
            "addOptions": {
                "searchForMovie": True
            }
        }
        headers = {"Content-Type": "application/json"}
        add_response = perform_request('POST', add_url, data, headers)
        logging.info(f"Data sent for adding movie: {data}")
        if add_response:
            logging.info(f"Added {movie_title} with a response of {add_response}")
        else:
            logging.error(f"Failed to add {movie_title}")

        if add_response and 200 <= add_response.status_code < 400:
            await self.interaction.followup.send(content=f"`{self.interaction.user.name}` your request to delete and redownload {movie_title} ({movie_year}) is being processed.")
        else:
            await self.interaction.followup.send(content=f"`{self.interaction.user.name}` your request of {movie_title} ({movie_year}) had an issue, please contact the admin")

    async def cancel_callback(self, interaction):
        await self.interaction.delete_original_response()
        await self.interaction.followup.send(content="Cancelled the request.", ephemeral=True)


class ConfirmButtonsSeries(View):
    def __init__(self, interaction, media_info):
        super().__init__()
        self.interaction = interaction
        self.media_info = media_info

        regrab_button = Button(style=discord.ButtonStyle.primary, label="Regrab")
        regrab_button.callback = self.regrab_callback
        self.add_item(regrab_button)

        cancel_button = Button(style=discord.ButtonStyle.danger, label="Cancel")
        cancel_button.callback = self.cancel_callback
        self.add_item(cancel_button)

    async def regrab_callback(self, interaction):
        await self.interaction.delete_original_response()

        if self.media_info['episodeFileId'] != 0:
            delete_url = f"{sonarr_base_url}/episodefile/{self.media_info['episodeFileId']}?apikey={sonarr_api_key}"
            try:
                delete_response = perform_request('DELETE', delete_url)
                logging.info(f"Deleted EpisodeFileID {self.media_info['episodeFileId']} with a response of {delete_response.status_code}")
            except requests.exceptions.RequestException as e:
                logging.error(f"Error deleting EpisodeFileID {self.media_info['episodeFileId']}: {e}")
        else:
            logging.info(f"No Episode Found")

        search_url = f"{sonarr_base_url}/command/"
        headers = {
            "Content-Type": "application/json",
            "X-Api-Key": sonarr_api_key
        }
        data = {
            "episodeIds": [self.media_info['episodeId']],
            "name": "EpisodeSearch",
        }
        try:
            search_response = perform_request('POST', search_url, data, headers)
            logging.info(f"Searching for EpisodeID {self.media_info['episodeNumber']} with a response of {search_response.status_code}")
        except requests.exceptions.RequestException as e:
            logging.error(f"Error searching for EpisodeID {self.media_info['episodeId']}: {e}")

        if search_response and 200 <= search_response.status_code < 400:
            await self.interaction.followup.send(content=f"`{self.interaction.user.name}` your request to (re)grab {self.media_info['series']} Season {self.media_info['seasonNumber']} Episode {self.media_info['episodeNumber']} is being processed.")
        else:
            await self.interaction.followup.send(content=f"`{self.interaction.user.name}` your request to (re)grab {self.media_info['series']} Season {self.media_info['seasonNumber']} Episode {self.media_info['episodeNumber']} had an issue, please contact the admin")

    async def cancel_callback(self, interaction):
        await self.interaction.delete_original_response()
        await self.interaction.followup.send(content="Cancelled the request.", ephemeral=True)


class MovieSelectorView(View):
    def __init__(self, search_results, media_info):
        super().__init__()
        self.search_results = search_results
        self.add_item(MovieSelector(search_results, media_info))


class MovieSelector(Select):
    def __init__(self, search_results, media_info):
        self.search_results = search_results
        self.media_info = media_info
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
        self.media_info['movieId'] = selected_movie_data.get('id', 'N/A')
        self.media_info['tmdbId'] = selected_movie_data.get('tmdbId', 'N/A')
        self.media_info['title'] = selected_movie_data.get('title', 'Unknown Title')
        self.media_info['year'] = selected_movie_data.get('year', 'Unknown Year')
        self.media_info['overview'] = selected_movie_data.get('overview', 'No overview available')

        confirmation_message = (
            f"Please confirm that you would like to regrab the following movie:\n"
            f"**Title:** {self.media_info['title']}\n"
            f"**Year:** {self.media_info['year']}\n"
            f"**Overview:** {self.media_info['overview']}\n"
        )
        confirmation_view = ConfirmButtonsMovie(interaction, self.media_info)
        await interaction.response.edit_message(content=confirmation_message, view=confirmation_view)


async def fetch_movie(movie_name):
    url = f"{radarr_base_url}/movie/lookup?term={movie_name}"
    headers = {"X-Api-Key": radarr_api_key}
    try:
        response = perform_request('GET', url, headers=headers)
        if response and response.status_code == 200:
            movie_list = response.json()
            return movie_list[:10]
        else:
            return []
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching movie data: {e}")
        return []


class SeriesSelectorView(View):
    def __init__(self, series_results, media_info):
        super().__init__()
        self.series_results = series_results
        self.media_info = media_info
        self.add_item(TVSeriesSelector(series_results, media_info))


class TVSeriesSelector(Select):
    def __init__(self, series_results, media_info):
        self.series_results = series_results
        self.media_info = media_info
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
        self.media_info['series'] = selected_series_data['title']
        self.media_info['seriesId'] = selected_series_data['id']
        await interaction.response.edit_message(content="Please select a season", view=SeasonSelectorView(seasons_results, self.media_info))


async def fetch_series(series_name):
    url = f"{sonarr_base_url}/series/lookup?term={series_name}"
    headers = {"X-Api-Key": sonarr_api_key}
    try:
        response = perform_request('GET', url, headers=headers)
        if response and response.status_code == 200:
            series_list = response.json()
            return series_list[:10]
        else:
            return []
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching series data: {e}")
        return []


class SeasonSelectorView(View):
    def __init__(self, season_results, media_info):
        super().__init__()
        self.season_results = season_results
        self.media_info = media_info
        self.add_item(SeasonSelector(season_results, media_info))


class SeasonSelector(Select):
    def __init__(self, seasons_results, media_info):
        self.seasons_results = seasons_results
        self.media_info = media_info
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
        self.media_info['seasonNumber'] = self.seasons_results[selected_season_index]['seasonNumber']
        episode_results = await fetch_episodes(self.media_info)
        await interaction.response.edit_message(content="Please select an episode", view=EpisodeSelectorView(episode_results, self.media_info))


async def fetch_seasons(selected_series_data):
    seasons = selected_series_data.get('seasons', [])
    seasons = [season for season in seasons if season['seasonNumber'] != 0]
    return seasons


class EpisodeSelectorView(View):
    def __init__(self, episode_results, media_info):
        super().__init__()
        self.series_results = episode_results
        self.media_info = media_info
        self.add_item(EpisodeSelector(episode_results, media_info))


class EpisodeSelector(Select):
    def __init__(self, episodes_results, media_info):
        options = []
        current_date = datetime.now().date()
        self.media_info = media_info
        self.episode_results = episodes_results

        for idx, episode in enumerate(episodes_results):
            episode_number = episode['episodeNumber']
            episode_name = f"Episode {episode_number}"
            air_date_str = episode.get('airDate', 'Air Date Unknown')
            try:
                air_date = datetime.strptime(air_date_str, "%Y-%m-%d").date()
                is_past_air_date = air_date <= current_date
            except ValueError:
                is_past_air_date = False

            if is_past_air_date:
                formatted_description = f"Air Date: {air_date.strftime('%b %d %Y')}"
                options.append(discord.SelectOption(
                    label=episode_name,
                    value=str(idx),
                    description=formatted_description
                ))
        super().__init__(placeholder="Please select an episode", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        self.media_info['episodeArrayNumber'] = int(self.values[0])
        await fetch_episode_details(self.episode_results, self.media_info)
        confirmation_message = (
            f"Please confirm that you would like to regrab the following episode:\n"
            f"**Series:** {self.media_info['series']}\n"
            f"**Season:** Season {self.media_info['seasonNumber']}\n"
            f"**Episode:** Episode {self.media_info['episodeNumber']}\n"
            f"**Title:** {self.media_info['title']}\n"
            f"**Air Date:** {self.media_info['airDate']}\n"
            f"**Overview:** {self.media_info['overview']}\n"
        )
        confirmation_view = ConfirmButtonsSeries(interaction, self.media_info)
        await interaction.response.edit_message(content=confirmation_message, view=confirmation_view)


async def fetch_episodes(media_info):
    url = f"{sonarr_base_url}/episode"
    params = {
        'seriesId': media_info['seriesId'],
        'seasonNumber': media_info['seasonNumber']
    }
    headers = {"X-Api-Key": sonarr_api_key}
    logging.info(f"Fetching episodes with URL: {url}, params: {params}")

    try:
        response = perform_request('GET', url, headers=headers, params=params)
        if response and response.status_code == 200:
            return response.json()
        else:
            logging.warning(f"Response was not a 200 (was a {response.status_code}) for fetch episode of {media_info['seriesId']} Season {media_info['seasonNumber']}")
            return []
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching episode data: {e}")
        return []


async def fetch_episode_details(episode_results, media_info):
    episode_details = episode_results[media_info['episodeArrayNumber']]
    media_info['title'] = episode_details['title']
    media_info['episodeNumber'] = episode_details['episodeNumber']
    media_info['overview'] = episode_details['overview']
    media_info['episodeFileId'] = episode_details['episodeFileId']
    media_info['episodeId'] = episode_details['id']
    media_info['airDate'] = episode_details['airDate']


media_info = {}


@bot.event
async def on_ready():
    logging.info('Bot is Up and Ready!')
    try:
        synced = await bot.tree.sync()
        logging.info(f"Synced {len(synced)} command(s)")
    except Exception as e:
        logging.error(f"{e}")


@bot.tree.command(name=regrab_movie_command_name, description="Will delete and redownload selected movie")
@app_commands.describe(movie="What movie should we regrab?")
async def regrab_movie(ctx, *, movie: str):
    movie_results = await fetch_movie(movie)
    if not movie_results:
        await ctx.response.send_message(
            f"{ctx.user.name} no movie matching the following title was found: {movie}")
        return
    media_info['what'] = 'movie'
    media_info['delete'] = 'yes'
    await ctx.response.send_message("Select a movie to regrab", view=MovieSelectorView(movie_results, media_info), ephemeral=True)


@bot.tree.command(name=regrab_episode_command_name, description="Will delete and redownload selected episode")
@app_commands.describe(series="What TV series should we regrab from?")
async def regrab_episode(ctx, *, series: str):
    series_results = await fetch_series(series)
    if not series_results:
        await ctx.response.send_message(f"No TV series matching the title: {series}")
        return
    media_info['what'] = 'series'
    media_info['delete'] = 'yes'
    await ctx.response.send_message("Select a TV series to regrab", view=SeriesSelectorView(series_results, media_info), ephemeral=True)


bot.run(bot_token)
