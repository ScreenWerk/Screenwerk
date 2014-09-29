from os import path

from tornado import ioloop
from tornado import locale
from tornado import web
from tornado import httpserver
from tornado import options
from tornado import version

import hashlib
import json
import logging
import mimetypes
import random
import string

from croniter import croniter
from datetime import datetime
from email import utils
from operator import itemgetter

from helper import *
from db import *




class Schedule():
    days = 7
    def get_schedule(self, entity_id):
        now = datetime.datetime.now()
        last_day = now + datetime.timedelta(days=self.days)
        schedule_dict = {}
        files_dict = {}

        # get screen
        screen = self.get_entities(entity_id=entity_id, limit=1, only_public=True)
        if not screen:
            return {}

        # get group
        group_id = screen.get('properties', {}).get('screen-group', {}).get('values', [{}])[0].get('db_value')
        if not group_id:
            return {}
        group = self.get_entities(entity_id=group_id, limit=1, only_public=True)
        if not group:
            return {}

        # get configuration
        configuration_id = group.get('properties', {}).get('configuration', {}).get('values', [{}])[0].get('db_value')
        if not configuration_id:
            return {}
        configuration = self.get_entities(entity_id=configuration_id, limit=1, only_public=True)
        if not configuration:
            return {}

        update_interval = configuration.get('properties', {}).get('update-interval', {}).get('values', [{}])[0].get('value', 60)

        # get schedules
        schedule_ids = self.get_relatives(ids_only=True, entity_id=configuration_id, relationship_definition_keyname='child', entity_definition_keyname='sw-schedule', only_public=True)
        if not schedule_ids:
            return {}
        schedules = self.get_entities(entity_id=schedule_ids, only_public=True)
        if not schedules:
            return {}

        for s in schedules:
            # get schedule valid-from date
            valid_from = s.get('properties', {}).get('valid-from', {}).get('values', [{}])[0].get('db_value')
            if valid_from and valid_from > last_day:
                continue
            if not valid_from or valid_from < now:
                valid_from = now
            valid_from = valid_from - datetime.timedelta(seconds=1)

            # get schedule valid-to date
            valid_to = s.get('properties', {}).get('valid-to', {}).get('values', [{}])[0].get('db_value')
            if valid_to and valid_to < now:
                continue
            if not valid_to or valid_to > last_day:
                valid_to = last_day
            valid_to = valid_to + datetime.timedelta(seconds=1)

            # get run times
            run_times = []
            for crontab in s.get('properties', {}).get('crontab', {}).get('values', []):
                if not crontab.get('value'):
                    continue

                try:
                    crontab_iter = croniter(crontab.get('value'), valid_from)
                except:
                    continue

                if valid_from < now:
                    run_time = crontab_iter.get_prev(datetime.datetime)
                else:
                    run_time = crontab_iter.get_next(datetime.datetime)

                while run_time <= valid_to:
                    run_times.append(run_time)
                    run_time = crontab_iter.get_next(datetime.datetime)
            if not run_times:
                continue
            run_times = sorted(list(set(run_times)))

            # get layout
            layout_id = s.get('properties', {}).get('layout', {}).get('values', [{}])[0].get('db_value')
            if not layout_id:
                self.write('No layout id!')
                continue
            layout = self.get_entities(entity_id=layout_id, limit=1, only_public=True)
            if not layout:
                continue

            # get layout-playlists
            layout_playlist_ids = self.get_relatives(ids_only=True, entity_id=layout_id, relationship_definition_keyname='child', entity_definition_keyname='sw-layout-playlist', only_public=True)
            if not layout_playlist_ids:
                continue
            layout_playlists = self.get_entities(entity_id=layout_playlist_ids, only_public=True)
            if not layout_playlists:
                continue

            for lp in layout_playlists:
                # get playlist
                playlist_id = lp.get('properties', {}).get('playlist', {}).get('values', [{}])[0].get('db_value')
                if not playlist_id:
                    continue
                playlist = self.get_entities(entity_id=playlist_id, limit=1, only_public=True)
                if not playlist:
                    continue

                # get playlist-media
                playlist_media_ids = self.get_relatives(ids_only=True, entity_id=playlist_id, relationship_definition_keyname='child', entity_definition_keyname='sw-playlist-media', only_public=True)
                if not playlist_media_ids:
                    continue
                playlist_medias = self.get_entities(entity_id=playlist_media_ids, only_public=True)
                if not playlist_medias:
                    continue

                for pm in playlist_medias:
                    # get media
                    media_id = pm.get('properties', {}).get('media', {}).get('values', [{}])[0].get('db_value')
                    if not media_id:
                        continue
                    media = self.get_entities(entity_id=media_id, limit=1, only_public=True)
                    if not media:
                        continue
                    if not media.get('properties', {}).get('type', {}).get('values', [{}])[0].get('value'):
                        continue

                    media_type = media.get('properties', {}).get('type', {}).get('values', [{}])[0].get('value', '').lower()
                    media_file = '%s://%s/piletilevi/file-%s' % (self.request.protocol, self.request.host, media.get('properties', {}).get('file', {}).get('values', [{}])[0].get('db_value')) if media.get('properties', {}).get('file', {}).get('values', [{}])[0].get('db_value', '') else media.get('properties', {}).get('url', {}).get('values', [{}])[0].get('value')
                    media_ratio = float(media.get('properties', {}).get('width', {}).get('values', [{}])[0].get('db_value', 1)) / float(media.get('properties', {}).get('height', {}).get('values', [{}])[0].get('db_value', 1))

                    media_delay = playlist.get('properties', {}).get('delay', {}).get('values', [{}])[0].get('value')
                    if pm.get('properties', {}).get('delay', {}).get('values', [{}])[0].get('value'):
                        media_delay = pm.get('properties', {}).get('delay', {}).get('values', [{}])[0].get('value')

                    if not media.get('properties', {}).get('url', {}).get('values', [{}])[0].get('value') and not media.get('properties', {}).get('file', {}).get('values', [{}])[0].get('db_value'):
                        continue

                    for t in run_times:
                        if playlist.get('properties', {}).get('valid-from', {}).get('values', [{}])[0].get('db_value'):
                            if playlist.get('properties', {}).get('valid-from', {}).get('values', [{}])[0].get('db_value') > t:
                                continue
                        if playlist.get('properties', {}).get('valid-to', {}).get('values', [{}])[0].get('db_value'):
                            if playlist.get('properties', {}).get('valid-to', {}).get('values', [{}])[0].get('db_value') < t:
                                continue
                        if pm.get('properties', {}).get('valid-from', {}).get('values', [{}])[0].get('db_value'):
                            if pm.get('properties', {}).get('valid-from', {}).get('values', [{}])[0].get('db_value') > t:
                                logging.debug(str(t) + ' ' + str(valid_from))
                                continue
                        if pm.get('properties', {}).get('valid-to', {}).get('values', [{}])[0].get('db_value'):
                            if pm.get('properties', {}).get('valid-to', {}).get('values', [{}])[0].get('db_value') < t:
                                continue
                        if media.get('properties', {}).get('valid-from', {}).get('values', [{}])[0].get('db_value'):
                            if media.get('properties', {}).get('valid-from', {}).get('values', [{}])[0].get('db_value') > t:
                                continue
                        if media.get('properties', {}).get('valid-to', {}).get('values', [{}])[0].get('db_value'):
                            if media.get('properties', {}).get('valid-to', {}).get('values', [{}])[0].get('db_value') < t:
                                continue

                        # schedule
                        schedule_dict.setdefault(int(time.mktime(t.timetuple())), {})['start'] = int(time.mktime(t.timetuple()))
                        schedule_dict.setdefault(int(time.mktime(t.timetuple())), {})['start_dt'] = str(t)
                        if not schedule_dict.setdefault(int(time.mktime(t.timetuple())), {}).get('cleanup', False):
                            schedule_dict.setdefault(int(time.mktime(t.timetuple())), {})['cleanup'] = bool(s.get('properties', {}).get('cleanup', {}).get('values', [{}])[0].get('db_value', False))
                        # playlist
                        schedule_dict.setdefault(int(time.mktime(t.timetuple())), {}).setdefault('playlists', {}).setdefault(lp.get('id'), {})['id'] = lp.get('id')
                        schedule_dict.setdefault(int(time.mktime(t.timetuple())), {}).setdefault('playlists', {}).setdefault(lp.get('id'), {})['top'] = lp.get('properties', {}).get('top', {}).get('values', [{}])[0].get('value', 0)
                        schedule_dict.setdefault(int(time.mktime(t.timetuple())), {}).setdefault('playlists', {}).setdefault(lp.get('id'), {})['left'] = lp.get('properties', {}).get('left', {}).get('values', [{}])[0].get('value', 0)
                        schedule_dict.setdefault(int(time.mktime(t.timetuple())), {}).setdefault('playlists', {}).setdefault(lp.get('id'), {})['width'] = lp.get('properties', {}).get('width', {}).get('values', [{}])[0].get('value', 100)
                        schedule_dict.setdefault(int(time.mktime(t.timetuple())), {}).setdefault('playlists', {}).setdefault(lp.get('id'), {})['height'] = lp.get('properties', {}).get('height', {}).get('values', [{}])[0].get('value', 100)
                        schedule_dict.setdefault(int(time.mktime(t.timetuple())), {}).setdefault('playlists', {}).setdefault(lp.get('id'), {})['zindex'] = lp.get('properties', {}).get('zindex', {}).get('values', [{}])[0].get('value', 1)
                        schedule_dict.setdefault(int(time.mktime(t.timetuple())), {}).setdefault('playlists', {}).setdefault(lp.get('id'), {})['pixels'] = bool(lp.get('properties', {}).get('in-pixels', {}).get('values', [{}])[0].get('db_value', False))
                        schedule_dict.setdefault(int(time.mktime(t.timetuple())), {}).setdefault('playlists', {}).setdefault(lp.get('id'), {})['loop'] = bool(lp.get('properties', {}).get('loop', {}).get('values', [{}])[0].get('db_value', False))
                        # media
                        schedule_dict.setdefault(int(time.mktime(t.timetuple())), {}).setdefault('playlists', {}).setdefault(lp.get('id'), {}).setdefault('media', {}).setdefault(pm.get('id'), {})['id'] = pm.get('id')
                        schedule_dict.setdefault(int(time.mktime(t.timetuple())), {}).setdefault('playlists', {}).setdefault(lp.get('id'), {}).setdefault('media', {}).setdefault(pm.get('id'), {})['top'] = pm.get('properties', {}).get('top', {}).get('values', [{}])[0].get('value')
                        schedule_dict.setdefault(int(time.mktime(t.timetuple())), {}).setdefault('playlists', {}).setdefault(lp.get('id'), {}).setdefault('media', {}).setdefault(pm.get('id'), {})['left'] = pm.get('properties', {}).get('left', {}).get('values', [{}])[0].get('value')
                        schedule_dict.setdefault(int(time.mktime(t.timetuple())), {}).setdefault('playlists', {}).setdefault(lp.get('id'), {}).setdefault('media', {}).setdefault(pm.get('id'), {})['width'] = pm.get('properties', {}).get('width', {}).get('values', [{}])[0].get('value')
                        schedule_dict.setdefault(int(time.mktime(t.timetuple())), {}).setdefault('playlists', {}).setdefault(lp.get('id'), {}).setdefault('media', {}).setdefault(pm.get('id'), {})['height'] = pm.get('properties', {}).get('height', {}).get('values', [{}])[0].get('value')
                        schedule_dict.setdefault(int(time.mktime(t.timetuple())), {}).setdefault('playlists', {}).setdefault(lp.get('id'), {}).setdefault('media', {}).setdefault(pm.get('id'), {})['duration'] = pm.get('properties', {}).get('duration', {}).get('values', [{}])[0].get('value')
                        schedule_dict.setdefault(int(time.mktime(t.timetuple())), {}).setdefault('playlists', {}).setdefault(lp.get('id'), {}).setdefault('media', {}).setdefault(pm.get('id'), {})['ordinal'] = pm.get('properties', {}).get('ordinal', {}).get('values', [{}])[0].get('value')
                        schedule_dict.setdefault(int(time.mktime(t.timetuple())), {}).setdefault('playlists', {}).setdefault(lp.get('id'), {}).setdefault('media', {}).setdefault(pm.get('id'), {})['stretch'] = bool(pm.get('properties', {}).get('stretch', {}).get('values', [{}])[0].get('db_value', False))
                        schedule_dict.setdefault(int(time.mktime(t.timetuple())), {}).setdefault('playlists', {}).setdefault(lp.get('id'), {}).setdefault('media', {}).setdefault(pm.get('id'), {})['type'] = media_type
                        schedule_dict.setdefault(int(time.mktime(t.timetuple())), {}).setdefault('playlists', {}).setdefault(lp.get('id'), {}).setdefault('media', {}).setdefault(pm.get('id'), {})['src'] = media_file
                        schedule_dict.setdefault(int(time.mktime(t.timetuple())), {}).setdefault('playlists', {}).setdefault(lp.get('id'), {}).setdefault('media', {}).setdefault(pm.get('id'), {})['delay'] = media_delay
                        schedule_dict.setdefault(int(time.mktime(t.timetuple())), {}).setdefault('playlists', {}).setdefault(lp.get('id'), {}).setdefault('media', {}).setdefault(pm.get('id'), {})['filename'] = media.get('properties', {}).get('file', {}).get('values', [{}])[0].get('value', 0)
                        if media_type == 'video':
                            schedule_dict.setdefault(int(time.mktime(t.timetuple())), {}).setdefault('playlists', {}).setdefault(lp.get('id'), {}).setdefault('media', {}).setdefault(pm.get('id'), {})['ratio'] = media_ratio
                            schedule_dict.setdefault(int(time.mktime(t.timetuple())), {}).setdefault('playlists', {}).setdefault(lp.get('id'), {}).setdefault('media', {}).setdefault(pm.get('id'), {})['mute'] = bool(pm.get('properties', {}).get('mute', {}).get('values', [{}])[0].get('db_value', 0))

        delete_keys_from_dict(schedule_dict)

        for s in schedule_dict.keys():
            for p in schedule_dict[s]['playlists'].keys():
                schedule_dict.setdefault(s, {}).setdefault('playlists', {}).setdefault(p, {})['media'] = sorted(schedule_dict.get(s, {}).get('playlists', {}).get(p, {}).get('media', {}).values(), key=itemgetter('ordinal'))
                for m in schedule_dict.get(s, {}).get('playlists', {}).get(p, {}).get('media', {}):
                    files_dict.setdefault(m.get('id'), {})['id'] = m.get('id')
                    files_dict.setdefault(m.get('id'), {})['type'] = m.get('type')
                    files_dict.setdefault(m.get('id'), {})['src'] = m.get('src')
                    files_dict.setdefault(m.get('id'), {})['filename'] = m.get('filename')
            schedule_dict.setdefault(s, {})['playlists'] = schedule_dict.get(s, {}).get('playlists', {}).values()

        return {
            'generated': str(now),
            'update_interval': update_interval,
            'schedule': sorted(schedule_dict.values(), key=itemgetter('start')),
            'files': sorted(files_dict.values(), key=itemgetter('id'))
        }




class ShowPlayer(myRequestHandler, Entity, Schedule):
    def get(self, entity_id):
        screen = self.get_entities(entity_id=entity_id, limit=1, only_public=True)
        if not screen:
            return self.missing()

        now = datetime.datetime.now()
        tomorrow = datetime.datetime(now.year, now.month, now.day) + datetime.timedelta(1)

        self.render('template/index.html',
            screen = screen,
            refresh_time = (tomorrow - now).seconds
        )




class ShowCacheManifest(myRequestHandler, Entity, Schedule):
    def get(self, entity_id):
        schedule = self.get_schedule(entity_id=entity_id)
        schedule_md5 = hashlib.md5(json.dumps(schedule['schedule'], sort_keys=True)).hexdigest()

        self.set_property(entity_id=entity_id, property_definition_keyname='sw-screen-last-check', value='%s' % datetime.datetime.now())

        self.add_header('Content-Type', 'text/cache-manifest')
        self.add_header('Cache-Control', 'private,max-age=0')
        self.render('template/cache.manifest',
            files = list({v['src']:v for v in schedule.get('files', {})}.values()),
            update_interval = int(schedule['update_interval']),
            schedule_md5 = schedule_md5,
            json_url = '%s://%s/piletilevi/%s/json' % (self.request.protocol, self.request.host, entity_id)
        )




class ShowPlayerJSON(myRequestHandler, Entity, Schedule):
    def get(self, entity_id):
        schedule = self.get_schedule(entity_id=entity_id)

        self.set_property(entity_id=entity_id, property_definition_keyname='sw-screen-last-update', value='%s' % datetime.datetime.now())

        self.json(schedule)




class ShowFile(myRequestHandler, Entity):
    def get(self, file_id):
        files = self.get_file(file_id)
        if not files:
            return self.missing()

        mediafile = files[0]

        mimetypes.init()
        mime = mimetypes.types_map.get('.%s' % mediafile.filename.lower().split('.')[-1], 'application/octet-stream')

        self.add_header('Content-Type', mime)
        self.add_header('Cache-Control', 'private,max-age=31536000')
        self.add_header('Content-Disposition', 'inline; filename="%s"' % mediafile.filename)
        self.write(mediafile.file)




class NoPage(myRequestHandler):
    def get(self, url):
        self.missing()




def delete_keys_from_dict(dict_del):
    for k in dict_del.keys():
        if isinstance(dict_del[k], dict):
            delete_keys_from_dict(dict_del[k])
        if dict_del[k] == None:
            del dict_del[k]
    return dict_del




# Command line options
options.define('debug',         help='run on debug mode',     type=str, default='False')
options.define('port',          help='run on the given port', type=int, default=8000)
options.define('host',          help='database host',         type=str)
options.define('database',      help='database name',         type=str)
options.define('user',          help='database user',         type=str)
options.define('password',      help='database password',     type=str)




handlers = [
    (r'/piletilevi/file-(.*)', ShowFile),
    (r'/piletilevi/(.*)/json', ShowPlayerJSON),
    (r'/piletilevi/(.*)/cache.manifest', ShowCacheManifest),
    (r'/piletilevi/(.*)/screenwerk.appcache', ShowCacheManifest),
    (r'/piletilevi/(.*)', ShowPlayer),
    (r'(.*)', NoPage),
]




class myApplication(web.Application):
    """
    Main Application handler. Imports controllers, settings, translations.

    """
    def __init__(self):
        # load settings
        settings = {
            'port':                 options.options.port,
            'debug':                True if str(options.options.debug).lower() == 'true' else False,
            'xsrf_coocies':         True,
            'cookie_secret':        '90897fasdf709sa8fv9sa0643vs',
            'static_path':          path.join(path.dirname(__file__), '..', 'static'),
            'database-host':        options.options.host,
            'database-database':    options.options.database,
            'database-user':        options.options.user,
            'database-password':    options.options.password,
        }

        logging.warning('\n\nTornado %s started\n' % version)

        web.Application.__init__(self, handlers, **settings)




if __name__ == '__main__':
    options.parse_command_line()
    httpserver.HTTPServer(myApplication(), xheaders=True).listen(options.options.port)
    ioloop.IOLoop.instance().start()
