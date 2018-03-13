#!/usr/bin/env python3

# https://sysadministrivia.com/news/every-new-beginning

import hashlib
import argparse
import os
import glob
from urllib.request import urlopen
try:
    from lxml import etree
except ImportError:
    import xml.etree.ElementTree as etree
# TODO: GPG verification too

baseurl = 'https://sysadministrivia.com'

feeds = {'itunes':'/feed/itunes.xml',
         'google':'/feed/google.xml',
         'mp3':'/feed/podcast.xml',
         'ogg':'/feed/oggcast.xml'}

def getXML(baseurl, feeds, args):
    xml = {}
    print('Fetching feed(s) XML, please wait...')
    for feed in args.feedlist:
        with urlopen(baseurl + feeds[feed]) as url:
            xml[feed] = etree.fromstring(url.read())
    return(xml)

def getSums(xml, args):
    sums = {}
    for feed in args.feedlist:
        sums[feed] = {}
        for episode in xml[feed].findall('channel/item'):
            epID = episode.find('title').text.split(':')[0]
            sums[feed][epID] = {}
            sums[feed][epID]['uri'] = episode.find('enclosure').attrib['url']
            sums[feed][epID]['guid'] = episode.find('guid').text
            sums[feed][epID]['file'] = os.path.basename(sums[feed][epID]['uri'])
            if args.livesums:
                livesha = hashlib.sha256()
                print('{0}({1}): Fetching/verifying live sum...'.format(epID, feed))
                with urlopen(sums[feed][epID]['uri']) as url:
                    for chunk in iter(lambda: url.read(4096), b''):
                        livesha.update(chunk)
                sums[feed][epID]['livesha'] = livesha.hexdigest()
                if sums[feed][epID]['livesha'] != sums[feed][epID]['guid']:
                    print('\t\tWARNING: GUID {1} does not match live sum {1}!'.format(sums[feed][epID]['guid'],
                                                                                      sums[feed][epID]['livesha']))
    if args.locdir:
        localdir = os.path.abspath(os.path.expanduser(args.locdir))
        if not os.path.isdir(localdir):
            exit('ERROR: Directory {0} does not exist!'.format(args.locdir))
        episodes = sums[args.feedlist[0]]
        print('Checking local files...')
        for episode in episodes.keys():
            filename = episodes[episode]['file']
            guid = episodes[episode]['guid']
            for localfile in glob.iglob('{0}/**/{1}'.format(localdir, filename), recursive = True):
                localsha = hashlib.sha256()
                print('Checking {0}...'.format(localfile))
                with open(localfile, 'rb') as f:
                    for chunk in iter(lambda: f.read(4096), b''):
                        localsha.update(chunk)
                if localsha.hexdigest() != guid:
                    print('WARNING: GUID {0} does not match local hash {1}!'.format(guid, localsha.hexdigest()))
        print('Finished checking local files.')
    if not args.locdir and not args.livesums:
        for episode in sums[args.feedlist[0]].keys():
            print(episode + ':')
            for feed in args.feedlist:
                print('\t{0:6}: {1}'.format(feed,
                                        sums[feed][episode]['guid']))
    return(sums)

def parseArgs():
    args = argparse.ArgumentParser(description = 'Sysadministrivia Verifier',
                                   epilog = 'https://git.square-r00t.net/Podloader')
    args.add_argument('-l',
                      '--live',
                      dest = 'livesums',
                      action = 'store_true',
                      help = 'If specified, calculate the sums live from the site and compare against the GUIDs served. This can take a long time.')
    args.add_argument('-f',
                      '--feed',
                      choices = ['itunes', 'google', 'mp3', 'ogg'],
                      dest = 'feedlist',
                      nargs = '*',
                      default = ['itunes', 'google', 'mp3', 'ogg'],
                      help = 'Which feed(s) to check. The default is all. Multiple can be specified via "-f itunes google" etc.')
    args.add_argument('-d',
                      '--directory',
                      dest = 'locdir',
                      metavar = 'path',
                      default = False,
                      help = 'If specified, a directory where local copies of the episodes exist. (e.g. ~/gPodder/Downloads/Sysadministrivia)')
    return(args)

def main():
    args = parseArgs().parse_args()
    xml = getXML(baseurl, feeds, args)
    sums = getSums(xml, args)

if __name__ == '__main__':
    main()
