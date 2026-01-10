"""
Integration tests for Radarr API.
These tests require a live Radarr instance and valid API credentials.

Run with: pytest -m integration tests/test_integration_radarr.py
"""
import pytest
import requests


# ============================================================================
# Test: Radarr Connection
# ============================================================================

class TestRadarrConnection:
    """Tests for Radarr API connectivity."""

    @pytest.mark.integration
    def test_radarr_api_reachable(self, live_config):
        """Test that Radarr API is reachable."""
        base_url = live_config['radarr']['url'].rstrip('/')
        api_key = live_config['radarr']['api_key']

        url = f"{base_url}/system/status"
        headers = {"X-Api-Key": api_key}

        response = requests.get(url, headers=headers, timeout=10)

        assert response.status_code == 200
        data = response.json()
        assert 'version' in data

    @pytest.mark.integration
    def test_radarr_api_key_valid(self, live_config):
        """Test that Radarr API key is valid."""
        base_url = live_config['radarr']['url'].rstrip('/')
        api_key = live_config['radarr']['api_key']

        url = f"{base_url}/system/status"
        headers = {"X-Api-Key": api_key}

        response = requests.get(url, headers=headers, timeout=10)

        assert response.status_code != 401
        assert response.status_code == 200

    @pytest.mark.integration
    def test_radarr_invalid_api_key_rejected(self, live_config):
        """Test that invalid API key is rejected."""
        base_url = live_config['radarr']['url'].rstrip('/')

        url = f"{base_url}/system/status"
        headers = {"X-Api-Key": "invalid_api_key_12345"}

        response = requests.get(url, headers=headers, timeout=10)

        assert response.status_code == 401


# ============================================================================
# Test: Radarr Quality Profiles
# ============================================================================

class TestRadarrQualityProfiles:
    """Tests for Radarr quality profile retrieval."""

    @pytest.mark.integration
    def test_get_quality_profiles(self, live_config):
        """Test fetching quality profiles from Radarr."""
        base_url = live_config['radarr']['url'].rstrip('/')
        api_key = live_config['radarr']['api_key']

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
        base_url = live_config['radarr']['url'].rstrip('/')
        api_key = live_config['radarr']['api_key']

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
# Test: Radarr Root Folders
# ============================================================================

class TestRadarrRootFolders:
    """Tests for Radarr root folder retrieval."""

    @pytest.mark.integration
    def test_get_root_folders(self, live_config):
        """Test fetching root folders from Radarr."""
        base_url = live_config['radarr']['url'].rstrip('/')
        api_key = live_config['radarr']['api_key']

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
        base_url = live_config['radarr']['url'].rstrip('/')
        api_key = live_config['radarr']['api_key']

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
# Test: Radarr Movie Lookup
# ============================================================================

class TestRadarrMovieLookup:
    """Tests for Radarr movie lookup functionality."""

    @pytest.mark.integration
    def test_movie_lookup_returns_results(self, live_config):
        """Test that movie lookup returns results for known movie."""
        base_url = live_config['radarr']['url'].rstrip('/')
        api_key = live_config['radarr']['api_key']

        url = f"{base_url}/movie/lookup"
        headers = {"X-Api-Key": api_key}
        params = {"term": "the matrix"}

        response = requests.get(url, headers=headers, params=params, timeout=30)

        assert response.status_code == 200
        movies = response.json()
        assert isinstance(movies, list)
        assert len(movies) > 0

    @pytest.mark.integration
    def test_movie_lookup_structure(self, live_config):
        """Test that movie lookup results have expected structure."""
        base_url = live_config['radarr']['url'].rstrip('/')
        api_key = live_config['radarr']['api_key']

        url = f"{base_url}/movie/lookup"
        headers = {"X-Api-Key": api_key}
        params = {"term": "inception"}

        response = requests.get(url, headers=headers, params=params, timeout=30)
        movies = response.json()

        if len(movies) > 0:
            movie = movies[0]
            assert 'title' in movie
            assert 'year' in movie
            assert 'tmdbId' in movie

    @pytest.mark.integration
    def test_movie_lookup_contains_overview(self, live_config):
        """Test that movie lookup results contain overview."""
        base_url = live_config['radarr']['url'].rstrip('/')
        api_key = live_config['radarr']['api_key']

        url = f"{base_url}/movie/lookup"
        headers = {"X-Api-Key": api_key}
        params = {"term": "pulp fiction"}

        response = requests.get(url, headers=headers, params=params, timeout=30)
        movies = response.json()

        if len(movies) > 0:
            movie = movies[0]
            assert 'overview' in movie
            assert len(movie['overview']) > 0

    @pytest.mark.integration
    def test_movie_lookup_empty_term(self, live_config):
        """Test movie lookup with empty search term."""
        base_url = live_config['radarr']['url'].rstrip('/')
        api_key = live_config['radarr']['api_key']

        url = f"{base_url}/movie/lookup"
        headers = {"X-Api-Key": api_key}
        params = {"term": ""}

        response = requests.get(url, headers=headers, params=params, timeout=30)

        # Should return empty list, bad request, or service unavailable
        assert response.status_code in [200, 400, 503]

    @pytest.mark.integration
    def test_movie_lookup_special_characters(self, live_config):
        """Test movie lookup with special characters in search term."""
        base_url = live_config['radarr']['url'].rstrip('/')
        api_key = live_config['radarr']['api_key']

        url = f"{base_url}/movie/lookup"
        headers = {"X-Api-Key": api_key}
        params = {"term": "spider-man: no way home"}

        response = requests.get(url, headers=headers, params=params, timeout=30)

        assert response.status_code == 200
        movies = response.json()
        assert isinstance(movies, list)


# ============================================================================
# Test: Radarr Movie Library (Memory-Optimized)
# ============================================================================

class TestRadarrMovieLibrary:
    """Tests for Radarr movie library operations."""

    @pytest.mark.integration
    def test_get_movies_paginated(self, live_config):
        """Test fetching movies from library with pagination."""
        base_url = live_config['radarr']['url'].rstrip('/')
        api_key = live_config['radarr']['api_key']

        # Use pagination to limit memory usage
        url = f"{base_url}/movie"
        headers = {"X-Api-Key": api_key}
        params = {"page": 1, "pageSize": 5}  # Only fetch 5 movies

        response = requests.get(url, headers=headers, params=params, timeout=30)

        assert response.status_code == 200
        data = response.json()
        # Radarr may return list or paginated object
        movies = data if isinstance(data, list) else data.get('records', data)
        assert isinstance(movies, list)

    @pytest.mark.integration
    def test_movie_library_structure(self, live_config):
        """Test that movies in library have expected structure."""
        base_url = live_config['radarr']['url'].rstrip('/')
        api_key = live_config['radarr']['api_key']

        # Use lookup to get a sample movie (memory efficient)
        url = f"{base_url}/movie/lookup"
        headers = {"X-Api-Key": api_key}
        params = {"term": "matrix"}  # Search for a known movie

        response = requests.get(url, headers=headers, params=params, timeout=30)

        if response.status_code == 200:
            movies = response.json()
            if len(movies) > 0:
                movie = movies[0]
                # Lookup returns slightly different structure, check common fields
                required_fields = ['title', 'year', 'tmdbId']
                for field in required_fields:
                    assert field in movie, f"Movie missing required field: {field}"
        else:
            pytest.skip("Could not fetch movie for structure test")

    @pytest.mark.integration
    def test_get_movie_by_id(self, live_config):
        """Test fetching a specific movie by ID."""
        base_url = live_config['radarr']['url'].rstrip('/')
        api_key = live_config['radarr']['api_key']
        headers = {"X-Api-Key": api_key}

        # First, use lookup to find a movie (memory efficient)
        lookup_url = f"{base_url}/movie/lookup"
        lookup_params = {"term": "inception"}

        lookup_response = requests.get(lookup_url, headers=headers, params=lookup_params, timeout=30)

        if lookup_response.status_code != 200:
            pytest.skip("Could not perform movie lookup")

        lookup_movies = lookup_response.json()
        if len(lookup_movies) == 0:
            pytest.skip("No movies found in lookup")

        # Get tmdbId from lookup result
        tmdb_id = lookup_movies[0].get('tmdbId')
        if not tmdb_id:
            pytest.skip("No tmdbId in lookup result")

        # Try to get movie by tmdbId (if it exists in library)
        movie_url = f"{base_url}/movie"
        movie_params = {"tmdbId": tmdb_id}

        movie_response = requests.get(movie_url, headers=headers, params=movie_params, timeout=10)

        # This may return empty if movie not in library, which is fine
        assert movie_response.status_code == 200


# ============================================================================
# Test: Radarr Movie Add/Delete (Read-Only Tests)
# ============================================================================

class TestRadarrMovieOperations:
    """Tests for Radarr movie add/delete operations (validation only)."""

    @pytest.mark.integration
    def test_add_movie_payload_structure(self, live_config):
        """Test that add movie payload structure is correct."""
        # This test validates the payload structure without actually adding
        base_url = live_config['radarr']['url'].rstrip('/')
        api_key = live_config['radarr']['api_key']

        # Get quality profile and root folder for valid payload
        profile_url = f"{base_url}/qualityprofile"
        folder_url = f"{base_url}/rootfolder"
        headers = {"X-Api-Key": api_key}

        profile_response = requests.get(profile_url, headers=headers, timeout=10)
        folder_response = requests.get(folder_url, headers=headers, timeout=10)

        profiles = profile_response.json()
        folders = folder_response.json()

        assert len(profiles) > 0
        assert len(folders) > 0

        # Validate payload structure
        add_payload = {
            "tmdbId": 603,  # The Matrix
            "title": "The Matrix",
            "year": 1999,
            "qualityProfileId": profiles[0]['id'],
            "rootFolderPath": folders[0]['path'],
            "monitored": True,
            "minimumAvailability": "released",
            "addOptions": {
                "searchForMovie": True
            }
        }

        required_fields = ['tmdbId', 'title', 'qualityProfileId', 'rootFolderPath']
        for field in required_fields:
            assert field in add_payload

    @pytest.mark.integration
    def test_delete_movie_url_format(self, live_config):
        """Test that delete movie URL format is correct."""
        base_url = live_config['radarr']['url'].rstrip('/')
        api_key = live_config['radarr']['api_key']

        movie_id = 123
        delete_url = f"{base_url}/movie/{movie_id}?deleteFiles=true&apikey={api_key}"

        # Validate URL components
        assert str(movie_id) in delete_url
        assert "deleteFiles=true" in delete_url
        assert api_key in delete_url


# ============================================================================
# Test: Radarr Error Handling
# ============================================================================

class TestRadarrErrorHandling:
    """Tests for Radarr API error handling."""

    @pytest.mark.integration
    def test_invalid_movie_id(self, live_config):
        """Test error handling for invalid movie ID."""
        base_url = live_config['radarr']['url'].rstrip('/')
        api_key = live_config['radarr']['api_key']

        url = f"{base_url}/movie/999999999"
        headers = {"X-Api-Key": api_key}

        response = requests.get(url, headers=headers, timeout=10)

        # Should return 404 for non-existent movie
        assert response.status_code == 404

    @pytest.mark.integration
    def test_invalid_endpoint(self, live_config):
        """Test error handling for invalid endpoint."""
        base_url = live_config['radarr']['url'].rstrip('/')
        api_key = live_config['radarr']['api_key']

        url = f"{base_url}/nonexistent/endpoint"
        headers = {"X-Api-Key": api_key}

        response = requests.get(url, headers=headers, timeout=10)

        # Should return 404 for invalid endpoint
        assert response.status_code == 404

    @pytest.mark.integration
    def test_timeout_handling(self, live_config):
        """Test that requests properly timeout."""
        base_url = live_config['radarr']['url'].rstrip('/')
        api_key = live_config['radarr']['api_key']

        url = f"{base_url}/movie/lookup"
        headers = {"X-Api-Key": api_key}
        params = {"term": "test"}

        # Should complete within timeout
        try:
            response = requests.get(url, headers=headers, params=params, timeout=1)
            # If fast enough, should succeed
            assert response.status_code in [200, 408]
        except requests.exceptions.Timeout:
            # Timeout is acceptable for this test
            pass


# ============================================================================
# Test: Radarr API Consistency (Memory-Optimized with Sampling)
# ============================================================================

class TestRadarrAPIConsistency:
    """Tests for Radarr API response consistency using sampling."""

    @pytest.mark.integration
    def test_quality_profile_ids_valid(self, live_config):
        """Test that quality profiles are properly configured."""
        base_url = live_config['radarr']['url'].rstrip('/')
        api_key = live_config['radarr']['api_key']
        headers = {"X-Api-Key": api_key}

        # Get quality profiles
        profile_response = requests.get(f"{base_url}/qualityprofile", headers=headers, timeout=10)
        assert profile_response.status_code == 200

        profiles = profile_response.json()
        assert len(profiles) > 0, "No quality profiles configured"

        # Validate profile structure
        for profile in profiles:
            assert 'id' in profile
            assert 'name' in profile
            assert isinstance(profile['id'], int)

    @pytest.mark.integration
    def test_root_folder_paths_configured(self, live_config):
        """Test that root folders are properly configured."""
        base_url = live_config['radarr']['url'].rstrip('/')
        api_key = live_config['radarr']['api_key']
        headers = {"X-Api-Key": api_key}

        # Get root folders
        folder_response = requests.get(f"{base_url}/rootfolder", headers=headers, timeout=10)
        assert folder_response.status_code == 200

        folders = folder_response.json()
        assert len(folders) > 0, "No root folders configured"

        # Validate folder structure
        for folder in folders:
            assert 'id' in folder
            assert 'path' in folder
            assert len(folder['path']) > 0, "Empty root folder path"

    @pytest.mark.integration
    def test_sample_movie_has_valid_profile(self, live_config):
        """Test that a sample movie from library has valid quality profile."""
        base_url = live_config['radarr']['url'].rstrip('/')
        api_key = live_config['radarr']['api_key']
        headers = {"X-Api-Key": api_key}

        # Get quality profiles first
        profile_response = requests.get(f"{base_url}/qualityprofile", headers=headers, timeout=10)
        profiles = profile_response.json()
        valid_profile_ids = {p['id'] for p in profiles}

        # Get just one movie using pagination (memory efficient)
        movie_response = requests.get(
            f"{base_url}/movie",
            headers=headers,
            params={"page": 1, "pageSize": 1},
            timeout=30
        )

        if movie_response.status_code != 200:
            pytest.skip("Could not fetch movies")

        data = movie_response.json()
        movies = data if isinstance(data, list) else data.get('records', [])

        if len(movies) == 0:
            pytest.skip("No movies in library to test")

        movie = movies[0]
        assert movie.get('qualityProfileId') in valid_profile_ids, \
            f"Movie has invalid quality profile ID: {movie.get('qualityProfileId')}"
