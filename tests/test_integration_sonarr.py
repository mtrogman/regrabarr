"""
Integration tests for Sonarr API.
These tests require a live Sonarr instance and valid API credentials.

Run with: pytest -m integration tests/test_integration_sonarr.py
"""
import pytest
import requests


# ============================================================================
# Test: Sonarr Connection
# ============================================================================

class TestSonarrConnection:
    """Tests for Sonarr API connectivity."""

    @pytest.mark.integration
    def test_sonarr_api_reachable(self, live_config):
        """Test that Sonarr API is reachable."""
        base_url = live_config['sonarr']['url'].rstrip('/')
        api_key = live_config['sonarr']['api_key']

        url = f"{base_url}/system/status"
        headers = {"X-Api-Key": api_key}

        response = requests.get(url, headers=headers, timeout=10)

        assert response.status_code == 200
        data = response.json()
        assert 'version' in data

    @pytest.mark.integration
    def test_sonarr_api_key_valid(self, live_config):
        """Test that Sonarr API key is valid."""
        base_url = live_config['sonarr']['url'].rstrip('/')
        api_key = live_config['sonarr']['api_key']

        url = f"{base_url}/system/status"
        headers = {"X-Api-Key": api_key}

        response = requests.get(url, headers=headers, timeout=10)

        # 401 would indicate invalid API key
        assert response.status_code != 401
        assert response.status_code == 200

    @pytest.mark.integration
    def test_sonarr_invalid_api_key_rejected(self, live_config):
        """Test that invalid API key is rejected."""
        base_url = live_config['sonarr']['url'].rstrip('/')

        url = f"{base_url}/system/status"
        headers = {"X-Api-Key": "invalid_api_key_12345"}

        response = requests.get(url, headers=headers, timeout=10)

        assert response.status_code == 401


# ============================================================================
# Test: Sonarr Quality Profiles
# ============================================================================

class TestSonarrQualityProfiles:
    """Tests for Sonarr quality profile retrieval."""

    @pytest.mark.integration
    def test_get_quality_profiles(self, live_config):
        """Test fetching quality profiles from Sonarr."""
        base_url = live_config['sonarr']['url'].rstrip('/')
        api_key = live_config['sonarr']['api_key']

        url = f"{base_url}/qualityprofile"
        headers = {"X-Api-Key": api_key}

        response = requests.get(url, headers=headers, timeout=10)

        assert response.status_code == 200
        profiles = response.json()
        assert isinstance(profiles, list)
        assert len(profiles) > 0

    @pytest.mark.integration
    def test_quality_profile_structure(self, live_config):
        """Test that quality profiles have expected structure."""
        base_url = live_config['sonarr']['url'].rstrip('/')
        api_key = live_config['sonarr']['api_key']

        url = f"{base_url}/qualityprofile"
        headers = {"X-Api-Key": api_key}

        response = requests.get(url, headers=headers, timeout=10)
        profiles = response.json()

        for profile in profiles:
            assert 'id' in profile
            assert 'name' in profile
            assert isinstance(profile['id'], int)
            assert isinstance(profile['name'], str)


# ============================================================================
# Test: Sonarr Root Folders
# ============================================================================

class TestSonarrRootFolders:
    """Tests for Sonarr root folder retrieval."""

    @pytest.mark.integration
    def test_get_root_folders(self, live_config):
        """Test fetching root folders from Sonarr."""
        base_url = live_config['sonarr']['url'].rstrip('/')
        api_key = live_config['sonarr']['api_key']

        url = f"{base_url}/rootfolder"
        headers = {"X-Api-Key": api_key}

        response = requests.get(url, headers=headers, timeout=10)

        assert response.status_code == 200
        folders = response.json()
        assert isinstance(folders, list)
        assert len(folders) > 0

    @pytest.mark.integration
    def test_root_folder_structure(self, live_config):
        """Test that root folders have expected structure."""
        base_url = live_config['sonarr']['url'].rstrip('/')
        api_key = live_config['sonarr']['api_key']

        url = f"{base_url}/rootfolder"
        headers = {"X-Api-Key": api_key}

        response = requests.get(url, headers=headers, timeout=10)
        folders = response.json()

        for folder in folders:
            assert 'id' in folder
            assert 'path' in folder
            assert isinstance(folder['path'], str)
            assert len(folder['path']) > 0


# ============================================================================
# Test: Sonarr Series Lookup
# ============================================================================

class TestSonarrSeriesLookup:
    """Tests for Sonarr series lookup functionality."""

    @pytest.mark.integration
    def test_series_lookup_returns_results(self, live_config):
        """Test that series lookup returns results for known series."""
        base_url = live_config['sonarr']['url'].rstrip('/')
        api_key = live_config['sonarr']['api_key']

        # Search for a well-known series
        url = f"{base_url}/series/lookup"
        headers = {"X-Api-Key": api_key}
        params = {"term": "breaking bad"}

        response = requests.get(url, headers=headers, params=params, timeout=30)

        assert response.status_code == 200
        series = response.json()
        assert isinstance(series, list)
        assert len(series) > 0

    @pytest.mark.integration
    def test_series_lookup_structure(self, live_config):
        """Test that series lookup results have expected structure."""
        base_url = live_config['sonarr']['url'].rstrip('/')
        api_key = live_config['sonarr']['api_key']

        url = f"{base_url}/series/lookup"
        headers = {"X-Api-Key": api_key}
        params = {"term": "the office"}

        response = requests.get(url, headers=headers, params=params, timeout=30)
        series_list = response.json()

        if len(series_list) > 0:
            series = series_list[0]
            assert 'title' in series
            assert 'year' in series
            assert 'tvdbId' in series or 'tvRageId' in series

    @pytest.mark.integration
    def test_series_lookup_empty_term(self, live_config):
        """Test series lookup with empty search term."""
        base_url = live_config['sonarr']['url'].rstrip('/')
        api_key = live_config['sonarr']['api_key']

        url = f"{base_url}/series/lookup"
        headers = {"X-Api-Key": api_key}
        params = {"term": ""}

        response = requests.get(url, headers=headers, params=params, timeout=30)

        # Should return empty list, bad request, or service unavailable
        assert response.status_code in [200, 400, 503]

    @pytest.mark.integration
    def test_series_lookup_no_results(self, live_config):
        """Test series lookup with nonsense term returns empty results."""
        base_url = live_config['sonarr']['url'].rstrip('/')
        api_key = live_config['sonarr']['api_key']

        url = f"{base_url}/series/lookup"
        headers = {"X-Api-Key": api_key}
        params = {"term": "xyznonexistent12345abcdef"}

        response = requests.get(url, headers=headers, params=params, timeout=30)

        assert response.status_code == 200
        series = response.json()
        assert isinstance(series, list)
        # May or may not be empty depending on fuzzy matching


# ============================================================================
# Test: Sonarr Series in Library
# ============================================================================

class TestSonarrSeriesLibrary:
    """Tests for Sonarr series library operations."""

    @pytest.mark.integration
    def test_get_all_series(self, live_config):
        """Test fetching all series from library."""
        base_url = live_config['sonarr']['url'].rstrip('/')
        api_key = live_config['sonarr']['api_key']

        url = f"{base_url}/series"
        headers = {"X-Api-Key": api_key}

        response = requests.get(url, headers=headers, timeout=30)

        assert response.status_code == 200
        series = response.json()
        assert isinstance(series, list)

    @pytest.mark.integration
    def test_series_has_seasons(self, live_config):
        """Test that series in library have season information."""
        base_url = live_config['sonarr']['url'].rstrip('/')
        api_key = live_config['sonarr']['api_key']

        url = f"{base_url}/series"
        headers = {"X-Api-Key": api_key}

        response = requests.get(url, headers=headers, timeout=30)
        series_list = response.json()

        if len(series_list) > 0:
            series = series_list[0]
            assert 'seasons' in series
            assert isinstance(series['seasons'], list)


# ============================================================================
# Test: Sonarr Episode Operations
# ============================================================================

class TestSonarrEpisodes:
    """Tests for Sonarr episode operations."""

    @pytest.mark.integration
    def test_get_episodes_for_series(self, live_config):
        """Test fetching episodes for a series."""
        base_url = live_config['sonarr']['url'].rstrip('/')
        api_key = live_config['sonarr']['api_key']

        # First get a series from the library
        series_url = f"{base_url}/series"
        headers = {"X-Api-Key": api_key}

        series_response = requests.get(series_url, headers=headers, timeout=30)
        series_list = series_response.json()

        if len(series_list) == 0:
            pytest.skip("No series in Sonarr library to test with")

        series_id = series_list[0]['id']

        # Now get episodes
        episode_url = f"{base_url}/episode"
        params = {"seriesId": series_id}

        episode_response = requests.get(episode_url, headers=headers, params=params, timeout=30)

        assert episode_response.status_code == 200
        episodes = episode_response.json()
        assert isinstance(episodes, list)

    @pytest.mark.integration
    def test_episode_structure(self, live_config):
        """Test that episodes have expected structure."""
        base_url = live_config['sonarr']['url'].rstrip('/')
        api_key = live_config['sonarr']['api_key']

        # Get first series
        series_url = f"{base_url}/series"
        headers = {"X-Api-Key": api_key}

        series_response = requests.get(series_url, headers=headers, timeout=30)
        series_list = series_response.json()

        if len(series_list) == 0:
            pytest.skip("No series in Sonarr library to test with")

        series_id = series_list[0]['id']

        # Get episodes
        episode_url = f"{base_url}/episode"
        params = {"seriesId": series_id}

        episode_response = requests.get(episode_url, headers=headers, params=params, timeout=30)
        episodes = episode_response.json()

        if len(episodes) > 0:
            episode = episodes[0]
            required_fields = ['id', 'seriesId', 'seasonNumber', 'episodeNumber', 'title']
            for field in required_fields:
                assert field in episode, f"Episode missing required field: {field}"


# ============================================================================
# Test: Sonarr Command API
# ============================================================================

class TestSonarrCommands:
    """Tests for Sonarr command API (used for episode search)."""

    @pytest.mark.integration
    def test_command_endpoint_accessible(self, live_config):
        """Test that command endpoint is accessible."""
        base_url = live_config['sonarr']['url'].rstrip('/')
        api_key = live_config['sonarr']['api_key']

        # Get command status/history
        url = f"{base_url}/command"
        headers = {"X-Api-Key": api_key}

        response = requests.get(url, headers=headers, timeout=10)

        assert response.status_code == 200
        commands = response.json()
        assert isinstance(commands, list)


# ============================================================================
# Test: Sonarr Error Handling
# ============================================================================

class TestSonarrErrorHandling:
    """Tests for Sonarr API error handling."""

    @pytest.mark.integration
    def test_invalid_series_id(self, live_config):
        """Test error handling for invalid series ID."""
        base_url = live_config['sonarr']['url'].rstrip('/')
        api_key = live_config['sonarr']['api_key']

        url = f"{base_url}/series/999999999"
        headers = {"X-Api-Key": api_key}

        response = requests.get(url, headers=headers, timeout=10)

        # Should return 404 for non-existent series
        assert response.status_code == 404

    @pytest.mark.integration
    def test_invalid_episode_file_id(self, live_config):
        """Test error handling for invalid episode file ID."""
        base_url = live_config['sonarr']['url'].rstrip('/')
        api_key = live_config['sonarr']['api_key']

        url = f"{base_url}/episodefile/999999999"
        headers = {"X-Api-Key": api_key}

        response = requests.get(url, headers=headers, timeout=10)

        # Should return 404 for non-existent episode file
        assert response.status_code == 404

    @pytest.mark.integration
    def test_malformed_request(self, live_config):
        """Test error handling for malformed request."""
        base_url = live_config['sonarr']['url'].rstrip('/')
        api_key = live_config['sonarr']['api_key']

        url = f"{base_url}/episode"
        headers = {"X-Api-Key": api_key}
        # Missing required seriesId parameter
        params = {"seasonNumber": 1}

        response = requests.get(url, headers=headers, params=params, timeout=10)

        # Should handle gracefully (either 400 or return all episodes)
        assert response.status_code in [200, 400]
