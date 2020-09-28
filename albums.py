#!/usr/bin/env python3
from typing import Collection, Iterable, Callable

from gmusicapi import Mobileclient
from spotipy import Spotify, util, client
from dotenv import load_dotenv
from os import getenv
import logging
import json
from sys import exit


# env
def load_env():
    load_dotenv()


# utility
def flat_map(f: Callable[[any], Collection], xs: Iterable):
    return [y for ys in xs for y in f(ys)]


logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(lineno)d -- %(message)s")


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
        token = util.prompt_for_user_token(self.username, scope, client_id=client_id, client_secret=client_secret,
                                           redirect_uri=redirect_uri)
        self.sp_client = Spotify(auth=token)

    def create_playlist(self, playlist_name):
        logging.debug(f'playlist_name: {playlist_name}')
        return self.sp_client.user_playlist_create(user=self.username, name=playlist_name, public=False)

    def search_track(self, search_string):
        logging.debug(f'search_string: {search_string}')
        return self.sp_client.search(search_string, limit=1)

    def search_album(self, album_name, artist_name):
        artist_string = f'artist:"{artist_name}"' \
            if artist_name and "various" not in artist_name.lower() \
            else ""
        search_string = f'album:"{album_name}" {artist_string}'
        logging.debug(search_string)
        return self.sp_client.search(search_string, limit=1, type="album")

    def add_to_playlist(self, playlist_id, track_ids):
        logging.debug(f'playlist_id: {playlist_id}, track_ids: {track_ids}')
        return self.sp_client.playlist_add_items(self.username, playlist_id, track_ids)


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
            if not self.gpm_client.oauth_login(device_id=Mobileclient.FROM_MAC_ADDRESS,
                                               oauth_credentials='./.gpmtoken'):
                logging.debug("No previous credentials - performing Oauth")
                self.gpm_client.perform_oauth(open_browser=True, storage_filepath='./.gpmtoken')

            #################


def try_getting_album(gpm: GPM_client, album_id: str):
    from gmusicapi import CallFailure
    result = []
    try:
        result.append(gpm.gpm_client.get_album_info(album_id, include_tracks=False))
    except CallFailure:
        logging.info("This album does not exist publicly on GPM. Skipping")
        with open('./errored-albums.log', 'a') as file:
            file.writelines(f'album: {album_id}\n')
    return result


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

    # initialize spotify
    logging.debug('loading Spotify')
    spot = Spotify_client(scope='user-library-modify')

    # get a dump of the songs
    logging.info('getting all songs')
    songs = gpm.gpm_client.get_all_songs()

    # get album info
    logging.info('getting all albums')
    album_ids = set(map(lambda song: song['albumId'], filter(lambda song: 'albumId' in song, songs)))
    albums = list(flat_map(lambda album_id: try_getting_album(gpm, album_id), album_ids))

    for album in albums:
        try:
            # search by title and artist
            search_result = spot.search_album(album['name'], album['albumArtist'])
            logging.debug(search_result)
            album_uri = search_result.get('albums').get('items')[0].get('uri')
            logging.debug(album_uri)

            # add to saved albums
            logging.info(f"Adding {album_uri} to saved albums")
            album_add = spot.sp_client.current_user_saved_albums_add([album_uri])
            logging.info('Album added')
            logging.debug(album_add)

        # cheap way to fix this, almost certainly means the track doesn't exist on spotify
        except IndexError:
            logging.info("Index out of range: This track may not exist or was not found. Skipping")
            with open('./errored-albums.log', 'a') as file:
                file.writelines(f"album: {album['name']} -- {album['albumArtist']}\n")
        # cheap fix for random 500 errors
        except client.SpotifyException:
            logging.info("500 error - failed track written to log. It might have been added anyway, check later")
            with open('./errored-albums.log', 'a') as file:
                file.writelines(f"album: {album['name']} -- {album['albumArtist']}\n")


if __name__ == "__main__":
    main()
    print("Finished\nPlease check errored-albums.log for missing tracks")
