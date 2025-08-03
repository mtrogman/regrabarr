import sys
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Select, View, Button
from datetime import datetime
import requests
import yaml
import logging
import time

def get_config(file):
    with open(file, 'r') as yaml_file:
        return yaml.safe_load(yaml_file)

def save_config(file, config):
    with open(file, 'w') as yaml_file:
        yaml.safe_dump(config, yaml_file)

config_location = "./config/config.yml"
config = get_config(config_location)
bot_token = config['bot']['token']
radarr_api_key = config['radarr']['api_key']
radarr_base_url = config['radarr']['url'].rstrip('/')
sonarr_api_key = config['sonarr']['api_key']
sonarr_base_url = config['sonarr']['url'].rstrip('/')

regrab_movie_command_name = config['bot'].get('regrab_movie', 'regrab_movie')
regrab_episode_command_name = config['bot'].get('regrab_episode', 'regrab_episode')

logging.basicConfig(stream=sys.stdout, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())
session = requests.Session()

def get_root_folders(base_url, api_key):
    url = f"{base_url}/rootfolder?apikey={api_key}"
    try:
        response = session.get(url)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logging.error(f"Failed to get root folders from {base_url}: {e}")
        return []

def select_root_folder(folders):
    if folders:
        return folders[0]['path']
    raise Exception("No root folders available")

def get_first_quality_profile(base_url, api_key):
    url = f"{base_url}/qualityprofile?apikey={api_key}"
    try:
        response = session.get(url)
        response.raise_for_status()
        profiles = response.json()
        if profiles:
            return profiles[0]['id']
        else:
            raise Exception("No quality profiles available")
    except Exception as e:
        logging.error(f"Failed to get quality profiles from {base_url}: {e}")
        return None

def ensure_config_value(section, key, fetch_func):
    if key not in config[section] or not config[section][key]:
        value = fetch_func()
        if value:
            config[section][key] = value
            save_config(config_location, config)
            logging.info(f"Set {key} for {section}: {value}")
        else:
            logging.critical(f"Could not fetch {key} for {section}. Exiting.")
            sys.exit(1)
    return config[section][key]

sonarr_quality_profile_id = ensure_config_value('sonarr', 'qualityprofileid', lambda: get_first_quality_profile(sonarr_base_url, sonarr_api_key))
sonarr_root_folder_path  = ensure_config_value('sonarr', 'root_path', lambda: select_root_folder(get_root_folders(sonarr_base_url, sonarr_api_key)))
radarr_quality_profile_id = ensure_config_value('radarr', 'qualityprofileid', lambda: get_first_quality_profile(radarr_base_url, radarr_api_key))
radarr_root_folder_path  = ensure_config_value('radarr', 'root_path', lambda: select_root_folder(get_root_folders(radarr_base_url, radarr_api_key)))

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
    except Exception as e:
        logging.error(f"{method} request failed: {e}")
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

        try:
            await self.interaction.delete_original_response()
        except Exception:
            pass

        if movie_id == 'N/A':
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
                    "searchForMovie": False
                }
            }
            headers = {"Content-Type": "application/json"}
            perform_request('POST', add_url, data, headers)
            query_url = f"{radarr_base_url}/movie?tmdbId={movie_tmdb}&apikey={radarr_api_key}"
            query_response = session.get(query_url)
            if query_response.ok and query_response.json():
                movie_obj = query_response.json()[0]
                movie_id = movie_obj['id']
            else:
                try:
                    await self.interaction.followup.send(
                        f"Failed to add or fetch {movie_title} in Radarr. Please try again.", ephemeral=True)
                except Exception:
                    pass
                return

        delete_url = f"{radarr_base_url}/movie/{movie_id}?deleteFiles=true&apikey={radarr_api_key}"
        perform_request('DELETE', delete_url)

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

        msg = ""
        if add_response and 200 <= add_response.status_code < 400:
            msg = f"`{self.interaction.user.name}` your request to clean regrab {movie_title} ({movie_year}) is being processed."
        else:
            msg = f"`{self.interaction.user.name}` your request of {movie_title} ({movie_year}) had an issue, please contact the admin"
        try:
            await self.interaction.followup.send(content=msg)
        except Exception:
            pass

    async def cancel_callback(self, interaction):
        try:
            await self.interaction.delete_original_response()
        except Exception:
            pass
        try:
            await self.interaction.followup.send(content="Cancelled the request.", ephemeral=True)
        except Exception:
            pass

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
        try:
            await self.interaction.delete_original_response()
        except Exception:
            pass

        if self.media_info['episodeFileId'] != 0:
            delete_url = f"{sonarr_base_url}/episodefile/{self.media_info['episodeFileId']}?apikey={sonarr_api_key}"
            perform_request('DELETE', delete_url)

        search_url = f"{sonarr_base_url}/command/"
        headers = {
            "Content-Type": "application/json",
            "X-Api-Key": sonarr_api_key
        }
        data = {
            "episodeIds": [self.media_info['episodeId']],
            "name": "EpisodeSearch",
        }
        search_response = perform_request('POST', search_url, data, headers)

        msg = ""
        if search_response and 200 <= search_response.status_code < 400:
            msg = f"`{self.interaction.user.name}` your request to (re)grab {self.media_info['series']} Season {self.media_info['seasonNumber']} Episode {self.media_info['episodeNumber']} is being processed."
        else:
            msg = f"`{self.interaction.user.name}` your request to (re)grab {self.media_info['series']} Season {self.media_info['seasonNumber']} Episode {self.media_info['episodeNumber']} had an issue, please contact the admin"
        try:
            await self.interaction.followup.send(content=msg)
        except Exception:
            pass

    async def cancel_callback(self, interaction):
        try:
            await self.interaction.delete_original_response()
        except Exception:
            pass
        try:
            await self.interaction.followup.send(content="Cancelled the request.", ephemeral=True)
        except Exception:
            pass

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
        try:
            await interaction.response.edit_message(content=confirmation_message, view=confirmation_view)
        except discord.errors.NotFound:
            try:
                await interaction.followup.send(
                    "This session has expired or took too long to process. Please re-run the command.",
                    ephemeral=True
                )
            except Exception:
                pass

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
    except Exception as e:
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
                description=str(series.get('year', ''))
            )
            for idx, series in enumerate(series_results)
        ]
        super().__init__(placeholder="Please select a TV series", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        selected_series_index = int(self.values[0])
        selected_series_data = self.series_results[selected_series_index]

        # If not already in Sonarr, add
        if 'id' not in selected_series_data:
            add_url = f"{sonarr_base_url}/series"
            headers = {"X-Api-Key": sonarr_api_key, "Content-Type": "application/json"}
            add_payload = {
                "tvdbId": selected_series_data['tvdbId'],
                "title": selected_series_data['title'],
                "qualityProfileId": sonarr_quality_profile_id,
                "titleSlug": selected_series_data['titleSlug'],
                "rootFolderPath": sonarr_root_folder_path,
                "languageProfileId": 1,
                "monitored": True,
                "addOptions": {
                    "searchForMissingEpisodes": True
                }
            }
            add_response = perform_request('POST', add_url, add_payload, headers)
            if add_response and 200 <= add_response.status_code < 400:
                search_url = f"{sonarr_base_url}/series?apikey={sonarr_api_key}"
                resp = session.get(search_url)
                found = False
                if resp.ok and resp.json():
                    for series in resp.json():
                        if series.get('tvdbId') == selected_series_data['tvdbId']:
                            selected_series_data = series
                            found = True
                            break
                if not found:
                    try:
                        await interaction.response.edit_message(content="Failed to add series to Sonarr. Please try again.")
                    except discord.errors.NotFound:
                        try:
                            await interaction.followup.send(
                                "This session has expired or took too long to process. Please re-run the command.",
                                ephemeral=True
                            )
                        except Exception:
                            logging.error("Interaction and followup both failed after Sonarr add fail.")
                    return
            else:
                try:
                    await interaction.response.edit_message(content="Failed to add series to Sonarr. Please try again.")
                except discord.errors.NotFound:
                    try:
                        await interaction.followup.send(
                            "This session has expired or took too long to process. Please re-run the command.",
                            ephemeral=True
                        )
                    except Exception:
                        logging.error("Interaction and followup both failed after Sonarr add fail.")
                return

        self.media_info['series'] = selected_series_data['title']
        self.media_info['seriesId'] = selected_series_data['id']
        seasons_results = await fetch_seasons(selected_series_data)
        try:
            await interaction.response.edit_message(content="Please select a season", view=SeasonSelectorView(seasons_results, self.media_info))
        except discord.errors.NotFound:
            try:
                await interaction.followup.send(
                    "This session has expired or took too long to process. Please re-run the command.",
                    ephemeral=True
                )
            except Exception:
                logging.error("Interaction and followup both failed on season picker.")

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
    except Exception as e:
        logging.error(f"Error fetching series data: {e}")
        return []

async def fetch_seasons(selected_series_data):
    seasons = selected_series_data.get('seasons', [])
    seasons = [season for season in seasons if season['seasonNumber'] != 0]
    return seasons

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
        if not episode_results:
            try:
                await interaction.response.edit_message(
                    content="Episodes for this season are not available yet (Sonarr is still importing metadata). Please try again in a minute!",
                    view=None
                )
            except discord.errors.NotFound:
                try:
                    await interaction.followup.send(
                        "This session has expired or took too long to process. Please re-run the command.",
                        ephemeral=True
                    )
                except Exception:
                    pass
            return
        try:
            await interaction.response.edit_message(content="Please select an episode", view=EpisodeSelectorView(episode_results, self.media_info))
        except discord.errors.NotFound:
            try:
                await interaction.followup.send(
                    "This session has expired or took too long to process. Please re-run the command.",
                    ephemeral=True
                )
            except Exception:
                pass

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
        try:
            await interaction.response.edit_message(content=confirmation_message, view=confirmation_view)
        except discord.errors.NotFound:
            try:
                await interaction.followup.send(
                    "This session has expired or took too long to process. Please re-run the command.",
                    ephemeral=True
                )
            except Exception:
                pass

async def fetch_episodes(media_info, max_wait=30, poll_interval=3):
    url = f"{sonarr_base_url}/episode"
    params = {
        'seriesId': media_info['seriesId'],
        'seasonNumber': media_info['seasonNumber']
    }
    headers = {"X-Api-Key": sonarr_api_key}
    logging.info(f"Fetching episodes with URL: {url}, params: {params}")

    waited = 0
    while waited < max_wait:
        try:
            response = perform_request('GET', url, headers=headers, params=params)
            if response and response.status_code == 200:
                episodes = response.json()
                if episodes:
                    return episodes
            else:
                logging.warning(f"Response was not a 200 (was a {response.status_code}) for fetch episode of {media_info['seriesId']} Season {media_info['seasonNumber']}")
        except Exception as e:
            logging.error(f"Error fetching episode data: {e}")
        time.sleep(poll_interval)
        waited += poll_interval

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
    await ctx.response.defer(ephemeral=True)
    movie_results = await fetch_movie(movie)
    if not movie_results:
        await ctx.followup.send(
            f"{ctx.user.name} no movie matching the following title was found: {movie}")
        return
    media_info['what'] = 'movie'
    media_info['delete'] = 'yes'
    await ctx.followup.send("Select a movie to regrab", view=MovieSelectorView(movie_results, media_info), ephemeral=True)

@bot.tree.command(name=regrab_episode_command_name, description="Will delete and redownload selected episode")
@app_commands.describe(series="What TV series should we regrab from?")
async def regrab_episode(ctx, *, series: str):
    await ctx.response.defer(ephemeral=True)
    series_results = await fetch_series(series)
    if not series_results:
        await ctx.followup.send(f"No TV series matching the title: {series}")
        return
    media_info['what'] = 'series'
    media_info['delete'] = 'yes'
    await ctx.followup.send("Select a TV series to regrab", view=SeriesSelectorView(series_results, media_info), ephemeral=True)

if __name__ == "__main__":
    bot.run(bot_token)
