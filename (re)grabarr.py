import json
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Select, View, Button
import httpx

bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())


def getConfig(file):
    with open(file) as f:
        config = json.loads(f.read())
    return config


config_location = "/config/config.json"
config = getConfig(config_location)
bot_token = config['bot']['token']
radarr_api_key = config['radarr']['api_key']
radarr_base_url = config['radarr']['url']
sonarr_api_key = config['sonarr']['api_key']
sonarr_base_url = config['sonarr']['url']


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

        async with httpx.AsyncClient() as client:
            delete_url = f"{radarr_base_url}/movie/{movie_id}?deleteFiles=true&apikey={radarr_api_key}"
            delete_response = await client.delete(delete_url)
            print(f"Deleted {movie_title} with a response of {delete_response}")

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
            add_response = await client.post(add_url, json=data, headers=headers)
            print(f"Added {movie_title} with a response of {add_response}")

        await self.interaction.followup.send(content=f"`{self.interaction.user.name} your request to delete and redownload {movie_title}` ({movie_year}) is being processed.")

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
        if self.selected_episode_data['episodeFileId'] != 0:
            async with httpx.AsyncClient() as client:
                delete_url = f"{sonarr_base_url}/episodefile/{self.selected_episode_data['episodeFileId']}?apikey={sonarr_api_key}"
                print(delete_url)
                delete_response = await client.delete(delete_url)
                print(f"Deleted EpisodeFileID {self.selected_episode_data['episodeFileId']} with a response of {delete_response}")
        else:
            print(f"No Episode Found")
        
        async with httpx.AsyncClient() as client:
            search_url = f"{sonarr_base_url}/command/"
            headers = {
                "Content-Type": "application/json",
                "X-Api-Key": sonarr_api_key
            }
            data = {
                "episodeIds": [self.selected_episode_data['episodeId']],
                "name": "EpisodeSearch",
            }

            search_response = await client.post(search_url, headers=headers, json=data)
            print(f"Searching for EpisodeID {self.selected_episode_data['episodeId']} with a response of {search_response}")
     
        await self.interaction.delete_original_response()
        await self.interaction.followup.send(content=f"`{self.interaction.user.name} your request to (re)grab {self.selected_episode_data['series']}` Season {self.selected_episode_data['season']}) Episode {self.selected_episode_data['episode']} is being processed.")

    async def cancel_callback(self, button):
        await self.interaction.delete_original_response()
        await self.interaction.followup.send(content="Cancelled the request.", ephemeral=True)

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
async def fetch_movie(movie_name):
    url = f"{radarr_base_url}/movie/lookup?term={movie_name}"
    headers = {"X-Api-Key": radarr_api_key}

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        if response.status_code == 200:
            movie_list = response.json()
            return movie_list[:10]  # Return the first 10 series
        else:
            return []
        
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
async def fetch_series(series_name):
    url = f"{sonarr_base_url}/series/lookup?term={series_name}"
    headers = {"X-Api-Key": sonarr_api_key}

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        if response.status_code == 200:
            series_list = response.json()
            return series_list[:10]  # Return the first 10 series
        else:
            return []

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
async def fetch_seasons(selected_series_data, ):
    seasons = selected_series_data.get('seasons', [])
    # Filter out season 0 which is extras
    seasons = [season for season in seasons if season['seasonNumber'] != 0]

    return seasons

class EpisodeSelectorView(View):
    def __init__(self, episode_results):
        super().__init__()
        self.series_results = episode_results
        self.add_item(EpisodeSelector(episode_results))
class EpisodeSelector(Select):
    def __init__(self, episodes_results):
        options = [
            discord.SelectOption(
                label=f"Episode {episode['episodeNumber']}",
                value=str(idx)            
            )
            for idx, episode in enumerate(episodes_results)
        ]
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
            f"**Episode:** Overview {selected_episode_data['overview']}\n"
        )

        # Create and display the ConfirmButtons view for confirmation
        confirmation_view = ConfirmButtonsSeries(interaction, selected_episode_data)
        await interaction.response.edit_message(content=confirmation_message, view=confirmation_view)
async def fetch_episodes(selected_season_number):
    url = f"{sonarr_base_url}/episode"
    parameters = {
        'seriesId': seriesId,
        'seasonNumber': selected_season_number
    }
    headers = {"X-Api-Key": sonarr_api_key}

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers, params=parameters)
        if response.status_code == 200:
            return response.json()
        else:
            print("derp")
            return []
async def fetch_episode_details(episode_num):
    episode_details = episode_results[episode_num]
    print("Episode Details")
    print(episode_details)
    
    # Create a dictionary to store the parameters
    episode_info = {
        "series": episode_details['title'],
        "season": episode_details['seasonNumber'],
        "episode": episode_details['episodeNumber'],
        "title": episode_details['title'],
        "overview": episode_details['overview'],
        "episodeFileId": episode_details['episodeFileId'],
        "episodeId": episode_details['id']
    }
    episode_json = json.dumps(episode_info)
    return episode_json 


# Variable to store the selected item
selected_movie = None
selected_series = None

@bot.event
async def on_ready():
    print(f"Bot is Up and Ready!")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(e)

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
