# Features

(RE)grabbar uses discord and Sonarr/Radarr to allow discord users to 'regrab' content.  
Regrabbing content will have the bot delete the original file and start a new search for the content.

# Installation and setup

## Requirements

- Sonarr
- Radarr
- A Discord server
- Docker
- [A Discord bot token](https://www.digitaltrends.com/gaming/how-to-make-a-discord-bot/)
    - Permissions required:
        - Manage Channels
        - View Channels
        - Send Messages
        - Manage Messages
        - Read Message History
        - Add Reactions
        - Manage Emojis


Regrabarr runs as a Docker container. The Dockerfile is included in this repository or can be pulled
from [Docker Hub](https://hub.docker.com/r/mtrogman/regrabarr)
or [GitHub Packages](https://github.com/mtrogman/regrabarr/pkgs/container/regrabarr).

### Volumes

You will need to map the following volumes:

| Host Path              | Container Path | Reason                                                                                            |
|------------------------|----------------|---------------------------------------------------------------------------------------------------|
| /path/to/config/folder | /config        | Required, path to the folder containing the configuration file                                    |



You can also set these variables via a configuration file:

1. Map the `/config` directory (see volumes above)
2. Enter the mapped directory on your host machine
3. Rename the ``config.yml.example`` file in the path to ``config.yml``
4. Complete the variables in ``config.yml``

# Development

This bot is still a work in progress. If you have any ideas for improving or adding to (RE)grabarr, please open an issue
or a pull request.

# Contact

Please leave a pull request if you would like to contribute.

Feel free to check out my other projects here on [GitHub](https://github.com/mtrogman) or join my Discord server below.

<div align="center">
	<p>
		<a href="https://discord.gg/jp68q5C3pr"><img src="https://discordapp.com/api/guilds/783077604101455882/widget.png?style=banner2" alt="" /></a>
	</p>
</div>

## Contributors ✨

Thanks goes to these wonderful people:

<!-- ALL-CONTRIBUTORS-LIST:START - Do not remove or modify this section -->
<!-- prettier-ignore-start -->
<!-- markdownlint-disable -->

### Contributors

<table>
<tr>
    <td align="center" style="word-wrap: break-word; width: 75.0; height: 75.0">
        <a href=https://github.com/mtrogman>
            <img src=https://avatars.githubusercontent.com/u/47980633?v=4 width="50;"  style="border-radius:50%;align-items:center;justify-content:center;overflow:hidden;padding-top:10px" alt=trog/>
            <br />
            <sub style="font-size:14px"><b>trog</b></sub>
        </a>
    </td>
</tr>
</table>

<table>

</table>

<!-- markdownlint-restore -->
<!-- prettier-ignore-end -->

<!-- ALL-CONTRIBUTORS-LIST:END -->
