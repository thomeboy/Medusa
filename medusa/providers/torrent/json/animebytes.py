# coding=utf-8

"""Provider code for AnimeBytes."""

from __future__ import unicode_literals

import logging
import re

from medusa import tv
from medusa.helper.common import convert_size
from medusa.logger.adapters.style import BraceAdapter
from medusa.providers.torrent.torrent_provider import TorrentProvider
from medusa.scene_numbering import get_indexer_numbering

from requests.compat import urljoin

log = BraceAdapter(logging.getLogger(__name__))
log.logger.addHandler(logging.NullHandler())

SEASON_PACK = 1
SINGLE_EP = 2
MULTI_EP = 3
MULTI_SEASON = 4
COMPLETE = 5
OTHER = 6


class AnimeBytes(TorrentProvider):
    """AnimeBytes Torrent provider."""

    def __init__(self):
        """Initialize the class."""
        super(AnimeBytes, self).__init__('AnimeBytes')

        # Credentials
        self.username = None
        self.passkey = None

        # URLs
        self.url = 'https://animebytes.tv'
        self.urls = {
            'search': urljoin(self.url, 'scrape.php'),
        }

        # Proper Strings
        self.proper_strings = []

        # Miscellaneous Options
        self.freeleech = True
        self.anime_only = True

        # Cache
        self.cache = tv.Cache(self, min_time=30)

    def search(self, search_strings, age=0, ep_obj=None, **kwargs):
        """
        Search a provider and parse the results.

        :param search_strings: A dict with mode (key) and the search value (value)
        :param age: Not used
        :param ep_obj: Not used
        :returns: A list of search results (structure)
        """
        results = []

        # Search Params
        search_params = {
            'filter_cat[1]': '1',
            'filter_cat[5]': '1',
            'action': 'advanced',
            'search_type': 'title',
            'year': '',
            'year2': '',
            'tags': '',
            'tags_type': '0',
            'sort': 'time_added',
            'way': 'desc',
            'hentai': '2',
            'anime[tv_series]': '1',
            'anime[tv_special]': '1',
            'releasegroup': '',
            'epcount': '',
            'epcount2': '',
            'artbooktitle': '',
            'type': 'anime',
            'username': self.username,
            'torrent_pass': self.passkey,
        }

        show = None
        if ep_obj:
            show = ep_obj.series

        for mode in search_strings:
            log.debug('Search Mode: {0}', mode)

            for search_string in search_strings[mode]:

                if mode != 'RSS':
                    log.debug('Search string: {search}',
                              {'search': search_string})
                    search_params['searchstr'] = search_string

                response = self.session.get(self.urls['search'], params=search_params)
                if not response or not response.content:
                    log.debug('No data returned from provider')
                    continue

                try:
                    jdata = response.json()
                except ValueError:
                    log.debug('No data returned from provider')
                    continue

                if jdata['Matches'] == 0:
                    log.debug('0 results returned from provider for this search')
                    continue

                results += self.parse(jdata, mode, show)

        return results

    def parse(self, data, mode, show=None):
        """
        Parse search results for items.

        :param data: The raw response from a search
        :param mode: The current mode used to search, e.g. RSS

        :return: A list of items found
        """
        def get_season_from_series_name(series_name):
            """
            Compare the series_name to the aliases available for the searched show.

            Compare names and try to map the scene_season to an indexer season if available.
            """
            if not show:
                return

            def clean(title):
                """Clean title, for easier comparison."""
                for char in '-:; ':
                    title = title.replace(char, '')
                return title.lower()

            for alias in show.aliases:
                if clean(alias.title) == clean(series_name):
                    return get_indexer_numbering(show, alias.season)[0]
            return

        items = []

        group_rows = data.get('Groups')
        if not group_rows:
            log.debug('Data returned from provider does not contain any torrents')
            return items

        for group in group_rows:
            torrent_rows = group.get('Torrents')
            if not torrent_rows:
                continue

            for row in torrent_rows:
                properties_string = row.get('Property').rstrip(' |').replace(' ', '')
                # Hack for the h264 10bit stuff
                properties_string = properties_string.replace('h26410-bit', 'h264|hi10p')
                properties = properties_string.split('|')
                download_url = row.get('Link')
                if not (download_url or all(properties)):
                    continue

                # Get rid of freeleech from properties
                if properties[-1] == 'Freeleech':
                    del properties[-1]
                elif self.freeleech:
                    # Discard if we wanted free leech
                    continue

                tags = '{torrent_source}.{torrent_container}.{torrent_codec}.{torrent_res}.' \
                       '{torrent_audio}'.format(torrent_source=properties[0],
                                                torrent_container=properties[1],
                                                torrent_codec=properties[2],
                                                torrent_res=properties[3],
                                                torrent_audio=properties[4])

                last_field = re.match(r'(.*)\((.*)\)', properties[-1])

                # subs = last_field.group(1) if last_field else ''
                release_group = '-{0}'.format(last_field.group(2)) if last_field else ''

                release_type = OTHER
                season = None
                episode = None
                multi_ep_start = None
                multi_ep_end = None
                title = None

                # Attempt and get a season or episode number
                title_info = row.get('EditionData').get('EditionTitle')

                def match_season_from_series_name():
                    """Try getting a season from the series name"""
                    season_match = re.match(r'.+[sS]eason.(\d+)$', group.get('SeriesName'))
                    if season_match:
                        return season_match.group(1)
                    # Try getting the season from the SeriesName.
                    return get_season_from_series_name(group.get('SeriesName'))

                if title_info != '':
                    if title_info.startswith('Episodes'):
                        multi_ep_match = re.match(r'Episodes (\d+)-(\d+)', title_info)
                        if multi_ep_match:
                            multi_ep_start = multi_ep_match.group(1)
                            multi_ep_end = multi_ep_match.group(2)
                        release_type = MULTI_EP
                    elif title_info.startswith('Episode'):
                        episode = re.match('^Episode.([0-9]+)', title_info).group(1)
                        release_type = SINGLE_EP

                        season_match = re.match(r'.+[sS]eason.(\d+)$', group.get('SeriesName'))
                        if season_match:
                            season = season_match.group(1)
                        else:
                            match_season_from_series_name()
                    elif title_info.startswith('Season'):
                        if re.match(r'Season.[0-9]+-[0-9]+.\([0-9-]+\)', title_info):
                            # We can read the season AND the episodes, but we can only process multiep.
                            # So i've chosen to use it like 12-23 or 1-12.
                            match = re.match(r'Season.([0-9]+)-([0-9]+).\(([0-9-]+)\)', title_info)
                            episode = match.group(3).upper()
                            season = '{0}-{1}'.format(match.group(1), match.group(2))
                            release_type = MULTI_SEASON
                        else:
                            season = re.match('Season.([0-9]+)', title_info).group(1)

                            # Try getting the season from the group['SeriesName']
                            if not season:
                                season = match_season_from_series_name()
                            release_type = SEASON_PACK
                elif group.get('EpCount') > 0:
                    # This is a season pack.
                    # 13 episodes -> SXXEXX-EXX
                    episode = group.get('EpCount')
                    # Try to get the season
                    season = match_season_from_series_name()
                    release_type = SEASON_PACK

                # These are probably specials which we just can't handle anyways
                if release_type == OTHER:
                    continue

                if release_type == SINGLE_EP:
                    # Create the single episode release_name (use the shows default title)
                    title = '{title}.{season}{episode}.{tags}' \
                            '{release_group}'.format(title=show.name,
                                                     season='S{0}'.format(season) if season else 'S01',
                                                     episode='E{0}'.format(episode),
                                                     tags=tags,
                                                     release_group=release_group)
                if release_type == MULTI_EP:
                    # Create the multi-episode release_name
                    # Multiple.Episode.TV.Show.SXXEXX-EXX[Episode.Part].[Episode.Title].TAGS.[LANGUAGE].720p.FORMAT.x264-GROUP
                    title = '{title}.{season}{multi_episode_start}-{multi_episode_end}.{tags}' \
                            '{release_group}'.format(title=group.get('SeriesName'),
                                                     season='S{0}'.format(season) if season else 'S01',
                                                     multi_episode_start='E{0}'.format(multi_ep_start),
                                                     multi_episode_end='E{0}'.format(multi_ep_end),
                                                     tags=tags,
                                                     release_group=release_group)
                if release_type == SEASON_PACK:
                    # Create the season pack release_name
                    # if `Season` is already in the SeriesName, we ommit adding it another time.
                    if season:
                        title = '{title}.{season}.{tags}' \
                            '{release_group}'.format(title=show.name,
                                                     season='S{0}'.format(season),
                                                     tags=tags,
                                                     release_group=release_group)
                    else:
                        # If season not found, that this might be a season 1 name, or season exception.
                        # In both cases, we can omit the season tag.
                        title = '{title}.{tags}' \
                            '{release_group}'.format(title=group.get('SeriesName'),
                                                     tags=tags,
                                                     release_group=release_group)

                if release_type == MULTI_SEASON:
                    # Create the multi season pack release_name
                    # Multiple.Episode.TV.Show.EXX-EXX[Episode.Part].[Episode.Title].TAGS.[LANGUAGE].720p.FORMAT.x264-GROUP
                    title = '{title}.{episode}.{tags}' \
                            '{release_group}'.format(title=group.get('SeriesName'),
                                                     episode=episode,
                                                     tags=tags,
                                                     release_group=release_group)

                seeders = row.get('Seeders')
                leechers = row.get('Leechers')
                pubdate = self.parse_pubdate(row.get('UploadTime'))

                # Filter unseeded torrent
                if seeders < self.minseed:
                    if mode != 'RSS':
                        log.debug("Discarding torrent because it doesn't meet the"
                                  ' minimum seeders: {0}. Seeders: {1}',
                                  title, seeders)
                    continue

                size = convert_size(row.get('Size'), default=-1)

                item = {
                    'title': title,
                    'link': download_url,
                    'size': size,
                    'seeders': seeders,
                    'leechers': leechers,
                    'pubdate': pubdate,
                }

                if mode != 'RSS':
                    log.debug('Found result: {0} with {1} seeders and {2} leechers',
                              title, seeders, leechers)

                items.append(item)

        return items

    def _get_episode_search_strings(self, episode, add_string=''):
        """Override method because AnimeBytes doesn't support searching showname + episode number."""
        if not episode:
            return []

        search_string = {
            'Episode': []
        }

        for show_name in episode.series.get_all_possible_names(season=episode.scene_season):
            search_string['Episode'].append(show_name.strip())

        return [search_string]

    def _get_season_search_strings(self, episode):
        """Override method because AnimeBytes doesn't support searching showname + season number."""
        search_string = {
            'Season': []
        }

        for show_name in episode.series.get_all_possible_names(season=episode.scene_season):
            search_string['Season'].append(show_name.strip())

        return [search_string]


provider = AnimeBytes()
