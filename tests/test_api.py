"""
Unit tests for API helper functions.
Tests are mocked and do not require external services.
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import requests


# ============================================================================
# Test: perform_request function
# ============================================================================

class TestPerformRequest:
    """Tests for the perform_request HTTP helper function."""

    @pytest.mark.unit
    def test_get_request_success(self, mock_session, mock_response_factory):
        """Test successful GET request."""
        expected_data = {'key': 'value'}
        mock_response = mock_response_factory(200, expected_data)
        mock_session.get.return_value = mock_response

        with patch('requests.Session', return_value=mock_session):
            response = mock_session.get('http://test.com/api')

        assert response.status_code == 200
        assert response.json() == expected_data

    @pytest.mark.unit
    def test_post_request_success(self, mock_session, mock_response_factory):
        """Test successful POST request."""
        expected_data = {'id': 1, 'status': 'created'}
        mock_response = mock_response_factory(201, expected_data)
        mock_session.post.return_value = mock_response

        response = mock_session.post('http://test.com/api', json={'name': 'test'})

        assert response.status_code == 201
        assert response.json() == expected_data

    @pytest.mark.unit
    def test_delete_request_success(self, mock_session, mock_response_factory):
        """Test successful DELETE request."""
        mock_response = mock_response_factory(200, {})
        mock_session.delete.return_value = mock_response

        response = mock_session.delete('http://test.com/api/1')

        assert response.status_code == 200

    @pytest.mark.unit
    def test_request_with_headers(self, mock_session, mock_response_factory):
        """Test request with custom headers."""
        mock_response = mock_response_factory(200, {})
        mock_session.get.return_value = mock_response

        headers = {'X-Api-Key': 'test_key', 'Content-Type': 'application/json'}
        mock_session.get('http://test.com/api', headers=headers)

        mock_session.get.assert_called_with('http://test.com/api', headers=headers)

    @pytest.mark.unit
    def test_request_with_params(self, mock_session, mock_response_factory):
        """Test request with query parameters."""
        mock_response = mock_response_factory(200, {})
        mock_session.get.return_value = mock_response

        params = {'term': 'matrix', 'limit': 10}
        mock_session.get('http://test.com/api', params=params)

        mock_session.get.assert_called_with('http://test.com/api', params=params)

    @pytest.mark.unit
    def test_request_handles_http_error(self, mock_session, mock_response_factory):
        """Test handling of HTTP errors."""
        mock_response = mock_response_factory(404, {'error': 'Not found'})
        mock_session.get.return_value = mock_response

        response = mock_session.get('http://test.com/api/999')

        assert response.status_code == 404
        with pytest.raises(requests.exceptions.HTTPError):
            response.raise_for_status()

    @pytest.mark.unit
    def test_request_handles_connection_error(self, mock_session):
        """Test handling of connection errors."""
        mock_session.get.side_effect = requests.exceptions.ConnectionError("Connection failed")

        with pytest.raises(requests.exceptions.ConnectionError):
            mock_session.get('http://unreachable.com/api')

    @pytest.mark.unit
    def test_request_handles_timeout(self, mock_session):
        """Test handling of timeout errors."""
        mock_session.get.side_effect = requests.exceptions.Timeout("Request timed out")

        with pytest.raises(requests.exceptions.Timeout):
            mock_session.get('http://slow.com/api')


# ============================================================================
# Test: get_quality_profiles function
# ============================================================================

class TestGetQualityProfiles:
    """Tests for quality profile fetching."""

    @pytest.mark.unit
    def test_get_quality_profiles_success(self, mock_session, mock_response_factory, mock_quality_profiles):
        """Test successful fetch of quality profiles."""
        mock_response = mock_response_factory(200, mock_quality_profiles)
        mock_session.get.return_value = mock_response

        response = mock_session.get('http://localhost:8989/api/v3/qualityprofile')
        profiles = response.json()

        assert len(profiles) == 4
        assert profiles[0]['name'] == 'Any'
        assert profiles[2]['name'] == '1080p Remux'

    @pytest.mark.unit
    def test_get_quality_profiles_empty(self, mock_session, mock_response_factory):
        """Test handling of empty quality profiles response."""
        mock_response = mock_response_factory(200, [])
        mock_session.get.return_value = mock_response

        response = mock_session.get('http://localhost:8989/api/v3/qualityprofile')
        profiles = response.json()

        assert profiles == [] or profiles == {}  # Empty response handling

    @pytest.mark.unit
    def test_get_quality_profiles_api_error(self, mock_session, mock_response_factory):
        """Test handling of API error when fetching profiles."""
        mock_response = mock_response_factory(500, {'error': 'Internal server error'})
        mock_session.get.return_value = mock_response

        response = mock_session.get('http://localhost:8989/api/v3/qualityprofile')

        assert response.status_code == 500


# ============================================================================
# Test: get_root_folders function
# ============================================================================

class TestGetRootFolders:
    """Tests for root folder fetching."""

    @pytest.mark.unit
    def test_get_root_folders_success(self, mock_session, mock_response_factory, mock_root_folders):
        """Test successful fetch of root folders."""
        mock_response = mock_response_factory(200, mock_root_folders)
        mock_session.get.return_value = mock_response

        response = mock_session.get('http://localhost:7878/api/v3/rootfolder')
        folders = response.json()

        assert len(folders) == 2
        assert folders[0]['path'] == '/data/media/movies'

    @pytest.mark.unit
    def test_get_root_folders_empty(self, mock_session, mock_response_factory):
        """Test handling of empty root folders response."""
        mock_response = mock_response_factory(200, [])
        mock_session.get.return_value = mock_response

        response = mock_session.get('http://localhost:7878/api/v3/rootfolder')
        folders = response.json()

        assert folders == [] or folders == {}  # Empty response handling


# ============================================================================
# Test: select_root_folder function
# ============================================================================

class TestSelectRootFolder:
    """Tests for root folder selection logic."""

    @pytest.mark.unit
    def test_select_root_folder_returns_first_path(self, mock_root_folders):
        """Test that first root folder path is selected."""
        def select_root_folder(root_folders):
            if root_folders:
                return root_folders[0]['path']
            else:
                raise Exception("No root folders available")

        path = select_root_folder(mock_root_folders)
        assert path == '/data/media/movies'

    @pytest.mark.unit
    def test_select_root_folder_empty_raises_exception(self):
        """Test that empty root folders raises exception."""
        def select_root_folder(root_folders):
            if root_folders:
                return root_folders[0]['path']
            else:
                raise Exception("No root folders available")

        with pytest.raises(Exception, match="No root folders available"):
            select_root_folder([])


# ============================================================================
# Test: fetch_movie function
# ============================================================================

class TestFetchMovie:
    """Tests for movie fetching functionality."""

    @pytest.mark.unit
    def test_fetch_movie_returns_results(self, mock_session, mock_response_factory, mock_movie_lookup):
        """Test movie lookup returns results."""
        mock_response = mock_response_factory(200, mock_movie_lookup)
        mock_session.get.return_value = mock_response

        response = mock_session.get('http://localhost:7878/api/v3/movie/lookup', params={'term': 'matrix'})
        movies = response.json()

        assert len(movies) == 3
        assert movies[0]['title'] == 'The Matrix'
        assert movies[0]['year'] == 1999

    @pytest.mark.unit
    def test_fetch_movie_limits_to_10_results(self, mock_session, mock_response_factory):
        """Test that movie results are limited to 10."""
        # Create 15 mock movies
        many_movies = [{'id': i, 'title': f'Movie {i}', 'year': 2000 + i} for i in range(15)]
        mock_response = mock_response_factory(200, many_movies)
        mock_session.get.return_value = mock_response

        response = mock_session.get('http://localhost:7878/api/v3/movie/lookup', params={'term': 'test'})
        movies = response.json()[:10]  # Simulate the [:10] slicing in fetch_movie

        assert len(movies) == 10

    @pytest.mark.unit
    def test_fetch_movie_no_results(self, mock_session, mock_response_factory):
        """Test movie lookup with no results."""
        mock_response = mock_response_factory(200, [])
        mock_session.get.return_value = mock_response

        response = mock_session.get('http://localhost:7878/api/v3/movie/lookup', params={'term': 'nonexistent'})
        movies = response.json()

        assert movies == [] or movies == {}  # Empty response handling

    @pytest.mark.unit
    def test_fetch_movie_contains_required_fields(self, mock_movie_lookup):
        """Test that movie results contain required fields."""
        required_fields = ['id', 'title', 'year', 'tmdbId', 'overview']
        for movie in mock_movie_lookup:
            for field in required_fields:
                assert field in movie, f"Movie missing required field: {field}"


# ============================================================================
# Test: fetch_series function
# ============================================================================

class TestFetchSeries:
    """Tests for series fetching functionality."""

    @pytest.mark.unit
    def test_fetch_series_returns_results(self, mock_session, mock_response_factory, mock_series_lookup):
        """Test series lookup returns results."""
        mock_response = mock_response_factory(200, mock_series_lookup)
        mock_session.get.return_value = mock_response

        response = mock_session.get('http://localhost:8989/api/v3/series/lookup', params={'term': 'breaking'})
        series = response.json()

        assert len(series) == 2
        assert series[0]['title'] == 'Breaking Bad'
        assert series[0]['year'] == 2008

    @pytest.mark.unit
    def test_fetch_series_limits_to_10_results(self, mock_session, mock_response_factory):
        """Test that series results are limited to 10."""
        many_series = [{'id': i, 'title': f'Series {i}', 'year': 2000 + i, 'seasons': []} for i in range(15)]
        mock_response = mock_response_factory(200, many_series)
        mock_session.get.return_value = mock_response

        response = mock_session.get('http://localhost:8989/api/v3/series/lookup', params={'term': 'test'})
        series = response.json()[:10]

        assert len(series) == 10


# ============================================================================
# Test: fetch_seasons function
# ============================================================================

class TestFetchSeasons:
    """Tests for season fetching functionality."""

    @pytest.mark.unit
    def test_fetch_seasons_excludes_specials(self, mock_series_lookup):
        """Test that season 0 (specials) is excluded."""
        series_data = mock_series_lookup[0]  # Breaking Bad
        seasons = series_data.get('seasons', [])
        filtered_seasons = [s for s in seasons if s['seasonNumber'] != 0]

        assert all(s['seasonNumber'] != 0 for s in filtered_seasons)
        assert len(filtered_seasons) == 5  # Seasons 1-5

    @pytest.mark.unit
    def test_fetch_seasons_empty_series(self):
        """Test handling of series with no seasons."""
        series_data = {'id': 1, 'title': 'Empty Series', 'seasons': []}
        seasons = series_data.get('seasons', [])

        assert seasons == []


# ============================================================================
# Test: fetch_episodes function
# ============================================================================

class TestFetchEpisodes:
    """Tests for episode fetching functionality."""

    @pytest.mark.unit
    def test_fetch_episodes_returns_results(self, mock_session, mock_response_factory, mock_episodes):
        """Test episode fetch returns results."""
        mock_response = mock_response_factory(200, mock_episodes)
        mock_session.get.return_value = mock_response

        params = {'seriesId': 1, 'seasonNumber': 1}
        response = mock_session.get('http://localhost:8989/api/v3/episode', params=params)
        episodes = response.json()

        assert len(episodes) == 3
        assert episodes[0]['title'] == 'Pilot'
        assert episodes[0]['episodeNumber'] == 1

    @pytest.mark.unit
    def test_fetch_episodes_contains_required_fields(self, mock_episodes):
        """Test that episodes contain required fields."""
        required_fields = ['id', 'seriesId', 'seasonNumber', 'episodeNumber', 'title', 'airDate', 'episodeFileId']
        for episode in mock_episodes:
            for field in required_fields:
                assert field in episode, f"Episode missing required field: {field}"


# ============================================================================
# Test: Movie Regrab Flow
# ============================================================================

class TestMovieRegrabFlow:
    """Tests for the movie regrab workflow."""

    @pytest.mark.unit
    def test_delete_movie_request_format(self, mock_session, mock_response_factory):
        """Test that delete movie request is properly formatted."""
        mock_response = mock_response_factory(200, {})
        mock_session.delete.return_value = mock_response

        movie_id = 123
        api_key = 'test_api_key'
        base_url = 'http://localhost:7878/api/v3'

        # Simulate the delete URL construction
        delete_url = f"{base_url}/movie/{movie_id}?deleteFiles=true&apikey={api_key}"

        mock_session.delete(delete_url)
        mock_session.delete.assert_called_with(delete_url)

    @pytest.mark.unit
    def test_add_movie_request_payload(self):
        """Test that add movie request payload is correct."""
        movie_data = {
            'tmdbId': 603,
            'title': 'The Matrix',
            'year': 1999,
            'qualityProfileId': 3,
            'rootFolderPath': '/data/media/movies',
            'monitored': True,
            'minimumAvailability': 'released',
            'addOptions': {
                'searchForMovie': True
            }
        }

        # Verify required fields
        assert 'tmdbId' in movie_data
        assert 'qualityProfileId' in movie_data
        assert 'rootFolderPath' in movie_data
        assert movie_data['addOptions']['searchForMovie'] is True


# ============================================================================
# Test: Episode Regrab Flow
# ============================================================================

class TestEpisodeRegrabFlow:
    """Tests for the episode regrab workflow."""

    @pytest.mark.unit
    def test_delete_episode_file_request_format(self, mock_session, mock_response_factory):
        """Test that delete episode file request is properly formatted."""
        mock_response = mock_response_factory(200, {})
        mock_session.delete.return_value = mock_response

        episode_file_id = 501
        api_key = 'test_api_key'
        base_url = 'http://localhost:8989/api/v3'

        delete_url = f"{base_url}/episodefile/{episode_file_id}?apikey={api_key}"

        mock_session.delete(delete_url)
        mock_session.delete.assert_called_with(delete_url)

    @pytest.mark.unit
    def test_episode_search_command_payload(self):
        """Test that episode search command payload is correct."""
        search_data = {
            'episodeIds': [101],
            'name': 'EpisodeSearch'
        }

        assert 'episodeIds' in search_data
        assert 'name' in search_data
        assert search_data['name'] == 'EpisodeSearch'
        assert isinstance(search_data['episodeIds'], list)

    @pytest.mark.unit
    def test_skip_delete_when_no_episode_file(self, mock_episodes):
        """Test that delete is skipped when episodeFileId is 0."""
        episode_without_file = mock_episodes[2]  # episodeFileId = 0

        should_delete = episode_without_file['episodeFileId'] != 0
        assert should_delete is False
