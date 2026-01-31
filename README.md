# Wikipedia Race
Challenge your friends to a multiplayer version of Wikipedia race!

## Contact Information
Email: excaliber632@gmail.com

## Installation
Navigate to the Releases page and choose a release. Your best option would be to use the most recent version. Download the .zip archive and extract its contents. Run the setup file and choose your desired install destination.

### Uninstallation
To uninstall the game, run the included uninstaller.

NOTE: Wikipedia Race relies on the Selenium package for browsing Wikipedia's site. Presently, if you wish to remove the webdriver on Windows, you must navigate to {OS drive}/Users/{user}/.cache/selenium and manually delete the folder. This feature is planned to be integrated into the uninstaller in the future.

## Known Issues
* ~~When quitting the game or playing again, the webdriver will open and close itself while reconnecting.~~ (ae7b740)
* ~~Quitting after playing more than one round continuously results in application hanging.~~ (dbf75ba)
* ~~Extra submit screen after exitting application.~~ (9d73b42)
* Quitting during game can sometimes cause geckodriver persistence.

## Future Features
* Special host menu and options.
* When player is finished, show them a "live feed" of players still searching.
* Countdown mode: Players aim for a score to win the lobby.

##
A Python-based server and client for playing multiplayer Wikipedia races.
