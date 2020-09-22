#!/usr/bin/env python3
from gmusicapi import Mobileclient
from spotipy import Spotify, util, client
from dotenv import load_dotenv
from os import getenv
import logging
import json
from sys import exit, argv


# env
def load_env():
    load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(lineno)d -- %(message)s")

playlist_name = argv[1]

#################
# spotify
#################
class Spotify_client:
    def __init__(self, scope='playlist-modify-private', *args, **kwargs):
        client_id = getenv('SPOTIFY_client_id')
        client_secret = getenv('SPOTIFY_client_secret')
        self.username = getenv('SPOTIFY_username')
        redirect_uri = getenv('SPOTIFY_redirect_uri')

        # login
        logging.info("Starting Spotify client")
        token = util.prompt_for_user_token(self.username,scope,client_id=client_id,client_secret=client_secret,redirect_uri=redirect_uri)
        self.sp_client = Spotify(auth=token)

    def create_playlist(self, playlist_name):
        logging.debug(f'playlist_name: {playlist_name}')
        return self.sp_client.user_playlist_create(user=self.username, name=playlist_name, public=False)

    def search_track(self, search_string):
        logging.debug(f'search_string: {search_string}')
        return self.sp_client.search(search_string, limit=1)

    def add_to_playlist(self, playlist_id, track_ids):
        logging.debug(f'playlist_id: {playlist_id}, track_ids: {track_ids}')
        return self.sp_client.user_playlist_add_tracks(self.username, playlist_id, track_ids)
  

#################
# GPM
#################
class GPM_client:
    def __init__(self):
        logging.info("Starting GPM client")
        self.gpm_client = Mobileclient()
        # login
        while not self.gpm_client.is_authenticated():
            logging.info("Logging you in...")
            if not self.gpm_client.oauth_login(device_id=Mobileclient.FROM_MAC_ADDRESS, oauth_credentials='./.gpmtoken'):
              logging.debug("No previous credentials - performing Oauth")
              self.gpm_client.perform_oauth(open_browser=True, storage_filepath='./.gpmtoken') 
   

#################
# Common
#################
def main():
    
    '''
    Playlists data structure is a list of dicts - each playlist, "name" field for playlist name and "tracks" list for all tracks
    Tracks is a list, each with a track ID
    We can grab the name field to know what playlists to create and the track ID to convert/search
    '''

     # load env
    logging.debug('Loading env')
    load_env()

    # initialize GPM
    logging.debug('loading GPM')
    gpm = GPM_client()

    # Get a dump of the playlist
    logging.info(f'Getting {playlist_name}')
    full_playlist_list = gpm.gpm_client.get_all_user_playlist_contents()

    for playlist in full_playlist_list:

        # create the new playlists GPM->Spotify
        logging.info(f'Looking for {playlist_name}')
        name = playlist.get('name')

        if playlist_name in name:
            
            # search and add the track into new album
            logging.info(f'Adding tracks to {name}')
            # need to modify the scope
            spot = Spotify_client(scope='user-library-modify')

            for track in playlist.get('tracks'):
                try:
                    track_data = track.get('track')
                    artist = track_data.get('artist')
                    title = track_data.get('title')
                    logging.info(f'Searching {artist} {title}')

                    # search by artist and title
                    search_result = spot.search_track(f'{artist} {title}')
                    logging.debug(search_result)
                    #todo: This search relies on the naming structure being similar. Can be improved with regex
                    track_uri = search_result.get('tracks').get('items')[0].get('uri')
                    logging.debug(track_uri)

                    # add to new playlist
                    logging.info(f'Adding {track_uri} to {name}')
                    #todo: speed could be improved with async
                    playlist_add = spot.sp_client.current_user_saved_tracks_add([track_uri])
                    logging.info('Song added')
                    logging.debug(playlist_add)

                # thrown when 'tracks' is missing    
                except AttributeError as e:
                    logging.info(e)
                    logging.info("This track does not have metadata - probably uploaded. Skipping")
                    with open('./errored-tracks_thumbs-up.log', 'a') as file:
                        file.writelines(f'playist: {name}\n')
                # cheap way to fix this, almost certainly means the track doesn't exist on spotify
                except IndexError:
                    logging.info("Index out of range: This track may not exist or was not found. Skipping")
                    with open('./errored-tracks_thumbs-up.log', 'a') as file:
                        file.writelines(f'playist: {name} -- {artist} - {title}\n')
                # cheap fix for random 500 errors
                except client.SpotifyException:
                    logging.info("500 error - failed track written to log. It might have been added anyway, check later")
                    with open('./errored-tracks_thumbs-up.log', 'a') as file:
                        file.writelines(f'playist: {name} -- {artist} - {title}\n')


if __name__ == "__main__":
   main()
   print("Finished\nPlease check errored-tracks.log for missing tracks")
