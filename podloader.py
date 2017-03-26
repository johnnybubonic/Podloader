#!/usr/bin/env python3


import configparser
import argparse
import os
import re
import base64
import subprocess
import hashlib
import datetime
from io import BytesIO
# You might need to install these modules; they aren't in stdlib.
import pymysql
import magic
import gpgme
from mutagen.id3 import ID3, APIC, TALB, TDRC, TENC, TRCK, COMM, WXXX, TCON, TIT2, TPE1, TCOP
from mutagen.oggvorbis import OggVorbis
from mutagen.flac import Picture
from PIL import Image  # This is really pillowtalk for what I'm using. I don't think PIL proper ever released a py3k version.
# Note: also requires ffmpeg to be installed.

dflt_config_paths = ['~/.podloader.ini',
                    '~/.podloader/podloader.ini',
                    'podloader.ini',
                    'podloader.ini.dist']

def configParse(configfile = dflt_config_paths[-1]):
    # Here we find and parse the config, then return a dict of the values.
    # We COULD return a configparser object, but that's a PITA to reference.
    conf = configfile
    olddef = dflt_config_paths[-1]
    for i, item in enumerate(dflt_config_paths):
        dflt_config_paths[i] = os.path.expanduser(item)
    for i, item in enumerate(dflt_config_paths):
        if not dflt_config_paths[i].startswith('/'):
            dflt_config_paths[i] = '{0}/{1}'.format(os.path.dirname(os.path.realpath(__file__)), item)
    if configfile != olddef:
        conf = configfile
    else:
        for p in dflt_config_paths:
            if os.path.isfile(p):
                conf = p
                break
    defconf = dflt_config_paths[-1]
    config = configparser.ConfigParser()
    config._interpolation = configparser.ExtendedInterpolation()
    config.read([defconf, conf])
    config_dict = {s:dict(config.items(s)) for s in config.sections()}
    # Convert the booleans to pythonic booleans in the dict, convert to ints, etc.
    if config['mysql']['password'] == 'False':
        config_dict['mysql']['password'] = config['mysql'].getboolean('password')
    config_dict['gpg']['enabled'] = config['gpg'].getboolean('enabled')
    config_dict['mysql']['port'] = config['mysql'].getint('port')
    config_dict['tags']['season_pad'] = config['tags'].getint('season_pad')
    config_dict['tags']['episode_pad'] = config['tags'].getint('episode_pad')
    # Set some "magic" interpolation
    if not config_dict['mysql']['password']:
        config_dict['mysql']['conf'] = os.path.expanduser(config_dict['mysql']['conf'])
        mysqlconf = configparser.ConfigParser(allow_no_value = True)
        if os.path.isfile(config_dict['mysql']['conf']):
            mysqlconf.read(config_dict['mysql']['conf'])
            mysqlcnf_dict = {s:dict(mysqlconf.items(s)) for s in mysqlconf.sections()}
            mysqlcnf = mysqlcnf_dict['client' + config_dict['mysql']['confsec']]
            if 'host' in mysqlcnf:
                config_dict['mysql']['host'] = mysqlcnf['host']
            else:
                config_dict['mysql']['host'] = 'localhost'
            if 'ssl' in mysqlcnf:
                config_dict['mysql']['ssl'] = {}
                for c in ('ssl-ca','ssl-cert', 'ssl-key', 'ssl-cipher'):
                    if c in mysqlcnf:
                        newkey = c.replace('ssl-', '')
                        config_dict['mysql']['ssl'][newkey] = mysqlcnf[c]
            config_dict['mysql']['user'] = mysqlcnf['user']
            config_dict['mysql']['password'] = mysqlcnf['password']
            if 'port' in mysqlcnf:
                config_dict['mysql']['port'] = int(mysqlcnf['port'])
            else:
                config_dict['mysql']['port'] = 3306
            del config_dict['mysql']['confsec']
            mysqlcnf.clear()
            mysqlcnf_dict.clear()
            for s in mysqlconf.sections():
                mysqlconf.remove_section(s)
        else:
            exit('ERROR: You specified [mysql]password as False but did not provide a valid .my.cnf path!')
    config_dict['gpg']['keys'] = config_dict['gpg']['keys'].split(',')
    if len(config_dict['gpg']['keys']) >= 1:
        config_dict['gpg']['keys'][:] = [re.sub('^\s*(0x)?([0-9A-F]*)\s*',
                                        '\g<2>', x).upper() for x in config_dict['gpg']['keys']]
    if config_dict['gpg']['enabled'] == True:
        if config_dict['gpg']['homedir'] != '':
            config_dict['gpg']['homedir'] = os.path.expanduser(config_dict['gpg']['homedir'])
    config_dict['local']['path'] = os.path.expanduser(config_dict['local']['path'])
    config_dict['local']['mediadir'] = os.path.expanduser(config_dict['local']['mediadir'])
    os.makedirs(config_dict['local']['mediadir'], exist_ok = True)
    if config_dict['tags']['year'] == 'False':
        config_dict['tags']['year'] = config['tags'].getboolean('year')
    config_dict['tags']['img'] = os.path.expanduser(config_dict['tags']['img'])
    return(config_dict)

def confArgs(conf, args):
    conf['episode'] = {}
    conf['episode']['title'] = args.title
    conf['episode']['file_title'] = re.sub('[^A-Za-z0-9-]', '.', conf['episode']['title']).lower()
    conf['episode']['season'] = str(args.season).zfill(conf['tags']['season_pad'])
    conf['episode']['serial'] = str(args.episode).zfill(conf['tags']['episode_pad'])
    for i in ('season', 'episode'):
        del conf['tags'][i + '_pad']
    conf['episode']['id'] = 'S{0}E{1}'.format(str(conf['episode']['season']),
                                            str(conf['episode']['serial']))
    conf['episode']['pretty_title'] = '{0}: {1}'.format(conf['episode']['id'], conf['episode']['title'])
    if conf['tags']['track'] == 'EPISODE':
        conf['tags']['track'] = conf['episode']['serial']
    conf['tags']['url'] = re.sub('^(.*)SEASONEPISODE(.*)$',
                                '\g<1>' + conf['episode']['id'] + '\g<2>',
                                conf['tags']['url'])
    conf['tags']['url'] = re.sub('^(.*)SEASON(.*)$',
                                '\g<1>' + conf['episode']['season'] + '\g<2>',
                                conf['tags']['url'])
    conf['tags']['url'] = re.sub('^(.*)EPISODE(.*)$',
                                '\g<1>' + conf['episode']['serial'] + '\g<2>',
                                conf['tags']['url'])
    conf['local']['subdir'] = re.sub('^(.*)SEASONEPISODE(.*)$',
                                '\g<1>' + conf['episode']['id'] + '\g<2>',
                                conf['local']['subdir'])
    conf['local']['subdir'] = re.sub('^(.*)SEASON(.*)$',
                                '\g<1>' + conf['episode']['season'] + '\g<2>',
                                conf['local']['subdir'])
    conf['local']['subdir'] = re.sub('^(.*)EPISODE(.*)$',
                                '\g<1>' + conf['episode']['serial'] + '\g<2>',
                                conf['local']['subdir'])
    conf['local']['path'] = '{0}/{1}'.format(conf['local']['path'],
                                            conf['local']['subdir'].lower())
    if not conf['tags']['year']:
        conf['tags']['year'] = datetime.datetime.now().year
    conf['tags']['year'] = str(conf['tags']['year'])
    if not os.path.isdir(conf['local']['path']):
        os.makedirs(conf['local']['path'], exist_ok = True)
    del conf['local']['subdir']
    conf['episode']['raw'] = args.flacfile
    if args.flacfile:
        newpath = os.path.abspath(os.path.expanduser(args.flacfile))
        if os.path.isfile(newpath):
            conf['episode']['raw'] = newpath
        else:
            exit('ERROR: The FLAC file you specified does not seem to exist({0}). Check your path.'.format(newpath))
    else:
        dflt_flac_names = ['{0}.edited.flac'.format(conf['episode']['id'].lower()),
                        '{0}.final.flac'.format(conf['episode']['id'].lower()),
                        '{0}.flac'.format(conf['episode']['id'].lower())]
        for f in dflt_flac_names:
            if os.path.isfile('{0}/{1}'.format(conf['local']['path'], f)):
                conf['episode']['raw'] = '{0}/{1}'.format(conf['local']['path'], f)
                break
        if not conf['episode']['raw']:
            exit('ERROR: We cannot seem to locate a FLAC to convert. Try using the -f/--file argument.')
    magic_file = magic.open(magic.MAGIC_MIME)
    magic_file.load()
    if not magic_file.file(conf['episode']['raw']) == 'audio/x-flac; charset=binary':
        exit('ERROR: Your FLAC file does not seem to actually be FLAC.')
    conf['flac'] = {}
    conf['flac']['samples'] = subprocess.check_output(['metaflac',
                                                            '--show-total-samples',
                                                            '{0}'.format(conf['episode']['raw'])]).decode('utf-8').strip()
    conf['flac']['rate'] = subprocess.check_output(['metaflac',
                                                            '--show-sample-rate',
                                                            '{0}'.format(conf['episode']['raw'])]).decode('utf-8').strip()
    conf['flac']['rate'] = '{0:.2f}'.format(float(conf['flac']['rate']))
    rawfilepath = os.path.abspath(os.path.expanduser(args.raw_recording))
    if not os.path.isfile(rawfilepath):
        exit('ERROR: the raw recording evaluated to {0} but it does not seem to exist!'.format(rawfilepath))
    conf['episode']['recorded'] = (str(datetime.datetime.utcfromtimestamp(os.path.getmtime(rawfilepath)))).split('.')[0]
    conf['episode']['length'] = float(conf['flac']['samples'])/float(conf['flac']['rate'])
    conf['episode']['length'] = str(int(conf['episode']['length']))
    if args.now:
        timestamp = datetime.datetime.timestamp(datetime.datetime.now())
    else:
        timestamp = os.path.getmtime(conf['episode']['raw'])
    conf['episode']['sha'] = {}
    conf['episode']['size'] = {}
    conf['episode']['released'] = (str(datetime.datetime.utcnow())).split('.')[0]
    conf['episode']['month'] = datetime.datetime.fromtimestamp(timestamp).strftime('%m')
    conf['episode']['day'] = datetime.datetime.fromtimestamp(timestamp).strftime('%d')
    conf['episode']['file_title'] = re.sub('\.+', '.', conf['episode']['file_title'])
    conf['episode']['file_title'] = '{0}.{1}'.format(conf['episode']['id'].lower(),
                                                    re.sub('\.$',
                                                        '',
                                                        conf['episode']['file_title']))
    del conf['flac']
    if args.editor:
        del conf['tags']['editor']
        conf['episode']['editor'] = args.editor
    else:
        conf['episode']['editor'] = conf['tags']['editor']
    if conf['tags']['album'] == 'SEASON':
        conf['tags']['album'] = 'Season {0}'.format(conf['episode']['season'])
    conf['local']['mediadir'] = '{0}/S{1}/E{2}'.format(conf['local']['mediadir'],
                                                    conf['episode']['season'],
                                                    conf['episode']['serial'])
    os.makedirs(conf['local']['mediadir'], exist_ok = True)
    cc_base_url = 'https://creativecommons.org/licenses'
    conf['music'] = {}
    conf['music']['intro'] = {}
    conf['music']['intro']['artist'] = args.intro_artist
    conf['music']['intro']['title'] = args.intro_title
    conf['music']['intro']['copyright'] = args.intro_copyright
    conf['music']['intro']['link'] = args.intro_link
    if args.intro_copyrightlink:
        conf['music']['intro']['copyrightlink'] = args.intro_copyrightlink
    else:
        strp_cr = (re.sub('CC-?', '', args.intro_copyright, flags = re.I)).split()
        if len(strp_cr) != 2:
            exit('ERROR: You did not specify a copyright link and this does not seem to be a CC license!')
        conf['music']['intro']['copyrightlink'] = '{0}/{1}/{2}/'.format(
                                                    cc_base_url,
                                                    strp_cr[0].lower(),
                                                    strp_cr[1])
    conf['music']['outro'] = {}
    conf['music']['outro']['artist'] = args.outro_artist
    conf['music']['outro']['title'] = args.outro_title
    conf['music']['outro']['copyright'] = args.outro_copyright
    conf['music']['outro']['link'] = args.outro_link
    if args.intro_copyrightlink:
        conf['music']['outro']['copyrightlink'] = args.outro_copyrightlink
    else:
        strp_cr = (re.sub('CC-?', '', args.outro_copyright, flags = re.I)).split()
        conf['music']['outro']['copyrightlink'] = '{0}/{1}/{2}/'.format(
                                                    cc_base_url,
                                                    strp_cr[0].lower(),
                                                    strp_cr[1])
    return(conf)

def transcodeMP3(conf):
    mediatype = 'mp3'
    mediadir = '{0}/{1}'.format(conf['local']['mediadir'], mediatype)
    mediafile = '{0}/{1}.{2}'.format(mediadir,
                                    conf['episode']['file_title'],
                                    mediatype)
    if os.path.isfile(mediafile):
        os.remove(mediafile)
    os.makedirs(mediadir, exist_ok = True)
    print('{0}: Transcoding to {1}...'.format(datetime.datetime.now(), mediatype))
    subprocess.call(['ffmpeg', '-stats', '-loglevel', '0', '-i',
                    conf['episode']['raw'], '-b:a', '128k', '-ac','1', '-joint_stereo', '1',
                    mediafile])
    return(mediafile)

def transcodeOGG(conf):
    mediatype = 'ogg'
    mediadir = '{0}/{1}'.format(conf['local']['mediadir'], mediatype)
    mediafile = '{0}/{1}.{2}'.format(mediadir,
                                    conf['episode']['file_title'],
                                    mediatype)
    if os.path.isfile(mediafile):
        os.remove(mediafile)
    os.makedirs(mediadir, exist_ok = True)
    print('{0}: Transcoding to {1}...'.format(datetime.datetime.now(), mediatype))
    subprocess.call(['ffmpeg', '-stats', '-loglevel', '0', '-i',
                    conf['episode']['raw'], '-qscale:a', '8', '-ac','1', '-joint_stereo', '1',
                    mediafile])
    return(mediafile)

def imgConv(imgfile):
    # Rockbox (and probably some other clients) don't like progressive JPEGs and stuff. SO let's fix that.
    # Thanks to the io module, we don't even need to write a new file out.
    img_meta = {}
    magic_file = magic.open(magic.MAGIC_MIME)
    magic_file.load()
    img_meta['mime'] = magic_file.file(imgfile).split(';')[0]
    with Image.open(imgfile) as img_data:
        img_meta['height'] = img_data.height
        img_meta['width'] = img_data.width
        img_meta['depth'] = img_data.bits
        # And we need to remove the progressiveness if it exists.
        if 'progressive' in img_data.info.keys():
            # This isn't strictly necessary since we explicitly specify format = 'JPEG' when saving.
            #if p.format in ('JPEG', 'PNG'):
            #    imgformat = img_data.format
            #else:
            #    imgformat = 'PNG'
            img_stream = BytesIO()
            img_data.save(img_stream,
                          format = 'JPEG',
                          dpi = img_data.info.get('dpi'),
                          quality = 95,
                          optimize = True,
                          progressive = False,
                          icc_profile = img_data.info.get('icc_profile'),
                          subsampling = 'keep')
            # Be kind, please rewind.
            # Don't sue me, Blockbuster. lol
            img_stream.seek(0)
            img_stream = img_stream.read()
        else:
            with open(imgfile) as f:
                img_stream = f.read()
    return(img_stream, img_meta)


def tagMP3(conf, mediafile):
    # http://id3.org/id3v2.3.0#Attached_picture
    # http://id3.org/id3v2.4.0-frames (section 4.14)
    # https://stackoverflow.com/questions/7275710/mutagen-how-to-detect-and-embed-album-art-in-mp3-flac-and-mp4
    # https://stackoverflow.com/questions/409949/how-do-you-embed-album-art-into-an-mp3-using-python
    img_stream, img_meta = imgConv(conf['tags']['img'])
    print('{0}: Now adding tags to {1}...'.format(datetime.datetime.now(), mediafile))
    tag = ID3(mediafile)
    tag.add(TALB(encoding = 3,
                 text = [conf['tags']['album']]))
    tag.add(APIC(encoding = 3,
                 mime = img_meta['mime'],
                 type = 3,
                 desc = '{0} ({1})'.format(conf['tags']['artist'],
                                           conf['tags']['comment']),
                 data = img_stream))
    tag.add(TDRC(encoding = 3,
                 text = ['{0}.{1}.{2}'.format(conf['tags']['year'],
                                              conf['episode']['month'],
                                              conf['episode']['day'])]))
    tag.add(TENC(encoding = 3,
                 text = [conf['tags']['encoded']]))
    tag.add(TRCK(encoding = 3,
                 text = [conf['tags']['track']]))
    tag.add(COMM(encoding = 3,
                 #lang = '\x00\x00\x00',  # I'm not sure why we're sending three NULLs, but best to be explicit.
                 lang = 'eng',
                 desc = 'Description provided by Podloader. https://git.square-r00t.net/Podloader',
                 text = [conf['tags']['comment']]))
    tag.add(WXXX(encoding = 3,
                 desc = conf['tags']['artist'],
                 url = conf['tags']['url']))
    tag.add(TCON(encoding = 3,
                 text = [conf['tags']['genre']]))
    tag.add(TIT2(encoding = 3,
                 text = [conf['episode']['pretty_title']]))
    tag.add(TPE1(encoding = 3,
                 text = [conf['tags']['artist']]))
    tag.add(TCOP(encoding = 3,
                 text = [conf['tags']['copyright']]))
    tag.save()

def tagOGG(conf, mediafile):
    # https://mutagen.readthedocs.io/en/latest/user/vcomment.html
    # https://wiki.xiph.org/VorbisComment#METADATA_BLOCK_PICTURE
    # https://xiph.org/flac/format.html#metadata_block_picture
    # https://github.com/quodlibet/mutagen/issues/200
    img_stream, img_meta = imgConv(conf['tags']['img'])
    picture = Picture()
    picture.data = img_stream
    picture.type = 3
    picture.description = '{0} ({1})'.format(conf['tags']['artist'],
                                             conf['tags']['comment'])
    picture.mime = img_meta['mime']
    picture.width = img_meta['width']
    picture.height = img_meta['height']
    picture.depth = img_meta['depth']
    picture.desc = '{0} ({1})'.format(conf['tags']['artist'],
                                      conf['tags']['comment'])
    containered_data = picture.write()
    encoded_data = base64.b64encode(containered_data)
    img_tag = encoded_data.decode('ascii')
    print('{0}: Now adding tags to {1}...'.format(datetime.datetime.now(), mediafile))
    tag = OggVorbis(mediafile)
    tag['TITLE'] = conf['episode']['pretty_title']
    tag['ARTIST'] = conf['tags']['artist']
    tag['ALBUM'] = conf['tags']['album']
    tag['DATE'] = '{0}.{1}.{2}'.format(conf['tags']['year'],
                                        conf['episode']['month'],
                                        conf['episode']['day'])
    tag['TRACKNUMBER'] = conf['tags']['track']
    tag['GENRE'] = conf['tags']['genre']
    tag['DESCRIPTION'] = conf['tags']['comment']
    tag['COPYRIGHT'] = conf['tags']['copyright']
    tag['CONTACT'] = conf['tags']['url']
    tag['ENCODED-BY'] = conf['tags']['encoded']
    tag['ENCODER'] = conf['tags']['encoded']
    tag['METADATA_BLOCK_PICTURE'] = [img_tag]
    tag.save()

def getSHA256(mediafile):
    print('{0}: Generating SHA256 for {1}...'.format(datetime.datetime.now(),
                                                    mediafile))
    filehash = hashlib.sha256()
    with open(mediafile, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            filehash.update(chunk)
    return(filehash.hexdigest())

def getSize(mediafile):
    filesize = os.path.getsize(mediafile)
    return(filesize)

def dbEntry(conf):
    print('{0}: Inserting into the {1}.{2}@{3} table...'.format(datetime.datetime.now(),
                                                                conf['mysql']['db'],
                                                                conf['mysql']['table'],
                                                                conf['mysql']['host']))
    ssl = False
    if 'ssl' in conf['mysql']:
        ssl = conf['mysql']['ssl']
    vals = "'{0}','{1}','{2}','{3}','{4}','{5}','{6}','{7}','{8}','{9}','{10}','{11}','{12}','{13}','{14}','{15}','{16}','{17}','{18}','{19}'".format(conf['episode']['id'],
            conf['episode']['file_title'],
            conf['episode']['sha']['mp3'],
            conf['episode']['sha']['ogg'],
            conf['episode']['size']['mp3'],
            conf['episode']['size']['ogg'],
            conf['episode']['length'],
            re.sub("'", "\\'", conf['episode']['editor']),
            re.sub("'", "\\'", conf['music']['intro']['title']),
            re.sub("'", "\\'", conf['music']['intro']['artist']),
            conf['music']['intro']['link'],
            re.sub("'", "\\'", conf['music']['intro']['copyright']),
            conf['music']['intro']['copyrightlink'],
            re.sub("'", "\\'", conf['music']['outro']['title']),
            re.sub("'", "\\'", conf['music']['outro']['artist']),
            conf['music']['outro']['link'],
            re.sub("'", "\\'", conf['music']['outro']['copyright']),
            conf['music']['outro']['copyrightlink'],
            conf['episode']['recorded'],
            conf['episode']['released'])


    conn = pymysql.connect(host = conf['mysql']['host'],
                        port = conf['mysql']['port'],
                        user = conf['mysql']['user'],
                        passwd = conf['mysql']['password'],
                        db = conf['mysql']['db'],
                        ssl = ssl,
                        autocommit = True)
    cur = conn.cursor()
    query = 'INSERT INTO {0} ({1}) VALUES ({2})'.format(conf['mysql']['table'],
                                                conf['mysql']['cols'],
                                                vals)
    try:
        cur.execute(query)
        cur.close()
        conn.close()
    except:
        print('{0}: There seems to have been some error when inserting into the DB. Check access (or it is a dupe).'.format(
                                                datetime.datetime.now()))

def signEp(mediatype, conf):
    # No reason to call this for each file. Fix.
    os.makedirs('{0}/gpg'.format(conf['local']['mediadir']), exist_ok = True)
    sigfile = '{0}/gpg/{1}.{2}.asc'.format(conf['local']['mediadir'],
                                            conf['episode']['file_title'],
                                            mediatype)
    os.environ['GNUPGHOME'] = conf['gpg']['homedir']
    vrfykeys = []
    sigs = {}
    gpg = gpgme.Context()
    gpg.armor = True
    for k in conf['gpg']['keys']:
        if gpg.get_key(k, True).can_sign:
            # it seems pygpgme does not allow signing with subkeys. sad day. gpg.signkeys complains if you pass it Subkey objects.
            #subkeys = []
            #for i in gpg.get_key(k, True).subkeys:
            #    subkeys.append(i.fpr)
            #indexnum = [x for x, s in enumerate(subkeys) if k in s][0]
            #vrfykeys.append(gpg.get_key(k, True).subkeys[indexnum].fpr)
            if gpg.get_key(k, True).subkeys[0].fpr not in vrfykeys:
                vrfykeys.append(gpg.get_key(k, True).subkeys[0].fpr)
    data_in = '{0}/{1}/{2}.{3}'.format(conf['local']['mediadir'],
                                            mediatype,
                                            conf['episode']['file_title'],
                                            mediatype)
    print('{0}: Checking for existing GPG signatures (and skipping if we signed)...'.format(datetime.datetime.now()))
    if os.path.isfile(sigfile):
        with open(sigfile, 'rb') as s:
            with open(data_in, 'rb') as f:
                for k in gpg.verify(s, f, None):
                    try:
                        sigs[gpg.get_key(k.fpr, True).subkeys[0].fpr] = True
                    except:
                        pass
    for k in vrfykeys:
        if k not in sigs:
            sigkeys = []
            if gpg.get_key(k, True).can_sign:
                print('{0}: Signing with key {1}...'.format(datetime.datetime.now(),
                                                            k))
                sigkeys.append(gpg.get_key(k, True))
                gpg.signers = sigkeys
                with open(sigfile, 'ab') as s:
                    with open(data_in, 'rb') as f:
                        gpg.sign(f, s, gpgme.SIG_MODE_DETACH)
    return(sigfile)

def uploadFile(conf):
    # TODO: Can we do this via paramiko? That way we can check for the destination dir
    # and create if it doesn't exist.
    # Also, no reason to call this for each file.
    print('{0}: Syncing files to server...'.format(datetime.datetime.now()))
    subprocess.call(['rsync',
                    '-a',
                    '{0}'.format(conf['local']['mediadir']),
                    '{0}@{1}:{2}S{3}/.'.format(conf['rsync']['user'],
                                                conf['rsync']['host'],
                                                conf['rsync']['path'],
                                                conf['episode']['season'])])

def argParse():
    parser = argparse.ArgumentParser(
                            description = 'PodLoader - a script to assist in Textpattern-powered podcasts',
                            prog = 'podloader v1.1')
    requiredArgs = parser.add_argument_group('REQUIRED arguments')
    requiredArgs.add_argument('-t',
                            '--title',
                            dest = 'title',
                            required = True,
                            help = "The episode's title (as it will appear in meta information).")
    requiredArgs.add_argument('-e',
                            '--episode',
                            dest = 'episode',
                            required = True,
                            type = int,
                            help = "The episode number for this episode.")
    requiredArgs.add_argument('-s',
                            '--season',
                            dest = 'season',
                            required = True,
                            type = int,
                            help = "The season number this episode is in.")
    requiredArgs.add_argument('-r',
                            '--raw-recording',
                            dest = 'raw_recording',
                            required = True,
                            help = "The path to a single-track *raw* recording. This file is used to get the timestamp of recording.")
    requiredArgs.add_argument('-i:a',
                            '--intro-artist',
                            dest = 'intro_artist',
                            required = True,
                            help = "The artist for the intro music.")
    requiredArgs.add_argument('-i:t',
                            '--intro-title',
                            dest = 'intro_title',
                            required = True,
                            help = "The title for the intro music.")
    requiredArgs.add_argument('-i:l',
                            '--intro-link',
                            dest = 'intro_link',
                            required = True,
                            help = "The link to the intro track (i.e. page to more information about the track).")
    requiredArgs.add_argument('-i:c',
                            '--intro-copyright',
                            dest = 'intro_copyright',
                            required = True,
                            help = "The copyright for the intro music. If it's a Creative Commons type, you do not need to include a copyright link. e.g. '-i:c \"CC-BY-SA 3.0\"'")
    requiredArgs.add_argument('-o:a',
                            '--outro-artist',
                            dest = 'outro_artist',
                            required = True,
                            help = "The artist for the outro music.")
    requiredArgs.add_argument('-o:t',
                            '--outro-title',
                            dest = 'outro_title',
                            required = True,
                            help = "The title for the outro music.")
    requiredArgs.add_argument('-o:l',
                            '--outro-link',
                            dest = 'outro_link',
                            required = True,
                            help = "The link to the outro track (i.e. page to more information about the track).")
    requiredArgs.add_argument('-o:c',
                            '--outro-copyright',
                            dest = 'outro_copyright',
                            required = True,
                            help = "The copyright for the outro music. If it's a Creative Commons type, you do not need to include a copyright link. e.g. '-i:c \"CC-BY-SA 3.0\"'")
    parser.add_argument('-i:cl',
                        '--intro-copyrightlink',
                        dest = 'intro_copyrightlink',
                        default = False,
                        help = "The link to the copyright terms for the intro. Optional if it's a CC license.")
    parser.add_argument('-o:cl',
                        '--outro-copyrightlink',
                        default = False,
                        dest = 'outro_copyrightlink',
                        help = "The link to the copyright terms for the outro. Optional if it's a CC license.")
    parser.add_argument('-d',
                        '--editor',
                        dest = 'editor',
                        help = 'The audio editor for the episode. Can (should) contain HTML link to editor (e.g. \'<a href="https://editorname.tld">Editor Name</a>\'')
    parser.add_argument('-f',
                        '--file',
                        dest = 'flacfile',
                        default = False,
                        help = "The (final edit) FLAC file to be used for the episode. If not specified, we'll try to guess.")
    parser.add_argument('-n',
                        '--now',
                        dest = 'now',
                        default = False,
                        action = 'store_true',
                        help = "Instead of getting the date based on the time of the file, use today's date (for media tags).")
    try:
        args = parser.parse_args()
        print('{0}: Starting.'.format(datetime.datetime.now()))
    except (NameError, TypeError):
        parser.print_help()
        exit(1)
    return(args)

def main():
    conf = confArgs(configParse(), argParse())
    mp3 = transcodeMP3(conf)
    tagMP3(conf, mp3)
    ogg = transcodeOGG(conf)
    tagOGG(conf, ogg)
    conf['episode']['sha']['mp3'] = getSHA256(mp3)
    conf['episode']['sha']['ogg'] = getSHA256(ogg)
    conf['episode']['size']['mp3'] = getSize(mp3)
    conf['episode']['size']['ogg'] = getSize(ogg)
    dbEntry(conf)
    signEp('mp3', conf)
    signEp('ogg', conf)
    uploadFile(conf)
    print('{0}: Finished.'.format(datetime.datetime.now()))

if __name__ == '__main__':
    main()
